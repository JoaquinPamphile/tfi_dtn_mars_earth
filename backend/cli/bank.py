"""Manejo de los comandos del banco configurable ``inspect-e1`` y ``run-e1``.

``inspect-e1`` prepara una campaña y no la ejecuta. ``run-e1`` ejecuta
una campaña E1 configurable y muestra cada corrida en consola, sin
exportar evidencia. No despacha otros comandos.
"""

from __future__ import annotations

import sys
from pathlib import Path

from core.simulation.engine import SimulationStatus
from experiments.campaign import CampaignResult, execute_campaign
from experiments.experiment_bank_interpretation import assess_e1_bank_comparison
from experiments.experiment_bank_result import (
    build_e1_bank_result,
    write_e1_bank_result,
)
from experiments.experiment_campaign_loader import load_e1_campaign

from cli.arguments import ErrorDeUso, valor_opcion
from cli.present import (
    format_configurable_e1_campaign,
    format_e1_bank_comparison,
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
        config_path, output_path = _opciones_run_e1(tokens)
    except ErrorDeUso as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        resuelta = load_e1_campaign(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    resultado = execute_campaign(resuelta.campaign)
    comparabilidad = assess_e1_bank_comparison(resuelta, resultado)
    print(format_configurable_e1_campaign(resultado))
    print()
    print(format_e1_bank_comparison(comparabilidad))
    fallos = _resumen_de_fallos(resultado)
    if fallos:
        print(fallos, file=sys.stderr)
    if output_path is not None:
        try:
            document = build_e1_bank_result(resuelta, resultado)
            written = write_e1_bank_result(Path(output_path), document)
        except (OSError, TypeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Resultado guardado: {written}", file=sys.stderr)
    return 0 if _todas_las_corridas_completaron(resultado) else 1


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
        "--output",
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


def _opciones_run_e1(tokens: list[str]) -> tuple[str, str | None]:
    """Lee las dos opciones de ``run-e1`` sin abrir ninguna ruta."""
    config_path: str | None = None
    output_path: str | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        option = token.split("=", 1)[0]
        if option in _OPCIONES_DE_EJECUCION and option != "--output":
            raise ErrorDeUso(_opcion_no_admitida("run-e1", option))
        if option not in {"--config", "--output"}:
            raise ErrorDeUso(f"argumento no reconocido: {token}")
        if option == "--config" and config_path is not None:
            raise ErrorDeUso("--config está repetido")
        if option == "--output" and output_path is not None:
            raise ErrorDeUso("--output está repetido")
        if not token.startswith(option + "=") and index + 1 < len(tokens):
            next_token = tokens[index + 1]
            next_option = next_token.split("=", 1)[0]
            if (
                next_option in _OPCIONES_DE_EJECUCION
                and next_option != "--output"
            ):
                raise ErrorDeUso(_opcion_no_admitida("run-e1", next_option))
            if next_token.startswith("-"):
                raise ErrorDeUso(f"falta el valor de {option}")
        value, index = valor_opcion(tokens, index, option)
        if value.strip() == "":
            raise ErrorDeUso(f"la ruta de {option} no debe estar vacía")
        value_option = value.split("=", 1)[0]
        if (
            value_option in _OPCIONES_DE_EJECUCION
            and value_option != "--output"
        ):
            raise ErrorDeUso(_opcion_no_admitida("run-e1", value_option))
        if value.startswith("-"):
            raise ErrorDeUso(f"argumento no reconocido: {value}")
        if option == "--config":
            config_path = value
        else:
            output_path = value
        index += 1
    if config_path is None:
        raise ErrorDeUso("run-e1 requiere --config")
    return config_path, output_path


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
