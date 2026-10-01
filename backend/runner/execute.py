"""Ejecuta una corrida con el ``SimulationStack`` del núcleo.

No abre un segundo camino de simulación y no depende de la consola.
"""

from __future__ import annotations

from core.domain.retry import RetryPolicy
from core.earth.node import EarthNode
from core.mars.node import MarsNode
from core.runtime.stack import SimulationStack
from core.state.earth import FastEarthStateRepository
from core.state.mars import FastMarsStateRepository
from runner.config import RunConfig
from runner.result import RunResult, TraceLine


def execute_run(config: RunConfig) -> RunResult:
    """Construye el stack, genera la telemetría y corre el motor.

    Los repositorios son los rápidos en memoria. La identidad de dataset
    queda fijada en el nodo de Marte por ``SimulationStack.build``.
    """
    mars = MarsNode(FastMarsStateRepository(), source_id=config.source_id)
    earth = EarthNode(FastEarthStateRepository())
    stack = SimulationStack.build(
        config.contact_plan,
        strategy_type=config.strategy_type,
        batch_size_events=config.batch_size_events,
        experiment_identity=config.experiment_identity,
        mars=mars,
        earth=earth,
        retry_policy=RetryPolicy(ack_timeout_seconds=config.ack_timeout_seconds),
    )
    stack.generate_many(
        config.event_count,
        event_type=config.event_type,
        payload_for_sequence=lambda sequence: {"n": sequence},
        priority=config.priority,
        generated_at_sim=config.generated_at_sim,
    )
    stack.run(config.stop_policy, config.horizon_seconds)
    return _collect(stack)


def _collect(stack: SimulationStack) -> RunResult:
    earth_status = stack.earth.status()
    trace = tuple(
        TraceLine(
            simulation_time=entry.simulation_time,
            sequence_index=entry.sequence_index,
            event_type=entry.event_type,
            entity_id=entry.entity_id,
        )
        for entry in stack.engine.trace
    )
    return RunResult(
        simulation_time=stack.engine.now,
        engine_status=stack.engine.status.value,
        strategy_type=stack.strategy.strategy_type,
        batch_size_events=stack.strategy.batch_size_events,
        events_generated=stack.mars.generated_count(),
        events_persisted_earth=earth_status.persisted_unique,
        events_confirmed_mars=stack.mars.confirmed_count(),
        events_pending_mars=stack.mars.pending_count(),
        attempts_total=_attempts_total(stack.mars),
        retry_count=stack.mars.retry_attempts_total(),
        earth_gaps_count=earth_status.gaps_count,
        duplicates_received=earth_status.duplicates_received,
        trace_entries=trace,
    )


def _attempts_total(mars: MarsNode) -> int:
    """Intentos distintos visibles por la API pública de Marte."""
    attempt_ids: set[str] = set()
    for event in mars.events_for_source():
        for attempt in mars.sync_attempts_for_event(event.event_id):
            attempt_ids.add(attempt.attempt_id)
    return len(attempt_ids)
