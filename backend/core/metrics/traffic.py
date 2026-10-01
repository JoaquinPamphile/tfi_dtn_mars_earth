"""Overhead de aplicación y utilización de contacto de una corrida.

Los bytes creados son el ``payload_size_bytes`` canónico de cada SyncUnit
en el momento de crearla. Los bytes de transporte son los que cada hop
serializó, incluida una porción interrumpida. Un mismo payload que cruza
Marte → relé y relé → Tierra cuenta dos veces en el transporte. La
propagación no suma bytes. No se inventan cabeceras de red.

``total_transport_application_bytes`` y
``application_bytes_transmitted_total`` suman ``bytes_transmitted`` de
todos los hops registrados. Los breakdowns de telemetría y de ACK no
reemplazan ese total: un ``gap_request`` u otro kind con registro también
cuenta.

``retry_transport_bytes`` suma hops con ``attempt_number > 1``. El primer
intento no entra. ``interrupted_transport_bytes`` suma solo los hops
cortados. La utilización es bits usados sobre bits realmente disponibles.
Si la capacidad es cero, la utilización es ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.contact.contact import Contact, LogicalNode
from core.metrics.errors import MetricInvariantError
from core.transport.accounting import ForcedContactCut, HopTransmissionRecord

KIND_TELEMETRY_EVENTS = "telemetry_events"
KIND_APPLICATION_ACK = "application_ack"

FORWARD_HOPS = {
    (LogicalNode.MARS.value, LogicalNode.RELAY.value),
    (LogicalNode.RELAY.value, LogicalNode.EARTH.value),
}
REVERSE_HOPS = {
    (LogicalNode.EARTH.value, LogicalNode.RELAY.value),
    (LogicalNode.RELAY.value, LogicalNode.MARS.value),
}

UTILIZATION_OVERSHOOT_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class CreatedByteCounters:
    """Bytes de aplicación ofrecidos al crearse la unidad, sin hops."""

    telemetry_syncunit_bytes_created: int
    telemetry_initial_syncunit_bytes_created: int
    telemetry_retry_syncunit_bytes_created: int
    ack_syncunit_bytes_created: int


@dataclass(frozen=True, slots=True)
class TrafficMetrics:
    """Contadores de bytes de una corrida ya terminada."""

    telemetry_syncunit_bytes_created: int
    telemetry_initial_syncunit_bytes_created: int
    telemetry_retry_syncunit_bytes_created: int
    ack_syncunit_bytes_created: int
    application_bytes_transmitted_total: int
    mars_to_relay_bytes: int
    relay_to_earth_bytes: int
    earth_to_relay_bytes: int
    relay_to_mars_bytes: int
    telemetry_transport_bytes: int
    ack_transport_bytes: int
    total_transport_application_bytes: int
    retry_transport_bytes: int
    interrupted_transport_bytes: int
    forward_bytes_transmitted: int
    reverse_bytes_transmitted: int


@dataclass(frozen=True, slots=True)
class ContactUtilization:
    """Capacidad y uso de una ventana dirigida."""

    contact_id: str
    source: str
    destination: str
    planned_start_sim: float
    planned_end_sim: float
    actual_end_sim: float
    data_rate_bps: int
    planned_capacity_bytes: float
    actual_capacity_bytes: float
    used_capacity_bytes: float
    unused_capacity_bytes: float
    utilization: float | None
    forced_cut: bool
    transmissions_completed: int
    transmissions_interrupted: int


@dataclass(frozen=True, slots=True)
class ContactSummaryMetrics:
    """Agregados de utilización. La media y la ponderada usan ventanas ya iniciadas."""

    contacts_total: int
    contacts_used: int
    contacts_forced_cut: int
    contact_utilization_mean: float | None
    contact_utilization_weighted: float | None
    forward_contact_utilization_weighted: float | None
    reverse_contact_utilization_weighted: float | None
    items: tuple[ContactUtilization, ...]


def traffic_metrics(
    *,
    created: CreatedByteCounters,
    hop_records: tuple[HopTransmissionRecord, ...],
) -> TrafficMetrics:
    """Arma los contadores de bytes a partir de unidades creadas y hops."""
    mars_to_relay = _sum_link(hop_records, LogicalNode.MARS.value, LogicalNode.RELAY.value)
    relay_to_earth = _sum_link(hop_records, LogicalNode.RELAY.value, LogicalNode.EARTH.value)
    earth_to_relay = _sum_link(hop_records, LogicalNode.EARTH.value, LogicalNode.RELAY.value)
    relay_to_mars = _sum_link(hop_records, LogicalNode.RELAY.value, LogicalNode.MARS.value)
    telemetry_transport = sum(
        record.bytes_transmitted
        for record in hop_records
        if record.payload_kind == KIND_TELEMETRY_EVENTS
    )
    ack_transport = sum(
        record.bytes_transmitted
        for record in hop_records
        if record.payload_kind == KIND_APPLICATION_ACK
    )
    retry_transport = sum(
        record.bytes_transmitted for record in hop_records if record.attempt_number > 1
    )
    interrupted_transport = sum(
        record.bytes_transmitted for record in hop_records if record.interrupted
    )
    total = sum(record.bytes_transmitted for record in hop_records)
    return TrafficMetrics(
        telemetry_syncunit_bytes_created=created.telemetry_syncunit_bytes_created,
        telemetry_initial_syncunit_bytes_created=(
            created.telemetry_initial_syncunit_bytes_created
        ),
        telemetry_retry_syncunit_bytes_created=created.telemetry_retry_syncunit_bytes_created,
        ack_syncunit_bytes_created=created.ack_syncunit_bytes_created,
        application_bytes_transmitted_total=total,
        mars_to_relay_bytes=mars_to_relay,
        relay_to_earth_bytes=relay_to_earth,
        earth_to_relay_bytes=earth_to_relay,
        relay_to_mars_bytes=relay_to_mars,
        telemetry_transport_bytes=telemetry_transport,
        ack_transport_bytes=ack_transport,
        total_transport_application_bytes=total,
        retry_transport_bytes=retry_transport,
        interrupted_transport_bytes=interrupted_transport,
        forward_bytes_transmitted=mars_to_relay + relay_to_earth,
        reverse_bytes_transmitted=earth_to_relay + relay_to_mars,
    )


def contact_summary(
    *,
    contacts: tuple[Contact, ...],
    forced_cuts: tuple[ForcedContactCut, ...],
    hop_records: tuple[HopTransmissionRecord, ...],
    time_sim: float,
) -> ContactSummaryMetrics:
    """Utilización de cada contacto ya definido en el plan."""
    cut_by_id: dict[str, ForcedContactCut] = {}
    for item in forced_cuts:
        cut_by_id[item.contact_id] = item
    items = tuple(
        _contact_utilization(contact, cut_by_id.get(contact.contact_id), hop_records)
        for contact in contacts
    )
    started = tuple(item for item in items if time_sim >= item.planned_start_sim)
    return ContactSummaryMetrics(
        contacts_total=len(items),
        contacts_used=sum(1 for item in items if item.used_capacity_bytes > 0),
        contacts_forced_cut=sum(1 for item in items if item.forced_cut),
        contact_utilization_mean=_mean_utilization(started),
        contact_utilization_weighted=_weighted_utilization(started),
        forward_contact_utilization_weighted=_weighted_utilization(
            tuple(
                item
                for item in started
                if (item.source, item.destination) in FORWARD_HOPS
            )
        ),
        reverse_contact_utilization_weighted=_weighted_utilization(
            tuple(
                item
                for item in started
                if (item.source, item.destination) in REVERSE_HOPS
            )
        ),
        items=items,
    )


def _contact_utilization(
    contact: Contact,
    cut: ForcedContactCut | None,
    hop_records: tuple[HopTransmissionRecord, ...],
) -> ContactUtilization:
    forced = cut is not None and cut.triggered
    actual_end = cut.cut_at_sim if forced else contact.end_time_sim
    planned_duration = contact.end_time_sim - contact.start_time_sim
    actual_duration = actual_end - contact.start_time_sim
    planned_capacity_bytes = planned_duration * contact.data_rate_bps / 8.0
    actual_capacity_bytes = actual_duration * contact.data_rate_bps / 8.0
    used_capacity_bytes = float(
        sum(
            record.bytes_transmitted
            for record in hop_records
            if record.contact_id == contact.contact_id
        )
    )
    completed = sum(
        1
        for record in hop_records
        if record.contact_id == contact.contact_id and record.completed
    )
    interrupted = sum(
        1
        for record in hop_records
        if record.contact_id == contact.contact_id and record.interrupted
    )
    return ContactUtilization(
        contact_id=contact.contact_id,
        source=contact.source.value,
        destination=contact.destination.value,
        planned_start_sim=contact.start_time_sim,
        planned_end_sim=contact.end_time_sim,
        actual_end_sim=actual_end,
        data_rate_bps=contact.data_rate_bps,
        planned_capacity_bytes=planned_capacity_bytes,
        actual_capacity_bytes=actual_capacity_bytes,
        used_capacity_bytes=used_capacity_bytes,
        unused_capacity_bytes=actual_capacity_bytes - used_capacity_bytes,
        utilization=_utilization_ratio(used_capacity_bytes, actual_capacity_bytes),
        forced_cut=forced,
        transmissions_completed=completed,
        transmissions_interrupted=interrupted,
    )


def _utilization_ratio(used_bytes: float, actual_capacity_bytes: float) -> float | None:
    if actual_capacity_bytes <= 0:
        return None
    ratio = (used_bytes * 8.0) / (actual_capacity_bytes * 8.0)
    if ratio > 1.0 + UTILIZATION_OVERSHOOT_TOLERANCE:
        raise MetricInvariantError(
            "la utilización del contacto supera 1 más allá de la tolerancia "
            f"{UTILIZATION_OVERSHOOT_TOLERANCE}: {ratio}"
        )
    if ratio < 0:
        raise MetricInvariantError(f"la utilización del contacto es negativa: {ratio}")
    if ratio > 1.0:
        return 1.0
    return ratio


def _mean_utilization(items: tuple[ContactUtilization, ...]) -> float | None:
    values = [item.utilization for item in items if item.utilization is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _weighted_utilization(items: tuple[ContactUtilization, ...]) -> float | None:
    used_bits = sum(item.used_capacity_bytes * 8.0 for item in items)
    capacity_bits = sum(item.actual_capacity_bytes * 8.0 for item in items)
    if capacity_bits <= 0:
        return None
    ratio = used_bits / capacity_bits
    if ratio > 1.0 + UTILIZATION_OVERSHOOT_TOLERANCE:
        raise MetricInvariantError(
            "la utilización ponderada supera 1 más allá de la tolerancia: "
            f"{ratio}"
        )
    if ratio > 1.0:
        return 1.0
    return ratio


def _sum_link(
    records: tuple[HopTransmissionRecord, ...], source: str, destination: str
) -> int:
    return sum(
        record.bytes_transmitted
        for record in records
        if record.source_node == source and record.destination_node == destination
    )
