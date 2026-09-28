from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LogicalNode(StrEnum):
    """
    Los valores son ``MARS``, ``RELAY`` y ``EARTH``.
    Identifican el origen y el destino de la ventana. No describen almacenamiento,
    reenvío ni ningún otro comportamiento del extremo.
    """
    MARS = "MARS"
    RELAY = "RELAY"
    EARTH = "EARTH"

class Contact(BaseModel):
    """Ventana de contacto dirigida e inmutable, en tiempo lógico de simulación.
    ``start_time_sim``, ``end_time_sim`` y ``propagation_delay_s`` están en
    segundos de simulación. ``data_rate_bps`` está en bits por segundo.
    La ventana activa es semiabierta por la derecha:
    ``start_time_sim <= t < end_time_sim``.
    ``end_time_sim`` solo debe ser mayor que ``start_time_sim`` según la
    comparación ``<=``. No hay otra cota: un fin ``+inf`` es válido si el
    inicio es finito, y un fin NaN también lo es, porque NaN no resulta
    ``<=`` que el inicio.
    La capacidad nominal, en bits, es ``duration_seconds * data_rate_bps``.
    El producto queda en ``float``, sin redondeo ni truncamiento.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    contact_id: str
    source: LogicalNode
    destination: LogicalNode
    start_time_sim: float = Field(ge=0)
    end_time_sim: float
    data_rate_bps: int = Field(gt=0)
    propagation_delay_s: float = Field(ge=0)

    @field_validator("contact_id")
    @classmethod
    def contact_id_must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

    @model_validator(mode="after")
    def check_interval_and_endpoints(self) -> Self:
        if self.end_time_sim <= self.start_time_sim:
            raise ValueError("end_time_sim debe ser mayor que start_time_sim")
        if self.source == self.destination:
            raise ValueError("source y destination deben ser distintos")
        return self

    @property
    def duration_seconds(self) -> float:
        """Duración de la ventana en segundos: fin menos inicio."""
        return self.end_time_sim - self.start_time_sim

    @property
    def nominal_capacity_bits(self) -> float:
        """Capacidad nominal en bits: ``duration_seconds * data_rate_bps``.

        El resultado es el producto en ``float``. No se redondea ni se trunca,
        y no se convierte a bytes.
        """
        return self.duration_seconds * self.data_rate_bps

    def is_active_at(self, time_sim: float) -> bool:
        """Indica si ``time_sim`` pertenece a la ventana ``[start_time_sim, end_time_sim)``."""
        return self.start_time_sim <= time_sim < self.end_time_sim