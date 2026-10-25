"""Consola mínima para ejecutar la demostración local del motor.

La ejecución vive en ``runner``. Este módulo solo interpreta argumentos
y presenta el resultado. ``inspect-e1`` prepara una campaña y no la ejecuta.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

from core.simulation.engine import SimulationStatus
from core.sync.strategy import (
    STRATEGY_TYPE_FIXED_BATCH,
    STRATEGY_TYPE_INDIVIDUAL,
    InvalidSyncStrategyConfigError,
    UnknownSyncStrategyError,
)
from experiments.campaign import controlled_development_campaign, execute_campaign
from experiments.controlled import controlled_local_run_spec
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
from experiments.experiment_campaign_loader import load_e1_campaign
from experiments.execute import execute_scientific_run
from experiments.report import format_campaign, format_scientific_run
from runner import execute_run
from runner.config import RECOVERY_MODES
from runner.demo import DEMO_DEFAULT_EVENTS, FAULT_MODES, FAULT_NONE, demo_run_config
from runner.result import RunResult

from cli.present import (
    format_e1_campaign_inspection,
    format_scientific_summary,
    format_summary,
    format_trace,
    summary_json,
)

AYUDA = """\
Uso:
  python -m cli run [opciones]
  python -m cli scientific-run
  python -m cli scientific-campaign
  python -m cli e1 [--json] [--export-evidence]
  python -m cli e2 [--json] [--export-evidence]
  python -m cli e3 [--json] [--export-evidence]
  python -m cli e3-sensitivity [--json] [--export-evidence]
  python -m cli inspect-e1 --config <archivo.json>

Comandos:
  run                  Ejecuta una demostración local.
  scientific-run       Ejecuta la corrida científica controlada.
  scientific-campaign  Ejecuta la campaña controlada de desarrollo.
  e1                   Ejecuta E1.
  e2                   Ejecuta E2.
  e3                   Ejecuta E3.
  e3-sensitivity       Ejecuta el análisis de sensibilidad de E3.
  inspect-e1           Prepara e inspecciona una campaña E1, sin ejecutarla.

Opciones de run:
  --strategy {individual,fixed_batch}   Estrategia. Por defecto: individual.
  --batch-size N                        Tamaño de lote. Obligatorio en fixed_batch.
  --events N                            Eventos a generar. Por defecto: 10.
  --recovery {none,sender-driven,receiver-driven}
                                        Recuperación. Por defecto: none.
  --fault silent-loss                   Inyecta una pérdida silenciosa.
  --json                                Resumen operativo en JSON.
  --show-trace                          Traza: tiempo, índice, tipo y entidad.
  --scientific-summary                  Métricas científicas de esta corrida.

Opciones de E1, E2, E3 y sensibilidad:
  --json                                Informe estructurado en JSON.
  --export-evidence                     Exporta evidencia bajo evidence/.

Opciones de inspect-e1:
  --config ARCHIVO                      Configuración E1. Prepara e inspecciona, sin ejecutar.

Ayuda:
  -h, --help                            Muestra esta ayuda.
"""

_ESTRATEGIAS = (STRATEGY_TYPE_INDIVIDUAL, STRATEGY_TYPE_FIXED_BATCH)


class _UsoError(Exception):
    """El uso de la consola no es válido."""


class _AyudaPedida(Exception):
    """El usuario pidió la ayuda."""


@dataclass(frozen=True, slots=True)
class _Opciones:
    strategy: str
    batch_size: int | None
    events: int
    recovery: str
    fault: str
    as_json: bool
    show_trace: bool
    scientific_summary: bool


def main(argv: list[str] | None = None) -> int:
    """Ejecuta la consola y devuelve el código de salida."""
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if not argumentos:
        print(AYUDA, end="")
        return 2
    if argumentos[0] in {"-h", "--help", "help"}:
        print(AYUDA, end="")
        return 0
    comando = argumentos[0]
    if comando == "scientific-run":
        return _comando_scientific(argumentos[1:])
    if comando == "scientific-campaign":
        return _comando_campaign(argumentos[1:])
    if comando == "inspect-e1":
        return _comando_inspect_e1(argumentos[1:])
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
    familia = familias.get(comando)
    if familia is not None:
        construir, evaluar, formatear, a_json = familia
        return _comando_familia(
            argumentos[1:],
            comando=comando,
            construir=construir,
            evaluar=evaluar,
            formatear=formatear,
            a_json=a_json,
        )
    if comando != "run":
        print(f"comando desconocido: {comando}", file=sys.stderr)
        print(AYUDA, end="", file=sys.stderr)
        return 2
    try:
        opciones = _parse_opciones(argumentos[1:])
    except _AyudaPedida:
        print(AYUDA, end="")
        return 0
    except _UsoError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        config = demo_run_config(
            strategy_type=opciones.strategy,
            batch_size_events=opciones.batch_size,
            event_count=opciones.events,
            recovery=opciones.recovery,
            fault=opciones.fault,
        )
        result = execute_run(config)
    except (UnknownSyncStrategyError, InvalidSyncStrategyConfigError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    _emitir(result, opciones)
    if result.engine_status != SimulationStatus.COMPLETED.value:
        return 1
    return 0


def _comando_scientific(tokens: list[str]) -> int:
    """Ejecuta la especificación controlada local. No acepta una campaña."""
    if tokens:
        if tokens == ["-h"] or tokens == ["--help"]:
            print(AYUDA, end="")
            return 0
        print(
            "scientific-run no admite argumentos: usa la corrida controlada local",
            file=sys.stderr,
        )
        return 2
    result = execute_scientific_run(controlled_local_run_spec())
    print(format_scientific_run(result))
    if result.engine_status != SimulationStatus.COMPLETED.value:
        return 1
    return 0


def _comando_campaign(tokens: list[str]) -> int:
    """Ejecuta la campaña controlada de desarrollo. No acepta una grilla."""
    if tokens:
        if tokens == ["-h"] or tokens == ["--help"]:
            print(AYUDA, end="")
            return 0
        print(
            "scientific-campaign no admite argumentos: usa la campaña controlada de desarrollo",
            file=sys.stderr,
        )
        return 2
    result = execute_campaign(controlled_development_campaign())
    print("Campaña científica controlada de desarrollo.")
    print("No es evidencia científica.")
    print()
    print("Campaña científica controlada")
    print()
    print(format_campaign(result))
    incompleta = any(
        run.result is None or run.result.engine_status != SimulationStatus.COMPLETED.value
        for run in result.runs
    )
    if incompleta:
        return 1
    return 0


_OPCIONES_DE_EJECUCION = frozenset(
    {
        "--json",
        "--export-evidence",
        "--show-trace",
        "--scientific-summary",
        "--strategy",
        "--batch-size",
        "--events",
        "--recovery",
        "--fault",
    }
)


def _comando_inspect_e1(tokens: list[str]) -> int:
    """Prepara una campaña E1 y muestra el resumen. No ejecuta el motor."""
    if tokens == ["-h"] or tokens == ["--help"]:
        print(AYUDA, end="")
        return 0
    try:
        config_path = _ruta_de_config(tokens)
    except _UsoError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        resuelta = load_e1_campaign(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(format_e1_campaign_inspection(resuelta))
    return 0


def _ruta_de_config(tokens: list[str]) -> str:
    """Devuelve la ruta de --config. No abre el archivo."""
    ruta: str | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        opcion = token.split("=", 1)[0]
        if opcion in _OPCIONES_DE_EJECUCION:
            raise _UsoError(
                "inspect-e1 no admite opciones de ejecución ni de exportación: "
                f"{opcion}"
            )
        if opcion != "--config":
            raise _UsoError(f"argumento no reconocido: {token}")
        if ruta is not None:
            raise _UsoError("--config está repetido")
        if not token.startswith("--config="):
            if index + 1 < len(tokens):
                siguiente = tokens[index + 1].split("=", 1)[0]
                if siguiente in _OPCIONES_DE_EJECUCION:
                    raise _UsoError(
                        "inspect-e1 no admite opciones de ejecución ni de exportación: "
                        f"{siguiente}"
                    )
            if index + 1 >= len(tokens) or tokens[index + 1].startswith("-"):
                raise _UsoError("falta el valor de --config")
        valor, index = _valor(tokens, index, "--config")
        if valor.strip() == "":
            raise _UsoError("la ruta de --config no debe estar vacía")
        opcion_valor = valor.split("=", 1)[0]
        if opcion_valor in _OPCIONES_DE_EJECUCION:
            raise _UsoError(
                "inspect-e1 no admite opciones de ejecución ni de exportación: "
                f"{opcion_valor}"
            )
        if valor.startswith("-"):
            raise _UsoError(f"argumento no reconocido: {valor}")
        ruta = valor
        index += 1
    if ruta is None:
        raise _UsoError("inspect-e1 requiere --config")
    return ruta


def _comando_familia(
    tokens: list[str],
    *,
    comando: str,
    construir: object,
    evaluar: object,
    formatear: object,
    a_json: object,
) -> int:
    """Ejecuta una familia. --export-evidence no cambia el informe de stdout."""
    try:
        exportar, resto = _separar_export(tokens)
    except _UsoError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if resto in (["-h"], ["--help"]):
        print(AYUDA, end="")
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
                raise _UsoError("--export-evidence está repetido")
            exportar = True
            continue
        resto.append(token)
    return exportar, resto


def _evidence_root() -> Path:
    return Path.cwd() / "evidence"


def _parse_opciones(tokens: list[str]) -> _Opciones:
    strategy = STRATEGY_TYPE_INDIVIDUAL
    batch_size: int | None = None
    events = DEMO_DEFAULT_EVENTS
    recovery = "none"
    fault = FAULT_NONE
    as_json = False
    show_trace = False
    scientific_summary = False
    batch_informado = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        opcion = token.split("=", 1)[0]
        if token in {"-h", "--help"}:
            raise _AyudaPedida()
        if token == "--json":
            as_json = True
        elif token == "--show-trace":
            show_trace = True
        elif token == "--scientific-summary":
            scientific_summary = True
        elif opcion == "--strategy":
            valor, index = _valor(tokens, index, "--strategy")
            if valor not in _ESTRATEGIAS:
                admitidas = ", ".join(_ESTRATEGIAS)
                raise _UsoError(
                    f"estrategia no admitida: {valor}. Admitidas: {admitidas}."
                )
            strategy = valor
        elif opcion == "--batch-size":
            valor, index = _valor(tokens, index, "--batch-size")
            batch_size = _entero(valor, "--batch-size")
            batch_informado = True
        elif opcion == "--events":
            valor, index = _valor(tokens, index, "--events")
            events = _entero(valor, "--events")
        elif opcion == "--recovery":
            valor, index = _valor(tokens, index, "--recovery")
            if valor not in RECOVERY_MODES:
                admitidas = ", ".join(RECOVERY_MODES)
                raise _UsoError(
                    f"recuperación no admitida: {valor}. Admitidas: {admitidas}."
                )
            recovery = valor
        elif opcion == "--fault":
            valor, index = _valor(tokens, index, "--fault")
            if valor not in FAULT_MODES or valor == FAULT_NONE:
                raise _UsoError(
                    f"falla no admitida: {valor}. Admitida: silent-loss."
                )
            fault = valor
        else:
            raise _UsoError(f"argumento no reconocido: {token}")
        index += 1
    if events < 1:
        raise _UsoError("la cantidad de eventos debe ser al menos 1")
    if strategy == STRATEGY_TYPE_FIXED_BATCH and not batch_informado:
        raise _UsoError("fixed_batch requiere --batch-size")
    if strategy == STRATEGY_TYPE_INDIVIDUAL and batch_informado:
        raise _UsoError("individual no admite --batch-size")
    return _Opciones(
        strategy=strategy,
        batch_size=batch_size,
        events=events,
        recovery=recovery,
        fault=fault,
        as_json=as_json,
        show_trace=show_trace,
        scientific_summary=scientific_summary,
    )


def _valor(tokens: list[str], index: int, flag: str) -> tuple[str, int]:
    token = tokens[index]
    prefijo = flag + "="
    if token.startswith(prefijo):
        valor = token[len(prefijo) :]
        if valor == "":
            raise _UsoError(f"falta el valor de {flag}")
        return valor, index
    if index + 1 >= len(tokens):
        raise _UsoError(f"falta el valor de {flag}")
    return tokens[index + 1], index + 1


def _entero(valor: str, flag: str) -> int:
    try:
        return int(valor)
    except ValueError:
        raise _UsoError(f"el valor de {flag} debe ser un entero") from None


def _emitir(result: RunResult, opciones: _Opciones) -> None:
    if opciones.as_json:
        print(
            summary_json(
                result,
                include_trace=opciones.show_trace,
                include_scientific=opciones.scientific_summary,
            )
        )
        return
    print(format_summary(result))
    if opciones.scientific_summary:
        print()
        print(format_scientific_summary(result))
    if opciones.show_trace:
        print()
        print(format_trace(result))
