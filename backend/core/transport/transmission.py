"""Intento de serialización en un hop. No es un SyncAttempt de aplicación."""
from dataclasses import dataclass
from core.sync.unit import SyncUnit

@dataclass
class TransmissionAttempt:
    """Una serialización en curso, desde el inicio hasta el fin previsto.
    ``scheduled_complete_time`` es el fin de la serialización, sin sumar
    ``propagation_delay_s``. ``valid`` pasa a falso si el contacto se cierra
    de forma forzada mientras la unidad todavía ocupa el enlace. La unidad
    se conserva completa: este intento no guarda un payload residual.
    """
    transmission_id: str
    unit: SyncUnit
    contact_id: str
    start_time_sim: float
    scheduled_complete_time: float
    payload_size_bytes: int
    data_rate_bps: int
    valid: bool = True
