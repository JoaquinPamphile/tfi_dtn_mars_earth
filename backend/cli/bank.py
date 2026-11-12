from __future__ import annotations

import sys
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.simulation.engine import SimulationStatus
from experiments.campaign import CampaignResult, execute_campaign
from experiments.campaign_persistence import (
    PersistedCampaignResult,
    execute_campaign_persisted,
)
from experiments.experiment_bank import (
    ResolvedCampaign,
    ResolvedE1Campaign,
    ResolvedE2Campaign,
    ResolvedE3Campaign,
    ResolvedE3SensitivityCampaign,
    ResolvedExperimentBank,
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
from experiments import experiment_bank_run_index as bank_index
from experiments.software_provenance import SoftwareProvenance, current_provenance
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
from cli.utils import parse_path_options
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
        input_sources: dict[str, dict[str, str]] = {}
        if comando == "run" and rutas.get("--output") is not None:
            declarado = load_declared_configuration(config_path, input_sources=input_sources)
        else:
            declarado = load_declared_configuration(config_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if comando == "inspect":
        if isinstance(declarado, ResolvedSuite):
            print(format_suite_inspection(declarado))
        elif isinstance(declarado, ResolvedExperimentBank):
            print("\n\n".join(
                format_campaign_inspection(resolved)
                for _, resolved in declarado.entries
            ))
        else:
            print(format_campaign_inspection(declarado))
        return 0
    output_path = rutas.get("--output")
    output_dir = rutas.get("--output-dir")
    if isinstance(declarado, ResolvedSuite):
        if output_dir is not None:
            print(
                "--output-dir no admite suites; declare una campaña E1, E2 o E3",
                file=sys.stderr,
            )
            return 1
        return ejecutar_suite(declarado, output_path)
    if isinstance(declarado, ResolvedExperimentBank):
        if output_dir is not None:
            print("--output-dir no admite bancos multi-experimento", file=sys.stderr)
            return 1
        if output_path is not None:
            return ejecutar_banco(declarado, output_path, input_sources=input_sources)
        return ejecutar_banco(declarado, output_path)
    if output_dir is not None:
        return ejecutar_campana_persistida(declarado, output_dir)
    return codigo_de_salida(procesar_campana_resuelta(declarado, output_path))

def ejecutar_campana_persistida(
    resuelta: ResolvedCampaign,
    output_dir: str,
) -> int:
    """Ejecuta con persistencia por corrida. No construye el JSON monolítico."""
    try:
        directorio = crear_directorio_exclusivo(Path(output_dir))
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        persisted = execute_campaign_persisted(resuelta.campaign, directorio)
    except (OSError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return codigo_de_salida_persistida(persisted)

def presentar_campana_persistida(persisted: PersistedCampaignResult) -> None:
    """Resumen breve sin recargar resultados ni construir el monolítico."""
    print(f"Estado: {persisted.status}")
    print(f"Corridas completadas: {persisted.completed_count}")
    print(f"Corridas fallidas: {persisted.failed_count}")
    print(f"Directorio: {persisted.directory}")
    if persisted.index_path is not None:
        print(f"Índice: {persisted.index_path}")

def codigo_de_salida_persistida(persisted: PersistedCampaignResult) -> int:
    presentar_campana_persistida(persisted)
    if persisted.index_path is None:
        print(
            "Ejecución incompleta: no se publicó el índice.",
            file=sys.stderr,
        )
        return 1
    return 0


def ejecutar_banco(
    bank: ResolvedExperimentBank,
    output_path: str | None,
    *,
    input_sources: dict[str, dict[str, str]] | None = None,
) -> int:
    """Ejecuta la colección directamente, sin fabricar una suite."""
    directorio: Path | None = None
    if output_path is not None:
        try:
            if input_sources is None or set(input_sources) != {"configuration", "contact_plan"}:
                raise ValueError("el índice requiere hashes capturados por el loader")
            provenance = current_provenance()
            confirmed = bank_index.build_initial_index(
                bank, configuration_source=input_sources["configuration"],
                contact_plan_source=input_sources["contact_plan"], provenance=provenance,
            )
        except (OSError, TypeError, ValueError) as exc:
            print(f"Contexto de ejecución indexada inválido: {exc}", file=sys.stderr)
            return 1
        try:
            directorio = crear_directorio_exclusivo(Path(output_path))
        except OSError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if directorio is not None:
        return ejecutar_banco_indexado(bank, directorio, confirmed, provenance)
    registros: list[ProcessedCampaign] = []
    for experiment_id, resolved in bank.entries:
        destino = (
            None
            if directorio is None
            else str(directorio / f"{experiment_id}.json")
        )
        registros.append(procesar_campana_resuelta(resolved, destino))
    return codigo_de_salida(*registros)


def ejecutar_banco_indexado(
    bank: ResolvedExperimentBank,
    directory: Path,
    confirmed: dict[str, Any],
    provenance: SoftwareProvenance,
) -> int:
    """Solo V2 + --output. Estado confirmado avanza tras cada escritura exitosa."""
    try:
        bank_index.write_bank_run_index(directory, confirmed)
    except (OSError, TypeError, ValueError) as exc:
        print(f"No se pudo publicar el índice inicial: {exc}", file=sys.stderr)
        return 1
    records: list[ProcessedCampaign] = []
    integrity_failed = False
    for position, (family, resolved) in enumerate(bank.entries):
        entry = deepcopy(confirmed["entries"][position])
        aborted = False
        try:
            processed = procesar_campana_resuelta(
                resolved, str(directory / f"{family}.json"),
                index_entry=entry, provenance=provenance,
            )
            records.append(processed)
        except Exception as exc:
            # KeyboardInterrupt/SystemExit no se interceptan: un cierre abrupto
            # deja el último checkpoint y cualquier archivo recién publicado.
            aborted = True
            if entry["execution_status"] == "pending":
                entry.update(execution_status="failed", execution_error={
                    "type": type(exc).__name__, "message": str(exc),
                })
            elif entry["publication_status"] == "pending":
                entry.update(publication_status="failed", publication_error=str(exc))
            print(f"Campaña abortada: {type(exc).__name__}: {exc}", file=sys.stderr)
        try:
            following = bank_index.advance_index(confirmed, entry)
            bank_index.write_bank_run_index(directory, following, previous=confirmed)
        except (OSError, TypeError, ValueError) as exc:
            print(f"No se pudo publicar el checkpoint: {exc}", file=sys.stderr)
            return 1
        confirmed = following
        integrity_failed |= entry["publication_status"] == "unverified"
        if aborted:
            # Solo se cierra si este era el último desenlace; nunca se sigue
            # ejecutando tras una excepción de campaña no controlada previamente.
            if position == len(bank.entries) - 1:
                _publicar_indice_final(directory, confirmed)
            return 1
    if not _publicar_indice_final(directory, confirmed):
        return 1
    return 1 if integrity_failed else codigo_de_salida(*records)


def _publicar_indice_final(directory: Path, confirmed: dict[str, Any]) -> bool:
    try:
        final = bank_index.finalize_index(confirmed)
        written = bank_index.write_bank_run_index(directory, final, previous=confirmed)
    except (OSError, TypeError, ValueError) as exc:
        print(f"No se pudo publicar el índice final: {exc}", file=sys.stderr)
        return False
    print(f"Índice de banco guardado: {written}", file=sys.stderr)
    return True

def ejecutar_suite(
    suite: ResolvedSuite,
    output_path: str | None,
) -> int:
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
    *,
    index_entry: dict[str, Any] | None = None,
    provenance: SoftwareProvenance | None = None,
) -> "ProcessedCampaign":
    """Ejecuta una campaña ya resuelta, la presenta y, si hay ruta, la publica.

    El ``CampaignResult`` y el documento construido no salen de esta
    función. La suite llama una vez por entrada y descarta el regreso
    antes de la campaña siguiente.
    """
    resultado = execute_campaign(resuelta.campaign)
    if index_entry is not None:
        index_entry.update(execution_status="returned", campaign_status=resultado.status)
        if (resultado.campaign_id != index_entry["campaign_id"]
                or resultado.campaign_identity != index_entry["campaign_identity"]
                or len(resultado.runs) != len(index_entry["runs"])):
            raise ValueError("el retorno no corresponde a la campaña planificada")
        for target, run in zip(index_entry["runs"], resultado.runs, strict=True):
            if target["index"] != run.index or target["label"] != run.label:
                raise ValueError("el retorno no respeta el orden planificado")
            target["terminal"] = {
                "completed": run.completed,
                "engine_status": None if run.result is None else run.result.engine_status,
                "error_type": run.error_type, "error_message": run.error_message,
            }
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
        arguments = (construir, escribir, resuelta, resultado, output_path)
        if index_entry is None:
            publication_error = publicar_resultado(*arguments)
        else:
            publication_error = publicar_resultado(
                *arguments, index_entry=index_entry, provenance=provenance,
            )
        publication_status = (
            PUBLICATION_FAILED
            if publication_error is not None
            else PUBLICATION_PUBLISHED
        )
        if index_entry is not None:
            index_entry.update(publication_status=publication_status, publication_error=publication_error)
            if publication_status == PUBLICATION_PUBLISHED:
                try:
                    index_entry["artifact"] = bank_index.artifact_metadata(
                        Path(output_path).parent, index_entry["experiment_id"],
                    )
                except (OSError, ValueError) as exc:
                    index_entry.update(
                        publication_status="unverified", integrity_error=f"{type(exc).__name__}: {exc}",
                        artifact={"relative_path": Path(output_path).name, "size_bytes": None, "sha256": None},
                    )
                    print(f"Resultado publicado sin hash confirmado: {exc}", file=sys.stderr)
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


OPCIONES = frozenset({"--config", "--output", "--output-dir"})


def rutas_de_opciones(tokens: list[str], *, comando: str) -> dict[str, str]:
    """Devuelve la ruta de --config y --output"""
    permitidas = frozenset({"--config"}) if comando == "inspect" else OPCIONES
    return parse_path_options(
        tokens,
        allowed=permitidas,
        command_name=comando,
        require_output=False,
    )


def publicar_resultado(
    construir: Callable[..., dict[str, Any]],
    escribir: Callable[..., Path],
    resuelta: object,
    resultado: CampaignResult,
    output_path: str,
    *,
    index_entry: dict[str, Any] | None = None,
    provenance: SoftwareProvenance | None = None,
) -> str | None:
    """Publica el resultado. Devuelve None si terminó, o el texto del error."""
    try:
        if index_entry is None:
            document = construir(resuelta, resultado)
        else:
            document = construir(resuelta, resultado, provenance=provenance)
            _proyectar_manifiesto(index_entry, document)
        written = escribir(Path(output_path), document)
    except (OSError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return str(exc)
    finally:
        document = None
    print(f"Resultado guardado: {written}", file=sys.stderr)
    return None


def _proyectar_manifiesto(entry: dict[str, Any], document: dict[str, Any]) -> None:
    """Copia únicamente escalares ya calculados; no retiene manifiestos/eventos."""
    manifest = document["campaign_manifest"]
    if (manifest["campaign_id"] != entry["campaign_id"]
            or manifest["campaign_identity"] != entry["campaign_identity"]
            or manifest["status"] != entry["campaign_status"]):
        raise ValueError("manifiesto no corresponde al desenlace planificado")
    for target, observed in zip(entry["runs"], manifest["runs"], strict=True):
        body = observed["manifest"]
        if observed["index"] != target["index"] or observed["label"] != target["label"]:
            raise ValueError("manifiesto no respeta el orden planificado")
        for key in ("dataset_identity", "experiment_identity", "execution_identity", "configuration_hash"):
            if body[key] != target[key]:
                raise ValueError(f"manifiesto difiere de la planificación en {key}")
        if body["terminal"] != target["terminal"]:
            raise ValueError("terminal de manifiesto difiere del retorno observado")
        target["dataset_fingerprint"] = body["dataset_fingerprint"]

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
