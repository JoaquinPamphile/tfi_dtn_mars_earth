"""Agenda la generación del workload en el motor ya armado.

Programa ``TELEMETRY_GENERATED`` de a uno. El scheduler del motor ordena
esas acciones con el mismo desempate que el resto de la corrida: a igual
tiempo, la que se programó antes. Marte persiste y asigna la secuencia.
"""

from __future__ import annotations

from core.domain.priority import TelemetryPriority
from core.runtime.stack import SimulationStack
from core.simulation.scheduler import ScheduledAction
from core.trace.types import SimulationEventType

from experiments.spec import ScientificRunSpec
from experiments.workload import Workload


class WorkloadGeneration:
    """Driver de un workload sobre un ``SimulationStack`` ya construido."""

    def __init__(self, stack: SimulationStack, spec: ScientificRunSpec) -> None:
        self._stack = stack
        self._workload: Workload = spec.workload
        self._dataset_identity = spec.dataset_identity
        self._profile = spec.workload.generation_profile(
            dataset_identity=spec.dataset_identity
        )
        self._next_n = 0
        self._emitted = 0

    def install(self) -> None:
        """Registra el handler y programa el primer evento del perfil."""
        engine = self._stack.engine
        engine.register_handler(
            SimulationEventType.TELEMETRY_GENERATED.value,
            self._on_telemetry_generated,
        )
        self._schedule_next()

    def _schedule_next(self) -> None:
        profile = self._profile
        if profile is None or not profile.enabled:
            return
        engine = self._stack.engine
        n = self._next_n
        now = engine.now
        while True:
            if profile.max_events is not None and self._emitted >= profile.max_events:
                self._profile = None
                return
            event_time = profile.event_time(n)
            if not profile.allows_event_time(event_time):
                self._profile = None
                return
            if event_time < now:
                n += 1
                continue
            self._next_n = n
            engine.schedule(
                time=event_time,
                event_type=SimulationEventType.TELEMETRY_GENERATED.value,
                payload={
                    "profile_id": profile.profile_id,
                    "generation_index": n,
                    "event_type": profile.event_type,
                    "priority": profile.priority.value,
                    "rate_events_per_second": profile.rate_events_per_second,
                },
                entity_id=profile.profile_id,
            )
            return

    def _on_telemetry_generated(self, action: ScheduledAction) -> None:
        profile = self._profile
        if profile is None or action.payload.get("profile_id") != profile.profile_id:
            return
        generated_at = float(action.time)
        workload = self._workload
        identity = self._dataset_identity
        mars = self._stack.mars
        schema_version = mars.schema_version

        def payload_for_sequence(sequence_number: int) -> dict[str, object]:
            return workload.payload_for(
                dataset_identity=identity,
                sequence_number=sequence_number,
                generated_at_sim=generated_at,
                schema_version=schema_version,
            )

        mars.generate_many(
            1,
            generated_at_sim=generated_at,
            event_type=profile.event_type,
            payload_for_sequence=payload_for_sequence,
            priority=TelemetryPriority(profile.priority),
        )
        self._emitted += 1
        self._next_n = int(action.payload["generation_index"]) + 1
        self._stack.session.submit_pending()
        self._schedule_next()


def install_workload_generation(stack: SimulationStack, spec: ScientificRunSpec) -> None:
    """Engancha el workload al motor. Los contactos ya deben estar programados."""
    WorkloadGeneration(stack, spec).install()
