"""
Abre el JSON de una campaña E1 y el plan de contactos que ese JSON nombra.
"""
from __future__ import annotations
from pathlib import Path
from pydantic import ValidationError
from experiments.contact_plan import ContactPlanDefinition
from experiments.experiment_bank import ExperimentBankDocument,ResolvedE1Campaign,resolve_e1_campaign

def load_e1_campaign(config_path: str | Path) -> ResolvedE1Campaign:
    """
    Carga la campaña descripta en config_path.
    """
    config_file = Path(config_path)
    bank = read_bank(config_file)
    plan_file = resolve_contact_plan_path(config_file, bank.scenario.contact_plan_file)
    plan = read_contact_plan(plan_file)
    return resolve_e1_campaign(bank, plan)

def resolve_contact_plan_path(config_file: Path, contact_plan_file: str) -> Path:
    reference = Path(contact_plan_file)
    if reference.is_absolute():
        return reference
    return config_file.parent / reference

def read_bank(config_file: Path) -> ExperimentBankDocument:
    text = read_utf8(config_file, "la configuración")
    try:
        return ExperimentBankDocument.model_validate_json(text)
    except ValidationError as error:
        raise ValueError(
            f"no se pudo validar la configuración: {config_file}\n{error}"
        ) from error

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
