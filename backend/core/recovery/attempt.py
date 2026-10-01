"""Estado de entrega de un GapRequest.
Es estado de aplicación del recovery receiver-driven. No es un
``SyncAttempt`` de telemetría: esos modelan la sincronización Marte → Tierra
de eventos.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from core.domain.gap import GapRequest, MissingSequenceRange

class GapRequestAttemptStatus(StrEnum):
    """Ciclo del intento de transporte vigente de un GapRequest lógico."""
    PENDING = "PENDING"
    IN_FLIGHT = "IN_FLIGHT"
    WAITING_FOR_REPAIR = "WAITING_FOR_REPAIR"
    SATISFIED = "SATISFIED"

@dataclass
class GapRequestAttemptState:
    """Un GapRequest lógico y el intento de transporte que está en curso.
    ``request`` conserva la identidad lógica original: ``request_id``,
    rangos originales y ``created_at_sim``. ``current_missing_ranges`` es
    la intersección que todavía falta según los huecos de Tierra.
    ``attempt_number`` cuenta entregas de este pedido, no intentos de
    telemetría.
    """
    request: GapRequest
    current_missing_ranges: tuple[MissingSequenceRange, ...]
    attempt_number: int = 1
    last_submitted_at_sim: float | None = None
    first_departed_at_sim: float | None = None
    current_sync_unit_id: str | None = None
    status: GapRequestAttemptStatus = GapRequestAttemptStatus.PENDING
    transport_attempt_count: int = 0