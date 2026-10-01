"""Métricas científicas de una corrida.

Las fórmulas viven en este paquete. No dependen de la consola ni del
motor de simulación. Una serie temporal de intervalo no forma parte de
la respuesta de E1, E2 o E3 y no se aproxima aquí.
"""

from core.metrics.delivery import FreshnessDistribution, FreshnessSample
from core.metrics.recovery import RecoveryEpisodeResult, RecoveryRunSummary
from core.metrics.run import RunMetricsInput, ScientificRunMetrics, compute_run_metrics

__all__ = [
    "FreshnessDistribution",
    "FreshnessSample",
    "RecoveryEpisodeResult",
    "RecoveryRunSummary",
    "RunMetricsInput",
    "ScientificRunMetrics",
    "compute_run_metrics",
]
