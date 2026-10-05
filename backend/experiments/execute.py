"""Ejecuta una ``ScientificRunSpec`` con el stack que ya existe.

No abre un segundo motor. La generación entra por el scheduler y Marte
persiste cada evento.
"""

from __future__ import annotations

from copy import deepcopy

from core.domain.retry import RetryPolicy
from core.earth.node import EarthNode
from core.mars.node import MarsNode
from core.runtime.stack import SimulationStack
from core.state.earth import FastEarthStateRepository
from core.state.mars import FastMarsStateRepository

from experiments.generation import install_workload_generation
from experiments.result import GeneratedTelemetry, ScientificRunResult
from experiments.spec import ScientificRunSpec
from runner.scientific import collect_scientific_metrics


def execute_scientific_run(spec: ScientificRunSpec) -> ScientificRunResult:
    """Arma el stack, agenda el workload y corre hasta la política de parada."""
    mars = MarsNode(FastMarsStateRepository(), source_id=spec.workload.source_id)
    earth = EarthNode(FastEarthStateRepository())
    stack = SimulationStack.build(
        spec.scenario.contact_plan,
        strategy_type=spec.strategy_type,
        batch_size_events=spec.batch_size_events,
        experiment_identity=spec.dataset_identity,
        trace_level=spec.trace_level,
        mars=mars,
        earth=earth,
        retry_policy=RetryPolicy(
            ack_timeout_seconds=spec.retry_policy.ack_timeout_seconds
        ),
        gap_request_timeout_seconds=spec.gap_request_timeout_seconds,
        recovery_policy=spec.recovery_policy,
        failures=spec.failure_plan,
    )
    install_workload_generation(stack, spec)
    stack.run(spec.stop_policy, spec.horizon_seconds)
    metrics = collect_scientific_metrics(stack, spec.recovery_policy.value)
    events = tuple(
        GeneratedTelemetry(
            event_id=str(event.event_id),
            source_id=event.source_id,
            sequence_number=event.sequence_number,
            generated_at_sim=event.generated_at_sim,
            event_type=event.event_type,
            payload=deepcopy(event.payload),
            priority=event.priority.value,
            schema_version=event.schema_version,
        )
        for event in mars.events_for_source()
    )
    return ScientificRunResult(
        scenario_id=spec.scenario.scenario_id,
        workload_id=spec.workload.workload_id,
        seed=spec.seed,
        dataset_identity=spec.dataset_identity,
        experiment_identity=spec.experiment_identity,
        execution_identity=spec.execution_identity,
        strategy_type=stack.strategy.strategy_type,
        batch_size_events=stack.strategy.batch_size_events,
        stop_policy=spec.stop_policy.value,
        horizon_seconds=spec.horizon_seconds,
        recovery_policy=spec.recovery_policy.value,
        offered_load_fraction=spec.workload.offered_load_fraction,
        simulation_time=stack.engine.now,
        engine_status=stack.engine.status.value,
        events=events,
        events_persisted_earth=earth.status().persisted_unique,
        events_confirmed_mars=mars.confirmed_count(),
        metrics=metrics,
        trace_entry_count=len(stack.engine.trace),
    )
