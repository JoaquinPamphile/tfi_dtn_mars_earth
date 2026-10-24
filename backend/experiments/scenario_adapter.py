from __future__ import annotations
from experiments.contact_plan import ContactPlanDefinition
from experiments.scenario import Scenario

def scenario_from_contact_plan_definition(
    definition: ContactPlanDefinition,
    *,
    scenario_id: str,
    horizon_seconds: float | None = None,
    description: str = "",
    notes: str = "",
) -> Scenario:
    runtime_plan = definition.to_runtime_contact_plan()
    return Scenario(
        scenario_id=scenario_id,
        contacts=runtime_plan.contacts,
        horizon_seconds=horizon_seconds,
        description=description,
        notes=notes,
    )
