"""Estado de Marte en memoria para una corrida científica.
Conserva el ``TelemetryEvent`` original, el outbox y los intentos que el
llamador entrega. No elige cuándo reintentar, no ordena la selección de
envío y no escribe a disco.
"""
from __future__ import annotations
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from uuid import UUID
from core.domain.attempt import ACTIVE_ATTEMPT_STATUSES, SyncAttempt, SyncAttemptStatus
from core.domain.event import TelemetryEvent
from core.domain.gap import MissingSequenceRange, normalize_missing_ranges
from core.domain.state import TelemetryEventState
from core.domain.sync import TelemetrySyncState
from core.state.errors import DuplicateTelemetryEventError
from core.state.ports import MarsApplicationStatus, MarsNodeStatus, MarsStateRepository

# Historial inicial de un alta. El estado vigente del outbox queda en PENDING.
_COMMIT_STATES = (
    TelemetryEventState.GENERATED,
    TelemetryEventState.PERSISTED_LOCAL,
    TelemetryEventState.PENDING,
)

# Se anotan en el historial. No reemplazan el PENDING del outbox.
_OBSERVABILITY = {
    TelemetryEventState.IN_FLIGHT,
    TelemetryEventState.PERSISTED_EARTH,
}

# La lista de pendientes es append-only con tumbas. Solo se compacta de vez en cuando.
_PENDING_COMPACT_MIN_LEN = 4096
_PENDING_COMPACT_LIVE_RATIO = 0.5

@dataclass
class _Outbox:
    state: TelemetryEventState
    last_transition_at_sim: float
    retry_count: int

@dataclass
class _HistoryEntry:
    state: TelemetryEventState
    at_sim: float
    ordinal: int
    attempt_id: str | None

@dataclass
class _AttemptRecord:
    attempt: SyncAttempt
    sync_unit_id: str | None
    event_ids: tuple[UUID, ...]

@dataclass
class _SourceIndex:
    event_ids_by_sequence: list[UUID] = field(default_factory=list)
    pending_event_ids: list[UUID] = field(default_factory=list)
    pending_set: set[UUID] = field(default_factory=set)
    confirmed_event_ids: set[UUID] = field(default_factory=set)
    generated: int = 0
    pending: int = 0
    confirmed: int = 0
    in_flight: int = 0
    next_sequence: int = 0
    max_generated_at_sim: float | None = None
    max_confirmed_at_sim: float | None = None

class FastMarsStateRepository:
    """Estado lógico de Marte dentro de una corrida, solo en memoria.
    Modela la durabilidad de aplicación de esa corrida. No demuestra que
    el estado sobreviva a una caída del proceso.
    """
    def __init__(self) -> None:
        self._events_by_id: dict[UUID, TelemetryEvent] = {}
        self._outbox: dict[UUID, _Outbox] = {}
        self._history: dict[UUID, list[_HistoryEntry]] = {}
        self._source: dict[str, _SourceIndex] = {}
        self._attempts_by_id: dict[str, _AttemptRecord] = {}
        self._attempt_ids_by_event: dict[UUID, list[str]] = {}
        self._active_attempt_by_event: dict[UUID, str] = {}
        self._latest_attempt_by_event: dict[UUID, str] = {}
        self._latest_attempt_by_group: dict[str, str] = {}
        self._retry_attempt_ids_by_source: dict[str, set[str]] = {}
        self._event_source: dict[UUID, str] = {}
        self._pending_compactions = 0

    def close(self) -> None:
        """No libera recursos externos. El estado en memoria sigue disponible."""
        return

    def wipe(self) -> None:
        """Vacía eventos, outbox, historial, secuencias e intentos."""
        self._events_by_id.clear()
        self._outbox.clear()
        self._history.clear()
        self._source.clear()
        self._attempts_by_id.clear()
        self._attempt_ids_by_event.clear()
        self._active_attempt_by_event.clear()
        self._latest_attempt_by_event.clear()
        self._latest_attempt_by_group.clear()
        self._retry_attempt_ids_by_source.clear()
        self._event_source.clear()
        self._pending_compactions = 0

    def commit_new_event(
        self,
        source_id: str,
        factory: Callable[[int], TelemetryEvent],
    ) -> TelemetryEvent:
        """Registra un evento nuevo y le asigna la próxima secuencia de la fuente."""
        return self.commit_new_events(source_id, 1, factory)[0]

    def commit_new_events(
        self,
        source_id: str,
        count: int,
        factory: Callable[[int], TelemetryEvent],
    ) -> list[TelemetryEvent]:
        """Registra ``count`` eventos como un solo alta.

        La fábrica recibe cada secuencia, empezando por la próxima de la
        fuente. Si algún ``event_id`` ya existe o el ``source_id`` no
        coincide, no se inserta ninguno de este grupo y la secuencia no avanza.
        El orden de la lista devuelta es el de asignación.
        """
        if count < 1:
            raise ValueError("count debe ser >= 1")
        index = self._source.setdefault(source_id, _SourceIndex())
        planned: list[TelemetryEvent] = []
        sequence = index.next_sequence
        for offset in range(count):
            event = factory(sequence + offset)
            planned.append(event)
        for event in planned:
            if event.event_id in self._events_by_id:
                raise DuplicateTelemetryEventError(event.event_id)
            if event.source_id != source_id:
                raise ValueError("el source_id del evento no coincide con la fuente del commit")
        for event in planned:
            self._insert_event_and_outbox(event, index)
        index.next_sequence = sequence + count
        return planned

    def persist(self, event: TelemetryEvent) -> None:
        """Guarda un evento que ya trae su secuencia.

        Un ``event_id`` repetido se rechaza. El objeto recibido se almacena
        tal cual. Si la secuencia es mayor o igual que la próxima, la próxima
        pasa a ser esa secuencia más uno.
        """
        if event.event_id in self._events_by_id:
            raise DuplicateTelemetryEventError(event.event_id)
        index = self._source.setdefault(event.source_id, _SourceIndex())
        self._insert_event_and_outbox(event, index)
        if event.sequence_number >= index.next_sequence:
            index.next_sequence = event.sequence_number + 1

    def generated_count(self, source_id: str) -> int:
        """Eventos registrados para la fuente. Una fuente desconocida vale 0."""
        return self._source.get(source_id, _SourceIndex()).generated

    def max_generated_at_sim(self, source_id: str) -> float | None:
        """Mayor ``generated_at_sim`` registrado, o ``None`` si no hay eventos."""
        return self._source.get(source_id, _SourceIndex()).max_generated_at_sim

    def max_confirmed_at_sim(self, source_id: str) -> float | None:
        """Mayor instante de confirmación de la fuente, o ``None`` si no hubo."""
        return self._source.get(source_id, _SourceIndex()).max_confirmed_at_sim

    def pending_count(self, source_id: str) -> int:
        """Eventos cuyo outbox todavía no está confirmado."""
        return self._source.get(source_id, _SourceIndex()).pending

    def confirmed_count(self, source_id: str) -> int:
        """Eventos confirmados de la fuente."""
        return self._source.get(source_id, _SourceIndex()).confirmed

    def local_persisted_count(self, source_id: str) -> int:
        """Coincide con los eventos generados: el alta ya los dejó persistidos."""
        return self.generated_count(source_id)

    def in_flight_count(self, source_id: str) -> int:
        """Eventos cuyo intento vigente acaba de quedar ``IN_FLIGHT``.

        Confirmar un evento no descuenta este contador. Lo actualiza
        ``save_sync_attempt`` cuando cambia el estado del intento.
        """
        return self._source.get(source_id, _SourceIndex()).in_flight

    def latest_sequence_number(self, source_id: str) -> int | None:
        """Última posición del índice de secuencia, o ``None`` si está vacío."""
        index = self._source.get(source_id)
        if index is None or not index.event_ids_by_sequence:
            return None
        return len(index.event_ids_by_sequence) - 1

    def pending_events(self, source_id: str) -> list[TelemetryEvent]:
        """Pendientes de la fuente, en orden de registro.

        Una confirmación deja una tumba y no reordena al resto. No se ordena
        por ``sequence_number``. Una fuente desconocida devuelve una lista vacía.
        """
        index = self._source.get(source_id)
        if index is None or not index.pending_set:
            return []
        return [
            self._events_by_id[event_id]
            for event_id in index.pending_event_ids
            if event_id in index.pending_set
        ]

    def retry_eligible_events(self, source_id: str) -> list[TelemetryEvent]:
        """Pendientes sin un intento activo, en el mismo orden de registro.

        Es una consulta. No crea un intento ni aplica una política de retry.
        """
        index = self._source.get(source_id)
        if index is None or not index.pending_set:
            return []
        eligible: list[TelemetryEvent] = []
        for event_id in index.pending_event_ids:
            if event_id not in index.pending_set:
                continue
            if event_id in self._active_attempt_by_event:
                continue
            eligible.append(self._events_by_id[event_id])
        return eligible

    def events_for_source(self, source_id: str) -> list[TelemetryEvent]:
        """Eventos según el índice de secuencia, de la posición 0 en adelante.

        Incluye confirmados. Una fuente desconocida devuelve una lista vacía.
        """
        index = self._source.get(source_id)
        if index is None:
            return []
        return [self._events_by_id[event_id] for event_id in index.event_ids_by_sequence]

    def events_for_sequence_ranges(
        self,
        source_id: str,
        ranges: Sequence[MissingSequenceRange],
    ) -> list[TelemetryEvent]:
        """Eventos originales de las secuencias pedidas.

        Los rangos se normalizan y se recorren de menor a mayor. Una secuencia
        que no tiene un evento con ese ``sequence_number`` se omite. No se
        inventa el evento faltante.
        """
        index = self._source.get(source_id)
        if index is None:
            return []
        found: list[TelemetryEvent] = []
        limit = len(index.event_ids_by_sequence)
        for rng in normalize_missing_ranges(ranges):
            if rng.start_sequence >= limit:
                continue
            last = min(rng.end_sequence, limit - 1)
            for sequence in range(rng.start_sequence, last + 1):
                event_id = index.event_ids_by_sequence[sequence]
                event = self._events_by_id.get(event_id)
                if event is None or event.sequence_number != sequence:
                    continue
                found.append(event)
        return found

    def get_event(self, event_id: UUID) -> TelemetryEvent | None:
        """El mismo objeto registrado, o ``None`` si el id no existe."""
        return self._events_by_id.get(event_id)

    def sync_state(self, event_id: UUID) -> TelemetrySyncState | None:
        """Copia del outbox vigente. Mutarla no cambia el repositorio.

        Un id desconocido devuelve ``None``. Hasta la confirmación el estado
        vigente es ``PENDING``, aunque el historial haya anotado observabilidad.
        """
        outbox = self._outbox.get(event_id)
        if outbox is None:
            return None
        return TelemetrySyncState(
            event_id=event_id,
            state=outbox.state,
            last_transition_at_sim=outbox.last_transition_at_sim,
            retry_count=outbox.retry_count,
        )

    def transition_history(self, event_id: UUID) -> list[TelemetryEventState]:
        """Estados anotados, del más antiguo al más reciente.

        Un id desconocido devuelve una lista vacía. La lista es nueva: vaciarla
        no borra el historial guardado.
        """
        rows = self._history.get(event_id, [])
        return [row.state for row in rows]

    def status(self, source_id: str) -> MarsNodeStatus:
        """Contadores resumidos de la fuente."""
        snapshot = self.application_status(source_id)
        return MarsNodeStatus(
            source_id=snapshot.source_id,
            generated=snapshot.generated,
            pending=snapshot.pending,
            latest_sequence_number=snapshot.latest_sequence_number,
        )

    def application_status(self, source_id: str) -> MarsApplicationStatus:
        """Instantánea de contadores. Una fuente desconocida queda en ceros."""
        index = self._source.get(source_id, _SourceIndex())
        latest = self.latest_sequence_number(source_id)
        return MarsApplicationStatus(
            source_id=source_id,
            generated=index.generated,
            pending=index.pending,
            confirmed=index.confirmed,
            local_persisted=index.generated,
            in_flight=index.in_flight,
            latest_sequence_number=latest,
            retry_attempts_total=len(self._retry_attempt_ids_by_source.get(source_id, ())),
            active_sync=self.active_sync_count(source_id),
            max_generated_at_sim=index.max_generated_at_sim,
            max_confirmed_at_sim=index.max_confirmed_at_sim,
        )

    def record_observability_state(
        self,
        event_id: UUID,
        state: TelemetryEventState,
        at_sim: float,
        attempt_id: str | None = None,
    ) -> None:
        """Anota ``IN_FLIGHT`` o ``PERSISTED_EARTH`` solo en el historial.
        El outbox sigue en ``PENDING`` hasta el ACK. El mismo estado con el
        mismo ``attempt_id`` no se repite y no mueve el instante. Otro
        ``attempt_id`` sí se anota. Un id desconocido o ya confirmado no hace
        nada. Cualquier otro estado lanza ``ValueError``.
        """
        if state not in _OBSERVABILITY:
            raise ValueError(
                "el registro de observabilidad solo admite IN_FLIGHT y PERSISTED_EARTH"
            )
        outbox = self._outbox.get(event_id)
        if outbox is None or event_id not in self._events_by_id:
            return
        if outbox.state is TelemetryEventState.CONFIRMED:
            return
        history = self._history.setdefault(event_id, [])
        for row in history:
            if row.state is state and row.attempt_id == attempt_id:
                return
        next_ordinal = 0 if not history else history[-1].ordinal + 1
        history.append(
            _HistoryEntry(
                state=state,
                at_sim=at_sim,
                ordinal=next_ordinal,
                attempt_id=attempt_id,
            )
        )
        outbox.last_transition_at_sim = at_sim

    def confirm_events(self, event_ids: Sequence[UUID], at_sim: float) -> None:
        """Confirma los ids conocidos que todavía no lo están.

        Un id desconocido, una lista vacía o un id que ya estaba confirmado
        se omiten. La revisión ocurre antes de aplicar, así que un id repetido
        en la misma llamada se aplica una vez por aparición: el pendiente baja
        solo la primera, y confirmados e historial avanzan en cada una. Una
        llamada posterior ya lo encuentra confirmado y no lo toca. El evento
        original sigue consultable. No cambia ``in_flight``.
        """
        planned: list[UUID] = []
        for event_id in event_ids:
            outbox = self._outbox.get(event_id)
            if outbox is None or event_id not in self._events_by_id:
                continue
            if outbox.state is TelemetryEventState.CONFIRMED:
                continue
            planned.append(event_id)
        for event_id in planned:
            outbox = self._outbox[event_id]
            source_id = self._event_source[event_id]
            index = self._source[source_id]
            outbox.state = TelemetryEventState.CONFIRMED
            outbox.last_transition_at_sim = at_sim
            history = self._history.setdefault(event_id, [])
            next_ordinal = 0 if not history else history[-1].ordinal + 1
            history.append(
                _HistoryEntry(
                    state=TelemetryEventState.CONFIRMED,
                    at_sim=at_sim,
                    ordinal=next_ordinal,
                    attempt_id=None,
                )
            )
            if event_id in index.pending_set:
                index.pending_set.discard(event_id)
                index.pending -= 1
            index.confirmed_event_ids.add(event_id)
            index.confirmed += 1
            if index.max_confirmed_at_sim is None or at_sim > index.max_confirmed_at_sim:
                index.max_confirmed_at_sim = at_sim
        if planned:
            affected: list[str] = []
            seen_sources: set[str] = set()
            for event_id in planned:
                source_id = self._event_source[event_id]
                if source_id in seen_sources:
                    continue
                seen_sources.add(source_id)
                affected.append(source_id)
            for source_id in affected:
                self._maybe_compact_pending(self._source[source_id])

    def save_sync_attempt(self, attempt: SyncAttempt, sync_unit_id: str | None) -> None:
        """Guarda el intento recibido.

        La primera vez, un ``attempt_number`` mayor que 1 incrementa
        ``retry_count`` de cada evento que ya tiene outbox. Una actualización
        del mismo ``attempt_id`` no vuelve a incrementar. Si ``sync_unit_id``
        llega ``None`` en una actualización, se conserva el valor anterior.
        Un intento activo queda asociado al evento; uno terminal lo suelta
        solo si era el intento activo. No decide crear el siguiente intento.
        """
        existing = self._attempts_by_id.get(attempt.attempt_id)
        previous_status = existing.attempt.status if existing is not None else None
        resolved_unit = sync_unit_id
        if existing is not None and sync_unit_id is None:
            resolved_unit = existing.sync_unit_id
        record = _AttemptRecord(
            attempt=attempt,
            sync_unit_id=resolved_unit,
            event_ids=tuple(attempt.event_ids),
        )
        self._attempts_by_id[attempt.attempt_id] = record
        if existing is None:
            for event_id in attempt.event_ids:
                self._attempt_ids_by_event.setdefault(event_id, []).append(attempt.attempt_id)
                if attempt.attempt_number > 1:
                    outbox = self._outbox.get(event_id)
                    if outbox is not None:
                        outbox.retry_count += 1
                    source_id = self._event_source.get(event_id)
                    if source_id is not None:
                        self._retry_attempt_ids_by_source.setdefault(source_id, set()).add(
                            attempt.attempt_id
                        )
        else:
            wanted = set(attempt.event_ids)
            already = set(existing.event_ids)
            for event_id in wanted - already:
                ids = self._attempt_ids_by_event.setdefault(event_id, [])
                if attempt.attempt_id not in ids:
                    ids.append(attempt.attempt_id)
            record.event_ids = tuple(attempt.event_ids)
        for event_id in attempt.event_ids:
            latest_id = self._latest_attempt_by_event.get(event_id)
            if latest_id is None:
                self._latest_attempt_by_event[event_id] = attempt.attempt_id
            else:
                latest = self._attempts_by_id[latest_id].attempt
                if attempt.attempt_number >= latest.attempt_number:
                    self._latest_attempt_by_event[event_id] = attempt.attempt_id
            source_id = self._event_source.get(event_id)
            if source_id is not None:
                if attempt.status in ACTIVE_ATTEMPT_STATUSES:
                    self._active_attempt_by_event[event_id] = attempt.attempt_id
                elif self._active_attempt_by_event.get(event_id) == attempt.attempt_id:
                    del self._active_attempt_by_event[event_id]
                self._update_in_flight(
                    source_id,
                    event_id,
                    previous_status=previous_status if existing is not None else None,
                    new_status=attempt.status,
                )
        group_id = attempt.sync_group_id
        latest_group = self._latest_attempt_by_group.get(group_id)
        if latest_group is None:
            self._latest_attempt_by_group[group_id] = attempt.attempt_id
        else:
            latest = self._attempts_by_id[latest_group].attempt
            if attempt.attempt_number >= latest.attempt_number:
                self._latest_attempt_by_group[group_id] = attempt.attempt_id

    def get_sync_attempt(self, attempt_id: str) -> SyncAttempt | None:
        """El mismo objeto guardado, o ``None`` si el intento no existe."""
        record = self._attempts_by_id.get(attempt_id)
        if record is None:
            return None
        return record.attempt

    def sync_unit_id_for_attempt(self, attempt_id: str) -> str | None:
        """Unidad asociada al intento, o ``None`` si no hay intento o no hay unidad."""
        record = self._attempts_by_id.get(attempt_id)
        if record is None:
            return None
        return record.sync_unit_id

    def sync_attempts_for_event(self, event_id: UUID) -> list[SyncAttempt]:
        """Intentos del evento, de menor a mayor ``attempt_number``.

        Un evento sin intentos devuelve una lista vacía.
        """
        ids = self._attempt_ids_by_event.get(event_id, [])
        attempts = [self._attempts_by_id[item].attempt for item in ids]
        attempts.sort(key=lambda item: item.attempt_number)
        return attempts

    def latest_sync_attempt_for_event(self, event_id: UUID) -> SyncAttempt | None:
        """Intento de mayor ``attempt_number`` del evento, o ``None``."""
        attempt_id = self._latest_attempt_by_event.get(event_id)
        if attempt_id is None:
            return None
        return self._attempts_by_id[attempt_id].attempt

    def latest_sync_attempt_for_group(self, sync_group_id: str) -> SyncAttempt | None:
        """Intento de mayor ``attempt_number`` del grupo, o ``None``."""
        attempt_id = self._latest_attempt_by_group.get(sync_group_id)
        if attempt_id is None:
            return None
        return self._attempts_by_id[attempt_id].attempt

    def active_sync_attempt_for_event(self, event_id: UUID) -> SyncAttempt | None:
        """Intento activo del evento, o ``None`` si no tiene uno."""
        attempt_id = self._active_attempt_by_event.get(event_id)
        if attempt_id is None:
            return None
        return self._attempts_by_id[attempt_id].attempt

    def active_sync_count(self, source_id: str) -> int:
        """Cantidad de intentos activos distintos entre los pendientes de la fuente."""
        index = self._source.get(source_id)
        if index is None or not index.pending_set:
            return 0
        counted: set[str] = set()
        for event_id in index.pending_event_ids:
            if event_id not in index.pending_set:
                continue
            attempt_id = self._active_attempt_by_event.get(event_id)
            if attempt_id is not None:
                counted.add(attempt_id)
        return len(counted)

    @property
    def pending_compaction_count(self) -> int:
        """Veces que se compactó la lista de pendientes.

        Diagnóstico del índice de tumbas. No es una métrica científica.
        """
        return self._pending_compactions

    def retry_attempts_total(self, source_id: str) -> int:
        """Intentos con ``attempt_number`` mayor que 1 guardados para la fuente."""
        return len(self._retry_attempt_ids_by_source.get(source_id, ()))

    def _insert_event_and_outbox(self, event: TelemetryEvent, index: _SourceIndex) -> None:
        sequence = event.sequence_number
        while len(index.event_ids_by_sequence) <= sequence:
            index.event_ids_by_sequence.append(event.event_id)
        index.event_ids_by_sequence[sequence] = event.event_id
        self._events_by_id[event.event_id] = event
        self._event_source[event.event_id] = event.source_id
        self._outbox[event.event_id] = _Outbox(
            state=TelemetryEventState.PENDING,
            last_transition_at_sim=event.generated_at_sim,
            retry_count=0,
        )
        self._history[event.event_id] = [
            _HistoryEntry(
                state=state,
                at_sim=event.generated_at_sim,
                ordinal=ordinal,
                attempt_id=None,
            )
            for ordinal, state in enumerate(_COMMIT_STATES)
        ]
        index.pending_event_ids.append(event.event_id)
        index.pending_set.add(event.event_id)
        index.generated += 1
        index.pending += 1
        if (
            index.max_generated_at_sim is None
            or event.generated_at_sim > index.max_generated_at_sim
        ):
            index.max_generated_at_sim = event.generated_at_sim

    def _update_in_flight(
        self,
        source_id: str,
        event_id: UUID,
        *,
        previous_status: SyncAttemptStatus | None,
        new_status: SyncAttemptStatus,
    ) -> None:
        index = self._source[source_id]
        was = previous_status is SyncAttemptStatus.IN_FLIGHT
        now = (
            new_status is SyncAttemptStatus.IN_FLIGHT
            and self._active_attempt_by_event.get(event_id) is not None
        )
        if was and not now:
            index.in_flight = max(0, index.in_flight - 1)
        elif now and not was:
            index.in_flight += 1

    def _maybe_compact_pending(self, index: _SourceIndex) -> None:
        stored = len(index.pending_event_ids)
        if stored <= _PENDING_COMPACT_MIN_LEN:
            return
        live = len(index.pending_set)
        if live / stored >= _PENDING_COMPACT_LIVE_RATIO:
            return
        index.pending_event_ids = [
            event_id for event_id in index.pending_event_ids if event_id in index.pending_set
        ]
        self._pending_compactions += 1


assert isinstance(FastMarsStateRepository(), MarsStateRepository)
