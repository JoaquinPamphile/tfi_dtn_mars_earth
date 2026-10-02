"""Escenario y corrida controlados, pequeños, para una sola ejecución.

Los contactos son explícitos. No provienen de un plan de misión y no
constituyen una campaña.
"""

from __future__ import annotations

from core.stopping.policy import StopPolicy
from core.sync.strategy import STRATEGY_TYPE_INDIVIDUAL
from core.trace.level import TraceLevel

from experiments.scenario import Scenario, directed_round_trip
from experiments.spec import ScientificRunSpec
from experiments.workload import (
    CONTROLLED_COMMON_CANONICAL_INDIVIDUAL_BYTES,
    CONTROLLED_COMMON_EVENT_TYPE,
    CONTROLLED_COMMON_FLOW,
    Workload,
)

CONTROLLED_LOCAL_SCENARIO_ID = "controlled-local-v1"
CONTROLLED_LOCAL_WORKLOAD_ID = "controlled-local-v1"
CONTROLLED_LOCAL_SEED = 1
CONTROLLED_LOCAL_HORIZON_SECONDS = 60.0
CONTROLLED_LOCAL_CONTACT_END_SECONDS = 60.0
CONTROLLED_LOCAL_DATA_RATE_BPS = 8_000_000
CONTROLLED_LOCAL_PROPAGATION_DELAY_S = 1.0
CONTROLLED_LOCAL_RATE = 1.0
CONTROLLED_LOCAL_DURATION_SECONDS = 4.0


def controlled_local_scenario() -> Scenario:
    """Round trip corto con horizonte de perfil de 60 s."""
    return Scenario(
        scenario_id=CONTROLLED_LOCAL_SCENARIO_ID,
        description="Escenario controlado local de una corrida.",
        contacts=directed_round_trip(
            prefix=CONTROLLED_LOCAL_SCENARIO_ID,
            start_time_sim=0.0,
            end_time_sim=CONTROLLED_LOCAL_CONTACT_END_SECONDS,
            data_rate_bps=CONTROLLED_LOCAL_DATA_RATE_BPS,
            propagation_delay_s=CONTROLLED_LOCAL_PROPAGATION_DELAY_S,
        ),
        horizon_seconds=CONTROLLED_LOCAL_HORIZON_SECONDS,
    )


def controlled_local_workload() -> Workload:
    """Cuatro eventos, uno por segundo, con SyncUnit Individual de 4096 B."""
    return Workload(
        workload_id=CONTROLLED_LOCAL_WORKLOAD_ID,
        event_type=CONTROLLED_COMMON_EVENT_TYPE,
        flow=CONTROLLED_COMMON_FLOW,
        rate_events_per_second=CONTROLLED_LOCAL_RATE,
        start_time_sim=0.0,
        duration_seconds=CONTROLLED_LOCAL_DURATION_SECONDS,
        canonical_individual_syncunit_bytes=CONTROLLED_COMMON_CANONICAL_INDIVIDUAL_BYTES,
    )


def controlled_local_run_spec() -> ScientificRunSpec:
    """Corrida Individual que cabe en el horizonte controlado.

    La parada es ``PROFILE_HORIZON_SETTLED``: procesa hasta el horizonte
    del escenario y después solo el trabajo en vuelo ya causado.
    """
    return ScientificRunSpec(
        scenario=controlled_local_scenario(),
        workload=controlled_local_workload(),
        seed=CONTROLLED_LOCAL_SEED,
        strategy_type=STRATEGY_TYPE_INDIVIDUAL,
        stop_policy=StopPolicy.PROFILE_HORIZON_SETTLED,
        trace_level=TraceLevel.SUMMARY,
    )
