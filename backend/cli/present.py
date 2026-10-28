"""Texto y JSON del resumen de una corrida, la inspección E1, E2 y E3, y los informes de run-e1, run-e2 y run-e3.

No ejecuta el motor ni lee archivos.
"""

from __future__ import annotations

import json

from core.failure.plan import FailurePlan
from core.metrics.recovery import RecoveryEpisodeResult
from core.metrics.run import ScientificRunMetrics
from runner.demo import DEMO_NOTICE, DEMO_RECOVERY_NOTICE
from runner.result import RunResult

from experiments.campaign import CampaignResult, CampaignRunResult, CampaignRunSpec
from experiments.contact_plan import (
    contact_plan_definition_fingerprint,
    contact_plan_fingerprint,
)
from experiments.experiment_bank import (
    ExperimentBankE3Section,
    ExperimentBankE3SensitivitySection,
    ResolvedE1Campaign,
    ResolvedE2Campaign,
    ResolvedE3Campaign,
    ResolvedE3SensitivityCampaign,
)
from experiments.experiment_suite import ResolvedSuite, SuiteSummaryEntry
from experiments.fingerprint import configuration_hash
from experiments.report import format_campaign


def format_summary(result: RunResult) -> str:
    """Resumen breve en español para la salida estándar."""
    estrategia = result.strategy_type
    if result.batch_size_events is not None:
        estrategia = f"{estrategia} ({result.batch_size_events})"
    filas: list[tuple[str, str]] = [
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
    ]
    if _muestra_recuperacion(result):
        filas[7:7] = [
            ("Recuperación", _etiqueta_recuperacion(result.recovery_mode)),
            ("Fallos inyectados", str(result.failures_injected)),
            ("Gaps observados", str(result.gaps_observed)),
            ("Gaps cerrados", str(result.gaps_closed)),
            ("Pedidos de hueco", str(result.gap_requests)),
        ]
    aviso = DEMO_RECOVERY_NOTICE if _muestra_recuperacion(result) else DEMO_NOTICE
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
            f"{_numero(entry.simulation_time)}  "
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
        _fila("Generados", str(metrics.generated)),
        _fila("Persistidos en Tierra", str(metrics.earth_persisted_unique)),
        _fila("Confirmados en Marte", str(metrics.confirmed)),
        _fila("Backlog", str(metrics.final_backlog)),
        _fila("No persistidos en Tierra", str(metrics.not_persisted_on_earth)),
        _fila("Persistidos sin confirmar", str(metrics.persisted_on_earth_but_unconfirmed)),
        _fila("Completitud en Tierra", _cantidad(metrics.completeness)),
        _fila("Confirmación en Marte", _cantidad(metrics.confirmation_ratio)),
        _fila("Convergió", "sí" if metrics.converged else "no"),
        _fila("Referencia de convergencia", _segundos(metrics.convergence.reference_at_sim)),
        _fila("Convergencia", _segundos(metrics.convergence.converged_at_sim)),
        _fila(
            "Tiempo hasta convergencia",
            _segundos(metrics.convergence.time_to_convergence_seconds),
        ),
        _fila("Fin del escenario", _segundos(metrics.scenario_completed_at_sim)),
        _fila("Edad de la vista", _segundos(metrics.view_age_seconds)),
        _fila("Muestra de frescura", str(metrics.freshness.count)),
        _fila("Cobertura de frescura", _cantidad(metrics.freshness_coverage)),
        _fila("Frescura mínima", _segundos(metrics.freshness.min_seconds)),
        _fila("Frescura p50", _segundos(metrics.freshness.p50_seconds)),
        _fila("Frescura p95", _segundos(metrics.freshness.p95_seconds)),
        _fila("Frescura máxima", _segundos(metrics.freshness.max_seconds)),
        _fila("Frescura media", _segundos(metrics.freshness.mean_seconds)),
        _fila("Huecos", str(metrics.gaps_count)),
        _fila("Duplicados recibidos", str(metrics.duplicates_received)),
        _fila("Duplicados almacenados", str(metrics.duplicates_stored)),
        _fila("Intentos con número > 1", str(metrics.retry_attempts_total)),
        _fila("SyncUnits de telemetría", str(metrics.sync_units_created)),
        _fila(
            "Bytes de telemetría creados",
            str(metrics.traffic.telemetry_syncunit_bytes_created),
        ),
        _fila(
            "Bytes iniciales creados",
            str(metrics.traffic.telemetry_initial_syncunit_bytes_created),
        ),
        _fila(
            "Bytes de reintento creados",
            str(metrics.traffic.telemetry_retry_syncunit_bytes_created),
        ),
        _fila("Bytes de ACK creados", str(metrics.traffic.ack_syncunit_bytes_created)),
        _fila(
            "Bytes de transporte",
            str(metrics.traffic.total_transport_application_bytes),
        ),
        _fila("Bytes de transporte en reintento", str(metrics.traffic.retry_transport_bytes)),
        _fila("Bytes interrumpidos", str(metrics.traffic.interrupted_transport_bytes)),
        _fila(
            "Utilización ponderada",
            _cantidad(metrics.contacts.contact_utilization_weighted),
        ),
    ]
    lineas.extend(_lineas_recuperacion(metrics))
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
    if _muestra_recuperacion(result):
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


def format_e1_campaign_inspection(resolved: ResolvedE1Campaign) -> str:
    """Resumen de una campaña E1 ya resuelta.

    El resolver copia el mismo escenario y la misma semilla en cada corrida.
    No lee archivos, no ejecuta la simulación y no inventa métricas.
    """
    preparada = resolved.campaign
    especificacion = preparada.runs[0].spec
    escenario = especificacion.scenario
    plan = resolved.contact_plan_definition
    horizonte = (
        "no definido"
        if escenario.horizon_seconds is None
        else f"{_numero(escenario.horizon_seconds)} s"
    )
    lineas = [
        "Campaña preparada; simulación no ejecutada.",
        (
            "Preparar la campaña no garantiza convergencia "
            "ni validez científica equivalente al E1 oficial."
        ),
        "",
        f"scenario_id: {escenario.scenario_id}",
        f"Horizonte: {horizonte}",
        f"contact_plan_id: {plan.contact_plan_id}",
        f"Contactos: {len(plan.contacts)}",
        f"Huella operacional del plan: {contact_plan_fingerprint(plan)}",
        f"Huella documental del plan: {contact_plan_definition_fingerprint(plan)}",
        f"Semilla: {especificacion.seed}",
        f"campaign_identity: {preparada.campaign_identity}",
        f"Corridas: {len(preparada.runs)}",
        "",
    ]
    for run in preparada.runs:
        lineas.append(run.label)
        lineas.append(f"Estrategia: {run.spec.strategy_type}")
        if run.spec.batch_size_events is not None:
            lineas.append(f"Tamaño de lote: {run.spec.batch_size_events}")
        lineas.append(f"configuration_hash: {configuration_hash(run.spec)}")
        lineas.append("")
    return "\n".join(lineas).rstrip("\n")


def format_e2_campaign_inspection(resolved: ResolvedE2Campaign) -> str:
    """Resumen de una campaña E2 ya resuelta.

    Muestra la capacidad, los conteos y las tasas que ya trae la
    resolución. No los vuelve a calcular, no abre archivos, no
    materializa eventos y no ejecuta la simulación.
    """
    preparada = resolved.campaign
    especificacion = preparada.runs[0].spec
    escenario = especificacion.scenario
    workload = especificacion.workload
    plan = resolved.contact_plan_definition
    capacidad = resolved.reference_capacity
    horizonte = (
        "no definido"
        if escenario.horizon_seconds is None
        else f"{_numero(escenario.horizon_seconds)} s"
    )
    duracion = (
        "no definido"
        if workload.duration_seconds is None
        else f"{_numero(workload.duration_seconds)} s"
    )
    lineas = [
        "Campaña E2 preparada; simulación no ejecutada.",
        (
            "La capacidad es nominal del enlace MARS → RELAY; no garantiza entrega "
            "extremo a extremo. La fracción de carga ofrecida no es utilización."
        ),
        (
            "La inspección no certifica convergencia "
            "ni equivalencia con el E2 oficial."
        ),
        "",
        f"scenario_id: {escenario.scenario_id}",
        f"Horizonte: {horizonte}",
        f"contact_plan_id: {plan.contact_plan_id}",
        f"Contactos: {len(plan.contacts)}",
        f"Huella operacional del plan: {contact_plan_fingerprint(plan)}",
        f"Huella documental del plan: {contact_plan_definition_fingerprint(plan)}",
        f"Semilla: {especificacion.seed}",
        f"Inicio de generación: {_numero(workload.start_time_sim)} s",
        f"Duración de generación: {duracion}",
        (
            "Intervalo de capacidad: "
            f"[{_numero(capacidad.interval_start_sim)}, "
            f"{_numero(capacidad.interval_end_sim)})"
        ),
        (
            "Capacidad nominal MARS → RELAY: "
            f"{_numero(capacidad.serialized_capacity_bytes)} bytes"
        ),
        f"Contactos que aportan capacidad: {capacidad.contact_count}",
        (
            "Tamaño canónico Individual: "
            f"{workload.canonical_individual_syncunit_bytes} bytes"
        ),
        f"Tamaño de lote: {_tamano_de_lote(preparada.runs)}",
        f"Timeout ACK: {_numero(especificacion.retry_policy.ack_timeout_seconds)} s",
        f"campaign_identity: {preparada.campaign_identity}",
        f"Corridas: {len(preparada.runs)}",
        "",
    ]
    for run in preparada.runs:
        lineas.extend(_lineas_de_corrida_e2(run))
        lineas.append("")
    return "\n".join(lineas).rstrip("\n")


def format_e3_campaign_inspection(resolved: ResolvedE3Campaign) -> str:
    """Resumen de una campaña E3 ya resuelta.

    Lee la spec de cada corrida y el plan ya resuelto. El intervalo es el
    valor declarado que la resolución conservó: no se obtiene invirtiendo
    la tasa. No abre archivos, no materializa eventos y no ejecuta.
    """
    preparada = resolved.campaign
    especificacion = preparada.runs[0].spec
    escenario = especificacion.scenario
    workload = especificacion.workload
    plan = resolved.contact_plan_definition
    horizonte = (
        "no definido"
        if escenario.horizon_seconds is None
        else f"{_numero(escenario.horizon_seconds)} s"
    )
    conteo = (
        "no definido"
        if workload.max_events is None
        else str(workload.max_events)
    )
    lineas = [
        "Campaña E3 preparada; simulación no ejecutada.",
        (
            "Preparar la campaña no garantiza que la pérdida se active "
            "ni que la recuperación complete. No corresponde a la evidencia oficial RC1."
        ),
        "",
        f"scenario_id: {escenario.scenario_id}",
        f"Horizonte: {horizonte}",
        f"contact_plan_id: {plan.contact_plan_id}",
        f"Contactos: {len(plan.contacts)}",
        f"Huella operacional del plan: {contact_plan_fingerprint(plan)}",
        f"Huella documental del plan: {contact_plan_definition_fingerprint(plan)}",
        f"Semilla: {especificacion.seed}",
        f"Identidad del workload: {workload.workload_id}",
        f"Tipo de evento: {workload.event_type}",
        f"Flujo: {workload.flow}",
        f"Conteo: {conteo}",
        f"Intervalo: {_intervalo_e3(resolved)}",
        f"Tamaño Individual: {workload.canonical_individual_syncunit_bytes} bytes",
        f"Secuencia perdida: {_secuencia_configurada(preparada.runs)}",
        f"campaign_identity: {preparada.campaign_identity}",
        f"Corridas: {len(preparada.runs)}",
        "",
    ]
    for run in preparada.runs:
        lineas.extend(_lineas_de_corrida_e3(run))
        lineas.append("")
    return "\n".join(lineas).rstrip("\n")


def format_configurable_e1_campaign(result: CampaignResult) -> str:
    """Informe de una campaña E1 configurable ya ejecutada.

    Reutiliza el informe de campaña y agrega, por cada corrida con
    resultado, el estado del motor, el backlog y la convergencia.
    No compara estrategias.
    """
    partes = [
        "Campaña E1 configurable. No corresponde a la evidencia oficial RC1.",
        "",
        format_campaign(result),
    ]
    estado = _estado_de_motor(result)
    if estado:
        partes.extend(["", estado])
    return "\n".join(partes)


def format_configurable_e2_campaign(
    resolved: ResolvedE2Campaign, result: CampaignResult
) -> str:
    """Informe de una campaña E2 configurable ya ejecutada.

    La capacidad, la fracción y la estrategia salen de la resolución.
    Los conteos, el estado, el backlog y la convergencia salen del
    resultado. No vuelve a calcular nada y no arma un segundo informe.
    """
    capacidad = resolved.reference_capacity
    lineas = [
        "Campaña E2 configurable. No corresponde a la evidencia oficial RC1.",
        "",
        (
            "La fracción de carga ofrecida no es utilización. La capacidad nominal "
            "del primer enlace no garantiza entrega extremo a extremo."
        ),
        "",
        (
            "Intervalo de capacidad: "
            f"[{_numero(capacidad.interval_start_sim)}, "
            f"{_numero(capacidad.interval_end_sim)})"
        ),
        (
            "Capacidad nominal MARS → RELAY: "
            f"{_numero(capacidad.serialized_capacity_bytes)} bytes"
        ),
        f"Identidad de campaña: {result.campaign_identity}",
        "",
    ]
    bloques = [
        "\n".join(_lineas_de_resultado_e2(planeada, corrida))
        for planeada, corrida in zip(resolved.campaign.runs, result.runs, strict=True)
    ]
    lineas.append("\n\n".join(bloques))
    return "\n".join(lineas)


def format_configurable_e3_campaign(
    resolved: ResolvedE3Campaign, result: CampaignResult
) -> str:
    """Informe de una campaña E3 configurable ya ejecutada.

    La política y el fallo salen de cada spec. Los conteos, el estado,
    el backlog, la convergencia y los episodios salen del resultado, en
    el orden recibido. No evalúa la campaña ni calcula métricas nuevas.
    """
    lineas = [
        "Campaña E3 configurable. No corresponde a la evidencia oficial RC1.",
        "",
        f"Identidad de campaña: {result.campaign_identity}",
        "",
    ]
    bloques = [
        "\n".join(_lineas_de_resultado_e3(planeada, corrida))
        for planeada, corrida in zip(resolved.campaign.runs, result.runs, strict=True)
    ]
    lineas.append("\n\n".join(bloques))
    return "\n".join(lineas)


def format_e3_sensitivity_campaign_inspection(
    resolved: ResolvedE3SensitivityCampaign,
) -> str:
    """Resumen de una sensibilidad de E3 ya resuelta. No ejecuta el motor.

    Reutiliza las líneas de cada corrida E3. El encabezado deja explícito
    que es sensibilidad por parejas, no un cuarto experimento.
    """
    preparada = resolved.campaign
    especificacion = preparada.runs[0].spec
    escenario = especificacion.scenario
    workload = especificacion.workload
    plan = resolved.contact_plan_definition
    horizonte = (
        "no definido"
        if escenario.horizon_seconds is None
        else f"{_numero(escenario.horizon_seconds)} s"
    )
    conteo = (
        "no definido"
        if workload.max_events is None
        else str(workload.max_events)
    )
    lineas = [
        "Sensibilidad de E3 preparada; simulación no ejecutada.",
        (
            "Cada secuencia declarada arma una pareja sender-driven y "
            "receiver-driven, en ese orden, con la misma pérdida. "
            "No es un experimento independiente ni corresponde a la evidencia oficial RC1."
        ),
        "",
        f"scenario_id: {escenario.scenario_id}",
        f"Horizonte: {horizonte}",
        f"contact_plan_id: {plan.contact_plan_id}",
        f"Contactos: {len(plan.contacts)}",
        f"Huella operacional del plan: {contact_plan_fingerprint(plan)}",
        f"Huella documental del plan: {contact_plan_definition_fingerprint(plan)}",
        f"Semilla: {especificacion.seed}",
        f"Identidad del workload: {workload.workload_id}",
        f"Tipo de evento: {workload.event_type}",
        f"Flujo: {workload.flow}",
        f"Conteo: {conteo}",
        f"Intervalo: {_intervalo_e3_sensitivity(resolved)}",
        f"Tamaño Individual: {workload.canonical_individual_syncunit_bytes} bytes",
        f"Secuencias perdidas: {_secuencia_configurada(preparada.runs)}",
        f"campaign_identity: {preparada.campaign_identity}",
        f"Corridas: {len(preparada.runs)}",
        "",
    ]
    for run in preparada.runs:
        lineas.extend(_lineas_de_corrida_e3(run))
        lineas.append("")
    return "\n".join(lineas).rstrip("\n")


def format_configurable_e3_sensitivity_campaign(
    resolved: ResolvedE3SensitivityCampaign, result: CampaignResult
) -> str:
    """Informe de una sensibilidad ya ejecutada, en el orden recibido.

    Muestra secuencia, política, estado del motor, métricas básicas y
    episodios observados con el formato de cada corrida E3. No evalúa
    parejas ni calcula rankings.
    """
    lineas = [
        "Sensibilidad de E3 configurable. No corresponde a la evidencia oficial RC1.",
        "",
        f"Identidad de campaña: {result.campaign_identity}",
        "",
    ]
    bloques = [
        "\n".join(_lineas_de_resultado_e3(planeada, corrida))
        for planeada, corrida in zip(resolved.campaign.runs, result.runs, strict=True)
    ]
    lineas.append("\n\n".join(bloques))
    return "\n".join(lineas)


def format_suite_inspection(suite: ResolvedSuite) -> str:
    """Muestra la suite y el informe de inspección de cada campaña ya resuelta.

    No abre archivos, no ejecuta el motor y no escribe resultados.
    """
    lineas = [
        f"suite_id: {suite.document.suite_id}",
        "Suite preparada; simulación no ejecutada.",
        "Orden:",
    ]
    for indice, entrada in enumerate(suite.entries, start=1):
        lineas.append(f"{indice}. {entrada.experiment_id} {entrada.config_file}")
    informes = [
        _informe_de_inspeccion(entrada.resolved) for entrada in suite.entries
    ]
    return "\n\n".join(["\n".join(lineas), *informes])


def format_suite_execution_summary(
    suite_id: str,
    entries: tuple[SuiteSummaryEntry, ...] | list[SuiteSummaryEntry],
) -> str:
    """Resumen breve de una suite ya ejecutada. No repite métricas ni eventos."""
    lineas = [
        f"suite_id: {suite_id}",
        "Ejecución secuencial terminada. No es evidencia oficial RC1.",
    ]
    for entrada in entries:
        motores = "sí" if entrada.all_runs_engine_completed else "no"
        lineas.append(
            f"{entrada.experiment_id}: campaña {entrada.campaign_status}; "
            f"corridas con resultado {entrada.completed_run_count}/{entrada.run_count}; "
            f"motor COMPLETED en todas: {motores}"
        )
    return "\n".join(lineas)


def _informe_de_inspeccion(
    resolved: (
        ResolvedE1Campaign
        | ResolvedE2Campaign
        | ResolvedE3Campaign
        | ResolvedE3SensitivityCampaign
    ),
) -> str:
    if isinstance(resolved, ResolvedE1Campaign):
        return format_e1_campaign_inspection(resolved)
    if isinstance(resolved, ResolvedE2Campaign):
        return format_e2_campaign_inspection(resolved)
    if isinstance(resolved, ResolvedE3Campaign):
        return format_e3_campaign_inspection(resolved)
    if isinstance(resolved, ResolvedE3SensitivityCampaign):
        return format_e3_sensitivity_campaign_inspection(resolved)
    raise TypeError(
        "la campaña resuelta no es E1, E2, E3 ni sensibilidad de E3: "
        f"{type(resolved).__name__}"
    )


def format_e1_bank_comparison(assessment: dict[str, object]) -> str:
    """Resumen de comparabilidad, sin agregar reglas a la evaluación."""
    if assessment["comparable"] is True:
        return "\n".join(
            (
                "Comparación controlada de agrupación: verificada.",
                (
                    "Se verificaron los factores compartidos y el dataset material "
                    "completo. Esto no implica convergencia ni equivalencia con el "
                    "E1 oficial."
                ),
            )
        )
    inconsistencies = assessment["inconsistencies"]
    return "\n".join(
        (
            "Comparación controlada de agrupación: no verificada.",
            *(f"- {item}" for item in inconsistencies),
        )
    )


def _estado_de_motor(result: CampaignResult) -> str:
    """Estado, backlog y convergencia, en el orden de la campaña."""
    bloques: list[str] = []
    for run in result.runs:
        if run.result is None:
            continue
        bloques.append(
            "\n".join(
                (
                    f"[{run.index + 1}] {run.label}",
                    f"Estado del motor: {run.result.engine_status}",
                    f"Backlog: {run.result.metrics.final_backlog}",
                    "Convergió: " + ("sí" if run.result.metrics.converged else "no"),
                )
            )
        )
    return "\n\n".join(bloques)


def _muestra_recuperacion(result: RunResult) -> bool:
    """La demostración normal no agrega filas de recuperación."""
    return result.recovery_mode != "none" or result.failures_injected > 0


def _etiqueta_recuperacion(recovery_mode: str) -> str:
    if recovery_mode == "none":
        return "ninguna"
    return recovery_mode


def _numero(value: float) -> str:
    texto = f"{value:.6f}".rstrip("0").rstrip(".")
    if "." not in texto:
        return f"{texto}.0"
    return texto


def _fraccion(value: float) -> str:
    """Conserva fracciones cercanas: 0.251 y 0.254 siguen siendo distintas."""
    return format(value, ".16g")


def _tamano_de_lote(runs: tuple[CampaignRunSpec, ...]) -> str:
    for run in runs:
        size = run.spec.batch_size_events
        if size is not None:
            return str(size)
    return "no definido"


def _lineas_de_resultado_e2(
    planeada: CampaignRunSpec, corrida: CampaignRunResult
) -> list[str]:
    """Una corrida ejecutada, en el orden de la campaña.

    La fracción y la estrategia se leen de la spec. El resultado solo
    aporta conteos, estado y, si no terminó, el error ya capturado.
    """
    spec = planeada.spec
    workload = spec.workload
    fraccion = (
        "no definida"
        if workload.offered_load_fraction is None
        else _fraccion(workload.offered_load_fraction)
    )
    lineas = [
        f"[{corrida.index + 1}] {corrida.label}",
        f"Fracción de carga: {fraccion}",
        f"Estrategia: {spec.strategy_type}",
    ]
    if spec.batch_size_events is not None:
        lineas.append(f"Tamaño de lote: {spec.batch_size_events}")
    if corrida.result is None:
        lineas.extend(
            (
                "Estado: falló",
                f"Tipo: {corrida.error_type}",
                f"Mensaje: {corrida.error_message}",
            )
        )
        return lineas
    lineas.extend(
        (
            f"Generados: {corrida.result.events_generated}",
            f"Persistidos: {corrida.result.events_persisted_earth}",
            f"Confirmados: {corrida.result.events_confirmed_mars}",
            f"Estado del motor: {corrida.result.engine_status}",
            f"Backlog: {corrida.result.metrics.final_backlog}",
            "Convergió: " + ("sí" if corrida.result.metrics.converged else "no"),
        )
    )
    return lineas


def _lineas_de_resultado_e3(
    planeada: CampaignRunSpec, corrida: CampaignRunResult
) -> list[str]:
    """Una corrida ejecutada, en el orden recibido.

    La política y el fallo se leen de la spec. Una corrida sin resultado
    muestra el error capturado y no consulta métricas ni episodios.
    """
    spec = planeada.spec
    lineas = [
        f"[{corrida.index + 1}] {corrida.label}",
        f"Política de recuperación: {spec.recovery_policy.value}",
    ]
    lineas.extend(_lineas_del_fallo_configurado(spec.failure_plan))
    if corrida.result is None:
        lineas.extend(
            (
                "Estado: falló",
                f"Tipo: {corrida.error_type}",
                f"Mensaje: {corrida.error_message}",
            )
        )
        return lineas
    metrics = corrida.result.metrics
    lineas.extend(
        (
            f"Generados: {corrida.result.events_generated}",
            f"Persistidos: {corrida.result.events_persisted_earth}",
            f"Confirmados: {corrida.result.events_confirmed_mars}",
            f"Estado del motor: {corrida.result.engine_status}",
            f"Backlog: {metrics.final_backlog}",
            "Convergió: " + ("sí" if metrics.converged else "no"),
        )
    )
    lineas.extend(_lineas_de_episodios_registrados(metrics))
    return lineas


def _lineas_de_episodios_registrados(metrics: ScientificRunMetrics) -> list[str]:
    """Episodios ya presentes en el resultado, en el orden recibido.

    La ausencia de episodios no se lee como pérdida inactiva, como
    ausencia de huecos ni como recuperación lograda.
    """
    episodios = metrics.episodes
    if not episodios:
        return ["Sin episodios registrados"]
    lineas = [f"Episodios registrados: {metrics.recovery.episode_count}"]
    for episodio in episodios:
        lineas.extend(_lineas_de_episodio(episodio))
    return lineas


def _lineas_de_episodio(episodio: RecoveryEpisodeResult) -> list[str]:
    """Campos ya publicados del episodio. Los instantes ausentes siguen vacíos."""
    return [
        f"Secuencia afectada: {episodio.sequence_number}",
        f"Disparador de recuperación: {_texto_presente(episodio.recovery_trigger)}",
        f"Estado del episodio: {episodio.episode_status}",
        f"Pérdida: {_segundos(episodio.loss_at_sim)}",
        f"Observación: {_segundos(episodio.gap_observed_at_sim)}",
        f"Recuperación en Tierra: {_segundos(episodio.earth_recovered_at_sim)}",
        f"Confirmación en Marte: {_segundos(episodio.origin_confirmed_at_sim)}",
    ]


def _texto_presente(value: str | None) -> str:
    if value is None:
        return "no definido"
    return value


def _intervalo_e3(resolved: ResolvedE3Campaign) -> str:
    """Intervalo declarado en la resolución. No invierte la tasa de la spec."""
    experiments = resolved.bank_document.experiments
    if isinstance(experiments, ExperimentBankE3Section):
        return f"{_numero(experiments.e3.event_interval_seconds)} s"
    return "no definido"


def _intervalo_e3_sensitivity(resolved: ResolvedE3SensitivityCampaign) -> str:
    """Intervalo declarado. No invierte la tasa de la spec."""
    experiments = resolved.bank_document.experiments
    if isinstance(experiments, ExperimentBankE3SensitivitySection):
        return f"{_numero(experiments.e3_sensitivity.event_interval_seconds)} s"
    return "no definido"


def _secuencia_configurada(runs: tuple[CampaignRunSpec, ...]) -> str:
    """Secuencia del fallo ya escrito en las specs, en el orden de la campaña."""
    vistas: list[int] = []
    for run in runs:
        for loss in run.spec.failure_plan.silent_forward_delivery_losses:
            if loss.sequence_number not in vistas:
                vistas.append(loss.sequence_number)
    if not vistas:
        return "no definida"
    return ", ".join(str(numero) for numero in vistas)


def _lineas_de_corrida_e3(run: CampaignRunSpec) -> list[str]:
    """Una corrida preparada. El ACK auxiliar se aclara solo en receiver-driven."""
    spec = run.spec
    lineas = [
        run.label,
        f"Política de recuperación: {spec.recovery_policy.value}",
        f"Estrategia: {spec.strategy_type}",
        (
            "Timeout ACK de RetryPolicy: "
            f"{_numero(spec.retry_policy.ack_timeout_seconds)} s"
        ),
    ]
    if spec.recovery_policy.receiver_driven_enabled:
        lineas.append(
            "El ACK de RetryPolicy es auxiliar y no es el timeout del receptor."
        )
    if spec.gap_request_timeout_seconds is not None:
        lineas.append(
            f"Timeout GapRequest: {_numero(spec.gap_request_timeout_seconds)} s"
        )
    lineas.extend(_lineas_del_fallo_configurado(spec.failure_plan))
    lineas.append(f"configuration_hash: {configuration_hash(spec)}")
    return lineas


def _lineas_del_fallo_configurado(plan: FailurePlan) -> list[str]:
    """El fallo está escrito en la spec. Preparar no lo activa."""
    perdidas = plan.silent_forward_delivery_losses
    if not perdidas and not plan.contact_cuts and not plan.ack_drops:
        return ["Sin pérdida configurada"]
    lineas = ["Fallo configurado"]
    for perdida in perdidas:
        lineas.extend(
            (
                f"Fuente: {perdida.source_id}",
                f"Secuencia: {perdida.sequence_number}",
                f"Hop: {perdida.hop}",
                f"Intento: {perdida.telemetry_attempt_number}",
                f"Ocurrencias: {perdida.max_occurrences}",
            )
        )
    return lineas


def _lineas_de_corrida_e2(run: CampaignRunSpec) -> list[str]:
    spec = run.spec
    workload = spec.workload
    fraccion = (
        "no definida"
        if workload.offered_load_fraction is None
        else _fraccion(workload.offered_load_fraction)
    )
    conteo = "no definido" if workload.max_events is None else str(workload.max_events)
    lineas = [
        run.label,
        f"Fracción de carga: {fraccion}",
        f"Estrategia: {spec.strategy_type}",
    ]
    if spec.batch_size_events is not None:
        lineas.append(f"Tamaño de lote: {spec.batch_size_events}")
    lineas.append(f"Conteo derivado: {conteo}")
    lineas.append(
        f"Tasa derivada: {_numero(workload.rate_events_per_second)} eventos/s"
    )
    lineas.append(f"configuration_hash: {configuration_hash(spec)}")
    return lineas


def _fila(etiqueta: str, valor: str) -> str:
    return f"{etiqueta}:  {valor}"


def _cantidad(value: float | None) -> str:
    if value is None:
        return "no definido"
    return format(value, ".12g")


def _segundos(value: float | None) -> str:
    if value is None:
        return "no definido"
    return f"{format(value, '.12g')} s"


def _lineas_recuperacion(metrics: ScientificRunMetrics) -> list[str]:
    """Tiempos del episodio. No los reduce a un único tiempo de recuperación."""
    summary = metrics.recovery
    lineas = [
        _fila("Episodios de recuperación", str(summary.episode_count)),
    ]
    if summary.episode_count == 0:
        return lineas
    lineas.extend(
        [
            _fila("Pérdida → disparo", _segundos(summary.loss_to_trigger_seconds)),
            _fila(
                "Disparo → persistencia en Tierra",
                _segundos(summary.trigger_to_earth_recovery_seconds),
            ),
            _fila(
                "Pérdida → persistencia en Tierra",
                _segundos(summary.loss_to_earth_recovery_seconds),
            ),
            _fila(
                "Persistencia → confirmación en Marte",
                _segundos(summary.earth_recovery_to_origin_confirmation_seconds),
            ),
            _fila(
                "Pérdida → confirmación en Marte",
                _segundos(summary.loss_to_origin_confirmation_seconds),
            ),
            _fila("Hueco observado", _segundos(summary.gap_observed_at_sim)),
            _fila("Timeouts de ACK del emisor", _entero(summary.sender_ack_timeout_count)),
            _fila("Retries del emisor", _entero(summary.sender_retry_attempt_count)),
            _fila(
                "GapRequest lógicos",
                _entero(summary.receiver_gap_request_logical_count),
            ),
            _fila(
                "Intentos de transporte del GapRequest",
                _entero(summary.gap_request_transport_attempt_count),
            ),
            _fila(
                "Reparaciones del receptor",
                _entero(summary.receiver_repair_attempt_count),
            ),
            _fila(
                "Bytes de red de la política",
                _entero(summary.policy_recovery_network_bytes_total),
            ),
        ]
    )
    return lineas


def _entero(value: int | None) -> str:
    if value is None:
        return "no definido"
    return str(value)
