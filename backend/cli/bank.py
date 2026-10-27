from __future__ import annotations
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.simulation.engine import SimulationStatus
from experiments.campaign import CampaignResult, execute_campaign
from experiments.experiment_bank import (
    ResolvedE1Campaign,
    ResolvedE2Campaign,
    ResolvedE3Campaign,
)
from experiments.experiment_bank_interpretation import assess_e1_bank_comparison
from experiments.experiment_bank_result import (
    build_e1_bank_result,
    build_e2_bank_result,
    build_e3_bank_result,
    write_e1_bank_result,
    write_e2_bank_result,
    write_e3_bank_result,
)
from experiments.experiment_campaign_loader import load_bank_campaign
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

def comando_inspect(tokens: list[str], *, ayuda: str) -> int:
    """Prepara la campaña declarada y muestra su resumen. No ejecuta el motor."""
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        config_path = _ruta_de_config(tokens, comando="inspect")
    except ErrorDeUso as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        resuelta = load_bank_campaign(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if isinstance(resuelta, ResolvedE1Campaign):
        print(format_e1_campaign_inspection(resuelta))
    elif isinstance(resuelta, ResolvedE2Campaign):
        print(format_e2_campaign_inspection(resuelta))
    elif isinstance(resuelta, ResolvedE3Campaign):
        print(format_e3_campaign_inspection(resuelta))
    else:
        raise TypeError(
            "la campaña resuelta no es E1, E2 ni E3: "
            f"{type(resuelta).__name__}"
        )
    return 0


def comando_run(tokens: list[str], *, ayuda: str) -> int:
    """Carga la campaña declarada, la ejecuta una vez y muestra cada corrida.
    sin ``--output`` no construye ni escribe el documento.
    """
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        config_path, output_path = opciones_de_campana(tokens, comando="run")
    except ErrorDeUso as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        resuelta = load_bank_campaign(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    resultado = execute_campaign(resuelta.campaign)
    if isinstance(resuelta, ResolvedE1Campaign):
        comparabilidad = assess_e1_bank_comparison(resuelta, resultado)
        print(format_configurable_e1_campaign(resultado))
        print()
        print(format_e1_bank_comparison(comparabilidad))
        construir, escribir = build_e1_bank_result, write_e1_bank_result
    elif isinstance(resuelta, ResolvedE2Campaign):
        print(format_configurable_e2_campaign(resuelta, resultado))
        construir, escribir = build_e2_bank_result, write_e2_bank_result
    elif isinstance(resuelta, ResolvedE3Campaign):
        print(format_configurable_e3_campaign(resuelta, resultado))
        construir, escribir = build_e3_bank_result, write_e3_bank_result
    else:
        raise TypeError(
            "la campaña resuelta no es E1, E2 ni E3: "
            f"{type(resuelta).__name__}"
        )
    fallos = resumen_de_fallos(resultado)
    if fallos:
        print(fallos, file=sys.stderr)
    if output_path is not None and not publicar_resultado(
        construir,
        escribir,
        resuelta,
        resultado,
        output_path,
    ):
        return 1
    return 0 if todas_las_corridas_completaron(resultado) else 1

OPCIONES_DE_EJECUCION = frozenset(
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
        if opcion in OPCIONES_DE_EJECUCION:
            raise ErrorDeUso(opcion_no_admitida(comando, opcion))
        if opcion != "--config":
            raise ErrorDeUso(f"argumento no reconocido: {token}")
        if ruta is not None:
            raise ErrorDeUso("--config está repetido")
        if not token.startswith("--config="):
            if index + 1 < len(tokens):
                siguiente = tokens[index + 1].split("=", 1)[0]
                if siguiente in OPCIONES_DE_EJECUCION:
                    raise ErrorDeUso(opcion_no_admitida(comando, siguiente))
            if index + 1 >= len(tokens) or tokens[index + 1].startswith("-"):
                raise ErrorDeUso("falta el valor de --config")
        valor, index = valor_opcion(tokens, index, "--config")
        if valor.strip() == "":
            raise ErrorDeUso("la ruta de --config no debe estar vacía")
        opcion_valor = valor.split("=", 1)[0]
        if opcion_valor in OPCIONES_DE_EJECUCION:
            raise ErrorDeUso(opcion_no_admitida(comando, opcion_valor))
        if valor.startswith("-"):
            raise ErrorDeUso(f"argumento no reconocido: {valor}")
        ruta = valor
        index += 1
    if ruta is None:
        raise ErrorDeUso(f"{comando} requiere --config")
    return ruta

def opciones_de_campana(tokens: list[str], *, comando: str) -> tuple[str, str | None]:
    config_path: str | None = None
    output_path: str | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        option = token.split("=", 1)[0]
        if option in OPCIONES_DE_EJECUCION and option != "--output":
            raise ErrorDeUso(opcion_no_admitida(comando, option))
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
                next_option in OPCIONES_DE_EJECUCION
                and next_option != "--output"
            ):
                raise ErrorDeUso(opcion_no_admitida(comando, next_option))
            if next_token.startswith("-"):
                raise ErrorDeUso(f"falta el valor de {option}")
        value, index = valor_opcion(tokens, index, option)
        if value.strip() == "":
            raise ErrorDeUso(f"la ruta de {option} no debe estar vacía")
        value_option = value.split("=", 1)[0]
        if (
            value_option in OPCIONES_DE_EJECUCION
            and value_option != "--output"
        ):
            raise ErrorDeUso(opcion_no_admitida(comando, value_option))
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


def publicar_resultado(
    construir: Callable[..., dict[str, Any]],
    escribir: Callable[..., Path],
    resuelta: object,
    resultado: CampaignResult,
    output_path: str,
) -> bool:
    """
    Escritura de los resultados en el archivo especificado en --output
    """
    try:
        document = construir(resuelta, resultado)
        written = escribir(Path(output_path), document)
    except (OSError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return False
    print(f"Resultado guardado: {written}", file=sys.stderr)
    return True


def opcion_no_admitida(comando: str, opcion: str) -> str:
    return (
        f"{comando} no admite opciones de ejecución ni de exportación: {opcion}"
    )


def resumen_de_fallos(resultado: CampaignResult) -> str:
    lineas: list[str] = []
    for run in resultado.runs:
        if run.result is None:
            lineas.append(f"{run.label}: {run.error_type}: {run.error_message}")
            continue
        if run.result.engine_status != SimulationStatus.COMPLETED.value:
            lineas.append(f"{run.label}: estado {run.result.engine_status}")
    return "\n".join(lineas)


def todas_las_corridas_completaron(resultado: CampaignResult) -> bool:
    return all(
        run.result is not None
        and run.result.engine_status == SimulationStatus.COMPLETED.value
        for run in resultado.runs
    )
