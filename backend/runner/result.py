"""Resumen operativo de una corrida ya terminada.

Las métricas científicas viajan en ``scientific_metrics``. Este módulo
no las calcula.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.metrics.run import ScientificRunMetrics


@dataclass(frozen=True, slots=True)
class TraceLine:
    """Una entrada de traza reducida a lo que la consola necesita mostrar.

    No incluye el payload.
    """

    simulation_time: float
    sequence_index: int
    event_type: str
    entity_id: str | None


@dataclass(frozen=True, slots=True)
class RunResult:
    """Estado final consultable después de ejecutar el motor.

    ``attempts_total`` cuenta ``attempt_id`` distintos leídos con
    ``MarsNode.sync_attempts_for_event``. ``retry_count`` es
    ``MarsNode.retry_attempts_total``. ``failures_injected`` cuenta
    pérdidas silenciosas ya registradas en el runtime. Los huecos
    observados, los cerrados y los pedidos salen de la traza pública.
    El resto sale de las consultas públicas del motor, de Marte y de Tierra.
    """

    simulation_time: float
    engine_status: str
    strategy_type: str
    batch_size_events: int | None
    events_generated: int
    events_persisted_earth: int
    events_confirmed_mars: int
    events_pending_mars: int
    attempts_total: int
    retry_count: int
    earth_gaps_count: int
    duplicates_received: int
    trace_entries: tuple[TraceLine, ...]
    recovery_mode: str = "none"
    failures_injected: int = 0
    gaps_observed: int = 0
    gaps_closed: int = 0
    gap_requests: int = 0
    scientific_metrics: ScientificRunMetrics | None = None
