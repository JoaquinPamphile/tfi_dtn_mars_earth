"""Sensibilidad de E3 a la posición de una pérdida silenciosa.

No es E4 y no reemplaza el diseño oficial. Reutiliza el escenario, el
workload de 10000 eventos, la semilla, la estrategia Individual, los
timeouts y las métricas de E3. Cambia solo la secuencia perdida.

Las 10000 secuencias se generan antes del primer contacto Marte → relé
y salen en esa primera ventana. Su entrega en Tierra cabe en la
propagación de una sola ventana relé → Tierra, entre unos 28380 s y
28708 s. La posición solo se desliza dentro de esa cohorte. No hay una
secuencia de este workload que caiga en otra ventana de contacto.

Por eso las posiciones son tres, todas con vecino anterior y posterior:
la primera observable, la oficial 5000 y la última observable. No se
repiten los controles sin falla. No se amplía el volumen: desbordar la
primera ventana Marte → relé exigiría más de 45776 eventos y haría que
la generación se solape con los contactos.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from core.domain.retry import DEFAULT_ACK_TIMEOUT_SECONDS, RetryPolicy
from core.failure.plan import FailurePlan
from core.recovery.policy import RecoveryPolicy
from core.simulation.engine import SimulationStatus
from core.stopping.policy import StopPolicy
from core.sync.strategy import STRATEGY_TYPE_INDIVIDUAL
from core.trace.level import TraceLevel

from experiments.campaign import CampaignResult, CampaignRunSpec, CampaignSpec
from experiments.e3 import (
    E3_CAMPAIGN_ID,
    E3_GAP_REQUEST_TIMEOUT_SECONDS,
    E3_LOSS_SEQUENCE,
    E3_MAX_EVENTS,
    E3_SEED,
    E3_SENDER_ACK_TIMEOUT_SECONDS,
    e3_failure_plan,
    e3_scenario,
    e3_workload,
)
from experiments.result import ScientificRunResult
from experiments.scenario import Scenario
from experiments.spec import ScientificRunSpec
from experiments.workload import Workload

E3_SENSITIVITY_CAMPAIGN_ID = "e3-loss-position-sensitivity"
E3_SENSITIVITY_SEQUENCES = (1, E3_LOSS_SEQUENCE, E3_MAX_EVENTS - 2)
E3_SENSITIVITY_RUNS_PER_POSITION = 2

E3_SENSITIVITY_QUESTION = (
    "¿El contraste observado entre sender-driven y receiver-driven en E3 "
    "se mantiene cuando la misma pérdida silenciosa ocurre en diferentes "
    "posiciones temporales del flujo?"
)

E3_SENSITIVITY_BANNER = (
    "Análisis de sensibilidad de E3.\n"
    "No constituye un experimento E4."
)

E3_SENSITIVITY_COHORT_NOTE = (
    "Cohorte única. El último evento se genera en 20477.952 s, antes del "
    "primer contacto Marte → relé en 27000 s. Los 10000 eventos caben en "
    "esa ventana, que cierra en 28500 s. La entrega en Tierra del intento 1 "
    "queda entre unos 28380 s y 28708 s, dentro de la propagación de la "
    "ventana relé → Tierra 22500–27600 s. La ventana siguiente abre en "
    "29400 s. Estas posiciones no cambian de ventana de contacto."
)

E3_SENSITIVITY_VOLUME_NOTE = (
    "El volumen permanece en 10000 eventos. Para que una pérdida cayera en "
    "la segunda ventana Marte → relé harían falta más de 45776 eventos a "
    "esta tasa. Esa ampliación haría que la generación se solape con los "
    "contactos y dejaría de ser el mismo backlog de E3."
)

E3_SENSITIVITY_POSITION_NOTE = (
    "1 es el primer hueco interno. 5000 es la secuencia oficial de E3. "
    "9998 es el último hueco interno: existen 9997 y 9999."
)

E3_SENSITIVITY_METRICS = (
    "loss_to_trigger_seconds",
    "loss_to_earth_recovery_seconds",
    "loss_to_origin_confirmation_seconds",
    "policy_recovery_network_bytes",
    "sender_retry_attempt_count",
    "receiver_gap_request_logical_count",
    "receiver_repair_attempt_count",
)

E3_SENSITIVITY_DIAGNOSTIC_NOTE = (
    "El reloj de pared y la cantidad de registros de traza son diagnóstico "
    "de software. No son un resultado científico."
)


@dataclass(frozen=True, slots=True)
class E3SensitivitySide:
    """Métricas ya calculadas de un miembro de la pareja."""

    recovery_policy: str
    episode_count: int
    loss_event_id: str | None
    loss_sequence: int | None
    loss_at_sim: float | None
    loss_to_trigger_seconds: float | None
    loss_to_earth_recovery_seconds: float | None
    loss_to_origin_confirmation_seconds: float | None
    policy_recovery_network_bytes: int | None
    sender_retry_attempt_count: int | None
    receiver_gap_request_logical_count: int | None
    receiver_repair_attempt_count: int | None

    def metrics_dict(self) -> dict[str, object]:
        payload = {
            "loss_to_trigger_seconds": self.loss_to_trigger_seconds,
            "loss_to_earth_recovery_seconds": self.loss_to_earth_recovery_seconds,
            "loss_to_origin_confirmation_seconds": self.loss_to_origin_confirmation_seconds,
            "policy_recovery_network_bytes": self.policy_recovery_network_bytes,
            "sender_retry_attempt_count": self.sender_retry_attempt_count,
            "receiver_gap_request_logical_count": self.receiver_gap_request_logical_count,
            "receiver_repair_attempt_count": self.receiver_repair_attempt_count,
        }
        return {name: payload[name] for name in E3_SENSITIVITY_METRICS}


@dataclass(frozen=True, slots=True)
class E3SensitivityPosition:
    """Una secuencia perdida, vista en las dos políticas."""

    sequence_number: int
    valid: bool
    invalid_reason: str | None
    loss_event_id: str | None
    loss_at_sim: float | None
    sender: E3SensitivitySide
    receiver: E3SensitivitySide

    def relations(self) -> dict[str, str]:
        """Sentido del contraste. No ordena las políticas."""
        if not self.valid:
            return {}
        return {
            "trigger": _relacion_tiempo(
                self.sender.loss_to_trigger_seconds,
                self.receiver.loss_to_trigger_seconds,
                antes="el receptor dispara antes",
                despues="el receptor dispara después",
                igual="el receptor dispara al mismo tiempo",
            ),
            "earth": _relacion_tiempo(
                self.sender.loss_to_earth_recovery_seconds,
                self.receiver.loss_to_earth_recovery_seconds,
                antes="el receptor recupera Tierra antes",
                despues="el receptor recupera Tierra después",
                igual="el receptor recupera Tierra al mismo tiempo",
            ),
            "origin": _relacion_tiempo(
                self.sender.loss_to_origin_confirmation_seconds,
                self.receiver.loss_to_origin_confirmation_seconds,
                antes="el receptor confirma Marte antes",
                despues="el receptor confirma Marte después",
                igual="el receptor confirma Marte al mismo tiempo",
            ),
            "bytes": _relacion_bytes(
                self.sender.policy_recovery_network_bytes,
                self.receiver.policy_recovery_network_bytes,
            ),
        }


@dataclass(frozen=True, slots=True)
class E3SensitivityResult:
    """Vista aparte de ``E3Result``. Una fila por posición de pérdida."""

    campaign_id: str
    description: str
    question: str
    campaign_identity: str
    dataset_identity: str
    positions: tuple[E3SensitivityPosition, ...]
    trace_entries: tuple[int, ...] = ()
    wall_execution_seconds: float | None = None

    @property
    def trace_entries_total(self) -> int:
        return sum(self.trace_entries)


def build_e3_sensitivity_campaign() -> CampaignSpec:
    """Tres parejas. No incluye los controles A y C ni cambia E3 oficial."""
    _require_internal_sequences(E3_SENSITIVITY_SEQUENCES)
    scenario = e3_scenario()
    workload = e3_workload(max_events=E3_MAX_EVENTS)
    sender_retry = RetryPolicy(ack_timeout_seconds=E3_SENDER_ACK_TIMEOUT_SECONDS)
    receiver_retry = RetryPolicy(ack_timeout_seconds=DEFAULT_ACK_TIMEOUT_SECONDS)
    runs: list[CampaignRunSpec] = []
    for sequence in E3_SENSITIVITY_SEQUENCES:
        loss = e3_failure_plan(sequence_number=sequence)
        runs.append(
            CampaignRunSpec(
                label=_label(sequence, "sender"),
                spec=_sender_spec(
                    scenario=scenario,
                    workload=workload,
                    failure_plan=loss,
                    retry_policy=sender_retry,
                ),
            )
        )
        runs.append(
            CampaignRunSpec(
                label=_label(sequence, "receiver"),
                spec=_receiver_spec(
                    scenario=scenario,
                    workload=workload,
                    failure_plan=loss,
                    retry_policy=receiver_retry,
                ),
            )
        )
    return CampaignSpec(
        campaign_id=E3_SENSITIVITY_CAMPAIGN_ID,
        description=(
            f"{E3_SENSITIVITY_BANNER.replace(chr(10), ' ')} {E3_SENSITIVITY_QUESTION}"
        ),
        runs=tuple(runs),
    )


def e3_sensitivity_result(
    spec: CampaignSpec,
    campaign: CampaignResult,
    *,
    wall_execution_seconds: float | None = None,
) -> E3SensitivityResult:
    """Lee las métricas de cada pareja. Una pareja desigual queda inválida."""
    expected = tuple(
        _label(sequence, side)
        for sequence in E3_SENSITIVITY_SEQUENCES
        for side in ("sender", "receiver")
    )
    if tuple(run.label for run in spec.runs) != expected:
        raise ValueError("la sensibilidad no tiene las parejas previstas")
    if tuple(run.label for run in campaign.runs) != expected:
        raise ValueError("el resultado no sigue el orden de las parejas")
    if spec.campaign_id != E3_SENSITIVITY_CAMPAIGN_ID:
        raise ValueError("la especificación no es la sensibilidad de E3")
    if spec.campaign_id == E3_CAMPAIGN_ID:
        raise ValueError("la sensibilidad no puede usar la campaña oficial de E3")
    sides: list[E3SensitivitySide] = []
    traces: list[int] = []
    for finished in campaign.runs:
        result = finished.result
        if result is None:
            raise ValueError(
                f"la corrida {finished.label} falló: "
                f"{finished.error_type}: {finished.error_message}"
            )
        if result.engine_status != SimulationStatus.COMPLETED.value:
            raise ValueError(f"la corrida {finished.label} no terminó COMPLETED")
        sides.append(_side(result))
        traces.append(result.trace_entry_count)
    positions: list[E3SensitivityPosition] = []
    for index, sequence in enumerate(E3_SENSITIVITY_SEQUENCES):
        sender = sides[index * 2]
        receiver = sides[index * 2 + 1]
        positions.append(_position(sequence, sender, receiver))
    first = campaign.runs[0].result
    if first is None:
        raise ValueError("la primera corrida no tiene resultado")
    return E3SensitivityResult(
        campaign_id=campaign.campaign_id,
        description=campaign.description,
        question=E3_SENSITIVITY_QUESTION,
        campaign_identity=campaign.campaign_identity,
        dataset_identity=first.dataset_identity,
        positions=tuple(positions),
        trace_entries=tuple(traces),
        wall_execution_seconds=wall_execution_seconds,
    )


def format_e3_sensitivity(result: E3SensitivityResult) -> str:
    """Tabla por posición. Describe el sentido del contraste."""
    encabezado = (
        "Seq",
        "Instante de pérdida",
        "Emisor Pérdida→Disparo",
        "Receptor Pérdida→Disparo",
        "Emisor Pérdida→Tierra",
        "Receptor Pérdida→Tierra",
        "Emisor bytes",
        "Receptor bytes",
        "Emisor Pérdida→Marte",
        "Receptor Pérdida→Marte",
    )
    filas = [encabezado]
    for item in result.positions:
        filas.append(
            (
                str(item.sequence_number),
                _cantidad(item.loss_at_sim) if item.valid else "inválida",
                _cantidad(item.sender.loss_to_trigger_seconds),
                _cantidad(item.receiver.loss_to_trigger_seconds),
                _cantidad(item.sender.loss_to_earth_recovery_seconds),
                _cantidad(item.receiver.loss_to_earth_recovery_seconds),
                _entero(item.sender.policy_recovery_network_bytes),
                _entero(item.receiver.policy_recovery_network_bytes),
                _cantidad(item.sender.loss_to_origin_confirmation_seconds),
                _cantidad(item.receiver.loss_to_origin_confirmation_seconds),
            )
        )
    anchos = [max(len(fila[col]) for fila in filas) for col in range(len(encabezado))]
    lineas = [
        E3_SENSITIVITY_BANNER,
        "",
        result.question,
        "",
        f"Campaña: {result.campaign_id}",
        f"Identidad de campaña: {result.campaign_identity}",
        f"Identidad de dataset: {result.dataset_identity}",
        "No modifica la campaña oficial e3-recovery-policy.",
        "",
        E3_SENSITIVITY_COHORT_NOTE,
        E3_SENSITIVITY_POSITION_NOTE,
        E3_SENSITIVITY_VOLUME_NOTE,
        (
            f"Posiciones: {len(E3_SENSITIVITY_SEQUENCES)}. "
            f"Corridas: {len(E3_SENSITIVITY_SEQUENCES) * E3_SENSITIVITY_RUNS_PER_POSITION}. "
            f"Eventos por corrida: {E3_MAX_EVENTS}."
        ),
        "",
    ]
    for fila in filas:
        lineas.append("  ".join(celda.ljust(anchos[i]) for i, celda in enumerate(fila)))
    lineas.append("")
    lineas.append("Pérdida→Disparo es loss_to_trigger_seconds.")
    lineas.append("Pérdida→Tierra es loss_to_earth_recovery_seconds.")
    lineas.append("Pérdida→Marte es loss_to_origin_confirmation_seconds.")
    lineas.append("Bytes es policy_recovery_network_bytes.")
    lineas.append("")
    for item in result.positions:
        if not item.valid:
            lineas.append(
                f"Secuencia {item.sequence_number}: pareja inválida. {item.invalid_reason}"
            )
            continue
        relaciones = item.relations()
        lineas.append(
            f"Secuencia {item.sequence_number}: {relaciones['trigger']}; "
            f"{relaciones['earth']}; {relaciones['bytes']}; {relaciones['origin']}."
        )
        lineas.append(
            f"Secuencia {item.sequence_number}: reintentos del emisor "
            f"{_entero(item.sender.sender_retry_attempt_count)}; "
            f"GapRequests del receptor "
            f"{_entero(item.receiver.receiver_gap_request_logical_count)}; "
            f"reparaciones "
            f"{_entero(item.receiver.receiver_repair_attempt_count)}."
        )
    estable = _estabilidad(result.positions)
    if estable is not None:
        lineas.append("")
        lineas.append(estable)
    lineas.append("")
    lineas.append("Diagnóstico de ejecución. No es resultado científico.")
    traces = _traces(result)
    for item, trace_count in zip(result.positions, _trace_pairs(traces), strict=True):
        lineas.append(
            f"Secuencia {item.sequence_number}: traza emisor {trace_count[0]} registros; "
            f"traza receptor {trace_count[1]} registros"
        )
    lineas.append(f"Registros de traza en total: {sum(traces)}")
    if result.wall_execution_seconds is None:
        lineas.append("Reloj de pared: no medido")
    else:
        lineas.append(
            "Reloj de pared: "
            f"{_numero(result.wall_execution_seconds)} s. No es una métrica científica."
        )
    return "\n".join(lineas)


def e3_sensitivity_payload(result: E3SensitivityResult) -> dict[str, object]:
    """JSON de la vista. No promedia las posiciones."""
    return {
        "experiment": "E3-sensitivity",
        "title": "Análisis de sensibilidad de E3",
        "not_e4": True,
        "banner": E3_SENSITIVITY_BANNER,
        "question": result.question,
        "campaign_id": result.campaign_id,
        "official_e3_campaign_id": E3_CAMPAIGN_ID,
        "campaign_identity": result.campaign_identity,
        "dataset_identity": result.dataset_identity,
        "cohort_note": E3_SENSITIVITY_COHORT_NOTE,
        "volume_note": E3_SENSITIVITY_VOLUME_NOTE,
        "position_note": E3_SENSITIVITY_POSITION_NOTE,
        "sequences": list(E3_SENSITIVITY_SEQUENCES),
        "run_count": len(E3_SENSITIVITY_SEQUENCES) * E3_SENSITIVITY_RUNS_PER_POSITION,
        "events_per_run": E3_MAX_EVENTS,
        "statistical_analysis": "not_implemented",
        "positions": [
            {
                "sequence_number": item.sequence_number,
                "valid": item.valid,
                "invalid_reason": item.invalid_reason,
                "loss_event_id": item.loss_event_id,
                "loss_at_sim": item.loss_at_sim,
                "sender": {
                    "recovery_policy": item.sender.recovery_policy,
                    "metrics": item.sender.metrics_dict(),
                },
                "receiver": {
                    "recovery_policy": item.receiver.recovery_policy,
                    "metrics": item.receiver.metrics_dict(),
                },
                "relations": item.relations(),
            }
            for item in result.positions
        ],
        "execution_diagnostics": {
            "wall_execution_seconds": result.wall_execution_seconds,
            "trace_entries_total": sum(_traces(result)),
            "trace_entries": list(_traces(result)),
            "note": E3_SENSITIVITY_DIAGNOSTIC_NOTE,
        },
    }


def e3_sensitivity_json(result: E3SensitivityResult) -> str:
    """Texto JSON de la vista, con caracteres Unicode."""
    return json.dumps(e3_sensitivity_payload(result), ensure_ascii=False, indent=2)


def _require_internal_sequences(sequences: tuple[int, ...]) -> None:
    if not 3 <= len(sequences) <= 5:
        raise ValueError("la sensibilidad usa entre 3 y 5 posiciones")
    if E3_LOSS_SEQUENCE not in sequences:
        raise ValueError("la sensibilidad debe incluir la secuencia oficial 5000")
    seen: set[int] = set()
    for sequence in sequences:
        if sequence in seen:
            raise ValueError("las posiciones de pérdida no se repiten")
        seen.add(sequence)
        if sequence <= 0 or sequence >= E3_MAX_EVENTS - 1:
            raise ValueError(
                f"la secuencia {sequence} no deja un vecino anterior y uno posterior"
            )


def _label(sequence: int, side: str) -> str:
    return f"{sequence}-{side}"


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


def _side(result: ScientificRunResult) -> E3SensitivitySide:
    episodes = result.metrics.episodes
    episode = None if not episodes else episodes[0]
    if len(episodes) > 1:
        episode = None
    return E3SensitivitySide(
        recovery_policy=result.recovery_policy,
        episode_count=len(episodes),
        loss_event_id=None if episode is None else episode.event_id,
        loss_sequence=None if episode is None else episode.sequence_number,
        loss_at_sim=None if episode is None else episode.loss_at_sim,
        loss_to_trigger_seconds=None if episode is None else episode.loss_to_trigger_seconds,
        loss_to_earth_recovery_seconds=(
            None if episode is None else episode.loss_to_earth_recovery_seconds
        ),
        loss_to_origin_confirmation_seconds=(
            None if episode is None else episode.loss_to_origin_confirmation_seconds
        ),
        policy_recovery_network_bytes=(
            None if episode is None else episode.policy_recovery_network_bytes
        ),
        sender_retry_attempt_count=(
            None if episode is None else episode.sender_retry_attempt_count
        ),
        receiver_gap_request_logical_count=(
            None if episode is None else episode.receiver_gap_request_logical_count
        ),
        receiver_repair_attempt_count=(
            None if episode is None else episode.receiver_repair_attempt_count
        ),
    )


def _position(
    sequence: int,
    sender: E3SensitivitySide,
    receiver: E3SensitivitySide,
) -> E3SensitivityPosition:
    reason = _invalid_reason(sequence, sender, receiver)
    shared_event = sender.loss_event_id if reason is None else None
    shared_time = sender.loss_at_sim if reason is None else None
    return E3SensitivityPosition(
        sequence_number=sequence,
        valid=reason is None,
        invalid_reason=reason,
        loss_event_id=shared_event,
        loss_at_sim=shared_time,
        sender=sender,
        receiver=receiver,
    )


def _invalid_reason(
    sequence: int,
    sender: E3SensitivitySide,
    receiver: E3SensitivitySide,
) -> str | None:
    if sender.episode_count != 1 or receiver.episode_count != 1:
        return "la pareja no tiene exactamente un episodio en cada política"
    if sender.loss_event_id != receiver.loss_event_id:
        return "loss_event_id distinto entre emisor y receptor"
    if sender.loss_sequence != receiver.loss_sequence:
        return "loss_sequence distinta entre emisor y receptor"
    if sender.loss_sequence != sequence or receiver.loss_sequence != sequence:
        return "la secuencia perdida no es la de esta posición"
    if sender.loss_at_sim != receiver.loss_at_sim:
        return "loss_at_sim distinto entre emisor y receptor"
    if sender.loss_event_id is None or sender.loss_at_sim is None:
        return "la pérdida no identifica evento e instante"
    return None


def _relacion_tiempo(
    sender: float | None,
    receiver: float | None,
    *,
    antes: str,
    despues: str,
    igual: str,
) -> str:
    if sender is None or receiver is None:
        return "no definido"
    if receiver < sender:
        return antes
    if receiver > sender:
        return despues
    return igual


def _relacion_bytes(sender: int | None, receiver: int | None) -> str:
    if sender is None or receiver is None:
        return "no definido"
    if receiver < sender:
        return "el receptor usa menos bytes"
    if receiver > sender:
        return "el receptor usa más bytes"
    return "el receptor usa los mismos bytes"


def _estabilidad(positions: tuple[E3SensitivityPosition, ...]) -> str | None:
    validas = [item for item in positions if item.valid]
    if len(validas) != len(positions) or not validas:
        return None
    firmas = [tuple(item.relations().values()) for item in validas]
    if len(set(firmas)) != 1:
        return "El sentido del contraste no es el mismo en todas las posiciones."
    hechos = "; ".join(firmas[0])
    return f"El sentido del contraste es el mismo en las {len(validas)} posiciones: {hechos}."


def _traces(result: E3SensitivityResult) -> tuple[int, ...]:
    return result.trace_entries


def _trace_pairs(traces: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    pairs: list[tuple[int, int]] = []
    for index in range(0, len(traces), 2):
        pairs.append((traces[index], traces[index + 1]))
    return tuple(pairs)


def _numero(value: float) -> str:
    text = f"{value:.9f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _cantidad(value: float | None) -> str:
    if value is None:
        return "no definido"
    return _numero(value)


def _entero(value: int | None) -> str:
    if value is None:
        return "no definido"
    return str(value)
