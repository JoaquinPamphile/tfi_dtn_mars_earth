"""Escenario de una corrida: contactos, nodos lógicos y horizonte.

Describe el comportamiento físico y lógico. No guarda métricas,
resultados ni la forma de cargarlo desde un archivo.
"""

from __future__ import annotations

from math import isfinite
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.contact.contact import Contact, LogicalNode
from core.contact.plan import ContactPlan


class Scenario(BaseModel):
    """Geometría lógica de una corrida, inmutable.

    ``horizon_seconds`` es el horizonte del perfil, en segundos de
    simulación. La política de parada vive en la especificación de la
    corrida y decide cómo se usa ese horizonte.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str
    contacts: tuple[Contact, ...]
    horizon_seconds: float | None = Field(default=None, gt=0)
    description: str = ""
    notes: str = ""

    @field_validator("scenario_id")
    @classmethod
    def scenario_id_must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

    @model_validator(mode="after")
    def finite_horizon_and_plan(self) -> Self:
        if self.horizon_seconds is not None and not isfinite(self.horizon_seconds):
            raise ValueError("el horizonte debe ser finito y mayor que 0")
        ContactPlan(self.contacts)
        return self

    @property
    def contact_plan(self) -> ContactPlan:
        """Plan ordenado que consume el runtime."""
        return ContactPlan(self.contacts)

    @property
    def logical_nodes(self) -> tuple[LogicalNode, ...]:
        """Nodos que aparecen como origen o destino de algún contacto."""
        present = {contact.source for contact in self.contacts}
        present.update(contact.destination for contact in self.contacts)
        return tuple(node for node in LogicalNode if node in present)


def directed_round_trip(
    *,
    prefix: str,
    start_time_sim: float,
    end_time_sim: float,
    data_rate_bps: int,
    propagation_delay_s: float,
) -> tuple[Contact, ...]:
    """Cuatro ventanas simultáneas, una por sentido del round trip.

    Sirve para escenarios controlados pequeños. Cada ventana es explícita.
    """
    links = (
        ("mars-relay", LogicalNode.MARS, LogicalNode.RELAY),
        ("relay-earth", LogicalNode.RELAY, LogicalNode.EARTH),
        ("earth-relay", LogicalNode.EARTH, LogicalNode.RELAY),
        ("relay-mars", LogicalNode.RELAY, LogicalNode.MARS),
    )
    return tuple(
        Contact(
            contact_id=f"{prefix}-{name}",
            source=source,
            destination=destination,
            start_time_sim=start_time_sim,
            end_time_sim=end_time_sim,
            data_rate_bps=data_rate_bps,
            propagation_delay_s=propagation_delay_s,
        )
        for name, source, destination in links
    )
