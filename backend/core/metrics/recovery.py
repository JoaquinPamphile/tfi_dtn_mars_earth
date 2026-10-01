"""Episodio de recuperación de una pérdida silenciosa ya ocurrida.

El origen temporal común es ``loss_at_sim``: el instante en que la
entrega relé → Tierra fue suprimida. No es el instante de generación.

Se conservan separados:

- pérdida → disparo de la política;
- disparo → persistencia en Tierra;
- pérdida → persistencia en Tierra;
- persistencia en Tierra → confirmación en Marte;
- pérdida → confirmación en Marte.

Un instante que no ocurrió deja la duración en ``None``. No se usa 0,
infinito ni el horizonte del escenario.

El retry del emisor es un intento cuyo padre quedó en ``TIMED_OUT``.
La reparación del receptor es un reenvío disparado por un GapRequest.
``retry_attempts_total`` de la corrida, que cuenta todo
``attempt_number > 1``, no sustituye a ninguno de los dos.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.contact.contact import LogicalNode
from core.domain.attempt import SyncAttempt, SyncAttemptStatus
from core.domain.gap import GapRequest, MissingSequenceRange
from core.domain.identity import make_recovery_episode_id
from core.failure.runtime import SilentForwardDeliveryDropRecord
from core.recovery.attempt import GapRequestAttemptState
from core.sync.codec import KIND_APPLICATION_ACK, KIND_GAP_REQUEST, KIND_TELEMETRY_EVENTS
from core.transport.accounting import HopTransmissionRecord

FAILURE_SILENT_FORWARD_DELIVERY_LOSS = "SILENT_FORWARD_DELIVERY_LOSS"
TRIGGER_SENDER_ACK_TIMEOUT = "SENDER_ACK_TIMEOUT"
TRIGGER_RECEIVER_GAP_REQUEST = "RECEIVER_GAP_REQUEST"
POLICY_SENDER_DRIVEN = "SENDER_DRIVEN"
POLICY_RECEIVER_DRIVEN = "RECEIVER_DRIVEN"
STATUS_UNRECOVERED = "UNRECOVERED"
STATUS_EARTH_RECOVERED_UNCONFIRMED = "EARTH_RECOVERED_UNCONFIRMED"
STATUS_RECOVERED_AND_CONFIRMED = "RECOVERED_AND_CONFIRMED"


@dataclass(frozen=True, slots=True)
class PersistenceObservation:
    """Primera persistencia durable de un evento en Tierra."""

    event_id: str
    source_id: str
    sequence_number: int
    generated_at_sim: float
    earth_first_persisted_at_sim: float


@dataclass(frozen=True, slots=True)
class SenderTimeoutObservation:
    """Timeout de ACK ya aplicado a una cohorte."""

    attempt_id: str
    event_ids: tuple[str, ...]
    at_sim: float


@dataclass(frozen=True, slots=True)
class RecoveryEpisodeResult:
    """Un episodio por cada pérdida silenciosa ya registrada."""

    episode_id: str
    failure_type: str
    failure_occurrence: int
    recovery_policy: str | None
    recovery_trigger: str | None
    source_id: str
    event_id: str
    sequence_number: int
    telemetry_attempt_number: int
    hop: str
    loss_at_sim: float | None
    gap_observed_at_sim: float | None
    recovery_triggered_at_sim: float | None
    first_recovery_data_departed_mars_at_sim: float | None
    earth_recovered_at_sim: float | None
    gap_closed_at_sim: float | None
    origin_confirmed_at_sim: float | None
    loss_to_gap_observed_seconds: float | None
    loss_to_trigger_seconds: float | None
    trigger_to_earth_recovery_seconds: float | None
    loss_to_earth_recovery_seconds: float | None
    earth_recovery_to_origin_confirmation_seconds: float | None
    loss_to_origin_confirmation_seconds: float | None
    sender_ack_timeout_count: int
    sender_retry_attempt_count: int
    receiver_gap_request_logical_count: int
    gap_request_transport_attempt_count: int
    receiver_repair_attempt_count: int
    duplicates_received_after_loss: int
    duplicates_stored_after_loss: int
    common_lost_attempt_bytes_mars_relay: int
    common_lost_attempt_bytes_relay_earth: int
    recovery_data_bytes_mars_relay: int
    recovery_data_bytes_relay_earth: int
    gap_request_bytes_earth_relay: int
    gap_request_bytes_relay_mars: int
    recovery_ack_bytes_earth_relay: int
    recovery_ack_bytes_relay_mars: int
    policy_recovery_forward_bytes: int
    policy_recovery_reverse_bytes: int
    policy_recovery_network_bytes: int
    earth_recovered: bool
    origin_confirmed: bool
    episode_status: str


@dataclass(frozen=True, slots=True)
class RecoveryRunSummary:
    """Resumen de los episodios de esta corrida. No agrega varias corridas.

    Con un solo episodio, las latencias son las de ese episodio. Con
    varios, las latencias quedan en ``None`` y solo se suman los conteos.
    Sin episodios, las latencias también quedan en ``None``.
    """

    episode_count: int = 0
    recovered_count: int = 0
    confirmed_count: int = 0
    policy_recovery_network_bytes_total: int = 0
    loss_to_trigger_seconds: float | None = None
    trigger_to_earth_recovery_seconds: float | None = None
    loss_to_earth_recovery_seconds: float | None = None
    earth_recovery_to_origin_confirmation_seconds: float | None = None
    loss_to_origin_confirmation_seconds: float | None = None
    sender_ack_timeout_count: int | None = None
    sender_retry_attempt_count: int | None = None
    receiver_gap_request_logical_count: int | None = None
    gap_request_transport_attempt_count: int | None = None
    receiver_repair_attempt_count: int | None = None
    duplicates_received_after_loss: int | None = None
    duplicates_stored_after_loss: int | None = None
    policy_recovery_forward_bytes: int | None = None
    policy_recovery_reverse_bytes: int | None = None
    gap_observed_at_sim: float | None = None


@dataclass(frozen=True, slots=True)
class RecoveryEpisodeInputs:
    """Estado científico ya producido. No es un volcado de la traza."""

    recovery_policy: str | None
    persistence: tuple[PersistenceObservation, ...]
    confirmed_at_by_event_id: Mapping[str, float]
    duplicate_receipts_by_event_id: Mapping[str, int]
    attempts_by_event_id: Mapping[str, Sequence[SyncAttempt]]
    hop_records: tuple[HopTransmissionRecord, ...]
    silent_drops: tuple[SilentForwardDeliveryDropRecord, ...]
    sender_timeouts: tuple[SenderTimeoutObservation, ...]
    issued_gap_requests: tuple[GapRequest, ...]
    gap_request_attempts: Mapping[str, GapRequestAttemptState]
    receiver_repairs: tuple[tuple[str, int, str, float], ...]


def latency_seconds(later: float | None, earlier: float | None) -> float | None:
    """``later - earlier``. Si falta un instante, el resultado es ``None``."""
    if later is None or earlier is None:
        return None
    return later - earlier


def episode_status_for(*, earth_recovered: bool, origin_confirmed: bool) -> str:
    """Separa Tierra recuperada de Marte confirmado."""
    if not earth_recovered:
        return STATUS_UNRECOVERED
    if not origin_confirmed:
        return STATUS_EARTH_RECOVERED_UNCONFIRMED
    return STATUS_RECOVERED_AND_CONFIRMED


def build_recovery_episodes(
    inputs: RecoveryEpisodeInputs,
) -> tuple[RecoveryEpisodeResult, ...]:
    """Un episodio por cada descarte silencioso, en el orden registrado."""
    by_id = {row.event_id: row for row in inputs.persistence}
    by_source_seq = {(row.source_id, row.sequence_number): row for row in inputs.persistence}
    episodes: list[RecoveryEpisodeResult] = []
    for drop in inputs.silent_drops:
        row = by_id.get(drop.event_id) or by_source_seq.get(
            (drop.source_id, drop.sequence_number)
        )
        event_id = drop.event_id if row is None else row.event_id
        source_id = drop.source_id if row is None else row.source_id
        sequence_number = drop.sequence_number if row is None else row.sequence_number
        episodes.append(
            _episode_for_drop(
                inputs=inputs,
                drop=drop,
                row=row,
                event_id=event_id,
                source_id=source_id,
                sequence_number=sequence_number,
            )
        )
    return tuple(episodes)


def recovery_run_summary(
    episodes: tuple[RecoveryEpisodeResult, ...],
) -> RecoveryRunSummary:
    """Resume los episodios. No promedia latencias de varios fallos."""
    if not episodes:
        return RecoveryRunSummary()
    recovered = sum(1 for item in episodes if item.earth_recovered)
    confirmed = sum(1 for item in episodes if item.origin_confirmed)
    total_bytes = sum(item.policy_recovery_network_bytes for item in episodes)
    primary = episodes[0] if len(episodes) == 1 else None
    return RecoveryRunSummary(
        episode_count=len(episodes),
        recovered_count=recovered,
        confirmed_count=confirmed,
        policy_recovery_network_bytes_total=total_bytes,
        loss_to_trigger_seconds=_primary(primary, "loss_to_trigger_seconds"),
        trigger_to_earth_recovery_seconds=_primary(
            primary, "trigger_to_earth_recovery_seconds"
        ),
        loss_to_earth_recovery_seconds=_primary(primary, "loss_to_earth_recovery_seconds"),
        earth_recovery_to_origin_confirmation_seconds=_primary(
            primary, "earth_recovery_to_origin_confirmation_seconds"
        ),
        loss_to_origin_confirmation_seconds=_primary(
            primary, "loss_to_origin_confirmation_seconds"
        ),
        sender_ack_timeout_count=_primary(primary, "sender_ack_timeout_count"),
        sender_retry_attempt_count=_primary(primary, "sender_retry_attempt_count"),
        receiver_gap_request_logical_count=_primary(
            primary, "receiver_gap_request_logical_count"
        ),
        gap_request_transport_attempt_count=_primary(
            primary, "gap_request_transport_attempt_count"
        ),
        receiver_repair_attempt_count=_primary(primary, "receiver_repair_attempt_count"),
        duplicates_received_after_loss=_primary(primary, "duplicates_received_after_loss"),
        duplicates_stored_after_loss=_primary(primary, "duplicates_stored_after_loss"),
        policy_recovery_forward_bytes=_primary(primary, "policy_recovery_forward_bytes"),
        policy_recovery_reverse_bytes=_primary(primary, "policy_recovery_reverse_bytes"),
        gap_observed_at_sim=_primary(primary, "gap_observed_at_sim"),
    )


def gap_observed_at_sim(
    rows: Sequence[PersistenceObservation],
    *,
    source_id: str,
    sequence_number: int,
) -> float | None:
    """Primera persistencia posterior mientras el objetivo sigue ausente.

    Sale de los instantes de Tierra. No depende de la política ni de la
    traza del controlador.
    """
    target_persist: float | None = None
    later_persists: list[float] = []
    for row in rows:
        if row.source_id != source_id:
            continue
        if row.sequence_number == sequence_number:
            target_persist = row.earth_first_persisted_at_sim
            continue
        if row.sequence_number > sequence_number:
            later_persists.append(row.earth_first_persisted_at_sim)
    if not later_persists:
        return None
    earliest_later = min(later_persists)
    if target_persist is not None and earliest_later >= target_persist:
        return None
    return earliest_later


def _episode_for_drop(
    *,
    inputs: RecoveryEpisodeInputs,
    drop: SilentForwardDeliveryDropRecord,
    row: PersistenceObservation | None,
    event_id: str,
    source_id: str,
    sequence_number: int,
) -> RecoveryEpisodeResult:
    loss_at = drop.lost_at_sim
    gap_at = gap_observed_at_sim(
        inputs.persistence, source_id=source_id, sequence_number=sequence_number
    )
    earth_recovered_at = None if row is None else row.earth_first_persisted_at_sim
    origin_confirmed_at = inputs.confirmed_at_by_event_id.get(event_id)
    gap_closed_at = _gap_closed_at_sim(
        gap_observed_at=gap_at, earth_recovered_at_sim=earth_recovered_at
    )
    trigger, triggered_at = _first_trigger(
        inputs=inputs,
        event_id=event_id,
        source_id=source_id,
        sequence_number=sequence_number,
        policy=inputs.recovery_policy,
    )
    attempts = tuple(inputs.attempts_by_event_id.get(event_id, ()))
    sender_timeouts = _sender_timeouts_for(inputs.sender_timeouts, event_id)
    covering_requests = _covering_requests(
        inputs.issued_gap_requests, source_id, sequence_number
    )
    covering_ids = {item.request_id for item in covering_requests}
    transport_attempts = sum(
        _transport_attempt_count(inputs.gap_request_attempts.get(request_id))
        for request_id in _ordered_ids(covering_requests)
    )
    receiver_repairs = sum(
        1
        for repair_event_id, repair_sequence, _request_id, _at in inputs.receiver_repairs
        if repair_event_id == event_id or repair_sequence == sequence_number
    )
    bytes_ = _byte_accounting(
        hops=inputs.hop_records,
        event_id=event_id,
        lost_attempt=drop.telemetry_attempt_number,
        covering_request_ids=covering_ids,
    )
    duplicates_received = inputs.duplicate_receipts_by_event_id.get(event_id, 0)
    earth_recovered = earth_recovered_at is not None
    origin_confirmed = origin_confirmed_at is not None
    return RecoveryEpisodeResult(
        episode_id=make_recovery_episode_id(
            failure_type=FAILURE_SILENT_FORWARD_DELIVERY_LOSS,
            source_id=source_id,
            sequence_number=sequence_number,
            failure_occurrence=drop.occurrence_number,
            telemetry_attempt_number=drop.telemetry_attempt_number,
            hop=drop.hop,
        ),
        failure_type=FAILURE_SILENT_FORWARD_DELIVERY_LOSS,
        failure_occurrence=drop.occurrence_number,
        recovery_policy=inputs.recovery_policy,
        recovery_trigger=trigger,
        source_id=source_id,
        event_id=event_id,
        sequence_number=sequence_number,
        telemetry_attempt_number=drop.telemetry_attempt_number,
        hop=drop.hop,
        loss_at_sim=loss_at,
        gap_observed_at_sim=gap_at,
        recovery_triggered_at_sim=triggered_at,
        first_recovery_data_departed_mars_at_sim=_first_recovery_data_departed(
            inputs.hop_records,
            event_id=event_id,
            lost_attempt=drop.telemetry_attempt_number,
        ),
        earth_recovered_at_sim=earth_recovered_at,
        gap_closed_at_sim=gap_closed_at,
        origin_confirmed_at_sim=origin_confirmed_at,
        loss_to_gap_observed_seconds=latency_seconds(gap_at, loss_at),
        loss_to_trigger_seconds=latency_seconds(triggered_at, loss_at),
        trigger_to_earth_recovery_seconds=latency_seconds(earth_recovered_at, triggered_at),
        loss_to_earth_recovery_seconds=latency_seconds(earth_recovered_at, loss_at),
        earth_recovery_to_origin_confirmation_seconds=latency_seconds(
            origin_confirmed_at, earth_recovered_at
        ),
        loss_to_origin_confirmation_seconds=latency_seconds(origin_confirmed_at, loss_at),
        sender_ack_timeout_count=len(sender_timeouts),
        sender_retry_attempt_count=_sender_retry_count(attempts),
        receiver_gap_request_logical_count=len(covering_requests),
        gap_request_transport_attempt_count=transport_attempts,
        receiver_repair_attempt_count=receiver_repairs,
        duplicates_received_after_loss=duplicates_received,
        duplicates_stored_after_loss=0,
        common_lost_attempt_bytes_mars_relay=bytes_["common_mars_relay"],
        common_lost_attempt_bytes_relay_earth=bytes_["common_relay_earth"],
        recovery_data_bytes_mars_relay=bytes_["recovery_mars_relay"],
        recovery_data_bytes_relay_earth=bytes_["recovery_relay_earth"],
        gap_request_bytes_earth_relay=bytes_["gap_earth_relay"],
        gap_request_bytes_relay_mars=bytes_["gap_relay_mars"],
        recovery_ack_bytes_earth_relay=bytes_["ack_earth_relay"],
        recovery_ack_bytes_relay_mars=bytes_["ack_relay_mars"],
        policy_recovery_forward_bytes=bytes_["forward"],
        policy_recovery_reverse_bytes=bytes_["reverse"],
        policy_recovery_network_bytes=bytes_["network"],
        earth_recovered=earth_recovered,
        origin_confirmed=origin_confirmed,
        episode_status=episode_status_for(
            earth_recovered=earth_recovered, origin_confirmed=origin_confirmed
        ),
    )


def _gap_closed_at_sim(
    *, gap_observed_at: float | None, earth_recovered_at_sim: float | None
) -> float | None:
    """Instante en que el objetivo deja de ser un hueco ya observado."""
    if gap_observed_at is None or earth_recovered_at_sim is None:
        return None
    if earth_recovered_at_sim < gap_observed_at:
        return None
    return earth_recovered_at_sim


def _first_trigger(
    *,
    inputs: RecoveryEpisodeInputs,
    event_id: str,
    source_id: str,
    sequence_number: int,
    policy: str | None,
) -> tuple[str | None, float | None]:
    sender_times = _sender_timeouts_for(inputs.sender_timeouts, event_id)
    covering = _covering_requests(inputs.issued_gap_requests, source_id, sequence_number)
    receiver_times = [item.created_at_sim for item in covering]
    if policy == POLICY_SENDER_DRIVEN:
        if not sender_times:
            return None, None
        return TRIGGER_SENDER_ACK_TIMEOUT, min(sender_times)
    if policy == POLICY_RECEIVER_DRIVEN:
        if not receiver_times:
            return None, None
        return TRIGGER_RECEIVER_GAP_REQUEST, min(receiver_times)
    if sender_times and (not receiver_times or min(sender_times) <= min(receiver_times)):
        return TRIGGER_SENDER_ACK_TIMEOUT, min(sender_times)
    if receiver_times:
        return TRIGGER_RECEIVER_GAP_REQUEST, min(receiver_times)
    return None, None


def _sender_timeouts_for(
    records: Sequence[SenderTimeoutObservation], event_id: str
) -> tuple[float, ...]:
    return tuple(item.at_sim for item in records if event_id in item.event_ids)


def _covering_requests(
    requests: Sequence[GapRequest], source_id: str, sequence_number: int
) -> tuple[GapRequest, ...]:
    return tuple(
        item
        for item in requests
        if item.target_source_id == source_id
        and _ranges_cover(item.missing_ranges, sequence_number)
    )


def _ranges_cover(ranges: Sequence[MissingSequenceRange], sequence_number: int) -> bool:
    return any(item.start_sequence <= sequence_number <= item.end_sequence for item in ranges)


def _ordered_ids(requests: Sequence[GapRequest]) -> tuple[str, ...]:
    """Identificadores en el orden de emisión, sin repetir."""
    seen: list[str] = []
    for item in requests:
        if item.request_id not in seen:
            seen.append(item.request_id)
    return tuple(seen)


def _transport_attempt_count(state: GapRequestAttemptState | None) -> int:
    if state is None:
        return 0
    if state.transport_attempt_count > 0:
        return state.transport_attempt_count
    return max(state.attempt_number, 0)


def _sender_retry_count(attempts: Sequence[SyncAttempt]) -> int:
    """Intentos cuyo padre quedó en ``TIMED_OUT``.

    Una reparación cuyo padre quedó en ``REPAIR_REQUESTED`` no entra.
    """
    timed_out_ids = {
        item.attempt_id for item in attempts if item.status is SyncAttemptStatus.TIMED_OUT
    }
    return sum(
        1
        for item in attempts
        if item.parent_attempt_id is not None and item.parent_attempt_id in timed_out_ids
    )


def _first_recovery_data_departed(
    hops: Sequence[HopTransmissionRecord],
    *,
    event_id: str,
    lost_attempt: int,
) -> float | None:
    times = [
        hop.end_time_sim
        for hop in hops
        if hop.completed
        and hop.source_node == LogicalNode.MARS.value
        and hop.destination_node == LogicalNode.RELAY.value
        and hop.payload_kind == KIND_TELEMETRY_EVENTS
        and event_id in hop.event_ids
        and hop.attempt_number > lost_attempt
    ]
    if not times:
        return None
    return min(times)


def _byte_accounting(
    *,
    hops: Sequence[HopTransmissionRecord],
    event_id: str,
    lost_attempt: int,
    covering_request_ids: set[str],
) -> dict[str, int]:
    common_mars = 0
    common_relay = 0
    recovery_mars = 0
    recovery_relay = 0
    gap_earth = 0
    gap_mars = 0
    ack_earth = 0
    ack_mars = 0
    for hop in hops:
        size = hop.bytes_transmitted
        mars_relay = (
            hop.source_node == LogicalNode.MARS.value
            and hop.destination_node == LogicalNode.RELAY.value
        )
        relay_earth = (
            hop.source_node == LogicalNode.RELAY.value
            and hop.destination_node == LogicalNode.EARTH.value
        )
        earth_relay = (
            hop.source_node == LogicalNode.EARTH.value
            and hop.destination_node == LogicalNode.RELAY.value
        )
        relay_mars = (
            hop.source_node == LogicalNode.RELAY.value
            and hop.destination_node == LogicalNode.MARS.value
        )
        if hop.payload_kind == KIND_TELEMETRY_EVENTS and event_id in hop.event_ids:
            if hop.attempt_number <= lost_attempt:
                if mars_relay:
                    common_mars += size
                elif relay_earth:
                    common_relay += size
            else:
                if mars_relay:
                    recovery_mars += size
                elif relay_earth:
                    recovery_relay += size
            continue
        if (
            hop.payload_kind == KIND_GAP_REQUEST
            and hop.gap_request_id in covering_request_ids
        ):
            if earth_relay:
                gap_earth += size
            elif relay_mars:
                gap_mars += size
            continue
        if hop.payload_kind == KIND_APPLICATION_ACK and event_id in hop.event_ids:
            if earth_relay:
                ack_earth += size
            elif relay_mars:
                ack_mars += size
    forward = recovery_mars + recovery_relay
    reverse = gap_earth + gap_mars + ack_earth + ack_mars
    return {
        "common_mars_relay": common_mars,
        "common_relay_earth": common_relay,
        "recovery_mars_relay": recovery_mars,
        "recovery_relay_earth": recovery_relay,
        "gap_earth_relay": gap_earth,
        "gap_relay_mars": gap_mars,
        "ack_earth_relay": ack_earth,
        "ack_relay_mars": ack_mars,
        "forward": forward,
        "reverse": reverse,
        "network": forward + reverse,
    }


def _primary(episode: RecoveryEpisodeResult | None, name: str) -> object:
    if episode is None:
        return None
    return getattr(episode, name)
