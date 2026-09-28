from enum import StrEnum
from core.trace.types import SimulationEventType

class TraceLevel(StrEnum):
    """Verbosidad de la traza. No cambia los resultados científicos.
    ``FULL``
        Conserva cualquier tipo de evento.
    ``SCIENTIFIC``
        Conserva el subconjunto científico.
    ``SUMMARY``
        Conserva un subconjunto más corto.
    El valor serializado de cada miembro es su nombre. Quién decide guardar
    o descartar un evento es quien registra. El almacén en memoria guarda lo
    que recibe.
    """
    FULL = "FULL"
    SCIENTIFIC = "SCIENTIFIC"
    SUMMARY = "SUMMARY"

# Tipos que conserva el nivel SCIENTIFIC.
_SCIENTIFIC_TYPES = frozenset(
    {
        SimulationEventType.TELEMETRY_BURST_GENERATED.value,
        SimulationEventType.CONTACT_OPEN.value,
        SimulationEventType.CONTACT_CLOSE.value,
        SimulationEventType.FAILURE_INJECTED.value,
        SimulationEventType.CONTACT_FORCED_CLOSE.value,
        SimulationEventType.TRANSMISSION_INTERRUPTED.value,
        SimulationEventType.EARTH_EVENT_PERSISTED.value,
        SimulationEventType.EARTH_DUPLICATE_RECEIVED.value,
        SimulationEventType.ACK_DROPPED.value,
        SimulationEventType.SILENT_FORWARD_DELIVERY_DROPPED.value,
        SimulationEventType.MARS_EVENT_CONFIRMED.value,
        SimulationEventType.CONFIRMED.value,
        SimulationEventType.ACK_TIMEOUT.value,
        SimulationEventType.RETRY_SCHEDULED.value,
        SimulationEventType.RETRY_SUBMITTED.value,
        SimulationEventType.GAP_OBSERVED.value,
        SimulationEventType.GAP_REQUEST_CREATED.value,
        SimulationEventType.GAP_REQUEST_ATTEMPT_SUBMITTED.value,
        SimulationEventType.GAP_REQUEST_RECEIVED_MARS.value,
        SimulationEventType.GAP_REPAIR_SUBMITTED.value,
        SimulationEventType.GAP_CLOSED.value,
        SimulationEventType.SCENARIO_HORIZON_REACHED.value,
    }
)

# Tipos que conserva el nivel SUMMARY.
_SUMMARY_TYPES = frozenset(
    {
        SimulationEventType.TELEMETRY_BURST_GENERATED.value,
        SimulationEventType.CONTACT_OPEN.value,
        SimulationEventType.CONTACT_CLOSE.value,
        SimulationEventType.FAILURE_INJECTED.value,
        SimulationEventType.CONTACT_FORCED_CLOSE.value,
        SimulationEventType.SILENT_FORWARD_DELIVERY_DROPPED.value,
        SimulationEventType.SCENARIO_HORIZON_REACHED.value,
    }
)

def records_event_type(level: TraceLevel, event_type: str) -> bool:
    """Indica si ese nivel de traza conserva el tipo de evento.
    ``FULL`` conserva todos. ``SCIENTIFIC`` y ``SUMMARY`` conservan solo su
    conjunto. La comparación del nivel es por identidad del enum.
    """
    if level is TraceLevel.FULL:
        return True
    if level is TraceLevel.SCIENTIFIC:
        return event_type in _SCIENTIFIC_TYPES
    return event_type in _SUMMARY_TYPES
