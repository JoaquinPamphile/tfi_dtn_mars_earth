from __future__ import annotations
import sys
import time
from pathlib import Path

from experiments.campaign import execute_campaign
from experiments.e1 import build_e1_campaign, e1_result, e1_result_json, format_e1
from experiments.e2 import build_e2_campaign, e2_result, e2_result_json, format_e2
from experiments.e3 import build_e3_campaign, e3_result, e3_result_json, format_e3
from experiments.e3_sensitivity import (
    build_e3_sensitivity_campaign,
    e3_sensitivity_json,
    e3_sensitivity_result,
    format_e3_sensitivity,
)
from experiments.evidence import EvidenceExistsError, export_campaign_evidence

from cli.arguments import ErrorDeUso


def comando_familia(comando: str, tokens: list[str], *, ayuda: str) -> int:
    """Ejecuta una familia. --export-evidence no cambia el informe de stdout."""
    familias = {
        "e1": (build_e1_campaign, e1_result, format_e1, e1_result_json),
        "e2": (build_e2_campaign, e2_result, format_e2, e2_result_json),
        "e3": (build_e3_campaign, e3_result, format_e3, e3_result_json),
        "e3-sensitivity": (
            build_e3_sensitivity_campaign,
            e3_sensitivity_result,
            format_e3_sensitivity,
            e3_sensitivity_json,
        ),
    }
    construir, evaluar, formatear, a_json = familias[comando]
    try:
        exportar, resto = _separar_export(tokens)
    except ErrorDeUso as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if resto in (["-h"], ["--help"]):
        print(ayuda, end="")
        return 0
    if resto not in ([], ["--json"]):
        print(
            f"{comando} solo admite --json y --export-evidence",
            file=sys.stderr,
        )
        return 2
    spec = construir()
    started = time.perf_counter()
    campaign = execute_campaign(spec)
    elapsed = time.perf_counter() - started
    try:
        result = evaluar(spec, campaign, wall_execution_seconds=elapsed)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if resto == ["--json"]:
        print(a_json(result))
    else:
        print(formatear(result))
    if not exportar:
        return 0
    try:
        exported = export_campaign_evidence(spec, campaign, root=_evidence_root())
    except (EvidenceExistsError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for path in exported.paths:
        print(f"Evidencia: {path}", file=sys.stderr)
    return 0


def _separar_export(tokens: list[str]) -> tuple[bool, list[str]]:
    exportar = False
    resto: list[str] = []
    for token in tokens:
        if token == "--export-evidence":
            if exportar:
                raise ErrorDeUso("--export-evidence está repetido")
            exportar = True
            continue
        resto.append(token)
    return exportar, resto


def _evidence_root() -> Path:
    return Path.cwd() / "evidence"


_FAMILIAS = frozenset({"e1", "e2", "e3", "e3-sensitivity"})

AYUDA = """\
Uso:
  python -m cli.official e1 [--json] [--export-evidence]
  python -m cli.official e2 [--json] [--export-evidence]
  python -m cli.official e3 [--json] [--export-evidence]
  python -m cli.official e3-sensitivity [--json] [--export-evidence]

Comandos:
  e1                   Ejecuta E1.
  e2                   Ejecuta E2.
  e3                   Ejecuta E3.
  e3-sensitivity       Ejecuta el análisis de sensibilidad de E3.

Opciones de E1, E2, E3 y sensibilidad:
  --json                                Informe estructurado en JSON.
  --export-evidence                     Exporta evidencia bajo evidence/.

Ayuda:
  -h, --help                            Muestra esta ayuda.
"""


def main(argv: list[str] | None = None) -> int:
    """Ejecuta la consola oficial y devuelve el código de salida."""
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if not argumentos:
        print(AYUDA, end="")
        return 2
    if argumentos[0] in {"-h", "--help", "help"}:
        print(AYUDA, end="")
        return 0
    comando = argumentos[0]
    if comando in _FAMILIAS:
        return comando_familia(comando, argumentos[1:], ayuda=AYUDA)
    print(f"comando desconocido: {comando}", file=sys.stderr)
    print(AYUDA, end="", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
