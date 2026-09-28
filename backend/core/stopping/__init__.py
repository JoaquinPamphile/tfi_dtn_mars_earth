"""Política de parada de una corrida científica. La evaluación queda para el motor."""

from core.stopping.policy import StopPolicy, resolve_stop_policy

__all__ = [
    "StopPolicy",
    "resolve_stop_policy",
]
