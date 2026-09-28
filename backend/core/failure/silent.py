from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

SILENT_FORWARD_DELIVERY_LOSS_FAILURE_PREFIX = "silent-forward-delivery-loss"
FORWARD_HOP_RELAY_TO_EARTH = "RELAY_TO_EARTH"
TELEMETRY_EVENTS_PAYLOAD_KIND = "telemetry_events"

class SilentForwardDeliveryLossFailure(BaseModel):
    """Pérdida silenciosa de una entrega de aplicación en Tierra, después del salto.
    La serialización y la propagación del salto se completan. No se genera el
    arribo de aplicación en Tierra para la ocurrencia que coincide. No es un
    corte de contacto ni un fallo de envío local.
    El objetivo es determinista y explícito: ``source_id``, ``sequence_number``,
    ``telemetry_attempt_number`` y ``hop``. No intervienen ``event_id``, un
    identificador transitorio de transporte ni una semilla. ``max_occurrences``
    acota cuántas coincidencias de esa misma identidad se pierden. La primera
    coincidencia es la ocurrencia 1.
    Solo aplica a una carga ``telemetry_events`` de un único evento. La
    supresión efectiva de la entrega queda para el motor.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    failure_id: str
    source_id: str
    sequence_number: int = Field(ge=0)
    telemetry_attempt_number: int = Field(default=1, ge=1)
    hop: Literal["RELAY_TO_EARTH"] = FORWARD_HOP_RELAY_TO_EARTH
    max_occurrences: int = Field(default=1, ge=1)

    @field_validator("failure_id", "source_id")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

    def matches(
        self,
        *,
        source_id: str,
        sequence_number: int,
        telemetry_attempt_number: int,
        hop: str,
        payload_kind: str | None,
        event_count: int,
        occurrences_used: int,
    ) -> bool:
        """Indica si esta definición selecciona la entrega candidata.
        No modifica ``occurrences_used`` ni descarta la entrega.
        """
        if payload_kind != TELEMETRY_EVENTS_PAYLOAD_KIND:
            return False
        if event_count != 1:
            return False
        if self.hop != hop:
            return False
        if self.source_id != source_id:
            return False
        if self.sequence_number != sequence_number:
            return False
        if self.telemetry_attempt_number != telemetry_attempt_number:
            return False
        if occurrences_used >= self.max_occurrences:
            return False
        return True

def silent_forward_delivery_loss_failure_id(
    source_id: str,
    sequence_number: int,
    telemetry_attempt_number: int,
    hop: str,
) -> str:
    """Identificador determinista de una pérdida silenciosa.
    Las mismas cuatro entradas producen siempre el mismo identificador.
    """
    return (
        f"{SILENT_FORWARD_DELIVERY_LOSS_FAILURE_PREFIX}-"
        f"{source_id}-{sequence_number}-a{telemetry_attempt_number}-{hop}"
    )

@dataclass(frozen=True, slots=True)
class SilentForwardDeliveryLossHit:
    """Coincidencia de una pérdida silenciosa, sin registrar el descarte.
    ``occurrence_number`` es 1-based: la primera coincidencia de esa
    identidad vale 1.
    """
    failure: SilentForwardDeliveryLossFailure
    occurrence_number: int
