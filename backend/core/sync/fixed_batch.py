from collections.abc import Sequence
from uuid import UUID

from core.domain.event import TelemetryEvent
from core.sync.strategy import (
    STRATEGY_TYPE_FIXED_BATCH,
    SyncPlan,
    SyncPlanningContext,
)

class FixedBatchSyncStrategy:
    """Agrupa eventos en planes de como máximo ``batch_size_events``.

    El tamaño es un máximo, no un mínimo. El último grupo puede tener menos
    eventos: 17 eventos con tamaño 50 producen un plan de 17. No espera a
    completar el grupo.

    El corte sigue la posición en la entrada ya deduplicada. No ordena por
    ``sequence_number``, por ``generated_at_sim`` ni por ``event_id``. No
    filtra por origen ni por prioridad. No usa la capacidad del enlace.

    La cohorte de un reintento no se decide aquí.
    """

    def __init__(self, batch_size_events: int) -> None:
        self._batch_size_events = batch_size_events

    @property
    def strategy_type(self) -> str:
        return STRATEGY_TYPE_FIXED_BATCH

    @property
    def batch_size_events(self) -> int | None:
        return self._batch_size_events

    def plan(
        self,
        eligible_events: Sequence[TelemetryEvent],
        context: SyncPlanningContext,
    ) -> tuple[SyncPlan, ...]:
        # El contexto no decide qué eventos entran ni en qué orden.
        del context
        ordered: list[TelemetryEvent] = []
        seen: set[UUID] = set()
        for event in eligible_events:
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            ordered.append(event)
        size = self._batch_size_events
        plans: list[SyncPlan] = []
        for index in range(0, len(ordered), size):
            chunk = tuple(ordered[index : index + size])
            plans.append(
                SyncPlan(
                    event_ids=tuple(event.event_id for event in chunk),
                    events=chunk,
                    strategy_type=STRATEGY_TYPE_FIXED_BATCH,
                )
            )
        return tuple(plans)
