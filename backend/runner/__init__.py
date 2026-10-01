"""Ejecución headless de una corrida, aparte de la presentación por consola."""

from runner.config import RunConfig
from runner.demo import DEMO_NOTICE, demo_contact_plan, demo_run_config
from runner.execute import execute_run
from runner.result import RunResult, TraceLine

__all__ = [
    "DEMO_NOTICE",
    "RunConfig",
    "RunResult",
    "TraceLine",
    "demo_contact_plan",
    "demo_run_config",
    "execute_run",
]
