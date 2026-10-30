from __future__ import annotations

import json

from core.metrics.run import ScientificRunMetrics
from runner.demo import DEMO_NOTICE, DEMO_RECOVERY_NOTICE
from runner.result import RunResult

from cli.utils import cantidad, entero, fila, numero, segundos


def format_summary(result: RunResult) -> str:
    """Resumen breve en español para la salida estándar."""
    estrategia = result.strategy_type
    if result.batch_size_events is not None:
        estrategia = f"{estrategia} ({result.batch_size_events})"
    filas: list[tuple[str, str]] = [
        ("Tiempo simulado", f"{numero(result.simulation_time)} s"),
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
    ]
    if muestra_recuperacion(result):
        filas[7:7] = [
            ("Recuperación", etiqueta_recuperacion(result.recovery_mode)),
            ("Fallos inyectados", str(result.failures_injected)),
            ("Gaps observados", str(result.gaps_observed)),
            ("Gaps cerrados", str(result.gaps_closed)),
            ("Pedidos de hueco", str(result.gap_requests)),
        ]
    aviso = DEMO_RECOVERY_NOTICE if muestra_recuperacion(result) else DEMO_NOTICE
    ancho = max(len(etiqueta) for etiqueta, _valor in filas)
    lineas = ["Simulación completada", aviso, ""]
    for etiqueta, valor in filas:
        lineas.append(f"{etiqueta + ':':<{ancho + 1}}  {valor}")
    return "\n".join(lineas)


def format_trace(result: RunResult) -> str:
    """Una línea por entrada: tiempo, índice, tipo y entidad."""
    lineas = ["Traza", ""]
    for entry in result.trace_entries:
        entidad = "-" if entry.entity_id is None else entry.entity_id
        lineas.append(
            f"{numero(entry.simulation_time)}  "
            f"{entry.sequence_index}  "
            f"{entry.event_type}  "
            f"{entidad}"
        )
    return "\n".join(lineas)


def format_scientific_summary(result: RunResult) -> str:
    """Métricas científicas de esta corrida, en español.

    Un valor que no ocurrió se imprime como ``no definido``. No se
    reemplaza por cero.
    """
    metrics = result.scientific_metrics
    if metrics is None:
        return "Métricas científicas\n\nno definidas"
    lineas = [
        "Métricas científicas",
        "Una corrida. No es una campaña.",
        "",
        fila("Generados", str(metrics.generated)),
        fila("Persistidos en Tierra", str(metrics.earth_persisted_unique)),
        fila("Confirmados en Marte", str(metrics.confirmed)),
        fila("Backlog", str(metrics.final_backlog)),
        fila("No persistidos en Tierra", str(metrics.not_persisted_on_earth)),
        fila("Persistidos sin confirmar", str(metrics.persisted_on_earth_but_unconfirmed)),
        fila("Completitud en Tierra", cantidad(metrics.completeness)),
        fila("Confirmación en Marte", cantidad(metrics.confirmation_ratio)),
        fila("Convergió", "sí" if metrics.converged else "no"),
        fila("Referencia de convergencia", segundos(metrics.convergence.reference_at_sim)),
        fila("Convergencia", segundos(metrics.convergence.converged_at_sim)),
        fila(
            "Tiempo hasta convergencia",
            segundos(metrics.convergence.time_to_convergence_seconds),
        ),
        fila("Fin del escenario", segundos(metrics.scenario_completed_at_sim)),
        fila("Edad de la vista", segundos(metrics.view_age_seconds)),
        fila("Muestra de frescura", str(metrics.freshness.count)),
        fila("Cobertura de frescura", cantidad(metrics.freshness_coverage)),
        fila("Frescura mínima", segundos(metrics.freshness.min_seconds)),
        fila("Frescura p50", segundos(metrics.freshness.p50_seconds)),
        fila("Frescura p95", segundos(metrics.freshness.p95_seconds)),
        fila("Frescura máxima", segundos(metrics.freshness.max_seconds)),
        fila("Frescura media", segundos(metrics.freshness.mean_seconds)),
        fila("Huecos", str(metrics.gaps_count)),
        fila("Duplicados recibidos", str(metrics.duplicates_received)),
        fila("Duplicados almacenados", str(metrics.duplicates_stored)),
        fila("Intentos con número > 1", str(metrics.retry_attempts_total)),
        fila("SyncUnits de telemetría", str(metrics.sync_units_created)),
        fila(
            "Bytes de telemetría creados",
            str(metrics.traffic.telemetry_syncunit_bytes_created),
        ),
        fila(
            "Bytes iniciales creados",
            str(metrics.traffic.telemetry_initial_syncunit_bytes_created),
        ),
        fila(
            "Bytes de reintento creados",
            str(metrics.traffic.telemetry_retry_syncunit_bytes_created),
        ),
        fila("Bytes de ACK creados", str(metrics.traffic.ack_syncunit_bytes_created)),
        fila(
            "Bytes de transporte",
            str(metrics.traffic.total_transport_application_bytes),
        ),
        fila("Bytes de transporte en reintento", str(metrics.traffic.retry_transport_bytes)),
        fila("Bytes interrumpidos", str(metrics.traffic.interrupted_transport_bytes)),
        fila(
            "Utilización ponderada",
            cantidad(metrics.contacts.contact_utilization_weighted),
        ),
    ]
    lineas.extend(lineas_recuperacion(metrics))
    return "\n".join(lineas)


def summary_json(
    result: RunResult, *, include_trace: bool, include_scientific: bool = False
) -> str:
    """Resumen operativo en JSON. No escribe archivos.

    ``trace_entries`` es la cantidad de entradas. Con ``include_trace``,
    se agrega ``trace`` con tiempo, índice, tipo y entidad, sin payload.
    Con ``include_scientific``, se agrega ``scientific_metrics``.
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
    if muestra_recuperacion(result):
        payload["recovery_mode"] = result.recovery_mode
        payload["failures_injected"] = result.failures_injected
        payload["gaps_observed"] = result.gaps_observed
        payload["gaps_closed"] = result.gaps_closed
        payload["gap_requests"] = result.gap_requests
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
    if include_scientific and result.scientific_metrics is not None:
        payload["scientific_metrics"] = result.scientific_metrics.to_dict()
    return json.dumps(payload, ensure_ascii=False, indent=2)


def muestra_recuperacion(result: RunResult) -> bool:
    """La demostración normal no agrega filas de recuperación."""
    return result.recovery_mode != "none" or result.failures_injected > 0


def etiqueta_recuperacion(recovery_mode: str) -> str:
    if recovery_mode == "none":
        return "ninguna"
    return recovery_mode


def lineas_recuperacion(metrics: ScientificRunMetrics) -> list[str]:
    """Tiempos del episodio. No los reduce a un único tiempo de recuperación."""
    summary = metrics.recovery
    lineas = [
        fila("Episodios de recuperación", str(summary.episode_count)),
    ]
    if summary.episode_count == 0:
        return lineas
    lineas.extend(
        [
            fila("Pérdida → disparo", segundos(summary.loss_to_trigger_seconds)),
            fila(
                "Disparo → persistencia en Tierra",
                segundos(summary.trigger_to_earth_recovery_seconds),
            ),
            fila(
                "Pérdida → persistencia en Tierra",
                segundos(summary.loss_to_earth_recovery_seconds),
            ),
            fila(
                "Persistencia → confirmación en Marte",
                segundos(summary.earth_recovery_to_origin_confirmation_seconds),
            ),
            fila(
                "Pérdida → confirmación en Marte",
                segundos(summary.loss_to_origin_confirmation_seconds),
            ),
            fila("Hueco observado", segundos(summary.gap_observed_at_sim)),
            fila("Timeouts de ACK del emisor", entero(summary.sender_ack_timeout_count)),
            fila("Retries del emisor", entero(summary.sender_retry_attempt_count)),
            fila(
                "GapRequest lógicos",
                entero(summary.receiver_gap_request_logical_count),
            ),
            fila(
                "Intentos de transporte del GapRequest",
                entero(summary.gap_request_transport_attempt_count),
            ),
            fila(
                "Reparaciones del receptor",
                entero(summary.receiver_repair_attempt_count),
            ),
            fila(
                "Bytes de red de la política",
                entero(summary.policy_recovery_network_bytes_total),
            ),
        ]
    )
    return lineas