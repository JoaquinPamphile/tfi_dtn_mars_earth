"""Consola mínima para ejecutar la demostración local del motor.

La ejecución vive en ``runner``. Este módulo solo interpreta argumentos
y presenta el resultado.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass

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
from experiments.execute import execute_scientific_run
from experiments.report import format_campaign, format_scientific_run
from runner import execute_run
from runner.config import RECOVERY_MODES
from runner.demo import DEMO_DEFAULT_EVENTS, FAULT_MODES, FAULT_NONE, demo_run_config
from runner.result import RunResult

from cli.present import format_scientific_summary, format_summary, format_trace, summary_json

AYUDA = """\
Uso:
  python -m cli run [opciones]
  python -m cli scientific-run
  python -m cli scientific-campaign
  python -m cli e1 [--json]
  python -m cli e2 [--json]
  python -m cli e3 [--json]
  python -m cli e3-sensitivity [--json]

run ejecuta una corrida headless de demostración del motor.
No es un experimento científico ni usa un escenario Alessi.

scientific-run ejecuta la corrida controlada local por defecto.
Es una sola corrida, con escenario y workload explícitos.

scientific-campaign ejecuta la campaña controlada de desarrollo.
Son dos corridas en orden, con el mismo escenario, el mismo workload
y la misma semilla. No es evidencia científica.

e1 ejecuta E1 — Granularidad de sincronización.
Son cuatro corridas, en el orden oficial: individual, lote fijo 10,
lote fijo 25 y lote fijo 50. --json imprime la comparación estructurada.
No escribe archivos.

e2 ejecuta E2 — Efecto de la carga ofrecida.
Son doce corridas: seis fracciones de carga y, en cada una, Individual
y lote fijo 25. --json imprime la vista estructurada.
No escribe archivos.

e3 ejecuta E3 — Comparación controlada de recovery.
Son cuatro celdas: sender-driven y receiver-driven, cada una sin pérdida
y con la misma pérdida silenciosa. --json imprime la vista estructurada.
No escribe archivos. No declara una política ganadora.

e3-sensitivity ejecuta el análisis de sensibilidad de E3 a la posición
de la pérdida. No constituye un experimento E4. No escribe archivos.

Opciones:
  --strategy {individual,fixed_batch}   Estrategia. Por defecto: individual.
  --batch-size N                        Tamaño de lote. Obligatorio en fixed_batch.
  --events N                            Eventos a generar. Por defecto: 10.
  --recovery {none,sender-driven,receiver-driven}
                                        Recuperación. Por defecto: none.
                                        none no programa timeout de ACK ni GapRequest.
                                        sender-driven reintenta por timeout de ACK
                                        y no pide huecos.
                                        receiver-driven pide los huecos que Tierra observa
                                        y no reintenta por timeout de ACK.
  --fault silent-loss                   Pierde en silencio la secuencia intermedia 1,
                                        intento 1, hop RELAY_TO_EARTH.
                                        Exige al menos 3 eventos y la estrategia individual.
                                        Sigue siendo una demostración local.
  --json                                Resumen operativo en JSON.
  --show-trace                          Traza: tiempo, índice, tipo y entidad.
  --scientific-summary                  Métricas científicas de esta corrida.
                                        Con --json se agregan al objeto.
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
    if argumentos[0] == "scientific-run":
        return _comando_scientific(argumentos[1:])
    if argumentos[0] == "scientific-campaign":
        return _comando_campaign(argumentos[1:])
    if argumentos[0] == "e1":
        return _comando_e1(argumentos[1:])
    if argumentos[0] == "e2":
        return _comando_e2(argumentos[1:])
    if argumentos[0] == "e3":
        return _comando_e3(argumentos[1:])
    if argumentos[0] == "e3-sensitivity":
        return _comando_e3_sensitivity(argumentos[1:])
    if argumentos[0] != "run":
        print(f"comando desconocido: {argumentos[0]}", file=sys.stderr)
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


def _comando_e2(tokens: list[str]) -> int:
    """Ejecuta el diseño oficial de E2. No escribe archivos."""
    if tokens in (["-h"], ["--help"]):
        print(AYUDA, end="")
        return 0
    if tokens not in ([], ["--json"]):
        print("e2 solo admite --json", file=sys.stderr)
        return 2
    spec = build_e2_campaign()
    started = time.perf_counter()
    campaign = execute_campaign(spec)
    elapsed = time.perf_counter() - started
    try:
        result = e2_result(spec, campaign, wall_execution_seconds=elapsed)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if tokens == ["--json"]:
        print(e2_result_json(result))
    else:
        print(format_e2(result))
    return 0


def _comando_e3(tokens: list[str]) -> int:
    """Ejecuta el diseño oficial de E3. No escribe archivos."""
    if tokens in (["-h"], ["--help"]):
        print(AYUDA, end="")
        return 0
    if tokens not in ([], ["--json"]):
        print("e3 solo admite --json", file=sys.stderr)
        return 2
    spec = build_e3_campaign()
    started = time.perf_counter()
    campaign = execute_campaign(spec)
    elapsed = time.perf_counter() - started
    try:
        result = e3_result(spec, campaign, wall_execution_seconds=elapsed)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if tokens == ["--json"]:
        print(e3_result_json(result))
    else:
        print(format_e3(result))
    return 0


def _comando_e3_sensitivity(tokens: list[str]) -> int:
    """Ejecuta la sensibilidad de E3. No toca la campaña oficial."""
    if tokens in (["-h"], ["--help"]):
        print(AYUDA, end="")
        return 0
    if tokens not in ([], ["--json"]):
        print("e3-sensitivity solo admite --json", file=sys.stderr)
        return 2
    spec = build_e3_sensitivity_campaign()
    started = time.perf_counter()
    campaign = execute_campaign(spec)
    elapsed = time.perf_counter() - started
    try:
        result = e3_sensitivity_result(spec, campaign, wall_execution_seconds=elapsed)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if tokens == ["--json"]:
        print(e3_sensitivity_json(result))
    else:
        print(format_e3_sensitivity(result))
    return 0


def _comando_e1(tokens: list[str]) -> int:
    """Ejecuta el diseño oficial de E1. No reemplaza los otros comandos."""
    if tokens in (["-h"], ["--help"]):
        print(AYUDA, end="")
        return 0
    if tokens not in ([], ["--json"]):
        print("e1 solo admite --json", file=sys.stderr)
        return 2
    spec = build_e1_campaign()
    started = time.perf_counter()
    campaign = execute_campaign(spec)
    elapsed = time.perf_counter() - started
    try:
        result = e1_result(spec, campaign, wall_execution_seconds=elapsed)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if tokens == ["--json"]:
        print(e1_result_json(result))
    else:
        print(format_e1(result))
    return 0


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
        if token in {"-h", "--help"}:
            raise _AyudaPedida()
        if token == "--json":
            as_json = True
        elif token == "--show-trace":
            show_trace = True
        elif token == "--scientific-summary":
            scientific_summary = True
        elif token == "--strategy" or token.startswith("--strategy="):
            valor, index = _valor(tokens, index, "--strategy")
            if valor not in _ESTRATEGIAS:
                admitidas = ", ".join(_ESTRATEGIAS)
                raise _UsoError(
                    f"estrategia no admitida: {valor}. Admitidas: {admitidas}."
                )
            strategy = valor
        elif token == "--batch-size" or token.startswith("--batch-size="):
            valor, index = _valor(tokens, index, "--batch-size")
            batch_size = _entero(valor, "--batch-size")
            batch_informado = True
        elif token == "--events" or token.startswith("--events="):
            valor, index = _valor(tokens, index, "--events")
            events = _entero(valor, "--events")
        elif token == "--recovery" or token.startswith("--recovery="):
            valor, index = _valor(tokens, index, "--recovery")
            if valor not in RECOVERY_MODES:
                admitidas = ", ".join(RECOVERY_MODES)
                raise _UsoError(
                    f"recuperación no admitida: {valor}. Admitidas: {admitidas}."
                )
            recovery = valor
        elif token == "--fault" or token.startswith("--fault="):
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
