"""Compara una campaña nueva con la evidencia RC1 cerrada.

No importa el motor, no reejecuta simulaciones y no escribe en evidence/.
Los números se comparan con decimal exacto. No hay tolerancia.

Estados:
  PASS            métricas persistidas y parámetros efectivos coinciden
  FAIL            hay una diferencia científica o de identidad exigida
  INCONCLUSIVE    falta un campo indispensable o no se puede vincular

Exit 0, 1 y 2, en ese orden. El orden de contactos, las etiquetas del
banco, la identidad de campaña y la procedencia de software se informan
aparte y no alcanzan, solos, para declarar FAIL.
"""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

from .rc1_catalog import PACKAGES, RC1_REVISION, RC1_SOFTWARE_VERSION, RC1_TAG

FINGERPRINT_FIELDS = (
    "event_id",
    "source_id",
    "sequence_number",
    "generated_at_sim",
    "event_type",
    "payload",
    "priority",
    "schema_version",
)
DOCUMENTARY_SPEC_SUFFIXES = ("/trace_level",)
MISSING = object()
DIFF_LIMIT = 80


def main(argv: list[str]) -> int:
    args = _parse(argv)
    repo = Path(args["repo"]).resolve()
    candidate_path = Path(args["candidate"]).resolve()
    output = Path(args["output"]).resolve()
    _refuse_protected(output, repo)
    if not candidate_path.is_file():
        raise SystemExit(f"no existe el candidato: {candidate_path}")
    candidate = _read(candidate_path)
    family = _match_family(candidate)
    package_path = repo / family["package"]
    if not package_path.is_file():
        raise SystemExit(f"no existe la referencia: {package_path}")
    reference = _read(package_path)
    report = _compare(family, reference, candidate, package_path, candidate_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"{report['status']} config={report['scientific_configuration']} "
        f"results={report['scientific_results']} "
        f"scientific={len(report['scientific_differences'])} "
        f"identity={len(report['identity_differences'])} "
        f"documentary={len(report['documentary_differences'])} "
        f"missing={len(report['missing_fields'])}"
    )
    print(output)
    return {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 2}[report["status"]]


def _parse(argv: list[str]) -> dict[str, str]:
    values = {
        "repo": str(Path(__file__).resolve().parents[2]),
        "candidate": "",
        "output": "",
    }
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"-h", "--help"}:
            print(
                "uso: compare_to_rc1.py --candidate RESULTADO.json "
                "--output INFORME.json [--repo RAIZ]",
                file=sys.stderr,
            )
            raise SystemExit(0)
        if token not in {"--candidate", "--output", "--repo"}:
            raise SystemExit(f"opción desconocida: {token}")
        if index + 1 >= len(argv):
            raise SystemExit(f"falta el valor de {token}")
        values[token[2:]] = argv[index + 1]
        index += 2
    if not values["candidate"] or not values["output"]:
        raise SystemExit("hacen falta --candidate y --output")
    return values


def _match_family(candidate: dict) -> dict:
    artifact = candidate.get("artifact_type")
    identity = candidate.get("campaign_identity")
    manifest = candidate.get("campaign_manifest")
    if identity is None and isinstance(manifest, dict):
        identity = manifest.get("campaign_identity")
    for spec in PACKAGES:
        if artifact in spec["artifact_types"] or identity == spec["campaign_identity"]:
            return spec
    raise SystemExit(
        "el candidato no se vincula con E1, E2, E3 ni la sensibilidad RC1"
    )


def _compare(family, reference, candidate, reference_path: Path, candidate_path: Path) -> dict:
    problems: list[str] = []
    if reference.get("campaign_identity") != family["campaign_identity"]:
        problems.append("el paquete de referencia no tiene la identidad RC1 esperada")
    repro = reference.get("reproducibility") if isinstance(reference.get("reproducibility"), dict) else {}
    if repro.get("source_revision") != RC1_REVISION:
        problems.append("la referencia no declara la revisión RC1")
    if repro.get("software_version") != RC1_SOFTWARE_VERSION:
        problems.append("la referencia no declara software_version 1.0.0-rc1")
    ref_runs = _runs(reference)
    cand_runs = _runs(candidate)
    cand_results = candidate.get("run_results")
    links, link_problems = _link(ref_runs, cand_runs)
    problems.extend(link_problems)
    provenance = candidate.get("software_provenance")
    if not isinstance(provenance, dict):
        observed = candidate.get("reproducibility")
        provenance = observed if isinstance(observed, dict) else {}
        manifest = candidate.get("campaign_manifest")
        if isinstance(manifest, dict) and "source_revision" in manifest:
            provenance = {
                "software_version": manifest.get("software_version"),
                "source_revision": manifest.get("source_revision"),
                "source_state": manifest.get("source_state"),
            }
    documentary: list[dict] = []
    scientific: list[dict] = []
    identity: list[dict] = []
    missing: list[dict] = []
    coverage: list[dict] = []
    run_reports = []
    config_states = []
    result_states = []
    for ref_index, cand_index in links:
        item = _compare_run(
            ref_runs[ref_index],
            cand_runs[cand_index],
            _result_at(cand_results, cand_index),
            ref_index,
            cand_index,
        )
        run_reports.append(item["summary"])
        documentary.extend(item["documentary"])
        scientific.extend(item["scientific"])
        identity.extend(item["identity"])
        missing.extend(item["missing"])
        coverage.extend(item["coverage"])
        config_states.append(item["configuration"])
        result_states.append(item["results"])
    _campaign_documentary(reference, candidate, documentary)
    configuration = _fold_configuration(config_states, bool(links), bool(link_problems))
    results = _fold_results(result_states, bool(links), bool(link_problems))
    status = _status(problems, configuration, results, scientific, identity, missing)
    return {
        "status": status,
        "scientific_configuration": configuration,
        "scientific_results": results,
        "release_tag": RC1_TAG,
        "reference_revision": repro.get("source_revision"),
        "reference_software_version": repro.get("software_version"),
        "candidate_revision": provenance.get("source_revision"),
        "candidate_source_state": provenance.get("source_state"),
        "candidate_software_version": provenance.get("software_version"),
        "family": family["family"],
        "reference_campaign_id": family["campaign_id"],
        "reference_campaign_identity": family["campaign_identity"],
        "problems": problems,
        "runs": run_reports,
        "scientific_differences": scientific[:DIFF_LIMIT],
        "identity_differences": identity[:DIFF_LIMIT],
        "documentary_differences": documentary[:DIFF_LIMIT],
        "missing_fields": missing[:DIFF_LIMIT],
        "coverage_limits": coverage[:DIFF_LIMIT],
        "truncated": any(
            len(bucket) > DIFF_LIMIT
            for bucket in (scientific, identity, documentary, missing, coverage)
        ),
        "inputs": [
            {"role": "reference", "path": str(reference_path), "sha256": _sha256(reference_path)},
            {"role": "candidate", "path": str(candidate_path), "sha256": _sha256(candidate_path)},
        ],
        "policy": {
            "numeric": "exact decimal equality; no tolerance",
            "contact_order": (
                "un orden distinto de la misma lista de contactos es documental; "
                "cualquier otro campo de contacto es diferencia de configuración"
            ),
            "trace_level": "documental: entra en configuration_hash y no es factor de E1, E2 ni E3",
            "campaign_identity": "el banco V2 puede usar otra identidad de campaña",
            "provenance": "source_revision y source_state no entran en configuration_hash",
            "contacts_items": "si RC1 no publicó items, su ausencia no es una lista vacía",
            "pass_means": (
                "coinciden los parámetros efectivos y todas las métricas persistidas "
                "de RC1; no afirma igualdad del artefacto completo ni de trazas"
            ),
        },
    }


def _runs(document: dict) -> list[dict]:
    manifest = document.get("campaign_manifest")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("runs"), list):
        return []
    return manifest["runs"]


def _result_at(results: object, index: int) -> dict | None:
    if not isinstance(results, list) or index >= len(results):
        return None
    item = results[index]
    if not isinstance(item, dict):
        return None
    result = item.get("result")
    return result if isinstance(result, dict) else None


def _link(reference: list[dict], candidate: list[dict]) -> tuple[list[tuple[int, int]], list[str]]:
    problems: list[str] = []
    if not reference or not candidate:
        return [], ["falta la lista de corridas de la referencia o del candidato"]
    ref_keys = []
    for index, run in enumerate(reference):
        key = _scientific_key(_manifest(run))
        if key is None:
            problems.append(f"RC1 run {index} no tiene manifiesto vinculable")
            return [], problems
        ref_keys.append(key)
    if len(set(ref_keys)) != len(ref_keys):
        problems.append("dos corridas RC1 comparten la misma clave científica")
        return [], problems
    used: set[int] = set()
    links: list[tuple[int, int]] = []
    for index, run in enumerate(candidate):
        key = _scientific_key(_manifest(run))
        if key is None:
            problems.append(f"candidato run {index} no tiene manifiesto vinculable")
            continue
        matches = [pos for pos, ref_key in enumerate(ref_keys) if ref_key == key]
        if len(matches) != 1:
            problems.append(f"candidato run {index} label={run.get('label')!r} no tiene equivalente RC1 único")
            continue
        if matches[0] in used:
            problems.append(f"dos corridas del candidato equivalen a RC1[{matches[0]}]")
            continue
        used.add(matches[0])
        links.append((matches[0], index))
    missing = [index for index in range(len(reference)) if index not in used]
    if missing:
        labels = [reference[index].get("label") for index in missing]
        problems.append(f"quedaron tratamientos RC1 sin candidato: {labels}")
    if len(candidate) != len(reference):
        problems.append(
            f"cantidad de corridas candidato={len(candidate)} referencia={len(reference)}"
        )
    return links, problems


def _manifest(run: dict) -> dict | None:
    manifest = run.get("manifest")
    return manifest if isinstance(manifest, dict) else None


def _scientific_key(manifest: dict | None) -> tuple | None:
    if manifest is None:
        return None
    workload = manifest.get("workload")
    failure = manifest.get("failure_plan")
    retry = manifest.get("retry_policy")
    if not isinstance(workload, dict) or not isinstance(failure, dict) or not isinstance(retry, dict):
        return None
    losses = failure.get("silent_forward_delivery_losses")
    if not isinstance(losses, list):
        return None
    sequences = tuple(
        sorted(
            item.get("sequence_number")
            for item in losses
            if isinstance(item, dict)
        )
    )
    if len(sequences) != len(losses):
        return None
    return (
        manifest.get("strategy_type"),
        manifest.get("batch_size_events"),
        _decimal(workload.get("offered_load_fraction")),
        manifest.get("recovery_policy"),
        sequences,
        _decimal(manifest.get("gap_request_timeout_seconds")),
        _decimal(retry.get("ack_timeout_seconds")),
        workload.get("workload_id"),
        workload.get("max_events"),
        _decimal(workload.get("duration_seconds")),
        _decimal(workload.get("rate_events_per_second")),
    )


def _compare_run(reference: dict, candidate: dict, result: dict | None, ref_index: int, cand_index: int) -> dict:
    ref_manifest = _manifest(reference) or {}
    cand_manifest = _manifest(candidate) or {}
    base = f"runs[{ref_index}|{cand_index}]"
    documentary: list[dict] = []
    scientific: list[dict] = []
    identity: list[dict] = []
    missing: list[dict] = []
    coverage: list[dict] = []
    if reference.get("label") != candidate.get("label"):
        documentary.append(_row(
            f"{base}/label",
            reference.get("label"),
            candidate.get("label"),
            "la etiqueta del banco no tiene que copiar la etiqueta histórica",
        ))
    for field in ("source_revision", "source_state", "software_version"):
        if ref_manifest.get(field) != cand_manifest.get(field):
            documentary.append(_row(
                f"{base}/manifest/{field}",
                ref_manifest.get(field),
                cand_manifest.get(field),
                "procedencia de software; no entra en configuration_hash",
            ))
    config_state = _compare_spec(
        ref_manifest.get("specification"),
        cand_manifest.get("specification"),
        f"{base}/specification",
        scientific,
        documentary,
        missing,
    )
    if ref_manifest.get("configuration_hash") != cand_manifest.get("configuration_hash"):
        reason = (
            "configuration_hash cambia con el orden de contactos o trace_level"
            if config_state != "different"
            else "configuration_hash distinto junto con la especificación"
        )
        bucket = documentary if config_state != "different" else scientific
        bucket.append(_row(
            f"{base}/configuration_hash",
            ref_manifest.get("configuration_hash"),
            cand_manifest.get("configuration_hash"),
            reason,
        ))
    for field in (
        "dataset_identity",
        "dataset_fingerprint",
        "dataset_event_count",
        "execution_identity",
        "experiment_identity",
        "seed",
        "scenario_id",
    ):
        if field not in ref_manifest:
            missing.append(_row(f"{base}/manifest/{field}", None, cand_manifest.get(field), "falta en RC1"))
            continue
        if field not in cand_manifest:
            missing.append(_row(f"{base}/manifest/{field}", ref_manifest.get(field), None, "falta en el candidato"))
            continue
        if not _same(ref_manifest.get(field), cand_manifest.get(field)):
            identity.append(_row(
                f"{base}/manifest/{field}",
                ref_manifest.get(field),
                cand_manifest.get(field),
                "identidad o dataset que debe coincidir si el escenario efectivo es el de RC1",
            ))
    result_state = _compare_metrics(
        ref_manifest.get("metrics"),
        cand_manifest.get("metrics"),
        f"{base}/metrics",
        scientific,
        missing,
        coverage,
    )
    terminal_ref = (ref_manifest.get("terminal") or {}).get("engine_status")
    terminal_cand = (cand_manifest.get("terminal") or {}).get("engine_status")
    if terminal_ref != "COMPLETED" or terminal_cand != "COMPLETED":
        missing.append(_row(
            f"{base}/terminal/engine_status",
            terminal_ref,
            terminal_cand,
            "sin motor COMPLETED no hay cierre científico comparable",
        ))
        result_state = "incomplete"
    fingerprint_state = _recompute_fingerprint(
        ref_manifest.get("dataset_fingerprint"),
        ref_manifest.get("dataset_event_count"),
        result,
        f"{base}/events",
        scientific,
        coverage,
    )
    if fingerprint_state == "mismatch":
        result_state = "different"
    _candidate_consistency(cand_manifest, result, f"{base}/result", missing)
    return {
        "configuration": config_state,
        "results": result_state,
        "documentary": documentary,
        "scientific": scientific,
        "identity": identity,
        "missing": missing,
        "coverage": coverage,
        "summary": {
            "reference_index": ref_index,
            "candidate_index": cand_index,
            "reference_label": reference.get("label"),
            "candidate_label": candidate.get("label"),
            "configuration": config_state,
            "results": result_state,
            "dataset_fingerprint_recomputed": fingerprint_state,
        },
    }


def _compare_spec(reference, candidate, path, scientific, documentary, missing) -> str:
    if not isinstance(reference, dict) or not isinstance(candidate, dict):
        missing.append(_row(path, reference if isinstance(reference, dict) else None, None, "falta specification"))
        return "incomplete"
    ref_norm, ref_order = _normalize_contacts(reference)
    cand_norm, cand_order = _normalize_contacts(candidate)
    diffs: list[dict] = []
    _walk(ref_norm, cand_norm, path, diffs, scientific_bucket=True)
    real = []
    for item in diffs:
        if item["path"].endswith(DOCUMENTARY_SPEC_SUFFIXES):
            item["reason"] = "trace_level no es factor científico de E1, E2 ni E3"
            documentary.append(item)
        else:
            real.append(item)
    scientific.extend(real)
    order_diff = ref_order != cand_order
    if order_diff and not real:
        documentary.append(_row(
            path + "/scenario/contacts",
            "orden histórico",
            "orden del banco",
            "misma lista de contactos en distinto orden; configuration_hash no coincide",
        ))
    if real:
        return "different"
    if order_diff or any(item["path"].endswith(DOCUMENTARY_SPEC_SUFFIXES) for item in documentary):
        return "equivalent_with_disclosed_differences"
    return "equivalent"


def _normalize_contacts(value):
    orders = []

    def visit(node, path):
        if isinstance(node, dict):
            copied = {}
            for key in node:
                child = f"{path}/{key}"
                if key == "contacts" and isinstance(node[key], list):
                    orders.append([item.get("contact_id") if isinstance(item, dict) else None for item in node[key]])
                    copied[key] = sorted(
                        (visit(item, child + "/item") for item in node[key]),
                        key=_contact_sort_key,
                    )
                else:
                    copied[key] = visit(node[key], child)
            return copied
        if isinstance(node, list):
            return [visit(item, f"{path}/{index}") for index, item in enumerate(node)]
        return node

    return visit(value, ""), orders


def _contact_sort_key(contact) -> tuple:
    if not isinstance(contact, dict):
        return (Decimal("Infinity"), "")
    return (_decimal(contact.get("start_time_sim")) or Decimal("Infinity"), str(contact.get("contact_id")))


def _compare_metrics(reference, candidate, path, scientific, missing, coverage) -> str:
    if not isinstance(reference, dict):
        missing.append(_row(path, None, None, "RC1 no publicó metrics"))
        return "incomplete"
    if not isinstance(candidate, dict):
        missing.append(_row(path, "object", None, "el candidato no publicó metrics"))
        return "incomplete"
    scientific_before = len(scientific)
    missing_before = len(missing)
    _walk(reference, candidate, path, scientific, missing=missing, coverage=coverage, scientific_bucket=True)
    if len(missing) > missing_before:
        return "incomplete"
    if len(scientific) > scientific_before:
        return "different"
    return "match"


def _walk(left, right, path, bucket, missing=None, coverage=None, scientific_bucket=False) -> None:
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right), key=str):
            child = path + "/" + _escape(key)
            if key not in left:
                (coverage if coverage is not None else bucket).append(_row(
                    child, None, right[key], "campo del candidato que RC1 no publicó",
                ))
                continue
            if key not in right:
                if key == "items" and path.endswith("/contacts"):
                    (coverage if coverage is not None else bucket).append(_row(
                        child, "unpublished", None,
                        "RC1 no publicó contacts.items; la ausencia no es []",
                    ))
                    continue
                (missing if missing is not None else bucket).append(_row(
                    child, left[key], None, "campo RC1 ausente en el candidato",
                ))
                continue
            _walk(left[key], right[key], child, bucket, missing, coverage, scientific_bucket)
        return
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            bucket.append(_row(path, len(left), len(right), "distinta cantidad de elementos"))
        for index in range(max(len(left), len(right))):
            if index >= len(left) or index >= len(right):
                continue
            _walk(left[index], right[index], path + f"/{index}", bucket, missing, coverage, scientific_bucket)
        return
    if not _same(left, right):
        bucket.append(_row(path, left, right, "valor distinto"))


def _recompute_fingerprint(expected, count, result, path, scientific, coverage) -> str:
    if not isinstance(result, dict) or not isinstance(result.get("events"), list):
        coverage.append(_row(
            path, expected, None,
            "el candidato no trae eventos; la huella publicada se compara, no se recalcula",
        ))
        return "not_recomputed"
    events = result["events"]
    if any(not isinstance(event, dict) or set(event) != set(FINGERPRINT_FIELDS) for event in events):
        scientific.append(_row(path, list(FINGERPRINT_FIELDS), None, "los eventos no tienen los ocho campos de la huella"))
        return "mismatch"
    sequences = [event.get("sequence_number") for event in events]
    if len(set(sequences)) != len(events):
        scientific.append(_row(path, count, len(events), "hay sequence_number repetido"))
        return "mismatch"
    digest = hashlib.sha256()
    for event in sorted(events, key=lambda item: item["sequence_number"]):
        encoded = json.dumps(
            _binary64(event),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ) + "\n"
        digest.update(encoded.encode("utf-8"))
    actual = digest.hexdigest()
    if actual != expected or len(events) != count:
        scientific.append(_row(path, {"fingerprint": expected, "count": count}, {"fingerprint": actual, "count": len(events)}, "la huella recalculada no es la de RC1"))
        return "mismatch"
    return "match"


def _candidate_consistency(manifest: dict, result: dict | None, path: str, missing: list[dict]) -> None:
    if result is None:
        return
    metrics = manifest.get("metrics") if isinstance(manifest.get("metrics"), dict) else {}
    pairs = (
        ("events_persisted_earth", "earth_persisted_unique"),
        ("events_confirmed_mars", "confirmed"),
        ("simulation_time", "time_sim"),
    )
    for result_field, metric_field in pairs:
        if result_field in result and not _same(result.get(result_field), metrics.get(metric_field)):
            missing.append(_row(
                path + "/" + result_field,
                metrics.get(metric_field),
                result.get(result_field),
                "el candidato no coincide consigo mismo",
            ))


def _campaign_documentary(reference: dict, candidate: dict, documentary: list[dict]) -> None:
    ref_manifest = reference.get("campaign_manifest") if isinstance(reference.get("campaign_manifest"), dict) else {}
    cand_manifest = candidate.get("campaign_manifest") if isinstance(candidate.get("campaign_manifest"), dict) else {}
    for field, reason in (
        ("campaign_id", "el banco V2 usa su propio identificador de campaña"),
        ("campaign_identity", "la identidad de campaña del banco no replica la histórica"),
        ("description", "el texto de campaña puede diferir sin cambiar los parámetros"),
        ("source_revision", "la revisión ejecutada no es la revisión que produjo RC1"),
        ("source_state", "la imagen de desarrollo no demuestra un árbol clean"),
        ("software_version", "etiqueta de versión; no entra en configuration_hash"),
    ):
        left = ref_manifest.get(field, reference.get(field))
        right = cand_manifest.get(field, candidate.get(field))
        if right is not None and not _same(left, right):
            documentary.append(_row("campaign/" + field, left, right, reason))


def _fold_configuration(states: list[str], linked: bool, link_problems: bool) -> str:
    if not linked or link_problems:
        return "incomplete"
    if any(state == "different" for state in states):
        return "different"
    if any(state == "incomplete" for state in states):
        return "incomplete"
    if any(state == "equivalent_with_disclosed_differences" for state in states):
        return "equivalent_with_disclosed_differences"
    if states and all(state == "equivalent" for state in states):
        return "equivalent"
    return "incomplete"


def _fold_results(states: list[str], linked: bool, link_problems: bool) -> str:
    if not linked or link_problems:
        return "incomplete"
    if any(state == "different" for state in states):
        return "different"
    if any(state != "match" for state in states):
        return "incomplete"
    return "match"


def _status(problems, configuration, results, scientific, identity, missing) -> str:
    if scientific or identity or configuration == "different" or results == "different":
        return "FAIL"
    if (
        problems
        or missing
        or configuration not in {"equivalent", "equivalent_with_disclosed_differences"}
        or results != "match"
    ):
        return "INCONCLUSIVE"
    return "PASS"


def _row(path: str, left, right, reason: str) -> dict:
    return {"path": path, "reference": _plain(left), "candidate": _plain(right), "reason": reason}


def _plain(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        if len(value) > 12:
            return {"length": len(value), "head": [_plain(item) for item in value[:4]]}
        return [_plain(item) for item in value]
    return value


def _same(left, right) -> bool:
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        left_num = _decimal(left)
        right_num = _decimal(right)
        return left_num is not None and right_num is not None and left_num == right_num
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(_same(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _decimal(value):
    if value is None or value is MISSING:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except Exception:
            return None
    return None


def _binary64(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_binary64(item) for item in value]
    if isinstance(value, dict):
        return {key: _binary64(item) for key, item in value.items()}
    return value


def _escape(key: object) -> str:
    return str(key).replace("~", "~0").replace("/", "~1")


def _read(path: Path) -> dict:
    def unique(pairs):
        result = {}
        seen = set()
        for key, value in pairs:
            if key in seen:
                raise SystemExit(f"clave JSON duplicada en {path}: {key}")
            seen.add(key)
            result[key] = value
        return result

    def parse_number(text: str):
        return Decimal(text)

    loaded = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique,
        parse_float=parse_number,
    )
    if not isinstance(loaded, dict):
        raise SystemExit(f"{path} no es un objeto JSON")
    return loaded


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _refuse_protected(path: Path, repo: Path) -> None:
    resolved = path.resolve()
    for folder in ("evidence", "configs", "backend"):
        root = (repo / folder).resolve()
        if resolved == root or root in resolved.parents:
            raise SystemExit(f"no se escribe dentro de {folder}/")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main(sys.argv[1:]))
