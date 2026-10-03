"""E1: efecto de la granularidad de sincronización.

La única variable es la agrupación. El escenario, el workload, la semilla,
la recuperación, el plan de fallos, la parada y el horizonte se mantienen.

Los contactos Marte–relé salen de una reconstrucción de la figura 5 del
análisis de prestaciones DTN de comunicaciones multi-activo Marte–Tierra,
redondeada al múltiplo de 5 s de esa figura. No son una tabla exacta ni un
efemérides. Los contactos relé–Tierra combinan esa reconstrucción con el
colapso de GS1, GS2, GS3 y EDRS en un solo extremo Tierra.

El tiempo físico es el de la figura multiplicado por 60:
1440 s de figura equivalen a 86400 s, un día.

``build_e1_probe_campaign`` no es el diseño oficial. Solo cambia el conteo
de eventos para tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from core.contact.contact import Contact, LogicalNode
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
from experiments.result import ScientificRunResult
from experiments.scenario import Scenario
from experiments.spec import ScientificRunSpec
from experiments.workload import Workload

SOURCE_APPROXIMATED = "SOURCE_APPROXIMATED"
SOURCE_TRANSFORMED = "SOURCE_TRANSFORMED"
SOURCE_DIRECT = "SOURCE_DIRECT"
TFI_ASSUMPTION = "TFI_ASSUMPTION"

E1_CAMPAIGN_ID = "e1-strategy-alessi-10k"
E1_PROBE_CAMPAIGN_ID = "e1-probe"
E1_SCENARIO_ID = "research-alessi-baseline"
E1_WORKLOAD_ID = "alessi-normal-tm"
E1_EVENT_TYPE = "research.alessi.normal_tm"
E1_FLOW = "alessi.normal_tm"
E1_SEED = 1
E1_MAX_EVENTS = 10_000
E1_START_TIME_SIM = 0.0

E1_SOURCE_BUNDLE_BYTES = 4096
E1_SOURCE_BYTE_RATE = 2000
E1_CANONICAL_INDIVIDUAL_BYTES = E1_SOURCE_BUNDLE_BYTES
E1_EVENT_RATE = E1_SOURCE_BYTE_RATE / E1_SOURCE_BUNDLE_BYTES
E1_PERIOD_SECONDS = E1_SOURCE_BUNDLE_BYTES / E1_SOURCE_BYTE_RATE

E1_PAPER_TO_PHYSICAL_SECONDS = 60
E1_HORIZON_PAPER_SECONDS = 1440
E1_HORIZON_SECONDS = float(E1_HORIZON_PAPER_SECONDS * E1_PAPER_TO_PHYSICAL_SECONDS)

E1_MARS_RELAY_RATE_BPS = 1_000_000
E1_RELAY_EARTH_RATE_BPS = 2_000_000
E1_EARTH_RELAY_RATE_BPS = 32_000
E1_MARS_RELAY_DELAY_S = 0.0
E1_INTERPLANETARY_DELAY_S = float(23 * 60)
E1_ACK_GUARD_MARGIN_SECONDS = 600.0
E1_ACK_TIMEOUT_SECONDS = (
    E1_HORIZON_SECONDS + 2 * E1_INTERPLANETARY_DELAY_S + E1_ACK_GUARD_MARGIN_SECONDS
)

E1_QUESTION = (
    "¿Cómo afecta la estrategia de sincronización a una aplicación de "
    "telemetría nativa de DTN cuando la conectividad es idéntica, el "
    "dataset de telemetría generado es idéntico, no hay fallos y únicamente "
    "cambia la agrupación de la sincronización?"
)

E1_DESCRIPTION = f"E1 — granularidad de sincronización. {E1_QUESTION}"

E1_PROBE_DESCRIPTION = (
    "Sonda de E1 para tests. Conserva los factores del diseño oficial y "
    "cambia solo el conteo de eventos. No es el diseño oficial y no es evidencia."
)

E1_SCENARIO_DESCRIPTION = (
    "Línea base de tres nodos en tiempo físico, derivada del análisis de "
    "prestaciones DTN de comunicaciones multi-activo Marte–Tierra. Corte "
    "representativo del orbitador 1: lander 143, orbitador 141 y un extremo "
    "Tierra que reúne GS1 (201), GS2 (202), GS3 (203) y EDRS (105). Los "
    "instantes salen de una reconstrucción de la figura 5, redondeada al "
    "múltiplo de 5 s de esa figura y pasada a tiempo físico multiplicando "
    "por 60. No son una tabla exacta de contactos ni un efemérides orbital. "
    "No reproduce la red de nueve nodos y no usa el orbitador 2."
)

E1_SCENARIO_NOTES = (
    "Clasificación. Intervalos Marte–relé: tiempo SOURCE_APPROXIMATED; "
    "tasa SOURCE_TRANSFORMED desde 1 Mbps; retardo SOURCE_DIRECT, "
    "aproximadamente nulo; el corte a solo el orbitador 1 es TFI_ASSUMPTION. "
    "Intervalos relé–Tierra: tiempo SOURCE_APPROXIMATED de la unión "
    "reconstruida y topología TFI_ASSUMPTION por el colapso de las "
    "estaciones en un extremo. El camino de vuelta, en ambos tramos, es "
    "TFI_ASSUMPTION. Horizonte SOURCE_TRANSFORMED: 1440 s de figura por 60. "
    "Retardo interplanetario SOURCE_TRANSFORMED: 23 min por 60. Tasas de "
    "bajada 2 Mbps y de subida 0,032 Mbps, SOURCE_TRANSFORMED a bps."
)

E1_DESCRIPTIVE_DELTA_NOTE = (
    "Comparación descriptiva derivada respecto de Individual. "
    "Estos valores no son métricas crudas independientes y no ordenan estrategias."
)

E1_DIAGNOSTIC_NOTE = (
    "El reloj de pared y la cantidad de registros de traza son diagnóstico "
    "de software. No son un resultado científico."
)

E1_RESPONSE_METRICS = (
    "generated",
    "earth_persisted_unique",
    "confirmed",
    "completeness",
    "final_backlog",
    "gaps_count",
    "duplicates_received",
    "duplicates_stored",
    "converged",
    "freshness_p50_seconds",
    "freshness_p95_seconds",
    "freshness_max_seconds",
    "time_to_convergence_seconds",
    "converged_at_sim",
    "telemetry_syncunit_bytes_created",
    "ack_syncunit_bytes_created",
    "retry_transport_bytes",
    "interrupted_transport_bytes",
    "contact_utilization_weighted",
    "sync_units_created",
)

# Intervalos ya redondeados al múltiplo de 5 s de la figura, enlace 143-141.
_MARS_RELAY_PAPER = (
    (1, 450, 475),
    (2, 575, 595),
    (3, 1220, 1245),
    (4, 1345, 1365),
)

# Unión reconstruida de los enlaces del orbitador 1 hacia Tierra, ya redondeada.
_RELAY_EARTH_PAPER = (
    (1, 20, 105),
    (2, 135, 160),
    (3, 255, 345),
    (4, 375, 460),
    (5, 490, 580),
    (6, 605, 700),
    (7, 725, 815),
    (8, 845, 935),
    (9, 960, 1055),
    (10, 1080, 1170),
    (11, 1200, 1290),
    (12, 1320, 1400),
)


@dataclass(frozen=True, slots=True)
class E1Treatment:
    """Un tratamiento. El rótulo es el de la campaña; el nombre es de presentación."""

    label: str
    display_name: str
    strategy_type: str
    batch_size_events: int | None


E1_TREATMENTS = (
    E1Treatment("individual", "Individual", STRATEGY_TYPE_INDIVIDUAL, None),
    E1Treatment("fixed_batch_10", "Lote fijo 10", STRATEGY_TYPE_FIXED_BATCH, 10),
    E1Treatment("fixed_batch_25", "Lote fijo 25", STRATEGY_TYPE_FIXED_BATCH, 25),
    E1Treatment("fixed_batch_50", "Lote fijo 50", STRATEGY_TYPE_FIXED_BATCH, 50),
)


@dataclass(frozen=True, slots=True)
class ContactoAlessi:
    """Ventana dirigida y la clasificación de cada dato que la define."""

    contact_id: str
    source: LogicalNode
    destination: LogicalNode
    paper_start_s: int
    paper_end_s: int
    data_rate_bps: int
    propagation_delay_s: float
    timing_classification: str
    rate_classification: str
    delay_classification: str
    topology_classification: str
    return_path_classification: str | None
    timing_source: str

    def to_contact(self) -> Contact:
        return Contact(
            contact_id=self.contact_id,
            source=self.source,
            destination=self.destination,
            start_time_sim=paper_seconds_to_sim(self.paper_start_s),
            end_time_sim=paper_seconds_to_sim(self.paper_end_s),
            data_rate_bps=self.data_rate_bps,
            propagation_delay_s=self.propagation_delay_s,
        )


@dataclass(frozen=True, slots=True)
class E1TreatmentResult:
    """Métricas de un tratamiento, leídas de la corrida. No las recalcula."""

    label: str
    display_name: str
    strategy_type: str
    batch_size_events: int | None
    dataset_identity: str
    execution_identity: str
    generated: int
    earth_persisted_unique: int
    confirmed: int
    completeness: float | None
    final_backlog: int
    gaps_count: int
    duplicates_received: int
    duplicates_stored: int
    converged: bool
    freshness_p50_seconds: float | None
    freshness_p95_seconds: float | None
    freshness_max_seconds: float | None
    time_to_convergence_seconds: float | None
    converged_at_sim: float | None
    telemetry_syncunit_bytes_created: int
    ack_syncunit_bytes_created: int
    retry_transport_bytes: int
    interrupted_transport_bytes: int
    contact_utilization_weighted: float | None
    sync_units_created: int
    simulation_time: float
    trace_entry_count: int

    def metrics_dict(self) -> dict[str, object]:
        """Solo las métricas de respuesta de E1, sin redondeo."""
        payload = {
            "generated": self.generated,
            "earth_persisted_unique": self.earth_persisted_unique,
            "confirmed": self.confirmed,
            "completeness": self.completeness,
            "final_backlog": self.final_backlog,
            "gaps_count": self.gaps_count,
            "duplicates_received": self.duplicates_received,
            "duplicates_stored": self.duplicates_stored,
            "converged": self.converged,
            "freshness_p50_seconds": self.freshness_p50_seconds,
            "freshness_p95_seconds": self.freshness_p95_seconds,
            "freshness_max_seconds": self.freshness_max_seconds,
            "time_to_convergence_seconds": self.time_to_convergence_seconds,
            "converged_at_sim": self.converged_at_sim,
            "telemetry_syncunit_bytes_created": self.telemetry_syncunit_bytes_created,
            "ack_syncunit_bytes_created": self.ack_syncunit_bytes_created,
            "retry_transport_bytes": self.retry_transport_bytes,
            "interrupted_transport_bytes": self.interrupted_transport_bytes,
            "contact_utilization_weighted": self.contact_utilization_weighted,
            "sync_units_created": self.sync_units_created,
        }
        return {name: payload[name] for name in E1_RESPONSE_METRICS}


@dataclass(frozen=True, slots=True)
class E1DescriptiveDelta:
    """Diferencia respecto de Individual. No es una métrica cruda ni un ranking."""

    label: str
    strategy_type: str
    batch_size_events: int | None
    delta_sync_units_created: float | None
    percent_reduction_sync_units: float | None
    delta_telemetry_syncunit_bytes: float | None
    percent_reduction_telemetry_syncunit_bytes: float | None
    delta_ack_syncunit_bytes: float | None
    percent_reduction_ack_syncunit_bytes: float | None
    delta_freshness_p95_seconds: float | None
    delta_time_to_convergence_seconds: float | None
    delta_contact_utilization_weighted: float | None


@dataclass(frozen=True, slots=True)
class E1Result:
    """Comparación de E1. Los números salen de cada ``ScientificRunMetrics``."""

    campaign_id: str
    description: str
    question: str
    campaign_identity: str
    dataset_identity: str
    treatments: tuple[E1TreatmentResult, ...]
    descriptive_deltas: tuple[E1DescriptiveDelta, ...]
    wall_execution_seconds: float | None = None

    @property
    def trace_entries_total(self) -> int:
        return sum(item.trace_entry_count for item in self.treatments)


def paper_seconds_to_sim(paper_seconds: int) -> float:
    """Segundos de la figura a segundos físicos: el valor de figura por 60."""
    return float(paper_seconds * E1_PAPER_TO_PHYSICAL_SECONDS)


def e1_contact_records() -> tuple[ContactoAlessi, ...]:
    """Ventanas del diseño, con la clasificación de cada dato."""
    records: list[ContactoAlessi] = []
    for index, start, end in _MARS_RELAY_PAPER:
        records.append(
            _mars_relay(
                index,
                start,
                end,
                source=LogicalNode.MARS,
                destination=LogicalNode.RELAY,
                return_path=False,
            )
        )
    for index, start, end in _MARS_RELAY_PAPER:
        records.append(
            _mars_relay(
                index,
                start,
                end,
                source=LogicalNode.RELAY,
                destination=LogicalNode.MARS,
                return_path=True,
            )
        )
    for index, start, end in _RELAY_EARTH_PAPER:
        records.append(
            _relay_earth(
                index,
                start,
                end,
                source=LogicalNode.RELAY,
                destination=LogicalNode.EARTH,
                return_path=False,
            )
        )
    for index, start, end in _RELAY_EARTH_PAPER:
        records.append(
            _relay_earth(
                index,
                start,
                end,
                source=LogicalNode.EARTH,
                destination=LogicalNode.RELAY,
                return_path=True,
            )
        )
    return tuple(records)


def e1_scenario() -> Scenario:
    """Escenario de E1. El horizonte es 1440 s de figura por 60."""
    return Scenario(
        scenario_id=E1_SCENARIO_ID,
        description=E1_SCENARIO_DESCRIPTION,
        notes=E1_SCENARIO_NOTES,
        horizon_seconds=E1_HORIZON_SECONDS,
        contacts=tuple(record.to_contact() for record in e1_contact_records()),
    )


def e1_workload(*, max_events: int = E1_MAX_EVENTS) -> Workload:
    """Telemetría normal del diseño. La duración no está fijada: manda el conteo.

    La tasa es 2000 B/s sobre el objetivo Individual de 4096 B, o sea
    0,48828125 eventos/s y un periodo de 2,048 s. El último instante lo
    calcula el perfil; no hay una constante redondeada de fin de generación.
    """
    return Workload(
        workload_id=E1_WORKLOAD_ID,
        source_id=DEFAULT_SOURCE_ID,
        event_type=E1_EVENT_TYPE,
        flow=E1_FLOW,
        priority=TelemetryPriority.NORMAL,
        start_time_sim=E1_START_TIME_SIM,
        duration_seconds=None,
        max_events=max_events,
        rate_events_per_second=E1_EVENT_RATE,
        canonical_individual_syncunit_bytes=E1_CANONICAL_INDIVIDUAL_BYTES,
    )


def build_e1_campaign() -> CampaignSpec:
    """Diseño oficial de E1. Cuatro corridas, 10000 eventos, en el orden fijo."""
    return _campaign(
        campaign_id=E1_CAMPAIGN_ID,
        description=E1_DESCRIPTION,
        max_events=E1_MAX_EVENTS,
    )


def build_e1_probe_campaign(*, max_events: int) -> CampaignSpec:
    """Misma estructura que E1 con otro conteo. No es el diseño oficial."""
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
        raise ValueError("max_events de la sonda debe ser un entero >= 1")
    if max_events == E1_MAX_EVENTS:
        raise ValueError("la sonda no usa el conteo oficial; el diseño es build_e1_campaign")
    return _campaign(
        campaign_id=E1_PROBE_CAMPAIGN_ID,
        description=E1_PROBE_DESCRIPTION,
        max_events=max_events,
    )


def e1_result(
    spec: CampaignSpec,
    campaign: CampaignResult,
    *,
    wall_execution_seconds: float | None = None,
) -> E1Result:
    """Arma la comparación. Exige los cuatro tratamientos en el orden oficial."""
    expected = tuple(item.label for item in E1_TREATMENTS)
    if tuple(run.label for run in spec.runs) != expected:
        raise ValueError(
            "E1 requiere individual, fixed_batch_10, fixed_batch_25 y fixed_batch_50"
        )
    if tuple(run.label for run in campaign.runs) != expected:
        raise ValueError("el resultado de E1 no sigue el orden oficial")
    if campaign.campaign_id != spec.campaign_id:
        raise ValueError("la campaña ejecutada no es la especificación recibida")
    treatments: list[E1TreatmentResult] = []
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
        treatments.append(_treatment_result(finished.label, result))
    dataset_ids = {item.dataset_identity for item in treatments}
    if len(dataset_ids) != 1:
        raise ValueError("E1 exige la misma dataset_identity en los cuatro tratamientos")
    return E1Result(
        campaign_id=campaign.campaign_id,
        description=campaign.description,
        question=E1_QUESTION,
        campaign_identity=campaign.campaign_identity,
        dataset_identity=treatments[0].dataset_identity,
        treatments=tuple(treatments),
        descriptive_deltas=_deltas(treatments),
        wall_execution_seconds=wall_execution_seconds,
    )


def format_e1(result: E1Result) -> str:
    """Tabla comparativa. El formato limita decimales; los valores no se redondean."""
    encabezado = (
        "Tratamiento",
        "Eventos",
        "SyncUnits",
        "Freshness p50",
        "Bytes",
        "Convergencia",
    )
    filas = [encabezado]
    for item in result.treatments:
        filas.append(
            (
                item.display_name,
                str(item.generated),
                str(item.sync_units_created),
                _cantidad(item.freshness_p50_seconds),
                str(item.telemetry_syncunit_bytes_created),
                _cantidad(item.time_to_convergence_seconds),
            )
        )
    anchos = [max(len(fila[col]) for fila in filas) for col in range(len(encabezado))]
    lineas = [
        "E1 — Granularidad de sincronización",
        "",
        result.question,
        "",
        f"Campaña: {result.campaign_id}",
        f"Identidad de campaña: {result.campaign_identity}",
        f"Identidad de dataset: {result.dataset_identity}",
        "",
    ]
    for fila in filas:
        lineas.append("  ".join(celda.ljust(anchos[i]) for i, celda in enumerate(fila)))
    lineas.append("")
    lineas.append("La columna Bytes es telemetry_syncunit_bytes_created.")
    lineas.append("La columna Convergencia es time_to_convergence_seconds.")
    lineas.append("")
    lineas.append("Diagnóstico de ejecución. No es resultado científico.")
    for item in result.treatments:
        lineas.append(
            f"{item.display_name}: tiempo simulado {_numero(item.simulation_time)} s; "
            f"traza {item.trace_entry_count} registros; "
            f"eventos {item.generated}"
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


def e1_result_payload(result: E1Result) -> dict[str, object]:
    """JSON de la comparación. Los floats conservan el valor de dominio."""
    return {
        "experiment": "E1",
        "title": "E1 — Granularidad de sincronización",
        "question": result.question,
        "campaign_id": result.campaign_id,
        "description": result.description,
        "campaign_identity": result.campaign_identity,
        "dataset_identity": result.dataset_identity,
        "statistical_analysis": "not_implemented",
        "statistical_note": (
            "Comparación descriptiva de las cuatro corridas. No hay inferencia estadística."
        ),
        "treatments": [
            {
                "label": item.label,
                "display_name": item.display_name,
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
        "descriptive_deltas": {
            "baseline_label": "individual",
            "note": E1_DESCRIPTIVE_DELTA_NOTE,
            "items": [
                {
                    "label": item.label,
                    "strategy_type": item.strategy_type,
                    "batch_size_events": item.batch_size_events,
                    "delta_sync_units_created": item.delta_sync_units_created,
                    "percent_reduction_sync_units": item.percent_reduction_sync_units,
                    "delta_telemetry_syncunit_bytes": item.delta_telemetry_syncunit_bytes,
                    "percent_reduction_telemetry_syncunit_bytes": (
                        item.percent_reduction_telemetry_syncunit_bytes
                    ),
                    "delta_ack_syncunit_bytes": item.delta_ack_syncunit_bytes,
                    "percent_reduction_ack_syncunit_bytes": (
                        item.percent_reduction_ack_syncunit_bytes
                    ),
                    "delta_freshness_p95_seconds": item.delta_freshness_p95_seconds,
                    "delta_time_to_convergence_seconds": item.delta_time_to_convergence_seconds,
                    "delta_contact_utilization_weighted": (
                        item.delta_contact_utilization_weighted
                    ),
                }
                for item in result.descriptive_deltas
            ],
        },
        "execution_diagnostics": {
            "wall_execution_seconds": result.wall_execution_seconds,
            "trace_entries_total": result.trace_entries_total,
            "note": E1_DIAGNOSTIC_NOTE,
        },
    }


def e1_result_json(result: E1Result) -> str:
    """Texto JSON de ``e1_result_payload``, con caracteres Unicode."""
    return json.dumps(
        e1_result_payload(result),
        ensure_ascii=False,
        indent=2,
    )


def _campaign(*, campaign_id: str, description: str, max_events: int) -> CampaignSpec:
    scenario = e1_scenario()
    workload = e1_workload(max_events=max_events)
    failure_plan = FailurePlan()
    retry_policy = RetryPolicy(ack_timeout_seconds=E1_ACK_TIMEOUT_SECONDS)
    runs = tuple(
        CampaignRunSpec(
            label=treatment.label,
            spec=ScientificRunSpec(
                scenario=scenario,
                workload=workload,
                seed=E1_SEED,
                strategy_type=treatment.strategy_type,
                batch_size_events=treatment.batch_size_events,
                recovery_policy=RecoveryPolicy.SENDER_DRIVEN,
                retry_policy=retry_policy,
                failure_plan=failure_plan,
                stop_policy=StopPolicy.PROFILE_HORIZON_SETTLED,
                trace_level=TraceLevel.SCIENTIFIC,
            ),
        )
        for treatment in E1_TREATMENTS
    )
    return CampaignSpec(campaign_id=campaign_id, description=description, runs=runs)


def _mars_relay(
    index: int,
    paper_start_s: int,
    paper_end_s: int,
    *,
    source: LogicalNode,
    destination: LogicalNode,
    return_path: bool,
) -> ContactoAlessi:
    if return_path:
        contact_id = f"alessi-relay-mars-{index:02d}"
        timing_source = "Figura 5, enlace 143-141. El camino de vuelta no está en la figura."
    else:
        contact_id = f"alessi-mars-relay-{index:02d}"
        timing_source = "Figura 5, enlace 143-141. Reconstruido y redondeado a 5 s de figura."
    return ContactoAlessi(
        contact_id=contact_id,
        source=source,
        destination=destination,
        paper_start_s=paper_start_s,
        paper_end_s=paper_end_s,
        data_rate_bps=E1_MARS_RELAY_RATE_BPS,
        propagation_delay_s=E1_MARS_RELAY_DELAY_S,
        timing_classification=SOURCE_APPROXIMATED,
        rate_classification=SOURCE_TRANSFORMED,
        delay_classification=SOURCE_DIRECT,
        topology_classification=TFI_ASSUMPTION,
        return_path_classification=TFI_ASSUMPTION if return_path else None,
        timing_source=timing_source,
    )


def _relay_earth(
    index: int,
    paper_start_s: int,
    paper_end_s: int,
    *,
    source: LogicalNode,
    destination: LogicalNode,
    return_path: bool,
) -> ContactoAlessi:
    if return_path:
        contact_id = f"alessi-earth-relay-{index:02d}"
        rate = E1_EARTH_RELAY_RATE_BPS
        timing_source = (
            "Figura 5, unión de enlaces del orbitador 1 hacia Tierra. "
            "Mismos intervalos reconstruidos. El camino de ACK es un supuesto."
        )
    else:
        contact_id = f"alessi-relay-earth-{index:02d}"
        rate = E1_RELAY_EARTH_RATE_BPS
        timing_source = (
            "Figura 5, unión reconstruida de 141-201, 141-202, 141-203 y 141-105. "
            "El colapso en un extremo Tierra es un supuesto. No es una tabla exacta."
        )
    return ContactoAlessi(
        contact_id=contact_id,
        source=source,
        destination=destination,
        paper_start_s=paper_start_s,
        paper_end_s=paper_end_s,
        data_rate_bps=rate,
        propagation_delay_s=E1_INTERPLANETARY_DELAY_S,
        timing_classification=SOURCE_APPROXIMATED,
        rate_classification=SOURCE_TRANSFORMED,
        delay_classification=SOURCE_TRANSFORMED,
        topology_classification=TFI_ASSUMPTION,
        return_path_classification=TFI_ASSUMPTION if return_path else None,
        timing_source=timing_source,
    )


def _treatment_result(label: str, result: ScientificRunResult) -> E1TreatmentResult:
    metrics = result.metrics
    traffic = metrics.traffic
    freshness = metrics.freshness
    display = next(item.display_name for item in E1_TREATMENTS if item.label == label)
    return E1TreatmentResult(
        label=label,
        display_name=display,
        strategy_type=result.strategy_type,
        batch_size_events=result.batch_size_events,
        dataset_identity=result.dataset_identity,
        execution_identity=result.execution_identity,
        generated=metrics.generated,
        earth_persisted_unique=metrics.earth_persisted_unique,
        confirmed=metrics.confirmed,
        completeness=metrics.completeness,
        final_backlog=metrics.final_backlog,
        gaps_count=metrics.gaps_count,
        duplicates_received=metrics.duplicates_received,
        duplicates_stored=metrics.duplicates_stored,
        converged=metrics.converged,
        freshness_p50_seconds=freshness.p50_seconds,
        freshness_p95_seconds=freshness.p95_seconds,
        freshness_max_seconds=freshness.max_seconds,
        time_to_convergence_seconds=metrics.convergence.time_to_convergence_seconds,
        converged_at_sim=metrics.convergence.converged_at_sim,
        telemetry_syncunit_bytes_created=traffic.telemetry_syncunit_bytes_created,
        ack_syncunit_bytes_created=traffic.ack_syncunit_bytes_created,
        retry_transport_bytes=traffic.retry_transport_bytes,
        interrupted_transport_bytes=traffic.interrupted_transport_bytes,
        contact_utilization_weighted=metrics.contacts.contact_utilization_weighted,
        sync_units_created=metrics.sync_units_created,
        simulation_time=result.simulation_time,
        trace_entry_count=result.trace_entry_count,
    )


def _deltas(treatments: list[E1TreatmentResult]) -> tuple[E1DescriptiveDelta, ...]:
    baseline = next(item for item in treatments if item.label == "individual")
    rows: list[E1DescriptiveDelta] = []
    for item in treatments:
        if item.label == baseline.label:
            continue
        rows.append(
            E1DescriptiveDelta(
                label=item.label,
                strategy_type=item.strategy_type,
                batch_size_events=item.batch_size_events,
                delta_sync_units_created=_delta(
                    item.sync_units_created, baseline.sync_units_created
                ),
                percent_reduction_sync_units=_percent_reduction(
                    item.sync_units_created, baseline.sync_units_created
                ),
                delta_telemetry_syncunit_bytes=_delta(
                    item.telemetry_syncunit_bytes_created,
                    baseline.telemetry_syncunit_bytes_created,
                ),
                percent_reduction_telemetry_syncunit_bytes=_percent_reduction(
                    item.telemetry_syncunit_bytes_created,
                    baseline.telemetry_syncunit_bytes_created,
                ),
                delta_ack_syncunit_bytes=_delta(
                    item.ack_syncunit_bytes_created, baseline.ack_syncunit_bytes_created
                ),
                percent_reduction_ack_syncunit_bytes=_percent_reduction(
                    item.ack_syncunit_bytes_created, baseline.ack_syncunit_bytes_created
                ),
                delta_freshness_p95_seconds=_delta(
                    item.freshness_p95_seconds, baseline.freshness_p95_seconds
                ),
                delta_time_to_convergence_seconds=_delta(
                    item.time_to_convergence_seconds, baseline.time_to_convergence_seconds
                ),
                delta_contact_utilization_weighted=_delta(
                    item.contact_utilization_weighted, baseline.contact_utilization_weighted
                ),
            )
        )
    return tuple(rows)


def _delta(value: object, baseline: object) -> float | None:
    if isinstance(value, bool) or isinstance(baseline, bool):
        return None
    if not isinstance(value, (int, float)) or not isinstance(baseline, (int, float)):
        return None
    return float(value) - float(baseline)


def _percent_reduction(value: object, baseline: object) -> float | None:
    if isinstance(value, bool) or isinstance(baseline, bool):
        return None
    if not isinstance(value, (int, float)) or not isinstance(baseline, (int, float)):
        return None
    if baseline == 0:
        return None
    return (float(baseline) - float(value)) / float(baseline) * 100.0


def _numero(value: float) -> str:
    text = f"{value:.9f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _cantidad(value: float | None) -> str:
    if value is None:
        return "no definido"
    return _numero(value)
