"""Instantánea de contadores de la aplicación en Tierra."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class EarthNodeStatus:
    """Contadores resumidos de la ingesta durable.
    ``persisted_unique`` son eventos distintos. ``gaps_count`` suma los
    enteros faltantes de todas las fuentes. ``duplicates_received`` cuenta
    las repeticiones marcadas en la ingesta. ``duplicates_stored`` permanece
    en 0: la repetición no crea una fila nueva.
    """
    persisted_unique: int
    gaps_count: int
    duplicates_received: int
    duplicates_stored: int
