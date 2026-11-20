"""Lectura y verificación del formato histórico campaign_run_set, versión 1.

La escritura ya no pertenece al contrato productivo V2.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.campaign import (
    CAMPAIGN_COMPLETED,
    CampaignSpec,
    _expected_result_spec_values,
)
from experiments.fingerprint import (
    dataset_event_count,
    dataset_fingerprint,
    dataset_fingerprint_from_events,
)
from experiments.result import GeneratedTelemetry
from experiments.spec import ScientificRunSpec

CAMPAIGN_RUN_SET_FORMAT = "campaign_run_set"
CAMPAIGN_RUN_SET_VERSION = 1
CAMPAIGN_RUN_RESULT_ARTIFACT = "campaign_run_result"
CAMPAIGN_RUN_SET_INDEX_ARTIFACT = "campaign_run_set_index"
INDEX_FILENAME = "campaign-run-set-index.json"


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


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

def main(argv: list[str] | None = None) -> int:
    """Verifica un índice histórico sin campaña esperada; emite el informe JSON."""
    import argparse

    parser = argparse.ArgumentParser(description="Verifica un campaign_run_set histórico sin ejecutar campañas.")
    parser.add_argument("index", type=Path, help="Archivo campaign-run-set-index.json a verificar")
    args = parser.parse_args(argv)
    report = verify_campaign_run_set(args.index)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
