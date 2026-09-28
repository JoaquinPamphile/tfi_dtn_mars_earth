from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from core.domain.state import TelemetryEventState

class TelemetrySyncState(BaseModel):
    """Progreso mutable de sincronización, a nivel de aplicación, de un evento."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    event_id: UUID
    state: TelemetryEventState
    last_transition_at_sim: float = Field(ge=0)
    retry_count: int = Field(default=0, ge=0)
