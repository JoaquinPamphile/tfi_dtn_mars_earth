"""Paquete de evidencia de una campaña ya ejecutada.

Agrupa el manifiesto, el resultado que ese manifiesto ya contiene y la
metadata de reproducibilidad. No copia las métricas a otro objeto y no
incluye capturas.

La escritura oficial usa el identificador de campaña. Si el archivo ya
existe con otro contenido, no se reemplaza.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiments.campaign import CampaignResult, CampaignSpec
from experiments.canonical import (
    EVIDENCE_SCHEMA_VERSION,
    HASH_ALGORITHM,
    SOFTWARE_VERSION,
    canonical_json_text,
)
from experiments.manifest import campaign_manifest

OFFICIAL_CAMPAIGNS = {
    "e1-strategy-alessi-10k": "e1",
    "e2-offered-load": "e2",
    "e3-recovery-policy": "e3",
}
SENSITIVITY_CAMPAIGNS = {
    "e3-loss-position-sensitivity": "e3",
}


class EvidenceExistsError(FileExistsError):
    """El destino ya existe y su contenido no es el mismo paquete."""


@dataclass(frozen=True, slots=True)
class EvidenceExport:
    """Rutas escritas, relativas a la raíz indicada."""

    root: Path
    paths: tuple[Path, ...]


def build_evidence_package(spec: CampaignSpec, result: CampaignResult) -> dict[str, Any]:
    """Paquete de E1, E2, E3 o de la sensibilidad de E3."""
    family, role = _family_role(spec.campaign_id)
    return _package(spec, result, family=family, role=role)


def export_campaign_evidence(
    spec: CampaignSpec,
    result: CampaignResult,
    *,
    root: Path,
) -> EvidenceExport:
    """Escribe el paquete oficial o la sensibilidad. No pisa un archivo distinto."""
    package = build_evidence_package(spec, result)
    identity = spec.campaign_identity
    family = str(package["family"])
    role = str(package["role"])
    written: list[Path] = []
    if role == "official":
        evidence_name = f"official/{family}/{identity}.json"
        written.append(_place(root / evidence_name, canonical_json_text(package)))
        written.append(
            _place(
                root / "manifests" / f"{identity}.json",
                canonical_json_text(_provenance_record(package, evidence_name)),
            )
        )
    elif role == "sensitivity":
        written.append(
            _place(
                root / "manifests" / f"{identity}.json",
                canonical_json_text(package),
            )
        )
    else:
        raise ValueError("rol de evidencia no exportable")
    return EvidenceExport(root=root, paths=tuple(written))


def export_development_evidence(
    spec: CampaignSpec,
    result: CampaignResult,
    *,
    root: Path,
) -> EvidenceExport:
    """Exporta una campaña de desarrollo fuera de ``official/``.

    No acepta E1, E2, E3 ni la sensibilidad: esas campañas tienen su ruta.
    """
    if spec.campaign_id in OFFICIAL_CAMPAIGNS or spec.campaign_id in SENSITIVITY_CAMPAIGNS:
        raise ValueError("una campaña oficial no se exporta como desarrollo")
    package = _package(spec, result, family="development", role="development")
    path = root / "development" / f"{spec.campaign_identity}.json"
    resolved = path.resolve()
    official = (root / "official").resolve()
    if resolved == official or official in resolved.parents:
        raise ValueError("el desarrollo no se escribe en official/")
    return EvidenceExport(
        root=root,
        paths=(_place(path, canonical_json_text(package)),),
    )


def _family_role(campaign_id: str) -> tuple[str, str]:
    if campaign_id in OFFICIAL_CAMPAIGNS:
        return OFFICIAL_CAMPAIGNS[campaign_id], "official"
    if campaign_id in SENSITIVITY_CAMPAIGNS:
        return SENSITIVITY_CAMPAIGNS[campaign_id], "sensitivity"
    raise ValueError(
        "solo se exporta evidencia de E1, E2, E3 o de la sensibilidad de E3"
    )


def _package(
    spec: CampaignSpec,
    result: CampaignResult,
    *,
    family: str,
    role: str,
) -> dict[str, Any]:
    manifest = campaign_manifest(spec, result).to_dict()
    return {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "family": family,
        "role": role,
        "campaign_id": spec.campaign_id,
        "campaign_identity": spec.campaign_identity,
        "reproducibility": _reproducibility(),
        "campaign_manifest": manifest,
    }


def _reproducibility() -> dict[str, Any]:
    return {
        "hash_algorithm": HASH_ALGORITHM,
        "software_version": SOFTWARE_VERSION,
        "configuration_hash_includes_trace_level": True,
        "trace_level_is_scientific_factor": False,
        "execution_identity_inputs": [
            "scenario_id",
            "seed",
            "strategy_type",
            "batch_size_events",
        ],
        "dataset_identity_inputs": ["scenario_id", "seed"],
        "dataset_fingerprint": (
            "SHA-256 de las líneas de identidad del dataset materializado"
        ),
        "wall_clock_in_scientific_identity": False,
        "note": (
            "El reloj de pared no entra en las identidades científicas ni en "
            "configuration_hash. trace_level distingue la configuración de "
            "ejecución y no es un factor de E1, E2 ni E3."
        ),
    }


def _provenance_record(package: dict[str, Any], evidence_file: str) -> dict[str, Any]:
    """Procedencia sin repetir las métricas del paquete oficial."""
    manifest = package["campaign_manifest"]
    order = []
    for run in manifest["runs"]:
        order.append(
            {
                "index": run["index"],
                "label": run["label"],
                "configuration_hash": run["configuration_hash"],
                "dataset_fingerprint": run["dataset_fingerprint"],
                "dataset_identity": run["dataset_identity"],
                "execution_identity": run["execution_identity"],
                "completed": run["completed"],
                "failed": run["failed"],
            }
        )
    return {
        "evidence_schema_version": package["evidence_schema_version"],
        "family": package["family"],
        "role": package["role"],
        "campaign_id": package["campaign_id"],
        "campaign_identity": package["campaign_identity"],
        "evidence_file": evidence_file,
        "status": manifest["status"],
        "run_order": order,
        "reproducibility": package["reproducibility"],
    }


def _place(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    if path.exists():
        if path.read_bytes() == data:
            return path
        raise EvidenceExistsError(f"no se sobrescribe {path}: el contenido difiere")
    binary = getattr(os, "O_BINARY", 0)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | binary
    descriptor = os.open(path, flags)
    try:
        os.write(descriptor, data)
    finally:
        os.close(descriptor)
    return path
