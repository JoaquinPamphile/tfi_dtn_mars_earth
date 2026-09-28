from collections.abc import Sequence
from uuid import UUID
from core.domain.event import TelemetryEvent
from core.sync.strategy import (
    STRATEGY_TYPE_INDIVIDUAL,
    SyncPlan,
    SyncPlanningContext,
)

class IndividualSyncStrategy:
    """Un evento elegible produce un plan, y ese plan una SyncUnit.
    No es stop-and-wait. Varias unidades de un evento pueden quedar
    encoladas, en transmisión o a la espera de ACK al mismo tiempo.
    ``batch_size_events`` es ``None``. 
    """
    @property
    def strategy_type(self) -> str:
        return STRATEGY_TYPE_INDIVIDUAL

    @property
    def batch_size_events(self) -> int | None:
        return None

    def plan(
        self,
        eligible_events: Sequence[TelemetryEvent],
        context: SyncPlanningContext,
    ) -> tuple[SyncPlan, ...]:
        # El contexto no decide qué eventos entran ni en qué orden.
        del context
        plans: list[SyncPlan] = []
        seen: set[UUID] = set()
        for event in eligible_events:
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            plans.append(
                SyncPlan(
                    event_ids=(event.event_id,),
                    events=(event,),
                    strategy_type=STRATEGY_TYPE_INDIVIDUAL,
                )
            )
        return tuple(plans)
