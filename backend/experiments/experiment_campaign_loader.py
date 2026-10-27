"""
Abre el JSON de una campaña configurable y el plan de contactos que nombra.

``load_e1_campaign`` rechaza un documento E2 o E3 antes de abrir el plan.
``load_e2_campaign`` rechaza un documento E1 o E3 antes de resolver esa ruta
y de abrir el archivo. ``load_e3_campaign`` rechaza un documento E1 o E2
antes de resolver esa ruta y de abrir el archivo. Ninguno ejecuta la campaña.
"""
from __future__ import annotations
from pathlib import Path
from pydantic import ValidationError
from experiments.contact_plan import ContactPlanDefinition
from experiments.experiment_bank import (
    ExperimentBankDocument,
    ResolvedE1Campaign,
    ResolvedE2Campaign,
    ResolvedE3Campaign,
    require_e1_bank_selection,
    require_e2_bank_selection,
    require_e3_bank_selection,
    resolve_e1_campaign,
    resolve_e2_campaign,
    resolve_e3_campaign,
)

def load_e1_campaign(config_path: str | Path) -> ResolvedE1Campaign:
    """
    Carga la campaña E1 descripta en config_path.

    Un documento que selecciona E2 o E3 se rechaza antes de abrir el
    ContactPlan y antes de resolver la campaña.
    """
    config_file = Path(config_path)
    bank = read_bank(config_file)
    require_e1_bank_selection(bank)
    plan_file = resolve_contact_plan_path(config_file, bank.scenario.contact_plan_file)
    plan = read_contact_plan(plan_file)
    return resolve_e1_campaign(bank, plan)

def load_e2_campaign(config_path: str | Path) -> ResolvedE2Campaign:
    """
    Carga la campaña E2 descripta en config_path.

    Un documento que selecciona E1 o E3 se rechaza antes de resolver la
    ruta del ContactPlan y antes de abrirlo.
    """
    config_file = Path(config_path)
    bank = read_bank(config_file)
    require_e2_bank_selection(bank)
    plan_file = resolve_contact_plan_path(config_file, bank.scenario.contact_plan_file)
    plan = read_contact_plan(plan_file)
    return resolve_e2_campaign(bank, plan)

def load_e3_campaign(config_path: str | Path) -> ResolvedE3Campaign:
    """
    Carga la campaña E3 descripta en config_path.

    Un documento que selecciona E1 o E2 se rechaza antes de resolver la
    ruta del ContactPlan y antes de abrirlo.
    """
    config_file = Path(config_path)
    bank = read_bank(config_file)
    require_e3_bank_selection(bank)
    plan_file = resolve_contact_plan_path(config_file, bank.scenario.contact_plan_file)
    plan = read_contact_plan(plan_file)
    return resolve_e3_campaign(bank, plan)

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
