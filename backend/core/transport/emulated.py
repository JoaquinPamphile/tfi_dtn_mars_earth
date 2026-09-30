"""Runtime de un hop dirigido sobre el motor de eventos ya existente.

Una SyncUnit espera en la cola de su enlace ``source_node → destination_node``.
Durante un ``Contact`` abierto se serializa como mucho una unidad. Puede
empezar en ``contact.start_time_sim`` si el reloj está ahí y la carga completa
entra antes de ``contact.end_time_sim``. Si no entra, sigue encolada.

Al terminar la serialización el enlace queda libre y puede empezar otra
unidad. La llegada se programa aparte, en
``fin_de_serialización + propagation_delay_s``. Esa propagación no ocupa
tasa ni entra en ``fits``. Puede ocurrir después del cierre.

El cierre natural no corta una serialización ya aceptada ni una llegada ya
programada. El cierre forzado sí invalida la serialización en curso, cancela
su fin y reencola la misma unidad completa, con el mismo ``submission_order``.

La entrega al receptor es un ``TransportDelivery`` hacia los handlers
registrados. Este módulo no conoce nodos de aplicación ni reenvío.
"""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field

from core.contact.contact import Contact, LogicalNode
from core.contact.plan import ContactPlan
from core.simulation.engine import SimulationEngine
from core.simulation.scheduler import ScheduledAction
from core.sync.unit import SyncUnit
from core.trace.types import SimulationEventType
from core.transport.capacity import (
    fits,
    transmission_seconds,
    transmitted_before_interrupt_bytes,
)
from core.transport.queue import OrderedFitQueue, queue_order
from core.transport.transmission import TransmissionAttempt


@dataclass(frozen=True, slots=True)
class TransportDelivery:
    """Llegada de una SyncUnit al extremo receptor de este hop.

    El instante es el de arribo en el reloj de simulación. No es la
    persistencia de una aplicación ni una cola de store-and-forward.
    """

    time_sim: float
    event_type: str
    sync_unit: SyncUnit
    contact_id: str


DeliveryHandler = Callable[[TransportDelivery], None]


@dataclass
class _LinkState:
    queue: OrderedFitQueue = field(default_factory=OrderedFitQueue)
    transmitting: SyncUnit | None = None
    current_attempt: TransmissionAttempt | None = None
    open_contact: Contact | None = None


class EmulatedTransport:
    """Enlace emulado de un hop, impulsado por ``SimulationEngine``.

    El plan solo resuelve el ``Contact`` de una apertura, un cierre o un
    corte. Este objeto no programa el plan. Quien integra programa
    ``CONTACT_OPEN`` y ``CONTACT_CLOSE``, o llama ``open_contact`` y
    ``close_contact`` con el reloj ya situado en el instante científico.

    ``submission_order`` lo asigna el motor al presentar la unidad. Un
    reencolado por interrupción conserva ese valor.
    """

    def __init__(self, engine: SimulationEngine, contact_plan: ContactPlan) -> None:
        self._engine = engine
        self._plan = contact_plan
        self._links: dict[tuple[LogicalNode, LogicalNode], _LinkState] = {}
        self._in_flight: dict[str, SyncUnit] = {}
        self._attempts: dict[str, TransmissionAttempt] = {}
        self._next_attempt_seq = 0
        self._pending_deliveries: list[TransportDelivery] = []
        self._delivery_handlers: list[DeliveryHandler] = []
        engine.register_handler(
            SimulationEventType.CONTACT_OPEN.value, self._on_contact_open
        )
        engine.register_handler(
            SimulationEventType.CONTACT_CLOSE.value, self._on_contact_close
        )
        engine.register_handler(
            SimulationEventType.TRANSMISSION_COMPLETED.value,
            self._on_transmission_completed,
        )
        engine.register_handler(
            SimulationEventType.ARRIVED_AT_RELAY.value, self._on_arrival
        )
        engine.register_handler(
            SimulationEventType.ARRIVED_AT_EARTH_TRANSPORT.value, self._on_arrival
        )
        engine.register_handler(
            SimulationEventType.ARRIVED_AT_MARS_TRANSPORT.value, self._on_arrival
        )

    def submit(self, unit: SyncUnit) -> None:
        """Presenta una SyncUnit a la cola de su enlace dirigido.

        Reemplaza ``submission_order`` con el siguiente valor del motor,
        mediante una copia. El objeto recibido no se muta. Si la unidad ya
        está en vuelo, encolada o serializándose, rechaza la presentación.
        Ese rechazo ocurre después de consumir el orden. Con el contacto
        abierto y el enlace libre, intenta transmitir en el acto.
        """
        unit = unit.model_copy(
            update={"submission_order": self._engine.allocate_submission_order()}
        )
        if unit.sync_unit_id in self._in_flight:
            raise ValueError(f"la SyncUnit ya está en vuelo: {unit.sync_unit_id}")
        link = self._link(unit.source_node, unit.destination_node)
        if link.queue.contains(unit.sync_unit_id):
            raise ValueError(f"la SyncUnit ya está encolada: {unit.sync_unit_id}")
        if (
            link.transmitting is not None
            and link.transmitting.sync_unit_id == unit.sync_unit_id
        ):
            raise ValueError(
                f"la SyncUnit ya se está transmitiendo: {unit.sync_unit_id}"
            )
        link.queue.add(unit)
        self._engine.emit_trace(
            SimulationEventType.SYNC_UNIT_QUEUED.value,
            _unit_payload(unit),
            entity_id=unit.sync_unit_id,
        )
        self._try_transmit(unit.source_node, unit.destination_node)

    def register_delivery_handler(self, handler: DeliveryHandler) -> None:
        """Registra quién recibe cada llegada de este hop."""
        self._delivery_handlers.append(handler)

    def poll_deliveries(self) -> tuple[TransportDelivery, ...]:
        """Devuelve y vacía las llegadas todavía no consultadas."""
        pending = tuple(self._pending_deliveries)
        self._pending_deliveries.clear()
        return pending

    def open_contact(self, contact: Contact) -> None:
        """Abre la ventana en su enlace e intenta transmitir.

        El inicio de serialización es ``engine.now``, no un instante guardado
        aparte. Puede coincidir con ``contact.start_time_sim``. Otra ventana
        ya abierta en el mismo enlace queda reemplazada por esta. No es un
        error. Una cola vacía no programa transmisión.
        """
        link = self._link(contact.source, contact.destination)
        link.open_contact = contact
        self._try_transmit(contact.source, contact.destination)

    def close_contact(self, contact: Contact) -> None:
        """Cierra la ventana si es la que está abierta en ese enlace.

        No interrumpe la serialización en curso ni cancela una llegada que
        ya está propagándose. Libera las unidades que no cabían en esta
        ventana para que un contacto posterior pueda evaluarlas. Cerrar
        cuando no hay esa ventana abierta no hace nada.
        """
        link = self._link(contact.source, contact.destination)
        if (
            link.open_contact is not None
            and link.open_contact.contact_id == contact.contact_id
        ):
            link.open_contact = None
            link.queue.release_contact()

    def force_close_contact(self, contact_id: str, failure_id: str) -> None:
        """Cierra ya la ventana e interrumpe la serialización de ese contacto.

        Una llegada ya programada no se cancela. Un ``contact_id`` ausente
        del plan no hace nada. No consulta un plan de fallos: ``failure_id``
        solo queda registrado en el hecho de interrupción.
        """
        try:
            contact = self._plan.get(contact_id)
        except KeyError:
            return
        link = self._link(contact.source, contact.destination)
        if (
            link.current_attempt is not None
            and link.current_attempt.valid
            and link.current_attempt.contact_id == contact_id
        ):
            self._interrupt_attempt(link, failure_id)
        if link.open_contact is not None and link.open_contact.contact_id == contact_id:
            link.open_contact = None
            link.queue.release_contact()

    def queued(self) -> tuple[SyncUnit, ...]:
        """Unidades que esperan, en orden ``(created_at_sim, submission_order)``."""
        units: list[SyncUnit] = []
        for link in self._links.values():
            units.extend(link.queue.iter_snapshot())
        return tuple(sorted(units, key=queue_order))

    def in_flight(self) -> tuple[SyncUnit, ...]:
        """Unidades serializándose o propagándose, todavía sin entregar."""
        return tuple(sorted(self._in_flight.values(), key=queue_order))

    def withdraw(self, sync_unit_id: str) -> bool:
        """Quita una unidad que espera. No toca la que está en vuelo."""
        for link in self._links.values():
            if link.queue.withdraw(sync_unit_id):
                return True
        return False

    def _link(self, source: LogicalNode, destination: LogicalNode) -> _LinkState:
        key = (source, destination)
        if key not in self._links:
            self._links[key] = _LinkState()
        return self._links[key]

    def _on_contact_open(self, action: ScheduledAction) -> None:
        contact = self._plan.get(str(action.entity_id))
        self.open_contact(contact)

    def _on_contact_close(self, action: ScheduledAction) -> None:
        contact = self._plan.get(str(action.entity_id))
        self.close_contact(contact)

    def _try_transmit(self, source: LogicalNode, destination: LogicalNode) -> None:
        link = self._link(source, destination)
        if link.transmitting is not None:
            return
        contact = link.open_contact
        if contact is None:
            return
        now = self._engine.now
        if now >= contact.end_time_sim:
            return

        def _cabe(unit: SyncUnit) -> bool:
            return fits(
                unit.payload_size_bytes,
                contact.data_rate_bps,
                start_time_sim=now,
                end_time_sim=contact.end_time_sim,
            )

        unit = link.queue.pop_next_fitting(contact_id=contact.contact_id, fits=_cabe)
        if unit is None:
            return
        duration = transmission_seconds(unit.payload_size_bytes, contact.data_rate_bps)
        bits = unit.payload_size_bytes * 8
        link.transmitting = unit
        self._in_flight[unit.sync_unit_id] = unit
        tx_complete = now + duration
        arrival_time = tx_complete + contact.propagation_delay_s
        transmission_id = self._new_transmission_id(unit.sync_unit_id)
        attempt = TransmissionAttempt(
            transmission_id=transmission_id,
            unit=unit,
            contact_id=contact.contact_id,
            start_time_sim=now,
            scheduled_complete_time=tx_complete,
            payload_size_bytes=unit.payload_size_bytes,
            data_rate_bps=contact.data_rate_bps,
        )
        self._attempts[transmission_id] = attempt
        link.current_attempt = attempt
        payload = _unit_payload(unit)
        payload.update(
            {
                "contact_id": contact.contact_id,
                "data_rate_bps": contact.data_rate_bps,
                "transmission_seconds": duration,
                "bits_transmitted": bits,
                "propagation_delay_s": contact.propagation_delay_s,
                "transmission_start_sim": now,
                "transmission_end_sim": tx_complete,
                "arrival_time_sim": arrival_time,
                "transmission_id": transmission_id,
            }
        )
        self._engine.emit_trace(
            SimulationEventType.TRANSMISSION_STARTED.value,
            payload,
            entity_id=unit.sync_unit_id,
        )
        self._engine.schedule(
            time=tx_complete,
            event_type=SimulationEventType.TRANSMISSION_COMPLETED.value,
            payload=payload,
            entity_id=unit.sync_unit_id,
        )

    def _on_transmission_completed(self, action: ScheduledAction) -> None:
        transmission_id = action.payload.get("transmission_id")
        attempt = (
            self._attempts.get(str(transmission_id))
            if transmission_id is not None
            else None
        )
        if attempt is None or not attempt.valid:
            return
        unit_id = str(action.entity_id)
        source = LogicalNode(action.payload["source_node"])
        destination = LogicalNode(action.payload["destination_node"])
        link = self._link(source, destination)
        if link.current_attempt is attempt:
            link.current_attempt = None
        link.transmitting = None
        arrival_time = float(action.payload["arrival_time_sim"])
        self._engine.schedule(
            time=arrival_time,
            event_type=_arrival_event_type(destination),
            payload=dict(action.payload),
            entity_id=unit_id,
        )
        self._try_transmit(source, destination)

    def _interrupt_attempt(self, link: _LinkState, failure_id: str) -> None:
        attempt = link.current_attempt
        if attempt is None or not attempt.valid:
            return
        attempt.valid = False
        now = self._engine.now
        duration = attempt.scheduled_complete_time - attempt.start_time_sim
        elapsed = max(0.0, now - attempt.start_time_sim)
        fraction_sent = 0.0 if duration <= 0 else min(1.0, elapsed / duration)
        bytes_sent = transmitted_before_interrupt_bytes(
            elapsed_sim=elapsed,
            data_rate_bps=attempt.data_rate_bps,
            payload_size_bytes=attempt.payload_size_bytes,
        )
        cancelled = self._engine.cancel(
            lambda action: (
                action.event_type == SimulationEventType.TRANSMISSION_COMPLETED.value
                and action.payload.get("transmission_id") == attempt.transmission_id
            )
        )
        unit = attempt.unit
        self._in_flight.pop(unit.sync_unit_id, None)
        if unit not in link.queue:
            link.queue.add(unit)
        link.transmitting = None
        link.current_attempt = None
        interrupted_details: dict[str, object] = {
            "sync_unit_id": unit.sync_unit_id,
            "transmission_id": attempt.transmission_id,
            "contact_id": attempt.contact_id,
            "failure_id": failure_id,
            "bytes_sent": bytes_sent,
            "transmitted_before_interrupt_bytes": bytes_sent,
            "fraction_sent": fraction_sent,
            "cancelled_tx_complete_events": cancelled,
            "event_ids": [str(event_id) for event_id in unit.event_ids],
            "source_node": unit.source_node.value,
            "destination_node": unit.destination_node.value,
        }
        attempt_id = unit.payload.get("attempt_id")
        if attempt_id is not None:
            interrupted_details["attempt_id"] = attempt_id
        self._engine.emit_trace(
            SimulationEventType.TRANSMISSION_INTERRUPTED.value,
            interrupted_details,
            entity_id=unit.sync_unit_id,
        )

    def _new_transmission_id(self, sync_unit_id: str) -> str:
        self._next_attempt_seq += 1
        return f"tx-{sync_unit_id}-{self._next_attempt_seq}"

    def _on_arrival(self, action: ScheduledAction) -> None:
        unit_id = str(action.entity_id)
        unit = self._in_flight.pop(unit_id, None)
        if unit is None:
            unit = SyncUnit(
                sync_unit_id=unit_id,
                source_node=LogicalNode(action.payload["source_node"]),
                destination_node=LogicalNode(action.payload["destination_node"]),
                payload_size_bytes=int(action.payload["payload_size_bytes"]),
                event_ids=tuple(action.payload["event_ids"]),
                created_at_sim=float(action.payload["created_at_sim"]),
                payload=dict(action.payload.get("payload") or {}),
                submission_order=int(action.payload.get("submission_order") or 0),
            )
        delivery = TransportDelivery(
            time_sim=self._engine.now,
            event_type=action.event_type,
            sync_unit=unit,
            contact_id=str(action.payload["contact_id"]),
        )
        self._pending_deliveries.append(delivery)
        for handler in list(self._delivery_handlers):
            handler(delivery)


def _arrival_event_type(destination: LogicalNode) -> str:
    if destination is LogicalNode.RELAY:
        return SimulationEventType.ARRIVED_AT_RELAY.value
    if destination is LogicalNode.EARTH:
        return SimulationEventType.ARRIVED_AT_EARTH_TRANSPORT.value
    if destination is LogicalNode.MARS:
        return SimulationEventType.ARRIVED_AT_MARS_TRANSPORT.value
    raise RuntimeError(f"el transporte emulado no entrega en {destination.value}")


def _unit_payload(unit: SyncUnit) -> dict[str, object]:
    payload: dict[str, object] = {
        "sync_unit_id": unit.sync_unit_id,
        "source_node": unit.source_node.value,
        "destination_node": unit.destination_node.value,
        "payload_size_bytes": unit.payload_size_bytes,
        "event_ids": [str(event_id) for event_id in unit.event_ids],
        "created_at_sim": unit.created_at_sim,
        "submission_order": unit.submission_order,
        "payload": deepcopy(unit.payload),
    }
    attempt_id = unit.payload.get("attempt_id")
    if attempt_id is not None:
        payload["attempt_id"] = attempt_id
    return payload
