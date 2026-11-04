from __future__ import annotations

import sys
from pathlib import Path

from core.contact.contact import LogicalNode
from experiments.contact_plan import (
    ContactPlanDefinition,
    contact_plan_definition_fingerprint,
    contact_plan_fingerprint,
)
from experiments.experiment_bank_result import write_exclusive_canonical_json
from importers.cpd.native import (
    CpdImportError,
    CpdNativeImportRequest,
    import_cpd_native_contact_plan,
)
from importers.cpd.support import CpdSupportError, loads_strict_utf8_json

from cli.utils import parse_path_options

_OPCIONES = frozenset({"--config", "--output"})
_LOGICAL_BY_VALUE = {node.value: node for node in LogicalNode}
_OPTIONAL_FIELDS = (
    "yaml_ref",
    "yaml_sha256",
    "generation_declaration",
    "audit_image_ref",
)


class ImportCpdConfigError(ValueError):
    """La configuración de ``import-cpd`` es inválida."""


def comando_import_cpd(tokens: list[str], *, ayuda: str) -> int:
    """Importa un plan nativo CPD y escribe un ContactPlanDefinition apto para el motor de simulación"""
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        rutas = _rutas_de_opciones(tokens)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    config_path = Path(rutas["--config"])
    output_path = Path(rutas["--output"])

    if output_path.exists():
        print(f"el archivo de salida ya existe: {output_path}", file=sys.stderr)
        return 1

    try:
        request = _load_import_request(config_path)
        definition = import_cpd_native_contact_plan(request)
        document = definition.model_dump(mode="json")
        written = write_exclusive_canonical_json(output_path, document)
    except FileExistsError:
        print(f"el archivo de salida ya existe: {output_path}", file=sys.stderr)
        return 1
    except (OSError, ImportCpdConfigError, CpdImportError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(_resumen(written, definition))
    return 0


def _rutas_de_opciones(tokens: list[str]) -> dict[str, str]:
    return parse_path_options(
        tokens,
        allowed=_OPCIONES,
        command_name="import-cpd",
        require_output=True,
    )


def _load_import_request(config_path: Path) -> CpdNativeImportRequest:
    try:
        raw = config_path.read_bytes()
    except OSError as exc:
        raise ImportCpdConfigError(
            f"no se pudo leer la configuración: {config_path}\n{exc}"
        ) from exc
    try:
        document = loads_strict_utf8_json(raw)
    except CpdSupportError as exc:
        msg = str(exc)
        if msg == "el documento debe ser UTF-8":
            raise ImportCpdConfigError(
                f"la configuración debe ser UTF-8: {config_path}"
            ) from exc
        raise ImportCpdConfigError(f"JSON de configuración inválido: {msg}") from exc
    if not isinstance(document, dict):
        raise ImportCpdConfigError("la configuración debe ser un objeto JSON")

    try:
        plan_path = _resolve_plan_path(config_path, document["plan_path"])
        node_mapping = _convert_node_mapping(document["node_mapping"])
        contact_plan_id = _require_config_string(document["contact_plan_id"], "contact_plan_id")
        cpd_revision = _require_config_string(document["cpd_revision"], "cpd_revision")
        plan_artifact_ref = _require_config_string(
            document["plan_artifact_ref"], "plan_artifact_ref"
        )
    except KeyError as exc:
        raise ImportCpdConfigError(f"falta la clave {exc.args[0]!r} en la configuración") from None

    optional: dict[str, str] = {}
    for field in _OPTIONAL_FIELDS:
        if field not in document:
            continue
        optional[field] = _require_config_string(document[field], field)

    return CpdNativeImportRequest(
        plan_path=plan_path,
        node_mapping=node_mapping,
        contact_plan_id=contact_plan_id,
        cpd_revision=cpd_revision,
        plan_artifact_ref=plan_artifact_ref,
        **optional,
    )


def _resolve_plan_path(config_path: Path, raw: object) -> Path:
    plan_text = _require_config_string(raw, "plan_path")
    candidate = Path(plan_text)
    if candidate.is_absolute():
        return candidate
    return (config_path.resolve().parent / candidate).resolve()


def _convert_node_mapping(raw: object) -> dict[int, LogicalNode]:
    """Manejo de tipo de datos."""
    if not isinstance(raw, dict):
        raise ImportCpdConfigError("node_mapping debe ser un objeto JSON")

    mapping: dict[int, LogicalNode] = {}
    for key, value in raw.items():
        cpd_id = _mapping_key_to_int(key)
        node = _mapping_value_to_logical(value)
        if cpd_id in mapping:
            raise ImportCpdConfigError(
                f"mapping duplicado tras conversión para nodo CPD {cpd_id}"
            )
        mapping[cpd_id] = node
    return mapping


def _mapping_key_to_int(key: object) -> int:
    if not isinstance(key, str):
        raise ImportCpdConfigError(
            "las claves de node_mapping deben ser strings decimales de enteros CPD"
        )
    try:
        parsed = int(key, 10)
    except ValueError as exc:
        raise ImportCpdConfigError(
            f"clave de node_mapping no es un entero decimal: {key!r}"
        ) from exc
    if str(parsed) != key:
        raise ImportCpdConfigError(
            f"clave de node_mapping no canónica tras conversión: {key!r}"
        )
    return parsed


def _mapping_value_to_logical(value: object) -> LogicalNode:
    if not isinstance(value, str):
        raise ImportCpdConfigError(
            "los valores de node_mapping deben ser strings de LogicalNode"
        )
    node = _LOGICAL_BY_VALUE.get(value)
    if node is None:
        admitidos = ", ".join(sorted(_LOGICAL_BY_VALUE))
        raise ImportCpdConfigError(
            f"LogicalNode desconocido en node_mapping: {value!r}. "
            f"Admitidos: {admitidos}."
        )
    return node


def _require_config_string(value: object, field: str) -> str:
    """Solo tipo. El importer exige nonblank en los campos del request."""
    if not isinstance(value, str):
        raise ImportCpdConfigError(f"{field} debe ser string")
    return value


def _resumen(written: Path, definition: ContactPlanDefinition) -> str:
    lines = [
        f"Archivo generado: {written}",
        f"contact_plan_id: {definition.contact_plan_id}",
        f"contactos: {len(definition.contacts)}",
        f"fingerprint operacional: {contact_plan_fingerprint(definition)}",
        f"fingerprint documental: {contact_plan_definition_fingerprint(definition)}",
        (
            "Advertencia: la revisión CPD y los metadatos externos de la "
            "configuración son declarados; no se verifican aquí ni acreditan "
            "validación orbital, ausencia de conflictos de interfaz ni "
            "aplicabilidad experimental."
        ),
    ]
    return "\n".join(lines) + "\n"
