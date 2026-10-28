"""Valida la entrada del banco y prepara campañas sin ejecutarlas.

El documento v1 acepta exactamente una sección: ``experiments.e1``,
``experiments.e2``, ``experiments.e3`` o ``experiments.e3_sensitivity``.
La última es sensibilidad de E3, no un cuarto experimento. Cada resolver
exige su sección y no corre el motor. La resolución queda en memoria:
no se carga desde un constructor histórico, no se ejecuta y no se persiste.
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
from core.failure.silent import (
    FORWARD_HOP_RELAY_TO_EARTH,
    SilentForwardDeliveryLossFailure,
    silent_forward_delivery_loss_failure_id,
)
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
_ADMITTED_EXPERIMENT_SECTIONS = frozenset({"e1", "e2", "e3", "e3_sensitivity"})
_EXPERIMENT_SECTION_ORDER = ("e1", "e2", "e3", "e3_sensitivity")
_UNSUPPORTED_EXPERIMENTS = frozenset({"sensitivity"})

E1_BANK_CAMPAIGN_ID = "e1-experiment-bank-v1"
E1_BANK_CAMPAIGN_DESCRIPTION = (
    "E1 configurable resuelto desde el banco experimental v1. "
    "No es el diseño oficial de E1."
)
# Defaults del banco cuando experiments.e1 no declara la identidad.
# Forman parte del workload materializado y, por lo tanto, de sus payloads
# y huellas. No se leen del builder oficial ni atribuyen el banco a Alessi.
E1_BANK_WORKLOAD_ID = "experiment-bank-e1-v1"
E1_BANK_EVENT_TYPE = "research.tfi.experiment_bank.e1"
E1_BANK_FLOW = "tfi.experiment_bank.e1"
E2_BANK_CAMPAIGN_ID = "e2-experiment-bank-v1"
E2_BANK_CAMPAIGN_DESCRIPTION = (
    "E2 configurable resuelto desde el banco experimental v1. "
    "No es el diseño oficial de E2."
)
# Defaults del banco cuando experiments.e2 no declara la identidad.
# Son los literales que el resolver imponía antes de leerlos del documento.
# Entran en el workload materializado. No son los identificadores de Alessi
# ni los de la campaña oficial de carga ofrecida, y no se importan de su builder.
E2_BANK_WORKLOAD_ID = "experiment-bank-e2-v1"
E2_BANK_EVENT_TYPE = "research.tfi.experiment_bank.e2"
E2_BANK_FLOW = "tfi.experiment_bank.e2"
# Defaults explícitos del contrato E3. No se importan del experimento oficial.
E3_BANK_DEFAULT_START_TIME_SIM = 0.0
E3_BANK_DEFAULT_INDIVIDUAL_SYNCUNIT_BYTES = 4096
E3_BANK_WORKLOAD_ID = "experiment-bank-e3-v1"
E3_BANK_EVENT_TYPE = "research.tfi.experiment_bank.e3"
E3_BANK_FLOW = "tfi.experiment_bank.e3"
E3_BANK_CAMPAIGN_ID = "e3-experiment-bank-v1"
E3_BANK_CAMPAIGN_DESCRIPTION = (
    "E3 configurable resuelto desde el banco experimental v1. "
    "No es el diseño oficial de E3."
)
# Identidad propia de la sensibilidad configurable. No es la campaña
# histórica ni la de RC1, y no atribuye el workload a Alessi.
E3_SENSITIVITY_BANK_WORKLOAD_ID = "experiment-bank-e3-sensitivity-v1"
E3_SENSITIVITY_BANK_EVENT_TYPE = "research.tfi.experiment_bank.e3_sensitivity"
E3_SENSITIVITY_BANK_FLOW = "tfi.experiment_bank.e3_sensitivity"
E3_SENSITIVITY_BANK_CAMPAIGN_ID = "e3-sensitivity-experiment-bank-v1"
E3_SENSITIVITY_BANK_CAMPAIGN_DESCRIPTION = (
    "Sensibilidad de E3 configurable resuelta desde el banco experimental v1. "
    "No es el diseño oficial de sensibilidad ni un experimento E4."
)
# ACK de RetryPolicy en las celdas receiver-driven C y D.
# Receiver-driven no programa ACK_TIMEOUT. Este valor es configuración
# auxiliar del protocolo inicial: no es gap_request_timeout_seconds y no
# se toma del default de RetryPolicy, que podría cambiar.
E3_BANK_RECEIVER_RETRY_ACK_TIMEOUT_SECONDS = 600.0
E3_BANK_LOSS_ATTEMPT = 1
E3_BANK_LOSS_MAX_OCCURRENCES = 1

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
    """Parámetros declarados para E1, todavía sin resolver a corridas.

    ``workload_id``, ``event_type`` y ``flow`` pueden omitirse. El default
    es el de este banco. No hay otro bloque ni un modo particular para
    reemplazarlos.
    """

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
    workload_id: str = Field(default=E1_BANK_WORKLOAD_ID, min_length=1)
    event_type: str = Field(default=E1_BANK_EVENT_TYPE)
    flow: str = Field(default=E1_BANK_FLOW)

    @field_validator("workload_id", "event_type", "flow")
    @classmethod
    def identity_labels_follow_workload(cls, value: str) -> str:
        """Rechaza vacío, como Workload, y devuelve el texto sin recortarlo."""
        return Workload.must_not_be_blank(value)

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

    ``workload_id``, ``event_type`` y ``flow`` pueden omitirse. El default
    es el de este banco. No hay otro bloque ni un modo particular para
    reemplazarlos.
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
    workload_id: str = Field(default=E2_BANK_WORKLOAD_ID, min_length=1)
    event_type: str = Field(default=E2_BANK_EVENT_TYPE)
    flow: str = Field(default=E2_BANK_FLOW)

    @field_validator("workload_id", "event_type", "flow")
    @classmethod
    def identity_labels_follow_workload(cls, value: str) -> str:
        """Rechaza vacío, como Workload, y devuelve el texto sin recortarlo."""
        return Workload.must_not_be_blank(value)

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


class ExperimentBankE3(_BankInputModel):
    """Parámetros declarados para E3.

    El documento v1 admite ``experiments.e3`` como única sección.
    ``resolve_e3_campaign`` arma las cuatro celdas en memoria. Este modelo,
    por sí solo, no calcula la tasa ni el último instante de generación, no
    consulta el horizonte ni los contactos, no calibra payloads y no arma
    ``Workload``, ``FailurePlan``, escenario ni campaña.
    La secuencia interna solo exige un vecino anterior y uno posterior:
    no afirma que la pérdida se active, se detecte o se recupere.

    ``workload_id``, ``event_type`` y ``flow`` pueden omitirse. El default
    es el de este banco. No se importa del builder oficial ni atribuye la
    corrida a Alessi.
    """

    event_count: int = Field(ge=3, strict=True)
    event_interval_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    sender_ack_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    gap_request_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    loss_sequence_number: int = Field(ge=1, strict=True)
    start_time_sim: float = Field(
        default=E3_BANK_DEFAULT_START_TIME_SIM,
        ge=0,
        allow_inf_nan=False,
        strict=True,
    )
    individual_syncunit_bytes: int = Field(
        default=E3_BANK_DEFAULT_INDIVIDUAL_SYNCUNIT_BYTES,
        gt=0,
        strict=True,
    )
    workload_id: str = Field(default=E3_BANK_WORKLOAD_ID, min_length=1)
    event_type: str = Field(default=E3_BANK_EVENT_TYPE)
    flow: str = Field(default=E3_BANK_FLOW)

    @field_validator("workload_id", "event_type", "flow")
    @classmethod
    def identity_labels_follow_workload(cls, value: str) -> str:
        """Rechaza vacío, como Workload, y devuelve el texto sin recortarlo."""
        return Workload.must_not_be_blank(value)

    @field_validator(
        "event_count",
        "event_interval_seconds",
        "sender_ack_timeout_seconds",
        "gap_request_timeout_seconds",
        "loss_sequence_number",
        "start_time_sim",
        "individual_syncunit_bytes",
        mode="before",
    )
    @classmethod
    def numeric_fields_must_not_be_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("los campos numéricos no admiten booleanos")
        return value

    @model_validator(mode="after")
    def loss_sequence_stays_internal(self) -> Self:
        """Exige vecino anterior y posterior dentro del conteo declarado."""
        upper = self.event_count - 2
        if self.loss_sequence_number > upper:
            raise ValueError(
                "loss_sequence_number debe estar entre 1 y "
                f"event_count - 2 ({upper}), inclusive"
            )
        return self


class ExperimentBankE3Sensitivity(_BankInputModel):
    """Parámetros declarados para la sensibilidad de E3.

    Es la misma generación, identidad, tamaño Individual, inicio y timeouts
    de E3, con varias secuencias internas. No es un experimento aparte.
    ``loss_sequence_number`` singular no pertenece a esta sección.
    El hop, el intento, las ocurrencias y la estrategia no se configuran.
    Validar este modelo no arma el plan de fallos ni consulta el horizonte.
    """

    event_count: int = Field(ge=3, strict=True)
    event_interval_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    sender_ack_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    gap_request_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    loss_sequence_numbers: tuple[StrictInt, ...]
    start_time_sim: float = Field(
        default=E3_BANK_DEFAULT_START_TIME_SIM,
        ge=0,
        allow_inf_nan=False,
        strict=True,
    )
    individual_syncunit_bytes: int = Field(
        default=E3_BANK_DEFAULT_INDIVIDUAL_SYNCUNIT_BYTES,
        gt=0,
        strict=True,
    )
    workload_id: str = Field(default=E3_SENSITIVITY_BANK_WORKLOAD_ID, min_length=1)
    event_type: str = Field(default=E3_SENSITIVITY_BANK_EVENT_TYPE)
    flow: str = Field(default=E3_SENSITIVITY_BANK_FLOW)

    @field_validator("workload_id", "event_type", "flow")
    @classmethod
    def identity_labels_follow_workload(cls, value: str) -> str:
        """Rechaza vacío, como Workload, y devuelve el texto sin recortarlo."""
        return Workload.must_not_be_blank(value)

    @field_validator(
        "event_count",
        "event_interval_seconds",
        "sender_ack_timeout_seconds",
        "gap_request_timeout_seconds",
        "start_time_sim",
        "individual_syncunit_bytes",
        mode="before",
    )
    @classmethod
    def numeric_fields_must_not_be_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("los campos numéricos no admiten booleanos")
        return value

    @field_validator("loss_sequence_numbers", mode="before")
    @classmethod
    def sequences_are_an_ordered_collection(cls, value: Any) -> Any:
        """Conserva el orden declarado. No acepta un entero suelto ni un conjunto."""
        if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
            raise ValueError("loss_sequence_numbers debe ser una colección ordenada")
        if len(value) == 0:
            raise ValueError("loss_sequence_numbers no debe estar vacío")
        seen: list[Any] = []
        for item in value:
            if isinstance(item, bool):
                raise ValueError("los campos numéricos no admiten booleanos")
            if item in seen:
                raise ValueError("loss_sequence_numbers no admite duplicados")
            seen.append(item)
        return value

    @model_validator(mode="after")
    def sequences_stay_internal(self) -> Self:
        """Cada secuencia necesita un vecino anterior y uno posterior."""
        upper = self.event_count - 2
        for number in self.loss_sequence_numbers:
            if number < 1 or number > upper:
                raise ValueError(
                    "cada secuencia debe estar entre 1 y "
                    f"event_count - 2 ({upper}), inclusive"
                )
        return self


class ExperimentBankExperiments(_BankInputModel):
    """Sección E1 del documento. No incluye ni serializa E2."""

    e1: ExperimentBankE1


class ExperimentBankE2Section(_BankInputModel):
    """Sección E2 del documento. No es una campaña resuelta ni ejecutable."""

    e2: ExperimentBankE2


class ExperimentBankE3Section(_BankInputModel):
    """Sección E3 del documento. Validarla no resuelve ni ejecuta la campaña."""

    e3: ExperimentBankE3


class ExperimentBankE3SensitivitySection(_BankInputModel):
    """Sección de sensibilidad de E3. Validarla no resuelve ni ejecuta."""

    e3_sensitivity: ExperimentBankE3Sensitivity


class ExperimentBankDocument(_BankInputModel):
    """Documento validado, no una configuración efectiva de ejecución.

    Contiene exactamente una sección: E1, E2, E3 o sensibilidad de E3.
    Validar el documento no abre el plan ni ejecuta la campaña.
    """

    schema_version: int = Field(strict=True)
    seed: int = Field(default=EXPERIMENT_BANK_DEFAULT_SEED, strict=True)
    scenario: ExperimentBankScenario
    experiments: (
        ExperimentBankExperiments
        | ExperimentBankE2Section
        | ExperimentBankE3Section
        | ExperimentBankE3SensitivitySection
    )

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
        if isinstance(
            value,
            (
                ExperimentBankExperiments,
                ExperimentBankE2Section,
                ExperimentBankE3Section,
                ExperimentBankE3SensitivitySection,
            ),
        ):
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
        selected = [name for name in _EXPERIMENT_SECTION_ORDER if name in value]
        if len(selected) == 0:
            raise ValueError(
                "el documento debe incluir exactamente una sección: "
                "experiments.e1, experiments.e2, experiments.e3 "
                "o experiments.e3_sensitivity"
            )
        if len(selected) > 1:
            names = " y ".join(f"experiments.{name}" for name in selected)
            raise ValueError(f"{names} no pueden estar presentes a la vez")
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
    """Devuelve la sección E1 o rechaza un documento que selecciona E2 o E3."""
    experiments = bank_document.experiments
    if isinstance(experiments, ExperimentBankE2Section):
        raise ValueError(
            "el documento selecciona experiments.e2; "
            "resolve_e1_campaign solo acepta experiments.e1 "
            "y no construye ni ejecuta una campaña E2"
        )
    if isinstance(experiments, ExperimentBankE3Section):
        raise ValueError(
            "el documento selecciona experiments.e3; "
            "resolve_e1_campaign solo acepta experiments.e1 "
            "y no construye ni ejecuta una campaña E3"
        )
    if isinstance(experiments, ExperimentBankE3SensitivitySection):
        raise ValueError(
            "el documento selecciona experiments.e3_sensitivity; "
            "resolve_e1_campaign solo acepta experiments.e1 "
            "y no construye ni ejecuta una sensibilidad de E3"
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
    construir el escenario o la campaña. Un documento que selecciona E3
    se rechaza del mismo modo, antes de construir el escenario, e
    identifica la sección E3. La identidad del workload es la
    declarada en ``experiments.e1`` o, si falta, la de este banco.
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
        workload_id=e1_config.workload_id,
        event_type=e1_config.event_type,
        flow=e1_config.flow,
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
    """Devuelve la sección E2 o rechaza un documento que selecciona E1 o E3."""
    experiments = bank_document.experiments
    if isinstance(experiments, ExperimentBankExperiments):
        raise ValueError(
            "el documento selecciona experiments.e1; "
            "resolve_e2_campaign solo acepta experiments.e2 "
            "y no construye ni ejecuta una campaña E1"
        )
    if isinstance(experiments, ExperimentBankE3Section):
        raise ValueError(
            "el documento selecciona experiments.e3; "
            "resolve_e2_campaign solo acepta experiments.e2 "
            "y no construye ni ejecuta una campaña E3"
        )
    if isinstance(experiments, ExperimentBankE3SensitivitySection):
        raise ValueError(
            "el documento selecciona experiments.e3_sensitivity; "
            "resolve_e2_campaign solo acepta experiments.e2 "
            "y no construye ni ejecuta una sensibilidad de E3"
        )
    if isinstance(experiments, ExperimentBankE2Section):
        return experiments.e2
    raise ValueError("el documento no selecciona experiments.e2")


def resolve_e2_campaign(
    bank_document: ExperimentBankDocument,
    contact_plan_definition: ContactPlanDefinition,
) -> ResolvedE2Campaign:
    """Convierte una entrada E2 validada en una campaña, sin ejecutarla.

    Rechaza un documento E1 antes de construir el escenario. Un documento
    E3 también se rechaza antes de construir el escenario e identifica
    la sección E3. Los contactos del escenario son los del plan recibido,
    sin recorte: el intervalo solo entra en el cálculo de capacidad.

    El fin de capacidad es ``capacity_interval_end_sim`` cuando está
    definido y, si no, el horizonte del escenario. La capacidad es la suma
    nominal de bytes serializables Marte → relé que solapan ese intervalo.
    No es capacidad extremo a extremo, utilización realizada ni una garantía
    de entrega. No exige convergencia, retorno suficiente ni ausencia de
    retries, y no usa el fin del último contacto del E2 oficial.
    La identidad del workload es la declarada en ``experiments.e2`` o, si
    falta, la de este banco. No se lee del builder oficial.
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
        workload_id=e2_config.workload_id,
        event_type=e2_config.event_type,
        flow=e2_config.flow,
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


@dataclass(frozen=True, slots=True)
class ResolvedE3Campaign:
    """Resolución E3 inmutable. Conserva las entradas y el spec; no guarda resultados."""

    bank_document: ExperimentBankDocument
    contact_plan_definition: ContactPlanDefinition
    campaign: CampaignSpec


def require_e3_bank_selection(
    bank_document: ExperimentBankDocument,
) -> ExperimentBankE3:
    """Devuelve la sección E3 o rechaza un documento que selecciona E1 o E2."""
    experiments = bank_document.experiments
    if isinstance(experiments, ExperimentBankExperiments):
        raise ValueError(
            "el documento selecciona experiments.e1; "
            "resolve_e3_campaign solo acepta experiments.e3 "
            "y no construye ni ejecuta una campaña E1"
        )
    if isinstance(experiments, ExperimentBankE2Section):
        raise ValueError(
            "el documento selecciona experiments.e2; "
            "resolve_e3_campaign solo acepta experiments.e3 "
            "y no construye ni ejecuta una campaña E2"
        )
    if isinstance(experiments, ExperimentBankE3SensitivitySection):
        raise ValueError(
            "el documento selecciona experiments.e3_sensitivity; "
            "resolve_e3_campaign solo acepta experiments.e3 "
            "y no construye ni ejecuta una sensibilidad de E3"
        )
    if isinstance(experiments, ExperimentBankE3Section):
        return experiments.e3
    raise ValueError("el documento no selecciona experiments.e3")


def resolve_e3_campaign(
    bank_document: ExperimentBankDocument,
    contact_plan_definition: ContactPlanDefinition,
) -> ResolvedE3Campaign:
    """Convierte en memoria una entrada E3 validada en cuatro celdas, sin ejecutarlas.

    ``contact_plan_file`` queda solo en ``bank_document``. Esta función no
    abre ese archivo ni presume el origen de la definición recibida. Los
    contactos pasan al escenario por ``scenario_from_contact_plan_definition``:
    no se recortan ni se inventa el enlace inverso.

    Un documento E1 o E2 se rechaza con ValueError antes de construir el
    escenario. La tasa es ``1 / event_interval_seconds`` y tiene que ser
    finita y positiva. El último evento se lee con el mismo perfil de
    generación que E1: ``start_time_sim + n / tasa``. No se usa el producto
    por el intervalo, que puede diferir por redondeo, y no se materializa
    el dataset. Un instante derivado no finito, o posterior al horizonte,
    se rechaza. Igualar el horizonte se acepta.

    Las cuatro corridas comparten escenario, workload y semilla, en el orden
    A, B, C, D. A y C no tienen fallos. B y D comparten una pérdida silenciosa
    de la secuencia declarada, intento 1, hop relé → Tierra y una ocurrencia.
    C y D fijan el ACK de ``RetryPolicy`` en
    ``E3_BANK_RECEIVER_RETRY_ACK_TIMEOUT_SECONDS`` (600 s). Ese número es
    configuración auxiliar de este protocolo: receiver-driven no programa
    ``ACK_TIMEOUT``. No es el timeout científico del receptor ni el default
    de ``RetryPolicy``.

    Resolver no certifica que la pérdida se active, que el hueco se observe,
    que el retorno alcance, que los controles no reintenten, ni que haya
    recuperación, completitud o convergencia. Un plan vacío o sin retorno
    sigue siendo válido. No se llama a ``e3_result``.
    """
    e3_config = require_e3_bank_selection(bank_document)
    scenario_config = bank_document.scenario
    scenario = scenario_from_contact_plan_definition(
        contact_plan_definition,
        scenario_id=scenario_config.id,
        horizon_seconds=scenario_config.horizon_seconds,
        description=scenario_config.description,
        notes=scenario_config.notes,
    )

    rate_events_per_second = 1.0 / e3_config.event_interval_seconds
    if not isfinite(rate_events_per_second) or rate_events_per_second <= 0:
        raise ValueError(
            "la tasa derivada debe ser finita y positiva: "
            f"event_interval_seconds={e3_config.event_interval_seconds}, "
            f"rate_events_per_second={rate_events_per_second}"
        )

    workload = Workload(
        workload_id=e3_config.workload_id,
        event_type=e3_config.event_type,
        flow=e3_config.flow,
        priority=TelemetryPriority.NORMAL,
        start_time_sim=e3_config.start_time_sim,
        duration_seconds=None,
        max_events=e3_config.event_count,
        rate_events_per_second=rate_events_per_second,
        canonical_individual_syncunit_bytes=e3_config.individual_syncunit_bytes,
        offered_load_fraction=None,
    )
    quiet = FailurePlan()
    loss = _e3_silent_loss_plan(
        source_id=workload.source_id,
        sequence_number=e3_config.loss_sequence_number,
    )
    sender_retry = RetryPolicy(
        ack_timeout_seconds=e3_config.sender_ack_timeout_seconds
    )
    receiver_retry = RetryPolicy(
        ack_timeout_seconds=E3_BANK_RECEIVER_RETRY_ACK_TIMEOUT_SECONDS
    )
    shared_run_parameters = {
        "scenario": scenario,
        "workload": workload,
        "seed": bank_document.seed,
        "stop_policy": StopPolicy.PROFILE_HORIZON_SETTLED,
        "trace_level": TraceLevel.SCIENTIFIC,
    }
    cell_a = CampaignRunSpec(
        label="A",
        spec=ScientificRunSpec(
            strategy_type=STRATEGY_TYPE_INDIVIDUAL,
            recovery_policy=RecoveryPolicy.SENDER_DRIVEN,
            retry_policy=sender_retry,
            failure_plan=quiet,
            **shared_run_parameters,
        ),
    )
    _require_e3_last_event_inside_horizon(
        event_count=e3_config.event_count,
        event_interval_seconds=e3_config.event_interval_seconds,
        start_time_sim=e3_config.start_time_sim,
        workload=workload,
        dataset_identity=cell_a.spec.dataset_identity,
        horizon_seconds=scenario_config.horizon_seconds,
    )
    runs = (
        cell_a,
        CampaignRunSpec(
            label="B",
            spec=ScientificRunSpec(
                strategy_type=STRATEGY_TYPE_INDIVIDUAL,
                recovery_policy=RecoveryPolicy.SENDER_DRIVEN,
                retry_policy=sender_retry,
                failure_plan=loss,
                **shared_run_parameters,
            ),
        ),
        CampaignRunSpec(
            label="C",
            spec=ScientificRunSpec(
                strategy_type=STRATEGY_TYPE_INDIVIDUAL,
                recovery_policy=RecoveryPolicy.RECEIVER_DRIVEN,
                retry_policy=receiver_retry,
                failure_plan=quiet,
                gap_request_timeout_seconds=e3_config.gap_request_timeout_seconds,
                **shared_run_parameters,
            ),
        ),
        CampaignRunSpec(
            label="D",
            spec=ScientificRunSpec(
                strategy_type=STRATEGY_TYPE_INDIVIDUAL,
                recovery_policy=RecoveryPolicy.RECEIVER_DRIVEN,
                retry_policy=receiver_retry,
                failure_plan=loss,
                gap_request_timeout_seconds=e3_config.gap_request_timeout_seconds,
                **shared_run_parameters,
            ),
        ),
    )
    campaign = CampaignSpec(
        campaign_id=E3_BANK_CAMPAIGN_ID,
        description=E3_BANK_CAMPAIGN_DESCRIPTION,
        runs=runs,
    )
    return ResolvedE3Campaign(
        bank_document=bank_document,
        contact_plan_definition=contact_plan_definition,
        campaign=campaign,
    )


@dataclass(frozen=True, slots=True)
class ResolvedE3SensitivityCampaign:
    """Resolución de sensibilidad E3. Conserva las entradas y el spec."""

    bank_document: ExperimentBankDocument
    contact_plan_definition: ContactPlanDefinition
    campaign: CampaignSpec


def require_e3_sensitivity_bank_selection(
    bank_document: ExperimentBankDocument,
) -> ExperimentBankE3Sensitivity:
    """Devuelve la sección de sensibilidad o rechaza E1, E2 o E3."""
    experiments = bank_document.experiments
    if isinstance(experiments, ExperimentBankExperiments):
        raise ValueError(
            "el documento selecciona experiments.e1; "
            "resolve_e3_sensitivity_campaign solo acepta "
            "experiments.e3_sensitivity "
            "y no construye ni ejecuta una campaña E1"
        )
    if isinstance(experiments, ExperimentBankE2Section):
        raise ValueError(
            "el documento selecciona experiments.e2; "
            "resolve_e3_sensitivity_campaign solo acepta "
            "experiments.e3_sensitivity "
            "y no construye ni ejecuta una campaña E2"
        )
    if isinstance(experiments, ExperimentBankE3Section):
        raise ValueError(
            "el documento selecciona experiments.e3; "
            "resolve_e3_sensitivity_campaign solo acepta "
            "experiments.e3_sensitivity "
            "y no construye ni ejecuta una campaña E3"
        )
    if isinstance(experiments, ExperimentBankE3SensitivitySection):
        return experiments.e3_sensitivity
    raise ValueError("el documento no selecciona experiments.e3_sensitivity")


def resolve_e3_sensitivity_campaign(
    bank_document: ExperimentBankDocument,
    contact_plan_definition: ContactPlanDefinition,
) -> ResolvedE3SensitivityCampaign:
    """Arma una pareja sender/receiver por cada secuencia, sin ejecutarla.

    El orden es el declarado: para cada secuencia, primero sender-driven y
    después receiver-driven. No hay controles sin pérdida. Las dos corridas
    de una pareja comparten el mismo ``FailurePlan``. Todas comparten
    escenario, workload y semilla.

    La pérdida sigue el protocolo de E3: entrega silenciosa relé → Tierra,
    intento 1 y una ocurrencia. La estrategia es Individual. El ACK auxiliar
    del receptor es ``E3_BANK_RECEIVER_RETRY_ACK_TIMEOUT_SECONDS``. La parada
    y la traza son las del banco E3.

    La etiqueta es ``<secuencia>-<política>``. La identidad de campaña es la
    de este banco, no la cohorte histórica ni RC1.

    El horizonte se comprueba con el calendario real de generación. Resolver
    no exige que la pérdida se active, que el retorno alcance ni que haya
    convergencia. No llama al evaluador histórico.
    """
    config = require_e3_sensitivity_bank_selection(bank_document)
    scenario_config = bank_document.scenario
    scenario = scenario_from_contact_plan_definition(
        contact_plan_definition,
        scenario_id=scenario_config.id,
        horizon_seconds=scenario_config.horizon_seconds,
        description=scenario_config.description,
        notes=scenario_config.notes,
    )
    rate_events_per_second = 1.0 / config.event_interval_seconds
    if not isfinite(rate_events_per_second) or rate_events_per_second <= 0:
        raise ValueError(
            "la tasa derivada debe ser finita y positiva: "
            f"event_interval_seconds={config.event_interval_seconds}, "
            f"rate_events_per_second={rate_events_per_second}"
        )
    workload = Workload(
        workload_id=config.workload_id,
        event_type=config.event_type,
        flow=config.flow,
        priority=TelemetryPriority.NORMAL,
        start_time_sim=config.start_time_sim,
        duration_seconds=None,
        max_events=config.event_count,
        rate_events_per_second=rate_events_per_second,
        canonical_individual_syncunit_bytes=config.individual_syncunit_bytes,
        offered_load_fraction=None,
    )
    sender_retry = RetryPolicy(ack_timeout_seconds=config.sender_ack_timeout_seconds)
    receiver_retry = RetryPolicy(
        ack_timeout_seconds=E3_BANK_RECEIVER_RETRY_ACK_TIMEOUT_SECONDS
    )
    shared_run_parameters = {
        "scenario": scenario,
        "workload": workload,
        "seed": bank_document.seed,
        "stop_policy": StopPolicy.PROFILE_HORIZON_SETTLED,
        "trace_level": TraceLevel.SCIENTIFIC,
    }
    runs: list[CampaignRunSpec] = []
    for sequence in config.loss_sequence_numbers:
        loss = _e3_silent_loss_plan(
            source_id=workload.source_id,
            sequence_number=sequence,
        )
        runs.append(
            CampaignRunSpec(
                label=f"{sequence}-{RecoveryPolicy.SENDER_DRIVEN.value}",
                spec=ScientificRunSpec(
                    strategy_type=STRATEGY_TYPE_INDIVIDUAL,
                    recovery_policy=RecoveryPolicy.SENDER_DRIVEN,
                    retry_policy=sender_retry,
                    failure_plan=loss,
                    **shared_run_parameters,
                ),
            )
        )
        runs.append(
            CampaignRunSpec(
                label=f"{sequence}-{RecoveryPolicy.RECEIVER_DRIVEN.value}",
                spec=ScientificRunSpec(
                    strategy_type=STRATEGY_TYPE_INDIVIDUAL,
                    recovery_policy=RecoveryPolicy.RECEIVER_DRIVEN,
                    retry_policy=receiver_retry,
                    failure_plan=loss,
                    gap_request_timeout_seconds=config.gap_request_timeout_seconds,
                    **shared_run_parameters,
                ),
            )
        )
    _require_e3_last_event_inside_horizon(
        event_count=config.event_count,
        event_interval_seconds=config.event_interval_seconds,
        start_time_sim=config.start_time_sim,
        workload=workload,
        dataset_identity=runs[0].spec.dataset_identity,
        horizon_seconds=scenario_config.horizon_seconds,
    )
    campaign = CampaignSpec(
        campaign_id=E3_SENSITIVITY_BANK_CAMPAIGN_ID,
        description=E3_SENSITIVITY_BANK_CAMPAIGN_DESCRIPTION,
        runs=tuple(runs),
    )
    return ResolvedE3SensitivityCampaign(
        bank_document=bank_document,
        contact_plan_definition=contact_plan_definition,
        campaign=campaign,
    )


def _e3_silent_loss_plan(
    *,
    source_id: str,
    sequence_number: int,
) -> FailurePlan:
    """Una pérdida silenciosa de la entrega original en relé → Tierra.

    El ``failure_id`` lo calcula el helper existente. La secuencia es la
    declarada en el documento: no se sustituye por el punto medio del conteo.
    El intento y las ocurrencias van explícitos; no se dejan en un default.
    """
    attempt = E3_BANK_LOSS_ATTEMPT
    hop = FORWARD_HOP_RELAY_TO_EARTH
    return FailurePlan(
        silent_forward_delivery_losses=(
            SilentForwardDeliveryLossFailure(
                failure_id=silent_forward_delivery_loss_failure_id(
                    source_id,
                    sequence_number,
                    attempt,
                    hop,
                ),
                source_id=source_id,
                sequence_number=sequence_number,
                telemetry_attempt_number=attempt,
                hop=hop,
                max_occurrences=E3_BANK_LOSS_MAX_OCCURRENCES,
            ),
        )
    )


def _require_e3_last_event_inside_horizon(
    *,
    event_count: int,
    event_interval_seconds: float,
    start_time_sim: float,
    workload: Workload,
    dataset_identity: str,
    horizon_seconds: float,
) -> None:
    """Rechaza un último evento no finito o posterior al horizonte.

    El instante sale de ``TelemetryGenerationProfile.last_generation_at_sim``,
    la misma lectura que usa el resolver E1. Ese método programa el índice
    ``n`` en ``start_time_sim + n / rate``. No recorre el dataset.
    E3 y su sensibilidad usan esta comprobación. No es una jerarquía de
    experimentos.
    """
    generation_profile = workload.generation_profile(dataset_identity=dataset_identity)
    try:
        last_generation_at_sim = generation_profile.last_generation_at_sim()
    except OverflowError as error:
        raise ValueError(
            "el instante derivado del último evento desbordó: "
            f"event_count={event_count}, "
            f"event_interval_seconds={event_interval_seconds}, "
            f"start_time_sim={start_time_sim}, "
            f"rate_events_per_second={workload.rate_events_per_second}"
        ) from error
    if last_generation_at_sim is None or not isfinite(last_generation_at_sim):
        raise ValueError(
            "el instante derivado del último evento no es finito: "
            f"event_count={event_count}, "
            f"event_interval_seconds={event_interval_seconds}, "
            f"start_time_sim={start_time_sim}, "
            f"rate_events_per_second={workload.rate_events_per_second}, "
            f"last_generation_at_sim={last_generation_at_sim}"
        )
    if last_generation_at_sim > horizon_seconds:
        raise ValueError(
            "el último evento queda después del horizonte: "
            f"event_count={event_count}, "
            f"event_interval_seconds={event_interval_seconds}, "
            f"start_time_sim={start_time_sim}, "
            f"last_generation_at_sim={last_generation_at_sim}, "
            f"horizon_seconds={horizon_seconds}"
        )
