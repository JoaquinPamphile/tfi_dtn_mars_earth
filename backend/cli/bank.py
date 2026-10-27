"""Manejo de los comandos del banco configurable.

``inspect-e1``, ``inspect-e2`` e ``inspect-e3`` preparan una campaña y no
la ejecutan. ``run-e1`` ejecuta una campaña E1 configurable y muestra cada
corrida en consola, sin exportar evidencia. ``run-e2`` hace lo mismo con
una campaña E2 configurable: no la evalúa ni exporta evidencia.
``run-e3`` ejecuta una campaña E3 configurable y muestra cada corrida.
No la evalúa y no clasifica comparabilidad. Con ``--output``, cada
ejecución guarda su resultado autocontenido. No despacha otros comandos.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.simulation.engine import SimulationStatus
from experiments.campaign import CampaignResult, execute_campaign
from experiments.experiment_bank_interpretation import assess_e1_bank_comparison
from experiments.experiment_bank_result import (
    build_e1_bank_result,
    build_e2_bank_result,
    build_e3_bank_result,
    write_e1_bank_result,
    write_e2_bank_result,
    write_e3_bank_result,
)
from experiments.experiment_campaign_loader import (
    load_e1_campaign,
    load_e2_campaign,
    load_e3_campaign,
)

from cli.arguments import ErrorDeUso, valor_opcion
from cli.present import (
    format_configurable_e1_campaign,
    format_configurable_e2_campaign,
    format_configurable_e3_campaign,
    format_e1_bank_comparison,
    format_e1_campaign_inspection,
    format_e2_campaign_inspection,
    format_e3_campaign_inspection,
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


def comando_inspect_e2(tokens: list[str], *, ayuda: str) -> int:
    """Prepara una campaña E2 y muestra el resumen. No ejecuta el motor."""
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        config_path = _ruta_de_config(tokens, comando="inspect-e2")
    except ErrorDeUso as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        resuelta = load_e2_campaign(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(format_e2_campaign_inspection(resuelta))
    return 0


def comando_inspect_e3(tokens: list[str], *, ayuda: str) -> int:
    """Prepara una campaña E3 y muestra el resumen. No ejecuta el motor."""
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        config_path = _ruta_de_config(tokens, comando="inspect-e3")
    except ErrorDeUso as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        resuelta = load_e3_campaign(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(format_e3_campaign_inspection(resuelta))
    return 0


def comando_run_e1(tokens: list[str], *, ayuda: str) -> int:
    """Carga una campaña E1, la ejecuta y muestra cada corrida."""
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        config_path, output_path = _opciones_de_campana(tokens, comando="run-e1")
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
    if output_path is not None and not _publicar_resultado(
        build_e1_bank_result,
        write_e1_bank_result,
        resuelta,
        resultado,
        output_path,
    ):
        return 1
    return 0 if _todas_las_corridas_completaron(resultado) else 1


def comando_run_e2(tokens: list[str], *, ayuda: str) -> int:
    """Carga una campaña E2, la ejecuta una vez y muestra cada corrida.

    Con ``--output`` guarda el documento ya construido. No evalúa la
    campaña, no compara cargas y no exporta evidencia.
    """
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        config_path, output_path = _opciones_de_campana(tokens, comando="run-e2")
    except ErrorDeUso as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        resuelta = load_e2_campaign(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    resultado = execute_campaign(resuelta.campaign)
    print(format_configurable_e2_campaign(resuelta, resultado))
    fallos = _resumen_de_fallos(resultado)
    if fallos:
        print(fallos, file=sys.stderr)
    if output_path is not None and not _publicar_resultado(
        build_e2_bank_result,
        write_e2_bank_result,
        resuelta,
        resultado,
        output_path,
    ):
        return 1
    return 0 if _todas_las_corridas_completaron(resultado) else 1


def comando_run_e3(tokens: list[str], *, ayuda: str) -> int:
    """Carga una campaña E3, la ejecuta una vez y muestra cada corrida.

    Con ``--output`` guarda el documento ya construido. No evalúa la
    campaña, no clasifica comparabilidad y no exporta evidencia. El
    parseo termina antes de cargar o ejecutar.
    """
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        config_path, output_path = _opciones_de_campana(tokens, comando="run-e3")
    except ErrorDeUso as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        resuelta = load_e3_campaign(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    resultado = execute_campaign(resuelta.campaign)
    print(format_configurable_e3_campaign(resuelta, resultado))
    fallos = _resumen_de_fallos(resultado)
    if fallos:
        print(fallos, file=sys.stderr)
    if output_path is not None and not _publicar_resultado(
        build_e3_bank_result,
        write_e3_bank_result,
        resuelta,
        resultado,
        output_path,
    ):
        return 1
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


def _opciones_de_campana(tokens: list[str], *, comando: str) -> tuple[str, str | None]:
    """Lee ``--config`` y el ``--output`` opcional sin abrir ninguna ruta."""
    config_path: str | None = None
    output_path: str | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        option = token.split("=", 1)[0]
        if option in _OPCIONES_DE_EJECUCION and option != "--output":
            raise ErrorDeUso(_opcion_no_admitida(comando, option))
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
                raise ErrorDeUso(_opcion_no_admitida(comando, next_option))
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
            raise ErrorDeUso(_opcion_no_admitida(comando, value_option))
        if value.startswith("-"):
            raise ErrorDeUso(f"argumento no reconocido: {value}")
        if option == "--config":
            config_path = value
        else:
            output_path = value
        index += 1
    if config_path is None:
        raise ErrorDeUso(f"{comando} requiere --config")
    return config_path, output_path


def _publicar_resultado(
    construir: Callable[..., dict[str, Any]],
    escribir: Callable[..., Path],
    resuelta: object,
    resultado: CampaignResult,
    output_path: str,
) -> bool:
    """Construye y escribe una sola vez, después de imprimir el informe.

    La ruta se usa tal como llegó. Una ruta relativa queda respecto del
    directorio de trabajo. Solo captura errores de construcción y de
    publicación.
    """
    try:
        document = construir(resuelta, resultado)
        written = escribir(Path(output_path), document)
    except (OSError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return False
    print(f"Resultado guardado: {written}", file=sys.stderr)
    return True


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
