"""Campaña: colección ordenada de corridas científicas ya especificadas.

No abre otro motor, no arma una grilla y no sortea semillas. Recorre
``runs`` en el orden declarado y delega cada una en
``execute_scientific_run``. Cada corrida arma su propio stack.

La identidad de la campaña es un UUID versión 5 de su definición. No es
un UUID aleatorio y no reescribe ``dataset_identity``,
``experiment_identity`` ni ``execution_identity`` de las corridas.

Si una corrida lanza ``Exception``, el resultado guarda el error, no
reintenta esa corrida y sigue con la siguiente. Las que ya terminaron
permanecen. ``KeyboardInterrupt`` y ``SystemExit`` se propagan.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from core.stopping.policy import StopPolicy
from core.sync.strategy import STRATEGY_TYPE_FIXED_BATCH, STRATEGY_TYPE_INDIVIDUAL
from core.trace.level import TraceLevel

from experiments.controlled import (
    CONTROLLED_LOCAL_SEED,
    controlled_local_scenario,
    controlled_local_workload,
)
from experiments.execute import execute_scientific_run
from experiments.result import ScientificRunResult
from experiments.spec import ScientificRunSpec

CAMPAIGN_COMPLETED = "COMPLETED"
CAMPAIGN_COMPLETED_WITH_FAILURES = "COMPLETED_WITH_FAILURES"

CONTROLLED_DEVELOPMENT_CAMPAIGN_ID = "controlled-campaign-v1"
CONTROLLED_DEVELOPMENT_BATCH_SIZE = 2

_CAMPAIGN_IDENTITY_NAMESPACE = uuid5(
    NAMESPACE_URL, "https://tfi.local/dtn-mars-earth-lab/campaign-identity"
)


@dataclass(frozen=True, slots=True)
class CampaignRunSpec:
    """Una corrida dentro de la campaña, con el rótulo que la distingue.

    ``label`` es texto de la definición. La infraestructura no interpreta
    tratamientos. ``spec`` es la corrida científica completa.
    """

    label: str
    spec: ScientificRunSpec

    def __post_init__(self) -> None:
        if not isinstance(self.label, str):
            raise ValueError("label debe ser un texto")
        label = self.label.strip()
        if label == "":
            raise ValueError("label no debe estar vacío")
        object.__setattr__(self, "label", label)
        if not isinstance(self.spec, ScientificRunSpec):
            raise ValueError("spec debe ser una ScientificRunSpec")


@dataclass(frozen=True, slots=True)
class CampaignSpec:
    """Definición inmutable. No guarda resultados ni métricas.

    ``runs`` es la secuencia de ejecución. La posición 0 es la primera
    corrida. El orden es el de esa secuencia: no hay conjunto, sorteo
    ni ejecución concurrente.
    """

    campaign_id: str
    description: str
    runs: tuple[CampaignRunSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.campaign_id, str):
            raise ValueError("campaign_id debe ser un texto")
        campaign_id = self.campaign_id.strip()
        if campaign_id == "":
            raise ValueError("campaign_id no debe estar vacío")
        if not isinstance(self.description, str):
            raise ValueError("description debe ser un texto")
        description = self.description.strip()
        if description == "":
            raise ValueError("description no debe estar vacía")
        runs = self.runs
        if isinstance(runs, (set, frozenset)):
            raise ValueError("el orden de las corridas debe ser una secuencia explícita")
        if isinstance(runs, (str, bytes)) or not isinstance(runs, Sequence):
            raise ValueError("runs debe ser una secuencia ordenada")
        ordered = tuple(runs)
        if not ordered:
            raise ValueError("una campaña requiere al menos una corrida")
        vistos: list[str] = []
        for run in ordered:
            if not isinstance(run, CampaignRunSpec):
                raise ValueError("cada corrida debe ser un CampaignRunSpec")
            if run.label in vistos:
                raise ValueError("los label de una campaña deben ser únicos")
            vistos.append(run.label)
        object.__setattr__(self, "campaign_id", campaign_id)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "runs", ordered)

    @property
    def campaign_identity(self) -> str:
        """UUID versión 5 de ``campaign_id``, la descripción y las corridas en orden."""
        return str(uuid5(_CAMPAIGN_IDENTITY_NAMESPACE, _canonical_campaign_json(self)))


@dataclass(frozen=True, slots=True)
class CampaignRunResult:
    """Posición, rótulo y salida de una corrida ya intentada.

    ``index`` es la posición en la campaña, desde 0. Una corrida
    terminada trae ``result``. Una que lanzó trae ``error_type`` y
    ``error_message``, y ``result`` queda en ``None``.
    """

    index: int
    label: str
    result: ScientificRunResult | None
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise ValueError("index debe ser un entero mayor o igual que 0")
        if not isinstance(self.label, str) or self.label.strip() == "":
            raise ValueError("label no debe estar vacío")
        terminada = self.result is not None
        fallo = self.error_type is not None
        if terminada == fallo:
            raise ValueError("una corrida tiene resultado o error, no ambos ni ninguno")
        if terminada and self.error_message is not None:
            raise ValueError("una corrida terminada no lleva mensaje de error")
        if fallo and self.error_message is None:
            raise ValueError("una corrida fallida requiere error_message")

    @property
    def completed(self) -> bool:
        return self.result is not None


@dataclass(frozen=True, slots=True)
class CampaignResult:
    """Salida de ``execute_campaign``. Las corridas siguen el orden de la spec.

    Los conteos son el tamaño de la campaña y cuántas corridas devolvieron
    resultado. No hay medias, rankings ni comparación entre rótulos.
    """

    campaign_id: str
    description: str
    campaign_identity: str
    runs: tuple[CampaignRunResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.runs, tuple):
            object.__setattr__(self, "runs", tuple(self.runs))
        for expected, run in enumerate(self.runs):
            if not isinstance(run, CampaignRunResult):
                raise ValueError("cada resultado debe ser un CampaignRunResult")
            if run.index != expected:
                raise ValueError("las corridas del resultado deben seguir el orden declarado")
        identity = self.campaign_identity
        if not isinstance(identity, str) or identity.strip() == "":
            raise ValueError("campaign_identity no debe estar vacía")
        parsed = UUID(identity)
        if parsed.version != 5:
            raise ValueError("campaign_identity debe ser un UUID versión 5")

    @property
    def run_count(self) -> int:
        return len(self.runs)

    @property
    def completed_count(self) -> int:
        return sum(1 for run in self.runs if run.completed)

    @property
    def failed_count(self) -> int:
        return self.run_count - self.completed_count

    @property
    def status(self) -> str:
        """``COMPLETED`` si todas terminaron. Si alguna falló, ``COMPLETED_WITH_FAILURES``."""
        if self.failed_count:
            return CAMPAIGN_COMPLETED_WITH_FAILURES
        return CAMPAIGN_COMPLETED


def execute_campaign(spec: CampaignSpec) -> CampaignResult:
    """Ejecuta cada corrida en orden, una después de la otra.

    Delega en ``execute_scientific_run``. No arma un ``SimulationStack``
    propio. Una excepción de la corrida no cancela las siguientes y no
    se vuelve a intentar.
    """
    if not isinstance(spec, CampaignSpec):
        raise TypeError("spec debe ser un CampaignSpec")
    outcomes: list[CampaignRunResult] = []
    for index, run in enumerate(spec.runs):
        try:
            result = execute_scientific_run(run.spec)
        except Exception as exc:
            outcomes.append(
                CampaignRunResult(
                    index=index,
                    label=run.label,
                    result=None,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )
        else:
            outcomes.append(
                CampaignRunResult(
                    index=index,
                    label=run.label,
                    result=result,
                )
            )
    return CampaignResult(
        campaign_id=spec.campaign_id,
        description=spec.description,
        campaign_identity=spec.campaign_identity,
        runs=tuple(outcomes),
    )


def controlled_development_campaign() -> CampaignSpec:
    """Dos corridas de desarrollo, en orden fijo.

    Comparten escenario, workload y semilla. La primera es individual y
    la segunda un lote fijo de dos eventos. No es evidencia científica.
    """
    scenario = controlled_local_scenario()
    workload = controlled_local_workload()
    comun = {
        "scenario": scenario,
        "workload": workload,
        "seed": CONTROLLED_LOCAL_SEED,
        "stop_policy": StopPolicy.PROFILE_HORIZON_SETTLED,
        "trace_level": TraceLevel.SUMMARY,
    }
    individual = ScientificRunSpec(strategy_type=STRATEGY_TYPE_INDIVIDUAL, **comun)
    lote = ScientificRunSpec(
        strategy_type=STRATEGY_TYPE_FIXED_BATCH,
        batch_size_events=CONTROLLED_DEVELOPMENT_BATCH_SIZE,
        **comun,
    )
    return CampaignSpec(
        campaign_id=CONTROLLED_DEVELOPMENT_CAMPAIGN_ID,
        description=(
            "Campaña científica controlada de desarrollo. No es evidencia científica."
        ),
        runs=(
            CampaignRunSpec(label=STRATEGY_TYPE_INDIVIDUAL, spec=individual),
            CampaignRunSpec(
                label=f"fixed_batch_{CONTROLLED_DEVELOPMENT_BATCH_SIZE}",
                spec=lote,
            ),
        ),
    )


def _canonical_campaign_json(spec: CampaignSpec) -> str:
    """JSON compacto y ordenado de la definición. La lista conserva el orden."""
    payload = {
        "campaign_id": spec.campaign_id,
        "description": spec.description,
        "runs": [
            {"label": run.label, "spec": _spec_payload(run.spec)} for run in spec.runs
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _spec_payload(spec: ScientificRunSpec) -> dict[str, object]:
    return {
        "scenario": spec.scenario.model_dump(mode="json"),
        "workload": spec.workload.model_dump(mode="json"),
        "seed": spec.seed,
        "strategy_type": spec.strategy_type,
        "batch_size_events": spec.batch_size_events,
        "recovery_policy": spec.recovery_policy.value,
        "retry_policy": spec.retry_policy.model_dump(mode="json"),
        "failure_plan": spec.failure_plan.model_dump(mode="json"),
        "stop_policy": spec.stop_policy.value,
        "trace_level": spec.trace_level.value,
        "gap_request_timeout_seconds": spec.gap_request_timeout_seconds,
    }
