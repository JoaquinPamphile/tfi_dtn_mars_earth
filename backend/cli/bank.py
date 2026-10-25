"""Manejo de los comandos del banco configurable ``inspect-e1`` y ``run-e1``.

``inspect-e1`` prepara una campaña y no la ejecuta. ``run-e1`` ejecuta
una campaña E1 configurable y muestra cada corrida en consola, sin
exportar evidencia. No despacha otros comandos.
"""

from __future__ import annotations

import sys

from core.simulation.engine import SimulationStatus
from experiments.campaign import CampaignResult, execute_campaign
from experiments.experiment_campaign_loader import load_e1_campaign

from cli.arguments import ErrorDeUso, valor_opcion
from cli.present import (
    format_configurable_e1_campaign,
    format_e1_campaign_inspection,
)


def comando_inspect_e1(tokens: list[str], *, ayuda: str) -> int:
    """Prepara una campaña E1 y muestra el resumen. No ejecuta el motor."""
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        config_path = _ruta_de_config(tokens, comando="inspect-e1")
    except ErrorDeUso as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        resuelta = load_e1_campaign(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(format_e1_campaign_inspection(resuelta))
    return 0


def comando_run_e1(tokens: list[str], *, ayuda: str) -> int:
    """Carga una campaña E1, la ejecuta y muestra cada corrida."""
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        config_path = _ruta_de_config(tokens, comando="run-e1")
    except ErrorDeUso as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        resuelta = load_e1_campaign(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    resultado = execute_campaign(resuelta.campaign)
    print(format_configurable_e1_campaign(resultado))
    fallos = _resumen_de_fallos(resultado)
    if fallos:
        print(fallos, file=sys.stderr)
    if _todas_las_corridas_completaron(resultado):
        return 0
    return 1


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


def _ruta_de_config(tokens: list[str], *, comando: str) -> str:
    """Devuelve la ruta de --config. No abre el archivo."""
    ruta: str | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        opcion = token.split("=", 1)[0]
        if opcion in _OPCIONES_DE_EJECUCION:
            raise ErrorDeUso(_opcion_no_admitida(comando, opcion))
        if opcion != "--config":
            raise ErrorDeUso(f"argumento no reconocido: {token}")
        if ruta is not None:
            raise ErrorDeUso("--config está repetido")
        if not token.startswith("--config="):
            if index + 1 < len(tokens):
                siguiente = tokens[index + 1].split("=", 1)[0]
                if siguiente in _OPCIONES_DE_EJECUCION:
                    raise ErrorDeUso(_opcion_no_admitida(comando, siguiente))
            if index + 1 >= len(tokens) or tokens[index + 1].startswith("-"):
                raise ErrorDeUso("falta el valor de --config")
        valor, index = valor_opcion(tokens, index, "--config")
        if valor.strip() == "":
            raise ErrorDeUso("la ruta de --config no debe estar vacía")
        opcion_valor = valor.split("=", 1)[0]
        if opcion_valor in _OPCIONES_DE_EJECUCION:
            raise ErrorDeUso(_opcion_no_admitida(comando, opcion_valor))
        if valor.startswith("-"):
            raise ErrorDeUso(f"argumento no reconocido: {valor}")
        ruta = valor
        index += 1
    if ruta is None:
        raise ErrorDeUso(f"{comando} requiere --config")
    return ruta


def _opcion_no_admitida(comando: str, opcion: str) -> str:
    return (
        f"{comando} no admite opciones de ejecución ni de exportación: {opcion}"
    )


def _resumen_de_fallos(resultado: CampaignResult) -> str:
    """Etiqueta y causa de cada corrida que no terminó COMPLETED."""
    lineas: list[str] = []
    for run in resultado.runs:
        if run.result is None:
            lineas.append(f"{run.label}: {run.error_type}: {run.error_message}")
            continue
        if run.result.engine_status != SimulationStatus.COMPLETED.value:
            lineas.append(f"{run.label}: estado {run.result.engine_status}")
    return "\n".join(lineas)


def _todas_las_corridas_completaron(resultado: CampaignResult) -> bool:
    """Cada corrida tiene resultado y el motor quedó en COMPLETED.

    No consulta ``status`` ni ``completed_count``. Un motor COMPLETED
    con backlog o sin convergencia sigue siendo una ejecución terminada.
    """
    return all(
        run.result is not None
        and run.result.engine_status == SimulationStatus.COMPLETED.value
        for run in resultado.runs
    )
