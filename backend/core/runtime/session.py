"""Sincronización de aplicación sobre el transporte ya existente.

Agrupa eventos elegibles con la estrategia inyectada, crea el intento y
presenta la SyncUnit al hop Marte → relé. Cuando la unidad llega a Tierra,
toma el ACK, lo codifica y lo presenta al hop Tierra → relé. Cuando ese
ACK llega a Marte, confirma los eventos y cancela el timeout de ese intento.

El timeout de ACK, solo si sender-driven está encendido, se mide desde
``last_submitted_at_sim``: el instante en que la unidad terminó de salir de
Marte hacia el relé. Al vencer, el intento pasa a ``TIMED_OUT`` y se evalúa
un retry de esa misma cohorte. La evaluación puede ocurrir en ese instante,
si el contacto Marte → relé está vigente, o quedar programada para el
próximo contacto. Un evento generado después no entra en esa cohorte.

Si sender-driven está apagado, ese timeout no se programa. Un evento cuyo
ACK no vuelve queda pendiente en Marte. Tierra puede registrar el hueco
cuando llega una secuencia posterior, sin que eso cree un retry.

Si no hay un contacto de retorno y sender-driven está encendido, el ACK
puede quedar en la cola del transporte y el timeout dispara el retry.

La reparación receiver-driven es opcional. Sin controlador no se arma un
GapRequest. Con controlador, una alta nueva en Tierra puede pedir los
huecos internos no cubiertos, y un GapRequest que llega a Marte rearma
esos eventos como unidades Individual. La detección de huecos del
repositorio de Tierra no depende de este controlador.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from core.contact.contact import Contact, LogicalNode
from core.contact.plan import ContactPlan
from core.domain.ack import ApplicationAck
from core.domain.attempt import (
    TERMINAL_ATTEMPT_STATUSES,
    SyncAttempt,
    SyncAttemptStatus,
    attempt_id_for_group,
    sync_group_id_for,
)
from core.domain.event import TelemetryEvent
from core.domain.retry import RetryPolicy
from core.domain.state import TelemetryEventState
from core.earth.node import EarthNode
from core.mars.node import MarsNode
from core.recovery.controller import ReceiverDrivenRecoveryController
from core.runtime.ordering import unique_in_order
from core.simulation.engine import SimulationEngine
from core.simulation.scheduler import ScheduledAction
from core.sync.codec import (
    KIND_TELEMETRY_EVENTS,
    attempt_id_from_unit,
    decode_application_ack,
    decode_telemetry_events,
    encode_application_ack,
    encode_telemetry_events,
    is_ack_unit,
    is_gap_request_unit,
    is_telemetry_unit,
)
from core.sync.individual import IndividualSyncStrategy
from core.sync.strategy import SyncPlan, SyncPlanningContext, SyncStrategy
from core.sync.unit import SyncUnit
from core.trace.types import SimulationEventType
from core.transport.emulated import EmulatedTransport, TransportDelivery

_TERMINAL_ATTEMPT = TERMINAL_ATTEMPT_STATUSES
_RECEIVER_REPAIR_TRIGGER = "receiver_gap_request"


@dataclass(frozen=True, slots=True)
class SenderAckTimeoutRecord:
    """Timeout de ACK que dejó un intento en ``TIMED_OUT``.

    ``at_sim`` es el instante de simulación en que venció la espera.
    No es el instante de la pérdida ni el de la confirmación en Marte.
    """

    attempt_id: str
    event_ids: tuple[str, ...]
    at_sim: float


@dataclass(frozen=True, slots=True)
class CreatedSyncByteCounters:
    """Bytes canónicos de las SyncUnit que la sesión ya creó.

    ``sync_units_created`` cuenta solo unidades de telemetría, reintentos
    incluidos. Los bytes de ACK van aparte. Un ``attempt_number`` mayor
    que 1 entra en los bytes de reintento creados, sea retry del emisor
    o reparación pedida por el receptor. No multiplican hops.
    """

    telemetry_syncunit_bytes_created: int
    telemetry_initial_syncunit_bytes_created: int
    telemetry_retry_syncunit_bytes_created: int
    ack_syncunit_bytes_created: int
    sync_units_created: int


class TelemetrySyncSession:
    """Une Marte, Tierra y el transporte, incluido el retry del emisor.

    La unidad se crea en una oportunidad de sincronización: el contacto
    Marte → relé está vigente en el plan, sea porque acaba de abrirse o
    porque apareció telemetría pendiente mientras esa ventana contiene el
    reloj. Generar un evento fuera de esa ventana no arma la unidad.

    Un retry no rearma el grupo con los pendientes globales. Conserva los
    ``event_ids`` del intento anterior, en el mismo orden, con el mismo
    ``sync_group_id`` y la misma estrategia. El ``attempt_id`` y el
    ``attempt_number`` son nuevos.

    ``sender_driven`` enciende el timeout de ACK y el retry de esa cohorte.
    Apagado, no se programa ``ACK_TIMEOUT``, no se evalúa un retry y no se
    crea un reintento del emisor. ``recovery`` enciende el pedido de huecos.
    Sin controlador no hay GapRequest.
    """

    def __init__(
        self,
        mars: MarsNode,
        earth: EarthNode,
        engine: SimulationEngine,
        transport: EmulatedTransport,
        contact_plan: ContactPlan,
        strategy: SyncStrategy,
        retry_policy: RetryPolicy | None = None,
        recovery: ReceiverDrivenRecoveryController | None = None,
        sender_driven: bool = False,
    ) -> None:
        self.mars = mars
        self.earth = earth
        self.engine = engine
        self.transport = transport
        self.contact_plan = contact_plan
        self.strategy = strategy
        self.retry_policy = retry_policy if retry_policy is not None else RetryPolicy()
        self.recovery = recovery
        self.sender_driven = sender_driven
        self._timeout_scheduled: set[str] = set()
        self._retry_eval_pending: set[str] = set()
        self._sync_units_created = 0
        self._telemetry_syncunit_bytes_created = 0
        self._telemetry_initial_syncunit_bytes_created = 0
        self._telemetry_retry_syncunit_bytes_created = 0
        self._ack_syncunit_bytes_created = 0
        self._sender_ack_timeouts: list[SenderAckTimeoutRecord] = []
        if self.recovery is not None:
            self.recovery.bind_repair_submitter(self.submit_receiver_repair_events)
        transport.register_delivery_handler(self.handle_delivery)
        engine.register_handler(
            SimulationEventType.CONTACT_OPEN.value,
            self._on_contact_open,
        )
        engine.register_handler(
            SimulationEventType.TRANSMISSION_STARTED.value,
            self._on_transmission_started,
        )
        engine.register_handler(
            SimulationEventType.TRANSMISSION_COMPLETED.value,
            self._on_transmission_completed,
        )
        engine.register_handler(
            SimulationEventType.ACK_TIMEOUT.value,
            self._on_ack_timeout,
        )
        engine.register_handler(
            SimulationEventType.RETRY_EVALUATION.value,
            self._on_retry_evaluation,
        )

    def created_sync_byte_counters(self) -> CreatedSyncByteCounters:
        """Contadores de unidades ya creadas. No lee la traza."""
        return CreatedSyncByteCounters(
            telemetry_syncunit_bytes_created=self._telemetry_syncunit_bytes_created,
            telemetry_initial_syncunit_bytes_created=(
                self._telemetry_initial_syncunit_bytes_created
            ),
            telemetry_retry_syncunit_bytes_created=(
                self._telemetry_retry_syncunit_bytes_created
            ),
            ack_syncunit_bytes_created=self._ack_syncunit_bytes_created,
            sync_units_created=self._sync_units_created,
        )

    def sender_ack_timeouts(self) -> tuple[SenderAckTimeoutRecord, ...]:
        """Timeouts de ACK que pasaron un intento a ``TIMED_OUT``, en orden."""
        return tuple(self._sender_ack_timeouts)

    def _note_telemetry_unit_created(self, payload_size_bytes: int, attempt_number: int) -> None:
        """Suma la unidad de telemetría recién creada. No cuenta hops ni ACK."""
        self._sync_units_created += 1
        self._telemetry_syncunit_bytes_created += payload_size_bytes
        if attempt_number > 1:
            self._telemetry_retry_syncunit_bytes_created += payload_size_bytes
        else:
            self._telemetry_initial_syncunit_bytes_created += payload_size_bytes

    def submit_pending(self) -> int:
        """Planifica y presenta lo elegible si el contacto Marte → relé está vigente.

        Devuelve cuántas unidades presentó. Cero si la ventana no contiene
        el reloj o si no hay eventos sin intento activo. Una cohorte ya
        vencida se reintenta aparte de los eventos que todavía no tuvieron
        intento.
        """
        return self._plan_and_submit()

    def submit_receiver_repair_events(
        self, events: Sequence[TelemetryEvent], request_id: str
    ) -> tuple[TelemetryEvent, ...]:
        """Presenta los eventos originales como unidades Individual de reparación.

        No fabrica eventos. No apaga la guarda de intento activo: un intento
        vigente de varios eventos no se reemplaza.

        Un evento confirmado se omite. Un intento Individual activo del
        evento pedido pasa a ``REPAIR_REQUESTED`` y se le cancela el timeout
        de ACK antes de crear el intento siguiente del linaje. Un intento
        activo de varios eventos no se reemplaza.
        """

        unique = unique_in_order(events)
        if not unique:
            return ()
        repairable: list[TelemetryEvent] = []
        parents: list[SyncAttempt | None] = []
        for event in unique:
            sync = self.mars.sync_state(event.event_id)
            if sync is not None and sync.state is TelemetryEventState.CONFIRMED:
                continue
            may_repair, parent = self._supersede_active_attempt_for_receiver_repair(
                event, request_id
            )
            if not may_repair:
                continue
            repairable.append(event)
            parents.append(parent)
        if not repairable:
            return ()
        context = SyncPlanningContext(
            simulation_time=self.engine.now,
            source_id=self.mars.source_id,
        )
        plans = IndividualSyncStrategy().plan(repairable, context)
        parent_by_event = {
            event.event_id: parent
            for event, parent in zip(repairable, parents, strict=True)
        }
        aligned_parents = [parent_by_event.get(plan.event_ids[0]) for plan in plans]
        submitted = self._execute_plans(
            plans,
            parents=aligned_parents,
            recovery_trigger=_RECEIVER_REPAIR_TRIGGER,
            request_id=request_id,
        )
        if submitted == 0:
            return ()
        return tuple(repairable)

    def _supersede_active_attempt_for_receiver_repair(
        self, event: TelemetryEvent, request_id: str
    ) -> tuple[bool, SyncAttempt | None]:
        """Cierra un intento Individual activo para que la reparación pueda seguir.

        Devuelve ``(puede_reparar, intento_padre)``. ``intento_padre`` es el
        intento reemplazado, si había uno. Un intento vigente de varios
        eventos no se reemplaza: la reparación Individual de un miembro de
        Fixed Batch queda fuera de este corte, y la guarda del emisor sigue.
        """

        active = self.mars.active_sync_attempt_for_event(event.event_id)
        if active is None:
            return True, None
        if len(active.event_ids) != 1:
            return False, None
        old_status = active.status
        if old_status is SyncAttemptStatus.QUEUED:
            sync_unit_id = self.mars.sync_unit_id_for_attempt(active.attempt_id)
            if sync_unit_id is not None:
                self.transport.withdraw(sync_unit_id)
        self._cancel_ack_timeout(active.attempt_id)
        self._save_attempt_status(active, SyncAttemptStatus.REPAIR_REQUESTED)
        next_attempt_number = active.attempt_number + 1
        self._emit_attempt_trace(
            SimulationEventType.SYNC_ATTEMPT_REPAIR_REQUESTED.value,
            active,
            self.mars.sync_unit_id_for_attempt(active.attempt_id),
            extra={
                "request_id": request_id,
                "event_id": str(event.event_id),
                "sequence_number": event.sequence_number,
                "old_attempt_id": active.attempt_id,
                "old_status": old_status.value,
                "next_attempt_number": next_attempt_number,
                "next_attempt_id": attempt_id_for_group(
                    active.event_ids, next_attempt_number
                ),
                "at_sim": self.engine.now,
            },
        )
        return True, self.mars.get_sync_attempt(active.attempt_id)

    def handle_delivery(self, delivery: TransportDelivery) -> None:
        """Recibe una llegada que el transporte ya produjo.

        En Tierra persiste la telemetría, emite los hechos de esa ingesta
        y presenta el ACK al mismo transporte. Si hay controlador y la alta
        es nueva, ese controlador puede crear un GapRequest. En Marte, un
        GapRequest se atiende antes que un ACK: se buscan los eventos y, si
        corresponde, se presenta la reparación. Un ACK cierra el intento
        vigente y cancela su timeout. Una llegada al relé no se atiende
        aquí. Un ACK repetido no abre otro retry.

        ``SILENT_FORWARD_DELIVERY_DROPPED`` no entra a Tierra: no persiste,
        no genera ACK y no cambia el intento. El relé suelta la custodia
        por su cuenta.
        """
        if delivery.event_type == SimulationEventType.SILENT_FORWARD_DELIVERY_DROPPED.value:
            return
        if delivery.event_type == SimulationEventType.ARRIVED_AT_EARTH_TRANSPORT.value:
            self._deliver_to_earth(delivery)
            return
        if delivery.event_type == SimulationEventType.ARRIVED_AT_MARS_TRANSPORT.value:
            if is_gap_request_unit(delivery.sync_unit):
                if self.recovery is not None:
                    self.recovery.handle_gap_request(
                        delivery.sync_unit, delivery.time_sim
                    )
                return
            self._deliver_ack_to_mars(delivery)

    def _on_contact_open(self, action: ScheduledAction) -> None:
        source = action.payload.get("source")
        destination = action.payload.get("destination")
        if source == LogicalNode.MARS.value and destination == LogicalNode.RELAY.value:
            self.submit_pending()

    def _on_transmission_started(self, action: ScheduledAction) -> None:
        self._observe_first_transmission(action.payload, action.time)

    def _on_transmission_completed(self, action: ScheduledAction) -> None:
        self._observe_first_hop_complete(action.payload, action.time)

    def _on_ack_timeout(self, action: ScheduledAction) -> None:
        """Vence la espera de ACK de un intento y, si corresponde, ofrece el retry.

        Un intento ya terminal no se toca. Si algún evento de la cohorte ya
        está confirmado, el intento pasa a ``ACKNOWLEDGED`` y no hay retry.
        Si la unidad de ese intento todavía sale de Marte, la acción no hace
        nada más: no reprograma el timeout. Con sender-driven apagado no
        hay timeout programado; si igual llega la acción, no cambia el intento.
        """
        if not self.sender_driven:
            return
        attempt_id = str(action.payload.get("attempt_id", ""))
        self._timeout_scheduled.discard(attempt_id)
        attempt = self.mars.get_sync_attempt(attempt_id)
        if attempt is None:
            return
        if attempt.status in _TERMINAL_ATTEMPT:
            return
        if attempt.status not in {
            SyncAttemptStatus.ACK_PENDING,
            SyncAttemptStatus.IN_FLIGHT,
            SyncAttemptStatus.DELIVERED_TO_EARTH,
        }:
            return
        confirmed = False
        for event_id in attempt.event_ids:
            sync = self.mars.sync_state(event_id)
            if sync is not None and sync.state is TelemetryEventState.CONFIRMED:
                confirmed = True
                break
        if confirmed:
            self._save_attempt_status(attempt, SyncAttemptStatus.ACKNOWLEDGED)
            return
        sync_unit_id = self.mars.sync_unit_id_for_attempt(attempt.attempt_id)
        if sync_unit_id is not None and self._mars_transmitting(sync_unit_id):
            return
        self._save_attempt_status(attempt, SyncAttemptStatus.TIMED_OUT)
        self._sender_ack_timeouts.append(
            SenderAckTimeoutRecord(
                attempt_id=attempt.attempt_id,
                event_ids=tuple(str(event_id) for event_id in attempt.event_ids),
                at_sim=self.engine.now,
            )
        )
        self._emit_attempt_trace(
            SimulationEventType.RETRY_SCHEDULED.value,
            attempt,
            sync_unit_id,
            extra={
                "reason": "ack_timeout",
                "last_submitted_at_sim": attempt.last_submitted_at_sim,
                "ack_timeout_seconds": self.retry_policy.ack_timeout_seconds,
            },
        )
        self._offer_retry(attempt.event_ids)

    def _on_retry_evaluation(self, action: ScheduledAction) -> None:
        """Reevalúa, en el instante programado, solo los eventos de esa acción."""
        if not self.sender_driven:
            return
        raw_ids = action.payload.get("event_ids")
        event_ids = _parse_event_ids(raw_ids)
        for event_id in event_ids:
            self._retry_eval_pending.discard(str(event_id))
        if not event_ids:
            return
        self._offer_retry(event_ids)

    def _offer_retry(self, event_ids: Sequence[UUID]) -> None:
        """Ofrece retry solo para estos eventos. No recorre el pendiente global.

        Si el contacto Marte → relé está vigente, planifica en el acto. Si no,
        deja ``RETRY_EVALUATION`` en el inicio del próximo contacto de ese
        sentido. Sin contacto futuro, registra el hecho y no crea intento.
        Con sender-driven apagado no crea intento ni programa la evaluación.
        """
        if not self.sender_driven:
            return
        eligible: list[TelemetryEvent] = []
        for event_id in event_ids:
            sync = self.mars.sync_state(event_id)
            if sync is None or sync.state is TelemetryEventState.CONFIRMED:
                continue
            if self.mars.active_sync_attempt_for_event(event_id) is not None:
                continue
            event = self.mars.get_event(event_id)
            if event is not None:
                eligible.append(event)
        if not eligible:
            return
        now = self.engine.now
        if self._mars_relay_available() is not None:
            self._plan_and_submit()
            return
        next_contact = self._next_mars_relay_contact(now)
        if next_contact is None:
            self.engine.emit_trace(
                SimulationEventType.RETRY_SCHEDULED.value,
                {
                    "event_ids": [str(event.event_id) for event in eligible],
                    "reason": "no_future_forward_contact",
                },
            )
            return
        self._schedule_retry_evaluation(
            [event.event_id for event in eligible],
            next_contact.start_time_sim,
        )

    def _schedule_retry_evaluation(self, event_ids: Sequence[UUID], when: float) -> None:
        """Programa una evaluación. Un evento que ya la tiene pendiente no se duplica."""
        pending: list[UUID] = []
        for event_id in event_ids:
            key = str(event_id)
            if key in self._retry_eval_pending:
                continue
            self._retry_eval_pending.add(key)
            pending.append(event_id)
        if not pending:
            return
        self.engine.schedule(
            when,
            SimulationEventType.RETRY_EVALUATION.value,
            payload={"event_ids": [str(event_id) for event_id in pending]},
            entity_id=str(pending[0]),
        )

    def _plan_and_submit(self) -> int:
        """Separa cohortes de retry y eventos sin intento, y presenta ambos."""
        if self._mars_relay_available() is None:
            return 0
        eligible = unique_in_order(self.mars.eligible_sync_events())
        if not self.sender_driven:
            eligible = [
                event
                for event in eligible
                if not self._is_sender_retry_candidate(event)
            ]
        if not eligible:
            return 0
        if self.sender_driven:
            retry_items, fresh = self._partition_retry_cohorts(eligible)
        else:
            retry_items, fresh = [], list(eligible)
        submitted = 0
        if retry_items:
            submitted += self._execute_plans(
                [plan for plan, _parent in retry_items],
                parents=[parent for _plan, parent in retry_items],
            )
        if not fresh:
            return submitted
        context = SyncPlanningContext(
            simulation_time=self.engine.now,
            source_id=self.mars.source_id,
        )
        submitted += self._execute_plans(self.strategy.plan(fresh, context))
        return submitted

    def _partition_retry_cohorts(
        self, eligible: Sequence[TelemetryEvent]
    ) -> tuple[list[tuple[SyncPlan, SyncAttempt]], list[TelemetryEvent]]:
        """Conserva el grupo vencido. No le agrega eventos nuevos.

        El intento anterior tiene que estar en ``TIMED_OUT`` o ``INTERRUPTED``.
        Si falta algún miembro entre los elegibles, esa cohorte no se rearma
        aquí. Los eventos que no quedaron en una cohorte siguen hacia la
        estrategia.
        """
        by_id = {event.event_id: event for event in eligible}
        claimed: set[UUID] = set()
        retry_items: list[tuple[SyncPlan, SyncAttempt]] = []
        for event in eligible:
            if event.event_id in claimed:
                continue
            latest = self.mars.latest_sync_attempt_for_event(event.event_id)
            if latest is None or latest.status not in {
                SyncAttemptStatus.TIMED_OUT,
                SyncAttemptStatus.INTERRUPTED,
            }:
                continue
            if any(event_id not in by_id for event_id in latest.event_ids):
                continue
            cohort = tuple(by_id[event_id] for event_id in latest.event_ids)
            retry_items.append(
                (
                    SyncPlan(
                        event_ids=latest.event_ids,
                        events=cohort,
                        strategy_type=self.strategy.strategy_type,
                    ),
                    latest,
                )
            )
            claimed.update(latest.event_ids)
        fresh = [event for event in eligible if event.event_id not in claimed]
        return retry_items, fresh

    def _deliver_to_earth(self, delivery: TransportDelivery) -> None:
        unit = delivery.sync_unit
        if not is_telemetry_unit(unit):
            return
        events = decode_telemetry_events(unit)
        attempt = self._attempt_from_unit(unit)
        if attempt is not None and attempt.status not in _TERMINAL_ATTEMPT:
            self._save_attempt_status(attempt, SyncAttemptStatus.DELIVERED_TO_EARTH)
        ack = self.earth.ingest_sync_unit(unit, delivery.time_sim)
        self._emit_earth_ingest(unit, ack, delivery.time_sim)
        if self.recovery is not None and ack.accepted_event_ids:
            self.recovery.on_unique_persist(events, ack, delivery.time_sim)
        for event_id in ack.event_ids:
            self.mars.record_observability_state(
                event_id,
                TelemetryEventState.PERSISTED_EARTH,
                delivery.time_sim,
                attempt_id=attempt.attempt_id if attempt is not None else None,
            )
        if attempt is not None and attempt.status not in _TERMINAL_ATTEMPT:
            self._save_attempt_status(attempt, SyncAttemptStatus.ACK_PENDING)
        ack_unit = encode_application_ack(ack, delivery.time_sim)
        self._ack_syncunit_bytes_created += ack_unit.payload_size_bytes
        self.transport.submit(ack_unit)

    def _deliver_ack_to_mars(self, delivery: TransportDelivery) -> None:
        unit = delivery.sync_unit
        if not is_ack_unit(unit):
            return
        ack = decode_application_ack(unit)
        self.mars.apply_application_ack(ack, delivery.time_sim)
        for event_id in ack.confirmed_event_ids():
            attempt = self.mars.latest_sync_attempt_for_event(event_id)
            if attempt is not None and attempt.status not in {
                SyncAttemptStatus.ACKNOWLEDGED,
                SyncAttemptStatus.REPAIR_REQUESTED,
            }:
                self._save_attempt_status(attempt, SyncAttemptStatus.ACKNOWLEDGED)
                self._cancel_ack_timeout(attempt.attempt_id)
            confirmed_details: dict[str, object] = {
                "event_id": str(event_id),
                "ack_id": ack.ack_id,
                "confirmed_at_sim": delivery.time_sim,
                "sync_unit_id": unit.sync_unit_id,
            }
            if attempt is not None:
                confirmed_details["attempt_id"] = attempt.attempt_id
            self.engine.emit_trace(
                SimulationEventType.MARS_EVENT_CONFIRMED.value,
                confirmed_details,
                entity_id=str(event_id),
            )
            self.engine.emit_trace(
                SimulationEventType.CONFIRMED.value,
                confirmed_details,
                entity_id=str(event_id),
            )

    def _execute_plans(
        self,
        plans: Sequence[SyncPlan],
        parents: Sequence[SyncAttempt | None] | None = None,
        *,
        recovery_trigger: str | None = None,
        request_id: str | None = None,
    ) -> int:
        submitted = 0
        now = self.engine.now
        claimed: set[UUID] = set()
        for index, plan in enumerate(plans):
            if any(event_id in claimed for event_id in plan.event_ids):
                continue
            if any(
                self.mars.active_sync_attempt_for_event(event_id) is not None
                for event_id in plan.event_ids
            ):
                continue
            parent = None if parents is None else parents[index]
            group_id = sync_group_id_for(plan.event_ids)
            attempt_number, parent_attempt_id = self._lineage_for_plan(
                group_id, parent
            )
            attempt_id = attempt_id_for_group(plan.event_ids, attempt_number)
            attempt = SyncAttempt(
                attempt_id=attempt_id,
                event_ids=plan.event_ids,
                created_at_sim=now,
                first_submitted_at_sim=now,
                last_submitted_at_sim=now,
                attempt_number=attempt_number,
                status=SyncAttemptStatus.QUEUED,
                sync_group_id=group_id,
                parent_attempt_id=parent_attempt_id,
            )
            unit = encode_telemetry_events(
                plan.events,
                created_at_sim=now,
                attempt_id=attempt_id,
                attempt_number=attempt_number,
                strategy_type=plan.strategy_type,
                sync_group_id=group_id,
            )
            self._emit_plan_created(plan, unit.sync_unit_id, group_id)
            self.mars.save_sync_attempt(attempt, unit.sync_unit_id)
            created_extra: dict[str, object] = {
                "status": attempt.status.value,
                "strategy": plan.strategy_type,
                "sync_group_id": group_id,
                "parent_attempt_id": parent_attempt_id,
            }
            if recovery_trigger is not None:
                created_extra["recovery_trigger"] = recovery_trigger
            if request_id is not None:
                created_extra["request_id"] = request_id
            self._emit_attempt_trace(
                SimulationEventType.SYNC_ATTEMPT_CREATED.value,
                attempt,
                unit.sync_unit_id,
                extra=created_extra,
            )
            unit_details: dict[str, object] = {
                "sync_unit_id": unit.sync_unit_id,
                "attempt_id": attempt.attempt_id,
                "sync_group_id": group_id,
                "event_ids": [str(event_id) for event_id in plan.event_ids],
                "event_count": len(plan.event_ids),
                "strategy": plan.strategy_type,
                "payload_size_bytes": unit.payload_size_bytes,
                "size_basis": "application_layer_serialized_sync_unit",
            }
            if recovery_trigger is not None:
                unit_details["recovery_trigger"] = recovery_trigger
            if request_id is not None:
                unit_details["request_id"] = request_id
            self.engine.emit_trace(
                SimulationEventType.SYNC_UNIT_CREATED.value,
                unit_details,
                entity_id=unit.sync_unit_id,
            )
            self._note_telemetry_unit_created(unit.payload_size_bytes, attempt_number)
            self.transport.submit(unit)
            if attempt_number > 1 and recovery_trigger is None:
                self._emit_attempt_trace(
                    SimulationEventType.RETRY_SUBMITTED.value,
                    attempt,
                    unit.sync_unit_id,
                    extra={"status": attempt.status.value, "sync_group_id": group_id},
                )
            claimed.update(plan.event_ids)
            submitted += 1
        return submitted

    def _lineage_for_plan(
        self, group_id: str, parent: SyncAttempt | None
    ) -> tuple[int, str | None]:
        """Número de intento dentro del grupo, no el máximo entre eventos sueltos.

        El primer envío es 1. Un retry de esa cohorte suma uno al intento
        padre y guarda su ``attempt_id``.
        """
        if parent is not None:
            return parent.attempt_number + 1, parent.attempt_id
        latest = self.mars.latest_sync_attempt_for_group(group_id)
        if latest is None:
            return 1, None
        return latest.attempt_number + 1, latest.attempt_id

    def _emit_plan_created(self, plan: SyncPlan, sync_unit_id: str, group_id: str) -> None:
        first = plan.events[0]
        last = plan.events[-1]
        details: dict[str, object] = {
            "strategy": plan.strategy_type,
            "event_count": len(plan.event_ids),
            "first_sequence": first.sequence_number,
            "last_sequence": last.sequence_number,
            "sync_group_id": group_id,
            "sync_unit_id": sync_unit_id,
            "event_ids": [str(event_id) for event_id in plan.event_ids],
        }
        if len(plan.events) == 1:
            details["event_id"] = str(first.event_id)
            details["source_id"] = first.source_id
            details["sequence_number"] = first.sequence_number
        self.engine.emit_trace(
            SimulationEventType.SYNC_PLAN_CREATED.value,
            details,
            entity_id=group_id,
        )

    def _mars_relay_available(self) -> Contact | None:
        now = self.engine.now
        for contact in self.contact_plan.active_at(now):
            if (
                contact.source is LogicalNode.MARS
                and contact.destination is LogicalNode.RELAY
            ):
                return contact
        return None

    def _observe_first_transmission(self, details: dict[str, object], at_sim: float) -> None:
        if details.get("source_node") != LogicalNode.MARS.value:
            return
        inner = details.get("payload")
        if not isinstance(inner, dict) or inner.get("kind") != KIND_TELEMETRY_EVENTS:
            return
        raw_ids = details.get("event_ids")
        if not isinstance(raw_ids, list):
            return
        attempt = self._attempt_from_details(details)
        if attempt is not None and attempt.status is SyncAttemptStatus.QUEUED:
            self._save_attempt_status(attempt, SyncAttemptStatus.IN_FLIGHT)
        attempt_id = attempt.attempt_id if attempt is not None else None
        for raw_id in raw_ids:
            self.mars.record_observability_state(
                UUID(str(raw_id)),
                TelemetryEventState.IN_FLIGHT,
                at_sim,
                attempt_id=attempt_id,
            )

    def _observe_first_hop_complete(self, details: dict[str, object], at_sim: float) -> None:
        if details.get("source_node") != LogicalNode.MARS.value:
            return
        inner = details.get("payload")
        if not isinstance(inner, dict) or inner.get("kind") != KIND_TELEMETRY_EVENTS:
            return
        attempt = self._attempt_from_details(details)
        if attempt is None or attempt.status in _TERMINAL_ATTEMPT:
            return
        updated = attempt.model_copy(update={"last_submitted_at_sim": at_sim})
        if updated.status is SyncAttemptStatus.QUEUED:
            updated = updated.model_copy(update={"status": SyncAttemptStatus.IN_FLIGHT})
        self.mars.save_sync_attempt(
            updated, self.mars.sync_unit_id_for_attempt(attempt.attempt_id)
        )
        self._schedule_ack_timeout(updated)

    def _is_sender_retry_candidate(self, event: TelemetryEvent) -> bool:
        """El último intento ya venció o se interrumpió y solo lo retoma el emisor."""
        latest = self.mars.latest_sync_attempt_for_event(event.event_id)
        if latest is None:
            return False
        return latest.status in {
            SyncAttemptStatus.TIMED_OUT,
            SyncAttemptStatus.INTERRUPTED,
        }

    def _schedule_ack_timeout(self, attempt: SyncAttempt) -> None:
        """Programa ``ACK_TIMEOUT`` una vez por intento, desde el último envío.

        El instante es ``last_submitted_at_sim + ack_timeout_seconds``. Si
        ese instante ya quedó atrás del reloj, la acción queda en el ahora.
        Un segundo completado del mismo intento no mueve el timeout ya puesto.
        Con sender-driven apagado no programa nada: el timeout configurado
        no se usa para dejar el mecanismo dormido.
        """
        if not self.sender_driven:
            return
        if attempt.attempt_id in self._timeout_scheduled:
            return
        timeout_at = attempt.last_submitted_at_sim + self.retry_policy.ack_timeout_seconds
        now = self.engine.now
        if timeout_at < now:
            timeout_at = now
        sync_unit_id = self.mars.sync_unit_id_for_attempt(attempt.attempt_id)
        payload: dict[str, object] = {
            "attempt_id": attempt.attempt_id,
            "event_ids": [str(event_id) for event_id in attempt.event_ids],
            "last_submitted_at_sim": attempt.last_submitted_at_sim,
            "ack_timeout_seconds": self.retry_policy.ack_timeout_seconds,
            "timeout_reference": "last_submitted_at_sim",
        }
        if sync_unit_id is not None:
            payload["sync_unit_id"] = sync_unit_id
        self.engine.schedule(
            timeout_at,
            SimulationEventType.ACK_TIMEOUT.value,
            payload=payload,
            entity_id=attempt.attempt_id,
        )
        self._timeout_scheduled.add(attempt.attempt_id)

    def _cancel_ack_timeout(self, attempt_id: str) -> None:
        """Quita el ``ACK_TIMEOUT`` futuro de ese intento. Si ya corrió, no queda nada."""
        self.engine.cancel(
            lambda action: (
                action.event_type == SimulationEventType.ACK_TIMEOUT.value
                and action.payload.get("attempt_id") == attempt_id
            )
        )
        self._timeout_scheduled.discard(attempt_id)

    def _mars_transmitting(self, sync_unit_id: str) -> bool:
        """Indica si esa unidad todavía está en vuelo saliendo de Marte."""
        for unit in self.transport.in_flight():
            if unit.sync_unit_id == sync_unit_id and unit.source_node is LogicalNode.MARS:
                return True
        return False

    def _next_mars_relay_contact(self, time_sim: float) -> Contact | None:
        """Próximo contacto Marte → relé cuyo inicio es posterior a ``time_sim``."""
        return self.contact_plan.next_contact_after(
            time_sim, LogicalNode.MARS, LogicalNode.RELAY
        )

    def _save_attempt_status(self, attempt: SyncAttempt, status: SyncAttemptStatus) -> None:
        if attempt.status is status:
            return
        updated = attempt.model_copy(update={"status": status})
        self.mars.save_sync_attempt(
            updated, self.mars.sync_unit_id_for_attempt(attempt.attempt_id)
        )

    def _attempt_from_unit(self, unit: SyncUnit) -> SyncAttempt | None:
        return self._attempt_from_event_ids(unit.event_ids, attempt_id_from_unit(unit))

    def _attempt_from_details(self, details: dict[str, object]) -> SyncAttempt | None:
        raw_attempt = details.get("attempt_id")
        if isinstance(raw_attempt, str):
            found = self.mars.get_sync_attempt(raw_attempt)
            if found is not None:
                return found
        inner = details.get("payload")
        if isinstance(inner, dict) and inner.get("attempt_id") is not None:
            found = self.mars.get_sync_attempt(str(inner["attempt_id"]))
            if found is not None:
                return found
        raw_ids = details.get("event_ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return None
        return self.mars.latest_sync_attempt_for_event(UUID(str(raw_ids[0])))

    def _attempt_from_event_ids(
        self, event_ids: tuple[UUID, ...], attempt_id: str | None
    ) -> SyncAttempt | None:
        if attempt_id is not None:
            found = self.mars.get_sync_attempt(attempt_id)
            if found is not None:
                return found
        if not event_ids:
            return None
        return self.mars.latest_sync_attempt_for_event(event_ids[0])

    def _emit_attempt_trace(
        self,
        event_type: str,
        attempt: SyncAttempt,
        sync_unit_id: str | None,
        extra: dict[str, object] | None = None,
    ) -> None:
        details: dict[str, object] = {
            "attempt_id": attempt.attempt_id,
            "event_ids": [str(event_id) for event_id in attempt.event_ids],
            "attempt_number": attempt.attempt_number,
            "sync_group_id": attempt.sync_group_id,
            "event_count": len(attempt.event_ids),
        }
        if len(attempt.event_ids) == 1:
            details["event_id"] = str(attempt.event_ids[0])
        if sync_unit_id is not None:
            details["sync_unit_id"] = sync_unit_id
        if extra:
            details.update(extra)
        self.engine.emit_trace(event_type, details, entity_id=attempt.attempt_id)

    def _emit_earth_ingest(self, unit: SyncUnit, ack: ApplicationAck, arrived_at_sim: float) -> None:
        """Hechos de la ingesta, en el orden de aceptados y luego duplicados.

        Tierra no escribe la traza. Estos detalles son los de esa ingesta:
        uno por alta nueva, dos por duplicado, y el ACK dos veces.
        """
        attempt_id = unit.payload.get("attempt_id")
        for event_id in ack.accepted_event_ids:
            self.engine.emit_trace(
                SimulationEventType.EARTH_EVENT_PERSISTED.value,
                _earth_event_details(event_id, unit, arrived_at_sim, attempt_id),
                entity_id=str(event_id),
            )
        for event_id in ack.duplicate_event_ids:
            duplicate_details = _earth_event_details(
                event_id, unit, arrived_at_sim, attempt_id
            )
            self.engine.emit_trace(
                SimulationEventType.EARTH_DUPLICATE_RECEIVED.value,
                duplicate_details,
                entity_id=str(event_id),
            )
            self.engine.emit_trace(
                SimulationEventType.DUPLICATE_RECEIVED.value,
                duplicate_details,
                entity_id=str(event_id),
            )
        ack_details: dict[str, object] = {
            "ack_id": ack.ack_id,
            "event_ids": [str(event_id) for event_id in ack.event_ids],
            "accepted_event_ids": [str(event_id) for event_id in ack.accepted_event_ids],
            "duplicate_event_ids": [
                str(event_id) for event_id in ack.duplicate_event_ids
            ],
            "rejected_event_ids": [str(event_id) for event_id in ack.rejected_event_ids],
            "generated_at_sim": ack.generated_at_sim,
            "status": ack.status.value,
            "sync_unit_id": unit.sync_unit_id,
        }
        if attempt_id is not None:
            ack_details["attempt_id"] = attempt_id
        self.engine.emit_trace(
            SimulationEventType.APPLICATION_ACK_GENERATED.value,
            ack_details,
            entity_id=ack.ack_id,
        )
        self.engine.emit_trace(
            SimulationEventType.ACK_GENERATED.value,
            ack_details,
            entity_id=ack.ack_id,
        )


def _parse_event_ids(raw: object) -> list[UUID]:
    """Lee ``event_ids`` de una acción. Una carga que no es lista no aporta ids."""
    if not isinstance(raw, list):
        return []
    return [UUID(str(item)) for item in raw]


def _earth_event_details(
    event_id: UUID,
    unit: SyncUnit,
    arrived_at_sim: float,
    attempt_id: object,
) -> dict[str, object]:
    details: dict[str, object] = {
        "event_id": str(event_id),
        "sync_unit_id": unit.sync_unit_id,
        "ingested_at_sim": arrived_at_sim,
    }
    if attempt_id is not None:
        details["attempt_id"] = attempt_id
    return details
