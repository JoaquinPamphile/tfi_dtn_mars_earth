"""Hechos de transporte ya ocurridos, conservados para las métricas.

No deciden si una unidad cabe ni cambian el enlace. Registran bytes de
aplicación que la serialización ya consumió. La propagación no suma bytes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HopTransmissionRecord:
    """Bytes de aplicación consumidos en un hop dirigido.

    Si la serialización terminó, ``bytes_transmitted`` es el
    ``payload_size_bytes`` completo y ``completed`` es verdadero.
    Si el contacto se cortó a la fuerza, ``bytes_transmitted`` es la
    porción ya serializada, ``interrupted`` es verdadero y ``completed``
    es falso. Una pérdida silenciosa posterior a la serialización queda
    como hop completado: la capacidad ya se usó.
    """

    transmission_id: str
    contact_id: str
    source_node: str
    destination_node: str
    bytes_transmitted: int
    payload_kind: str | None
    attempt_number: int
    interrupted: bool
    completed: bool
    event_ids: tuple[str, ...]
    gap_request_id: str | None
    end_time_sim: float


@dataclass(frozen=True, slots=True)
class ForcedContactCut:
    """Corte ya aplicado a una ventana.

    ``cut_at_sim`` reemplaza el fin planificado al medir la capacidad
    realmente disponible. ``triggered`` queda verdadero cuando el corte
    se aplicó.
    """

    contact_id: str
    cut_at_sim: float
    triggered: bool
