"""Valida la entrada del banco y prepara campañas E1 y E2 sin ejecutarlas.

El documento v1 acepta exactamente una sección: ``experiments.e1`` o
``experiments.e2``. Cada resolver exige su sección y no corre el motor.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationError,
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
from experiments.offered_load import ReferenceCapacity, reference_mars_to_relay_capacity
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
# Defaults explícitos del contrato E2. No se importan del experimento oficial.
E2_BANK_DEFAULT_START_TIME_SIM = 0.0
E2_BANK_DEFAULT_INDIVIDUAL_SYNCUNIT_BYTES = 4096
E2_BANK_DEFAULT_BATCH_SIZE_EVENTS = 25
_ADMITTED_EXPERIMENT_SECTIONS = frozenset({"e1", "e2"})
_UNSUPPORTED_EXPERIMENTS = frozenset({"e3", "sensitivity", "e3_sensitivity"})

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
E2_BANK_CAMPAIGN_ID = "e2-experiment-bank-v1"
E2_BANK_CAMPAIGN_DESCRIPTION = (
    "E2 configurable resuelto desde el banco experimental v1. "
    "No es el diseño oficial de E2."
)
# Entran en el workload materializado. No son los identificadores de Alessi
# ni los de la campaña oficial de carga ofrecida.
E2_BANK_WORKLOAD_ID = "experiment-bank-e2-v1"
E2_BANK_EVENT_TYPE = "research.tfi.experiment_bank.e2"
E2_BANK_FLOW = "tfi.experiment_bank.e2"

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


class ExperimentBankE2(_BankInputModel):
    """Parámetros declarados para E2, todavía sin resolver a corridas.

    ``individual_syncunit_bytes`` es el tamaño canónico de la SyncUnit
    Individual, no solamente el del payload. ``capacity_interval_end_sim``
    en ``None`` usa el horizonte del escenario como fin de capacidad.
    """

    generation_duration_seconds: float = Field(
        gt=0,
        allow_inf_nan=False,
        strict=True,
    )
    offered_load_fractions: tuple[float, ...]
    sender_ack_timeout_seconds: float = Field(
        gt=0,
        allow_inf_nan=False,
        strict=True,
    )
    start_time_sim: float = Field(
        default=E2_BANK_DEFAULT_START_TIME_SIM,
        ge=0,
        allow_inf_nan=False,
        strict=True,
    )
    individual_syncunit_bytes: int = Field(
        default=E2_BANK_DEFAULT_INDIVIDUAL_SYNCUNIT_BYTES,
        gt=0,
        strict=True,
    )
    batch_size_events: int = Field(
        default=E2_BANK_DEFAULT_BATCH_SIZE_EVENTS,
        ge=MIN_BATCH_SIZE_EVENTS,
        le=MAX_BATCH_SIZE_EVENTS,
        strict=True,
    )
    capacity_interval_end_sim: float | None = Field(
        default=None,
        allow_inf_nan=False,
        strict=True,
    )

    @field_validator(
        "generation_duration_seconds",
        "offered_load_fractions",
        "sender_ack_timeout_seconds",
        "start_time_sim",
        "individual_syncunit_bytes",
        "batch_size_events",
        "capacity_interval_end_sim",
        mode="before",
    )
    @classmethod
    def numeric_fields_must_not_be_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("los campos numéricos no admiten booleanos")
        if isinstance(value, (list, tuple)) and any(isinstance(item, bool) for item in value):
            raise ValueError("offered_load_fractions no admite booleanos")
        return value

    @field_validator("offered_load_fractions", mode="before")
    @classmethod
    def validate_offered_load_fractions(cls, value: Any) -> Any:
        if not isinstance(value, (list, tuple)):
            raise ValueError("offered_load_fractions debe ser una colección de números")
        if len(value) == 0:
            raise ValueError("offered_load_fractions no debe estar vacío")
        accepted: list[float] = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValueError("cada fracción debe ser un número finito mayor que 0")
            number = float(item)
            if not isfinite(number) or number <= 0:
                raise ValueError("cada fracción debe ser finita y mayor que 0")
            if number in accepted:
                raise ValueError("offered_load_fractions no admite valores repetidos")
            accepted.append(number)
        return accepted

    @model_validator(mode="after")
    def capacity_end_must_follow_start(self) -> Self:
        end = self.capacity_interval_end_sim
        if end is not None and end <= self.start_time_sim:
            raise ValueError(
                "capacity_interval_end_sim debe ser mayor que start_time_sim"
            )
        return self


class ExperimentBankExperiments(_BankInputModel):
    """Sección E1 del documento. No incluye ni serializa E2."""

    e1: ExperimentBankE1


class ExperimentBankE2Section(_BankInputModel):
    """Sección E2 del documento. No es una campaña resuelta ni ejecutable."""

    e2: ExperimentBankE2


class ExperimentBankDocument(_BankInputModel):
    """Documento validado, no una configuración efectiva de ejecución.

    Contiene exactamente una sección, E1 o E2. Validar el documento no
    resuelve ni ejecuta la campaña.
    """

    schema_version: int = Field(strict=True)
    seed: int = Field(default=EXPERIMENT_BANK_DEFAULT_SEED, strict=True)
    scenario: ExperimentBankScenario
    experiments: ExperimentBankExperiments | ExperimentBankE2Section

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

    @field_validator("experiments", mode="before")
    @classmethod
    def select_exactly_one_experiment(cls, value: Any) -> Any:
        if isinstance(value, (ExperimentBankExperiments, ExperimentBankE2Section)):
            return value
        if not isinstance(value, dict):
            return value
        unsupported = sorted(_UNSUPPORTED_EXPERIMENTS.intersection(value))
        if unsupported:
            names = ", ".join(unsupported)
            raise ValueError(
                f"{names} todavía no está soportado por el contrato de entrada v1"
            )
        unknown = sorted(set(value).difference(_ADMITTED_EXPERIMENT_SECTIONS))
        if unknown:
            names = ", ".join(unknown)
            raise ValueError(f"clave desconocida en experiments: {names}")
        selected = [name for name in ("e1", "e2") if name in value]
        if len(selected) == 0:
            raise ValueError(
                "el documento debe incluir exactamente una sección: "
                "experiments.e1 o experiments.e2"
            )
        if len(selected) > 1:
            raise ValueError(
                "experiments.e1 y experiments.e2 no pueden estar presentes a la vez"
            )
        chosen = selected[0]
        if value[chosen] is None:
            raise ValueError(f"experiments.{chosen} no puede ser null")
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


def require_e1_bank_selection(
    bank_document: ExperimentBankDocument,
) -> ExperimentBankE1:
    """Devuelve la sección E1 o rechaza un documento que selecciona E2."""
    experiments = bank_document.experiments
    if isinstance(experiments, ExperimentBankE2Section):
        raise ValueError(
            "el documento selecciona experiments.e2; "
            "resolve_e1_campaign solo acepta experiments.e1 "
            "y no construye ni ejecuta una campaña E2"
        )
    if isinstance(experiments, ExperimentBankExperiments):
        return experiments.e1
    raise ValueError("el documento no selecciona experiments.e1")


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
    Un documento que selecciona E2 se rechaza con ValueError antes de
    construir el escenario o la campaña.
    """
    e1_config = require_e1_bank_selection(bank_document)
    scenario_config = bank_document.scenario
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


@dataclass(frozen=True, slots=True)
class ResolvedE2Campaign:
    """Resolución E2 inmutable. No guarda resultados ni métricas de una corrida."""

    bank_document: ExperimentBankDocument
    contact_plan_definition: ContactPlanDefinition
    campaign: CampaignSpec
    reference_capacity: ReferenceCapacity


def require_e2_bank_selection(
    bank_document: ExperimentBankDocument,
) -> ExperimentBankE2:
    """Devuelve la sección E2 o rechaza un documento que selecciona E1."""
    experiments = bank_document.experiments
    if isinstance(experiments, ExperimentBankExperiments):
        raise ValueError(
            "el documento selecciona experiments.e1; "
            "resolve_e2_campaign solo acepta experiments.e2 "
            "y no construye ni ejecuta una campaña E1"
        )
    if isinstance(experiments, ExperimentBankE2Section):
        return experiments.e2
    raise ValueError("el documento no selecciona experiments.e2")


def resolve_e2_campaign(
    bank_document: ExperimentBankDocument,
    contact_plan_definition: ContactPlanDefinition,
) -> ResolvedE2Campaign:
    """Convierte una entrada E2 validada en una campaña, sin ejecutarla.

    Rechaza un documento E1 antes de construir el escenario. Los contactos
    del escenario son los del plan recibido, sin recorte: el intervalo solo
    entra en el cálculo de capacidad.

    El fin de capacidad es ``capacity_interval_end_sim`` cuando está
    definido y, si no, el horizonte del escenario. La capacidad es la suma
    nominal de bytes serializables Marte → relé que solapan ese intervalo.
    No es capacidad extremo a extremo, utilización realizada ni una garantía
    de entrega. No exige convergencia, retorno suficiente ni ausencia de
    retries, y no usa el fin del último contacto del E2 oficial.
    """
    e2_config = require_e2_bank_selection(bank_document)
    scenario_config = bank_document.scenario
    scenario = scenario_from_contact_plan_definition(
        contact_plan_definition,
        scenario_id=scenario_config.id,
        horizon_seconds=scenario_config.horizon_seconds,
        description=scenario_config.description,
        notes=scenario_config.notes,
    )
    interval_start, interval_end = _e2_capacity_interval(
        e2_config,
        horizon_seconds=scenario_config.horizon_seconds,
    )
    capacity = reference_mars_to_relay_capacity(
        scenario,
        interval_start_sim=interval_start,
        interval_end_sim=interval_end,
    )
    _require_positive_finite_capacity(capacity)

    # La tasa 1.0 solo completa el workload base. with_offered_load la reemplaza.
    base_workload = Workload(
        workload_id=E2_BANK_WORKLOAD_ID,
        event_type=E2_BANK_EVENT_TYPE,
        flow=E2_BANK_FLOW,
        priority=TelemetryPriority.NORMAL,
        start_time_sim=e2_config.start_time_sim,
        duration_seconds=e2_config.generation_duration_seconds,
        max_events=None,
        rate_events_per_second=1.0,
        canonical_individual_syncunit_bytes=e2_config.individual_syncunit_bytes,
    )
    retry_policy = RetryPolicy(
        ack_timeout_seconds=e2_config.sender_ack_timeout_seconds
    )
    failure_plan = FailurePlan()
    shared_run_parameters = {
        "scenario": scenario,
        "seed": bank_document.seed,
        "recovery_policy": RecoveryPolicy.SENDER_DRIVEN,
        "retry_policy": retry_policy,
        "failure_plan": failure_plan,
        "stop_policy": StopPolicy.PROFILE_HORIZON_SETTLED,
        "trace_level": TraceLevel.SCIENTIFIC,
    }
    runs: list[CampaignRunSpec] = []
    for load_index, load_fraction in enumerate(e2_config.offered_load_fractions):
        workload = _e2_workload_for_fraction(
            base_workload,
            load_index=load_index,
            load_fraction=load_fraction,
            capacity_bytes=capacity.serialized_capacity_bytes,
            individual_bytes=e2_config.individual_syncunit_bytes,
            duration_seconds=e2_config.generation_duration_seconds,
        )
        pair_parameters = {**shared_run_parameters, "workload": workload}
        runs.append(
            CampaignRunSpec(
                label=f"load_{load_index}_{STRATEGY_TYPE_INDIVIDUAL}",
                spec=ScientificRunSpec(
                    strategy_type=STRATEGY_TYPE_INDIVIDUAL,
                    **pair_parameters,
                ),
            )
        )
        runs.append(
            CampaignRunSpec(
                label=f"load_{load_index}_{STRATEGY_TYPE_FIXED_BATCH}",
                spec=ScientificRunSpec(
                    strategy_type=STRATEGY_TYPE_FIXED_BATCH,
                    batch_size_events=e2_config.batch_size_events,
                    **pair_parameters,
                ),
            )
        )
    campaign = CampaignSpec(
        campaign_id=E2_BANK_CAMPAIGN_ID,
        description=E2_BANK_CAMPAIGN_DESCRIPTION,
        runs=tuple(runs),
    )
    return ResolvedE2Campaign(
        bank_document=bank_document,
        contact_plan_definition=contact_plan_definition,
        campaign=campaign,
        reference_capacity=capacity,
    )


def _e2_capacity_interval(
    e2_config: ExperimentBankE2,
    *,
    horizon_seconds: float,
) -> tuple[float, float]:
    """``[inicio, fin de capacidad]`` acotado por el horizonte.

    ``fin`` es el extremo explícito o el horizonte. La generación debe
    terminar en el horizonte o antes. No recorta los contactos.
    """
    start = e2_config.start_time_sim
    end = (
        horizon_seconds
        if e2_config.capacity_interval_end_sim is None
        else e2_config.capacity_interval_end_sim
    )
    generation_end = start + e2_config.generation_duration_seconds
    if not isfinite(start) or not isfinite(end) or not isfinite(generation_end):
        raise ValueError(
            "una magnitud derivada del intervalo no es finita: "
            f"start_time_sim={start}, "
            f"capacity_interval_end_sim={end}, "
            f"generation_duration_seconds={e2_config.generation_duration_seconds}, "
            f"generation_end_sim={generation_end}, "
            f"horizon_seconds={horizon_seconds}"
        )
    if not (0 <= start < end <= horizon_seconds):
        raise ValueError(
            "el intervalo de capacidad debe cumplir "
            "0 <= start_time_sim < fin_capacidad <= horizon_seconds: "
            f"start_time_sim={start}, "
            f"capacity_interval_end_sim={end}, "
            f"horizon_seconds={horizon_seconds}"
        )
    if generation_end > horizon_seconds:
        raise ValueError(
            "la generación debe terminar dentro del horizonte: "
            f"start_time_sim={start}, "
            f"generation_duration_seconds={e2_config.generation_duration_seconds}, "
            f"generation_end_sim={generation_end}, "
            f"horizon_seconds={horizon_seconds}"
        )
    return start, end


def _require_positive_finite_capacity(capacity: ReferenceCapacity) -> None:
    """La suma nominal Marte → relé tiene que ser un real positivo."""
    amount = capacity.serialized_capacity_bytes
    if not isfinite(amount) or amount <= 0:
        raise ValueError(
            "la capacidad serializable nominal Marte → relé debe ser finita "
            "y mayor que 0. No es capacidad extremo a extremo, utilización "
            "ni garantía de entrega: "
            f"interval_start_sim={capacity.interval_start_sim}, "
            f"interval_end_sim={capacity.interval_end_sim}, "
            f"serialized_capacity_bytes={amount}, "
            f"contact_count={capacity.contact_count}"
        )


def _e2_workload_for_fraction(
    base_workload: Workload,
    *,
    load_index: int,
    load_fraction: float,
    capacity_bytes: float,
    individual_bytes: int,
    duration_seconds: float,
) -> Workload:
    """Conteo y tasa de una fracción, con un mensaje que la identifica."""
    context = (
        f"fraction_index={load_index}, "
        f"offered_load_fraction={load_fraction}, "
        f"capacity_bytes={capacity_bytes}, "
        f"individual_syncunit_bytes={individual_bytes}, "
        f"generation_duration_seconds={duration_seconds}"
    )
    try:
        workload = base_workload.with_offered_load(
            load_fraction=load_fraction,
            capacity_bytes=capacity_bytes,
        )
    except (ValueError, OverflowError, ValidationError) as error:
        raise ValueError(
            f"no se pudo derivar el conteo o la tasa de la fracción: {context}. {error}"
        ) from error
    event_count = workload.max_events
    rate = workload.rate_events_per_second
    if (
        event_count is None
        or isinstance(event_count, bool)
        or event_count < 1
        or not isfinite(rate)
        or rate <= 0
    ):
        raise ValueError(
            "el conteo o la tasa derivada no es válido: "
            f"{context}, "
            f"event_count={event_count}, "
            f"rate_events_per_second={rate}"
        )
    return workload
