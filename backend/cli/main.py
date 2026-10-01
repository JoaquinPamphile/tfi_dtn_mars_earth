"""Consola mínima para ejecutar la demostración local del motor.

La ejecución vive en ``runner``. Este módulo solo interpreta argumentos
y presenta el resultado.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from core.simulation.engine import SimulationStatus
from core.sync.strategy import (
    STRATEGY_TYPE_FIXED_BATCH,
    STRATEGY_TYPE_INDIVIDUAL,
    InvalidSyncStrategyConfigError,
    UnknownSyncStrategyError,
)
from runner import execute_run
from runner.config import RECOVERY_MODES
from runner.demo import DEMO_DEFAULT_EVENTS, FAULT_MODES, FAULT_NONE, demo_run_config
from runner.result import RunResult

from cli.present import format_scientific_summary, format_summary, format_trace, summary_json

AYUDA = """\
Uso: python -m cli run [opciones]

Ejecuta una corrida headless de demostración del motor.
No es un experimento científico ni usa un escenario Alessi.

Opciones:
  --strategy {individual,fixed_batch}   Estrategia. Por defecto: individual.
  --batch-size N                        Tamaño de lote. Obligatorio en fixed_batch.
  --events N                            Eventos a generar. Por defecto: 10.
  --recovery {none,sender-driven,receiver-driven}
                                        Recuperación. Por defecto: none.
                                        sender-driven reintenta por timeout de ACK.
                                        receiver-driven pide los huecos que Tierra observa.
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
