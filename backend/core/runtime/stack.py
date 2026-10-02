"""Composición headless de una corrida Marte → relé → Tierra y su ACK de vuelta.

Junta los componentes que ya existen. No reemplaza al motor, al
transporte, a los nodos ni a la estrategia.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.contact.plan import ContactPlan
from core.domain.event import TelemetryEvent
from core.domain.priority import TelemetryPriority
from core.domain.retry import RetryPolicy
from core.failure.plan import FailurePlan
from core.failure.runtime import FailureRuntime
from core.earth.node import EarthNode
from core.mars.node import MarsNode
from core.recovery.controller import ReceiverDrivenRecoveryController
from core.recovery.policy import RecoveryPolicy
from core.relay.node import RelayNode
from core.runtime.contacts import schedule_contact_plan
from core.runtime.session import TelemetrySyncSession
from core.simulation.engine import SimulationEngine
from core.state.earth import FastEarthStateRepository
from core.state.mars import FastMarsStateRepository
from core.stopping.policy import StopPolicy
from core.sync.strategy import (
    STRATEGY_TYPE_INDIVIDUAL,
    SyncStrategy,
    create_sync_strategy,
)
from core.trace.level import TraceLevel
from core.transport.emulated import EmulatedTransport


@dataclass
class SimulationStack:
    """Corrida cableada, lista para generar telemetría y ejecutar el motor.

    El resultado se consulta en los componentes: eventos en ``mars``,
    persistencia en ``earth``, custodia en ``relay``, traza y estado en
    ``engine``. No arma un informe aparte.
    """

    engine: SimulationEngine
    contact_plan: ContactPlan
    transport: EmulatedTransport
    relay: RelayNode
    mars: MarsNode
    earth: EarthNode
    strategy: SyncStrategy
    session: TelemetrySyncSession
    failures: FailureRuntime
    recovery: ReceiverDrivenRecoveryController | None = None

    @classmethod
    def build(
        cls,
        contact_plan: ContactPlan,
        *,
        strategy_type: str = STRATEGY_TYPE_INDIVIDUAL,
        batch_size_events: int | None = None,
        strategy: SyncStrategy | None = None,
        experiment_identity: str | None = None,
        trace_level: TraceLevel = TraceLevel.FULL,
        mars: MarsNode | None = None,
        earth: EarthNode | None = None,
        retry_policy: RetryPolicy | None = None,
        gap_request_timeout_seconds: float | None = None,
        recovery_policy: RecoveryPolicy = RecoveryPolicy.NONE,
        failures: FailurePlan | FailureRuntime | None = None,
    ) -> SimulationStack:
        """Arma el stack y programa el plan de contactos recibido.

        ``experiment_identity`` fija los ``event_id`` de la telemetría que
        genere este nodo de Marte. ``None`` deja que cada alta reciba un
        identificador nuevo. La estrategia, si no viene armada, sale de
        ``strategy_type`` y ``batch_size_events``. ``retry_policy`` ausente
        usa el timeout de ACK por defecto. Ese timeout solo se programa si
        ``recovery_policy`` enciende sender-driven.

        ``recovery_policy`` decide los mecanismos. ``NONE`` no programa
        timeout de ACK ni crea el controlador de huecos.
        ``SENDER_DRIVEN`` programa el timeout de ACK y no crea GapRequest.
        ``RECEIVER_DRIVEN`` crea el controlador y no programa timeout de
        ACK. En ese modo ``gap_request_timeout_seconds`` es obligatorio:
        es el timeout del GapRequest, medido desde que la unidad sale de
        Tierra. Un valor ausente no apaga el mecanismo; es un error.

        ``failures`` ausente deja un runtime vacío: el round trip no cambia.
        Un ``FailurePlan`` se envuelve sin copiar sus definiciones a otro
        objeto mutable. Un ``FailureRuntime`` se usa tal cual.
        """
        resolved = (
            strategy
            if strategy is not None
            else create_sync_strategy(strategy_type, batch_size_events)
        )
        engine = SimulationEngine(trace_level=trace_level)
        mars_node = mars if mars is not None else MarsNode(FastMarsStateRepository())
        earth_node = earth if earth is not None else EarthNode(FastEarthStateRepository())
        if experiment_identity is not None:
            mars_node.bind_experiment_identity(experiment_identity)
        transport = EmulatedTransport(engine, contact_plan)
        failure_runtime = _resolve_failures(failures)
        transport.bind_failures(failure_runtime)
        relay = RelayNode(engine, transport)
        recovery = None
        if recovery_policy.receiver_driven_enabled:
            if gap_request_timeout_seconds is None:
                raise ValueError(
                    "receiver-driven requiere gap_request_timeout_seconds"
                )
            recovery = ReceiverDrivenRecoveryController(
                earth=earth_node,
                mars=mars_node,
                transport=transport,
                engine=engine,
                gap_request_timeout_seconds=gap_request_timeout_seconds,
            )
        session = TelemetrySyncSession(
            mars_node,
            earth_node,
            engine,
            transport,
            contact_plan,
            resolved,
            retry_policy=retry_policy,
            recovery=recovery,
            sender_driven=recovery_policy.sender_driven_enabled,
        )
        schedule_contact_plan(engine, contact_plan)
        return cls(
            engine=engine,
            contact_plan=contact_plan,
            transport=transport,
            relay=relay,
            mars=mars_node,
            earth=earth_node,
            strategy=resolved,
            session=session,
            failures=failure_runtime,
            recovery=recovery,
        )

    def generate(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        priority: TelemetryPriority,
        generated_at_sim: float | None = None,
    ) -> TelemetryEvent:
        """Registra un evento y, si la ventana Marte → relé está vigente, lo planifica."""
        at_sim = self.engine.now if generated_at_sim is None else generated_at_sim
        event = self.mars.generate(
            generated_at_sim=at_sim,
            event_type=event_type,
            payload=payload,
            priority=priority,
        )
        self.session.submit_pending()
        return event

    def generate_many(
        self,
        count: int,
        *,
        event_type: str,
        payload_for_sequence: Callable[[int], dict[str, Any]],
        priority: TelemetryPriority,
        generated_at_sim: float | None = None,
    ) -> list[TelemetryEvent]:
        """Registra varios eventos de un alta y luego intenta planificarlos."""
        at_sim = self.engine.now if generated_at_sim is None else generated_at_sim
        events = self.mars.generate_many(
            count,
            generated_at_sim=at_sim,
            event_type=event_type,
            payload_for_sequence=payload_for_sequence,
            priority=priority,
        )
        self.session.submit_pending()
        return events

    def run(
        self,
        policy: StopPolicy | None = None,
        horizon_seconds: float | None = None,
    ) -> int:
        """Ejecuta el motor con la política recibida. Por defecto, hasta vaciar la cola."""
        return self.engine.run(policy, horizon_seconds)


def _resolve_failures(failures: FailurePlan | FailureRuntime | None) -> FailureRuntime:
    """Devuelve el runtime de la corrida sin mutar un plan congelado."""
    if isinstance(failures, FailureRuntime):
        return failures
    if isinstance(failures, FailurePlan):
        return FailureRuntime(failures)
    return FailureRuntime()
