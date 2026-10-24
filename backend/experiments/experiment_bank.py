"""
Validador de configuración de experimetnos de entrada
"""
from __future__ import annotations
from typing import Any, Self
from pydantic import (BaseModel,ConfigDict,Field,StrictInt,field_validator,model_validator,)
from core.sync.strategy import MAX_BATCH_SIZE_EVENTS, MIN_BATCH_SIZE_EVENTS
from experiments.e1 import (E1_CANONICAL_INDIVIDUAL_BYTES,E1_SEED,E1_START_TIME_SIM,E1_TREATMENTS,)

EXPERIMENT_BANK_SCHEMA_VERSION = 1
EXPERIMENT_BANK_DEFAULT_SEED = E1_SEED
E1_BANK_DEFAULT_START_TIME_SIM = E1_START_TIME_SIM
E1_BANK_DEFAULT_INDIVIDUAL_SYNCUNIT_BYTES = E1_CANONICAL_INDIVIDUAL_BYTES
E1_BANK_DEFAULT_BATCH_SIZES = tuple(
    treatment.batch_size_events
    for treatment in E1_TREATMENTS
    if treatment.batch_size_events is not None
)
_UNSUPPORTED_EXPERIMENTS = frozenset({"e2", "e3", "sensitivity", "e3_sensitivity"})

class _BankInputModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

class ExperimentBankScenario(_BankInputModel):
    id: str
    horizon_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    contact_plan_file: str
    description: str = ""
    notes: str = ""

    @field_validator("horizon_seconds", mode="before")
    @classmethod
    def horizon_must_not_be_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("horizon_seconds no admite booleanos")
        return value

    @field_validator("id", "contact_plan_file")
    @classmethod
    def text_reference_must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value


class ExperimentBankE1(_BankInputModel):
    """Parámetros declarados para E1, todavía sin resolver a corridas."""

    event_count: int = Field(gt=0, strict=True)
    event_interval_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    sender_ack_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    batch_sizes: tuple[StrictInt, ...] = E1_BANK_DEFAULT_BATCH_SIZES
    start_time_sim: float = Field(
        default=E1_BANK_DEFAULT_START_TIME_SIM,
        ge=0,
        allow_inf_nan=False,
        strict=True,
    )
    individual_syncunit_bytes: int = Field(
        default=E1_BANK_DEFAULT_INDIVIDUAL_SYNCUNIT_BYTES,
        gt=0,
        strict=True,
    )

    @field_validator(
        "event_count",
        "event_interval_seconds",
        "sender_ack_timeout_seconds",
        "batch_sizes",
        "start_time_sim",
        "individual_syncunit_bytes",
        mode="before",
    )
    @classmethod
    def numeric_fields_must_not_be_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("los campos numéricos no admiten booleanos")
        if isinstance(value, (list, tuple)) and any(isinstance(item, bool) for item in value):
            raise ValueError("batch_sizes no admite booleanos")
        return value

    @field_validator("batch_sizes")
    @classmethod
    def validate_batch_sizes(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value:
            raise ValueError("batch_sizes no debe estar vacío")
        if len(set(value)) != len(value):
            raise ValueError("batch_sizes no admite valores repetidos")
        if any(
            size < MIN_BATCH_SIZE_EVENTS or size > MAX_BATCH_SIZE_EVENTS
            for size in value
        ):
            raise ValueError(
                "cada batch_size debe estar entre "
                f"{MIN_BATCH_SIZE_EVENTS} y {MAX_BATCH_SIZE_EVENTS}, inclusive"
            )
        return value


class ExperimentBankExperiments(_BankInputModel):
    """Experimentos admitidos por la primera versión del contrato."""

    e1: ExperimentBankE1

    @model_validator(mode="before")
    @classmethod
    def reject_known_but_unsupported_experiments(cls, value: Any) -> Any:
        if isinstance(value, dict):
            unsupported = sorted(_UNSUPPORTED_EXPERIMENTS.intersection(value))
            if unsupported:
                names = ", ".join(unsupported)
                raise ValueError(
                    f"{names} todavía no está soportado por el contrato de entrada v1"
                )
        return value


class ExperimentBankDocument(_BankInputModel):
    """Documento validado, no una configuración efectiva de ejecución."""

    schema_version: int = Field(strict=True)
    seed: int = Field(default=EXPERIMENT_BANK_DEFAULT_SEED, strict=True)
    scenario: ExperimentBankScenario
    experiments: ExperimentBankExperiments

    @field_validator("schema_version", mode="before")
    @classmethod
    def schema_version_must_not_be_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("schema_version no admite booleanos")
        return value

    @field_validator("seed", mode="before")
    @classmethod
    def seed_must_not_be_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("seed no admite booleanos")
        return value

    @model_validator(mode="after")
    def supported_schema_version(self) -> Self:
        if self.schema_version != EXPERIMENT_BANK_SCHEMA_VERSION:
            raise ValueError(
                "schema_version no soportada: "
                f"se requiere {EXPERIMENT_BANK_SCHEMA_VERSION}"
            )
        return self
