from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from experiments.campaign import (
    CAMPAIGN_COMPLETED,
    CAMPAIGN_COMPLETED_WITH_FAILURES,
    CampaignSpec,
    _expected_result_spec_values,
    present_result_spec_differences,
)
from experiments.canonical import jsonable
from experiments.execute import execute_scientific_run
from experiments.publication import write_exclusive_canonical_json
from experiments.fingerprint import (
    dataset_event_count,
    dataset_fingerprint,
    dataset_fingerprint_from_events,
)
from experiments.manifest import scientific_run_manifest
from experiments.result import GeneratedTelemetry, ScientificRunResult
from experiments.software_provenance import SoftwareProvenance, current_provenance
from experiments.spec import ScientificRunSpec

CAMPAIGN_RUN_SET_FORMAT = "campaign_run_set"
CAMPAIGN_RUN_SET_VERSION = 1
CAMPAIGN_RUN_RESULT_ARTIFACT = "campaign_run_result"
CAMPAIGN_RUN_SET_INDEX_ARTIFACT = "campaign_run_set_index"
INDEX_FILENAME = "campaign-run-set-index.json"
RUNS_SUBDIR = "runs"

_LABEL_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class PersistedCampaignRunRef:
    """Referencia pequeña a una corrida ya publicada. Sin eventos ni payloads."""

    index: int
    label: str
    relative_path: str
    sha256: str
    completed: bool
    error_type: str | None
    error_message: str | None
    dataset_identity: str | None
    experiment_identity: str | None
    execution_identity: str | None


@dataclass(frozen=True, slots=True)
class PersistedCampaignResult:
    """Salida de ``execute_campaign_persisted``.

    ``index_path`` es ``None`` si la campaña no publicó índice final de éxito
    (fallo de corrida, validación o publicación incompleta). Los archivos de
    corrida ya escritos se conservan.
    """

    campaign_id: str
    description: str
    campaign_identity: str
    directory: Path
    runs: tuple[PersistedCampaignRunRef, ...]
    index_path: Path | None
    status: str
    format_name: str = CAMPAIGN_RUN_SET_FORMAT
    format_version: int = CAMPAIGN_RUN_SET_VERSION

    @property
    def run_count(self) -> int:
        return len(self.runs)

    @property
    def completed_count(self) -> int:
        return sum(1 for run in self.runs if run.completed)

    @property
    def failed_count(self) -> int:
        return self.run_count - self.completed_count

    @property
    def index_published(self) -> bool:
        return self.index_path is not None


def execute_campaign_persisted(
    spec: CampaignSpec,
    directory: Path,
    *,
    provenance: SoftwareProvenance | None = None,
    after_run_released=None,
) -> PersistedCampaignResult:
    """Ejecuta cada corrida, publica su resultado y libera objetos grandes.

    Reutiliza ``execute_scientific_run``. No acumula ``ScientificRunResult``
    de corridas anteriores. El índice final solo se publica si todas las
    corridas terminaron sin error de ejecución y pasaron la validación de
    correspondencia con su spec.

    ``after_run_released``, si se pasa, se invoca con el índice de corrida
    después de eliminar las referencias locales al resultado y al documento.
    Existe para comprobaciones de retención; no forma parte del artefacto.
    """
    if not isinstance(spec, CampaignSpec):
        raise TypeError("spec debe ser un CampaignSpec")
    if not isinstance(directory, Path):
        raise TypeError("directory debe ser un Path")
    if provenance is not None and not isinstance(provenance, SoftwareProvenance):
        raise TypeError("provenance debe ser una SoftwareProvenance")
    if after_run_released is not None and not callable(after_run_released):
        raise TypeError("after_run_released debe ser callable o None")

    directory.mkdir(parents=True, exist_ok=True)
    runs_dir = directory / RUNS_SUBDIR
    runs_dir.mkdir(parents=True, exist_ok=True)

    observed = current_provenance() if provenance is None else provenance
    refs: list[PersistedCampaignRunRef] = []
    hard_failure: str | None = None

    for index, run in enumerate(spec.runs):
        if hard_failure is not None:
            break
        relative_path = f"{RUNS_SUBDIR}/{_run_filename(index, run.label)}"
        target = directory / relative_path
        scientific: ScientificRunResult | None = None
        error_type: str | None = None
        error_message: str | None = None
        identity_dataset: str | None = None
        identity_experiment: str | None = None
        identity_execution: str | None = None
        try:
            scientific = execute_scientific_run(run.spec)
        except Exception as exc:
            error_type = type(exc).__name__
            error_message = str(exc)
        else:
            differences = present_result_spec_differences(scientific, run.spec)
            if differences:
                hard_failure = (
                    "el resultado de la corrida no coincide con su especificación: "
                    f"label={run.label}, campo={differences[0][0]}"
                )
                error_type = "ValidationError"
                error_message = hard_failure
                scientific = None
            else:
                identity_dataset = scientific.dataset_identity
                identity_experiment = scientific.experiment_identity
                identity_execution = scientific.execution_identity

        document = _build_run_document(
            campaign=spec,
            index=index,
            label=run.label,
            planned=run.spec,
            result=scientific,
            error_type=error_type,
            error_message=error_message,
            provenance=observed,
        )
        completed = scientific is not None
        _publish_run_document(target, document)
        digest = _sha256_file(target)
        refs.append(
            PersistedCampaignRunRef(
                index=index,
                label=run.label,
                relative_path=relative_path.replace("\\", "/"),
                sha256=digest,
                completed=completed,
                error_type=error_type,
                error_message=error_message,
                dataset_identity=identity_dataset,
                experiment_identity=identity_experiment,
                execution_identity=identity_execution,
            )
        )
        # Liberar referencias a objetos grandes antes de la siguiente corrida.
        del scientific
        del document
        if after_run_released is not None:
            after_run_released(index)

    runs = tuple(refs)
    failed = sum(1 for item in runs if not item.completed)
    if hard_failure is not None or failed or len(runs) != len(spec.runs):
        status = CAMPAIGN_COMPLETED_WITH_FAILURES
        return PersistedCampaignResult(
            campaign_id=spec.campaign_id,
            description=spec.description,
            campaign_identity=spec.campaign_identity,
            directory=directory,
            runs=runs,
            index_path=None,
            status=status,
        )

    index_document = _build_index_document(
        campaign=spec,
        runs=runs,
        provenance=observed,
        status=CAMPAIGN_COMPLETED,
    )
    index_path = directory / INDEX_FILENAME
    _publish_run_document(index_path, index_document)
    del index_document
    return PersistedCampaignResult(
        campaign_id=spec.campaign_id,
        description=spec.description,
        campaign_identity=spec.campaign_identity,
        directory=directory,
        runs=runs,
        index_path=index_path,
        status=CAMPAIGN_COMPLETED,
    )


def verify_campaign_run_set(
    index_path: Path,
    campaign: CampaignSpec | None = None,
) -> dict[str, Any]:
    """Verifica el índice y cada resultado en orden, sin retener todos a la vez.

    Comprueba existencia, SHA-256 del archivo, identidad/orden, presencia de
    eventos, fingerprints recalculados desde eventos y, si se aporta la
    campaña, las condiciones de comparabilidad controlada entre variantes
    (mismo dataset esperado/observado).
    """
    if not isinstance(index_path, Path):
        raise TypeError("index_path debe ser un Path")
    if campaign is not None and not isinstance(campaign, CampaignSpec):
        raise TypeError("campaign debe ser un CampaignSpec")

    inconsistencies: list[str] = []
    if not index_path.is_file():
        return {
            "ok": False,
            "comparable": False,
            "inconsistencies": [f"falta el índice: {index_path}"],
            "runs_checked": 0,
        }

    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("artifact_type") != CAMPAIGN_RUN_SET_INDEX_ARTIFACT:
        inconsistencies.append("artifact_type del índice incorrecto")
    if index.get("campaign_run_set_format") != CAMPAIGN_RUN_SET_FORMAT:
        inconsistencies.append("campaign_run_set_format incorrecto")
    if index.get("campaign_run_set_version") != CAMPAIGN_RUN_SET_VERSION:
        inconsistencies.append("campaign_run_set_version no soportada")
    if index.get("status") != CAMPAIGN_COMPLETED:
        inconsistencies.append(
            "el índice no declara campaña completa exitosa "
            f"(status={index.get('status')!r})"
        )

    directory = index_path.parent
    entries = index.get("runs")
    if not isinstance(entries, list) or not entries:
        inconsistencies.append("el índice no declara corridas")
        return {
            "ok": False,
            "comparable": False,
            "inconsistencies": inconsistencies,
            "runs_checked": 0,
        }

    if campaign is not None:
        if index.get("campaign_id") != campaign.campaign_id:
            inconsistencies.append("campaign_id del índice no coincide con la campaña")
        if index.get("campaign_identity") != campaign.campaign_identity:
            inconsistencies.append(
                "campaign_identity del índice no coincide con la campaña"
            )
        if len(entries) != len(campaign.runs):
            inconsistencies.append(
                "cantidad de corridas del índice no coincide con la campaña"
            )

    reference_observed_fingerprint: str | None = None
    reference_expected_fingerprint: str | None = None
    reference_expected_count: int | None = None
    checked = 0

    for position, entry in enumerate(entries):
        label = entry.get("label")
        if entry.get("index") != position:
            inconsistencies.append(
                f"corrida posición {position}: índice inconsistente "
                f"({entry.get('index')!r})"
            )
        relative = entry.get("relative_path")
        declared_hash = entry.get("sha256")
        if not isinstance(relative, str) or not relative:
            inconsistencies.append(f"corrida {position}: relative_path ausente")
            continue
        path = directory / relative
        if not path.is_file():
            inconsistencies.append(
                f"corrida {label!r}: archivo ausente ({relative})"
            )
            continue
        actual_hash = _sha256_file(path)
        if not isinstance(declared_hash, str) or actual_hash != declared_hash:
            inconsistencies.append(
                f"corrida {label!r}: SHA-256 del archivo no coincide "
                f"(índice={declared_hash!r}, archivo={actual_hash!r})"
            )
            continue

        document = json.loads(path.read_text(encoding="utf-8"))
        try:
            _verify_one_run_document(
                document=document,
                entry=entry,
                position=position,
                campaign=campaign,
                inconsistencies=inconsistencies,
            )
            observed_fp, expected_fp, expected_count = _observed_and_expected(
                document=document,
                campaign=campaign,
                position=position,
                inconsistencies=inconsistencies,
            )
            if position == 0:
                reference_observed_fingerprint = observed_fp
                reference_expected_fingerprint = expected_fp
                reference_expected_count = expected_count
            else:
                if (
                    observed_fp is not None
                    and reference_observed_fingerprint is not None
                    and observed_fp != reference_observed_fingerprint
                ):
                    inconsistencies.append(
                        f"tratamiento {label!r}: dataset_fingerprint observado "
                        "distinto de la referencia de la campaña"
                    )
                if (
                    expected_fp is not None
                    and reference_expected_fingerprint is not None
                    and expected_fp != reference_expected_fingerprint
                ):
                    inconsistencies.append(
                        f"tratamiento {label!r}: dataset_fingerprint esperado "
                        "distinto de la referencia de la campaña"
                    )
                if (
                    expected_count is not None
                    and reference_expected_count is not None
                    and expected_count != reference_expected_count
                ):
                    inconsistencies.append(
                        f"tratamiento {label!r}: conteo esperado del dataset "
                        "distinto de la referencia de la campaña"
                    )
            checked += 1
        finally:
            del document

    ok = not inconsistencies
    return {
        "ok": ok,
        "comparable": ok,
        "inconsistencies": inconsistencies,
        "runs_checked": checked,
        "campaign_identity": index.get("campaign_identity"),
        "format": index.get("campaign_run_set_format"),
        "version": index.get("campaign_run_set_version"),
    }


def _verify_one_run_document(
    *,
    document: dict[str, Any],
    entry: dict[str, Any],
    position: int,
    campaign: CampaignSpec | None,
    inconsistencies: list[str],
) -> None:
    if document.get("artifact_type") != CAMPAIGN_RUN_RESULT_ARTIFACT:
        inconsistencies.append(
            f"corrida índice {position}: artifact_type incorrecto"
        )
    if document.get("campaign_run_set_format") != CAMPAIGN_RUN_SET_FORMAT:
        inconsistencies.append(
            f"corrida índice {position}: formato incorrecto"
        )
    if document.get("index") != position:
        inconsistencies.append(
            f"corrida índice {position}: index del documento incorrecto"
        )
    if document.get("label") != entry.get("label"):
        inconsistencies.append(
            f"corrida índice {position}: label del documento no coincide "
            "con el índice"
        )
    if campaign is not None and position < len(campaign.runs):
        planned = campaign.runs[position]
        if document.get("label") != planned.label:
            inconsistencies.append(
                f"corrida índice {position}: label no coincide con la campaña"
            )
        if document.get("campaign_identity") != campaign.campaign_identity:
            inconsistencies.append(
                f"corrida {planned.label!r}: campaign_identity incorrecta"
            )


def _observed_and_expected(
    *,
    document: dict[str, Any],
    campaign: CampaignSpec | None,
    position: int,
    inconsistencies: list[str],
) -> tuple[str | None, str | None, int | None]:
    label = document.get("label")
    result_body = document.get("result")
    if result_body is None:
        inconsistencies.append(
            f"tratamiento {label!r}: resultado ausente en el documento"
        )
        return None, None, None

    events_raw = result_body.get("events")
    if not isinstance(events_raw, list):
        inconsistencies.append(
            f"tratamiento {label!r}: events ausentes o con tipo incorrecto"
        )
        return None, None, None
    if not events_raw:
        inconsistencies.append(f"tratamiento {label!r}: events vacíos")
        return None, None, None

    events = tuple(_event_from_dict(item) for item in events_raw)
    for event in events:
        if not isinstance(event.payload, dict):
            inconsistencies.append(
                f"tratamiento {label!r}: payload de evento ausente o inválido"
            )
            break

    observed_fingerprint = dataset_fingerprint_from_events(events)
    expected_fingerprint: str | None = None
    expected_count: int | None = None

    if campaign is not None and position < len(campaign.runs):
        planned = campaign.runs[position].spec
        expected_fingerprint = dataset_fingerprint(planned)
        expected_count = dataset_event_count(planned)
        if len(events) != expected_count:
            inconsistencies.append(
                f"tratamiento {label!r}: conteo observado del dataset "
                f"no coincide (esperado={expected_count}, observado={len(events)})"
            )
        if observed_fingerprint != expected_fingerprint:
            inconsistencies.append(
                f"tratamiento {label!r}: dataset_fingerprint observado "
                f"no coincide (esperado={expected_fingerprint}, "
                f"observado={observed_fingerprint})"
            )
        for field, expected_value, observed in _document_spec_differences(
            result_body, planned
        ):
            inconsistencies.append(
                f"tratamiento {label!r}: resultado no coincide con su spec en "
                f"{field} (esperado={expected_value!r}, observado={observed!r})"
            )
    else:
        # Sin campaña, aún se exige poder recalcular desde eventos; el
        # fingerprint declarado en el manifiesto no sustituye ese recálculo.
        declared = (
            document.get("manifest", {})
            .get("dataset_fingerprint")
        )
        if declared is not None and declared != observed_fingerprint:
            inconsistencies.append(
                f"tratamiento {label!r}: fingerprint del manifiesto no coincide "
                "con el recalculado desde events"
            )

    return observed_fingerprint, expected_fingerprint, expected_count


def _build_run_document(
    *,
    campaign: CampaignSpec,
    index: int,
    label: str,
    planned: ScientificRunSpec,
    result: ScientificRunResult | None,
    error_type: str | None,
    error_message: str | None,
    provenance: SoftwareProvenance,
) -> dict[str, Any]:
    if result is None:
        manifest = scientific_run_manifest(
            planned,
            None,
            error_type=error_type,
            error_message=error_message,
            provenance=provenance,
        )
        result_body = None
    else:
        manifest = scientific_run_manifest(planned, result, provenance=provenance)
        result_body = _result_body(result)

    return {
        "campaign_run_set_format": CAMPAIGN_RUN_SET_FORMAT,
        "campaign_run_set_version": CAMPAIGN_RUN_SET_VERSION,
        "artifact_type": CAMPAIGN_RUN_RESULT_ARTIFACT,
        "campaign_id": campaign.campaign_id,
        "campaign_identity": campaign.campaign_identity,
        "description": campaign.description,
        "index": index,
        "label": label,
        "software_provenance": {
            "software_version": provenance.software_version,
            "source_revision": provenance.source_revision,
            "source_state": provenance.source_state,
        },
        "manifest": manifest.to_dict(),
        "result": result_body,
        "format_note": (
            "Documento por corrida del conjunto campaign_run_set. "
            "No es un e1/e2/e3_configurable_bank_result monolítico."
        ),
    }


def _build_index_document(
    *,
    campaign: CampaignSpec,
    runs: tuple[PersistedCampaignRunRef, ...],
    provenance: SoftwareProvenance,
    status: str,
) -> dict[str, Any]:
    return {
        "campaign_run_set_format": CAMPAIGN_RUN_SET_FORMAT,
        "campaign_run_set_version": CAMPAIGN_RUN_SET_VERSION,
        "artifact_type": CAMPAIGN_RUN_SET_INDEX_ARTIFACT,
        "campaign_id": campaign.campaign_id,
        "campaign_identity": campaign.campaign_identity,
        "description": campaign.description,
        "status": status,
        "run_count": len(runs),
        "completed_count": sum(1 for run in runs if run.completed),
        "failed_count": sum(1 for run in runs if not run.completed),
        "software_provenance": {
            "software_version": provenance.software_version,
            "source_revision": provenance.source_revision,
            "source_state": provenance.source_state,
        },
        "expected_runs": [
            {
                "index": index,
                "label": run.label,
                "dataset_identity": run.spec.dataset_identity,
                "experiment_identity": run.spec.experiment_identity,
                "execution_identity": run.spec.execution_identity,
            }
            for index, run in enumerate(campaign.runs)
        ],
        "runs": [
            {
                "index": run.index,
                "label": run.label,
                "relative_path": run.relative_path,
                "sha256": run.sha256,
                "completed": run.completed,
                "error_type": run.error_type,
                "error_message": run.error_message,
                "dataset_identity": run.dataset_identity,
                "experiment_identity": run.experiment_identity,
                "execution_identity": run.execution_identity,
            }
            for run in runs
        ],
        "format_note": (
            "Índice de campaign_run_set. Formato distinto del JSON monolítico "
            "del banco configurable; cada corrida vive en relative_path."
        ),
    }


def _result_body(result: ScientificRunResult) -> dict[str, Any]:
    return {
        "scenario_id": result.scenario_id,
        "workload_id": result.workload_id,
        "seed": result.seed,
        "dataset_identity": result.dataset_identity,
        "experiment_identity": result.experiment_identity,
        "execution_identity": result.execution_identity,
        "strategy_type": result.strategy_type,
        "batch_size_events": result.batch_size_events,
        "stop_policy": result.stop_policy,
        "horizon_seconds": result.horizon_seconds,
        "recovery_policy": result.recovery_policy,
        "offered_load_fraction": result.offered_load_fraction,
        "simulation_time": result.simulation_time,
        "engine_status": result.engine_status,
        "events": [asdict(event) for event in result.events],
        "events_persisted_earth": result.events_persisted_earth,
        "events_confirmed_mars": result.events_confirmed_mars,
        "metrics": result.metrics.to_dict(),
        "trace_entry_count": result.trace_entry_count,
    }


def _publish_run_document(path: Path, document: dict[str, Any]) -> Path:
    """Normaliza con ``jsonable`` (tipos ricos) y publica con creación exclusiva."""
    serialized = jsonable(document)
    if not isinstance(serialized, dict):
        raise RuntimeError("el documento publicado debe ser un objeto JSON")
    return write_exclusive_canonical_json(path, serialized)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _run_filename(index: int, label: str) -> str:
    safe = _LABEL_SAFE.sub("_", label.strip()).strip("._") or "run"
    return f"{index:04d}-{safe}.json"


def _event_from_dict(item: dict[str, Any]) -> GeneratedTelemetry:
    return GeneratedTelemetry(
        event_id=str(item["event_id"]),
        source_id=str(item["source_id"]),
        sequence_number=int(item["sequence_number"]),
        generated_at_sim=float(item["generated_at_sim"]),
        event_type=str(item["event_type"]),
        payload=dict(item["payload"]),
        priority=str(item["priority"]),
        schema_version=int(item["schema_version"]),
    )


def _document_spec_differences(
    body: dict[str, Any],
    spec: ScientificRunSpec,
) -> tuple[tuple[str, Any, Any], ...]:
    """Misma contraste que ``present_result_spec_differences``, sobre el JSON."""
    expected = _expected_result_spec_values(spec)
    differences: list[tuple[str, Any, Any]] = []
    for field, expected_value in expected.items():
        observed = body.get(field)
        if observed != expected_value:
            differences.append((field, expected_value, observed))
    return tuple(differences)