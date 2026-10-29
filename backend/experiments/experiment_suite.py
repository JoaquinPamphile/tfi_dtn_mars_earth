"""Documento de suite y resumen pequeño de su ejecución.

La suite nombra configuraciones completas. No hereda parámetros, no
aplica plantillas y no registra plugins. Validar este documento no abre
esas configuraciones, no resuelve campañas y no ejecuta el motor.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from experiments.canonical import jsonable
from experiments.experiment_bank import ResolvedCampaign
from experiments.experiment_bank_result import write_exclusive_canonical_json

SUITE_SCHEMA_VERSION = 1
SUITE_SUMMARY_SCHEMA_VERSION = 1
SUITE_SUMMARY_ARTIFACT_TYPE = "experiment_suite_summary"
SUITE_EXPERIMENT_IDS = ("e1", "e2", "e3", "e3_sensitivity")
PUBLICATION_NOT_REQUESTED = "not_requested"
PUBLICATION_PUBLISHED = "published"
PUBLICATION_FAILED = "failed"
_PUBLICATION_STATUSES = frozenset(
    {
        PUBLICATION_NOT_REQUESTED,
        PUBLICATION_PUBLISHED,
        PUBLICATION_FAILED,
    }
)


class _SuiteModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SuiteExperimentEntry(_SuiteModel):
    """Referencia a una configuración completa. No es una campaña resuelta."""

    id: Literal["e1", "e2", "e3", "e3_sensitivity"]
    config_file: str

    @field_validator("config_file")
    @classmethod
    def config_file_must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("config_file no debe estar vacío")
        return value


class ExperimentSuiteDocument(_SuiteModel):
    """Lista ordenada de configuraciones. No admite una suite adentro de otra."""

    suite_schema_version: int = Field(strict=True)
    suite_id: str
    experiments: tuple[SuiteExperimentEntry, ...]

    @field_validator("suite_schema_version", mode="before")
    @classmethod
    def version_must_not_be_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("suite_schema_version no admite booleanos")
        return value

    @field_validator("suite_id")
    @classmethod
    def suite_id_must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("suite_id no debe estar vacío")
        return value

    @field_validator("experiments", mode="before")
    @classmethod
    def experiments_are_an_ordered_list(cls, value: Any) -> Any:
        if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
            raise ValueError("experiments debe ser una lista ordenada")
        if len(value) == 0:
            raise ValueError("experiments no debe estar vacío")
        return value

    @model_validator(mode="after")
    def supported_version_and_unique_ids(self) -> Self:
        if self.suite_schema_version != SUITE_SCHEMA_VERSION:
            raise ValueError(
                "suite_schema_version no soportada: "
                f"se requiere {SUITE_SCHEMA_VERSION}"
            )
        seen: list[str] = []
        for entry in self.experiments:
            if entry.id in seen:
                raise ValueError(f"id de suite repetido: {entry.id}")
            seen.append(entry.id)
        return self


def suite_from_text(text: str, source: Any) -> ExperimentSuiteDocument:
    """Valida un texto ya leído. No abre el archivo ni las configuraciones."""
    try:
        return ExperimentSuiteDocument.model_validate_json(text)
    except ValidationError as error:
        raise ValueError(f"no se pudo validar la suite: {source}\n{error}") from error


@dataclass(frozen=True, slots=True)
class ResolvedSuiteEntry:
    """Entrada ya resuelta. ``config_file`` es el texto declarado, no la ruta abierta."""

    experiment_id: str
    config_file: str
    resolved: ResolvedCampaign


@dataclass(frozen=True, slots=True)
class ResolvedSuite:
    """Suite validada y campañas resueltas, en el orden declarado. Sin resultados."""

    document: ExperimentSuiteDocument
    entries: tuple[ResolvedSuiteEntry, ...]


@dataclass(frozen=True, slots=True)
class SuiteSummaryEntry:
    """Hechos de una campaña ya intentada. No guarda métricas ni eventos."""

    experiment_id: str
    config_file: str
    campaign_id: str
    campaign_identity: str
    campaign_status: str
    run_count: int
    completed_run_count: int
    failed_run_count: int
    all_runs_engine_completed: bool
    publication_status: str
    result_file: str | None
    publication_error: str | None

    def __post_init__(self) -> None:
        if self.experiment_id not in SUITE_EXPERIMENT_IDS:
            raise ValueError(f"experimento de suite no admitido: {self.experiment_id}")
        if self.publication_status not in _PUBLICATION_STATUSES:
            raise ValueError(
                f"estado de publicación no admitido: {self.publication_status}"
            )
        if self.publication_status == PUBLICATION_PUBLISHED:
            if self.result_file != f"{self.experiment_id}.json":
                raise ValueError("el archivo publicado no corresponde al experimento")
            if self.publication_error is not None:
                raise ValueError("una publicación terminada no lleva error")
        elif self.result_file is not None:
            raise ValueError("solo una publicación terminada referencia un archivo")
        if self.publication_status != PUBLICATION_FAILED and self.publication_error is not None:
            raise ValueError("el error de guardado solo acompaña a una publicación fallida")
        if self.publication_status == PUBLICATION_FAILED and not self.publication_error:
            raise ValueError("una publicación fallida requiere el error de guardado")


def build_suite_summary(
    document: ExperimentSuiteDocument,
    entries: tuple[SuiteSummaryEntry, ...] | list[SuiteSummaryEntry],
) -> dict[str, Any]:
    """Arma el resumen pequeño. No ejecuta, no lee archivos y no copia eventos."""
    if not isinstance(document, ExperimentSuiteDocument):
        raise TypeError("document debe ser un ExperimentSuiteDocument")
    ordered = tuple(entries)
    declared = tuple(item.id for item in document.experiments)
    observed = tuple(entry.experiment_id for entry in ordered)
    if observed != declared:
        raise ValueError("el resumen no sigue el orden declarado de la suite")
    for entry, item in zip(ordered, document.experiments, strict=True):
        if entry.config_file != item.config_file:
            raise ValueError(
                "el resumen no conserva el config_file declarado: "
                f"{entry.experiment_id}"
            )
    summary = {
        "suite_summary_schema_version": SUITE_SUMMARY_SCHEMA_VERSION,
        "artifact_type": SUITE_SUMMARY_ARTIFACT_TYPE,
        "suite_id": document.suite_id,
        "suite_document": document.model_dump(mode="json"),
        "entries": [_summary_entry(entry) for entry in ordered],
    }
    serialized = jsonable(summary)
    if not isinstance(serialized, dict):
        raise RuntimeError("el resumen de suite debe ser un objeto JSON")
    return serialized


def write_suite_summary(path: Path, document: dict[str, Any]) -> Path:
    """Publica el resumen con el mismo enlace exclusivo de los resultados del banco.

    Acepta solamente ``experiment_suite_summary``. Un resultado E1, E2, E3
    o de sensibilidad se rechaza antes de crear el temporal. No cambia los
    marcadores de esos escritores.
    """
    if not isinstance(path, Path):
        raise TypeError("path debe ser un Path")
    if not isinstance(document, dict):
        raise TypeError("document debe ser un dict")
    serialized = jsonable(document)
    if document.get("artifact_type") != SUITE_SUMMARY_ARTIFACT_TYPE:
        raise ValueError("artifact_type no corresponde a un resumen de suite")
    version = document.get("suite_summary_schema_version")
    if isinstance(version, bool) or version != SUITE_SUMMARY_SCHEMA_VERSION:
        raise ValueError(
            "suite_summary_schema_version no soportada: "
            f"se requiere {SUITE_SUMMARY_SCHEMA_VERSION}"
        )
    return write_exclusive_canonical_json(path, serialized)


def _summary_entry(entry: SuiteSummaryEntry) -> dict[str, Any]:
    return {
        "id": entry.experiment_id,
        "config_file": entry.config_file,
        "campaign_id": entry.campaign_id,
        "campaign_identity": entry.campaign_identity,
        "campaign_status": entry.campaign_status,
        "run_count": entry.run_count,
        "completed_run_count": entry.completed_run_count,
        "failed_run_count": entry.failed_run_count,
        "all_runs_engine_completed": entry.all_runs_engine_completed,
        "publication_status": entry.publication_status,
        "result_file": entry.result_file,
        "publication_error": entry.publication_error,
    }
