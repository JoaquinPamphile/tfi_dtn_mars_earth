"""Inventario de solo lectura de la evidencia RC1. No escribe en evidence/."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from .rc1_catalog import (
    PACKAGES,
    RC1_REVISION,
    RC1_SOFTWARE_VERSION,
    RC1_TAG,
    RUN_ORDER_FIELDS,
)

METRIC_SCALARS = (
    "generated",
    "earth_persisted_unique",
    "confirmed",
    "backlog",
    "final_backlog",
    "not_persisted_on_earth",
    "persisted_on_earth_but_unconfirmed",
    "completeness",
    "confirmation_ratio",
    "confirmed_ratio",
    "persisted_unconfirmed_ratio",
    "not_persisted_ratio",
    "gaps_count",
    "duplicates_received",
    "duplicates_stored",
    "retry_attempts_total",
    "converged",
    "convergence_reference_at_sim",
    "converged_at_sim",
    "time_to_convergence_seconds",
    "time_sim",
    "scenario_completed_at_sim",
    "view_age_seconds",
    "freshness_coverage",
    "freshness_sample_count",
    "freshness_min_seconds",
    "freshness_p50_seconds",
    "freshness_p95_seconds",
    "freshness_max_seconds",
    "freshness_mean_seconds",
    "sync_units_created",
)

RECOVERY_SCALARS = (
    "episode_count",
    "recovered_count",
    "confirmed_count",
    "sender_ack_timeout_count",
    "sender_retry_attempt_count",
    "receiver_gap_request_logical_count",
    "receiver_repair_attempt_count",
    "gap_request_transport_attempt_count",
    "duplicates_received_after_loss",
    "duplicates_stored_after_loss",
    "policy_recovery_forward_bytes",
    "policy_recovery_reverse_bytes",
    "policy_recovery_network_bytes_total",
    "loss_to_trigger_seconds",
    "loss_to_earth_recovery_seconds",
    "loss_to_origin_confirmation_seconds",
    "loss_to_gap_observed_seconds",
    "trigger_to_earth_recovery_seconds",
    "earth_recovery_to_origin_confirmation_seconds",
    "gap_observed_at_sim",
)

CONTACT_SCALARS = (
    "contacts_total",
    "contacts_used",
    "contacts_forced_cut",
    "contact_utilization_mean",
    "contact_utilization_weighted",
    "forward_contact_utilization_weighted",
    "reverse_contact_utilization_weighted",
)

EPISODE_FIELDS = (
    "episode_id",
    "episode_status",
    "event_id",
    "failure_type",
    "failure_occurrence",
    "hop",
    "sequence_number",
    "loss_at_sim",
    "gap_observed_at_sim",
    "earth_recovered",
    "earth_recovered_at_sim",
    "loss_to_trigger_seconds",
    "loss_to_earth_recovery_seconds",
    "loss_to_origin_confirmation_seconds",
    "earth_recovery_to_origin_confirmation_seconds",
    "common_lost_attempt_bytes_mars_relay",
    "common_lost_attempt_bytes_relay_earth",
    "policy_recovery_forward_bytes",
    "policy_recovery_reverse_bytes",
    "policy_recovery_network_bytes_total",
    "sender_retry_attempt_count",
    "receiver_gap_request_logical_count",
    "receiver_repair_attempt_count",
    "gap_request_bytes_earth_relay",
    "gap_request_bytes_relay_mars",
)


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Inventario de lectura de RC1 congelado")
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    repo=args.repo.resolve()
    out=args.output
    if out.resolve()==Path(__file__).with_name('reference_inventory.json').resolve():
        raise ValueError('no sobrescribir la captura RC1 aprobada')
    _refuse_protected(out, repo)
    findings: list[str] = []
    packages = []
    for spec in PACKAGES:
        packages.append(_package(repo, spec, findings))
    _cross_checks(packages, findings)
    document = {
        "release_tag": RC1_TAG,
        "source_revision_required": RC1_REVISION,
        "software_version_required": RC1_SOFTWARE_VERSION,
        "integrity_ok": not findings,
        "findings": findings,
        "packages": packages,
        "note": (
            "Inventario leído de los JSON actuales. No recalcula campañas. "
            "La sensibilidad vive en el manifiesto; no hay copia en official/."
        ),
    }
    text = json.dumps(document, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"integrity_ok={document['integrity_ok']} findings={len(findings)} output={out}")
    for item in findings:
        print(f"FINDING {item}")
    return 0 if document["integrity_ok"] else 1


def _package(repo: Path, spec: dict, findings: list[str]) -> dict:
    identity = spec["campaign_identity"]
    package_path = repo / spec["package"]
    record: dict = {
        "family": spec["family"],
        "role": spec["role"],
        "campaign_id": spec["campaign_id"],
        "campaign_identity": identity,
        "package_path": spec["package"],
        "manifest_path": spec["manifest"],
        "artifact_types": list(spec["artifact_types"]),
    }
    if not package_path.is_file():
        findings.append(f"{identity}: falta {spec['package']}")
        record["present"] = False
        return record
    raw = package_path.read_bytes()
    record["present"] = True
    record["size_bytes"] = len(raw)
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        package = _load(raw, spec["package"], findings)
    except ValueError as exc:
        findings.append(f"{identity}: {exc}")
        return record
    record["canonical_roundtrip"] = _canonical(raw, package)
    if not record["canonical_roundtrip"]:
        findings.append(f"{identity}: el paquete no re-serializa al JSON canónico")
    _expect(package, spec, findings)
    manifest_body = package.get("campaign_manifest")
    if not isinstance(manifest_body, dict):
        findings.append(f"{identity}: falta campaign_manifest")
        return record
    runs = manifest_body.get("runs")
    if not isinstance(runs, list) or not runs:
        findings.append(f"{identity}: campaign_manifest.runs vacío")
        runs = []
    record["status"] = manifest_body.get("status")
    record["run_count"] = manifest_body.get("run_count")
    record["completed_count"] = manifest_body.get("completed_count")
    record["failed_count"] = manifest_body.get("failed_count")
    record["description"] = manifest_body.get("description")
    if record["run_count"] != len(runs):
        findings.append(f"{identity}: run_count no coincide con la lista")
    if record["status"] != "COMPLETED":
        findings.append(f"{identity}: status={record['status']!r}")
    if spec["manifest"] is None:
        official_copy = repo / "evidence" / "official" / "e3" / f"{identity}.json"
        record["official_copy_present"] = official_copy.is_file()
        if official_copy.is_file():
            findings.append(f"{identity}: apareció una copia official no prevista")
    else:
        record["manifest_check"] = _check_manifest(repo, spec, package, findings)
    summarized = [_summarize_run(run, identity, index, findings) for index, run in enumerate(runs)]
    record["runs"] = summarized
    _dataset_coherence(spec["family"], summarized, identity, findings)
    return record


def _load(raw: bytes, label: str, findings: list[str]) -> dict:
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError(f"UTF-8 inválido en {label}") from exc
    if "\r" in text:
        findings.append(f"{label}: contiene CR")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"clave JSON duplicada en {label}: {key}")
            result[key] = value
        return result

    loaded = json.loads(text, object_pairs_hook=unique)
    if not isinstance(loaded, dict):
        raise ValueError(f"{label} no es un objeto")
    return loaded


def _canonical(raw: bytes, package: dict) -> bool:
    text = json.dumps(package, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    return raw == text.encode("utf-8")


def _expect(package: dict, spec: dict, findings: list[str]) -> None:
    identity = spec["campaign_identity"]
    repro = package.get("reproducibility")
    if not isinstance(repro, dict):
        findings.append(f"{identity}: falta reproducibility")
        return
    if package.get("campaign_id") != spec["campaign_id"]:
        findings.append(f"{identity}: campaign_id={package.get('campaign_id')!r}")
    if package.get("campaign_identity") != identity:
        findings.append(f"{identity}: campaign_identity distinta")
    if package.get("family") != ("e3" if spec["family"] == "e3_sensitivity" else spec["family"]):
        findings.append(f"{identity}: family={package.get('family')!r}")
    if package.get("role") != spec["role"]:
        findings.append(f"{identity}: role={package.get('role')!r}")
    if package.get("evidence_schema_version") != 1:
        findings.append(f"{identity}: evidence_schema_version distinta de 1")
    if repro.get("source_revision") != RC1_REVISION:
        findings.append(f"{identity}: source_revision={repro.get('source_revision')!r}")
    if repro.get("source_state") != "clean":
        findings.append(f"{identity}: source_state={repro.get('source_state')!r}")
    if repro.get("software_version") != RC1_SOFTWARE_VERSION:
        findings.append(f"{identity}: software_version={repro.get('software_version')!r}")
    if repro.get("hash_algorithm") != "sha256":
        findings.append(f"{identity}: hash_algorithm distinto de sha256")
    manifest = package.get("campaign_manifest")
    if isinstance(manifest, dict):
        if manifest.get("source_revision") != RC1_REVISION:
            findings.append(f"{identity}: el manifiesto no repite source_revision RC1")
        if manifest.get("source_state") != "clean":
            findings.append(f"{identity}: el manifiesto no está clean")
        if manifest.get("campaign_identity") != identity:
            findings.append(f"{identity}: identidad del manifiesto distinta")


def _check_manifest(repo: Path, spec: dict, package: dict, findings: list[str]) -> dict:
    identity = spec["campaign_identity"]
    path = repo / spec["manifest"]
    result = {"path": spec["manifest"], "present": path.is_file()}
    if not path.is_file():
        findings.append(f"{identity}: falta el manifiesto {spec['manifest']}")
        return result
    raw = path.read_bytes()
    result["sha256"] = hashlib.sha256(raw).hexdigest()
    result["size_bytes"] = len(raw)
    try:
        manifest = _load(raw, spec["manifest"], findings)
    except ValueError as exc:
        findings.append(str(exc))
        return result
    result["canonical_roundtrip"] = _canonical(raw, manifest)
    if not result["canonical_roundtrip"]:
        findings.append(f"{identity}: el manifiesto no re-serializa al JSON canónico")
    expected = _provenance_record(package, spec["package"].split("evidence/", 1)[1])
    result["matches_package_projection"] = manifest == expected
    if manifest != expected:
        findings.append(f"{identity}: el manifiesto no es la proyección del paquete oficial")
    return result


def _provenance_record(package: dict, evidence_file: str) -> dict:
    manifest = package["campaign_manifest"]
    order = []
    for run in manifest["runs"]:
        order.append({field: run[field] for field in RUN_ORDER_FIELDS})
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


def _summarize_run(run: dict, identity: str, index: int, findings: list[str]) -> dict:
    label = run.get("label")
    prefix = f"{identity}[{index}:{label}]"
    if run.get("index") != index:
        findings.append(f"{prefix}: index={run.get('index')!r}")
    manifest = run.get("manifest")
    if not isinstance(manifest, dict):
        findings.append(f"{prefix}: falta manifest")
        return {"index": index, "label": label, "manifest_present": False}
    for field in (
        "configuration_hash",
        "dataset_fingerprint",
        "dataset_identity",
        "execution_identity",
    ):
        if run.get(field) != manifest.get(field):
            findings.append(f"{prefix}: {field} del orden no coincide con el manifiesto")
    if run.get("completed") is not True or run.get("failed") is not False:
        findings.append(f"{prefix}: completed/failed no están en éxito")
    if manifest.get("source_revision") != RC1_REVISION:
        findings.append(f"{prefix}: source_revision de la corrida distinta de RC1")
    workload = manifest.get("workload") if isinstance(manifest.get("workload"), dict) else {}
    metrics = manifest.get("metrics") if isinstance(manifest.get("metrics"), dict) else None
    if metrics is None:
        findings.append(f"{prefix}: metrics ausente")
    summary = {
        "index": index,
        "label": label,
        "configuration_hash": manifest.get("configuration_hash"),
        "dataset_fingerprint": manifest.get("dataset_fingerprint"),
        "dataset_identity": manifest.get("dataset_identity"),
        "experiment_identity": manifest.get("experiment_identity"),
        "execution_identity": manifest.get("execution_identity"),
        "dataset_event_count": manifest.get("dataset_event_count"),
        "seed": manifest.get("seed"),
        "scenario_id": manifest.get("scenario_id"),
        "horizon_seconds": manifest.get("horizon_seconds"),
        "strategy_type": manifest.get("strategy_type"),
        "batch_size_events": manifest.get("batch_size_events"),
        "recovery_policy": manifest.get("recovery_policy"),
        "stop_policy": manifest.get("stop_policy"),
        "gap_request_timeout_seconds": manifest.get("gap_request_timeout_seconds"),
        "trace_level": manifest.get("trace_level"),
        "ack_timeout_seconds": (manifest.get("retry_policy") or {}).get("ack_timeout_seconds"),
        "workload_id": manifest.get("workload_id"),
        "event_type": workload.get("event_type"),
        "flow": workload.get("flow"),
        "offered_load_fraction": workload.get("offered_load_fraction"),
        "max_events": workload.get("max_events"),
        "duration_seconds": workload.get("duration_seconds"),
        "rate_events_per_second": workload.get("rate_events_per_second"),
        "canonical_individual_syncunit_bytes": workload.get("canonical_individual_syncunit_bytes"),
        "failure_plan": manifest.get("failure_plan"),
        "engine_status": (manifest.get("terminal") or {}).get("engine_status"),
        "contact_count": _contact_count(manifest),
        "contacts_items_published": _contacts_items_published(metrics),
    }
    if metrics is not None:
        summary["metrics"] = {key: metrics.get(key) for key in METRIC_SCALARS}
        traffic = metrics.get("traffic") if isinstance(metrics.get("traffic"), dict) else {}
        summary["traffic"] = traffic
        contacts = metrics.get("contacts") if isinstance(metrics.get("contacts"), dict) else {}
        summary["contacts"] = {key: contacts.get(key) for key in CONTACT_SCALARS}
        recovery = metrics.get("recovery") if isinstance(metrics.get("recovery"), dict) else {}
        summary["recovery"] = {key: recovery.get(key) for key in RECOVERY_SCALARS if key in recovery}
        episodes = recovery.get("episodes")
        summary["episodes"] = _episodes(episodes)
        _metric_consistency(prefix, summary, metrics, findings)
    return summary


def _contact_count(manifest: dict) -> int | None:
    specification = manifest.get("specification")
    if not isinstance(specification, dict):
        return None
    scenario = specification.get("scenario")
    if not isinstance(scenario, dict) or not isinstance(scenario.get("contacts"), list):
        return None
    return len(scenario["contacts"])


def _contacts_items_published(metrics: dict | None) -> bool:
    if not isinstance(metrics, dict):
        return False
    contacts = metrics.get("contacts")
    return isinstance(contacts, dict) and "items" in contacts


def _episodes(episodes: object) -> list[dict]:
    if not isinstance(episodes, list):
        return []
    rows = []
    for episode in episodes:
        if not isinstance(episode, dict):
            continue
        row = {field: episode.get(field) for field in EPISODE_FIELDS if field in episode}
        loss = episode.get("loss")
        if isinstance(loss, dict) and "sequence_number" not in row:
            row["sequence_number"] = loss.get("sequence_number")
        rows.append(row)
    return rows


def _metric_consistency(prefix: str, summary: dict, metrics: dict, findings: list[str]) -> None:
    generated = metrics.get("generated")
    persisted = metrics.get("earth_persisted_unique")
    confirmed = metrics.get("confirmed")
    missing = metrics.get("not_persisted_on_earth")
    unconfirmed = metrics.get("persisted_on_earth_but_unconfirmed")
    if isinstance(generated, int) and isinstance(persisted, int) and isinstance(missing, int):
        if persisted + missing != generated:
            findings.append(f"{prefix}: persistencia no parte el total generado")
    if isinstance(persisted, int) and isinstance(confirmed, int) and isinstance(unconfirmed, int):
        if confirmed + unconfirmed != persisted:
            findings.append(f"{prefix}: confirmación no parte lo persistido en Tierra")
    if metrics.get("backlog") != metrics.get("final_backlog"):
        findings.append(f"{prefix}: backlog y final_backlog difieren")
    if isinstance(generated, int) and isinstance(confirmed, int):
        if metrics.get("backlog") != generated - confirmed:
            findings.append(f"{prefix}: backlog no es generados menos confirmados")
    if summary.get("dataset_event_count") != generated:
        findings.append(f"{prefix}: dataset_event_count distinto de generated")
    freshness = metrics.get("freshness")
    if isinstance(freshness, dict):
        for source, target in (
            ("count", "freshness_sample_count"),
            ("min_seconds", "freshness_min_seconds"),
            ("p50_seconds", "freshness_p50_seconds"),
            ("p95_seconds", "freshness_p95_seconds"),
            ("max_seconds", "freshness_max_seconds"),
            ("mean_seconds", "freshness_mean_seconds"),
        ):
            if freshness.get(source) != metrics.get(target):
                findings.append(f"{prefix}: freshness.{source} no coincide con {target}")
    recovery = metrics.get("recovery")
    if isinstance(recovery, dict) and isinstance(recovery.get("episodes"), list):
        if recovery.get("episode_count") != len(recovery["episodes"]):
            findings.append(f"{prefix}: episode_count distinto de la lista")
    terminal = summary.get("engine_status")
    if terminal != "COMPLETED":
        findings.append(f"{prefix}: engine_status={terminal!r}")


def _dataset_coherence(family: str, runs: list[dict], identity: str, findings: list[str]) -> None:
    fingerprints = [run.get("dataset_fingerprint") for run in runs]
    identities = [run.get("dataset_identity") for run in runs]
    if not fingerprints:
        return
    if family in {"e1", "e3", "e3_sensitivity"}:
        if len(set(fingerprints)) != 1:
            findings.append(f"{identity}: los tratamientos no comparten dataset_fingerprint")
        if len(set(identities)) != 1:
            findings.append(f"{identity}: los tratamientos no comparten dataset_identity")
    if family == "e2":
        if len(set(identities)) != 1:
            findings.append(f"{identity}: E2 no comparte dataset_identity")
        if len(runs) % 2 != 0:
            findings.append(f"{identity}: E2 no tiene parejas")
            return
        for offset in range(0, len(runs), 2):
            left = runs[offset].get("dataset_fingerprint")
            right = runs[offset + 1].get("dataset_fingerprint")
            if left != right:
                findings.append(f"{identity}: la pareja {offset} no comparte fingerprint")
            if offset >= 2 and left == runs[offset - 2].get("dataset_fingerprint"):
                findings.append(f"{identity}: cargas distintas comparten fingerprint")


def _cross_checks(packages: list[dict], findings: list[str]) -> None:
    by_family = {item["family"]: item for item in packages if item.get("runs")}
    needed = ("e1", "e3", "e3_sensitivity")
    if not all(name in by_family for name in needed):
        return
    fingerprints = {
        by_family[name]["runs"][0].get("dataset_fingerprint") for name in needed
    }
    identities = {
        by_family[name]["runs"][0].get("dataset_identity") for name in needed
    }
    if len(fingerprints) != 1:
        findings.append("E1, E3 y la sensibilidad no comparten dataset_fingerprint")
    if len(identities) != 1:
        findings.append("E1, E3 y la sensibilidad no comparten dataset_identity")
    if "e2" in by_family:
        e2_identity = by_family["e2"]["runs"][0].get("dataset_identity")
        e1_identity = by_family["e1"]["runs"][0].get("dataset_identity")
        if e2_identity != e1_identity:
            findings.append("E2 y E1 no comparten dataset_identity de escenario y semilla")
        e2_prints = {run.get("dataset_fingerprint") for run in by_family["e2"]["runs"]}
        if by_family["e1"]["runs"][0].get("dataset_fingerprint") in e2_prints:
            findings.append("una carga E2 reutiliza el fingerprint del dataset E1")


def _refuse_protected(path: Path, repo: Path) -> None:
    resolved = path.resolve()
    for folder in ("evidence", "configs", "backend"):
        root = (repo / folder).resolve()
        if resolved == root or root in resolved.parents:
            raise SystemExit(f"no se escribe dentro de {folder}/")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
