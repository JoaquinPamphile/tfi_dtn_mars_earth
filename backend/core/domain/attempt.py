from collections.abc import Sequence
from enum import StrEnum
from typing import Self
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SYNC_GROUP_NAMESPACE = uuid5(NAMESPACE_URL, "https://tfi.local/dtn-mars-earth-lab/sync-group")


class SyncAttemptStatus(StrEnum):
    """Ciclo de vida del intento a nivel de aplicación. Independiente de TelemetryEvent."""
    QUEUED = "QUEUED"
    IN_FLIGHT = "IN_FLIGHT"
    DELIVERED_TO_EARTH = "DELIVERED_TO_EARTH"
    ACK_PENDING = "ACK_PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INTERRUPTED = "INTERRUPTED"
    TIMED_OUT = "TIMED_OUT"
    REPAIR_REQUESTED = "REPAIR_REQUESTED"

ACTIVE_ATTEMPT_STATUSES = frozenset(
    {
        SyncAttemptStatus.QUEUED,
        SyncAttemptStatus.IN_FLIGHT,
        SyncAttemptStatus.DELIVERED_TO_EARTH,
        SyncAttemptStatus.ACK_PENDING,
    }
)

TERMINAL_ATTEMPT_STATUSES = frozenset(
    {
        SyncAttemptStatus.ACKNOWLEDGED,
        SyncAttemptStatus.INTERRUPTED,
        SyncAttemptStatus.TIMED_OUT,
        SyncAttemptStatus.REPAIR_REQUESTED,
    }
)

class SyncAttempt(BaseModel):
    """Un intento de sincronización de aplicación para un SyncPlan.
    El SyncPlan define la cantidad de intentos de transmisión para un grupo de eventos.
    ``sync_group_id`` identifica el grupo ordenado de eventos.
    ``attempt_id`` identifica la transmisióne.
    ``attempt_number`` comienza en 1 dentro de ese linaje: el primer envío es 1,
    un retry es 2, y así sucesivamente.
    ``parent_attempt_id`` apunta al intento que se continúa —por timeout,
    interrupción o reemplazo del receptor— cuando este intento es un retry
    del emisor o una reparación receiver-driven.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    attempt_id: str
    event_ids: tuple[UUID, ...]
    created_at_sim: float = Field(ge=0)
    first_submitted_at_sim: float = Field(ge=0)
    last_submitted_at_sim: float = Field(ge=0)
    attempt_number: int = Field(ge=1)
    status: SyncAttemptStatus
    sync_group_id: str = ""
    parent_attempt_id: str | None = None

    @field_validator("attempt_id")
    @classmethod
    def attempt_id_not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

    @field_validator("event_ids")
    @classmethod
    def event_ids_not_empty(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not value:
            raise ValueError("event_ids no debe estar vacío")
        return value

    @model_validator(mode="after")
    def default_sync_group_id(self) -> Self:
        if self.sync_group_id.strip() == "":
            self.sync_group_id = sync_group_id_for(self.event_ids)
        return self

def sync_group_id_for(event_ids: Sequence[UUID]) -> str:
    """Identidad determinista de un grupo ordenado de eventos."""
    items = tuple(event_ids)
    if not items:
        raise ValueError("event_ids no debe estar vacío")
    if len(items) == 1:
        return str(items[0])
    name = "\n".join(str(event_id) for event_id in items)
    return str(uuid5(SYNC_GROUP_NAMESPACE, name))

def attempt_id_for(event_id: UUID, attempt_number: int) -> str:
    return f"att-{event_id}-n{attempt_number}"

def attempt_id_for_group(event_ids: Sequence[UUID], attempt_number: int) -> str:
    """Identidad del intento para un grupo ordenado completo de eventos."""
    return f"att-{sync_group_id_for(event_ids)}-n{attempt_number}"
