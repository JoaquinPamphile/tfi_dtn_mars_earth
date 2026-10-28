"""
Abre el JSON de una campaña configurable, o de una suite, y el plan que nombra.

``load_declared_configuration`` es la entrada de ``inspect`` y ``run``.
Lee el archivo una vez y, por el discriminador explícito, carga esa campaña
o una suite. No prueba el otro modelo si el primero no valida.

Una suite valida cada entrada antes de devolverse. Rechaza una sección distinta
de la declarada y una suite anidada antes de abrir el plan de esa entrada.
No ejecuta el motor.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from experiments.contact_plan import ContactPlanDefinition
from experiments.experiment_bank import (
    ExperimentBankDocument,
    ExperimentBankE2Section,
    ExperimentBankE3Section,
    ExperimentBankE3SensitivitySection,
    ExperimentBankExperiments,
    ResolvedE1Campaign,
    ResolvedE2Campaign,
    ResolvedE3Campaign,
    ResolvedE3SensitivityCampaign,
    resolve_e1_campaign,
    resolve_e2_campaign,
    resolve_e3_campaign,
    resolve_e3_sensitivity_campaign,
)
from experiments.experiment_suite import (
    ResolvedSuite,
    ResolvedSuiteEntry,
    suite_from_text,
)

DocumentKind = Literal["campaign", "suite"]
ResolvedCampaign = (
    ResolvedE1Campaign
    | ResolvedE2Campaign
    | ResolvedE3Campaign
    | ResolvedE3SensitivityCampaign
)

def load_declared_configuration(
    config_path: str | Path,
) -> ResolvedCampaign | ResolvedSuite:
    """Carga la campaña o la suite que declara el archivo.

    Lee el archivo una sola vez. El discriminador es la clave presente:
    ``schema_version`` o ``suite_schema_version``. No prueba el otro
    modelo si el primero no valida. Una suite carga cada configuración
    una vez y, con ella, su plan una vez. No ejecuta el motor.
    """
    config_file = Path(config_path)
    text = read_utf8(config_file, "la configuración")
    return _load_declared_text(config_file, text, nested=False)


def resolve_loaded_bank(
    config_file: Path,
    bank: ExperimentBankDocument,
) -> ResolvedCampaign:
    """Resuelve la sección ya validada y abre su plan una sola vez."""
    experiments = bank.experiments
    if isinstance(experiments, ExperimentBankExperiments):
        resolve = resolve_e1_campaign
    elif isinstance(experiments, ExperimentBankE2Section):
        resolve = resolve_e2_campaign
    elif isinstance(experiments, ExperimentBankE3Section):
        resolve = resolve_e3_campaign
    elif isinstance(experiments, ExperimentBankE3SensitivitySection):
        resolve = resolve_e3_sensitivity_campaign
    else:
        raise ValueError(
            "el documento no selecciona experiments.e1, "
            "experiments.e2, experiments.e3 ni experiments.e3_sensitivity"
        )
    plan_file = resolve_contact_plan_path(
        config_file,
        bank.scenario.contact_plan_file,
    )
    plan = read_contact_plan(plan_file)
    return resolve(bank, plan)


def document_kind(payload: dict[str, Any]) -> DocumentKind:
    """Elige campaña o suite por la clave presente. No valida ninguno de los dos."""
    has_campaign = "schema_version" in payload
    has_suite = "suite_schema_version" in payload
    if has_campaign and has_suite:
        raise ValueError(
            "el documento declara schema_version y suite_schema_version; "
            "debe declarar exactamente uno"
        )
    if has_suite:
        return "suite"
    if has_campaign:
        return "campaign"
    raise ValueError(
        "el documento debe declarar schema_version o suite_schema_version"
    )


def resolve_suite_config_path(suite_file: Path, config_file: str) -> Path:
    """Resuelve ``config_file`` respecto de la suite. Una ruta absoluta se usa tal cual."""
    reference = Path(config_file)
    if reference.is_absolute():
        return reference
    return suite_file.parent / reference


def _load_declared_text(
    config_file: Path,
    text: str,
    *,
    nested: bool,
) -> ResolvedCampaign | ResolvedSuite:
    payload = _json_object(text, config_file)
    kind = document_kind(payload)
    if kind == "suite":
        if nested:
            raise ValueError(f"no se admiten suites anidadas: {config_file}")
        return _load_suite(config_file, text)
    return _load_campaign_text(config_file, text, expected_id=None)


def _load_suite(suite_file: Path, text: str) -> ResolvedSuite:
    document = suite_from_text(text, suite_file)
    entries: list[ResolvedSuiteEntry] = []
    for item in document.experiments:
        child = resolve_suite_config_path(suite_file, item.config_file)
        child_text = read_utf8(child, "la configuración")
        resolved = _load_campaign_entry(child, child_text, item.id)
        entries.append(
            ResolvedSuiteEntry(
                experiment_id=item.id,
                config_file=item.config_file,
                resolved=resolved,
            )
        )
    return ResolvedSuite(document=document, entries=tuple(entries))


def _load_campaign_entry(
    config_file: Path,
    text: str,
    expected_id: str,
) -> ResolvedCampaign:
    payload = _json_object(text, config_file)
    if document_kind(payload) == "suite":
        raise ValueError(f"no se admiten suites anidadas: {config_file}")
    return _load_campaign_text(config_file, text, expected_id=expected_id)


def _load_campaign_text(
    config_file: Path,
    text: str,
    *,
    expected_id: str | None,
) -> ResolvedCampaign:
    bank = bank_from_text(text, config_file)
    if expected_id is not None:
        actual = _bank_section(bank)
        if actual != expected_id:
            raise ValueError(
                f"la entrada {expected_id} no coincide con la sección "
                f"experiments.{actual} de {config_file}"
            )
    return resolve_loaded_bank(config_file, bank)


def _bank_section(bank: ExperimentBankDocument) -> str:
    experiments = bank.experiments
    if isinstance(experiments, ExperimentBankExperiments):
        return "e1"
    if isinstance(experiments, ExperimentBankE2Section):
        return "e2"
    if isinstance(experiments, ExperimentBankE3Section):
        return "e3"
    if isinstance(experiments, ExperimentBankE3SensitivitySection):
        return "e3_sensitivity"
    raise ValueError(
        "el documento no selecciona experiments.e1, "
        "experiments.e2, experiments.e3 ni experiments.e3_sensitivity"
    )


def _json_object(text: str, path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"no se pudo validar la configuración: {path}\n{error}"
        ) from error
    if not isinstance(payload, dict):
        raise ValueError(
            f"no se pudo validar la configuración: {path}\n"
            "el documento debe ser un objeto JSON"
        )
    return payload


def bank_from_text(text: str, config_file: Path) -> ExperimentBankDocument:
    try:
        return ExperimentBankDocument.model_validate_json(text)
    except ValidationError as error:
        raise ValueError(
            f"no se pudo validar la configuración: {config_file}\n{error}"
        ) from error


def resolve_contact_plan_path(config_file: Path, contact_plan_file: str) -> Path:
    reference = Path(contact_plan_file)
    if reference.is_absolute():
        return reference
    return config_file.parent / reference

def read_contact_plan(plan_file: Path) -> ContactPlanDefinition:
    text = read_utf8(plan_file, "el ContactPlan")
    try:
        return ContactPlanDefinition.model_validate_json(text)
    except ValidationError as error:
        raise ValueError(
            f"no se pudo validar el ContactPlan: {plan_file}\n{error}"
        ) from error

def read_utf8(path: Path, description: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"no se pudo leer {description} como UTF-8: {path}\n{error}") from error
