from __future__ import annotations

from core.failure.plan import FailurePlan
from core.metrics.recovery import RecoveryEpisodeResult
from core.metrics.run import ScientificRunMetrics
from experiments.campaign import CampaignResult, CampaignRunResult, CampaignRunSpec
from experiments.contact_plan import (
    ContactPlanDefinition,
    contact_plan_definition_fingerprint,
    contact_plan_fingerprint,
)
from experiments.experiment_bank import (
    ExperimentBankE3Section,
    ExperimentBankE3SensitivitySection,
    ResolvedCampaign,
    ResolvedE1Campaign,
    ResolvedE2Campaign,
    ResolvedE3Campaign,
    ResolvedE3SensitivityCampaign,
)
from experiments.experiment_suite import ResolvedSuite, SuiteSummaryEntry
from experiments.fingerprint import configuration_hash
from experiments.report import format_campaign
from experiments.scenario import Scenario

from cli.utils import fraccion, numero, segundos, texto_presente


def format_e1_campaign_inspection(resolved: ResolvedE1Campaign) -> str:
    """Resumen de una campaña E1 ya resuelta.

    El resolver copia el mismo escenario y la misma semilla en cada corrida.
    No lee archivos, no ejecuta la simulación y no inventa métricas.
    """
    preparada = resolved.campaign
    especificacion = preparada.runs[0].spec
    lineas = [
        "Campaña preparada; simulación no ejecutada.",
        (
            "Preparar la campaña no garantiza convergencia "
            "ni validez científica equivalente al E1 oficial."
        ),
        "",
        *lineas_de_escenario(
            especificacion.scenario,
            resolved.contact_plan_definition,
            especificacion.seed,
        ),
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
    workload = especificacion.workload
    capacidad = resolved.reference_capacity
    duracion = (
        "no definido"
        if workload.duration_seconds is None
        else f"{numero(workload.duration_seconds)} s"
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
        *lineas_de_escenario(
            especificacion.scenario,
            resolved.contact_plan_definition,
            especificacion.seed,
        ),
        f"Inicio de generación: {numero(workload.start_time_sim)} s",
        f"Duración de generación: {duracion}",
        (
            "Intervalo de capacidad: "
            f"[{numero(capacidad.interval_start_sim)}, "
            f"{numero(capacidad.interval_end_sim)})"
        ),
        (
            "Capacidad nominal MARS → RELAY: "
            f"{numero(capacidad.serialized_capacity_bytes)} bytes"
        ),
        f"Contactos que aportan capacidad: {capacidad.contact_count}",
        (
            "Tamaño canónico Individual: "
            f"{workload.canonical_individual_syncunit_bytes} bytes"
        ),
        f"Tamaño de lote: {tamano_de_lote(preparada.runs)}",
        f"Timeout ACK: {numero(especificacion.retry_policy.ack_timeout_seconds)} s",
        f"campaign_identity: {preparada.campaign_identity}",
        f"Corridas: {len(preparada.runs)}",
        "",
    ]
    for run in preparada.runs:
        lineas.extend(lineas_de_corrida_e2(run))
        lineas.append("")
    return "\n".join(lineas).rstrip("\n")


def format_e3_campaign_inspection(resolved: ResolvedE3Campaign) -> str:
    """Resumen de una campaña E3 ya resuelta.

    Lee la spec de cada corrida y el plan ya resuelto. El intervalo es el
    valor declarado que la resolución conservó: no se obtiene invirtiendo
    la tasa. No abre archivos, no materializa eventos y no ejecuta.
    """
    return inspeccion_de_campana_e3(
        resolved,
        titulo="Campaña E3 preparada; simulación no ejecutada.",
        aviso=(
            "Preparar la campaña no garantiza que la pérdida se active "
            "ni que la recuperación complete. No corresponde a la evidencia oficial RC1."
        ),
        etiqueta_secuencia="Secuencia perdida",
    )


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
    estado = estado_de_motor(result)
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
            f"[{numero(capacidad.interval_start_sim)}, "
            f"{numero(capacidad.interval_end_sim)})"
        ),
        (
            "Capacidad nominal MARS → RELAY: "
            f"{numero(capacidad.serialized_capacity_bytes)} bytes"
        ),
        f"Identidad de campaña: {result.campaign_identity}",
        "",
    ]
    bloques = [
        "\n".join(lineas_de_resultado_e2(planeada, corrida))
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
    return informe_configurable_e3(
        resolved,
        result,
        titulo="Campaña E3 configurable. No corresponde a la evidencia oficial RC1.",
    )


def format_e3_sensitivity_campaign_inspection(
    resolved: ResolvedE3SensitivityCampaign,
) -> str:
    """Resumen de una sensibilidad de E3 ya resuelta. No ejecuta el motor.

    Reutiliza las líneas de cada corrida E3. El encabezado deja explícito
    que es sensibilidad por parejas, no un cuarto experimento.
    """
    return inspeccion_de_campana_e3(
        resolved,
        titulo="Sensibilidad de E3 preparada; simulación no ejecutada.",
        aviso=(
            "Cada secuencia declarada arma una pareja sender-driven y "
            "receiver-driven, en ese orden, con la misma pérdida. "
            "No es un experimento independiente ni corresponde a la evidencia oficial RC1."
        ),
        etiqueta_secuencia="Secuencias perdidas",
    )


def format_configurable_e3_sensitivity_campaign(
    resolved: ResolvedE3SensitivityCampaign, result: CampaignResult
) -> str:
    """Informe de una sensibilidad ya ejecutada, en el orden recibido.

    Muestra secuencia, política, estado del motor, métricas básicas y
    episodios observados con el formato de cada corrida E3. No evalúa
    parejas ni calcula rankings.
    """
    return informe_configurable_e3(
        resolved,
        result,
        titulo="Sensibilidad de E3 configurable. No corresponde a la evidencia oficial RC1.",
    )


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
        format_campaign_inspection(entrada.resolved) for entrada in suite.entries
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


def format_campaign_inspection(resolved: ResolvedCampaign) -> str:
    """Informe de inspección de una campaña ya resuelta. No ejecuta el motor."""
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


def estado_de_motor(result: CampaignResult) -> str:
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


def tamano_de_lote(runs: tuple[CampaignRunSpec, ...]) -> str:
    for run in runs:
        size = run.spec.batch_size_events
        if size is not None:
            return str(size)
    return "no definido"


def lineas_de_resultado_e2(
    planeada: CampaignRunSpec, corrida: CampaignRunResult
) -> list[str]:
    """Una corrida ejecutada, en el orden de la campaña.

    La fracción y la estrategia se leen de la spec. El resultado solo
    aporta conteos, estado y, si no terminó, el error ya capturado.
    """
    spec = planeada.spec
    workload = spec.workload
    fraccion_texto = (
        "no definida"
        if workload.offered_load_fraction is None
        else fraccion(workload.offered_load_fraction)
    )
    lineas = [
        f"[{corrida.index + 1}] {corrida.label}",
        f"Fracción de carga: {fraccion_texto}",
        f"Estrategia: {spec.strategy_type}",
    ]
    if spec.batch_size_events is not None:
        lineas.append(f"Tamaño de lote: {spec.batch_size_events}")
    if corrida.result is None:
        lineas.extend(lineas_de_corrida_fallida(corrida))
        return lineas
    lineas.extend(lineas_de_conteos(corrida))
    return lineas


def lineas_de_resultado_e3(
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
    lineas.extend(lineas_del_fallo_configurado(spec.failure_plan))
    if corrida.result is None:
        lineas.extend(lineas_de_corrida_fallida(corrida))
        return lineas
    lineas.extend(lineas_de_conteos(corrida))
    lineas.extend(lineas_de_episodios_registrados(corrida.result.metrics))
    return lineas


def lineas_de_episodios_registrados(metrics: ScientificRunMetrics) -> list[str]:
    """Episodios ya presentes en el resultado, en el orden recibido.

    La ausencia de episodios no se lee como pérdida inactiva, como
    ausencia de huecos ni como recuperación lograda.
    """
    episodios = metrics.episodes
    if not episodios:
        return ["Sin episodios registrados"]
    lineas = [f"Episodios registrados: {metrics.recovery.episode_count}"]
    for episodio in episodios:
        lineas.extend(lineas_de_episodio(episodio))
    return lineas


def lineas_de_episodio(episodio: RecoveryEpisodeResult) -> list[str]:
    """Campos ya publicados del episodio. Los instantes ausentes siguen vacíos."""
    return [
        f"Secuencia afectada: {episodio.sequence_number}",
        f"Disparador de recuperación: {texto_presente(episodio.recovery_trigger)}",
        f"Estado del episodio: {episodio.episode_status}",
        f"Pérdida: {segundos(episodio.loss_at_sim)}",
        f"Observación: {segundos(episodio.gap_observed_at_sim)}",
        f"Recuperación en Tierra: {segundos(episodio.earth_recovered_at_sim)}",
        f"Confirmación en Marte: {segundos(episodio.origin_confirmed_at_sim)}",
    ]


def lineas_de_escenario(
    escenario: Scenario,
    plan: ContactPlanDefinition,
    semilla: int,
) -> list[str]:
    horizonte = (
        "no definido"
        if escenario.horizon_seconds is None
        else f"{numero(escenario.horizon_seconds)} s"
    )
    return [
        f"scenario_id: {escenario.scenario_id}",
        f"Horizonte: {horizonte}",
        f"contact_plan_id: {plan.contact_plan_id}",
        f"Contactos: {len(plan.contacts)}",
        f"Huella operacional del plan: {contact_plan_fingerprint(plan)}",
        f"Huella documental del plan: {contact_plan_definition_fingerprint(plan)}",
        f"Semilla: {semilla}",
    ]


def intervalo_declarado(
    resolved: ResolvedE3Campaign | ResolvedE3SensitivityCampaign,
) -> str:
    """Intervalo declarado en la resolución. No invierte la tasa de la spec."""
    experiments = resolved.bank_document.experiments
    if isinstance(experiments, ExperimentBankE3Section):
        intervalo = experiments.e3.event_interval_seconds
    elif isinstance(experiments, ExperimentBankE3SensitivitySection):
        intervalo = experiments.e3_sensitivity.event_interval_seconds
    else:
        return "no definido"
    return f"{numero(intervalo)} s"


def inspeccion_de_campana_e3(
    resolved: ResolvedE3Campaign | ResolvedE3SensitivityCampaign,
    *,
    titulo: str,
    aviso: str,
    etiqueta_secuencia: str,
) -> str:
    """Inspección compartida de E3 y de su sensibilidad. No ejecuta el motor."""
    preparada = resolved.campaign
    especificacion = preparada.runs[0].spec
    workload = especificacion.workload
    conteo = (
        "no definido"
        if workload.max_events is None
        else str(workload.max_events)
    )
    lineas = [
        titulo,
        aviso,
        "",
        *lineas_de_escenario(
            especificacion.scenario,
            resolved.contact_plan_definition,
            especificacion.seed,
        ),
        f"Identidad del workload: {workload.workload_id}",
        f"Tipo de evento: {workload.event_type}",
        f"Flujo: {workload.flow}",
        f"Conteo: {conteo}",
        f"Intervalo: {intervalo_declarado(resolved)}",
        f"Tamaño Individual: {workload.canonical_individual_syncunit_bytes} bytes",
        f"{etiqueta_secuencia}: {secuencia_configurada(preparada.runs)}",
        f"campaign_identity: {preparada.campaign_identity}",
        f"Corridas: {len(preparada.runs)}",
        "",
    ]
    for run in preparada.runs:
        lineas.extend(lineas_de_corrida_e3(run))
        lineas.append("")
    return "\n".join(lineas).rstrip("\n")


def informe_configurable_e3(
    resolved: ResolvedE3Campaign | ResolvedE3SensitivityCampaign,
    result: CampaignResult,
    *,
    titulo: str,
) -> str:
    """Informe ya ejecutado de E3 o de su sensibilidad, en el orden recibido."""
    lineas = [
        titulo,
        "",
        f"Identidad de campaña: {result.campaign_identity}",
        "",
    ]
    bloques = [
        "\n".join(lineas_de_resultado_e3(planeada, corrida))
        for planeada, corrida in zip(resolved.campaign.runs, result.runs, strict=True)
    ]
    lineas.append("\n\n".join(bloques))
    return "\n".join(lineas)


def lineas_de_corrida_fallida(corrida: CampaignRunResult) -> list[str]:
    """Error ya capturado. No consulta métricas ni episodios."""
    return [
        "Estado: falló",
        f"Tipo: {corrida.error_type}",
        f"Mensaje: {corrida.error_message}",
    ]


def lineas_de_conteos(corrida: CampaignRunResult) -> list[str]:
    """Conteos, estado, backlog y convergencia de una corrida con resultado."""
    resultado = corrida.result
    if resultado is None:
        raise ValueError("la corrida no tiene resultado")
    return [
        f"Generados: {resultado.events_generated}",
        f"Persistidos: {resultado.events_persisted_earth}",
        f"Confirmados: {resultado.events_confirmed_mars}",
        f"Estado del motor: {resultado.engine_status}",
        f"Backlog: {resultado.metrics.final_backlog}",
        "Convergió: " + ("sí" if resultado.metrics.converged else "no"),
    ]


def secuencia_configurada(runs: tuple[CampaignRunSpec, ...]) -> str:
    """Secuencia del fallo ya escrito en las specs, en el orden de la campaña."""
    vistas: list[int] = []
    for run in runs:
        for loss in run.spec.failure_plan.silent_forward_delivery_losses:
            if loss.sequence_number not in vistas:
                vistas.append(loss.sequence_number)
    if not vistas:
        return "no definida"
    return ", ".join(str(secuencia) for secuencia in vistas)


def lineas_de_corrida_e3(run: CampaignRunSpec) -> list[str]:
    """Una corrida preparada. El ACK auxiliar se aclara solo en receiver-driven."""
    spec = run.spec
    lineas = [
        run.label,
        f"Política de recuperación: {spec.recovery_policy.value}",
        f"Estrategia: {spec.strategy_type}",
        (
            "Timeout ACK de RetryPolicy: "
            f"{numero(spec.retry_policy.ack_timeout_seconds)} s"
        ),
    ]
    if spec.recovery_policy.receiver_driven_enabled:
        lineas.append(
            "El ACK de RetryPolicy es auxiliar y no es el timeout del receptor."
        )
    if spec.gap_request_timeout_seconds is not None:
        lineas.append(
            f"Timeout GapRequest: {numero(spec.gap_request_timeout_seconds)} s"
        )
    lineas.extend(lineas_del_fallo_configurado(spec.failure_plan))
    lineas.append(f"configuration_hash: {configuration_hash(spec)}")
    return lineas


def lineas_del_fallo_configurado(plan: FailurePlan) -> list[str]:
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


def lineas_de_corrida_e2(run: CampaignRunSpec) -> list[str]:
    spec = run.spec
    workload = spec.workload
    fraccion_texto = (
        "no definida"
        if workload.offered_load_fraction is None
        else fraccion(workload.offered_load_fraction)
    )
    conteo = "no definido" if workload.max_events is None else str(workload.max_events)
    lineas = [
        run.label,
        f"Fracción de carga: {fraccion_texto}",
        f"Estrategia: {spec.strategy_type}",
    ]
    if spec.batch_size_events is not None:
        lineas.append(f"Tamaño de lote: {spec.batch_size_events}")
    lineas.append(f"Conteo derivado: {conteo}")
    lineas.append(
        f"Tasa derivada: {numero(workload.rate_events_per_second)} eventos/s"
    )
    lineas.append(f"configuration_hash: {configuration_hash(spec)}")
    return lineas
