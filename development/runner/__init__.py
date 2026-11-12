"""Ejecución headless de una corrida, aparte de la presentación por consola."""

from development.runner.config import RunConfig
from development.runner.demo import DEMO_NOTICE, demo_contact_plan, demo_run_config
from development.runner.execute import execute_run
from development.runner.result import RunResult, TraceLine

__all__ = [
    "DEMO_NOTICE",
    "RunConfig",
    "RunResult",
    "TraceLine",
    "demo_contact_plan",
    "demo_run_config",
    "execute_run",
]
