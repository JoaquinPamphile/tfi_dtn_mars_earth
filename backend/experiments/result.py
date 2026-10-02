"""Resultado de una corrida científica ya terminada.

Las métricas son las que calcula el runner existente. Este objeto solo
las acompaña con la identidad y los eventos generados.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.metrics.run import ScientificRunMetrics


@dataclass(frozen=True, slots=True)
class GeneratedTelemetry:
    """Evento que Marte persistió durante la corrida."""

    event_id: str
    source_id: str
    sequence_number: int
    generated_at_sim: float
    event_type: str


@dataclass(frozen=True, slots=True)
class ScientificRunResult:
    """Salida de ``execute_scientific_run``. No agrega varias corridas."""

    scenario_id: str
    workload_id: str
    seed: int
    dataset_identity: str
    experiment_identity: str
    execution_identity: str
    strategy_type: str
    batch_size_events: int | None
    stop_policy: str
    horizon_seconds: float | None
    recovery_policy: str
    offered_load_fraction: float | None
    simulation_time: float
    engine_status: str
    events: tuple[GeneratedTelemetry, ...]
    events_persisted_earth: int
    events_confirmed_mars: int
    metrics: ScientificRunMetrics

    @property
    def events_generated(self) -> int:
        return len(self.events)

    @property
    def generation_timestamps(self) -> tuple[float, ...]:
        return tuple(event.generated_at_sim for event in self.events)
