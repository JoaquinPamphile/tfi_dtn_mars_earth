"""Documento autocontenido del resultado del banco E1 configurable.

La construcción es puramente en memoria. ``run_results`` sigue por posición
el orden de ``campaign_manifest.runs`` y conserva solamente los campos de
``ScientificRunResult`` que ese manifiesto no serializa.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from experiments.campaign import CampaignResult
from experiments.canonical import canonical_json_text, jsonable
from experiments.contact_plan import (
    contact_plan_definition_fingerprint,
    contact_plan_fingerprint,
)
from experiments.experiment_bank import ResolvedE1Campaign
from experiments.manifest import campaign_manifest
from experiments.result import ScientificRunResult
from experiments.software_provenance import SoftwareProvenance, current_provenance

BANK_RESULT_SCHEMA_VERSION = 1
E1_CONFIGURABLE_BANK_RESULT = "e1_configurable_bank_result"


def build_e1_bank_result(
    resolved: ResolvedE1Campaign,
    result: CampaignResult,
    provenance: SoftwareProvenance | None = None,
) -> dict[str, Any]:
    """Combina la entrada resuelta y su resultado sin ejecutar ni leer archivos.

    Materializar el manifiesto conserva su coste existente: calcula el hash de
    configuración y la huella del dataset esperado de cada corrida. Esta última
    puede generar en memoria todos los eventos esperados cuando aún no está en
    la caché de fingerprints.
    """
    if not isinstance(resolved, ResolvedE1Campaign):
        raise TypeError("resolved debe ser un ResolvedE1Campaign")
    if not isinstance(result, CampaignResult):
        raise TypeError("result debe ser un CampaignResult")
    if provenance is not None and not isinstance(provenance, SoftwareProvenance):
        raise TypeError("provenance debe ser una SoftwareProvenance")

    observed = current_provenance() if provenance is None else provenance
    manifest = campaign_manifest(
        resolved.campaign,
        result,
        provenance=observed,
    ).to_dict()
    _require_completed_results_match_specs(resolved, result)

    document = {
        "bank_result_schema_version": BANK_RESULT_SCHEMA_VERSION,
        "artifact_type": E1_CONFIGURABLE_BANK_RESULT,
        "configuration": resolved.bank_document.model_dump(mode="json"),
        "contact_plan_definition": resolved.contact_plan_definition.model_dump(
            mode="json"
        ),
        "contact_plan_fingerprint": contact_plan_fingerprint(
            resolved.contact_plan_definition
        ),
        "contact_plan_definition_fingerprint": (
            contact_plan_definition_fingerprint(resolved.contact_plan_definition)
        ),
        "software_provenance": {
            "software_version": observed.software_version,
            "source_revision": observed.source_revision,
            "source_state": observed.source_state,
        },
        "campaign_manifest": manifest,
        "run_results": [
            {"result": None if run.result is None else _result_remainder(run.result)}
            for run in result.runs
        ],
    }
    serialized = jsonable(document)
    if not isinstance(serialized, dict):
        raise RuntimeError("el resultado del banco debe ser un objeto JSON")
    return serialized


def write_e1_bank_result(path: Path, document: dict[str, Any]) -> Path:
    """Publica un documento nuevo sin reemplazar ninguna entrada existente.

    El temporal se escribe y cierra en el mismo directorio. El enlace duro
    publica entonces el inode completo con semántica de creación exclusiva:
    si ``path`` apareció antes de ese paso, ``os.link`` falla. No hay fallback
    para filesystems que no admitan enlaces duros.
    """
    if not isinstance(path, Path):
        raise TypeError("path debe ser un Path")
    if not isinstance(document, dict):
        raise TypeError("document debe ser un dict")

    text = canonical_json_text(document)
    if document.get("artifact_type") != E1_CONFIGURABLE_BANK_RESULT:
        raise ValueError("artifact_type no corresponde a un resultado del banco E1")
    version = document.get("bank_result_schema_version")
    if isinstance(version, bool) or version != BANK_RESULT_SCHEMA_VERSION:
        raise ValueError(
            "bank_result_schema_version no soportada: "
            f"se requiere {BANK_RESULT_SCHEMA_VERSION}"
        )

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    descriptor_open = True
    try:
        with os.fdopen(
            descriptor,
            mode="w",
            encoding="utf-8",
            newline="\n",
        ) as stream:
            descriptor_open = False
            stream.write(text)
        os.link(temporary, path)
    finally:
        if descriptor_open:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return path


def _require_completed_results_match_specs(
    resolved: ResolvedE1Campaign,
    result: CampaignResult,
) -> None:
    """Verifica los vínculos que existen en una corrida terminada.

    Los vínculos de campaña, cantidad, índice y rótulo ya fueron verificados por
    ``campaign_manifest``. Una corrida fallida no contiene un resultado del que
    puedan contrastarse identidades; queda vinculada por esos campos.
    """
    for planned, finished in zip(
        resolved.campaign.runs,
        result.runs,
        strict=True,
    ):
        completed = finished.result
        if completed is None:
            continue
        spec = planned.spec
        expected = {
            "scenario_id": spec.scenario.scenario_id,
            "workload_id": spec.workload.workload_id,
            "seed": spec.seed,
            "dataset_identity": spec.dataset_identity,
            "experiment_identity": spec.experiment_identity,
            "execution_identity": spec.execution_identity,
            "strategy_type": spec.strategy_type,
            "batch_size_events": spec.batch_size_events,
            "stop_policy": spec.stop_policy.value,
            "horizon_seconds": spec.horizon_seconds,
            "recovery_policy": spec.recovery_policy.value,
            "offered_load_fraction": spec.workload.offered_load_fraction,
        }
        for field, expected_value in expected.items():
            if getattr(completed, field) != expected_value:
                raise ValueError(
                    "el resultado de la corrida no coincide con su especificación: "
                    f"label={planned.label}, campo={field}"
                )


def _result_remainder(result: ScientificRunResult) -> dict[str, Any]:
    """Campos observados que ``ScientificRunManifest`` no conserva."""
    return {
        "offered_load_fraction": result.offered_load_fraction,
        "simulation_time": result.simulation_time,
        "events": [asdict(event) for event in result.events],
        "events_persisted_earth": result.events_persisted_earth,
        "events_confirmed_mars": result.events_confirmed_mars,
        "trace_entry_count": result.trace_entry_count,
    }
