"""Texto de una corrida o campaña ya terminada. No ejecuta el motor."""

from __future__ import annotations

from experiments.campaign import CampaignResult
from experiments.result import ScientificRunResult


def format_scientific_run(result: ScientificRunResult) -> str:
    """Resumen de la especificación, la generación y las métricas principales."""
    estrategia = result.strategy_type
    if result.batch_size_events is not None:
        estrategia = f"{estrategia} ({result.batch_size_events})"
    horizonte = (
        "sin horizonte"
        if result.horizon_seconds is None
        else f"{_numero(result.horizon_seconds)} s"
    )
    carga = (
        "sin fracción"
        if result.offered_load_fraction is None
        else _numero(result.offered_load_fraction)
    )
    marcas = ", ".join(_numero(mark) for mark in result.generation_timestamps)
    metrics = result.metrics
    filas = (
        ("Escenario", result.scenario_id),
        ("Workload", result.workload_id),
        ("Semilla", str(result.seed)),
        ("Identidad de dataset", result.dataset_identity),
        ("Identidad de ejecución", result.execution_identity),
        ("Estrategia", estrategia),
        ("Recuperación", result.recovery_policy),
        ("Política de parada", result.stop_policy),
        ("Horizonte", horizonte),
        ("Fracción de carga ofrecida", carga),
        ("Eventos generados", str(result.events_generated)),
        ("Marcas de generación", marcas if marcas else "ninguna"),
        ("Persistidos en Tierra", str(result.events_persisted_earth)),
        ("Confirmados en Marte", str(result.events_confirmed_mars)),
        ("Backlog", str(metrics.final_backlog)),
        ("Completitud en Tierra", _cantidad(metrics.completeness)),
        ("Confirmación", _cantidad(metrics.confirmation_ratio)),
        ("Tiempo simulado", f"{_numero(result.simulation_time)} s"),
        ("Estado", result.engine_status),
    )
    ancho = max(len(etiqueta) for etiqueta, _valor in filas)
    lineas = [
        "Corrida científica controlada",
        "Una corrida.",
        "",
    ]
    for etiqueta, valor in filas:
        lineas.append(f"{etiqueta + ':':<{ancho + 1}}  {valor}")
    return "\n".join(lineas)


def format_campaign(result: CampaignResult) -> str:
    """Corridas en el orden de la campaña, con identidad y conteos de cada una."""
    lineas = [
        f"Campaña: {result.campaign_id}",
        f"Identidad: {result.campaign_identity}",
        f"Corridas: {result.run_count}",
        f"Completadas: {result.completed_count}",
    ]
    if result.failed_count:
        lineas.append(f"Fallidas: {result.failed_count}")
    lineas.append("")
    for run in result.runs:
        lineas.append(f"[{run.index + 1}] {run.label}")
        if run.result is None:
            lineas.append("Estado: falló")
            lineas.append(f"Tipo: {run.error_type}")
            lineas.append(f"Mensaje: {run.error_message}")
        else:
            lineas.append(f"Identidad de dataset: {run.result.dataset_identity}")
            lineas.append(f"Identidad de ejecución: {run.result.execution_identity}")
            lineas.append(f"Generados: {run.result.events_generated}")
            lineas.append(f"Persistidos: {run.result.events_persisted_earth}")
            lineas.append(f"Confirmados: {run.result.events_confirmed_mars}")
        lineas.append("")
    return "\n".join(lineas).rstrip("\n")


def _numero(value: float) -> str:
    text = f"{value:.9f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _cantidad(value: float | None) -> str:
    if value is None:
        return "no definido"
    return _numero(value)
