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
from cli.arguments import ErrorDeUso, valor_opcion
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


def comando_inspect(tokens: list[str], *, ayuda: str) -> int:
    """Prepara la campaña o la suite declarada y muestra su resumen. No ejecuta el motor."""
    if tokens == ["-h"] or tokens == ["--help"]:
        print(ayuda, end="")
        return 0
    try:
        config_path = _ruta_de_config(tokens, comando="inspect")
    except ErrorDeUso as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        declarado = load_declared_configuration(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if isinstance(declarado, ResolvedSuite):
        print(format_suite_inspection(declarado))
        return 0
    print(format_campaign_inspection(declarado))
    return 0


def comando_run(tokens: list[str], *, ayuda: str) -> int:
    """Carga la campaña o la suite, la ejecuta y muestra cada corrida.

    Sin ``--output`` no construye ni escribe documentos. Una campaña
    individual conserva el archivo de salida. Una suite publica en un
    directorio nuevo, una campaña después de la otra.
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
        declarado = load_declared_configuration(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if isinstance(declarado, ResolvedSuite):
        return ejecutar_suite(declarado, output_path)
    return _codigo_de_campana(procesar_campana_resuelta(declarado, output_path))


def ejecutar_suite(suite: ResolvedSuite, output_path: str | None) -> int:
    """Ejecuta las campañas ya resueltas, en orden, y libera cada resultado.

    El directorio de salida se crea antes de la primera campaña. Si ya
    existe, no se ejecuta ninguna. Cada publicación ocurre antes de
    pasar a la campaña siguiente. Una interrupción no escribe el resumen
    ni borra lo ya publicado.
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
        return _codigo_de_suite(registros)
    document = build_suite_summary(suite.document, registros)
    try:
        written = write_suite_summary(directorio / "suite-summary.json", document)
    except (OSError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        del document
    print(f"Resumen de suite guardado: {written}", file=sys.stderr)
    return _codigo_de_suite(registros)


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


def _codigo_de_campana(procesada: ProcessedCampaign) -> int:
    if procesada.publication_status == PUBLICATION_FAILED:
        return 1
    if not procesada.all_runs_engine_completed:
        return 1
    return 0


def _codigo_de_suite(registros: list[SuiteSummaryEntry]) -> int:
    if any(entrada.publication_status == PUBLICATION_FAILED for entrada in registros):
        return 1
    if any(not entrada.all_runs_engine_completed for entrada in registros):
        return 1
    return 0


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
