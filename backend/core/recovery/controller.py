"""Coordinación de la recuperación receiver-driven a nivel de aplicación.
Tierra sigue a cargo de la persistencia, la idempotencia y el conocimiento
de huecos. Este controlador es la política que convierte un hueco interno
observado en un ``GapRequest`` lógico y, en Marte, en la reparación
selectiva de los eventos originales.
La entrega del GapRequest se puede reintentar: una unidad de control
Tierra → Marte perdida no deja la cobertura abierta trabada para siempre.
El reintento conserva el ``request_id`` lógico y se angosta a los rangos
que todavía faltan. No es un fallback sender-driven.
No forma parte de la corrida por defecto. Quien arma el stack lo construye
solo cuando quiere esta política.
"""
from __future__ import annotations
from collections.abc import Callable, Sequence
from math import isfinite
from typing import Protocol
from uuid import UUID
from core.contact.contact import LogicalNode
from core.domain.ack import ApplicationAck
from core.domain.event import TelemetryEvent
from core.domain.gap import (
    GapRequest,
    MissingSequenceRange,
    intersect_missing_ranges,
    subtract_missing_ranges,
)
from core.domain.state import TelemetryEventState
from core.earth.node import EarthNode
from core.mars.node import MarsNode
from core.recovery.attempt import GapRequestAttemptState, GapRequestAttemptStatus
from core.recovery.tracker import GapRequestTracker
from core.simulation.engine import SimulationEngine
from core.simulation.scheduler import ScheduledAction
from core.sync.codec import (
    KIND_GAP_REQUEST,
    decode_gap_request,
    encode_gap_request,
    gap_request_attempt_number,
    is_gap_request_unit,
)
from core.sync.unit import SyncUnit
from core.trace.types import SimulationEventType

RepairSubmitter = Callable[[Sequence[TelemetryEvent], str], tuple[TelemetryEvent, ...]]

class GapRequestTransport(Protocol):
    """Presentación de una SyncUnit ya construida. No elige contacto ni capacidad."""
    def submit(self, unit: SyncUnit) -> None:
        """Acepta la unidad en la cola de su enlace dirigido."""

def _range_payload(
    ranges: Sequence[MissingSequenceRange],
) -> list[dict[str, int]]:
    return [
        {
            "start_sequence": item.start_sequence,
            "end_sequence": item.end_sequence,
        }
        for item in ranges
    ]

def _payload_kind(details: dict[str, object]) -> str | None:
    inner = details.get("payload")
    if not isinstance(inner, dict):
        return None
    raw = inner.get("kind")
    return str(raw) if raw is not None else None

class ReceiverDrivenRecoveryController:
    """Coordina la emisión del GapRequest, su reintento de vuelta y la reparación.
    La identidad lógica del GapRequest es distinta de cada intento de
    transporte. El reloj de timeout empieza solo cuando la unidad terminó
    de salir de Tierra en el primer hop, igual que el timeout de ACK de
    aplicación.
    """
    def __init__(
        self,
        *,
        earth: EarthNode,
        mars: MarsNode,
        transport: GapRequestTransport,
        engine: SimulationEngine,
        gap_request_timeout_seconds: float,
    ) -> None:
        if not isfinite(gap_request_timeout_seconds) or gap_request_timeout_seconds <= 0:
            raise ValueError(
                "gap_request_timeout_seconds debe ser una duración finita y positiva"
            )
        self._earth = earth
        self._mars = mars
        self._transport = transport
        self._engine = engine
        self.gap_request_timeout_seconds = gap_request_timeout_seconds
        self._submit_repair: RepairSubmitter | None = None
        self._tracker = GapRequestTracker()
        self.issued_requests: list[GapRequest] = []
        self.repair_submissions: list[tuple[str, int, str, float]] = []
        self._attempts: dict[str, GapRequestAttemptState] = {}
        self._handled_request_ids: set[str] = set()
        self._receiver_repair_event_ids: set[UUID] = set()
        self._served_sequences_by_request: dict[str, set[int]] = {}
        engine.register_handler(
            SimulationEventType.TRANSMISSION_STARTED.value,
            self._on_transmission_started,
        )
        engine.register_handler(
            SimulationEventType.TRANSMISSION_COMPLETED.value,
            self._on_transmission_completed,
        )
        engine.register_handler(
            SimulationEventType.TRANSMISSION_INTERRUPTED.value,
            self._on_transmission_interrupted,
        )
        engine.register_handler(
            SimulationEventType.GAP_REQUEST_TIMEOUT.value,
            self._on_gap_request_timeout,
        )

    @property
    def attempts(self) -> dict[str, GapRequestAttemptState]:
        return self._attempts

    def bind_repair_submitter(self, submitter: RepairSubmitter) -> None:
        self._submit_repair = submitter

    def on_unique_persist(
        self,
        events: Sequence[TelemetryEvent],
        ack: ApplicationAck,
        at_sim: float,
    ) -> None:
        """Revisa huecos después de que Tierra persistió telemetría nueva.
        Una llegada duplicada no emite pedidos. El sufijo posterior a la
        secuencia persistida más alta no es un hueco y no se pide.
        """
        persisted_ids = set(ack.accepted_event_ids)
        if not persisted_ids:
            return
        sources = sorted(
            {
                event.source_id
                for event in events
                if event.event_id in persisted_ids
            }
        )
        for source_id in sources:
            self._observe_source(source_id, at_sim)

    def handle_gap_request(self, unit: SyncUnit, at_sim: float) -> tuple[TelemetryEvent, ...]:
        """Atiende un GapRequest que ya llegó al transporte de Marte.
        Busca los eventos originales de los rangos pedidos. No inventa los
        que Marte no tiene. Un ``request_id`` ya visto deja traza de
        duplicado y solo rearma reparación si el evento no está confirmado
        ni tiene ya un intento de reparación activo.
        """
        if not is_gap_request_unit(unit):
            return ()
        request = decode_gap_request(unit)
        attempt_number = gap_request_attempt_number(unit)
        received_details: dict[str, object] = {
            "request_id": request.request_id,
            "attempt_number": attempt_number,
            "source_id": request.target_source_id,
            "missing_ranges": _range_payload(request.missing_ranges),
            "sync_unit_id": unit.sync_unit_id,
            "received_at_sim": at_sim,
            "at_sim": at_sim,
        }
        self._trace(
            SimulationEventType.GAP_REQUEST_RECEIVED_MARS.value,
            received_details,
            entity_id=request.request_id,
        )
        is_duplicate = request.request_id in self._handled_request_ids
        if is_duplicate:
            self._trace(
                SimulationEventType.GAP_REQUEST_DUPLICATE_RECEIVED_MARS.value,
                received_details,
                entity_id=request.request_id,
            )
        self._handled_request_ids.add(request.request_id)
        if request.target_source_id != self._mars.source_id:
            return ()
        found = tuple(self._mars.events_for_sequence_ranges(request.missing_ranges))
        repairable = tuple(
            event for event in found if self._may_start_receiver_repair(event)
        )
        if not repairable or self._submit_repair is None:
            return found
        repaired = self._submit_repair(repairable, request.request_id)
        served = self._served_sequences_by_request.setdefault(request.request_id, set())
        for event in repaired:
            self._receiver_repair_event_ids.add(event.event_id)
            served.add(event.sequence_number)
            self.repair_submissions.append(
                (
                    str(event.event_id),
                    event.sequence_number,
                    request.request_id,
                    at_sim,
                )
            )
            self._trace(
                SimulationEventType.GAP_REPAIR_SUBMITTED.value,
                {
                    "request_id": request.request_id,
                    "attempt_number": attempt_number,
                    "source_id": event.source_id,
                    "event_id": str(event.event_id),
                    "sequence_number": event.sequence_number,
                    "missing_ranges": _range_payload(request.missing_ranges),
                    "recovery_trigger": "receiver_gap_request",
                },
                entity_id=str(event.event_id),
            )
        return found

    def _may_start_receiver_repair(self, event: TelemetryEvent) -> bool:
        sync = self._mars.sync_state(event.event_id)
        if sync is not None and sync.state is TelemetryEventState.CONFIRMED:
            return False
        active = self._mars.active_sync_attempt_for_event(event.event_id)
        if active is not None and event.event_id in self._receiver_repair_event_ids:
            return False
        return True

    def _observe_source(self, source_id: str, at_sim: float) -> None:
        current = self._earth.gap_ranges_for_source(source_id)
        closed_ids = self._tracker.trim_to_current_gaps(source_id, current)
        self._sync_attempts_with_gaps(source_id, current, at_sim)
        if not current:
            if closed_ids:
                self._trace(
                    SimulationEventType.GAP_CLOSED.value,
                    {
                        "source_id": source_id,
                        "request_ids": list(closed_ids),
                        "missing_ranges": [],
                    },
                    entity_id=source_id,
                )
            return
        uncovered = subtract_missing_ranges(
            current, self._tracker.outstanding_ranges_for_source(source_id)
        )
        if not uncovered:
            return
        self._trace(
            SimulationEventType.GAP_OBSERVED.value,
            {
                "source_id": source_id,
                "missing_ranges": _range_payload(uncovered),
            },
            entity_id=source_id,
        )
        request = GapRequest(
            target_source_id=source_id,
            missing_ranges=uncovered,
            created_at_sim=at_sim,
        )
        self._trace(
            SimulationEventType.GAP_REQUEST_CREATED.value,
            {
                "request_id": request.request_id,
                "source_id": source_id,
                "missing_ranges": _range_payload(request.missing_ranges),
                "created_at_sim": request.created_at_sim,
                "attempt_number": 1,
                "at_sim": at_sim,
            },
            entity_id=request.request_id,
        )
        self._tracker.record(request)
        self.issued_requests.append(request)
        state = GapRequestAttemptState(
            request=request,
            current_missing_ranges=request.missing_ranges,
            attempt_number=1,
            status=GapRequestAttemptStatus.PENDING,
        )
        self._attempts[request.request_id] = state
        self._submit_attempt(state, is_retry=False)

    def _sync_attempts_with_gaps(
        self,
        source_id: str,
        current: Sequence[MissingSequenceRange],
        at_sim: float,
    ) -> None:
        for state in list(self._attempts.values()):
            if state.request.target_source_id != source_id:
                continue
            if state.status is GapRequestAttemptStatus.SATISFIED:
                continue
            leftover = intersect_missing_ranges(state.current_missing_ranges, current)
            state.current_missing_ranges = leftover
            if not leftover:
                self._satisfy(state, at_sim)

    def _submit_attempt(
        self, state: GapRequestAttemptState, *, is_retry: bool
    ) -> None:
        transport_request = GapRequest(
            request_id=state.request.request_id,
            target_source_id=state.request.target_source_id,
            missing_ranges=state.current_missing_ranges,
            created_at_sim=state.request.created_at_sim,
            requesting_node_id=state.request.requesting_node_id,
        )
        unit = encode_gap_request(
            transport_request, attempt_number=state.attempt_number
        )
        state.current_sync_unit_id = unit.sync_unit_id
        state.status = GapRequestAttemptStatus.PENDING
        state.transport_attempt_count += 1
        self._transport.submit(unit)
        details: dict[str, object] = {
            "request_id": state.request.request_id,
            "attempt_number": state.attempt_number,
            "source_id": state.request.target_source_id,
            "missing_ranges": _range_payload(state.current_missing_ranges),
            "remaining_ranges": _range_payload(state.current_missing_ranges),
            "sync_unit_id": unit.sync_unit_id,
            "payload_size_bytes": unit.payload_size_bytes,
            "at_sim": self._engine.now,
        }
        self._trace(
            SimulationEventType.GAP_REQUEST_ATTEMPT_SUBMITTED.value,
            details,
            entity_id=unit.sync_unit_id,
        )
        self._trace(
            SimulationEventType.GAP_REQUEST_SUBMITTED.value,
            details,
            entity_id=unit.sync_unit_id,
        )
        if is_retry:
            self._trace(
                SimulationEventType.GAP_REQUEST_RETRY_SUBMITTED.value,
                details,
                entity_id=unit.sync_unit_id,
            )

    def _on_transmission_started(self, action: ScheduledAction) -> None:
        state = self._attempt_for_earth_gap_unit(action.payload)
        if state is None:
            return
        if state.status is GapRequestAttemptStatus.SATISFIED:
            return
        state.status = GapRequestAttemptStatus.IN_FLIGHT

    def _on_transmission_completed(self, action: ScheduledAction) -> None:
        state = self._attempt_for_earth_gap_unit(action.payload)
        if state is None:
            return
        if state.status is GapRequestAttemptStatus.SATISFIED:
            return
        at_sim = action.time
        state.last_submitted_at_sim = at_sim
        if state.first_departed_at_sim is None:
            state.first_departed_at_sim = at_sim
        state.status = GapRequestAttemptStatus.WAITING_FOR_REPAIR
        self._trace(
            SimulationEventType.GAP_REQUEST_FIRST_HOP_DEPARTED.value,
            {
                "request_id": state.request.request_id,
                "attempt_number": state.attempt_number,
                "source_id": state.request.target_source_id,
                "missing_ranges": _range_payload(state.current_missing_ranges),
                "remaining_ranges": _range_payload(state.current_missing_ranges),
                "sync_unit_id": state.current_sync_unit_id,
                "departed_at_sim": at_sim,
                "at_sim": at_sim,
                "timeout_reference": "first_hop_departure",
            },
            entity_id=state.request.request_id,
        )
        self._schedule_timeout(state, at_sim)

    def _on_transmission_interrupted(self, action: ScheduledAction) -> None:
        state = self._attempt_for_earth_gap_unit(action.payload)
        if state is None:
            return
        if state.status is GapRequestAttemptStatus.SATISFIED:
            return
        self._cancel_timeout(state.request.request_id)
        state.status = GapRequestAttemptStatus.PENDING

    def _on_gap_request_timeout(self, action: ScheduledAction) -> None:
        request_id = str(action.payload.get("request_id", ""))
        attempt_number = int(action.payload.get("attempt_number", -1))
        at_sim = action.time
        state = self._attempts.get(request_id)
        if state is None:
            return
        if state.status is GapRequestAttemptStatus.SATISFIED:
            return
        if state.attempt_number != attempt_number:
            return
        source_id = state.request.target_source_id
        current = self._earth.gap_ranges_for_source(source_id)
        remaining = intersect_missing_ranges(state.current_missing_ranges, current)
        self._tracker.trim_to_current_gaps(source_id, current)
        state.current_missing_ranges = remaining
        self._engine.annotate_last_trace(
            {
                "remaining_ranges": _range_payload(remaining),
                "at_sim": at_sim,
            }
        )
        if not remaining:
            self._satisfy(state, at_sim)
            return
        state.attempt_number += 1
        self._submit_attempt(state, is_retry=True)

    def _schedule_timeout(
        self, state: GapRequestAttemptState, departed_at_sim: float
    ) -> None:
        self._cancel_timeout(state.request.request_id)
        timeout_at = departed_at_sim + self.gap_request_timeout_seconds
        now = self._engine.now
        if timeout_at < now:
            timeout_at = now
        self._engine.schedule(
            time=timeout_at,
            event_type=SimulationEventType.GAP_REQUEST_TIMEOUT.value,
            payload={
                "request_id": state.request.request_id,
                "attempt_number": state.attempt_number,
                "source_id": state.request.target_source_id,
                "missing_ranges": _range_payload(state.current_missing_ranges),
                "remaining_ranges": _range_payload(state.current_missing_ranges),
                "last_submitted_at_sim": departed_at_sim,
                "gap_request_timeout_seconds": self.gap_request_timeout_seconds,
                "timeout_reference": "first_hop_departure",
                "sync_unit_id": state.current_sync_unit_id,
            },
            entity_id=state.request.request_id,
        )

    def _cancel_timeout(self, request_id: str) -> None:
        self._engine.cancel(
            lambda action: (
                action.event_type == SimulationEventType.GAP_REQUEST_TIMEOUT.value
                and action.payload.get("request_id") == request_id
            )
        )

    def _satisfy(self, state: GapRequestAttemptState, at_sim: float) -> None:
        if state.status is GapRequestAttemptStatus.SATISFIED:
            return
        self._cancel_timeout(state.request.request_id)
        state.current_missing_ranges = ()
        state.status = GapRequestAttemptStatus.SATISFIED
        self._trace(
            SimulationEventType.GAP_REQUEST_SATISFIED.value,
            {
                "request_id": state.request.request_id,
                "attempt_number": state.attempt_number,
                "source_id": state.request.target_source_id,
                "missing_ranges": _range_payload(state.request.missing_ranges),
                "remaining_ranges": [],
                "at_sim": at_sim,
            },
            entity_id=state.request.request_id,
        )

    def _attempt_for_earth_gap_unit(
        self, details: dict[str, object]
    ) -> GapRequestAttemptState | None:
        if details.get("source_node") != LogicalNode.EARTH.value:
            return None
        if _payload_kind(details) != KIND_GAP_REQUEST:
            return None
        sync_unit_id = details.get("sync_unit_id")
        if not isinstance(sync_unit_id, str):
            return None
        for state in self._attempts.values():
            if state.current_sync_unit_id == sync_unit_id:
                return state
        return None

    def _trace(
        self,
        event_type: str,
        payload: dict[str, object],
        entity_id: str | None,
    ) -> None:
        self._engine.emit_trace(event_type, payload, entity_id=entity_id)
