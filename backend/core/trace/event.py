from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SimulationTraceEntry:
    """Hecho ya ocurrido, en segundos lógicos de simulación.
    Los campos quedan fijos. ``details`` es el diccionario recibido: mutarlo
    se observa en el registro. Dos registros pueden compartir
    ``simulation_time``. ``sequence_index`` llega asignado por quien registra
    el hecho.
    """
    simulation_time: float
    sequence_index: int
    event_type: str
    entity_id: str | None
    details: dict[str, Any]
