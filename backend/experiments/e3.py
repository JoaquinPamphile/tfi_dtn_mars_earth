"""E3: comparación controlada de recovery sender-driven y receiver-driven.

La pregunta es la del diseño ``e3-recovery-policy``. El contraste primario
es la misma pérdida silenciosa bajo las dos políticas. Las celdas sin
pérdida comprueban que la política, sola, no cambia el dataset ni emite
tráfico de recuperación.

Es un experimento controlado sobre el perfil de contactos
``research-alessi-baseline``. No reproduce la red Alessi de nueve nodos.
La estrategia es Individual. Hay una sola pérdida silenciosa, de la
secuencia 5000, intento 1, salto relé → Tierra. Los timeouts 8250 s y
6694 s están calibrados en el modelo; no son parámetros de ese análisis.

La identidad de ejecución validada depende del escenario, la semilla, la
estrategia y el lote. No distingue la política ni el plan de fallos.

``build_e3_probe_campaign`` no es el diseño oficial. Cambia el conteo y,
con él, la secuencia perdida, para que el hueco siga siendo interno.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from core.domain.retry import DEFAULT_ACK_TIMEOUT_SECONDS, RetryPolicy
from core.failure.plan import FailurePlan
from core.failure.silent import (
    FORWARD_HOP_RELAY_TO_EARTH,
    SilentForwardDeliveryLossFailure,
    silent_forward_delivery_loss_failure_id,
)
from core.mars.node import DEFAULT_SOURCE_ID
from core.metrics.recovery import RecoveryEpisodeResult
from core.recovery.policy import RecoveryPolicy
from core.simulation.engine import SimulationStatus
from core.stopping.policy import StopPolicy
from core.sync.strategy import STRATEGY_TYPE_INDIVIDUAL
from core.trace.level import TraceLevel

from experiments.campaign import CampaignResult, CampaignRunSpec, CampaignSpec
from experiments.e1 import (
    E1_HORIZON_SECONDS,
    E1_MAX_EVENTS,
    E1_SCENARIO_ID,
    E1_WORKLOAD_ID,
    e1_scenario,
    e1_workload,
)
from experiments.result import ScientificRunResult
from experiments.scenario import Scenario
from experiments.spec import ScientificRunSpec
from experiments.workload import Workload

E3_CAMPAIGN_ID = "e3-recovery-policy"
E3_PROBE_CAMPAIGN_ID = "e3-probe"
E3_SEED = 1
E3_MAX_EVENTS = E1_MAX_EVENTS
E3_LOSS_SEQUENCE = 5000
E3_LOSS_ATTEMPT = 1
E3_LOSS_MAX_OCCURRENCES = 1
E3_LOSS_SOURCE_ID = DEFAULT_SOURCE_ID
E3_LOSS_HOP = FORWARD_HOP_RELAY_TO_EARTH
E3_SENDER_ACK_TIMEOUT_SECONDS = 8250.0
E3_GAP_REQUEST_TIMEOUT_SECONDS = 6694.0
E3_FAILURE_NONE = "NO_FAILURE"
E3_FAILURE_SILENT = "SILENT_FORWARD_DELIVERY_LOSS"
E3_CELL_ORDER = ("A", "B", "C", "D")
E3_PRIMARY_SENDER_LABEL = "B"
E3_PRIMARY_RECEIVER_LABEL = "D"

E3_LOSS_FAILURE_ID = silent_forward_delivery_loss_failure_id(
    E3_LOSS_SOURCE_ID,
    E3_LOSS_SEQUENCE,
    E3_LOSS_ATTEMPT,
    E3_LOSS_HOP,
)

E3_QUESTION = (
    "Ante la misma pérdida interna de telemetría, determinista y observable, "
    "¿cómo difieren la recuperación por timeout del emisor y la reparación "
    "selectiva de huecos del receptor en los tiempos de recuperación, la "
    "sobrecarga de sincronización y la convergencia de la aplicación?"
)

E3_DESCRIPTION = (
    f"E3 — comparación controlada de recovery. {E3_QUESTION} "
    "Experimento controlado sobre el perfil de contactos "
    "research-alessi-baseline. No es una reproducción completa de la red "
    "Alessi de nueve nodos."
)

E3_PROBE_DESCRIPTION = (
    "Sonda de E3 para tests. Conserva el escenario, la semilla, la "
    "estrategia Individual, los timeouts, la parada y el horizonte. Cambia "
    "el conteo de eventos y, con él, la secuencia perdida, para que el hueco "
    "siga teniendo un vecino anterior y uno posterior. No es el diseño "
    "oficial y no es evidencia."
)

E3_CONTROL_NOTE = (
    "Las celdas A y C no tienen pérdida. Comprueban que elegir la política "
    "no cambia el dataset ni emite tráfico de recuperación. El contraste "
    "primario es B frente a D, con la misma pérdida silenciosa."
)

E3_EXECUTION_IDENTITY_NOTE = (
    "La identidad de ejecución validada depende del escenario, de la semilla, "
    "de la estrategia y del tamaño de lote. No incluye la política de "
    "recuperación ni el plan de fallos. Las cuatro celdas comparten "
    "dataset_identity y execution_identity. Los rótulos A, B, C y D las distinguen."
)

E3_LOSS_NOTE = (
    "La pérdida es una entrega silenciosa relé → Tierra. La serialización y "
    "la propagación se completan y se suprime la entrega a la aplicación. "
    "No es un corte de contacto, ni una transmisión interrumpida, ni una "
    "pérdida de ACK. En el diseño oficial el objetivo es la secuencia 5000, "
    "intento 1, una ocurrencia. Las secuencias 4999 y 5001 pertenecen al "
    "dataset: no es un sufijo no observable."
)

E3_TIMEOUT_NOTE = (
    "El timeout de ACK del emisor es 8250 s desde last_submitted_at_sim, "
    "el completado del primer salto Marte → relé. El timeout del GapRequest "
    "es 6694 s. Son supuestos calibrados del modelo, no parámetros del "
    "análisis de Alessi."
)

E3_DIAGNOSTIC_NOTE = (
    "El reloj de pared y la cantidad de registros de traza son diagnóstico "
    "de software. No son un resultado científico."
)

E3_BYTES_NOTE = (
    "policy_recovery_network_bytes suma los saltos de la política: telemetría "
    "de reintento o de reparación, el GapRequest en sus dos saltos y el ACK "
    "asociado al evento. No inventa cabeceras. El intento perdido original "
    "no entra en ese total."
)

# Campos del episodio y de la corrida que el diseño ya nombra.
# Un episodio ausente deja el campo en None. No se rellena con 0.
E3_RESPONSE_METRICS = (
    "loss_at_sim",
    "gap_observed_at_sim",
    "recovery_triggered_at_sim",
    "earth_recovered_at_sim",
    "origin_confirmed_at_sim",
    "loss_to_trigger_seconds",
    "trigger_to_earth_recovery_seconds",
    "loss_to_earth_recovery_seconds",
    "earth_recovery_to_origin_confirmation_seconds",
    "loss_to_origin_confirmation_seconds",
    "sender_ack_timeout_count",
    "sender_retry_attempt_count",
    "receiver_gap_request_logical_count",
    "gap_request_transport_attempt_count",
    "receiver_repair_attempt_count",
    "duplicates_received_after_loss",
    "duplicates_stored_after_loss",
    "policy_recovery_forward_bytes",
    "policy_recovery_reverse_bytes",
    "policy_recovery_network_bytes",
    "recovery_data_bytes_mars_relay",
    "recovery_data_bytes_relay_earth",
    "gap_request_bytes_earth_relay",
    "gap_request_bytes_relay_mars",
    "recovery_ack_bytes_earth_relay",
    "recovery_ack_bytes_relay_mars",
    "generated",
    "earth_persisted_unique",
    "confirmed",
    "completeness",
    "confirmation_ratio",
    "final_backlog",
    "gaps_count",
    "converged",
    "time_to_convergence_seconds",
)


@dataclass(frozen=True, slots=True)
class E3Cell:
    """Una celda. El rótulo oficial no lo interpreta la campaña genérica."""

    label: str
    policy_display: str
    failure_id: str
    recovery_policy: RecoveryPolicy


E3_CELLS = (
    E3Cell("A", "Sender-driven", E3_FAILURE_NONE, RecoveryPolicy.SENDER_DRIVEN),
    E3Cell("B", "Sender-driven", E3_FAILURE_SILENT, RecoveryPolicy.SENDER_DRIVEN),
    E3Cell("C", "Receiver-driven", E3_FAILURE_NONE, RecoveryPolicy.RECEIVER_DRIVEN),
    E3Cell("D", "Receiver-driven", E3_FAILURE_SILENT, RecoveryPolicy.RECEIVER_DRIVEN),
)


@dataclass(frozen=True, slots=True)
class E3TreatmentResult:
    """Métricas de una celda, leídas del episodio y de la corrida."""

    label: str
    policy_display: str
    failure_id: str
    recovery_policy: str
    dataset_identity: str
    execution_identity: str
    episode_count: int
    loss_event_id: str | None
    loss_sequence: int | None
    loss_at_sim: float | None
    gap_observed_at_sim: float | None
    recovery_triggered_at_sim: float | None
    earth_recovered_at_sim: float | None
    origin_confirmed_at_sim: float | None
    loss_to_trigger_seconds: float | None
    trigger_to_earth_recovery_seconds: float | None
    loss_to_earth_recovery_seconds: float | None
    earth_recovery_to_origin_confirmation_seconds: float | None
    loss_to_origin_confirmation_seconds: float | None
    sender_ack_timeout_count: int | None
    sender_retry_attempt_count: int | None
    receiver_gap_request_logical_count: int | None
    gap_request_transport_attempt_count: int | None
    receiver_repair_attempt_count: int | None
    duplicates_received_after_loss: int | None
    duplicates_stored_after_loss: int | None
    policy_recovery_forward_bytes: int | None
    policy_recovery_reverse_bytes: int | None
    policy_recovery_network_bytes: int | None
    recovery_data_bytes_mars_relay: int | None
    recovery_data_bytes_relay_earth: int | None
    gap_request_bytes_earth_relay: int | None
    gap_request_bytes_relay_mars: int | None
    recovery_ack_bytes_earth_relay: int | None
    recovery_ack_bytes_relay_mars: int | None
    recovery_trigger: str | None
    generated: int
    earth_persisted_unique: int
    confirmed: int
    completeness: float | None
    confirmation_ratio: float | None
    final_backlog: int
    gaps_count: int
    converged: bool
    time_to_convergence_seconds: float | None
    operative_retry_attempts_total: int
    simulation_time: float
    trace_entry_count: int

    def metrics_dict(self) -> dict[str, object]:
        """Indicadores de E3. Un ausente queda en None."""
        payload = {
            "loss_at_sim": self.loss_at_sim,
            "gap_observed_at_sim": self.gap_observed_at_sim,
            "recovery_triggered_at_sim": self.recovery_triggered_at_sim,
            "earth_recovered_at_sim": self.earth_recovered_at_sim,
            "origin_confirmed_at_sim": self.origin_confirmed_at_sim,
            "loss_to_trigger_seconds": self.loss_to_trigger_seconds,
            "trigger_to_earth_recovery_seconds": self.trigger_to_earth_recovery_seconds,
            "loss_to_earth_recovery_seconds": self.loss_to_earth_recovery_seconds,
            "earth_recovery_to_origin_confirmation_seconds": (
                self.earth_recovery_to_origin_confirmation_seconds
            ),
            "loss_to_origin_confirmation_seconds": self.loss_to_origin_confirmation_seconds,
            "sender_ack_timeout_count": self.sender_ack_timeout_count,
            "sender_retry_attempt_count": self.sender_retry_attempt_count,
            "receiver_gap_request_logical_count": self.receiver_gap_request_logical_count,
            "gap_request_transport_attempt_count": self.gap_request_transport_attempt_count,
            "receiver_repair_attempt_count": self.receiver_repair_attempt_count,
            "duplicates_received_after_loss": self.duplicates_received_after_loss,
            "duplicates_stored_after_loss": self.duplicates_stored_after_loss,
            "policy_recovery_forward_bytes": self.policy_recovery_forward_bytes,
            "policy_recovery_reverse_bytes": self.policy_recovery_reverse_bytes,
            "policy_recovery_network_bytes": self.policy_recovery_network_bytes,
            "recovery_data_bytes_mars_relay": self.recovery_data_bytes_mars_relay,
            "recovery_data_bytes_relay_earth": self.recovery_data_bytes_relay_earth,
            "gap_request_bytes_earth_relay": self.gap_request_bytes_earth_relay,
            "gap_request_bytes_relay_mars": self.gap_request_bytes_relay_mars,
            "recovery_ack_bytes_earth_relay": self.recovery_ack_bytes_earth_relay,
            "recovery_ack_bytes_relay_mars": self.recovery_ack_bytes_relay_mars,
            "generated": self.generated,
            "earth_persisted_unique": self.earth_persisted_unique,
            "confirmed": self.confirmed,
            "completeness": self.completeness,
            "confirmation_ratio": self.confirmation_ratio,
            "final_backlog": self.final_backlog,
            "gaps_count": self.gaps_count,
            "converged": self.converged,
            "time_to_convergence_seconds": self.time_to_convergence_seconds,
        }
        return {name: payload[name] for name in E3_RESPONSE_METRICS}


@dataclass(frozen=True, slots=True)
class E3Result:
    """Vista de E3. Compara las celdas con pérdida y no las ordena."""

    campaign_id: str
    description: str
    question: str
    campaign_identity: str
    dataset_identity: str
    execution_identity: str
    official: bool
    loss_sequence: int
    loss_failure_id: str
    treatments: tuple[E3TreatmentResult, ...]
    wall_execution_seconds: float | None = None

    @property
    def trace_entries_total(self) -> int:
        return sum(item.trace_entry_count for item in self.treatments)

    def treatment(self, label: str) -> E3TreatmentResult:
        for item in self.treatments:
            if item.label == label:
                return item
        raise ValueError(f"rótulo desconocido de E3: {label}")

    @property
    def sender_loss(self) -> E3TreatmentResult:
        return self.treatment(E3_PRIMARY_SENDER_LABEL)

    @property
    def receiver_loss(self) -> E3TreatmentResult:
        return self.treatment(E3_PRIMARY_RECEIVER_LABEL)


def observable_loss_sequence(max_events: int) -> int:
    """Secuencia intermedia: hay un vecino anterior y uno posterior."""
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 3:
        raise ValueError("un hueco observable requiere al menos 3 eventos")
    sequence = max_events // 2
    if sequence <= 0 or sequence >= max_events - 1:
        raise ValueError("la secuencia perdida no puede ser un extremo")
    return sequence


def e3_scenario() -> Scenario:
    """El mismo escenario que E1. No se copian los contactos."""
    return e1_scenario()


def e3_workload(*, max_events: int = E3_MAX_EVENTS) -> Workload:
    """Telemetría normal Alessi. El diseño oficial usa 10000 eventos."""
    return e1_workload(max_events=max_events)


def e3_failure_plan(*, sequence_number: int | None) -> FailurePlan:
    """Plan vacío, o una pérdida silenciosa de esa secuencia."""
    if sequence_number is None:
        return FailurePlan()
    return FailurePlan(
        silent_forward_delivery_losses=(
            SilentForwardDeliveryLossFailure(
                failure_id=silent_forward_delivery_loss_failure_id(
                    E3_LOSS_SOURCE_ID,
                    sequence_number,
                    E3_LOSS_ATTEMPT,
                    E3_LOSS_HOP,
                ),
                source_id=E3_LOSS_SOURCE_ID,
                sequence_number=sequence_number,
                telemetry_attempt_number=E3_LOSS_ATTEMPT,
                hop=E3_LOSS_HOP,
                max_occurrences=E3_LOSS_MAX_OCCURRENCES,
            ),
        )
    )


def build_e3_campaign() -> CampaignSpec:
    """Diseño oficial. Cuatro celdas, en el orden A, B, C, D."""
    if observable_loss_sequence(E3_MAX_EVENTS) != E3_LOSS_SEQUENCE:
        raise ValueError("la secuencia oficial 5000 debe ser el índice intermedio")
    return _campaign(
        campaign_id=E3_CAMPAIGN_ID,
        description=E3_DESCRIPTION,
        max_events=E3_MAX_EVENTS,
        loss_sequence=E3_LOSS_SEQUENCE,
    )


def build_e3_probe_campaign(*, max_events: int) -> CampaignSpec:
    """Misma estructura con otro conteo. No es el diseño oficial."""
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 3:
        raise ValueError("max_events de la sonda debe ser un entero >= 3")
    if max_events == E3_MAX_EVENTS:
        raise ValueError("la sonda no usa el conteo oficial; el diseño es build_e3_campaign")
    return _campaign(
        campaign_id=E3_PROBE_CAMPAIGN_ID,
        description=E3_PROBE_DESCRIPTION,
        max_events=max_events,
        loss_sequence=observable_loss_sequence(max_events),
    )


def e3_result(
    spec: CampaignSpec,
    campaign: CampaignResult,
    *,
    wall_execution_seconds: float | None = None,
) -> E3Result:
    """Arma la vista. Exige las cuatro celdas y la misma pérdida en B y D."""
    if tuple(run.label for run in spec.runs) != E3_CELL_ORDER:
        raise ValueError("E3 requiere las celdas A, B, C y D, en ese orden")
    if tuple(run.label for run in campaign.runs) != E3_CELL_ORDER:
        raise ValueError("el resultado de E3 no sigue el orden A, B, C, D")
    if campaign.campaign_id != spec.campaign_id:
        raise ValueError("la campaña ejecutada no es la especificación recibida")
    if spec.campaign_id not in {E3_CAMPAIGN_ID, E3_PROBE_CAMPAIGN_ID}:
        raise ValueError("la especificación no es la campaña oficial de E3 ni su sonda")
    treatments: list[E3TreatmentResult] = []
    for planned, finished in zip(spec.runs, campaign.runs, strict=True):
        result = finished.result
        if result is None:
            raise ValueError(
                f"la corrida {finished.label} falló: "
                f"{finished.error_type}: {finished.error_message}"
            )
        if result.engine_status != SimulationStatus.COMPLETED.value:
            raise ValueError(f"la corrida {finished.label} no terminó COMPLETED")
        if result.recovery_policy != planned.spec.recovery_policy.value:
            raise ValueError("la política ejecutada no coincide con la especificación")
        treatments.append(_treatment_result(finished.label, result))
    dataset_ids = {item.dataset_identity for item in treatments}
    if len(dataset_ids) != 1:
        raise ValueError("E3 exige la misma dataset_identity en las cuatro celdas")
    execution_ids = {item.execution_identity for item in treatments}
    if len(execution_ids) != 1:
        raise ValueError(
            "la execution_identity validada no distingue la política; "
            "las cuatro celdas deben compartirla"
        )
    by_label = {item.label: item for item in treatments}
    sender = by_label[E3_PRIMARY_SENDER_LABEL]
    receiver = by_label[E3_PRIMARY_RECEIVER_LABEL]
    if sender.episode_count != 1 or receiver.episode_count != 1:
        raise ValueError("B y D deben registrar exactamente un episodio")
    if by_label["A"].episode_count != 0 or by_label["C"].episode_count != 0:
        raise ValueError("A y C no deben registrar un episodio de recuperación")
    if sender.loss_event_id != receiver.loss_event_id:
        raise ValueError("B y D no perdieron el mismo event_id")
    if sender.loss_sequence != receiver.loss_sequence:
        raise ValueError("B y D no perdieron la misma secuencia")
    if sender.loss_at_sim != receiver.loss_at_sim:
        raise ValueError("B y D no perdieron el evento en el mismo instante")
    if sender.loss_sequence is None or sender.loss_event_id is None:
        raise ValueError("el episodio de B no identifica el evento perdido")
    loss_plan = spec.runs[1].spec.failure_plan.silent_forward_delivery_losses
    if len(loss_plan) != 1:
        raise ValueError("B debe declarar exactamente una pérdida silenciosa")
    return E3Result(
        campaign_id=campaign.campaign_id,
        description=campaign.description,
        question=E3_QUESTION,
        campaign_identity=campaign.campaign_identity,
        dataset_identity=treatments[0].dataset_identity,
        execution_identity=treatments[0].execution_identity,
        official=spec.campaign_id == E3_CAMPAIGN_ID,
        loss_sequence=sender.loss_sequence,
        loss_failure_id=loss_plan[0].failure_id,
        treatments=tuple(treatments),
        wall_execution_seconds=wall_execution_seconds,
    )


def format_e3(result: E3Result) -> str:
    """Tabla del contraste primario. No declara una política ganadora."""
    encabezado = (
        "Política",
        "Pérdida→Disparo",
        "Pérdida→Tierra",
        "Pérdida→Marte",
        "Bytes de recovery",
    )
    filas = [encabezado]
    for item in (result.sender_loss, result.receiver_loss):
        filas.append(
            (
                item.policy_display,
                _cantidad(item.loss_to_trigger_seconds),
                _cantidad(item.loss_to_earth_recovery_seconds),
                _cantidad(item.loss_to_origin_confirmation_seconds),
                _entero_o_ausente(item.policy_recovery_network_bytes),
            )
        )
    anchos = [max(len(fila[col]) for fila in filas) for col in range(len(encabezado))]
    lineas = [
        "E3 — Comparación controlada de recovery",
        "",
        result.question,
        "",
        f"Campaña: {result.campaign_id}",
        f"Identidad de campaña: {result.campaign_identity}",
        f"Identidad de dataset: {result.dataset_identity}",
        f"Identidad de ejecución: {result.execution_identity}",
        E3_EXECUTION_IDENTITY_NOTE,
        "",
        "Experimento controlado sobre research-alessi-baseline.",
        "No es una reproducción completa de la red Alessi de nueve nodos.",
        "Estrategia: Individual.",
        f"Semilla: {E3_SEED}.",
        f"Pérdida: {result.loss_failure_id}.",
        (
            f"Secuencia {result.loss_sequence}, intento {E3_LOSS_ATTEMPT}, "
            f"hop {E3_LOSS_HOP}, una ocurrencia."
        ),
        E3_LOSS_NOTE if result.official else (
            "Sonda. La secuencia perdida no es la 5000 del diseño oficial. "
            "Sigue siendo un hueco interno, con vecino anterior y posterior."
        ),
        E3_TIMEOUT_NOTE,
        f"Parada: {StopPolicy.PROFILE_HORIZON_SETTLED.value}. Horizonte: {E1_HORIZON_SECONDS:.0f} s.",
        "",
        "Contraste primario. La misma pérdida silenciosa bajo las dos políticas.",
        "",
    ]
    for fila in filas:
        lineas.append("  ".join(celda.ljust(anchos[i]) for i, celda in enumerate(fila)))
    lineas.append("")
    lineas.append("Pérdida→Disparo es loss_to_trigger_seconds.")
    lineas.append("Pérdida→Tierra es loss_to_earth_recovery_seconds.")
    lineas.append("Pérdida→Marte es loss_to_origin_confirmation_seconds.")
    lineas.append("Bytes de recovery es policy_recovery_network_bytes.")
    lineas.append(E3_BYTES_NOTE)
    lineas.append("")
    emisor = result.sender_loss
    receptor = result.receiver_loss
    lineas.append(
        "Reintentos del emisor: "
        f"Sender-driven {_entero_o_ausente(emisor.sender_retry_attempt_count)}; "
        f"Receiver-driven {_entero_o_ausente(receptor.sender_retry_attempt_count)}."
    )
    lineas.append(
        "GapRequests: "
        f"Sender-driven {_entero_o_ausente(emisor.receiver_gap_request_logical_count)}; "
        f"Receiver-driven {_entero_o_ausente(receptor.receiver_gap_request_logical_count)}."
    )
    lineas.append(
        "Reparaciones: "
        f"Sender-driven {_entero_o_ausente(emisor.receiver_repair_attempt_count)}; "
        f"Receiver-driven {_entero_o_ausente(receptor.receiver_repair_attempt_count)}."
    )
    lineas.append("")
    lineas.append(E3_CONTROL_NOTE)
    for label in ("A", "C"):
        control = result.treatment(label)
        lineas.append(
            f"{label} {control.policy_display}: episodios {control.episode_count}; "
            "latencias no definidas."
        )
    lineas.append("")
    lineas.append("Diagnóstico de ejecución. No es resultado científico.")
    for item in result.treatments:
        lineas.append(
            f"{item.label} {item.policy_display}: tiempo simulado "
            f"{_numero(item.simulation_time)} s; traza {item.trace_entry_count} registros"
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


def e3_result_payload(result: E3Result) -> dict[str, object]:
    """JSON de la vista. Los floats conservan el valor de dominio."""
    emisor = result.sender_loss
    receptor = result.receiver_loss
    return {
        "experiment": "E3",
        "title": "E3 — Comparación controlada de recovery",
        "question": result.question,
        "campaign_id": result.campaign_id,
        "description": result.description,
        "campaign_identity": result.campaign_identity,
        "dataset_identity": result.dataset_identity,
        "execution_identity": result.execution_identity,
        "execution_identity_note": E3_EXECUTION_IDENTITY_NOTE,
        "official": result.official,
        "controlled_experiment": True,
        "scenario_id": E1_SCENARIO_ID,
        "workload_id": E1_WORKLOAD_ID,
        "strategy_type": STRATEGY_TYPE_INDIVIDUAL,
        "seed": E3_SEED,
        "statistical_analysis": "not_implemented",
        "statistical_note": (
            "Comparación descriptiva de las celdas. No hay inferencia estadística "
            "ni un orden entre políticas."
        ),
        "loss": {
            "failure_id": result.loss_failure_id,
            "source_id": E3_LOSS_SOURCE_ID,
            "sequence_number": result.loss_sequence,
            "telemetry_attempt_number": E3_LOSS_ATTEMPT,
            "hop": E3_LOSS_HOP,
            "max_occurrences": E3_LOSS_MAX_OCCURRENCES,
            "event_id": emisor.loss_event_id,
            "loss_at_sim": emisor.loss_at_sim,
            "note": E3_LOSS_NOTE if result.official else E3_PROBE_DESCRIPTION,
        },
        "timeouts": {
            "sender_ack_timeout_seconds": E3_SENDER_ACK_TIMEOUT_SECONDS,
            "sender_ack_timeout_reference": "last_submitted_at_sim",
            "gap_request_timeout_seconds": E3_GAP_REQUEST_TIMEOUT_SECONDS,
            "note": E3_TIMEOUT_NOTE,
        },
        "stop_policy": StopPolicy.PROFILE_HORIZON_SETTLED.value,
        "horizon_seconds": E1_HORIZON_SECONDS,
        "primary_contrast": {
            "sender_label": E3_PRIMARY_SENDER_LABEL,
            "receiver_label": E3_PRIMARY_RECEIVER_LABEL,
            "loss_to_trigger_seconds": {
                "sender-driven": emisor.loss_to_trigger_seconds,
                "receiver-driven": receptor.loss_to_trigger_seconds,
            },
            "loss_to_earth_recovery_seconds": {
                "sender-driven": emisor.loss_to_earth_recovery_seconds,
                "receiver-driven": receptor.loss_to_earth_recovery_seconds,
            },
            "loss_to_origin_confirmation_seconds": {
                "sender-driven": emisor.loss_to_origin_confirmation_seconds,
                "receiver-driven": receptor.loss_to_origin_confirmation_seconds,
            },
            "policy_recovery_network_bytes": {
                "sender-driven": emisor.policy_recovery_network_bytes,
                "receiver-driven": receptor.policy_recovery_network_bytes,
            },
            "sender_retry_attempt_count": {
                "sender-driven": emisor.sender_retry_attempt_count,
                "receiver-driven": receptor.sender_retry_attempt_count,
            },
            "receiver_gap_request_logical_count": {
                "sender-driven": emisor.receiver_gap_request_logical_count,
                "receiver-driven": receptor.receiver_gap_request_logical_count,
            },
            "receiver_repair_attempt_count": {
                "sender-driven": emisor.receiver_repair_attempt_count,
                "receiver-driven": receptor.receiver_repair_attempt_count,
            },
        },
        "treatments": [
            {
                "label": item.label,
                "policy_display": item.policy_display,
                "failure_id": item.failure_id,
                "recovery_policy": item.recovery_policy,
                "dataset_identity": item.dataset_identity,
                "execution_identity": item.execution_identity,
                "episode_count": item.episode_count,
                "loss_event_id": item.loss_event_id,
                "loss_sequence": item.loss_sequence,
                "recovery_trigger": item.recovery_trigger,
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
            "note": E3_DIAGNOSTIC_NOTE,
        },
    }


def e3_result_json(result: E3Result) -> str:
    """Texto JSON de ``e3_result_payload``, con caracteres Unicode."""
    return json.dumps(e3_result_payload(result), ensure_ascii=False, indent=2)


def _campaign(
    *,
    campaign_id: str,
    description: str,
    max_events: int,
    loss_sequence: int,
) -> CampaignSpec:
    scenario = e3_scenario()
    workload = e3_workload(max_events=max_events)
    quiet = e3_failure_plan(sequence_number=None)
    loss = e3_failure_plan(sequence_number=loss_sequence)
    sender_retry = RetryPolicy(ack_timeout_seconds=E3_SENDER_ACK_TIMEOUT_SECONDS)
    # Receiver-driven no programa ACK_TIMEOUT. Este valor no es el timeout de E3.
    receiver_retry = RetryPolicy(ack_timeout_seconds=DEFAULT_ACK_TIMEOUT_SECONDS)
    runs: list[CampaignRunSpec] = []
    for cell in E3_CELLS:
        if cell.recovery_policy is RecoveryPolicy.SENDER_DRIVEN:
            runs.append(
                CampaignRunSpec(
                    label=cell.label,
                    spec=_sender_spec(
                        scenario=scenario,
                        workload=workload,
                        failure_plan=loss if cell.failure_id == E3_FAILURE_SILENT else quiet,
                        retry_policy=sender_retry,
                    ),
                )
            )
            continue
        runs.append(
            CampaignRunSpec(
                label=cell.label,
                spec=_receiver_spec(
                    scenario=scenario,
                    workload=workload,
                    failure_plan=loss if cell.failure_id == E3_FAILURE_SILENT else quiet,
                    retry_policy=receiver_retry,
                ),
            )
        )
    return CampaignSpec(campaign_id=campaign_id, description=description, runs=tuple(runs))


def _sender_spec(
    *,
    scenario: Scenario,
    workload: Workload,
    failure_plan: FailurePlan,
    retry_policy: RetryPolicy,
) -> ScientificRunSpec:
    return ScientificRunSpec(
        scenario=scenario,
        workload=workload,
        seed=E3_SEED,
        strategy_type=STRATEGY_TYPE_INDIVIDUAL,
        recovery_policy=RecoveryPolicy.SENDER_DRIVEN,
        retry_policy=retry_policy,
        failure_plan=failure_plan,
        stop_policy=StopPolicy.PROFILE_HORIZON_SETTLED,
        trace_level=TraceLevel.SCIENTIFIC,
    )


def _receiver_spec(
    *,
    scenario: Scenario,
    workload: Workload,
    failure_plan: FailurePlan,
    retry_policy: RetryPolicy,
) -> ScientificRunSpec:
    return ScientificRunSpec(
        scenario=scenario,
        workload=workload,
        seed=E3_SEED,
        strategy_type=STRATEGY_TYPE_INDIVIDUAL,
        recovery_policy=RecoveryPolicy.RECEIVER_DRIVEN,
        retry_policy=retry_policy,
        failure_plan=failure_plan,
        stop_policy=StopPolicy.PROFILE_HORIZON_SETTLED,
        trace_level=TraceLevel.SCIENTIFIC,
        gap_request_timeout_seconds=E3_GAP_REQUEST_TIMEOUT_SECONDS,
    )


def _treatment_result(label: str, result: ScientificRunResult) -> E3TreatmentResult:
    cell = _cell_for(label)
    metrics = result.metrics
    episode = _single_episode(metrics.episodes)
    return E3TreatmentResult(
        label=label,
        policy_display=cell.policy_display,
        failure_id=cell.failure_id,
        recovery_policy=result.recovery_policy,
        dataset_identity=result.dataset_identity,
        execution_identity=result.execution_identity,
        episode_count=len(metrics.episodes),
        loss_event_id=None if episode is None else episode.event_id,
        loss_sequence=None if episode is None else episode.sequence_number,
        loss_at_sim=None if episode is None else episode.loss_at_sim,
        gap_observed_at_sim=None if episode is None else episode.gap_observed_at_sim,
        recovery_triggered_at_sim=None if episode is None else episode.recovery_triggered_at_sim,
        earth_recovered_at_sim=None if episode is None else episode.earth_recovered_at_sim,
        origin_confirmed_at_sim=None if episode is None else episode.origin_confirmed_at_sim,
        loss_to_trigger_seconds=None if episode is None else episode.loss_to_trigger_seconds,
        trigger_to_earth_recovery_seconds=(
            None if episode is None else episode.trigger_to_earth_recovery_seconds
        ),
        loss_to_earth_recovery_seconds=(
            None if episode is None else episode.loss_to_earth_recovery_seconds
        ),
        earth_recovery_to_origin_confirmation_seconds=(
            None
            if episode is None
            else episode.earth_recovery_to_origin_confirmation_seconds
        ),
        loss_to_origin_confirmation_seconds=(
            None if episode is None else episode.loss_to_origin_confirmation_seconds
        ),
        sender_ack_timeout_count=None if episode is None else episode.sender_ack_timeout_count,
        sender_retry_attempt_count=(
            None if episode is None else episode.sender_retry_attempt_count
        ),
        receiver_gap_request_logical_count=(
            None if episode is None else episode.receiver_gap_request_logical_count
        ),
        gap_request_transport_attempt_count=(
            None if episode is None else episode.gap_request_transport_attempt_count
        ),
        receiver_repair_attempt_count=(
            None if episode is None else episode.receiver_repair_attempt_count
        ),
        duplicates_received_after_loss=(
            None if episode is None else episode.duplicates_received_after_loss
        ),
        duplicates_stored_after_loss=(
            None if episode is None else episode.duplicates_stored_after_loss
        ),
        policy_recovery_forward_bytes=(
            None if episode is None else episode.policy_recovery_forward_bytes
        ),
        policy_recovery_reverse_bytes=(
            None if episode is None else episode.policy_recovery_reverse_bytes
        ),
        policy_recovery_network_bytes=(
            None if episode is None else episode.policy_recovery_network_bytes
        ),
        recovery_data_bytes_mars_relay=(
            None if episode is None else episode.recovery_data_bytes_mars_relay
        ),
        recovery_data_bytes_relay_earth=(
            None if episode is None else episode.recovery_data_bytes_relay_earth
        ),
        gap_request_bytes_earth_relay=(
            None if episode is None else episode.gap_request_bytes_earth_relay
        ),
        gap_request_bytes_relay_mars=(
            None if episode is None else episode.gap_request_bytes_relay_mars
        ),
        recovery_ack_bytes_earth_relay=(
            None if episode is None else episode.recovery_ack_bytes_earth_relay
        ),
        recovery_ack_bytes_relay_mars=(
            None if episode is None else episode.recovery_ack_bytes_relay_mars
        ),
        recovery_trigger=None if episode is None else episode.recovery_trigger,
        generated=metrics.generated,
        earth_persisted_unique=metrics.earth_persisted_unique,
        confirmed=metrics.confirmed,
        completeness=metrics.completeness,
        confirmation_ratio=metrics.confirmation_ratio,
        final_backlog=metrics.final_backlog,
        gaps_count=metrics.gaps_count,
        converged=metrics.converged,
        time_to_convergence_seconds=metrics.convergence.time_to_convergence_seconds,
        operative_retry_attempts_total=metrics.retry_attempts_total,
        simulation_time=result.simulation_time,
        trace_entry_count=result.trace_entry_count,
    )


def _single_episode(
    episodes: tuple[RecoveryEpisodeResult, ...],
) -> RecoveryEpisodeResult | None:
    if not episodes:
        return None
    if len(episodes) != 1:
        raise ValueError("E3 espera cero episodios o exactamente uno")
    return episodes[0]


def _cell_for(label: str) -> E3Cell:
    for cell in E3_CELLS:
        if cell.label == label:
            return cell
    raise ValueError(f"rótulo desconocido de E3: {label}")


def _numero(value: float) -> str:
    text = f"{value:.9f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _cantidad(value: float | None) -> str:
    if value is None:
        return "no definido"
    return _numero(value)


def _entero_o_ausente(value: int | None) -> str:
    if value is None:
        return "no definido"
    return str(value)
