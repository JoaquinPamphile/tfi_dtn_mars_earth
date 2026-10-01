"""Puertos del estado de aplicación de Marte y de Tierra.
El contrato es el estado científico de una corrida: eventos, outbox,
intentos ya decididos por el llamador, e ingesta idempotente. No abre
transporte, no construye un ``GapRequest`` y no elige cuándo reintentar.
"""
from __future__ import annotations
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID
from core.domain.attempt import SyncAttempt
from core.domain.event import TelemetryEvent
from core.domain.gap import MissingSequenceRange
from core.domain.state import TelemetryEventState
from core.domain.sync import TelemetrySyncState

@dataclass(frozen=True, slots=True)
class MarsNodeStatus:
    """Contadores resumidos de una fuente en Marte."""

    source_id: str
    generated: int
    pending: int
    latest_sequence_number: int | None

@dataclass(frozen=True, slots=True)
class MarsApplicationStatus:
    """Instantánea de contadores de una fuente.
    Agrupa una lectura. No abre un nodo ni decide un reintento.
    """
    source_id: str
    generated: int
    pending: int
    confirmed: int
    local_persisted: int
    in_flight: int
    latest_sequence_number: int | None
    retry_attempts_total: int
    active_sync: int
    max_generated_at_sim: float | None
    max_confirmed_at_sim: float | None

@dataclass(frozen=True, slots=True)
class EarthIngestResult:
    """Resultado de una ingesta, en el orden de entrada.
    ``persisted_event_ids`` son altas nuevas. ``duplicate_event_ids`` son
    repeticiones de esta llamada: mismo ``event_id`` o misma pareja
    ``source_id`` + ``sequence_number``. La primera versión se conserva.
    """
    persisted_event_ids: tuple[UUID, ...]
    duplicate_event_ids: tuple[UUID, ...]

@dataclass(frozen=True, slots=True)
class EarthPersistenceRecord:
    """Fila única persistida en Tierra.
    ``first_persisted_at_sim`` es el instante de la primera aceptación.
    Una repetición posterior no lo cambia.
    """
    event_id: UUID
    source_id: str
    sequence_number: int
    generated_at_sim: float
    first_persisted_at_sim: float

@runtime_checkable
class MarsStateRepository(Protocol):
    """Estado de aplicación de Marte para una corrida.
    Guarda el ``TelemetryEvent`` original, su outbox y los ``SyncAttempt``
    que el llamador ya construyó. Una consulta de pendientes sigue el orden
    de registro de esa fuente. No ordena por ``(source_id, sequence_number)``:
    ese orden, si hace falta para elegir qué enviar, lo aplica quien llama.
    """
    def close(self) -> None: ...

    def wipe(self) -> None: ...

    def commit_new_event(
        self,
        source_id: str,
        factory: Callable[[int], TelemetryEvent],
    ) -> TelemetryEvent: ...

    def commit_new_events(
        self,
        source_id: str,
        count: int,
        factory: Callable[[int], TelemetryEvent],
    ) -> list[TelemetryEvent]: ...

    def persist(self, event: TelemetryEvent) -> None: ...

    def generated_count(self, source_id: str) -> int: ...

    def max_generated_at_sim(self, source_id: str) -> float | None: ...

    def max_confirmed_at_sim(self, source_id: str) -> float | None: ...

    def confirmed_at_sim(self, event_id: UUID) -> float | None: ...

    def pending_count(self, source_id: str) -> int: ...

    def confirmed_count(self, source_id: str) -> int: ...

    def local_persisted_count(self, source_id: str) -> int: ...

    def in_flight_count(self, source_id: str) -> int: ...

    def latest_sequence_number(self, source_id: str) -> int | None: ...

    def pending_events(self, source_id: str) -> list[TelemetryEvent]: ...

    def retry_eligible_events(self, source_id: str) -> list[TelemetryEvent]: ...

    def events_for_source(self, source_id: str) -> list[TelemetryEvent]: ...

    def events_for_sequence_ranges(
        self,
        source_id: str,
        ranges: Sequence[MissingSequenceRange],
    ) -> list[TelemetryEvent]: ...

    def get_event(self, event_id: UUID) -> TelemetryEvent | None: ...

    def sync_state(self, event_id: UUID) -> TelemetrySyncState | None: ...

    def transition_history(self, event_id: UUID) -> list[TelemetryEventState]: ...

    def status(self, source_id: str) -> MarsNodeStatus: ...

    def application_status(self, source_id: str) -> MarsApplicationStatus: ...

    def record_observability_state(
        self,
        event_id: UUID,
        state: TelemetryEventState,
        at_sim: float,
        attempt_id: str | None = None,
    ) -> None: ...

    def confirm_events(self, event_ids: Sequence[UUID], at_sim: float) -> None: ...

    def save_sync_attempt(self, attempt: SyncAttempt, sync_unit_id: str | None) -> None: ...

    def get_sync_attempt(self, attempt_id: str) -> SyncAttempt | None: ...

    def sync_unit_id_for_attempt(self, attempt_id: str) -> str | None: ...

    def sync_attempts_for_event(self, event_id: UUID) -> list[SyncAttempt]: ...

    def latest_sync_attempt_for_event(self, event_id: UUID) -> SyncAttempt | None: ...

    def latest_sync_attempt_for_group(self, sync_group_id: str) -> SyncAttempt | None: ...

    def active_sync_attempt_for_event(self, event_id: UUID) -> SyncAttempt | None: ...

    def active_sync_count(self, source_id: str) -> int: ...

    def retry_attempts_total(self, source_id: str) -> int: ...

@runtime_checkable
class EarthStateRepository(Protocol):
    """Estado de aplicación de Tierra para una corrida.
    La ingesta es idempotente: el primer ``event_id`` y la primera pareja
    ``source_id`` + ``sequence_number`` se conservan. Una repetición no
    reemplaza la fila y no crea otra. Al aceptar una secuencia nueva, el
    repositorio observa esa secuencia en el índice de huecos de la fuente.
    No registra pedidos de reparación.
    """
    def close(self) -> None: ...

    def wipe(self) -> None: ...

    def ingest(
        self, events: Sequence[TelemetryEvent], ingested_at_sim: float
    ) -> EarthIngestResult: ...

    def get_event(self, event_id: UUID) -> TelemetryEvent | None: ...

    def event_count(self) -> int: ...

    def unique_event_count(self) -> int: ...

    def max_generated_at_sim(self) -> float | None: ...

    def persistence_sample_count(self) -> int: ...

    def persistence_samples(self) -> tuple[tuple[float, float], ...]: ...

    def persistence_records(self) -> tuple[EarthPersistenceRecord, ...]: ...

    def duplicates_stored(self) -> int: ...

    def duplicates_received(self) -> int: ...

    def duplicate_receipts_for(self, event_id: UUID) -> int: ...

    def sequence_numbers(self, source_id: str) -> tuple[int, ...]: ...

    def gaps_for_source(self, source_id: str) -> tuple[int, ...]: ...

    def gap_ranges_for_source(self, source_id: str) -> tuple[MissingSequenceRange, ...]: ...

    def gaps_count(self) -> int: ...
