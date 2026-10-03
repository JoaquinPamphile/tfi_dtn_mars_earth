"""E2: efecto de la carga ofrecida.

La conectividad permanece. Cambia la fracción de volumen ofrecido canónico
respecto de la capacidad serializada Marte → relé. En cada fracción se
comparan Individual y lote fijo 25.

La pregunta es la del diseño validado. Este módulo no infiere un umbral
de saturación ni declara que una fracción siempre falle.

La corrida histórica no trae una sección de recuperación v2. Aquí es
``RecoveryPolicy.SENDER_DRIVEN`` con el timeout de ACK del escenario
Alessi. No hay pérdida silenciosa. La parada es
``PROFILE_HORIZON_SETTLED`` sobre el horizonte del perfil. No se drena
hasta dejar el scheduler vacío.

La identidad configurada del dataset es la de escenario y semilla. Es la
misma en las doce corridas. Las huellas de eventos coinciden dentro de
cada carga y difieren entre cargas, porque cambian el conteo, la tasa y
las marcas de tiempo.

``build_e2_probe_campaign`` no es el diseño oficial. Solo reduce el conteo
para tests. No aplica la grilla.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from core.domain.priority import TelemetryPriority
from core.domain.retry import RetryPolicy
from core.failure.plan import FailurePlan
from core.mars.node import DEFAULT_SOURCE_ID
from core.recovery.policy import RecoveryPolicy
from core.simulation.engine import SimulationStatus
from core.stopping.policy import StopPolicy
from core.sync.strategy import STRATEGY_TYPE_FIXED_BATCH, STRATEGY_TYPE_INDIVIDUAL
from core.trace.level import TraceLevel

from experiments.campaign import CampaignResult, CampaignRunSpec, CampaignSpec
from experiments.e1 import E1_ACK_TIMEOUT_SECONDS, e1_scenario
from experiments.offered_load import (
    CANONICAL_OFFERED_LOAD_FRACTIONS,
    CAPACITY_INTERVAL_WORKLOAD_TO_LAST_MARS_RELAY_END,
    ReferenceCapacity,
    capacity_interval_to_last_mars_relay_end,
    generation_rate_for_event_count,
    reference_mars_to_relay_capacity,
)
from experiments.result import ScientificRunResult
from experiments.scenario import Scenario
from experiments.spec import ScientificRunSpec
from experiments.workload import (
    CONTROLLED_COMMON_CANONICAL_INDIVIDUAL_BYTES,
    CONTROLLED_COMMON_EVENT_RATE,
    CONTROLLED_COMMON_EVENT_TYPE,
    CONTROLLED_COMMON_FINITE_DURATION_SECONDS,
    CONTROLLED_COMMON_FLOW,
    CONTROLLED_COMMON_START_TIME_SIM,
    CONTROLLED_COMMON_WORKLOAD_ID,
    Workload,
)

E2_CAMPAIGN_ID = "e2-offered-load"
E2_PROBE_CAMPAIGN_ID = "e2-probe"
E2_SEED = 1
E2_BATCH_SIZE_EVENTS = 25

E2_QUESTION = (
    "¿Cómo cambia el comportamiento de la aplicación cuando la carga de "
    "telemetría ofrecida se acerca a la capacidad de comunicación disponible "
    "y la supera?"
)

E2_DESCRIPTION = f"E2 — efecto de la carga ofrecida. {E2_QUESTION}"

E2_PROBE_DESCRIPTION = (
    "Sonda de E2 para tests. Conserva el escenario, la semilla, la "
    "recuperación, el plan de fallos, la parada y el horizonte. Cambia solo "
    "el conteo de eventos y no aplica la grilla oficial. No es el diseño "
    "oficial y no es evidencia."
)

E2_DATASET_IDENTITY_NOTE = (
    "La identidad configurada del dataset depende solo del escenario y de "
    "la semilla. No depende de la estrategia ni de la fracción de carga. "
    "Dentro de cada carga las huellas de eventos coinciden. Entre cargas "
    "distintas, el conteo, la tasa y las marcas de tiempo difieren, y por "
    "eso las huellas de eventos difieren."
)

E2_DIAGNOSTIC_NOTE = (
    "El reloj de pared y la cantidad de registros de traza son diagnóstico "
    "de software. No son un resultado científico."
)

E2_CAPACITY_NOTE = (
    "La fracción es volumen ofrecido canónico respecto de la capacidad "
    "serializada Marte → relé. No es la utilización realizada."
)

# Indicadores del diseño más la separación entre persistencia en Tierra
# y confirmación en Marte. No hay una columna única de éxito.
E2_RESPONSE_METRICS = (
    "offered_load_fraction",
    "generated",
    "earth_persisted_unique",
    "confirmed",
    "completeness",
    "confirmation_ratio",
    "not_persisted_on_earth",
    "persisted_on_earth_but_unconfirmed",
    "final_backlog",
    "gaps_count",
    "converged",
    "freshness_p50_seconds",
    "freshness_p95_seconds",
    "time_to_convergence_seconds",
    "sync_units_created",
    "telemetry_syncunit_bytes_created",
    "ack_syncunit_bytes_created",
    "contact_utilization_weighted",
)

_STRATEGIES = (
    ("Individual", "Individual", STRATEGY_TYPE_INDIVIDUAL, None),
    ("Fixed Batch 25", "Lote fijo 25", STRATEGY_TYPE_FIXED_BATCH, E2_BATCH_SIZE_EVENTS),
)


@dataclass(frozen=True, slots=True)
class E2Cell:
    """Una celda. El rótulo oficial no lo interpreta la campaña genérica."""

    label: str
    load_display: str
    strategy_display: str
    offered_load_fraction: float | None
    strategy_type: str
    batch_size_events: int | None


def _official_cells() -> tuple[E2Cell, ...]:
    cells: list[E2Cell] = []
    for fraction in CANONICAL_OFFERED_LOAD_FRACTIONS:
        carga = f"{fraction * 100:.0f} %"
        token = f"{fraction:.2f}"
        for official, display, strategy, batch in _STRATEGIES:
            cells.append(
                E2Cell(
                    label=f"{token} {official}",
                    load_display=carga,
                    strategy_display=display,
                    offered_load_fraction=fraction,
                    strategy_type=strategy,
                    batch_size_events=batch,
                )
            )
    return tuple(cells)


E2_CELLS = _official_cells()

E2_PROBE_CELLS = (
    E2Cell(
        "sonda_individual",
        "sonda",
        "Individual",
        None,
        STRATEGY_TYPE_INDIVIDUAL,
        None,
    ),
    E2Cell(
        "sonda_fixed_batch_25",
        "sonda",
        "Lote fijo 25",
        None,
        STRATEGY_TYPE_FIXED_BATCH,
        E2_BATCH_SIZE_EVENTS,
    ),
)


@dataclass(frozen=True, slots=True)
class E2TreatmentResult:
    """Métricas de una celda, leídas de la corrida. No las recalcula."""

    label: str
    load_display: str
    strategy_display: str
    offered_load_fraction: float | None
    strategy_type: str
    batch_size_events: int | None
    dataset_identity: str
    execution_identity: str
    generated: int
    earth_persisted_unique: int
    confirmed: int
    completeness: float | None
    confirmation_ratio: float | None
    not_persisted_on_earth: int
    persisted_on_earth_but_unconfirmed: int
    final_backlog: int
    gaps_count: int
    converged: bool
    freshness_p50_seconds: float | None
    freshness_p95_seconds: float | None
    time_to_convergence_seconds: float | None
    sync_units_created: int
    telemetry_syncunit_bytes_created: int
    ack_syncunit_bytes_created: int
    contact_utilization_weighted: float | None
    simulation_time: float
    trace_entry_count: int

    def metrics_dict(self) -> dict[str, object]:
        """Indicadores de E2, sin redondeo y sin ranking."""
        payload = {
            "offered_load_fraction": self.offered_load_fraction,
            "generated": self.generated,
            "earth_persisted_unique": self.earth_persisted_unique,
            "confirmed": self.confirmed,
            "completeness": self.completeness,
            "confirmation_ratio": self.confirmation_ratio,
            "not_persisted_on_earth": self.not_persisted_on_earth,
            "persisted_on_earth_but_unconfirmed": self.persisted_on_earth_but_unconfirmed,
            "final_backlog": self.final_backlog,
            "gaps_count": self.gaps_count,
            "converged": self.converged,
            "freshness_p50_seconds": self.freshness_p50_seconds,
            "freshness_p95_seconds": self.freshness_p95_seconds,
            "time_to_convergence_seconds": self.time_to_convergence_seconds,
            "sync_units_created": self.sync_units_created,
            "telemetry_syncunit_bytes_created": self.telemetry_syncunit_bytes_created,
            "ack_syncunit_bytes_created": self.ack_syncunit_bytes_created,
            "contact_utilization_weighted": self.contact_utilization_weighted,
        }
        return {name: payload[name] for name in E2_RESPONSE_METRICS}


@dataclass(frozen=True, slots=True)
class E2Result:
    """Vista de E2 sobre las métricas de cada corrida."""

    campaign_id: str
    description: str
    question: str
    campaign_identity: str
    dataset_identity: str
    treatments: tuple[E2TreatmentResult, ...]
    reference_capacity: ReferenceCapacity | None = None
    wall_execution_seconds: float | None = None

    @property
    def trace_entries_total(self) -> int:
        return sum(item.trace_entry_count for item in self.treatments)


def e2_base_workload() -> Workload:
    """Perfil controlado común, antes de aplicar una fracción."""
    return Workload(
        workload_id=CONTROLLED_COMMON_WORKLOAD_ID,
        source_id=DEFAULT_SOURCE_ID,
        event_type=CONTROLLED_COMMON_EVENT_TYPE,
        flow=CONTROLLED_COMMON_FLOW,
        priority=TelemetryPriority.NORMAL,
        start_time_sim=CONTROLLED_COMMON_START_TIME_SIM,
        duration_seconds=CONTROLLED_COMMON_FINITE_DURATION_SECONDS,
        max_events=None,
        rate_events_per_second=CONTROLLED_COMMON_EVENT_RATE,
        canonical_individual_syncunit_bytes=CONTROLLED_COMMON_CANONICAL_INDIVIDUAL_BYTES,
    )


def e2_reference_capacity(scenario: Scenario) -> ReferenceCapacity:
    """Capacidad Marte → relé desde el inicio del workload hasta el último contacto."""
    start, end = capacity_interval_to_last_mars_relay_end(
        scenario,
        workload_start_sim=CONTROLLED_COMMON_START_TIME_SIM,
    )
    return reference_mars_to_relay_capacity(
        scenario,
        interval_start_sim=start,
        interval_end_sim=end,
    )


def build_e2_campaign() -> CampaignSpec:
    """Diseño oficial. Seis cargas por dos estrategias, en ese orden."""
    scenario = e1_scenario()
    capacity = e2_reference_capacity(scenario)
    base = e2_base_workload()
    failure_plan = FailurePlan()
    retry_policy = RetryPolicy(ack_timeout_seconds=E1_ACK_TIMEOUT_SECONDS)
    by_fraction: dict[float, list[E2Cell]] = {}
    for cell in E2_CELLS:
        if cell.offered_load_fraction is None:
            raise ValueError("la celda oficial requiere fracción de carga")
        by_fraction.setdefault(cell.offered_load_fraction, []).append(cell)
    runs: list[CampaignRunSpec] = []
    for fraction in CANONICAL_OFFERED_LOAD_FRACTIONS:
        workload = base.with_offered_load(
            load_fraction=fraction,
            capacity_bytes=capacity.serialized_capacity_bytes,
        )
        for cell in by_fraction[fraction]:
            runs.append(
                CampaignRunSpec(
                    label=cell.label,
                    spec=_run_spec(
                        scenario=scenario,
                        workload=workload,
                        cell=cell,
                        failure_plan=failure_plan,
                        retry_policy=retry_policy,
                    ),
                )
            )
    return CampaignSpec(
        campaign_id=E2_CAMPAIGN_ID,
        description=E2_DESCRIPTION,
        runs=tuple(runs),
    )


def build_e2_probe_campaign(*, max_events: int) -> CampaignSpec:
    """Individual y lote fijo 25 con un conteo chico. No es el diseño oficial."""
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
        raise ValueError("max_events de la sonda debe ser un entero >= 1")
    scenario = e1_scenario()
    base = e2_base_workload()
    if base.duration_seconds is None:
        raise ValueError("la sonda de E2 requiere la duración del perfil común")
    rate = generation_rate_for_event_count(
        event_count=max_events,
        duration_seconds=base.duration_seconds,
    )
    workload = base.model_copy(
        update={
            "max_events": max_events,
            "rate_events_per_second": rate,
        }
    )
    failure_plan = FailurePlan()
    retry_policy = RetryPolicy(ack_timeout_seconds=E1_ACK_TIMEOUT_SECONDS)
    runs = tuple(
        CampaignRunSpec(
            label=cell.label,
            spec=_run_spec(
                scenario=scenario,
                workload=workload,
                cell=cell,
                failure_plan=failure_plan,
                retry_policy=retry_policy,
            ),
        )
        for cell in E2_PROBE_CELLS
    )
    return CampaignSpec(
        campaign_id=E2_PROBE_CAMPAIGN_ID,
        description=E2_PROBE_DESCRIPTION,
        runs=runs,
    )


def e2_result(
    spec: CampaignSpec,
    campaign: CampaignResult,
    *,
    wall_execution_seconds: float | None = None,
) -> E2Result:
    """Arma la vista. Exige el orden de la especificación y corridas completas."""
    expected = _expected_labels(spec)
    if tuple(run.label for run in spec.runs) != expected:
        raise ValueError("la especificación de E2 no tiene los rótulos de su diseño")
    if tuple(run.label for run in campaign.runs) != expected:
        raise ValueError("el resultado de E2 no sigue el orden de la especificación")
    if campaign.campaign_id != spec.campaign_id:
        raise ValueError("la campaña ejecutada no es la especificación recibida")
    treatments: list[E2TreatmentResult] = []
    for planned, finished in zip(spec.runs, campaign.runs, strict=True):
        result = finished.result
        if result is None:
            raise ValueError(
                f"la corrida {finished.label} falló: {finished.error_type}: {finished.error_message}"
            )
        if result.engine_status != SimulationStatus.COMPLETED.value:
            raise ValueError(f"la corrida {finished.label} no terminó COMPLETED")
        if result.strategy_type != planned.spec.strategy_type:
            raise ValueError("la estrategia ejecutada no coincide con la especificación")
        if result.batch_size_events != planned.spec.batch_size_events:
            raise ValueError("el tamaño de lote ejecutado no coincide con la especificación")
        if result.offered_load_fraction != planned.spec.workload.offered_load_fraction:
            raise ValueError("la fracción ejecutada no coincide con la especificación")
        treatments.append(_treatment_result(finished.label, result))
    dataset_ids = {item.dataset_identity for item in treatments}
    if len(dataset_ids) != 1:
        raise ValueError(
            "E2 exige la misma dataset_identity configurada: escenario y semilla"
        )
    capacity = None
    if spec.campaign_id == E2_CAMPAIGN_ID:
        capacity = e2_reference_capacity(spec.runs[0].spec.scenario)
    return E2Result(
        campaign_id=campaign.campaign_id,
        description=campaign.description,
        question=E2_QUESTION,
        campaign_identity=campaign.campaign_identity,
        dataset_identity=treatments[0].dataset_identity,
        treatments=tuple(treatments),
        reference_capacity=capacity,
        wall_execution_seconds=wall_execution_seconds,
    )


def format_e2(result: E2Result) -> str:
    """Tabla por carga y estrategia. Tierra y Marte van en columnas distintas."""
    encabezado = (
        "Carga",
        "Estrategia",
        "Gen",
        "Tierra",
        "Marte",
        "Completitud",
        "Confirmación",
        "Backlog",
        "Convergió",
    )
    filas = [encabezado]
    for item in result.treatments:
        filas.append(
            (
                item.load_display,
                item.strategy_display,
                str(item.generated),
                str(item.earth_persisted_unique),
                str(item.confirmed),
                _cantidad(item.completeness),
                _cantidad(item.confirmation_ratio),
                str(item.final_backlog),
                "sí" if item.converged else "no",
            )
        )
    anchos = [max(len(fila[col]) for fila in filas) for col in range(len(encabezado))]
    lineas = [
        "E2 — Efecto de la carga ofrecida",
        "",
        result.question,
        "",
        f"Campaña: {result.campaign_id}",
        f"Identidad de campaña: {result.campaign_identity}",
        f"Identidad de dataset: {result.dataset_identity}",
        E2_DATASET_IDENTITY_NOTE,
        "",
    ]
    if result.reference_capacity is not None:
        capacidad = result.reference_capacity
        lineas.append(
            "Capacidad Marte → relé en "
            f"[{_numero(capacidad.interval_start_sim)}, {_numero(capacidad.interval_end_sim)}] s: "
            f"{_numero(capacidad.serialized_capacity_bytes)} bytes."
        )
        lineas.append(E2_CAPACITY_NOTE)
        lineas.append("")
    for fila in filas:
        lineas.append("  ".join(celda.ljust(anchos[i]) for i, celda in enumerate(fila)))
    lineas.append("")
    lineas.append("Tierra es earth_persisted_unique. Marte es confirmed.")
    lineas.append("Completitud es persistencia en Tierra. Confirmación es confirmación en Marte.")
    lineas.append("Backlog es final_backlog. Convergió es converged.")
    lineas.append("")
    lineas.append("Diagnóstico de ejecución. No es resultado científico.")
    for item in result.treatments:
        lineas.append(
            f"{item.label}: tiempo simulado {_numero(item.simulation_time)} s; "
            f"traza {item.trace_entry_count} registros"
        )
    lineas.append(f"Registros de traza en total: {result.trace_entries_total}")
    if result.wall_execution_seconds is None:
        lineas.append("Reloj de pared: no medido")
    else:
        lineas.append(
            "Reloj de pared: "
            f"{_numero(result.wall_execution_seconds)} s. No es una métrica científica."
        )
    return "\n".join(lineas)


def e2_result_payload(result: E2Result) -> dict[str, object]:
    """JSON de la vista. Los floats conservan el valor de dominio."""
    payload: dict[str, object] = {
        "experiment": "E2",
        "title": "E2 — Efecto de la carga ofrecida",
        "question": result.question,
        "campaign_id": result.campaign_id,
        "description": result.description,
        "campaign_identity": result.campaign_identity,
        "dataset_identity": result.dataset_identity,
        "dataset_identity_note": E2_DATASET_IDENTITY_NOTE,
        "statistical_analysis": "not_implemented",
        "statistical_note": (
            "Comparación descriptiva de las corridas. No hay inferencia estadística."
        ),
        "treatments": [
            {
                "label": item.label,
                "load_display": item.load_display,
                "strategy_display": item.strategy_display,
                "strategy_type": item.strategy_type,
                "batch_size_events": item.batch_size_events,
                "dataset_identity": item.dataset_identity,
                "execution_identity": item.execution_identity,
                "metrics": item.metrics_dict(),
                "diagnostics": {
                    "simulation_time": item.simulation_time,
                    "trace_entry_count": item.trace_entry_count,
                },
            }
            for item in result.treatments
        ],
        "execution_diagnostics": {
            "wall_execution_seconds": result.wall_execution_seconds,
            "trace_entries_total": result.trace_entries_total,
            "note": E2_DIAGNOSTIC_NOTE,
        },
    }
    if result.reference_capacity is not None:
        capacidad = result.reference_capacity
        payload["reference_capacity"] = {
            "capacity_interval": CAPACITY_INTERVAL_WORKLOAD_TO_LAST_MARS_RELAY_END,
            "interval_start_sim": capacidad.interval_start_sim,
            "interval_end_sim": capacidad.interval_end_sim,
            "serialized_capacity_bytes": capacidad.serialized_capacity_bytes,
            "contact_count": capacidad.contact_count,
            "note": E2_CAPACITY_NOTE,
        }
    return payload


def e2_result_json(result: E2Result) -> str:
    """Texto JSON de ``e2_result_payload``, con caracteres Unicode."""
    return json.dumps(e2_result_payload(result), ensure_ascii=False, indent=2)


def _run_spec(
    *,
    scenario: Scenario,
    workload: Workload,
    cell: E2Cell,
    failure_plan: FailurePlan,
    retry_policy: RetryPolicy,
) -> ScientificRunSpec:
    return ScientificRunSpec(
        scenario=scenario,
        workload=workload,
        seed=E2_SEED,
        strategy_type=cell.strategy_type,
        batch_size_events=cell.batch_size_events,
        recovery_policy=RecoveryPolicy.SENDER_DRIVEN,
        retry_policy=retry_policy,
        failure_plan=failure_plan,
        stop_policy=StopPolicy.PROFILE_HORIZON_SETTLED,
        trace_level=TraceLevel.SCIENTIFIC,
    )


def _expected_labels(spec: CampaignSpec) -> tuple[str, ...]:
    if spec.campaign_id == E2_CAMPAIGN_ID:
        return tuple(cell.label for cell in E2_CELLS)
    if spec.campaign_id == E2_PROBE_CAMPAIGN_ID:
        return tuple(cell.label for cell in E2_PROBE_CELLS)
    raise ValueError("la especificación no es la campaña oficial de E2 ni su sonda")


def _cell_for(label: str) -> E2Cell:
    for cell in (*E2_CELLS, *E2_PROBE_CELLS):
        if cell.label == label:
            return cell
    raise ValueError(f"rótulo desconocido de E2: {label}")


def _treatment_result(label: str, result: ScientificRunResult) -> E2TreatmentResult:
    cell = _cell_for(label)
    metrics = result.metrics
    traffic = metrics.traffic
    freshness = metrics.freshness
    return E2TreatmentResult(
        label=label,
        load_display=cell.load_display,
        strategy_display=cell.strategy_display,
        offered_load_fraction=result.offered_load_fraction,
        strategy_type=result.strategy_type,
        batch_size_events=result.batch_size_events,
        dataset_identity=result.dataset_identity,
        execution_identity=result.execution_identity,
        generated=metrics.generated,
        earth_persisted_unique=metrics.earth_persisted_unique,
        confirmed=metrics.confirmed,
        completeness=metrics.completeness,
        confirmation_ratio=metrics.confirmation_ratio,
        not_persisted_on_earth=metrics.not_persisted_on_earth,
        persisted_on_earth_but_unconfirmed=metrics.persisted_on_earth_but_unconfirmed,
        final_backlog=metrics.final_backlog,
        gaps_count=metrics.gaps_count,
        converged=metrics.converged,
        freshness_p50_seconds=freshness.p50_seconds,
        freshness_p95_seconds=freshness.p95_seconds,
        time_to_convergence_seconds=metrics.convergence.time_to_convergence_seconds,
        sync_units_created=metrics.sync_units_created,
        telemetry_syncunit_bytes_created=traffic.telemetry_syncunit_bytes_created,
        ack_syncunit_bytes_created=traffic.ack_syncunit_bytes_created,
        contact_utilization_weighted=metrics.contacts.contact_utilization_weighted,
        simulation_time=result.simulation_time,
        trace_entry_count=result.trace_entry_count,
    )


def _numero(value: float) -> str:
    text = f"{value:.9f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _cantidad(value: float | None) -> str:
    if value is None:
        return "no definido"
    return _numero(value)
