"""Especificación inmutable de una corrida científica.

Agrupa escenario, carga y la configuración de ejecución. No guarda
resultados ni describe una campaña.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.domain.identity import (
    make_dataset_identity,
    make_execution_identity,
    make_experiment_identity,
)
from core.domain.retry import RetryPolicy
from core.failure.plan import FailurePlan
from core.recovery.policy import RecoveryPolicy
from core.stopping.policy import StopPolicy
from core.sync.strategy import STRATEGY_TYPE_INDIVIDUAL, create_sync_strategy
from core.trace.level import TraceLevel

from experiments.scenario import Scenario
from experiments.workload import Workload


@dataclass(frozen=True, slots=True)
class ScientificRunSpec:
    """Una corrida. La misma especificación produce la misma identidad.

    ``dataset_identity`` y ``experiment_identity`` dependen del escenario
    y de la semilla. Entran en ``event_id``. La estrategia, la recuperación
    y los fallos no entran ahí.

    ``execution_identity`` agrega la estrategia y el tamaño de lote.
    ``seed`` es un entero de la especificación. No se sortea.
    """

    scenario: Scenario
    workload: Workload
    seed: int = 1
    strategy_type: str = "individual"
    batch_size_events: int | None = None
    recovery_policy: RecoveryPolicy = RecoveryPolicy.NONE
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    failure_plan: FailurePlan = field(default_factory=FailurePlan)
    stop_policy: StopPolicy = StopPolicy.PROFILE_HORIZON_SETTLED
    trace_level: TraceLevel = TraceLevel.SCIENTIFIC
    gap_request_timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed debe ser un entero")
        if not isinstance(self.recovery_policy, RecoveryPolicy):
            raise ValueError("recovery_policy debe ser una RecoveryPolicy")
        if not isinstance(self.stop_policy, StopPolicy):
            raise ValueError("stop_policy debe ser una StopPolicy")
        if not isinstance(self.trace_level, TraceLevel):
            raise ValueError("trace_level debe ser un TraceLevel")
        if not isinstance(self.retry_policy, RetryPolicy):
            raise ValueError("retry_policy debe ser una RetryPolicy")
        if not isinstance(self.failure_plan, FailurePlan):
            raise ValueError("failure_plan debe ser un FailurePlan")
        strategy_type = self.strategy_type.strip()
        object.__setattr__(self, "strategy_type", strategy_type)
        if strategy_type == STRATEGY_TYPE_INDIVIDUAL and self.batch_size_events is not None:
            raise ValueError("individual no admite batch_size_events")
        create_sync_strategy(strategy_type, self.batch_size_events)
        if self.recovery_policy.receiver_driven_enabled:
            timeout = self.gap_request_timeout_seconds
            if timeout is None or timeout <= 0:
                raise ValueError("receiver-driven requiere gap_request_timeout_seconds > 0")
        elif self.gap_request_timeout_seconds is not None:
            raise ValueError(
                "gap_request_timeout_seconds pertenece solo a receiver-driven"
            )
        horizon = self.scenario.horizon_seconds
        if self.stop_policy is not StopPolicy.UNTIL_IDLE and horizon is None:
            raise ValueError(
                f"{self.stop_policy.value} requiere el horizonte del escenario"
            )

    @property
    def dataset_identity(self) -> str:
        """Identidad del dataset: escenario y semilla."""
        return make_dataset_identity(self.scenario.scenario_id, self.seed)

    @property
    def experiment_identity(self) -> str:
        """Alias de la identidad de dataset. Entra en ``event_id``."""
        return make_experiment_identity(self.scenario.scenario_id, self.seed)

    @property
    def execution_identity(self) -> str:
        """Identidad de la ejecución: dataset más estrategia y lote."""
        return make_execution_identity(
            self.scenario.scenario_id,
            self.seed,
            strategy_type=self.strategy_type,
            batch_size_events=self.batch_size_events,
        )

    @property
    def horizon_seconds(self) -> float | None:
        """Horizonte del escenario. La política de parada dice cómo se aplica."""
        return self.scenario.horizon_seconds
