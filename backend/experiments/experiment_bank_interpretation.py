"""Comparabilidad controlada de una campaña E1 configurable, en memoria.

``comparable`` significa exclusivamente que la campaña completa es apta para
una comparación descriptiva controlada de agrupación. No implica convergencia,
superioridad, equivalencia con RC1 ni validez para inferencia estadística.
Un resultado ``False`` tampoco invalida todo análisis parcial.
"""

from __future__ import annotations

from typing import Any

from core.simulation.engine import SimulationStatus

from experiments.campaign import CampaignResult
from experiments.canonical import spec_payload
from experiments.experiment_bank import ResolvedE1Campaign
from experiments.fingerprint import (
    dataset_event_count,
    dataset_fingerprint,
    dataset_fingerprint_from_events,
)
from experiments.result import ScientificRunResult
from experiments.spec import ScientificRunSpec

_TREATMENT_FIELDS = frozenset({"strategy_type", "batch_size_events"})


def assess_e1_bank_comparison(
    resolved: ResolvedE1Campaign,
    result: CampaignResult,
) -> dict[str, object]:
    """Evalúa solo la comparabilidad descriptiva controlada de agrupación."""
    if not isinstance(resolved, ResolvedE1Campaign):
        raise TypeError("resolved debe ser un ResolvedE1Campaign")
    if not isinstance(result, CampaignResult):
        raise TypeError("result debe ser un CampaignResult")

    campaign = resolved.campaign
    inconsistencies: list[str] = []
    _check_campaign_correspondence(resolved, result, inconsistencies)
    _check_controlled_factors(campaign.runs, inconsistencies)

    expected_datasets = [
        (dataset_event_count(run.spec), dataset_fingerprint(run.spec))
        for run in campaign.runs
    ]
    _check_expected_datasets(campaign.runs, expected_datasets, inconsistencies)
    _check_run_results(
        campaign.runs,
        result,
        expected_datasets,
        inconsistencies,
    )
    return {
        "comparable": not inconsistencies,
        "inconsistencies": inconsistencies,
    }


def _check_campaign_correspondence(
    resolved: ResolvedE1Campaign,
    result: CampaignResult,
    inconsistencies: list[str],
) -> None:
    campaign = resolved.campaign
    if result.campaign_id != campaign.campaign_id:
        inconsistencies.append(
            "campaña: campaign_id del resultado no coincide "
            f"(esperado={campaign.campaign_id!r}, observado={result.campaign_id!r})"
        )
    if result.campaign_identity != campaign.campaign_identity:
        inconsistencies.append(
            "campaña: campaign_identity del resultado no coincide "
            f"(esperado={campaign.campaign_identity!r}, "
            f"observado={result.campaign_identity!r})"
        )
    if len(result.runs) != len(campaign.runs):
        inconsistencies.append(
            "campaña: cantidad de corridas no coincide "
            f"(esperada={len(campaign.runs)}, observada={len(result.runs)})"
        )

    for index, planned in enumerate(campaign.runs):
        if index >= len(result.runs):
            inconsistencies.append(
                f"tratamiento {planned.label!r} (índice {index}): "
                "falta la corrida en el resultado"
            )
            continue
        finished = result.runs[index]
        if finished.index != index:
            inconsistencies.append(
                f"tratamiento {planned.label!r}: índice incorrecto "
                f"(esperado={index}, observado={finished.index})"
            )
        if finished.label != planned.label:
            inconsistencies.append(
                f"tratamiento {planned.label!r} (índice {index}): "
                f"etiqueta incorrecta en el resultado ({finished.label!r})"
            )

    for extra in result.runs[len(campaign.runs) :]:
        inconsistencies.append(
            f"campaña: sobra la corrida de índice {extra.index} "
            f"y etiqueta {extra.label!r}"
        )


def _check_controlled_factors(
    runs: tuple[Any, ...],
    inconsistencies: list[str],
) -> None:
    reference = _controlled_payload(runs[0].spec)
    for run in runs[1:]:
        candidate = _controlled_payload(run.spec)
        differing = sorted(
            key
            for key in reference.keys() | candidate.keys()
            if reference.get(key) != candidate.get(key)
        )
        if differing:
            inconsistencies.append(
                f"tratamiento {run.label!r}: factores controlados distintos "
                f"({', '.join(differing)})"
            )


def _controlled_payload(spec: ScientificRunSpec) -> dict[str, Any]:
    return {
        key: value
        for key, value in spec_payload(spec).items()
        if key not in _TREATMENT_FIELDS
    }


def _check_expected_datasets(
    runs: tuple[Any, ...],
    expected_datasets: list[tuple[int, str]],
    inconsistencies: list[str],
) -> None:
    reference_count, reference_fingerprint = expected_datasets[0]
    for run, (count, fingerprint) in zip(runs[1:], expected_datasets[1:], strict=True):
        if count != reference_count:
            inconsistencies.append(
                f"tratamiento {run.label!r}: conteo esperado del dataset distinto "
                f"(referencia={reference_count}, tratamiento={count})"
            )
        if fingerprint != reference_fingerprint:
            inconsistencies.append(
                f"tratamiento {run.label!r}: dataset_fingerprint esperado distinto "
                f"(referencia={reference_fingerprint}, tratamiento={fingerprint})"
            )


def _check_run_results(
    runs: tuple[Any, ...],
    result: CampaignResult,
    expected_datasets: list[tuple[int, str]],
    inconsistencies: list[str],
) -> None:
    for index, (planned, (expected_count, expected_fingerprint)) in enumerate(
        zip(runs, expected_datasets, strict=True)
    ):
        if index >= len(result.runs):
            continue
        completed = result.runs[index].result
        if completed is None:
            failed = result.runs[index]
            inconsistencies.append(
                f"tratamiento {planned.label!r}: resultado ausente "
                f"(error={failed.error_type!r}, mensaje={failed.error_message!r})"
            )
            continue

        _check_result_specification(
            planned.label,
            planned.spec,
            completed,
            inconsistencies,
        )
        if completed.engine_status != SimulationStatus.COMPLETED.value:
            inconsistencies.append(
                f"tratamiento {planned.label!r}: engine_status no COMPLETED "
                f"({completed.engine_status!r})"
            )
            continue

        observed_count = len(completed.events)
        if observed_count != expected_count:
            inconsistencies.append(
                f"tratamiento {planned.label!r}: conteo observado del dataset "
                f"no coincide (esperado={expected_count}, observado={observed_count})"
            )
        observed_fingerprint = dataset_fingerprint_from_events(completed.events)
        if observed_fingerprint != expected_fingerprint:
            inconsistencies.append(
                f"tratamiento {planned.label!r}: dataset_fingerprint observado "
                f"no coincide (esperado={expected_fingerprint}, "
                f"observado={observed_fingerprint})"
            )


def _check_result_specification(
    label: str,
    spec: ScientificRunSpec,
    result: ScientificRunResult,
    inconsistencies: list[str],
) -> None:
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
        observed = getattr(result, field)
        if observed != expected_value:
            inconsistencies.append(
                f"tratamiento {label!r}: resultado no coincide con su spec en "
                f"{field} (esperado={expected_value!r}, observado={observed!r})"
            )
