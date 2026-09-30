"""Errores del estado de aplicación de Marte."""
from uuid import UUID

class DuplicateTelemetryEventError(Exception):
    """El ``event_id`` ya está registrado.
    El evento existente se conserva. No se reemplaza ni se fusiona.
    """
    def __init__(self, event_id: UUID) -> None:
        super().__init__(f"el evento de telemetría ya existe: {event_id}")
        self.event_id = event_id
