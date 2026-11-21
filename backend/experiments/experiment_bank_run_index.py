"""Propuesta aislada RUN-02-01: índice documental V2, sin CLI ni simulación.

Los hashes de inputs deben ser capturados por el lector de esos mismos bytes.
Este módulo no reabre inputs ni certifica su asociación con un objeto resuelto.
Los resultados científicos y sus manifiestos siguen siendo la fuente de verdad.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Any, BinaryIO, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator,
)

from core.simulation.engine import SimulationStatus
from experiments.canonical import canonical_json_text, jsonable
from experiments.contact_plan import (
    contact_plan_definition_fingerprint, contact_plan_fingerprint,
)
from experiments.experiment_bank import ExperimentBankDocument, ResolvedExperimentBank
from experiments.fingerprint import configuration_hash
from experiments.publication import write_exclusive_canonical_json
from experiments.software_provenance import SoftwareProvenance

ARTIFACT_TYPE = "experiment_bank_run_index"
SCHEMA_VERSION = 1
BLOCK_SIZE = 1024 * 1024
MAX_INDEX_BYTES = 4 * 1024 * 1024
EXPERIMENT_ORDER = ("e1", "e2", "e3", "e3_sensitivity")
_CHECKPOINT = re.compile(r"bank-index-([0-9]{4})\.json\Z")
_ENGINE_STATUSES = {item.value for item in SimulationStatus}


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("texto vacío")
    return value


def _uuid5(value: str) -> str:
    parsed = UUID(value)
    if parsed.version != 5 or str(parsed) != value:
        raise ValueError("se requiere UUID5 canónico")
    return value


Text = Annotated[str, AfterValidator(_nonblank)]
Hash = Annotated[str, StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
Identity = Annotated[str, AfterValidator(_uuid5)]
Position = Annotated[int, Field(ge=0)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class _Source(_Model):
    path: Text
    sha256: Hash


class _ContactPlan(_Model):
    source_path: Text
    sha256: Hash
    contact_plan_fingerprint: Hash
    contact_plan_definition_fingerprint: Hash


class _Provenance(_Model):
    software_version: Text
    source_revision: str | None
    source_state: Literal["clean", "dirty", "unknown"]

    @model_validator(mode="after")
    def native_contract(self) -> Self:
        SoftwareProvenance(**self.model_dump())
        return self


class _Snapshot(_Model):
    kind: Literal["checkpoint", "final"]
    sequence: Position


class _Error(_Model):
    type: Text
    message: str  # Una excepción puede tener str(exc) vacío.


class _Terminal(_Model):
    completed: bool  # Resultado presente; NO es estado del motor.
    engine_status: str | None
    error_type: Text | None
    error_message: str | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.completed:
            if self.engine_status not in _ENGINE_STATUSES:
                raise ValueError("resultado presente requiere estado nativo del motor")
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("resultado presente no lleva error")
        elif (self.engine_status is not None or self.error_type is None
              or self.error_message is None):
            raise ValueError("corrida sin resultado requiere error y motor nulo")
        return self


class _Run(_Model):
    index: Position
    label: Text
    dataset_identity: Identity
    experiment_identity: Identity
    execution_identity: Identity
    configuration_hash: Hash
    dataset_fingerprint: Hash | None
    terminal: _Terminal | None


class _Artifact(_Model):
    relative_path: Text
    size_bytes: Position | None
    sha256: Hash | None


class _Entry(_Model):
    index: Position
    experiment_id: Literal["e1", "e2", "e3", "e3_sensitivity"]
    campaign_id: Text
    campaign_identity: Identity
    execution_status: Literal["pending", "returned", "failed"]
    execution_error: _Error | None
    campaign_status: Literal["COMPLETED", "COMPLETED_WITH_FAILURES"] | None
    publication_status: Literal["pending", "published", "failed", "unverified"]
    publication_error: str | None
    integrity_error: Text | None
    artifact: _Artifact | None
    runs: Annotated[list[_Run], Field(min_length=1)]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if [run.index for run in self.runs] != list(range(len(self.runs))):
            raise ValueError("índices de corridas no contiguos")
        if len({run.label for run in self.runs}) != len(self.runs):
            raise ValueError("etiquetas duplicadas")
        if self.execution_status == "returned":
            if self.execution_error is not None or any(r.terminal is None for r in self.runs):
                raise ValueError("retorno requiere todos los terminales y ningún error de llamada")
            expected = ("COMPLETED" if all(r.terminal.completed for r in self.runs)
                        else "COMPLETED_WITH_FAILURES")
            if self.campaign_status != expected or self.publication_status == "pending":
                raise ValueError("estado de campaña/publicación incompatible con retorno observado")
        else:
            if self.campaign_status is not None or any(
                r.terminal is not None or r.dataset_fingerprint is not None for r in self.runs
            ):
                raise ValueError("llamada sin retorno no tiene terminales ni fingerprints observados")
            if (self.execution_error is not None) != (self.execution_status == "failed"):
                raise ValueError("error de llamada incompatible")
            if self.publication_status != "pending":
                raise ValueError("sin retorno no hay publicación atribuible")
        if self.publication_status in {"published", "unverified"}:
            if self.artifact is None or self.publication_error is not None:
                raise ValueError("publicación confirmada requiere artefacto y ningún error de escritura")
            if self.artifact.relative_path != f"{self.experiment_id}.json":
                raise ValueError("ruta de artefacto insegura o ajena a su familia")
            if any(r.dataset_fingerprint is None for r in self.runs):
                raise ValueError("documento publicado requiere fingerprints proyectados")
            complete = self.artifact.sha256 is not None and self.artifact.size_bytes is not None
            if self.publication_status == "published":
                if not complete or self.integrity_error is not None:
                    raise ValueError("published requiere tamaño y SHA completos sin error")
            elif complete or self.integrity_error is None:
                raise ValueError("unverified requiere metadatos incompletos y error de integridad")
        else:
            if self.artifact is not None or self.integrity_error is not None:
                raise ValueError("sin publicación confirmada no hay artefacto atribuido")
            if (self.publication_error is not None) != (self.publication_status == "failed"):
                raise ValueError("error de publicación incompatible")
        return self


def _expected_labels(configuration: ExperimentBankDocument, family: str) -> list[str]:
    """Solo orden documental vigente; no resolver specs ni generar datasets."""
    selected = getattr(configuration.experiments, family)
    if family == "e1":
        return ["individual", *(f"fixed_batch_{n}" for n in selected.batch_sizes)]
    if family == "e2":
        return [f"load_{i}_{strategy}" for i in range(len(selected.offered_load_fractions))
                for strategy in ("individual", "fixed_batch")]
    if family == "e3":
        return ["A", "B", "C", "D"]
    return [f"{n}-{policy}" for n in selected.loss_sequence_numbers
            for policy in ("sender-driven", "receiver-driven")]


class BankRunIndex(_Model):
    """Esquema estricto. No resuelve ContactPlan ni verifica ciencia."""

    artifact_type: Literal["experiment_bank_run_index"]
    bank_index_schema_version: Annotated[int, Field(ge=1, le=1)]
    snapshot: _Snapshot
    configuration_source: _Source
    configuration: ExperimentBankDocument
    contact_plan: _ContactPlan
    software_provenance: _Provenance
    entries: Annotated[list[_Entry], Field(min_length=1, max_length=4)]

    @model_validator(mode="after")
    def ordered(self) -> Self:
        selected = [family for family in EXPERIMENT_ORDER
                    if getattr(self.configuration.experiments, family) is not None]
        if [entry.experiment_id for entry in self.entries] != selected:
            raise ValueError("selección u orden de experimentos inconsistente")
        for i, entry in enumerate(self.entries):
            if entry.index != i or [r.label for r in entry.runs] != _expected_labels(
                self.configuration, entry.experiment_id
            ):
                raise ValueError("orden/cardinalidad de entradas o tratamientos inconsistente")
        observed = sum(e.execution_status != "pending" for e in self.entries)
        if any(e.execution_status == "pending" for e in self.entries[:observed]):
            raise ValueError("desenlaces deben formar un prefijo")
        expected = observed if self.snapshot.kind == "checkpoint" else len(self.entries) + 1
        if self.snapshot.sequence != expected:
            raise ValueError("secuencia inconsistente")
        if self.snapshot.kind == "final" and observed != len(self.entries):
            raise ValueError("final requiere desenlace de todas las entradas")
        return self


def validate_bank_run_index(document: dict[str, Any]) -> dict[str, Any]:
    """Valida y devuelve copia JSON independiente, sin E/S ni eventos."""
    return BankRunIndex.model_validate(document).model_dump(mode="json")


def source_from_bytes(path: str, content: bytes) -> dict[str, str]:
    """Hash de bytes suministrados; el llamador garantiza que fueron consumidos.

    No demuestra que un archivo actualmente en path sea el usado por el loader.
    """
    return _Source(path=path, sha256=hashlib.sha256(content).hexdigest()).model_dump()


def build_initial_index(
    bank: ResolvedExperimentBank, *, configuration_source: dict[str, Any],
    contact_plan_source: dict[str, Any], provenance: SoftwareProvenance,
) -> dict[str, Any]:
    """Proyecta specs ya resueltas; no calcula fingerprints de dataset."""
    if not isinstance(bank, ResolvedExperimentBank) or not bank.entries:
        raise ValueError("se requiere banco V2 resuelto no vacío")
    source = _Source.model_validate(contact_plan_source)
    plan = bank.entries[0][1].contact_plan_definition
    entries = []
    for i, (family, resolved) in enumerate(bank.entries):
        if resolved.bank_document != bank.document or resolved.contact_plan_definition != plan:
            raise ValueError("contexto resuelto no comparte configuración/ContactPlan")
        campaign = resolved.campaign
        entries.append({
            "index": i, "experiment_id": family, "campaign_id": campaign.campaign_id,
            "campaign_identity": campaign.campaign_identity,
            "execution_status": "pending", "execution_error": None,
            "campaign_status": None, "publication_status": "pending",
            "publication_error": None, "integrity_error": None, "artifact": None,
            "runs": [{
                "index": j, "label": run.label,
                "dataset_identity": run.spec.dataset_identity,
                "experiment_identity": run.spec.experiment_identity,
                "execution_identity": run.spec.execution_identity,
                "configuration_hash": configuration_hash(run.spec),
                "dataset_fingerprint": None, "terminal": None,
            } for j, run in enumerate(campaign.runs)],
        })
    return validate_bank_run_index({
        "artifact_type": ARTIFACT_TYPE, "bank_index_schema_version": SCHEMA_VERSION,
        "snapshot": {"kind": "checkpoint", "sequence": 0},
        "configuration_source": configuration_source,
        "configuration": bank.document.model_dump(mode="json"),
        "contact_plan": {
            "source_path": source.path, "sha256": source.sha256,
            "contact_plan_fingerprint": contact_plan_fingerprint(plan),
            "contact_plan_definition_fingerprint": contact_plan_definition_fingerprint(plan),
        },
        "software_provenance": {
            "software_version": provenance.software_version,
            "source_revision": provenance.source_revision, "source_state": provenance.source_state,
        },
        "entries": entries,
    })


def _planned(entry: dict[str, Any]) -> dict[str, Any]:
    return {**{k: entry[k] for k in ("index", "experiment_id", "campaign_id", "campaign_identity")},
            "runs": [{k: v for k, v in r.items() if k not in {"terminal", "dataset_fingerprint"}}
                     for r in entry["runs"]]}


def validate_transition(previous: dict[str, Any], following: dict[str, Any]) -> None:
    """Solo siguiente desenlace o cierre final; nada de reanudar/revisar historia."""
    before, after = validate_bank_run_index(previous), validate_bank_run_index(following)
    if before["snapshot"]["kind"] != "checkpoint":
        raise ValueError("no se puede avanzar un final")
    if any(before[k] != after[k] for k in before if k not in {"snapshot", "entries"}):
        raise ValueError("cambió el contexto de ejecución")
    position = before["snapshot"]["sequence"]
    if after["snapshot"]["sequence"] != position + 1:
        raise ValueError("transición debe incrementar secuencia en uno")
    if after["snapshot"]["kind"] == "final":
        if before["entries"] != after["entries"]:
            raise ValueError("cierre final no modifica entradas")
    else:
        for i, (left, right) in enumerate(zip(before["entries"], after["entries"], strict=True)):
            if _planned(left) != _planned(right) or (i != position and left != right):
                raise ValueError("transición cambia planificación o historia")


def advance_index(previous: dict[str, Any], observed_entry: dict[str, Any]) -> dict[str, Any]:
    following = validate_bank_run_index(previous)
    position = following["snapshot"]["sequence"]
    if position >= len(following["entries"]):
        raise ValueError("no hay campaña pendiente")
    following["entries"][position] = deepcopy(observed_entry)
    following["snapshot"] = {"kind": "checkpoint", "sequence": position + 1}
    validate_transition(previous, following)
    return validate_bank_run_index(following)


def finalize_index(previous: dict[str, Any]) -> dict[str, Any]:
    following = validate_bank_run_index(previous)
    following["snapshot"] = {"kind": "final", "sequence": len(following["entries"]) + 1}
    validate_transition(previous, following)
    return validate_bank_run_index(following)


def _index_filename(document: dict[str, Any]) -> str:
    snapshot = document["snapshot"]
    return ("bank-index.json" if snapshot["kind"] == "final"
            else f"bank-index-{snapshot['sequence']:04d}.json")


def write_bank_run_index(
    directory: Path, document: dict[str, Any], *, previous: dict[str, Any] | None = None,
) -> Path:
    """Publica exclusivamente en un directorio existente; no crea ni reemplaza."""
    validated = validate_bank_run_index(document)
    if previous is None:
        if validated["snapshot"] != {"kind": "checkpoint", "sequence": 0}:
            raise ValueError("instantánea no inicial requiere previous")
    else:
        validate_transition(previous, validated)
    if len(canonical_json_text(validated).encode("utf-8")) > MAX_INDEX_BYTES:
        raise ValueError("índice excede límite de 4 MiB")
    return write_exclusive_canonical_json(directory / _index_filename(validated), jsonable(validated))


def _hash_stream(stream: BinaryIO) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    while chunk := stream.read(BLOCK_SIZE):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _signature(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _safe_file(directory: Path, name: str) -> Path:
    """Nombres planos únicamente; rechaza también symlinks internos/reparse."""
    if not name or name in {".", ".."} or any(c in name for c in "/\\:"):
        raise ValueError("ruta insegura")
    path = directory / name
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
            or not stat.S_ISREG(info.st_mode)):
        raise ValueError("archivo no regular o enlace/reparse point")
    if path.resolve().parent != directory.resolve():
        raise ValueError("archivo fuera del directorio")
    return path


def artifact_metadata(directory: Path, experiment_id: str) -> dict[str, Any]:
    """Hash estable de un resultado YA publicado, sin parsear su contenido."""
    if experiment_id not in EXPERIMENT_ORDER:
        raise ValueError("experimento desconocido")
    name = f"{experiment_id}.json"
    path = _safe_file(directory, name)
    initial = path.lstat()
    flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
             | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(os.open(path, flags), "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or _signature(initial) != _signature(before):
            raise ValueError("archivo cambió antes de abrir")
        digest, size = _hash_stream(stream)
        after = os.fstat(stream.fileno())
    current = _safe_file(directory, name).stat()
    if (_signature(before) != _signature(after) or _signature(after) != _signature(current)
            or size != after.st_size):
        raise ValueError("archivo cambió durante la lectura")
    return {"relative_path": name, "size_bytes": size, "sha256": digest}


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"clave JSON duplicada: {key}")
        document[key] = value
    return document


def _reject_constant(value: str) -> None:
    raise ValueError(f"número JSON no finito: {value}")


def _read_index(path: Path) -> dict[str, Any]:
    safe = _safe_file(path.parent, path.name)
    with safe.open("rb") as stream:
        raw = stream.read(MAX_INDEX_BYTES + 1)
    if len(raw) > MAX_INDEX_BYTES:
        raise ValueError("índice excede límite de 4 MiB")
    document = validate_bank_run_index(json.loads(
        raw, object_pairs_hook=_unique, parse_constant=_reject_constant,
    ))
    if path.name != _index_filename(document):
        raise ValueError("nombre de índice no coincide con instantánea")
    return document


def _inventory(directory: Path, registered: set[str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {
        "unregistered_artifacts": [], "temporary_files": [], "extra_files": [],
    }
    for item in sorted(directory.iterdir(), key=lambda p: p.name):
        name = item.name
        if name in registered or name == "bank-index.json" or _CHECKPOINT.fullmatch(name):
            continue
        if name in {f"{family}.json" for family in EXPERIMENT_ORDER}:
            found["unregistered_artifacts"].append(name)
        elif name.startswith(".") and name.endswith(".tmp"):
            found["temporary_files"].append(name)
        else:
            found["extra_files"].append(name)
    return found


def verify_bank_run_index(index_path: Path) -> dict[str, Any]:
    """Informe documental; no lee inputs ni interpreta JSON de resultados.

    Frente a directorio, elige final o mayor checkpoint. Nunca cae a uno viejo
    si el elegido falla. Requiere un conjunto sin escritores concurrentes;
    los checks stat no son una defensa absoluta contra sustitución maliciosa.
    """
    report: dict[str, Any] = {
        "index_path": str(index_path), "document_integrity": "invalid",
        "snapshot_kind": None, "set_publication": "unclosed", "execution": [],
        "scientific_semantics": "not_checked", "files": [], "unregistered_artifacts": [],
        "temporary_files": [], "extra_files": [], "diagnostics": [],
    }
    try:
        path = Path(index_path)
        if path.is_dir():
            report.update(_inventory(path, set()))
            names = [item.name for item in path.iterdir()]
            if "bank-index.json" in names:
                path = path / "bank-index.json"
            else:
                checkpoints = sorted(name for name in names if _CHECKPOINT.fullmatch(name))
                if not checkpoints:
                    report["set_publication"] = "unindexed"
                    report["diagnostics"].append("no hay índice")
                    return report
                path = path / checkpoints[-1]
        report["index_path"] = str(path)
        report.update(_inventory(path.parent, set()))
        document = _read_index(path)
        report["snapshot_kind"] = document["snapshot"]["kind"]
        report["document_integrity"] = "valid"
        registered = set()
        for entry in document["entries"]:
            report["execution"].append({
                "experiment_id": entry["experiment_id"],
                "execution_status": entry["execution_status"],
                "execution_error": entry["execution_error"],
                "campaign_status": entry["campaign_status"],
                "publication_status": entry["publication_status"],
                "publication_error": entry["publication_error"],
                "integrity_error": entry["integrity_error"],
                "engine_statuses": [None if r["terminal"] is None else r["terminal"]["engine_status"]
                                    for r in entry["runs"]],
            })
            artifact = entry["artifact"]
            if artifact is None:
                continue
            name = artifact["relative_path"]
            registered.add(name)
            item = {"relative_path": name, "status": "invalid", "diagnostics": []}
            try:
                actual = artifact_metadata(path.parent, entry["experiment_id"])
                item["observed"] = actual
                for key in ("size_bytes", "sha256"):
                    if artifact[key] is not None and artifact[key] != actual[key]:
                        item["diagnostics"].append(f"{key} no coincide")
                if not item["diagnostics"]:
                    item["status"] = ("valid" if entry["publication_status"] == "published"
                                      else "incomplete")
            except (OSError, ValueError) as exc:
                item["diagnostics"].append(str(exc))
            report["files"].append(item)
        report.update(_inventory(path.parent, registered))
        statuses = {item["status"] for item in report["files"]}
        report["document_integrity"] = ("invalid" if "invalid" in statuses else
                                        "incomplete" if "incomplete" in statuses else "valid")
        if document["snapshot"]["kind"] == "final":
            complete = (all(e["publication_status"] == "published" for e in document["entries"])
                        and report["document_integrity"] == "valid"
                        and not report["unregistered_artifacts"])
            report["set_publication"] = "complete" if complete else "partial"
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        report["document_integrity"] = "invalid"
        report["diagnostics"].append(str(exc))
    return report
