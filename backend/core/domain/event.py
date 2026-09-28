from __future__ import annotations

import json
from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.domain.priority import TelemetryPriority


class TelemetryEvent(BaseModel):
    """Observación de telemetría inmutable. Una corrección debe ser un evento nuevo."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_id: UUID = Field(default_factory=uuid4)
    source_id: str
    sequence_number: int = Field(ge=0)
    generated_at_sim: float = Field(ge=0)
    event_type: str
    payload: dict[str, Any]
    priority: TelemetryPriority
    schema_version: int = Field(ge=1)

    @field_validator("source_id", "event_type")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

    @field_validator("payload")
    @classmethod
    def copy_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return deepcopy(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "source_id": self.source_id,
            "sequence_number": self.sequence_number,
            "generated_at_sim": self.generated_at_sim,
            "event_type": self.event_type,
            "payload": deepcopy(self.payload),
            "priority": self.priority.value,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryEvent:
        return cls(
            event_id=UUID(str(data["event_id"])),
            source_id=data["source_id"],
            sequence_number=data["sequence_number"],
            generated_at_sim=data["generated_at_sim"],
            event_type=data["event_type"],
            payload=data["payload"],
            priority=TelemetryPriority(data["priority"]),
            schema_version=data["schema_version"],
        )

    @classmethod
    def from_json(cls, raw: str) -> TelemetryEvent:
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise ValueError("la raíz JSON debe ser un objeto")
        return cls.from_dict(loaded)
