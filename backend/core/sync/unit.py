from copy import deepcopy
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.contact import LogicalNode


class SyncUnit(BaseModel):
    """Unidad de sincronización inmutable, independiente del transporte.

    No es un bundle, un bloque ni una PDU de Bundle Protocol. Un envío
    individual y un envío agrupado entregan este mismo tipo.

    ``sync_unit_id`` identifica la unidad. Se recibe ya formado: este modelo
    no lo deriva y no genera identificadores.

    ``event_ids`` son referencias por identificador, en el orden recibido.
    No son objetos ``TelemetryEvent``. La secuencia puede estar vacía y puede
    repetir identificadores.

    ``payload`` es un diccionario opaco. Se copia en profundidad al construir
    la unidad. ``payload_size_bytes`` es el tamaño de esa carga, en bytes, y
    también se recibe ya calculado: este modelo no lo deriva.

    ``created_at_sim`` está en segundos de simulación. ``submission_order``
    ordena unidades con el mismo instante; por defecto es 0.

    ``source_node`` y ``destination_node`` deben ser distintos al construir
    la unidad.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sync_unit_id: str
    source_node: LogicalNode
    destination_node: LogicalNode
    payload_size_bytes: int = Field(gt=0)
    event_ids: tuple[UUID, ...]
    created_at_sim: float = Field(ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)
    submission_order: int = Field(default=0, ge=0)

    @field_validator("sync_unit_id")
    @classmethod
    def sync_unit_id_must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

    @field_validator("event_ids", mode="before")
    @classmethod
    def tuple_event_ids(cls, value: object) -> tuple[UUID, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("event_ids debe ser una secuencia")
        return tuple(UUID(str(item)) if not isinstance(item, UUID) else item for item in value)

    @field_validator("payload")
    @classmethod
    def copy_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return deepcopy(value)

    @model_validator(mode="after")
    def endpoints_must_differ(self) -> Self:
        if self.source_node == self.destination_node:
            raise ValueError("source_node y destination_node deben ser distintos")
        return self

    def for_hop(self, source_node: LogicalNode, destination_node: LogicalNode) -> Self:
        """Misma identidad y misma carga, con el siguiente salto dirigido."""
        return self.model_copy(
            update={"source_node": source_node, "destination_node": destination_node}
        )
