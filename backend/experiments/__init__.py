"""Configuración y ejecución de una corrida científica."""

from experiments.controlled import controlled_local_run_spec
from experiments.execute import execute_scientific_run
from experiments.offered_load import (
    CANONICAL_OFFERED_LOAD_FRACTIONS,
    offered_load_event_count,
)
from experiments.result import ScientificRunResult
from experiments.scenario import Scenario
from experiments.spec import ScientificRunSpec
from experiments.workload import Workload

__all__ = [
    "CANONICAL_OFFERED_LOAD_FRACTIONS",
    "Scenario",
    "ScientificRunResult",
    "ScientificRunSpec",
    "Workload",
    "controlled_local_run_spec",
    "execute_scientific_run",
    "offered_load_event_count",
]
