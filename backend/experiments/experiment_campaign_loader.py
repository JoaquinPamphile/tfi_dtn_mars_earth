from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from experiments.contact_plan import ContactPlanDefinition
from experiments.experiment_bank import (
    ExperimentBankDocument, ResolvedExperimentBank, resolve_experiment_bank,
)


def load_declared_configuration(
    config_path: str | Path,
    *,
    input_sources: dict[str, dict[str, str]] | None = None,
) -> ResolvedExperimentBank:
    """Valida V2 antes de abrir su plan; lee y hashea los mismos bytes una vez."""
    config_file = Path(config_path)
    if input_sources is not None:
        input_sources.clear()
    configuration_source = {} if input_sources is not None else None
    bank = bank_from_text(
        read_utf8(config_file, "la configuración", source=configuration_source), config_file,
    )
    plan_file = resolve_declared_path(config_file, bank.scenario.contact_plan_file)
    plan_source = {} if input_sources is not None else None
    plan = read_contact_plan(plan_file, source=plan_source)
    if input_sources is not None:
        input_sources["contact_plan"] = plan_source
    resolved = resolve_experiment_bank(bank, plan)
    if input_sources is not None:
        input_sources["configuration"] = configuration_source
    return resolved


def resolve_declared_path(declaring_file: Path, reference: str) -> Path:
    """Resuelve el plan respecto de la configuración que lo declara."""
    path = Path(reference)
    return path if path.is_absolute() else declaring_file.parent / path


def _json_object(text: str, path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"no se pudo validar la configuración: {path}\n{error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"no se pudo validar la configuración: {path}\nel documento debe ser un objeto JSON")
    return payload


def bank_from_text(text: str, config_file: Path) -> ExperimentBankDocument:
    payload = _json_object(text, config_file)
    try:
        return ExperimentBankDocument.model_validate(payload)
    except ValidationError as error:
        raise ValueError(f"no se pudo validar la configuración: {config_file}\n{error}") from error


def read_contact_plan(
    plan_file: Path, *, source: dict[str, str] | None = None,
) -> ContactPlanDefinition:
    text = read_utf8(plan_file, "el ContactPlan", source=source)
    try:
        return ContactPlanDefinition.model_validate_json(text)
    except ValidationError as error:
        raise ValueError(
            f"no se pudo validar el ContactPlan: {plan_file}\n{error}"
        ) from error

def read_utf8(
    path: Path, description: str, *, source: dict[str, str] | None = None,
) -> str:
    try:
        if source is None:
            return path.read_text(encoding="utf-8")
        # Los mismos bytes se hashean y se decodifican una sola vez. TextIOWrapper
        # conserva la normalización universal de saltos de Path.read_text.
        from experiments.experiment_bank_run_index import source_from_bytes
        raw = path.read_bytes()
        with io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8") as stream:
            text = stream.read()
        source.update(source_from_bytes(str(path), raw))
        return text
    except UnicodeDecodeError as error:
        raise ValueError(f"no se pudo leer {description} como UTF-8: {path}\n{error}") from error
