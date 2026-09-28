from pydantic import BaseModel, ConfigDict, Field

# Valor por defecto solo de desarrollo de software. No es un RTT Marte–Tierra
# ni un parámetro científico del modelo de contactos.
DEFAULT_ACK_TIMEOUT_SECONDS = 600.0

class RetryPolicy(BaseModel):
    """Política de retry de aplicación para esta fase: solo un timeout fijo de ACK."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    ack_timeout_seconds: float = Field(gt=0, default=DEFAULT_ACK_TIMEOUT_SECONDS)
