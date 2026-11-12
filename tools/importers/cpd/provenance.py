from __future__ import annotations

from collections.abc import Mapping, Sequence

from core.contact.contact import Contact, LogicalNode
from core.domain.provenance import ProvenanceClassification

from experiments.contact_plan import (
    ContactPlanParameter,
    ContactPlanProvenance,
    ContactPlanSourceArtifact,
    ContactProvenanceStatement,
)

CPD_IMPORT_PROFILE = "native-t1-fcp+rx@v1"
CPD_LIGHT_SPEED_KM_S = 299792.458
CPD_CID_ALGORITHM = "cpd-cid-v1"

_COPY_FROM_ARTIFACT = (
    "copia desde el artefacto CPD (salida de diseño); "
    "no es una medición"
)
_CONTACT_COPY_STATEMENTS = (
    (ContactPlanParameter.TIME, "plan.json CPD: start_s/end_s"),
    (ContactPlanParameter.RATE, "plan.json CPD: rate_bps"),
)


def native_import_notes() -> str:
    return (
        f"Importación CPD perfil {CPD_IMPORT_PROFILE}; "
        f"algoritmo de contact_id={CPD_CID_ALGORITHM}; "
        "TIME/RATE=SOURCE_DIRECT (copia del artefacto CPD, no medición); "
        f"DELAY=SOURCE_TRANSFORMED (range_km/{CPD_LIGHT_SPEED_KM_S}); "
        "TOPOLOGY=TFI_ASSUMPTION (mapeo explícito)."
    )


def build_native_import_provenance(
    *,
    cpd_revision: str,
    plan_artifact_ref: str,
    plan_sha256: str,
    yaml_ref: str | None,
    yaml_sha256: str | None,
    generation_declaration: str | None,
    audit_image_ref: str | None,
    scenario_name: str,
    epoch_s: float,
    design_method: str,
    access_mode: str,
    mapping: Mapping[int, LogicalNode],
    contacts: Sequence[Contact],
    range_by_contact_id: Mapping[str, float],
) -> ContactPlanProvenance:
    source = ContactPlanSourceArtifact(
        source_ref=(
            "JSON nativo CPD (CLI); "
            "revisión declarada externamente; no verificada aquí: "
            f"{cpd_revision}"
        ),
        artifact_ref=plan_artifact_ref,
        artifact_sha256=plan_sha256,
    )

    mapping_text = "; ".join(
        f"{cpd_id}->{node.value}" for cpd_id, node in sorted(mapping.items())
    )
    references = _references(
        cpd_revision=cpd_revision,
        audit_image_ref=audit_image_ref,
        yaml_ref=yaml_ref,
        yaml_sha256=yaml_sha256,
    )
    generation = (
        generation_declaration
        if generation_declaration is not None
        else (
            f"design_method={design_method}; access_mode={access_mode} "
            "(leídos del plan nativo)"
        )
    )
    assumptions = [
        f"perfil_importacion_cpd={CPD_IMPORT_PROFILE}",
        f"algoritmo_contact_id={CPD_CID_ALGORITHM}",
        f"generacion: {generation}",
        f"mapeo_nodos: {mapping_text}",
        (
            f"velocidad_luz_km_s={CPD_LIGHT_SPEED_KM_S} "
            "solo para DELAY=range_km/c"
        ),
        f"nombre_escenario_cpd={scenario_name} (metadato CPD; no es scenario_id)",
        f"epoca_cpd_s={_format_float(epoch_s)} (metadato CPD; no se suma a ventanas)",
        f"plan_sha256_calculado={plan_sha256}",
    ]

    statements: list[ContactProvenanceStatement] = [
        ContactProvenanceStatement(
            parameter=ContactPlanParameter.TOPOLOGY,
            classification=ProvenanceClassification.TFI_ASSUMPTION,
            contact_id=None,
            source_ref="",
            assumption=(
                f"mapeo explícito CPD→TFI ({mapping_text}); "
                "no inferido por nombres ni orden"
            ),
        )
    ]
    for contact in contacts:
        range_km = range_by_contact_id[contact.contact_id]
        for parameter, source_ref in _CONTACT_COPY_STATEMENTS:
            statements.append(
                ContactProvenanceStatement(
                    parameter=parameter,
                    classification=ProvenanceClassification.SOURCE_DIRECT,
                    contact_id=contact.contact_id,
                    source_ref=source_ref,
                    assumption=_COPY_FROM_ARTIFACT,
                )
            )
        statements.append(
            ContactProvenanceStatement(
                parameter=ContactPlanParameter.DELAY,
                classification=ProvenanceClassification.SOURCE_TRANSFORMED,
                contact_id=contact.contact_id,
                source_ref="plan.json CPD: range_km",
                assumption=(
                    f"propagation_delay_s=range_km/{CPD_LIGHT_SPEED_KM_S} "
                    f"con range_km={_format_float(range_km)}; "
                    "transformación de importación TFI; no es una medición"
                ),
            )
        )

    return ContactPlanProvenance(
        source=source,
        statements=tuple(statements),
        references=tuple(references),
        assumptions=tuple(assumptions),
    )


def _references(
    *,
    cpd_revision: str,
    audit_image_ref: str | None,
    yaml_ref: str | None,
    yaml_sha256: str | None,
) -> list[str]:
    references = [
        f"revision_cpd={cpd_revision} (declarada externamente; no inferida del JSON)",
    ]
    if audit_image_ref is not None:
        references.append(
            f"imagen_auditoria_cpd={audit_image_ref} (declarada externamente)"
        )
    if yaml_ref is not None:
        references.append(f"yaml_ref={yaml_ref} (declarado externamente)")
    if yaml_sha256 is not None:
        references.append(
            f"yaml_sha256={yaml_sha256} (declarado externamente; no verificado aquí)"
        )
    return references


def _format_float(value: float) -> str:
    """Repr estable suficiente para metadatos; no redondea el Contact."""
    return format(value, ".17g")
