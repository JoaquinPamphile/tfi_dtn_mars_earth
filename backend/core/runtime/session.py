"""Sincronización de aplicación sobre el transporte ya existente.

Agrupa eventos elegibles con la estrategia inyectada, crea el primer
intento y presenta la SyncUnit al hop Marte → relé. Cuando la unidad
llega a Tierra, toma el ACK, lo codifica y lo presenta al hop Tierra →
relé. Cuando ese ACK llega a Marte, confirma los eventos.

No programa un timeout de ACK, no crea un segundo intento y no pide
reparación de huecos. Si el ACK no vuelve, el evento puede quedar
persistido en Tierra y pendiente en Marte.
"""

from __future__ import annotations

from collections.abc import Sequence
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
from core.domain.state import TelemetryEventState
from core.earth.node import EarthNode
from core.mars.node import MarsNode
from core.runtime.ordering import unique_in_order
from core.simulation.engine import SimulationEngine
from core.simulation.scheduler import ScheduledAction
from core.sync.codec import (
    KIND_TELEMETRY_EVENTS,
    attempt_id_from_unit,
    decode_application_ack,
    encode_application_ack,
    encode_telemetry_events,
    is_ack_unit,
    is_telemetry_unit,
)
from core.sync.strategy import SyncPlan, SyncPlanningContext, SyncStrategy
from core.sync.unit import SyncUnit
from core.trace.types import SimulationEventType
from core.transport.emulated import EmulatedTransport, TransportDelivery

_TERMINAL_ATTEMPT = TERMINAL_ATTEMPT_STATUSES


class TelemetrySyncSession:
    """Une Marte, Tierra y el transporte para el primer intento de cada grupo.

    La unidad se crea en una oportunidad de sincronización: el contacto
    Marte → relé está vigente en el plan, sea porque acaba de abrirse o
    porque apareció telemetría pendiente mientras esa ventana contiene el
    reloj. Generar un evento fuera de esa ventana no arma la unidad.
    """

    def __init__(
        self,
        mars: MarsNode,
        earth: EarthNode,
        engine: SimulationEngine,
        transport: EmulatedTransport,
        contact_plan: ContactPlan,
        strategy: SyncStrategy,
    ) -> None:
        self.mars = mars
        self.earth = earth
        self.engine = engine
        self.transport = transport
        self.contact_plan = contact_plan
        self.strategy = strategy
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

    def submit_pending(self) -> int:
        """Planifica y presenta lo elegible si el contacto Marte → relé está vigente.

        Devuelve cuántas unidades presentó. Cero si la ventana no contiene
        el reloj o si no hay eventos sin intento activo.
        """
        if self._mars_relay_available() is None:
            return 0
        eligible = unique_in_order(self.mars.eligible_sync_events())
        if not eligible:
            return 0
        context = SyncPlanningContext(
            simulation_time=self.engine.now,
            source_id=self.mars.source_id,
        )
        return self._execute_plans(self.strategy.plan(eligible, context))

    def handle_delivery(self, delivery: TransportDelivery) -> None:
        """Recibe una llegada que el transporte ya produjo.

        En Tierra persiste la telemetría, emite los hechos de esa ingesta
        y presenta el ACK al mismo transporte. En Marte, si la unidad es
        un ACK, lo aplica y cierra el intento. Una llegada al relé no se
        atiende aquí.
        """
        if delivery.event_type == SimulationEventType.ARRIVED_AT_EARTH_TRANSPORT.value:
            self._deliver_to_earth(delivery)
            return
        if delivery.event_type == SimulationEventType.ARRIVED_AT_MARS_TRANSPORT.value:
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

    def _deliver_to_earth(self, delivery: TransportDelivery) -> None:
        unit = delivery.sync_unit
        if not is_telemetry_unit(unit):
            return
        attempt = self._attempt_from_unit(unit)
        if attempt is not None and attempt.status not in _TERMINAL_ATTEMPT:
            self._save_attempt_status(attempt, SyncAttemptStatus.DELIVERED_TO_EARTH)
        ack = self.earth.ingest_sync_unit(unit, delivery.time_sim)
        self._emit_earth_ingest(unit, ack, delivery.time_sim)
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

    def _execute_plans(self, plans: Sequence[SyncPlan]) -> int:
        submitted = 0
        now = self.engine.now
        claimed: set[UUID] = set()
        for plan in plans:
            if any(event_id in claimed for event_id in plan.event_ids):
                continue
            if any(
                self.mars.active_sync_attempt_for_event(event_id) is not None
                for event_id in plan.event_ids
            ):
                continue
            group_id = sync_group_id_for(plan.event_ids)
            if self.mars.latest_sync_attempt_for_group(group_id) is not None:
                continue
            attempt_number = 1
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
                parent_attempt_id=None,
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
            self._emit_attempt_trace(
                SimulationEventType.SYNC_ATTEMPT_CREATED.value,
                attempt,
                unit.sync_unit_id,
                extra={
                    "status": attempt.status.value,
                    "strategy": plan.strategy_type,
                    "sync_group_id": group_id,
                    "parent_attempt_id": None,
                },
            )
            self.engine.emit_trace(
                SimulationEventType.SYNC_UNIT_CREATED.value,
                {
                    "sync_unit_id": unit.sync_unit_id,
                    "attempt_id": attempt.attempt_id,
                    "sync_group_id": group_id,
                    "event_ids": [str(event_id) for event_id in plan.event_ids],
                    "event_count": len(plan.event_ids),
                    "strategy": plan.strategy_type,
                    "payload_size_bytes": unit.payload_size_bytes,
                    "size_basis": "application_layer_serialized_sync_unit",
                },
                entity_id=unit.sync_unit_id,
            )
            self.transport.submit(unit)
            claimed.update(plan.event_ids)
            submitted += 1
        return submitted

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
