from __future__ import annotations

from dataclasses import dataclass, replace
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
from experiments.offered_load import (
    ReferenceCapacity,
    offered_load_count_and_rate,
    reference_mars_to_relay_capacity,
)
from experiments.scenario_adapter import scenario_from_contact_plan_definition
from experiments.scenario import Scenario
from experiments.spec import ScientificRunSpec
from experiments.workload import Workload

EXPERIMENT_BANK_SCHEMA_VERSION_V2 = 2

E1_BANK_CAMPAIGN_ID = "e1-experiment-bank-v1"
E1_BANK_CAMPAIGN_DESCRIPTION = (
    "E1 configurable resuelto desde el banco experimental v1. "
    "No es el diseño oficial de E1."
)
# Etiquetas científicas conservadas; V2 exige declarar la identidad.
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
# Etiquetas científicas conservadas; V2 exige declarar la identidad.
# Son los literales que el resolver imponía antes de leerlos del documento.
# Entran en el workload materializado. No son los identificadores de Alessi
# ni los de la campaña oficial de carga ofrecida, y no se importan de su builder.
E2_BANK_WORKLOAD_ID = "experiment-bank-e2-v1"
E2_BANK_EVENT_TYPE = "research.tfi.experiment_bank.e2"
E2_BANK_FLOW = "tfi.experiment_bank.e2"
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

    Todos los parámetros científicos e identidades se declaran explícitamente.
    """

    event_count: int = Field(gt=0, strict=True)
    event_interval_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    sender_ack_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    batch_sizes: tuple[StrictInt, ...]
    start_time_sim: float = Field(
        ge=0,
        allow_inf_nan=False,
        strict=True,
    )
    individual_syncunit_bytes: int = Field(
        gt=0,
        strict=True,
    )
    workload_id: str = Field(min_length=1)
    event_type: str = Field()
    flow: str = Field()

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

    Todos los parámetros científicos e identidades se declaran explícitamente.
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
        ge=0,
        allow_inf_nan=False,
        strict=True,
    )
    individual_syncunit_bytes: int = Field(
        gt=0,
        strict=True,
    )
    batch_size_events: int = Field(
        ge=MIN_BATCH_SIZE_EVENTS,
        le=MAX_BATCH_SIZE_EVENTS,
        strict=True,
    )
    capacity_interval_end_sim: float | None = Field(
        allow_inf_nan=False,
        strict=True,
    )
    workload_id: str = Field(min_length=1)
    event_type: str = Field()
    flow: str = Field()

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


class ExperimentBankE3V2(_BankInputModel):
    """Parámetros declarados para E3.

    V2 permite seleccionar E3 junto con otros protocolos.
    ``resolve_e3_campaign`` arma las cuatro celdas en memoria. Este modelo,
    por sí solo, no calcula la tasa ni el último instante de generación, no
    consulta el horizonte ni los contactos, no calibra payloads y no arma
    ``Workload``, ``FailurePlan``, escenario ni campaña.
    La secuencia interna solo exige un vecino anterior y uno posterior:
    no afirma que la pérdida se active, se detecte o se recupere.

    Todos los parámetros científicos e identidades se declaran explícitamente.
    """

    receiver_ack_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)

    event_count: int = Field(ge=3, strict=True)
    event_interval_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    sender_ack_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    gap_request_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    loss_sequence_number: int = Field(ge=1, strict=True)
    start_time_sim: float = Field(
        ge=0,
        allow_inf_nan=False,
        strict=True,
    )
    individual_syncunit_bytes: int = Field(
        gt=0,
        strict=True,
    )
    workload_id: str = Field(min_length=1)
    event_type: str = Field()
    flow: str = Field()

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


class ExperimentBankE3SensitivityV2(_BankInputModel):
    """Parámetros declarados para la sensibilidad de E3.

    Es la misma generación, identidad, tamaño Individual, inicio y timeouts
    de E3, con varias secuencias internas. No es un experimento aparte.
    ``loss_sequence_number`` singular no pertenece a esta sección.
    El hop, el intento, las ocurrencias y la estrategia no se configuran.
    Validar este modelo no arma el plan de fallos ni consulta el horizonte.
    """

    receiver_ack_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)

    event_count: int = Field(ge=3, strict=True)
    event_interval_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    sender_ack_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    gap_request_timeout_seconds: float = Field(gt=0, allow_inf_nan=False, strict=True)
    loss_sequence_numbers: tuple[StrictInt, ...]
    start_time_sim: float = Field(
        ge=0,
        allow_inf_nan=False,
        strict=True,
    )
    individual_syncunit_bytes: int = Field(
        gt=0,
        strict=True,
    )
    workload_id: str = Field(min_length=1)
    event_type: str = Field()
    flow: str = Field()

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


class ExperimentBankExperimentsV2(_BankInputModel):
    """Selección v2. Cada bloque presente es una campaña solicitada."""

    e1: ExperimentBankE1 | None = None
    e2: ExperimentBankE2 | None = None
    e3: ExperimentBankE3V2 | None = None
    e3_sensitivity: ExperimentBankE3SensitivityV2 | None = None

    @model_validator(mode="after")
    def selected_protocols_are_explicit(self) -> Self:
        selected = [
            item
            for item in (
                self.e1,
                self.e2,
                self.e3,
                self.e3_sensitivity,
            )
            if item is not None
        ]
        if not selected:
            raise ValueError("experiments debe declarar al menos un experimento")
        return self


class ExperimentBankDocument(_BankInputModel):
    """Entrada v2 multi-experimento sin presets ni referencias a suites."""

    schema_version: int = Field(strict=True)
    seed: int = Field(strict=True)
    scenario: ExperimentBankScenario
    experiments: ExperimentBankExperimentsV2

    @field_validator("schema_version", "seed", mode="before")
    @classmethod
    def integers_must_not_be_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("los enteros no admiten booleanos")
        return value

    @field_validator("schema_version")
    @classmethod
    def supported_schema_version(cls, value: int) -> int:
        if value != EXPERIMENT_BANK_SCHEMA_VERSION_V2:
            raise ValueError(
                "schema_version no soportada para el banco v2: "
                f"se requiere {EXPERIMENT_BANK_SCHEMA_VERSION_V2}"
            )
        return value


@dataclass(frozen=True, slots=True)
class ResolvedE1Campaign:
    """Resolución inmutable con sus dos documentos de entrada y el spec efectivo."""

    bank_document: ExperimentBankDocument
    contact_plan_definition: ContactPlanDefinition
    campaign: CampaignSpec


def _finite_workload_from_interval(
    *,
    event_interval_seconds: float,
    workload_id: str,
    event_type: str,
    flow: str,
    start_time_sim: float,
    event_count: int,
    individual_syncunit_bytes: int,
) -> Workload:
    """Construye la carga finita común a E1, E3 y su sensibilidad."""
    rate_events_per_second = 1.0 / event_interval_seconds
    if not isfinite(rate_events_per_second) or rate_events_per_second <= 0:
        raise ValueError(
            "la tasa derivada debe ser finita y positiva: "
            f"event_interval_seconds={event_interval_seconds}, "
            f"rate_events_per_second={rate_events_per_second}"
        )
    return Workload(
        workload_id=workload_id,
        event_type=event_type,
        flow=flow,
        priority=TelemetryPriority.NORMAL,
        start_time_sim=start_time_sim,
        duration_seconds=None,
        max_events=event_count,
        rate_events_per_second=rate_events_per_second,
        canonical_individual_syncunit_bytes=individual_syncunit_bytes,
        offered_load_fraction=None,
    )


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
    declarada explícitamente en ``experiments.e1``.
    """
    e1_config = bank_document.experiments.e1
    if e1_config is None:
        raise ValueError("el documento no selecciona experiments.e1")
    scenario_config = bank_document.scenario
    scenario = scenario_from_contact_plan_definition(
        contact_plan_definition,
        scenario_id=scenario_config.id,
        horizon_seconds=scenario_config.horizon_seconds,
        description=scenario_config.description,
        notes=scenario_config.notes,
    )

    workload = _finite_workload_from_interval(
        event_interval_seconds=e1_config.event_interval_seconds,
        workload_id=e1_config.workload_id,
        event_type=e1_config.event_type,
        flow=e1_config.flow,
        start_time_sim=e1_config.start_time_sim,
        event_count=e1_config.event_count,
        individual_syncunit_bytes=e1_config.individual_syncunit_bytes,
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
    La identidad del workload se declara en ``experiments.e2``. No se lee
    del builder oficial.
    """
    e2_config = bank_document.experiments.e2
    if e2_config is None:
        raise ValueError("el documento no selecciona experiments.e2")
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
            e2_config,
            load_index=load_index,
            load_fraction=load_fraction,
            capacity_bytes=capacity.serialized_capacity_bytes,
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
    config: ExperimentBankE2,
    *,
    load_index: int,
    load_fraction: float,
    capacity_bytes: float,
) -> Workload:
    """Carga efectiva de una fracción, con un mensaje que la identifica."""
    individual_bytes = config.individual_syncunit_bytes
    duration_seconds = config.generation_duration_seconds
    context = (
        f"fraction_index={load_index}, "
        f"offered_load_fraction={load_fraction}, "
        f"capacity_bytes={capacity_bytes}, "
        f"individual_syncunit_bytes={individual_bytes}, "
        f"generation_duration_seconds={duration_seconds}"
    )
    try:
        event_count, rate = offered_load_count_and_rate(
            load_fraction=load_fraction,
            capacity_bytes=capacity_bytes,
            canonical_individual_bytes=individual_bytes,
            duration_seconds=duration_seconds,
        )
    except (ValueError, OverflowError, ValidationError) as error:
        raise ValueError(
            f"no se pudo derivar el conteo o la tasa de la fracción: {context}. {error}"
        ) from error
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
    return Workload(
        workload_id=config.workload_id,
        event_type=config.event_type,
        flow=config.flow,
        priority=TelemetryPriority.NORMAL,
        start_time_sim=config.start_time_sim,
        duration_seconds=duration_seconds,
        max_events=event_count,
        rate_events_per_second=rate,
        canonical_individual_syncunit_bytes=individual_bytes,
        offered_load_fraction=load_fraction,
    )


@dataclass(frozen=True, slots=True)
class ResolvedE3Campaign:
    """Resolución E3 inmutable. Conserva las entradas y el spec; no guarda resultados."""

    bank_document: ExperimentBankDocument
    contact_plan_definition: ContactPlanDefinition
    campaign: CampaignSpec


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
    C y D usan el ACK de ``RetryPolicy`` declarado explícitamente. Es
    configuración auxiliar de este protocolo: receiver-driven no programa
    ``ACK_TIMEOUT``. No es el timeout científico del receptor ni el default
    de ``RetryPolicy``.

    Resolver no certifica que la pérdida se active, que el hueco se observe,
    que el retorno alcance, que los controles no reintenten, ni que haya
    recuperación, completitud o convergencia. Un plan vacío o sin retorno
    sigue siendo válido. No se llama a ``e3_result``.
    """
    e3_config = bank_document.experiments.e3
    if e3_config is None:
        raise ValueError("el documento no selecciona experiments.e3")
    scenario_config = bank_document.scenario
    scenario = scenario_from_contact_plan_definition(
        contact_plan_definition,
        scenario_id=scenario_config.id,
        horizon_seconds=scenario_config.horizon_seconds,
        description=scenario_config.description,
        notes=scenario_config.notes,
    )

    workload = _finite_workload_from_interval(
        event_interval_seconds=e3_config.event_interval_seconds,
        workload_id=e3_config.workload_id,
        event_type=e3_config.event_type,
        flow=e3_config.flow,
        start_time_sim=e3_config.start_time_sim,
        event_count=e3_config.event_count,
        individual_syncunit_bytes=e3_config.individual_syncunit_bytes,
    )
    loss = _e3_silent_loss_plan(
        source_id=workload.source_id,
        sequence_number=e3_config.loss_sequence_number,
    )
    sender, receiver = _e3_policy_specs(
        scenario=scenario, workload=workload, seed=bank_document.seed, config=e3_config,
    )
    cell_a = CampaignRunSpec(label="A", spec=sender)
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
            spec=replace(sender, failure_plan=loss),
        ),
        CampaignRunSpec(label="C", spec=receiver),
        CampaignRunSpec(
            label="D",
            spec=replace(receiver, failure_plan=loss),
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


ResolvedCampaign = (
    ResolvedE1Campaign
    | ResolvedE2Campaign
    | ResolvedE3Campaign
    | ResolvedE3SensitivityCampaign
)


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
    del receptor es ``receiver_ack_timeout_seconds`` declarado, separado de
    ``gap_request_timeout_seconds``. La parada y la traza son las del banco E3.

    La etiqueta es ``<secuencia>-<política>``. La identidad de campaña es la
    de este banco, no la cohorte histórica ni RC1.

    El horizonte se comprueba con el calendario real de generación. Resolver
    no exige que la pérdida se active, que el retorno alcance ni que haya
    convergencia. No llama al evaluador histórico.
    """
    config = bank_document.experiments.e3_sensitivity
    if config is None:
        raise ValueError("el documento no selecciona experiments.e3_sensitivity")
    scenario_config = bank_document.scenario
    scenario = scenario_from_contact_plan_definition(
        contact_plan_definition,
        scenario_id=scenario_config.id,
        horizon_seconds=scenario_config.horizon_seconds,
        description=scenario_config.description,
        notes=scenario_config.notes,
    )
    workload = _finite_workload_from_interval(
        event_interval_seconds=config.event_interval_seconds,
        workload_id=config.workload_id,
        event_type=config.event_type,
        flow=config.flow,
        start_time_sim=config.start_time_sim,
        event_count=config.event_count,
        individual_syncunit_bytes=config.individual_syncunit_bytes,
    )
    sender, receiver = _e3_policy_specs(
        scenario=scenario, workload=workload, seed=bank_document.seed, config=config,
    )
    runs: list[CampaignRunSpec] = []
    for sequence in config.loss_sequence_numbers:
        loss = _e3_silent_loss_plan(
            source_id=workload.source_id,
            sequence_number=sequence,
        )
        runs.append(
            CampaignRunSpec(
                label=f"{sequence}-{RecoveryPolicy.SENDER_DRIVEN.value}",
                spec=replace(sender, failure_plan=loss),
            )
        )
        runs.append(
            CampaignRunSpec(
                label=f"{sequence}-{RecoveryPolicy.RECEIVER_DRIVEN.value}",
                spec=replace(receiver, failure_plan=loss),
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


def _e3_policy_specs(
    *,
    scenario: Scenario,
    workload: Workload,
    seed: int,
    config: ExperimentBankE3V2 | ExperimentBankE3SensitivityV2,
) -> tuple[ScientificRunSpec, ScientificRunSpec]:
    """Bases sin pérdida; el resolver conserva etiquetas, controles y parejas.

    ``replace`` cambia solo el plan de fallos y conserva los objetos compartidos.
    El ACK auxiliar del receptor no sustituye al timeout de GapRequest.
    """
    shared = dict(
        scenario=scenario,
        workload=workload,
        seed=seed,
        strategy_type=STRATEGY_TYPE_INDIVIDUAL,
        failure_plan=FailurePlan(),
        stop_policy=StopPolicy.PROFILE_HORIZON_SETTLED,
        trace_level=TraceLevel.SCIENTIFIC,
    )
    return (
        ScientificRunSpec(
            recovery_policy=RecoveryPolicy.SENDER_DRIVEN,
            retry_policy=RetryPolicy(ack_timeout_seconds=config.sender_ack_timeout_seconds),
            **shared,
        ),
        ScientificRunSpec(
            recovery_policy=RecoveryPolicy.RECEIVER_DRIVEN,
            retry_policy=RetryPolicy(ack_timeout_seconds=config.receiver_ack_timeout_seconds),
            gap_request_timeout_seconds=config.gap_request_timeout_seconds,
            **shared,
        ),
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

@dataclass(frozen=True, slots=True)
class ResolvedExperimentBank:
    """Colección ordenada de campañas; no es una suite ni un documento puente."""

    document: ExperimentBankDocument
    entries: tuple[tuple[str, ResolvedCampaign], ...]


def resolve_experiment_bank(
    document: ExperimentBankDocument,
    contact_plan_definition: ContactPlanDefinition,
) -> ResolvedExperimentBank:
    """Resuelve en orden canónico E1, E2, E3 y sensibilidad.

    Sólo incluye bloques presentes. El orden es fijo y no depende del orden
    textual de las claves JSON.
    """
    selected = document.experiments
    entries: list[tuple[str, ResolvedCampaign]] = []
    if selected.e1 is not None:
        entries.append(
            (
                "e1",
                resolve_e1_campaign(
                    document,
                    contact_plan_definition,
                ),
            )
        )
    if selected.e2 is not None:
        entries.append(
            (
                "e2",
                resolve_e2_campaign(
                    document,
                    contact_plan_definition,
                ),
            )
        )
    if selected.e3 is not None:
        entries.append(
            (
                "e3",
                resolve_e3_campaign(
                    document,
                    contact_plan_definition,
                ),
            )
        )
    if selected.e3_sensitivity is not None:
        entries.append(
            (
                "e3_sensitivity",
                resolve_e3_sensitivity_campaign(
                    document,
                    contact_plan_definition,
                ),
            )
        )
    return ResolvedExperimentBank(document=document, entries=tuple(entries))

