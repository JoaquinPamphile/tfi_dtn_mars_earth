from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

ACK_DROP_FAILURE_ID = "ack-drop-first-n"

class AckDropFailure(BaseModel):
    """Pérdida de los primeros N ACK de aplicación tras persistir en Tierra.
    ``mode`` es ``first_n``. ``count`` es cuántos ACK generados se pierden.
    ``count`` 0 es válido y no selecciona ninguna pérdida.
    La selección es ordinal: el primer ACK generado, luego el segundo, hasta
    ``count``. No usa ``event_id`` ni una semilla. El descarte efectivo queda
    para el motor.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    failure_id: str
    mode: Literal["first_n"] = "first_n"
    count: int = Field(ge=0)

    @field_validator("failure_id")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value
