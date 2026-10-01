"""Texto y JSON del resumen de una corrida. No ejecuta el motor."""

from __future__ import annotations

import json

from runner.demo import DEMO_NOTICE
from runner.result import RunResult


def format_summary(result: RunResult) -> str:
    """Resumen breve en español para la salida estándar."""
    estrategia = result.strategy_type
    if result.batch_size_events is not None:
        estrategia = f"{estrategia} ({result.batch_size_events})"
    filas = (
        ("Tiempo simulado", f"{_numero(result.simulation_time)} s"),
        ("Estrategia", estrategia),
        ("Eventos generados", str(result.events_generated)),
        ("Persistidos en Tierra", str(result.events_persisted_earth)),
        ("Confirmados en Marte", str(result.events_confirmed_mars)),
        ("Pendientes en Marte", str(result.events_pending_mars)),
        ("Intentos", str(result.attempts_total)),
        ("Retries", str(result.retry_count)),
        ("Gaps en Tierra", str(result.earth_gaps_count)),
        ("Duplicados", str(result.duplicates_received)),
        ("Entradas de traza", str(len(result.trace_entries))),
        ("Estado", result.engine_status),
    )
    ancho = max(len(etiqueta) for etiqueta, _valor in filas)
    lineas = ["Simulación completada", DEMO_NOTICE, ""]
    for etiqueta, valor in filas:
        lineas.append(f"{etiqueta + ':':<{ancho + 1}}  {valor}")
    return "\n".join(lineas)


def format_trace(result: RunResult) -> str:
    """Una línea por entrada: tiempo, índice, tipo y entidad."""
    lineas = ["Traza", ""]
    for entry in result.trace_entries:
        entidad = "-" if entry.entity_id is None else entry.entity_id
        lineas.append(
            f"{_numero(entry.simulation_time)}  "
            f"{entry.sequence_index}  "
            f"{entry.event_type}  "
            f"{entidad}"
        )
    return "\n".join(lineas)


def summary_json(result: RunResult, *, include_trace: bool) -> str:
    """Resumen operativo en JSON. No escribe archivos.

    ``trace_entries`` es la cantidad de entradas. Con ``include_trace``,
    se agrega ``trace`` con tiempo, índice, tipo y entidad, sin payload.
    """
    payload: dict[str, object] = {
        "simulation_time": result.simulation_time,
        "engine_status": result.engine_status,
        "strategy_type": result.strategy_type,
        "batch_size_events": result.batch_size_events,
        "events_generated": result.events_generated,
        "events_persisted_earth": result.events_persisted_earth,
        "events_confirmed_mars": result.events_confirmed_mars,
        "events_pending_mars": result.events_pending_mars,
        "attempts_total": result.attempts_total,
        "retry_count": result.retry_count,
        "earth_gaps_count": result.earth_gaps_count,
        "duplicates_received": result.duplicates_received,
        "trace_entries": len(result.trace_entries),
    }
    if include_trace:
        payload["trace"] = [
            {
                "simulation_time": entry.simulation_time,
                "sequence_index": entry.sequence_index,
                "event_type": entry.event_type,
                "entity_id": entry.entity_id,
            }
            for entry in result.trace_entries
        ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _numero(value: float) -> str:
    texto = f"{value:.6f}".rstrip("0").rstrip(".")
    if "." not in texto:
        return f"{texto}.0"
    return texto
