"""Manifiestos inmutables de una corrida y de una campaña.

Describen cómo reproducir la ejecución y, si ya terminó, el resultado
terminal y las métricas científicas. No guardan objetos de Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.mars.node import DEFAULT_SCHEMA_VERSION

from experiments.campaign import CampaignResult, CampaignSpec
from experiments.canonical import (
    HASH_ALGORITHM,
    MANIFEST_SCHEMA_VERSION,
    jsonable,
    spec_payload,
)
from experiments.software_provenance import SoftwareProvenance, current_provenance
from experiments.fingerprint import (
    configuration_hash,
    dataset_event_count,
    dataset_fingerprint,
)
from experiments.result import ScientificRunResult
from experiments.spec import ScientificRunSpec


@dataclass(frozen=True, slots=True)
class ScientificRunManifest:
    """Cómo reproducir una corrida, y el cierre si ya existe."""

    manifest_schema_version: int
    software_version: str
    source_revision: str | None
    source_state: str
    telemetry_schema_version: int
    hash_algorithm: str
    dataset_identity: str
    experiment_identity: str
    execution_identity: str
    configuration_hash: str
    dataset_fingerprint: str
    dataset_event_count: int
    seed: int
    scenario_id: str
    horizon_seconds: float | None
    workload_id: str
    workload: dict[str, Any]
    strategy_type: str
    batch_size_events: int | None
    recovery_policy: str
    retry_policy: dict[str, Any]
    failure_plan: dict[str, Any]
    stop_policy: str
    gap_request_timeout_seconds: float | None
    trace_level: str
    specification: dict[str, Any]
    completed: bool
    engine_status: str | None
    error_type: str | None
    error_message: str | None
    metrics: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "manifest_schema_version": self.manifest_schema_version,
                "software_version": self.software_version,
                "source_revision": self.source_revision,
                "source_state": self.source_state,
                "telemetry_schema_version": self.telemetry_schema_version,
                "hash_algorithm": self.hash_algorithm,
                "dataset_identity": self.dataset_identity,
                "experiment_identity": self.experiment_identity,
                "execution_identity": self.execution_identity,
                "configuration_hash": self.configuration_hash,
                "dataset_fingerprint": self.dataset_fingerprint,
                "dataset_event_count": self.dataset_event_count,
                "seed": self.seed,
                "scenario_id": self.scenario_id,
                "horizon_seconds": self.horizon_seconds,
                "workload_id": self.workload_id,
                "workload": self.workload,
                "strategy_type": self.strategy_type,
                "batch_size_events": self.batch_size_events,
                "recovery_policy": self.recovery_policy,
                "retry_policy": self.retry_policy,
                "failure_plan": self.failure_plan,
                "stop_policy": self.stop_policy,
                "gap_request_timeout_seconds": self.gap_request_timeout_seconds,
                "trace_level": self.trace_level,
                "specification": self.specification,
                "terminal": {
                    "completed": self.completed,
                    "engine_status": self.engine_status,
                    "error_type": self.error_type,
                    "error_message": self.error_message,
                },
                "metrics": self.metrics,
            }
        )


@dataclass(frozen=True, slots=True)
class CampaignManifest:
    """Campaña ordenada. Cada corrida aparece una vez, en su índice."""

    manifest_schema_version: int
    software_version: str
    source_revision: str | None
    source_state: str
    campaign_id: str
    campaign_identity: str
    description: str
    status: str
    run_count: int
    completed_count: int
    failed_count: int
    runs: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "manifest_schema_version": self.manifest_schema_version,
                "software_version": self.software_version,
                "source_revision": self.source_revision,
                "source_state": self.source_state,
                "campaign_id": self.campaign_id,
                "campaign_identity": self.campaign_identity,
                "description": self.description,
                "status": self.status,
                "run_count": self.run_count,
                "completed_count": self.completed_count,
                "failed_count": self.failed_count,
                "runs": list(self.runs),
            }
        )


def scientific_run_manifest(
    spec: ScientificRunSpec,
    result: ScientificRunResult | None = None,
    *,
    error_type: str | None = None,
    error_message: str | None = None,
    provenance: SoftwareProvenance | None = None,
) -> ScientificRunManifest:
    """Arma el manifiesto. Sin resultado, las métricas quedan en null."""
    if not isinstance(spec, ScientificRunSpec):
        raise TypeError("spec debe ser una ScientificRunSpec")
    payload = spec_payload(spec)
    if result is not None and (error_type is not None or error_message is not None):
        raise ValueError("una corrida terminada no lleva error")
    if result is None and (error_type is None or error_message is None):
        raise ValueError("una corrida sin resultado requiere error_type y error_message")
    if result is None:
        completed = False
        metrics = None
        engine_status = None
    else:
        completed = True
        metrics = result.metrics.to_dict()
        engine_status = result.engine_status
    observed = current_provenance() if provenance is None else provenance
    return ScientificRunManifest(
        manifest_schema_version=MANIFEST_SCHEMA_VERSION,
        software_version=observed.software_version,
        source_revision=observed.source_revision,
        source_state=observed.source_state,
        telemetry_schema_version=DEFAULT_SCHEMA_VERSION,
        hash_algorithm=HASH_ALGORITHM,
        dataset_identity=spec.dataset_identity,
        experiment_identity=spec.experiment_identity,
        execution_identity=spec.execution_identity,
        configuration_hash=configuration_hash(spec),
        dataset_fingerprint=dataset_fingerprint(spec),
        dataset_event_count=dataset_event_count(spec),
        seed=spec.seed,
        scenario_id=spec.scenario.scenario_id,
        horizon_seconds=spec.horizon_seconds,
        workload_id=spec.workload.workload_id,
        workload=payload["workload"],
        strategy_type=spec.strategy_type,
        batch_size_events=spec.batch_size_events,
        recovery_policy=spec.recovery_policy.value,
        retry_policy=payload["retry_policy"],
        failure_plan=payload["failure_plan"],
        stop_policy=spec.stop_policy.value,
        gap_request_timeout_seconds=spec.gap_request_timeout_seconds,
        trace_level=spec.trace_level.value,
        specification=payload,
        completed=completed,
        engine_status=engine_status,
        error_type=error_type,
        error_message=error_message,
        metrics=metrics,
    )


def campaign_manifest(
    spec: CampaignSpec,
    result: CampaignResult,
    provenance: SoftwareProvenance | None = None,
) -> CampaignManifest:
    """Manifiesto de la campaña en el orden declarado de ``spec.runs``."""
    if spec.campaign_id != result.campaign_id:
        raise ValueError("la campaña del resultado no coincide con la especificación")
    if spec.campaign_identity != result.campaign_identity:
        raise ValueError("campaign_identity no coincide con la especificación")
    if len(spec.runs) != len(result.runs):
        raise ValueError("el resultado no tiene las corridas de la especificación")
    observed = current_provenance() if provenance is None else provenance
    entries: list[dict[str, Any]] = []
    for index, (planned, finished) in enumerate(zip(spec.runs, result.runs, strict=True)):
        if finished.index != index:
            raise ValueError("las corridas del resultado deben seguir el orden declarado")
        if finished.label != planned.label:
            raise ValueError("el rótulo del resultado no coincide con la especificación")
        if finished.completed:
            manifest = scientific_run_manifest(
                planned.spec,
                finished.result,
                provenance=observed,
            )
        else:
            manifest = scientific_run_manifest(
                planned.spec,
                None,
                error_type=finished.error_type,
                error_message=finished.error_message,
                provenance=observed,
            )
        body = manifest.to_dict()
        entries.append(
            {
                "index": index,
                "label": planned.label,
                "completed": finished.completed,
                "failed": not finished.completed,
                "configuration_hash": body["configuration_hash"],
                "dataset_fingerprint": body["dataset_fingerprint"],
                "dataset_identity": body["dataset_identity"],
                "execution_identity": body["execution_identity"],
                "manifest": body,
            }
        )
    return CampaignManifest(
        manifest_schema_version=MANIFEST_SCHEMA_VERSION,
        software_version=observed.software_version,
        source_revision=observed.source_revision,
        source_state=observed.source_state,
        campaign_id=spec.campaign_id,
        campaign_identity=spec.campaign_identity,
        description=spec.description,
        status=result.status,
        run_count=result.run_count,
        completed_count=result.completed_count,
        failed_count=result.failed_count,
        runs=tuple(entries),
    )
