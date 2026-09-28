"""Traza de simulación en memoria: registro, catálogo de tipos y consultas por posición."""

from core.trace.event import SimulationTraceEntry
from core.trace.level import TraceLevel, records_event_type
from core.trace.sink import MemoryTraceSink, TraceSink
from core.trace.types import SimulationEventType

__all__ = [
    "MemoryTraceSink",
    "SimulationEventType",
    "SimulationTraceEntry",
    "TraceLevel",
    "TraceSink",
    "records_event_type",
]
