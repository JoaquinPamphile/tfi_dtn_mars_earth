"""Documentos autocontenidos de los resultados del banco configurable.

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

from experiments.campaign import CampaignResult, CampaignSpec
from experiments.canonical import canonical_json_text, jsonable
from experiments.contact_plan import (
    ContactPlanDefinition,
    contact_plan_definition_fingerprint,
    contact_plan_fingerprint,
)
from experiments.experiment_bank import ResolvedE1Campaign, ResolvedE2Campaign
from experiments.manifest import campaign_manifest
from experiments.offered_load import ReferenceCapacity
from experiments.result import ScientificRunResult
from experiments.software_provenance import SoftwareProvenance, current_provenance

BANK_RESULT_SCHEMA_VERSION = 1
E1_CONFIGURABLE_BANK_RESULT = "e1_configurable_bank_result"
E2_CONFIGURABLE_BANK_RESULT = "e2_configurable_bank_result"


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
    observed, manifest = _observed_campaign_manifest(
        resolved.campaign,
        result,
        provenance,
    )
    document = _configured_bank_document(
        artifact_type=E1_CONFIGURABLE_BANK_RESULT,
        configuration=resolved.bank_document.model_dump(mode="json"),
        contact_plan_definition=resolved.contact_plan_definition,
        provenance=observed,
        manifest=manifest,
        result=result,
    )
    return _json_object(document)


def build_e2_bank_result(
    resolved: ResolvedE2Campaign,
    result: CampaignResult,
    provenance: SoftwareProvenance | None = None,
) -> dict[str, Any]:
    """Combina la campaña E2 resuelta y su resultado, sin ejecutar ni leer archivos.

    ``reference_capacity`` es la capacidad nominal ya resuelta Marte → relé:
    escenario, intervalo, bytes serializables y contactos que aportan. Se
    copia tal como quedó en la resolución. No se recalcula, no sale de un
    formateador y no se sustituye por una constante. No es capacidad extremo
    a extremo, utilización realizada ni garantía de entrega.

    Las fracciones, los conteos y las tasas quedan en las especificaciones
    del manifiesto. Las métricas tienen ahí su única copia. ``run_results``
    conserva los eventos observados y los demás campos de
    ``ScientificRunResult`` que el manifiesto no serializa. Un resultado
    parcial no tiene que cubrir el dataset esperado. No se exige
    convergencia, backlog cero ni motor COMPLETED.

    Cada pareja Individual/Batch puede compartir dataset. Cargas distintas
    pueden materializar datasets distintos.

    El manifiesto ya calcula el hash de configuración y la huella del
    dataset esperado de cada corrida. Esa huella puede generar en memoria
    los eventos esperados cuando aún no están en la caché, una vez por
    workload. El coste adicional son las dos huellas del plan de contacto
    y la serialización del documento, incluidos los eventos observados.
    Copiar la capacidad no genera eventos ni abre el archivo del plan.
    """
    if not isinstance(resolved, ResolvedE2Campaign):
        raise TypeError("resolved debe ser un ResolvedE2Campaign")
    observed, manifest = _observed_campaign_manifest(
        resolved.campaign,
        result,
        provenance,
    )
    document = _configured_bank_document(
        artifact_type=E2_CONFIGURABLE_BANK_RESULT,
        configuration=resolved.bank_document.model_dump(mode="json"),
        contact_plan_definition=resolved.contact_plan_definition,
        provenance=observed,
        manifest=manifest,
        result=result,
        reference_capacity=_nominal_mars_to_relay_capacity(
            resolved.reference_capacity
        ),
    )
    return _json_object(document)


def write_e1_bank_result(path: Path, document: dict[str, Any]) -> Path:
    """Publica un documento E1 nuevo sin reemplazar ninguna entrada existente.

    Acepta solamente ``e1_configurable_bank_result``.
    """
    return _publish_bank_result(path, document, E1_CONFIGURABLE_BANK_RESULT)


def write_e2_bank_result(path: Path, document: dict[str, Any]) -> Path:
    """Publica un documento E2 ya construido sin reemplazar ninguna entrada existente.

    Acepta solamente ``e2_configurable_bank_result``. Un resultado E1 se
    rechaza antes de crear archivos. No vuelve a validar campañas, capacidad,
    datasets ni métricas.
    """
    return _publish_bank_result(path, document, E2_CONFIGURABLE_BANK_RESULT)


def _publish_bank_result(
    path: Path,
    document: dict[str, Any],
    artifact_type: str,
) -> Path:
    """Escribe y cierra un temporal, luego lo publica con ``os.link``.

    La serialización canónica y las validaciones ocurren antes de crear el
    temporal, en el mismo directorio del destino. El enlace duro publica el
    inode completo con creación exclusiva: si ``path`` ya existe, ``os.link``
    falla y el destino queda intacto. El temporal se elimina al terminar,
    también si el enlace falla. No hay fallback para filesystems sin enlaces
    duros, ni se crean directorios padre. No promete durabilidad ante un
    corte de energía ni limpieza si el proceso termina de golpe.
    """
    if not isinstance(path, Path):
        raise TypeError("path debe ser un Path")
    if not isinstance(document, dict):
        raise TypeError("document debe ser un dict")

    text = canonical_json_text(document)
    if document.get("artifact_type") != artifact_type:
        bank = "E1" if artifact_type == E1_CONFIGURABLE_BANK_RESULT else "E2"
        raise ValueError(
            f"artifact_type no corresponde a un resultado del banco {bank}"
        )
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


def _observed_campaign_manifest(
    campaign: CampaignSpec,
    result: CampaignResult,
    provenance: SoftwareProvenance | None,
) -> tuple[SoftwareProvenance, dict[str, Any]]:
    """Usa una sola procedencia y exige que el resultado sea el de esta campaña.

    ``campaign_manifest`` comprueba identidad, cantidad, índices, rótulos y
    orden. Después, cada corrida terminada se compara con los identificadores
    y parámetros de su propia especificación. La misma longitud no dice que
    una corrida corresponda a la otra.
    """
    if not isinstance(result, CampaignResult):
        raise TypeError("result debe ser un CampaignResult")
    if provenance is not None and not isinstance(provenance, SoftwareProvenance):
        raise TypeError("provenance debe ser una SoftwareProvenance")

    observed = current_provenance() if provenance is None else provenance
    manifest = campaign_manifest(campaign, result, provenance=observed).to_dict()
    _require_completed_results_match_specs(campaign, result)
    return observed, manifest


def _configured_bank_document(
    *,
    artifact_type: str,
    configuration: dict[str, Any],
    contact_plan_definition: ContactPlanDefinition,
    provenance: SoftwareProvenance,
    manifest: dict[str, Any],
    result: CampaignResult,
    reference_capacity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Arma el documento común. La capacidad E2 entra solo cuando ya fue copiada."""
    document: dict[str, Any] = {
        "bank_result_schema_version": BANK_RESULT_SCHEMA_VERSION,
        "artifact_type": artifact_type,
        "configuration": configuration,
        "contact_plan_definition": contact_plan_definition.model_dump(mode="json"),
        "contact_plan_fingerprint": contact_plan_fingerprint(contact_plan_definition),
        "contact_plan_definition_fingerprint": contact_plan_definition_fingerprint(
            contact_plan_definition
        ),
    }
    if reference_capacity is not None:
        document["reference_capacity"] = reference_capacity
    document["software_provenance"] = {
        "software_version": provenance.software_version,
        "source_revision": provenance.source_revision,
        "source_state": provenance.source_state,
    }
    document["campaign_manifest"] = manifest
    document["run_results"] = [
        {"result": None if run.result is None else _result_remainder(run.result)}
        for run in result.runs
    ]
    return document


def _nominal_mars_to_relay_capacity(capacity: ReferenceCapacity) -> dict[str, Any]:
    """Copia la capacidad nominal Marte → relé ya resuelta.

    No vuelve a sumar contactos ni lee un formateador. El valor es el
    efectivo de la resolución: bytes serializables sobre el intervalo, no
    una constante ni la utilización realizada.
    """
    if not isinstance(capacity, ReferenceCapacity):
        raise TypeError("reference_capacity debe ser una ReferenceCapacity")
    return {
        "scenario_id": capacity.scenario_id,
        "interval_start_sim": capacity.interval_start_sim,
        "interval_end_sim": capacity.interval_end_sim,
        "serialized_capacity_bytes": capacity.serialized_capacity_bytes,
        "contact_count": capacity.contact_count,
    }


def _json_object(document: dict[str, Any]) -> dict[str, Any]:
    serialized = jsonable(document)
    if not isinstance(serialized, dict):
        raise RuntimeError("el resultado del banco debe ser un objeto JSON")
    return serialized


def _require_completed_results_match_specs(
    campaign: CampaignSpec,
    result: CampaignResult,
) -> None:
    """Verifica los vínculos que existen en una corrida terminada.

    Los vínculos de campaña, cantidad, índice y rótulo ya fueron verificados por
    ``campaign_manifest``. Una corrida fallida no contiene un resultado del que
    puedan contrastarse identidades; queda vinculada por esos campos. La
    comparación es contra la especificación de esa posición: no exige el
    mismo dataset entre cargas ni un motor COMPLETED.
    """
    for planned, finished in zip(campaign.runs, result.runs, strict=True):
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
