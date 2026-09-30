"""Estado de aplicación en memoria para la ejecución científica."""

from core.state.earth import FastEarthStateRepository
from core.state.errors import DuplicateTelemetryEventError
from core.state.mars import FastMarsStateRepository
from core.state.ports import (
    EarthIngestResult,
    EarthPersistenceRecord,
    EarthStateRepository,
    MarsApplicationStatus,
    MarsNodeStatus,
    MarsStateRepository,
)

__all__ = [
    "DuplicateTelemetryEventError",
    "EarthIngestResult",
    "EarthPersistenceRecord",
    "EarthStateRepository",
    "FastEarthStateRepository",
    "FastMarsStateRepository",
    "MarsApplicationStatus",
    "MarsNodeStatus",
    "MarsStateRepository",
]
