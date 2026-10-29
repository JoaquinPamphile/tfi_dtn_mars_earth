from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.simulation.engine import SimulationStatus
from experiments.campaign import CampaignResult, execute_campaign
from experiments.experiment_bank import (
    ResolvedCampaign,
    ResolvedE1Campaign,
    ResolvedE2Campaign,
    ResolvedE3Campaign,
    ResolvedE3SensitivityCampaign,
)
from experiments.experiment_bank_interpretation import assess_e1_bank_comparison
from experiments.experiment_bank_result import (
    build_e1_bank_result,
    build_e2_bank_result,
    build_e3_bank_result,
    build_e3_sensitivity_bank_result,
    write_e1_bank_result,
    write_e2_bank_result,
    write_e3_bank_result,
    write_e3_sensitivity_bank_result,
)
from experiments.experiment_campaign_loader import load_declared_configuration
from experiments.experiment_suite import (
    PUBLICATION_FAILED,
    PUBLICATION_NOT_REQUESTED,
    PUBLICATION_PUBLISHED,
    ResolvedSuite,
    ResolvedSuiteEntry,
    SuiteSummaryEntry,
    build_suite_summary,
    write_suite_summary,
)
from cli.arguments import valor_opcion, error_de_uso
from cli.present import (
    format_campaign_inspection,
    format_configurable_e1_campaign,
    format_configurable_e2_campaign,
    format_configurable_e3_campaign,
    format_configurable_e3_sensitivity_campaign,
    format_e1_bank_comparison,
    format_suite_execution_summary,
    format_suite_inspection,
)


def comando_banco(tokens: list[str], *, ayuda: str, comando: str) -> int:
    """Inspecciona o ejecuta la campaña o la suite declarada."""
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        rutas = rutas_de_opciones(tokens, comando=comando)
        config_path = rutas["--config"]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        declarado = load_declared_configuration(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if comando == "inspect":
        if isinstance(declarado, ResolvedSuite):
            print(format_suite_inspection(declarado))
        else:
            print(format_campaign_inspection(declarado))
        return 0
    output_path = rutas.get("--output")
    if isinstance(declarado, ResolvedSuite):
        return ejecutar_suite(declarado, output_path)
    return codigo_de_salida(procesar_campana_resuelta(declarado, output_path))

def ejecutar_suite(suite: ResolvedSuite, output_path: str | None) -> int:
    """
    Distribuye la ejecuón de las campañas en orden y luego invoca la contrucción del resumen de los resultados. 
    """
    directorio: Path | None = None
    if output_path is not None:
        try:
            directorio = crear_directorio_exclusivo(Path(output_path))
        except OSError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    registros: list[SuiteSummaryEntry] = []
    for entrada in suite.entries:
        destino = None
        if directorio is not None:
            destino = str(directorio / f"{entrada.experiment_id}.json")
        procesada = procesar_campana_resuelta(entrada.resolved, destino)
        registros.append(_entrada_de_resumen(entrada, procesada))
        del procesada
    if directorio is None:
        print(format_suite_execution_summary(suite.document.suite_id, registros))
        return codigo_de_salida(*registros)
    document = build_suite_summary(suite.document, registros)
    try:
        written = write_suite_summary(directorio / "suite-summary.json", document)
    except (OSError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        del document
    print(f"Resumen de suite guardado: {written}", file=sys.stderr)
    return codigo_de_salida(*registros)


def procesar_campana_resuelta(
    resuelta: ResolvedCampaign,
    output_path: str | None,
) -> "ProcessedCampaign":
    """Ejecuta una campaña ya resuelta, la presenta y, si hay ruta, la publica.

    El ``CampaignResult`` y el documento construido no salen de esta
    función. La suite llama una vez por entrada y descarta el regreso
    antes de la campaña siguiente.
    """
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
    elif isinstance(resuelta, ResolvedE3SensitivityCampaign):
        print(format_configurable_e3_sensitivity_campaign(resuelta, resultado))
        construir, escribir = (
            build_e3_sensitivity_bank_result,
            write_e3_sensitivity_bank_result,
        )
    else:
        raise TypeError(
            "la campaña resuelta no es E1, E2, E3 ni sensibilidad de E3: "
            f"{type(resuelta).__name__}"
        )
    fallos = resumen_de_fallos(resultado)
    if fallos:
        print(fallos, file=sys.stderr)
    publication_status = PUBLICATION_NOT_REQUESTED
    publication_error: str | None = None
    if output_path is not None:
        publication_error = publicar_resultado(
            construir,
            escribir,
            resuelta,
            resultado,
            output_path,
        )
        publication_status = (
            PUBLICATION_FAILED
            if publication_error is not None
            else PUBLICATION_PUBLISHED
        )
    procesada = ProcessedCampaign(
        campaign_id=resultado.campaign_id,
        campaign_identity=resultado.campaign_identity,
        campaign_status=resultado.status,
        run_count=resultado.run_count,
        completed_run_count=resultado.completed_count,
        failed_run_count=resultado.failed_count,
        all_runs_engine_completed=todas_las_corridas_completaron(resultado),
        publication_status=publication_status,
        publication_error=publication_error,
    )
    del resultado
    return procesada


@dataclass(frozen=True, slots=True)
class ProcessedCampaign:
    """Hechos que sobreviven al resultado de una campaña. Sin eventos."""

    campaign_id: str
    campaign_identity: str
    campaign_status: str
    run_count: int
    completed_run_count: int
    failed_run_count: int
    all_runs_engine_completed: bool
    publication_status: str
    publication_error: str | None


def crear_directorio_exclusivo(path: Path) -> Path:
    """Crea ``path`` solo si no existe. No crea el padre ni elige otro nombre."""
    if not isinstance(path, Path):
        raise TypeError("path debe ser un Path")
    if path.exists():
        raise FileExistsError(f"el directorio de salida ya existe: {path}")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"el directorio padre no existe: {path.parent}")
    path.mkdir(exist_ok=False)
    return path


def _entrada_de_resumen(
    entrada: ResolvedSuiteEntry,
    procesada: ProcessedCampaign,
) -> SuiteSummaryEntry:
    result_file = None
    if procesada.publication_status == PUBLICATION_PUBLISHED:
        result_file = f"{entrada.experiment_id}.json"
    return SuiteSummaryEntry(
        experiment_id=entrada.experiment_id,
        config_file=entrada.config_file,
        campaign_id=procesada.campaign_id,
        campaign_identity=procesada.campaign_identity,
        campaign_status=procesada.campaign_status,
        run_count=procesada.run_count,
        completed_run_count=procesada.completed_run_count,
        failed_run_count=procesada.failed_run_count,
        all_runs_engine_completed=procesada.all_runs_engine_completed,
        publication_status=procesada.publication_status,
        result_file=result_file,
        publication_error=procesada.publication_error,
    )


def codigo_de_salida(*entradas: ProcessedCampaign | SuiteSummaryEntry) -> int:
    if any(
        entrada.publication_status == PUBLICATION_FAILED
        or not entrada.all_runs_engine_completed
        for entrada in entradas
    ):
        return 1
    return 0


OPCIONES = frozenset({"--config", "--output"})


def rutas_de_opciones(tokens: list[str], *, comando: str) -> dict[str, str]:
    """Devuelve la ruta de --config y --output"""
    permitidas = frozenset({"--config"}) if comando == "inspect" else OPCIONES
    rutas: dict[str, str] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        opcion = token.split("=", 1)[0]
        if opcion not in permitidas:
            error_de_uso(1, token)
        if opcion in rutas:
            error_de_uso(2, opcion)
        if not token.startswith(opcion + "=") and index + 1 < len(tokens):
            siguiente = tokens[index + 1]
            if siguiente.startswith("-"):
                error_de_uso(4, opcion)
        valor, index = valor_opcion(tokens, index, opcion)
        if valor.strip() == "":
            error_de_uso(5, opcion)
        if valor.startswith("-"):
            error_de_uso(1, valor)
        rutas[opcion] = valor
        index += 1
    if "--config" not in rutas:
        error_de_uso(3, comando)
    return rutas


def publicar_resultado(
    construir: Callable[..., dict[str, Any]],
    escribir: Callable[..., Path],
    resuelta: object,
    resultado: CampaignResult,
    output_path: str,
) -> str | None:
    """Publica el resultado. Devuelve None si terminó, o el texto del error."""
    try:
        document = construir(resuelta, resultado)
        written = escribir(Path(output_path), document)
    except (OSError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return str(exc)
    finally:
        document = None
    print(f"Resultado guardado: {written}", file=sys.stderr)
    return None

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
