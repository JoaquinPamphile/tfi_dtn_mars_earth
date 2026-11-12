from __future__ import annotations
import hashlib
from collections.abc import Sequence
from typing import Any

from core.contact.contact import LogicalNode
from experiments.canonical import canonical_json
from importers.cpd.support import (
    CpdSupportError,
    as_finite_float64,
    as_positive_json_int,
    float64_hex,
)

CPD_CID_VERSION = 1
CPD_CID_PREFIX = "cpd-cid-v1-"


class CpdContactIdError(ValueError):
    """Payload de identidad CPD inválido, duplicado o en colisión."""


def derive_cpd_contact_identity(
    *,
    source: LogicalNode,
    destination: LogicalNode,
    start_s: object,
    end_s: object,
    rate_bps: object,
    range_km: object,
) -> tuple[str, str]:
    payload = _build_cpd_contact_identity_payload(
        source=source,
        destination=destination,
        start_s=start_s,
        end_s=end_s,
        rate_bps=rate_bps,
        range_km=range_km,
    )
    canonical = canonical_json(payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{CPD_CID_PREFIX}{digest[:16]}", canonical


def make_cpd_contact_id(
    *,
    source: LogicalNode,
    destination: LogicalNode,
    start_s: object,
    end_s: object,
    rate_bps: object,
    range_km: object,
) -> str:
    contact_id, _canonical = derive_cpd_contact_identity(
        source=source,
        destination=destination,
        start_s=start_s,
        end_s=end_s,
        rate_bps=rate_bps,
        range_km=range_km,
    )
    return contact_id


def validate_cpd_contact_identity_set(
    identities: Sequence[tuple[str, str]],
) -> None:
    seen_payloads: set[str] = set()
    seen_ids: dict[str, str] = {}
    for contact_id, canonical_payload in identities:
        if canonical_payload in seen_payloads:
            raise CpdContactIdError("payload canónico de contacto duplicado")
        previous = seen_ids.get(contact_id)
        if previous is not None and previous != canonical_payload:
            raise CpdContactIdError(
                f"colisión de contact_id sin sufijos: {contact_id}"
            )
        seen_payloads.add(canonical_payload)
        seen_ids[contact_id] = canonical_payload


def _build_cpd_contact_identity_payload(
    *,
    source: LogicalNode,
    destination: LogicalNode,
    start_s: object,
    end_s: object,
    rate_bps: object,
    range_km: object,
) -> dict[str, Any]:
    if source == destination:
        raise CpdContactIdError("source y destination deben ser distintos")

    try:
        start = as_finite_float64(start_s)
        end = as_finite_float64(end_s)
        distance = as_finite_float64(range_km)
        rate = as_positive_json_int(rate_bps)
        start_hex = float64_hex(start)
        end_hex = float64_hex(end)
        range_hex = float64_hex(distance)
    except CpdSupportError as exc:
        raise CpdContactIdError(str(exc)) from exc

    if start < 0.0:
        raise CpdContactIdError("start_s no puede ser negativo")
    if end <= start:
        raise CpdContactIdError("end_s debe ser mayor que start_s")
    if distance < 0.0:
        raise CpdContactIdError("range_km no puede ser negativo")

    return {
        "destination": destination.value,
        "end_s": end_hex,
        "range_km": range_hex,
        "rate_bps": rate,
        "source": source.value,
        "start_s": start_hex,
        "v": CPD_CID_VERSION,
    }