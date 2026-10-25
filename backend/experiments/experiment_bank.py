"""Valida la entrada del banco y prepara una campaña E1 sin ejecutarla."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from core.domain.priority import TelemetryPriority
from core.domain.retry import RetryPolicy
from core.failure.plan import FailurePlan
from core.recovery.policy import RecoveryPolicy
from core.stopping.policy import StopPolicy
from core.sync.strategy import MAX_BATCH_SIZE_EVENTS, MIN_BATCH_SIZE_EVENTS
from core.sync.strategy import STRATEGY_TYPE_FIXED_BATCH, STRATEGY_TYPE_INDIVIDUAL
from core.trace.level import TraceLevel

from experiments.campaign import CampaignRunSpec, CampaignSpec
from experiments.contact_plan import ContactPlanDefinition
from experiments.scenario_adapter import scenario_from_contact_plan_definition
from experiments.spec import ScientificRunSpec
from experiments.workload import Workload

EXPERIMENT_BANK_SCHEMA_VERSION = 1
# Defaults propios de la versión 1 del contrato de entrada. Inicialmente
# coinciden con E1 oficial, pero no se derivan de su builder histórico.
EXPERIMENT_BANK_DEFAULT_SEED = 1
E1_BANK_DEFAULT_START_TIME_SIM = 0.0
E1_BANK_DEFAULT_INDIVIDUAL_SYNCUNIT_BYTES = 4096
E1_BANK_DEFAULT_BATCH_SIZES = (10, 25, 50)
_UNSUPPORTED_EXPERIMENTS = frozenset({"e2", "e3", "sensitivity", "e3_sensitivity"})

E1_BANK_CAMPAIGN_ID = "e1-experiment-bank-v1"
E1_BANK_CAMPAIGN_DESCRIPTION = (
    "E1 configurable resuelto desde el banco experimental v1. "
    "No es el diseño oficial de E1."
)
# Estos identificadores forman parte del workload materializado y, por lo
# tanto, de sus payloads y huellas. No atribuyen este banco al escenario Alessi.
E1_BANK_WORKLOAD_ID = "experiment-bank-e1-v1"
E1_BANK_EVENT_TYPE = "research.tfi.experiment_bank.e1"
E1_BANK_FLOW = "tfi.experiment_bank.e1"

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


@dataclass(frozen=True, slots=True)
class ResolvedE1Campaign:
    """Resolución inmutable con sus dos documentos de entrada y el spec efectivo."""

    bank_document: ExperimentBankDocument
    contact_plan_definition: ContactPlanDefinition
    campaign: CampaignSpec


def resolve_e1_campaign(
    bank_document: ExperimentBankDocument,
    contact_plan_definition: ContactPlanDefinition,
) -> ResolvedE1Campaign:
    """Convierte en memoria una entrada validada del banco en una campaña E1.

    ``contact_plan_file`` queda solo en ``bank_document`` como referencia:
    esta función no abre archivos ni presume el origen de la definición recibida.
    La resolución construye una especificación ejecutable, pero no certifica
    completitud, convergencia, ausencia de retries ni las condiciones científicas
    del estudio oficial E1. La evaluación de campañas configurables es separada.
    """
    scenario_config = bank_document.scenario
    e1_config = bank_document.experiments.e1
    scenario = scenario_from_contact_plan_definition(
        contact_plan_definition,
        scenario_id=scenario_config.id,
        horizon_seconds=scenario_config.horizon_seconds,
        description=scenario_config.description,
        notes=scenario_config.notes,
    )

    rate_events_per_second = 1.0 / e1_config.event_interval_seconds
    if not isfinite(rate_events_per_second) or rate_events_per_second <= 0:
        raise ValueError(
            "la tasa derivada debe ser finita y positiva: "
            f"event_interval_seconds={e1_config.event_interval_seconds}, "
            f"rate_events_per_second={rate_events_per_second}"
        )

    workload = Workload(
        workload_id=E1_BANK_WORKLOAD_ID,
        event_type=E1_BANK_EVENT_TYPE,
        flow=E1_BANK_FLOW,
        priority=TelemetryPriority.NORMAL,
        start_time_sim=e1_config.start_time_sim,
        duration_seconds=None,
        max_events=e1_config.event_count,
        rate_events_per_second=rate_events_per_second,
        canonical_individual_syncunit_bytes=e1_config.individual_syncunit_bytes,
        offered_load_fraction=None,
    )
    retry_policy = RetryPolicy(
        ack_timeout_seconds=e1_config.sender_ack_timeout_seconds
    )
    failure_plan = FailurePlan()
    shared_run_parameters = {
        "scenario": scenario,
        "workload": workload,
        "seed": bank_document.seed,
        "recovery_policy": RecoveryPolicy.SENDER_DRIVEN,
        "retry_policy": retry_policy,
        "failure_plan": failure_plan,
        "stop_policy": StopPolicy.PROFILE_HORIZON_SETTLED,
        "trace_level": TraceLevel.SCIENTIFIC,
    }
    individual_spec = ScientificRunSpec(
        strategy_type=STRATEGY_TYPE_INDIVIDUAL,
        **shared_run_parameters,
    )
    generation_profile = workload.generation_profile(
        dataset_identity=individual_spec.dataset_identity
    )
    last_generation_at_sim = generation_profile.last_generation_at_sim()
    if (
        last_generation_at_sim is not None
        and last_generation_at_sim > scenario_config.horizon_seconds
    ):
        raise ValueError(
            "el último evento queda después del horizonte: "
            f"event_count={e1_config.event_count}, "
            f"event_interval_seconds={e1_config.event_interval_seconds}, "
            f"start_time_sim={e1_config.start_time_sim}, "
            f"last_generation_at_sim={last_generation_at_sim}, "
            f"horizon_seconds={scenario_config.horizon_seconds}"
        )

    runs = [CampaignRunSpec(label="individual", spec=individual_spec)]
    runs.extend(
        CampaignRunSpec(
            label=f"fixed_batch_{batch_size}",
            spec=ScientificRunSpec(
                strategy_type=STRATEGY_TYPE_FIXED_BATCH,
                batch_size_events=batch_size,
                **shared_run_parameters,
            ),
        )
        for batch_size in e1_config.batch_sizes
    )
    campaign = CampaignSpec(
        campaign_id=E1_BANK_CAMPAIGN_ID,
        description=E1_BANK_CAMPAIGN_DESCRIPTION,
        runs=tuple(runs),
    )
    return ResolvedE1Campaign(
        bank_document=bank_document,
        contact_plan_definition=contact_plan_definition,
        campaign=campaign,
    )
