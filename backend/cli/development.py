"""Manejo de los comandos de desarrollo ``run``, ``scientific-run`` y ``scientific-campaign``.

Cada comando reconoce sus argumentos, ejecuta su corrida y presenta el
resultado. ``run`` es la demostración local. Los otros dos usan
especificaciones controladas. No despacha otros comandos.
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
from experiments.campaign import execute_campaign
from experiments.controlled import (
    controlled_development_campaign,
    controlled_local_run_spec,
)
from experiments.execute import execute_scientific_run
from experiments.report import format_campaign, format_scientific_run
from runner import execute_run
from runner.config import RECOVERY_MODES
from runner.demo import DEMO_DEFAULT_EVENTS, FAULT_MODES, FAULT_NONE, demo_run_config
from runner.result import RunResult

from cli.arguments import ErrorDeUso, valor_opcion
from cli.present import (
    format_scientific_summary,
    format_summary,
    format_trace,
    summary_json,
)

_ESTRATEGIAS = (STRATEGY_TYPE_INDIVIDUAL, STRATEGY_TYPE_FIXED_BATCH)


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


def comando_scientific_run(tokens: list[str], *, ayuda: str) -> int:
    """Ejecuta la especificación controlada local. No acepta una campaña."""
    if tokens:
        if tokens == ["-h"] or tokens == ["--help"]:
            print(ayuda, end="")
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


def comando_scientific_campaign(tokens: list[str], *, ayuda: str) -> int:
    """Ejecuta la campaña controlada de desarrollo. No acepta una grilla."""
    if tokens:
        if tokens == ["-h"] or tokens == ["--help"]:
            print(ayuda, end="")
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


def comando_run(tokens: list[str], *, ayuda: str) -> int:
    """Ejecuta la demostración local. No acepta una campaña."""
    try:
        opciones = _parse_opciones(tokens)
    except _AyudaPedida:
        print(ayuda, end="")
        return 0
    except ErrorDeUso as exc:
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
            valor, index = valor_opcion(tokens, index, "--strategy")
            if valor not in _ESTRATEGIAS:
                admitidas = ", ".join(_ESTRATEGIAS)
                raise ErrorDeUso(
                    f"estrategia no admitida: {valor}. Admitidas: {admitidas}."
                )
            strategy = valor
        elif opcion == "--batch-size":
            valor, index = valor_opcion(tokens, index, "--batch-size")
            batch_size = _entero(valor, "--batch-size")
            batch_informado = True
        elif opcion == "--events":
            valor, index = valor_opcion(tokens, index, "--events")
            events = _entero(valor, "--events")
        elif opcion == "--recovery":
            valor, index = valor_opcion(tokens, index, "--recovery")
            if valor not in RECOVERY_MODES:
                admitidas = ", ".join(RECOVERY_MODES)
                raise ErrorDeUso(
                    f"recuperación no admitida: {valor}. Admitidas: {admitidas}."
                )
            recovery = valor
        elif opcion == "--fault":
            valor, index = valor_opcion(tokens, index, "--fault")
            if valor not in FAULT_MODES or valor == FAULT_NONE:
                raise ErrorDeUso(
                    f"falla no admitida: {valor}. Admitida: silent-loss."
                )
            fault = valor
        else:
            raise ErrorDeUso(f"argumento no reconocido: {token}")
        index += 1
    if events < 1:
        raise ErrorDeUso("la cantidad de eventos debe ser al menos 1")
    if strategy == STRATEGY_TYPE_FIXED_BATCH and not batch_informado:
        raise ErrorDeUso("fixed_batch requiere --batch-size")
    if strategy == STRATEGY_TYPE_INDIVIDUAL and batch_informado:
        raise ErrorDeUso("individual no admite --batch-size")
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


def _entero(valor: str, flag: str) -> int:
    try:
        return int(valor)
    except ValueError:
        raise ErrorDeUso(f"el valor de {flag} debe ser un entero") from None


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
