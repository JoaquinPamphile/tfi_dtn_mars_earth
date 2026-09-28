from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class ApplicationAckStatus(StrEnum):
    ACCEPTED = "ACCEPTED"

def _coerce_event_ids(value: object, *, allow_empty: bool) -> tuple[UUID, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("las listas de event_ids deben ser una secuencia")
    items = tuple(UUID(str(item)) if not isinstance(item, UUID) else item for item in value)
    if not items and not allow_empty:
        raise ValueError("event_ids no debe estar vacío")
    return items

class ApplicationAck(BaseModel):
    """Tierra procesó los eventos de telemetría en un SyncUnit duradero.
    - ``accepted_event_ids``: eventos únicos recién persistidos
    - ``duplicate_event_ids``: ya persistidos (reproducción idempotente)
    - ``rejected_event_ids``: no confirmados;

    Marte confirma ``accepted_event_ids`` y ``duplicate_event_ids``.
    Los eventos rechazados siguen sin confirmar.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    ack_id: str
    event_ids: tuple[UUID, ...]
    generated_at_sim: float = Field(ge=0)
    status: ApplicationAckStatus
    accepted_event_ids: tuple[UUID, ...] = ()
    duplicate_event_ids: tuple[UUID, ...] = ()
    rejected_event_ids: tuple[UUID, ...] = ()

    @field_validator("ack_id")
    @classmethod
    def ack_id_must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

    @field_validator("event_ids", mode="before")
    @classmethod
    def tuple_event_ids(cls, value: object) -> tuple[UUID, ...]:
        return _coerce_event_ids(value, allow_empty=False)

    @field_validator(
        "accepted_event_ids",
        "duplicate_event_ids",
        "rejected_event_ids",
        mode="before",
    )
    @classmethod
    def tuple_outcome_ids(cls, value: object) -> tuple[UUID, ...]:
        if value is None:
            return ()
        return _coerce_event_ids(value, allow_empty=True)

    @model_validator(mode="after")
    def status_is_application_acceptance(self) -> Self:
        if self.status is not ApplicationAckStatus.ACCEPTED:
            raise ValueError("el estado del ACK debe representar la aceptación durable en Tierra")
        return self

    @model_validator(mode="after")
    def default_accepted_from_unit_membership(self) -> Self:
        if (
            not self.accepted_event_ids
            and not self.duplicate_event_ids
            and not self.rejected_event_ids
        ):
            object.__setattr__(self, "accepted_event_ids", self.event_ids)
        return self

    def confirmed_event_ids(self) -> tuple[UUID, ...]:
        """Eventos que Marte debe tratar como confirmados a nivel de aplicación."""
        seen: set[UUID] = set()
        ordered: list[UUID] = []
        for event_id in (*self.accepted_event_ids, *self.duplicate_event_ids):
            if event_id in seen:
                continue
            seen.add(event_id)
            ordered.append(event_id)
        return tuple(ordered)

    def to_dict(self) -> dict[str, object]:
        return {
            "ack_id": self.ack_id,
            "event_ids": [str(event_id) for event_id in self.event_ids],
            "generated_at_sim": self.generated_at_sim,
            "status": self.status.value,
            "accepted_event_ids": [str(event_id) for event_id in self.accepted_event_ids],
            "duplicate_event_ids": [str(event_id) for event_id in self.duplicate_event_ids],
            "rejected_event_ids": [str(event_id) for event_id in self.rejected_event_ids],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls(
            ack_id=str(data["ack_id"]),
            event_ids=tuple(data["event_ids"]),  # type: ignore[arg-type]
            generated_at_sim=float(data["generated_at_sim"]),  # type: ignore[arg-type]
            status=ApplicationAckStatus(str(data["status"])),
            accepted_event_ids=tuple(data.get("accepted_event_ids") or ()),  # type: ignore[arg-type]
            duplicate_event_ids=tuple(data.get("duplicate_event_ids") or ()),  # type: ignore[arg-type]
            rejected_event_ids=tuple(data.get("rejected_event_ids") or ()),  # type: ignore[arg-type]
        )
