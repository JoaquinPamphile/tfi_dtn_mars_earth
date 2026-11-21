from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.contact.contact import Contact, LogicalNode
from core.contact.plan import ContactPlanError

from experiments.contact_plan import (
    CONTACT_PLAN_DEFINITION_SCHEMA_VERSION,
    ContactPlanDefinition,
    ContactPlanDefinitionError,
    ContactPlanSourceType,
)
from importers.cpd.cid import (
    CpdContactIdError,
    derive_cpd_contact_identity,
    validate_cpd_contact_identity_set,
)
from importers.cpd.provenance import (
    CPD_CID_ALGORITHM,
    CPD_IMPORT_PROFILE,
    CPD_LIGHT_SPEED_KM_S,
    build_native_import_provenance,
    native_import_notes,
)
from importers.cpd.support import (
    CpdSupportError,
    as_finite_float64,
    as_json_int,
    as_positive_json_int,
    loads_strict_utf8_json,
)

__all__ = [
    "CPD_CID_ALGORITHM",
    "CPD_IMPORT_PROFILE",
    "CPD_LIGHT_SPEED_KM_S",
    "CpdImportError",
    "CpdNativeImportRequest",
    "import_cpd_native_contact_plan",
]

_PLAN_KEYS = frozenset(
    {"contacts", "scenario_name", "epoch_s", "design_method", "access_mode"}
)
_CONTACT_KEYS = frozenset(
    {
        "tx_node",
        "rx_node",
        "start_s",
        "end_s",
        "rate_bps",
        "range_km",
        "start_cause",
        "end_cause",
        "transit_only",
        "owlt_s",
        "rx_start_s",
        "rx_end_s",
        "sep_deg",
        "shapiro_us",
    }
)
_NULL_ONLY_CONTACT_FIELDS = (
    "owlt_s",
    "rx_start_s",
    "rx_end_s",
    "sep_deg",
    "shapiro_us",
)
_OPTIONAL_NONBLANK_FIELDS = (
    "yaml_ref",
    "generation_declaration",
    "audit_image_ref",
)


class CpdImportError(ValueError):
    """El JSON nativo CPD no cumple el perfil de importación."""


@dataclass(frozen=True)
class CpdNativeImportRequest:
    plan_path: Path
    node_mapping: Mapping[int, LogicalNode]
    contact_plan_id: str
    cpd_revision: str
    plan_artifact_ref: str
    yaml_ref: str | None = None
    yaml_sha256: str | None = None
    generation_declaration: str | None = None
    audit_image_ref: str | None = None


def import_cpd_native_contact_plan(
    request: CpdNativeImportRequest,
) -> ContactPlanDefinition:
    """Traduce un ``plan.json`` nativo CPD a la configración apta para el banco."""
    _validate_request(request)
    mapping = _validated_mapping(request.node_mapping)
    document, plan_sha256 = _load_native_plan(Path(request.plan_path))
    header = _parse_plan_header(document)
    contacts, range_by_contact_id = _translate_contacts(header["contacts"], mapping)

    provenance = build_native_import_provenance(
        cpd_revision=request.cpd_revision,
        plan_artifact_ref=request.plan_artifact_ref,
        plan_sha256=plan_sha256,
        yaml_ref=request.yaml_ref,
        yaml_sha256=request.yaml_sha256,
        generation_declaration=request.generation_declaration,
        audit_image_ref=request.audit_image_ref,
        scenario_name=header["scenario_name"],
        epoch_s=header["epoch_s"],
        design_method=header["design_method"],
        access_mode=header["access_mode"],
        mapping=mapping,
        contacts=contacts,
        range_by_contact_id=range_by_contact_id,
    )
    declared_nodes = tuple(
        node for node in LogicalNode if node in set(mapping.values())
    )
    try:
        return ContactPlanDefinition(
            contact_plan_id=request.contact_plan_id,
            schema_version=CONTACT_PLAN_DEFINITION_SCHEMA_VERSION,
            source_type=ContactPlanSourceType.ORBIT_DERIVED,
            declared_nodes=declared_nodes,
            contacts=tuple(contacts),
            provenance=provenance,
            notes=native_import_notes(),
        )
    except (ContactPlanDefinitionError, ContactPlanError, ValueError) as exc:
        raise CpdImportError(str(exc)) from exc


def _validate_request(request: CpdNativeImportRequest) -> None:
    _require_nonblank(request.contact_plan_id, "contact_plan_id")
    _require_nonblank(request.cpd_revision, "cpd_revision")
    _require_nonblank(request.plan_artifact_ref, "plan_artifact_ref")
    for field in _OPTIONAL_NONBLANK_FIELDS:
        value = getattr(request, field)
        if value is not None:
            _require_nonblank(value, field)
    if request.yaml_sha256 is not None:
        _require_sha256_hex(request.yaml_sha256, "yaml_sha256")


def _load_native_plan(plan_path: Path) -> tuple[dict[str, Any], str]:
    raw_bytes = plan_path.read_bytes()
    plan_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    try:
        document = loads_strict_utf8_json(raw_bytes)
    except CpdSupportError as exc:
        msg = str(exc)
        if msg == "el documento debe ser UTF-8":
            raise CpdImportError("el plan CPD debe ser UTF-8") from exc
        if msg.startswith("JSON inválido:"):
            raise CpdImportError(
                msg.replace("JSON inválido:", "JSON CPD inválido:", 1)
            ) from exc
        raise CpdImportError(msg) from exc
    if not isinstance(document, dict):
        raise CpdImportError("la raíz del plan CPD debe ser un objeto JSON")
    return document, plan_sha256


def _parse_plan_header(document: dict[str, Any]) -> dict[str, Any]:
    _require_exact_keys(document, _PLAN_KEYS, scope="plan")
    contacts_raw = document["contacts"]
    if not isinstance(contacts_raw, list) or len(contacts_raw) < 1:
        raise CpdImportError("contacts debe ser un array no vacío")
    return {
        "contacts": contacts_raw,
        "scenario_name": _require_nonempty_string(
            document["scenario_name"], "scenario_name"
        ),
        "epoch_s": _require_finite_number(document["epoch_s"], "epoch_s"),
        "design_method": _require_exact_string(
            document["design_method"], "design_method", "fcp+rx"
        ),
        "access_mode": _require_exact_string(
            document["access_mode"], "access_mode", "true"
        ),
    }


def _translate_contacts(
    contacts_raw: list[Any],
    mapping: dict[int, LogicalNode],
) -> tuple[list[Contact], dict[str, float]]:
    contacts: list[Contact] = []
    identity_pairs: list[tuple[str, str]] = []
    range_by_contact_id: dict[str, float] = {}
    for index, item in enumerate(contacts_raw):
        if not isinstance(item, dict):
            raise CpdImportError(f"contacts[{index}] debe ser un objeto JSON")
        contact, identity_json, range_km = _translate_contact(item, mapping, index=index)
        contacts.append(contact)
        identity_pairs.append((contact.contact_id, identity_json))
        range_by_contact_id[contact.contact_id] = range_km
    try:
        validate_cpd_contact_identity_set(identity_pairs)
    except CpdContactIdError as exc:
        raise CpdImportError(str(exc)) from exc
    return contacts, range_by_contact_id


def _validated_mapping(
    node_mapping: Mapping[int, LogicalNode],
) -> dict[int, LogicalNode]:
    if not node_mapping:
        raise CpdImportError("el mapping de nodos no puede estar vacío")
    normalized: dict[int, LogicalNode] = {}
    seen_logical: dict[LogicalNode, int] = {}
    for key, value in node_mapping.items():
        if isinstance(key, bool) or not isinstance(key, int):
            raise CpdImportError("las claves del mapping deben ser enteros CPD")
        if not isinstance(value, LogicalNode):
            raise CpdImportError("los valores del mapping deben ser LogicalNode")
        if key in normalized:
            raise CpdImportError(f"mapping duplicado para nodo CPD {key}")
        previous = seen_logical.get(value)
        if previous is not None:
            raise CpdImportError(
                f"mapping no inyectivo: {previous} y {key} colapsan en {value.value}"
            )
        normalized[key] = value
        seen_logical[value] = key
    return normalized


def _translate_contact(
    item: dict[str, Any],
    mapping: dict[int, LogicalNode],
    *,
    index: int,
) -> tuple[Contact, str, float]:
    _require_exact_keys(item, _CONTACT_KEYS, scope=f"contacts[{index}]")

    tx_node = _require_json_int(item["tx_node"], "tx_node")
    rx_node = _require_json_int(item["rx_node"], "rx_node")
    if tx_node not in mapping:
        raise CpdImportError(f"nodo desconocido en mapping: tx_node={tx_node}")
    if rx_node not in mapping:
        raise CpdImportError(f"nodo desconocido en mapping: rx_node={rx_node}")

    start_s = _require_finite_number(item["start_s"], "start_s")
    end_s = _require_finite_number(item["end_s"], "end_s")
    range_km = _require_finite_number(item["range_km"], "range_km")
    rate_bps = _require_positive_json_int(item["rate_bps"], "rate_bps")
    _require_nonempty_string(item["start_cause"], "start_cause")
    _require_nonempty_string(item["end_cause"], "end_cause")
    if item["transit_only"] is True:
        raise CpdImportError("transit_only=true no está admitido en este perfil")
    if item["transit_only"] is not False:
        raise CpdImportError("transit_only debe ser boolean false")
    for field in _NULL_ONLY_CONTACT_FIELDS:
        if item[field] is not None:
            raise CpdImportError(
                f"{field} debe ser null en el perfil {CPD_IMPORT_PROFILE}"
            )

    source = mapping[tx_node]
    destination = mapping[rx_node]
    try:
        contact_id, identity_json = derive_cpd_contact_identity(
            source=source,
            destination=destination,
            start_s=start_s,
            end_s=end_s,
            rate_bps=rate_bps,
            range_km=range_km,
        )
    except CpdContactIdError as exc:
        raise CpdImportError(str(exc)) from exc

    delay = range_km / CPD_LIGHT_SPEED_KM_S
    if not math.isfinite(delay) or delay < 0.0:
        raise CpdImportError("propagation_delay_s calculado inválido")

    contact = Contact(
        contact_id=contact_id,
        source=source,
        destination=destination,
        start_time_sim=float(start_s),
        end_time_sim=float(end_s),
        data_rate_bps=rate_bps,
        propagation_delay_s=delay,
    )
    return contact, identity_json, float(range_km)


def _require_exact_keys(
    document: dict[str, Any],
    expected: frozenset[str],
    *,
    scope: str,
) -> None:
    keys = frozenset(document)
    missing = expected - keys
    extra = keys - expected
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(f"faltan {sorted(missing)}")
        if extra:
            parts.append(f"sobran {sorted(extra)}")
        raise CpdImportError(f"{scope}: conjunto de claves inválido; " + "; ".join(parts))


def _require_exact_string(value: object, field: str, expected: str) -> str:
    if not isinstance(value, str):
        raise CpdImportError(f"{field} debe ser string")
    if value != expected:
        raise CpdImportError(
            f"{field} debe ser {expected!r} en el perfil {CPD_IMPORT_PROFILE}"
        )
    return value


def _require_nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise CpdImportError(f"{field} debe ser string")
    if value.strip() == "":
        raise CpdImportError(f"{field} no debe estar vacío")
    return value


def _require_finite_number(value: object, field: str) -> float:
    try:
        return as_finite_float64(value)
    except CpdSupportError as exc:
        raise CpdImportError(f"{field}: {exc}") from None


def _require_json_int(value: object, field: str) -> int:
    try:
        return as_json_int(value)
    except CpdSupportError as exc:
        raise CpdImportError(f"{field} {exc}") from None


def _require_positive_json_int(value: object, field: str) -> int:
    try:
        return as_positive_json_int(value)
    except CpdSupportError as exc:
        raise CpdImportError(f"{field} {exc}") from None


def _require_nonblank(value: str, field: str) -> str:
    if value.strip() == "":
        raise CpdImportError(f"{field} no debe estar vacío")
    return value


def _require_sha256_hex(value: str, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise CpdImportError(f"{field} debe ser SHA-256 hexadecimal en minúsculas")
    return value
