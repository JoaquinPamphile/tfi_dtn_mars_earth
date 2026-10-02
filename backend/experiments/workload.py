"""Carga científica de una corrida: qué telemetría se genera, cuándo y cuánto.

La generación es determinista. El evento ``n`` ocurre en
``start_time_sim + n / rate_events_per_second``. No hay una distribución
de llegada. La secuencia la asigna Marte al persistir.
"""

from __future__ import annotations

from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.domain.generation import TelemetryGenerationProfile
from core.domain.identity import make_generation_profile_id, make_telemetry_event_id
from core.domain.priority import TelemetryPriority
from core.mars.node import DEFAULT_SCHEMA_VERSION, DEFAULT_SOURCE_ID

from experiments.calibration import calibrate_individual_syncunit_payload
from experiments.offered_load import (
    generation_rate_for_event_count,
    offered_load_event_count,
)

CONTROLLED_COMMON_WORKLOAD_ID = "controlled-common-v1"
CONTROLLED_COMMON_EVENT_TYPE = "research.tfi.controlled_common"
CONTROLLED_COMMON_FLOW = "tfi.controlled_common"
CONTROLLED_COMMON_EVENT_RATE = 0.48828125
CONTROLLED_COMMON_PERIOD_SECONDS = 2.048
CONTROLLED_COMMON_CANONICAL_INDIVIDUAL_BYTES = 4096
CONTROLLED_COMMON_START_TIME_SIM = 0.0
CONTROLLED_COMMON_FINITE_DURATION_SECONDS = 21600.0


class Workload(BaseModel):
    """Perfil determinista de generación, inmutable.

    ``canonical_individual_syncunit_bytes`` es el tamaño de la SyncUnit
    Individual de intento 1, envoltura incluida. El codec lo produce; el
    payload solo aporta el padding necesario.

    ``offered_load_fraction``, cuando está presente, es la fracción ``f``
    con la que se obtuvo el conteo. El modelo no fija la grilla 0.25 … 1.20.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    workload_id: str = Field(min_length=1)
    source_id: str = DEFAULT_SOURCE_ID
    event_type: str = CONTROLLED_COMMON_EVENT_TYPE
    flow: str = CONTROLLED_COMMON_FLOW
    priority: TelemetryPriority = TelemetryPriority.NORMAL
    start_time_sim: float = Field(default=0.0, ge=0)
    duration_seconds: float | None = Field(default=None, gt=0)
    max_events: int | None = Field(default=None, gt=0)
    rate_events_per_second: float = Field(gt=0)
    canonical_individual_syncunit_bytes: int = Field(
        default=CONTROLLED_COMMON_CANONICAL_INDIVIDUAL_BYTES, gt=0
    )
    offered_load_fraction: float | None = Field(default=None, gt=0)

    @field_validator("workload_id", "source_id", "event_type", "flow")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

    @model_validator(mode="after")
    def require_a_bound(self) -> Self:
        if self.duration_seconds is None and self.max_events is None:
            raise ValueError("se requiere duration_seconds o max_events")
        return self

    def generation_profile(self, *, dataset_identity: str) -> TelemetryGenerationProfile:
        """Perfil de generación con identificador determinista."""
        profile_id = make_generation_profile_id(
            experiment_identity=dataset_identity,
            event_type=self.event_type,
            priority=self.priority.value,
            rate_events_per_second=self.rate_events_per_second,
            start_time_sim=self.start_time_sim,
            duration_seconds=self.duration_seconds,
            max_events=self.max_events,
        )
        return self._profile(profile_id)

    def expected_event_count(self) -> int:
        """Conteo que el generador va a emitir."""
        return self._profile("count").expected_event_count()

    def generation_timestamps(self) -> tuple[float, ...]:
        """``generated_at_sim`` de cada evento, en orden de índice ``n``."""
        profile = self._profile("timestamps")
        count = profile.expected_event_count()
        return tuple(profile.event_time(n) for n in range(count))

    def payload_for(
        self,
        *,
        dataset_identity: str,
        sequence_number: int,
        generated_at_sim: float,
        schema_version: int = DEFAULT_SCHEMA_VERSION,
    ) -> dict[str, Any]:
        """Payload calibrado para la secuencia que Marte está por asignar."""
        event_id = make_telemetry_event_id(
            dataset_identity=dataset_identity,
            source_id=self.source_id,
            sequence_number=sequence_number,
            generated_at_sim=generated_at_sim,
            event_type=self.event_type,
        )
        return calibrate_individual_syncunit_payload(
            make_payload=lambda padding: self._payload_body(padding),
            target_bytes=self.canonical_individual_syncunit_bytes,
            event_id=event_id,
            source_id=self.source_id,
            sequence_number=sequence_number,
            generated_at_sim=generated_at_sim,
            event_type=self.event_type,
            priority=self.priority,
            schema_version=schema_version,
        )

    def with_offered_load(
        self,
        *,
        load_fraction: float,
        capacity_bytes: float,
    ) -> Workload:
        """Copia con el conteo y la tasa que corresponden a ``f * C``.

        Exige ``duration_seconds``: la tasa es ``conteo / duración``.
        """
        if self.duration_seconds is None:
            raise ValueError("la carga ofrecida requiere duration_seconds")
        event_count = offered_load_event_count(
            load_fraction=load_fraction,
            capacity_bytes=capacity_bytes,
            canonical_individual_bytes=self.canonical_individual_syncunit_bytes,
        )
        if event_count < 1:
            raise ValueError(
                f"la fracción {load_fraction} produce 0 eventos con esa capacidad"
            )
        rate = generation_rate_for_event_count(
            event_count=event_count,
            duration_seconds=self.duration_seconds,
        )
        return self.model_copy(
            update={
                "max_events": event_count,
                "rate_events_per_second": rate,
                "offered_load_fraction": load_fraction,
            }
        )

    def _profile(self, profile_id: str) -> TelemetryGenerationProfile:
        return TelemetryGenerationProfile(
            profile_id=profile_id,
            event_type=self.event_type,
            priority=self.priority,
            rate_events_per_second=self.rate_events_per_second,
            start_time_sim=self.start_time_sim,
            duration_seconds=self.duration_seconds,
            max_events=self.max_events,
            enabled=True,
        )

    def _payload_body(self, padding: str) -> dict[str, Any]:
        return {
            "canonical_individual_syncunit_bytes": self.canonical_individual_syncunit_bytes,
            "flow": self.flow,
            "padding": padding,
            "workload_id": self.workload_id,
        }


def event_id_for(
    workload: Workload,
    *,
    dataset_identity: str,
    sequence_number: int,
    generated_at_sim: float,
) -> UUID:
    """Identidad de evento que Marte asignará con esta carga y este dataset."""
    return make_telemetry_event_id(
        dataset_identity=dataset_identity,
        source_id=workload.source_id,
        sequence_number=sequence_number,
        generated_at_sim=generated_at_sim,
        event_type=workload.event_type,
    )
