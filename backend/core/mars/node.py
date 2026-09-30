"""Aplicación local de una fuente en Marte.
Registra telemetría en el repositorio inyectado y consulta el outbox de
esa fuente. El instante de simulación lo aporta quien llama. La secuencia
la asigna el repositorio en ``commit_new_events``.
"""
from __future__ import annotations
from collections.abc import Callable, Sequence
from typing import Any
from uuid import UUID
from core.domain.ack import ApplicationAck, ApplicationAckStatus
from core.domain.attempt import SyncAttempt
from core.domain.event import TelemetryEvent
from core.domain.gap import MissingSequenceRange
from core.domain.identity import make_telemetry_event_id
from core.domain.priority import TelemetryPriority
from core.domain.state import TelemetryEventState
from core.domain.sync import TelemetrySyncState
from core.state.ports import MarsApplicationStatus, MarsNodeStatus, MarsStateRepository

DEFAULT_SOURCE_ID = "MSR-SURFACE-01"
DEFAULT_SCHEMA_VERSION = 1

class MarsNode:
    """Fuente de telemetría en Marte, con el estado de aplicación inyectado.
    Genera eventos, los deja pendientes y responde consultas de esa fuente.
    Un intento que ya existe se guarda tal cual llega: este nodo no lo
    numera, no agrupa eventos en un plan y no arma una SyncUnit. Un ACK
    durable confirma eventos ya aceptados; no cambia el intento.
    """
    def __init__(
        self,
        repository: MarsStateRepository,
        source_id: str = DEFAULT_SOURCE_ID,
        schema_version: int = DEFAULT_SCHEMA_VERSION,
    ) -> None:
        if source_id.strip() == "":
            raise ValueError("source_id no debe estar vacío")
        self._source_id = source_id
        self._schema_version = schema_version
        self._experiment_identity: str | None = None
        self._repository = repository

    @property
    def source_id(self) -> str:
        """Identificador de la fuente que este nodo registra."""
        return self._source_id

    def close(self) -> None:
        """Cierra el repositorio inyectado. No borra el estado."""
        self._repository.close()

    def wipe(self) -> None:
        """Vacía el repositorio y olvida la identidad de dataset vinculada."""
        self._experiment_identity = None
        self._repository.wipe()

    def bind_experiment_identity(self, identity: str | None) -> None:
        """Fija la identidad de dataset usada para ``event_id``.

        Con una identidad, cada alta usa ``make_telemetry_event_id``.
        ``None`` vuelve a dejar que el evento reciba un ``event_id`` nuevo.
        """
        self._experiment_identity = identity

    def generate(
        self,
        *,
        generated_at_sim: float,
        event_type: str,
        payload: dict[str, Any],
        priority: TelemetryPriority,
    ) -> TelemetryEvent:
        """Registra un evento en el instante de simulación recibido."""
        return self.generate_many(
            1,
            generated_at_sim=generated_at_sim,
            event_type=event_type,
            payload_for_sequence=lambda _sequence: payload,
            priority=priority,
        )[0]

    def generate_many(
        self,
        count: int,
        *,
        generated_at_sim: float,
        event_type: str,
        payload_for_sequence: Callable[[int], dict[str, Any]],
        priority: TelemetryPriority,
    ) -> list[TelemetryEvent]:
        """Registra ``count`` eventos como un solo alta de esta fuente.
        Todos comparten ``generated_at_sim``, ``event_type``, ``priority``
        y ``schema_version``. La carga de cada uno sale de
        ``payload_for_sequence`` con la secuencia que asigna el repositorio.
        Si el alta falla, no queda ninguno de este grupo.
        """
        def factory(sequence_number: int) -> TelemetryEvent:
            kwargs: dict[str, Any] = {
                "source_id": self._source_id,
                "sequence_number": sequence_number,
                "generated_at_sim": generated_at_sim,
                "event_type": event_type,
                "payload": payload_for_sequence(sequence_number),
                "priority": priority,
                "schema_version": self._schema_version,
            }
            if self._experiment_identity is not None:
                kwargs["event_id"] = make_telemetry_event_id(
                    experiment_identity=self._experiment_identity,
                    source_id=self._source_id,
                    sequence_number=sequence_number,
                    generated_at_sim=generated_at_sim,
                    event_type=event_type,
                )
            return TelemetryEvent(**kwargs)
        return self._repository.commit_new_events(self._source_id, count, factory)

    def persist(self, event: TelemetryEvent) -> None:
        """Guarda un evento que ya trae secuencia, si es de esta fuente."""
        if event.source_id != self._source_id:
            raise ValueError("el source_id del evento no coincide con este nodo de Marte")
        self._repository.persist(event)

    def generated_count(self) -> int:
        """Eventos registrados de esta fuente."""
        return self._repository.generated_count(self._source_id)

    def max_generated_at_sim(self) -> float | None:
        """Mayor ``generated_at_sim`` de esta fuente, o ``None`` si no hay."""
        return self._repository.max_generated_at_sim(self._source_id)

    def max_confirmed_at_sim(self) -> float | None:
        """Mayor instante de confirmación de esta fuente, o ``None`` si no hubo."""
        return self._repository.max_confirmed_at_sim(self._source_id)

    def pending_count(self) -> int:
        """Eventos de esta fuente cuyo outbox todavía no está confirmado."""
        return self._repository.pending_count(self._source_id)

    def confirmed_count(self) -> int:
        """Eventos confirmados de esta fuente."""
        return self._repository.confirmed_count(self._source_id)

    def local_persisted_count(self) -> int:
        """Eventos de esta fuente ya persistidos en el alta local."""
        return self._repository.local_persisted_count(self._source_id)

    def in_flight_count(self) -> int:
        """Eventos de esta fuente con intento vigente en ``IN_FLIGHT``."""
        return self._repository.in_flight_count(self._source_id)

    def latest_sequence_number(self) -> int | None:
        """Última secuencia registrada de esta fuente, o ``None`` si no hay."""
        return self._repository.latest_sequence_number(self._source_id)

    def pending_events(self) -> list[TelemetryEvent]:
        """Pendientes de esta fuente, en orden de registro.

        Incluye los que tienen un intento activo. Excluye los confirmados.
        No reordena por ``sequence_number``.
        """
        return self._repository.pending_events(self._source_id)

    def eligible_sync_events(self) -> list[TelemetryEvent]:
        """Pendientes de esta fuente que no tienen un intento activo.

        El orden es el de registro. Un evento confirmado no aparece.
        """
        return self._repository.retry_eligible_events(self._source_id)

    def retry_eligible_events(self) -> list[TelemetryEvent]:
        """Mismos eventos que ``eligible_sync_events``."""
        return self.eligible_sync_events()

    def events_for_source(self) -> list[TelemetryEvent]:
        """Eventos de esta fuente según el índice de secuencia, confirmados incluidos."""
        return self._repository.events_for_source(self._source_id)

    def events_for_sequence_ranges(
        self, ranges: Sequence[MissingSequenceRange]
    ) -> list[TelemetryEvent]:
        """Eventos originales de esta fuente en los rangos pedidos."""
        return self._repository.events_for_sequence_ranges(self._source_id, ranges)

    def get_event(self, event_id: UUID) -> TelemetryEvent | None:
        """Evento registrado, o ``None`` si el id no existe."""
        return self._repository.get_event(event_id)

    def sync_state(self, event_id: UUID) -> TelemetrySyncState | None:
        """Outbox vigente del evento, o ``None`` si el id no existe."""
        return self._repository.sync_state(event_id)

    def transition_history(self, event_id: UUID) -> list[TelemetryEventState]:
        """Historial del evento, del más antiguo al más reciente."""
        return self._repository.transition_history(event_id)

    def status(self) -> MarsNodeStatus:
        """Contadores resumidos de esta fuente."""
        return self._repository.status(self._source_id)

    def application_status(self) -> MarsApplicationStatus:
        """Instantánea de contadores de esta fuente."""
        return self._repository.application_status(self._source_id)

    def apply_application_ack(self, ack: ApplicationAck, received_at_sim: float) -> None:
        """Confirma los eventos que el ACK durable ya aceptó en Tierra.

        ``received_at_sim`` es el instante de llegada del ACK. El orden es
        el de ``confirmed_event_ids``: primero aceptados, después duplicados.
        Un rechazado no entra. No decodifica una SyncUnit, no cambia el
        intento y no emite traza.
        """
        if ack.status is not ApplicationAckStatus.ACCEPTED:
            raise ValueError("el ACK no representa la aceptación durable en Tierra")
        self._repository.confirm_events(ack.confirmed_event_ids(), at_sim=received_at_sim)

    def record_observability_state(
        self,
        event_id: UUID,
        state: TelemetryEventState,
        at_sim: float,
        attempt_id: str | None = None,
    ) -> None:
        """Anota observabilidad en el historial. El outbox sigue en ``PENDING``."""
        self._repository.record_observability_state(
            event_id, state, at_sim, attempt_id=attempt_id
        )

    def save_sync_attempt(
        self, attempt: SyncAttempt, sync_unit_id: str | None = None
    ) -> None:
        """Guarda un intento que quien llama ya construyó."""
        self._repository.save_sync_attempt(attempt, sync_unit_id)

    def get_sync_attempt(self, attempt_id: str) -> SyncAttempt | None:
        """Intento guardado, o ``None`` si no existe."""
        return self._repository.get_sync_attempt(attempt_id)

    def sync_unit_id_for_attempt(self, attempt_id: str) -> str | None:
        """Identificador de unidad asociado al intento, si fue informado."""
        return self._repository.sync_unit_id_for_attempt(attempt_id)

    def sync_attempts_for_event(self, event_id: UUID) -> list[SyncAttempt]:
        """Intentos del evento, de menor a mayor ``attempt_number``."""
        return self._repository.sync_attempts_for_event(event_id)

    def latest_sync_attempt_for_event(self, event_id: UUID) -> SyncAttempt | None:
        """Intento de mayor ``attempt_number`` del evento, o ``None``."""
        return self._repository.latest_sync_attempt_for_event(event_id)

    def latest_sync_attempt_for_group(self, sync_group_id: str) -> SyncAttempt | None:
        """Intento de mayor ``attempt_number`` del grupo, o ``None``."""
        return self._repository.latest_sync_attempt_for_group(sync_group_id)

    def active_sync_attempt_for_event(self, event_id: UUID) -> SyncAttempt | None:
        """Intento activo del evento, o ``None`` si no tiene uno."""
        return self._repository.active_sync_attempt_for_event(event_id)

    def active_sync_count(self) -> int:
        """Intentos activos distintos entre los pendientes de esta fuente."""
        return self._repository.active_sync_count(self._source_id)

    def retry_attempts_total(self) -> int:
        """Intentos con ``attempt_number`` mayor que 1 guardados para esta fuente."""
        return self._repository.retry_attempts_total(self._source_id)
