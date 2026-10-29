"""Estado de Tierra en memoria para una corrida científica.
Persiste cada evento una sola vez y observa la secuencia aceptada en el
índice de huecos de esa fuente. No escribe a disco, no reemplaza un
duplicado y no registra un pedido de reparación.
"""
from __future__ import annotations
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID
from core.domain.event import TelemetryEvent
from core.domain.gap import MissingSequenceRange
from core.gap.index import EarthGapRangeStore
from core.state.ports import EarthIngestResult, EarthPersistenceRecord, EarthStateRepository

@dataclass
class _EarthRow:
    event: TelemetryEvent
    first_persisted_at_sim: float

class FastEarthStateRepository:
    """Estado lógico de Tierra dentro de una corrida, solo en memoria.
    Modela la ingesta durable de esa corrida. No demuestra que el estado
    sobreviva a una caída del proceso.
    """
    def __init__(self) -> None:
        self._by_id: dict[UUID, _EarthRow] = {}
        self._by_source_sequence: dict[tuple[str, int], UUID] = {}
        self._gap_ranges = EarthGapRangeStore()
        self._unique_count = 0
        self._duplicates_received = 0
        self._duplicate_receipts: dict[UUID, int] = {}
        self._max_generated_at_sim: float | None = None
        self._records: list[EarthPersistenceRecord] = []

    def close(self) -> None:
        """No libera recursos externos. El estado en memoria sigue disponible."""
        return

    def wipe(self) -> None:
        """Vacía eventos, secuencias, huecos y recibos duplicados."""
        self._by_id.clear()
        self._by_source_sequence.clear()
        self._gap_ranges.clear()
        self._unique_count = 0
        self._duplicates_received = 0
        self._duplicate_receipts.clear()
        self._max_generated_at_sim = None
        self._records.clear()

    def ingest(
        self, events: Sequence[TelemetryEvent], ingested_at_sim: float
    ) -> EarthIngestResult:
        """Acepta eventos nuevos y marca el resto como duplicados.
        Dentro de la llamada, y contra lo ya persistido, se considera
        duplicado un ``event_id`` ya visto o una pareja
        ``source_id`` + ``sequence_number`` ya vista. La primera versión se
        conserva: no se reemplaza ni se guarda una segunda fila. El orden de
        ambas tuplas del resultado es el orden de entrada. Una secuencia
        vacía no cambia el estado.
        """
        unique: list[TelemetryEvent] = []
        duplicates: list[UUID] = []
        seen_event_ids: set[UUID] = set()
        seen_source_sequences: set[tuple[str, int]] = set()
        for event in events:
            key = (event.source_id, event.sequence_number)
            if event.event_id in self._by_id or event.event_id in seen_event_ids:
                duplicates.append(event.event_id)
                continue
            if key in self._by_source_sequence or key in seen_source_sequences:
                duplicates.append(event.event_id)
                continue
            unique.append(event)
            seen_event_ids.add(event.event_id)
            seen_source_sequences.add(key)
        for event in unique:
            self._commit_unique(event, ingested_at_sim)
        for event_id in duplicates:
            self._note_duplicate(event_id)
        return EarthIngestResult(
            persisted_event_ids=tuple(event.event_id for event in unique),
            duplicate_event_ids=tuple(duplicates),
        )

    def get_event(self, event_id: UUID) -> TelemetryEvent | None:
        """El mismo objeto de la primera aceptación, o ``None`` si no está."""
        row = self._by_id.get(event_id)
        if row is None:
            return None
        return row.event

    def event_count(self) -> int:
        """Cantidad de eventos únicos persistidos."""
        return self.unique_event_count()

    def unique_event_count(self) -> int:
        """Cantidad de eventos únicos persistidos."""
        return self._unique_count

    def max_generated_at_sim(self) -> float | None:
        """Mayor ``generated_at_sim`` entre los únicos, o ``None`` si no hay."""
        return self._max_generated_at_sim

    def persistence_sample_count(self) -> int:
        """Cantidad de pares de frescura, una por evento único."""
        return self._unique_count

    def persistence_samples(self) -> tuple[tuple[float, float], ...]:
        """Pares ``(generated_at_sim, first_persisted_at_sim)``, en orden de alta."""
        return tuple(
            (record.generated_at_sim, record.first_persisted_at_sim) for record in self._records
        )

    def persistence_records(self) -> tuple[EarthPersistenceRecord, ...]:
        """Filas únicas en el orden en que fueron aceptadas, no por secuencia."""
        return tuple(self._records)

    def duplicates_stored(self) -> int:
        """Siempre 0: un duplicado no crea fila."""
        return 0

    def duplicates_received(self) -> int:
        """Veces que una ingesta marcó un evento como duplicado."""
        return self._duplicates_received

    def duplicate_receipts_for(self, event_id: UUID) -> int:
        """Recibos duplicados de ese id. Un id nunca visto vale 0.

        Si el conflicto es de secuencia, el contador usa el ``event_id``
        rechazado, no el de la fila conservada.
        """
        return self._duplicate_receipts.get(event_id, 0)

    def sequence_numbers(self, source_id: str) -> tuple[int, ...]:
        """Secuencias únicas de la fuente, de menor a mayor.

        Una fuente sin eventos devuelve una tupla vacía.
        """
        return tuple(
            sorted(
                sequence
                for stored_source, sequence in self._by_source_sequence
                if stored_source == source_id
            )
        )

    def gaps_for_source(self, source_id: str) -> tuple[int, ...]:
        """Enteros faltantes de la fuente, por debajo de su máxima observada."""
        missing: list[int] = []
        for item in self._gap_ranges.ranges_for_source(source_id):
            missing.extend(range(item.start_sequence, item.end_sequence + 1))
        return tuple(missing)

    def gap_ranges_for_source(self, source_id: str) -> tuple[MissingSequenceRange, ...]:
        """Rangos faltantes observados al aceptar cada secuencia nueva."""
        return self._gap_ranges.ranges_for_source(source_id)

    def gaps_count(self) -> int:
        """Enteros faltantes sumados entre todas las fuentes."""
        return self._gap_ranges.count()

    def _commit_unique(self, event: TelemetryEvent, ingested_at_sim: float) -> None:
        row = _EarthRow(event=event, first_persisted_at_sim=ingested_at_sim)
        self._by_id[event.event_id] = row
        self._by_source_sequence[(event.source_id, event.sequence_number)] = event.event_id
        self._records.append(
            EarthPersistenceRecord(
                event_id=event.event_id,
                source_id=event.source_id,
                sequence_number=event.sequence_number,
                generated_at_sim=event.generated_at_sim,
                first_persisted_at_sim=ingested_at_sim,
            )
        )
        self._gap_ranges.observe(event.source_id, event.sequence_number)
        self._unique_count += 1
        if (
            self._max_generated_at_sim is None
            or event.generated_at_sim > self._max_generated_at_sim
        ):
            self._max_generated_at_sim = event.generated_at_sim

    def _note_duplicate(self, event_id: UUID) -> None:
        self._duplicates_received += 1
        self._duplicate_receipts[event_id] = self._duplicate_receipts.get(event_id, 0) + 1


assert isinstance(FastEarthStateRepository(), EarthStateRepository)
