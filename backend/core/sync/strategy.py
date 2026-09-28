"""Agrupamiento puro de eventos de telemetría ya elegibles.

Una estrategia responde una sola pregunta: dados estos eventos, cómo se
parten en planes de sincronización. Cada plan es el grupo ordenado de
eventos de una SyncUnit futura.

No decide qué eventos siguen pendientes, no crea un SyncAttempt, no
reintenta, no abre contactos y no consulta la capacidad del enlace. El
orden recibido se conserva. Un ``event_id`` repetido se conserva solo en
su primera aparición.

``created_at_sim``, ``attempt_id`` y ``submission_order`` no se asignan
aquí. El codec construye la SyncUnit cuando el llamador ya tiene el intento.
"""
from __future__ import annotations
from collections.abc import Sequence
from typing import Protocol, Self
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from core.domain.event import TelemetryEvent

STRATEGY_TYPE_INDIVIDUAL = "individual"
STRATEGY_TYPE_FIXED_BATCH = "fixed_batch"
MIN_BATCH_SIZE_EVENTS = 2
MAX_BATCH_SIZE_EVENTS = 10_000

class UnknownSyncStrategyError(ValueError):
    """El nombre no corresponde a una estrategia implementada."""

class InvalidSyncStrategyConfigError(ValueError):
    """La estrategia existe, pero su configuración propia no es válida."""

class SyncPlanningContext(BaseModel):
    """Contexto disponible al planificar. Esta política no lo usa para agrupar.
    ``simulation_time`` está en segundos de simulación, es mayor o igual que
    0 y no se lee de un reloj global. ``source_id`` es el origen informado
    por el llamador. Ninguno de los dos cambia qué eventos entran en cada
    plan ni en qué orden.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    simulation_time: float = Field(ge=0)
    source_id: str

class SyncPlan(BaseModel):
    """Agrupación, independiente del transporte, de eventos para una unidad.
    No se persiste y no es un SyncAttempt. ``event_ids`` y ``events``
    describen la misma secuencia, en el mismo orden. La secuencia no está
    vacía. ``strategy_type`` es el valor serializado de la política que
    formó el plan.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_ids: tuple[UUID, ...]
    events: tuple[TelemetryEvent, ...]
    strategy_type: str

    @model_validator(mode="after")
    def event_ids_must_match_events(self) -> Self:
        if not self.events:
            raise ValueError("events no debe estar vacío")
        ids = tuple(event.event_id for event in self.events)
        if ids != self.event_ids:
            raise ValueError("event_ids debe coincidir con events en orden")
        return self

class SyncStrategy(Protocol):
    """Política que agrupa eventos ya elegibles en SyncPlans.
    No accede a transporte, a persistencia ni a la hora de pared. No decide
    reintentos y no modifica los eventos.
    """
    @property
    def strategy_type(self) -> str: ...

    @property
    def batch_size_events(self) -> int | None: ...

    def plan(
        self,
        eligible_events: Sequence[TelemetryEvent],
        context: SyncPlanningContext,
    ) -> Sequence[SyncPlan]: ...

def create_sync_strategy(
    strategy_type: str = STRATEGY_TYPE_INDIVIDUAL,
    batch_size_events: int | None = None,
) -> SyncStrategy:
    """Resuelve la estrategia a partir de su nombre serializado.
    Individual ignora ``batch_size_events`` si viene informado. Fixed Batch
    lo exige en el intervalo ``[2, 10000]``.
    """
    from core.sync.fixed_batch import FixedBatchSyncStrategy
    from core.sync.individual import IndividualSyncStrategy

    normalized = strategy_type.strip()
    if normalized == STRATEGY_TYPE_INDIVIDUAL:
        return IndividualSyncStrategy()
    if normalized == STRATEGY_TYPE_FIXED_BATCH:
        if batch_size_events is None:
            raise InvalidSyncStrategyConfigError("fixed_batch requiere batch_size_events")
        if (
            batch_size_events < MIN_BATCH_SIZE_EVENTS
            or batch_size_events > MAX_BATCH_SIZE_EVENTS
        ):
            raise InvalidSyncStrategyConfigError(
                "batch_size_events de fixed_batch debe estar entre "
                f"{MIN_BATCH_SIZE_EVENTS} y {MAX_BATCH_SIZE_EVENTS}, inclusive"
            )
        return FixedBatchSyncStrategy(batch_size_events)
    raise UnknownSyncStrategyError(
        f"estrategia de sincronización desconocida '{strategy_type}'. "
        f"Admitidas: {STRATEGY_TYPE_INDIVIDUAL}, {STRATEGY_TYPE_FIXED_BATCH}"
    )
