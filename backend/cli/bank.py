from __future__ import annotations

import sys
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.simulation.engine import SimulationStatus
from experiments.campaign import CampaignResult, execute_campaign
from experiments import campaign as campaign_execution
from experiments.bank_result_spool import BankResultSpool
from experiments.campaign import present_result_spec_differences
from experiments.manifest import campaign_run_manifest_entry, campaign_manifest_from_entries
from experiments.experiment_bank_result import bank_result_metadata, E2_CONFIGURABLE_BANK_RESULT
from cli.present.bank import format_e2_campaign_blocks, lineas_de_resultado_e2
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
from experiments.publication import (
    PUBLICATION_FAILED,
    PUBLICATION_NOT_REQUESTED,
    PUBLICATION_PUBLISHED,
)
from cli.utils import parse_path_options
from cli.present import (
    format_campaign_inspection,
    format_configurable_e1_campaign,
    format_configurable_e2_campaign,
    format_configurable_e3_campaign,
    format_configurable_e3_sensitivity_campaign,
    format_e1_bank_comparison,
)


def comando_banco(tokens: list[str], *, ayuda: str, comando: str) -> int:
    """Inspecciona o ejecuta el banco declarado."""
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
        print("\n\n".join(
            format_campaign_inspection(resolved)
            for _, resolved in declarado.entries
        ))
        return 0
    output_path = rutas.get("--output")
    if rutas.get("--output-dir") is not None:
        print("--output-dir no admite bancos multi-experimento", file=sys.stderr)
        return 1
    if output_path is not None:
        return ejecutar_banco(declarado, output_path, input_sources=input_sources)
    return ejecutar_banco(declarado, output_path)


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
    """Ejecuta las camañas del banco."""
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
    for _, resolved in bank.entries:
        registros.append(procesar_campana_resuelta(resolved, None))
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

def procesar_campana_resuelta(
    resuelta: ResolvedCampaign,
    output_path: str | None,
    *,
    index_entry: dict[str, Any] | None = None,
    provenance: SoftwareProvenance | None = None,
) -> "ProcessedCampaign":
    """Ejecuta una campaña ya resuelta, la presenta y, si hay ruta, la publica.

    El ``CampaignResult`` y el documento construido no salen de esta
    función. El banco llama una vez por entrada y conserva solo estos hechos
    entre campañas.
    """
    if isinstance(resuelta, ResolvedE2Campaign) and output_path is not None and index_entry is not None:
        return _ejecutar_e2_indexado(resuelta, output_path, index_entry, provenance)
    resultado = execute_campaign(resuelta.campaign)
    estado_campana = resultado.status
    if index_entry is not None:
        index_entry.update(execution_status="returned", campaign_status=estado_campana)
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
        campaign_status=estado_campana,
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


def codigo_de_salida(*entradas: ProcessedCampaign) -> int:
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

def _fallo_de_corrida(run) -> str | None:
    if run.result is None:
        return f"{run.label}: {run.error_type}: {run.error_message}"
    if run.result.engine_status != SimulationStatus.COMPLETED.value:
        return f"{run.label}: estado {run.result.engine_status}"
    return None


def resumen_de_fallos(resultado: CampaignResult) -> str:
    return "\n".join(text for run in resultado.runs if (text := _fallo_de_corrida(run)))


def _ejecutar_e2_indexado(resuelta, output_path, index_entry, provenance):
    """E2 con salida: solo hechos ligeros sobreviven a cada intento."""
    provenance = current_provenance() if provenance is None else provenance
    entries, blocks, failures, terminals = [], [], [], []
    validation_error = None
    engine_completed = True
    spool = BankResultSpool(Path(output_path))
    try:
        for run in campaign_execution._iter_campaign_runs(
            resuelta.campaign, campaign_execution.execute_scientific_run,
        ):
            planned = resuelta.campaign.runs[run.index]
            terminal = dict(completed=run.completed,
                engine_status=None if run.result is None else run.result.engine_status,
                error_type=run.error_type, error_message=run.error_message)
            terminals.append(terminal)
            engine_completed &= terminal['engine_status'] == SimulationStatus.COMPLETED.value
            blocks.append("\n".join(lineas_de_resultado_e2(planned, run)))
            if text := _fallo_de_corrida(run):
                failures.append(text)
            try:
                entries.append(campaign_run_manifest_entry(planned.spec, run, provenance))
            except (TypeError, ValueError) as exc:
                spool.fail('manifiesto', exc)
            if run.result is not None:
                differences = present_result_spec_differences(run.result, planned.spec)
                if differences and validation_error is None:
                    validation_error = (
                        "el resultado de la corrida no coincide con su especificación: "
                        f"label={run.label}, campo={differences[0][0]}"
                    )
            spool.append(run.index, run.result)
            del run
        completed = sum(t['completed'] for t in terminals)
        status = 'COMPLETED' if completed == len(terminals) else 'COMPLETED_WITH_FAILURES'
        identity = resuelta.campaign.campaign_identity
        index_entry.update(execution_status='returned', campaign_status=status)
        if (resuelta.campaign.campaign_id != index_entry['campaign_id']
                or identity != index_entry['campaign_identity']
                or len(terminals) != len(index_entry['runs'])):
            raise ValueError('el retorno no corresponde a la campaña planificada')
        for position, (target, terminal) in enumerate(zip(index_entry['runs'], terminals, strict=True)):
            if target['index'] != position or target['label'] != resuelta.campaign.runs[position].label:
                raise ValueError('el retorno no respeta el orden planificado')
            target['terminal'] = terminal
        print(format_e2_campaign_blocks(resuelta, identity, blocks))
        if failures:
            print("\n".join(failures), file=sys.stderr)
        try:
            manifest = campaign_manifest_from_entries(resuelta.campaign, entries, provenance).to_dict()
            if validation_error is not None:
                raise ValueError(validation_error)
            metadata = bank_result_metadata(resuelta, manifest, provenance, E2_CONFIGURABLE_BANK_RESULT)
            _proyectar_manifiesto(index_entry, metadata)
            spool.publish(metadata)
        except (OSError, TypeError, ValueError) as exc:
            spool.fail('construcción', exc)
        publication_error = None
        publication_status = PUBLICATION_PUBLISHED if spool.published else PUBLICATION_FAILED
        if not spool.published:
            publication_error = spool.error
            index_entry.update(publication_status='failed', publication_error=publication_error)
            print(publication_error, file=sys.stderr)
        else:
            print(f'Resultado guardado: {output_path}', file=sys.stderr)
            index_entry.update(publication_status='published', publication_error=None)
            try:
                if spool.cleanup_error is not None:
                    raise OSError(spool.cleanup_error)
                index_entry['artifact'] = bank_index.artifact_metadata(Path(output_path).parent, 'e2')
            except (OSError, ValueError) as exc:
                index_entry.update(publication_status='unverified', integrity_error=f'{type(exc).__name__}: {exc}',
                    artifact=dict(relative_path=Path(output_path).name, size_bytes=None, sha256=None))
                print(f'Resultado publicado sin hash confirmado: {exc}', file=sys.stderr)
        return ProcessedCampaign(resuelta.campaign.campaign_id, identity, status, len(terminals), completed,
            len(terminals)-completed, engine_completed, publication_status, publication_error)
    finally:
        spool.close()
        if spool.cleanup_error is not None:
            print(spool.cleanup_error, file=sys.stderr)


def todas_las_corridas_completaron(resultado: CampaignResult) -> bool:
    return all(
        run.result is not None
        and run.result.engine_status == SimulationStatus.COMPLETED.value
        for run in resultado.runs
    )
