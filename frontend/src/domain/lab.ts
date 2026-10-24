/**
 * Lectura de laboratorio sobre campos ya almacenados en RC1.
 * Una referencia de corrida de este módulo es UI_REFERENCE.
 * No es un identificador científico de corrida.
 */

import { formatBytes, formatCount, formatMegabytes, formatPercent, formatSecondsDetail } from "./metricFormat";
import { formatSimSeconds } from "./scenarioFormat";

export type UiReferenceKind = "UI_REFERENCE";

export type MetricGroup =
  | "estado"
  | "temporalidad"
  | "trafico"
  | "recovery"
  | "contactos"
  | "identidad";

export type MetricKind = "count" | "bytes" | "ratio" | "seconds" | "instant" | "boolean" | "text";

export type MetricSource = "metrics" | "run";

export interface LabMetricDef {
  id: string;
  path: string;
  source: MetricSource;
  group: MetricGroup;
  kind: MetricKind;
  name: string;
  unit: string;
  description: string;
}

export type LabStored =
  | { status: "missing"; path: string }
  | { status: "stored"; path: string; value: number | boolean | string | null };

export interface LabWorkload {
  workloadId: string;
  eventType: string;
  flow: string;
  maxEvents: number;
  rateEventsPerSecond: number;
  priority: string;
  sourceId: string;
  canonicalBytes: number;
  startTimeSim: number;
  offeredLoadFraction: number | null;
}

export interface LabFailure {
  enabled: boolean;
  silentLosses: number;
  sequences: number[];
  ackDrops: number;
  contactCuts: number;
}

export interface LabConfig {
  scenarioId: string;
  workloadId: string;
  strategyType: string;
  batchSizeEvents: number | null;
  seed: number;
  offeredLoadFraction: number | null;
  recoveryPolicy: string;
  stopPolicy: string;
  horizonSeconds: number;
  traceLevel: string;
  ackTimeoutSeconds: number;
  gapRequestTimeoutSeconds: number | null;
  datasetEventCount: number;
  sourceState: string;
  engineStatus: string;
  workload: LabWorkload;
  failure: LabFailure;
}

export interface LabEpisodeField {
  key: string;
  path: string;
  value: number | boolean | string | null;
}

export interface LabRun {
  uiReference: string;
  referenceKind: UiReferenceKind;
  index: number;
  label: string;
  completed: boolean;
  failed: boolean;
  executionIdentity: string;
  datasetIdentity: string;
  configurationHash: string;
  datasetFingerprint: string;
  config: LabConfig;
  metrics: Record<string, LabStored>;
  episode: LabEpisodeField[] | null;
  /** Objeto de la corrida ya cargado. No es una copia del paquete. */
  source: Record<string, unknown>;
}

export interface DesignFactor {
  name: string;
  levels: string[];
}

export interface DesignControl {
  name: string;
  value: string;
}

export interface DesignBlock {
  factors: DesignFactor[];
  controls: DesignControl[];
  note: string | null;
}

export interface AuditRow {
  field: string;
  shown: boolean;
  surface: string;
  reason: string;
}

export interface LabExperiment {
  evidenceSchemaVersion: string;
  manifestSchemaVersion: string;
  sourceState: string;
  hashAlgorithm: string;
  reproNote: string;
  datasetFingerprintFields: string[];
  executionIdentityInputs: string[];
  datasetIdentityInputs: string[];
  wallClockInIdentity: boolean;
  traceLevelIsFactor: boolean;
  runs: LabRun[];
  design: DesignBlock;
  audit: AuditRow[];
}

export const GROUP_LABEL: Record<MetricGroup, string> = {
  estado: "Estado",
  temporalidad: "Temporalidad",
  trafico: "Tráfico",
  recovery: "Recovery",
  contactos: "Contactos",
  identidad: "Identidad",
};

export const GROUP_ORDER: readonly MetricGroup[] = [
  "estado",
  "temporalidad",
  "trafico",
  "recovery",
  "contactos",
  "identidad",
];

const TRAFFIC_CREATED =
  "Bytes de aplicación al crear la SyncUnit. No incluyen hops ni cabeceras de red.";
const TRAFFIC_HOP =
  "Bytes de aplicación que ese hop serializó, incluida una porción interrumpida. Un payload que cruza dos hops cuenta en cada uno.";

function metric(
  path: string,
  group: MetricGroup,
  kind: MetricKind,
  name: string,
  unit: string,
  description: string,
  source: MetricSource = "metrics",
): LabMetricDef {
  return { id: path, path, source, group, kind, name, unit, description };
}

export const LAB_METRICS: readonly LabMetricDef[] = [
  metric("generated", "estado", "count", "Generados", "eventos", "Eventos de telemetría generados en Marte."),
  metric(
    "earth_persisted_unique",
    "estado",
    "count",
    "Persistidos en Tierra",
    "eventos",
    "Eventos distintos ya persistidos en Tierra.",
  ),
  metric(
    "confirmed",
    "estado",
    "count",
    "Confirmados en origen",
    "eventos",
    "Eventos cuyo ApplicationAck ya fue aplicado en Marte.",
  ),
  metric(
    "backlog",
    "estado",
    "count",
    "Backlog",
    "eventos",
    "Trabajo todavía no confirmado en Marte: generados menos confirmados.",
  ),
  metric(
    "final_backlog",
    "estado",
    "count",
    "Backlog final",
    "eventos",
    "Backlog al cierre de la corrida. En RC1 coincide con backlog; se muestra el campo almacenado.",
  ),
  metric(
    "not_persisted_on_earth",
    "estado",
    "count",
    "No persistido en Tierra (M)",
    "eventos",
    "Generados que Tierra todavía no persistió.",
  ),
  metric(
    "persisted_on_earth_but_unconfirmed",
    "estado",
    "count",
    "Persistido sin confirmar (U)",
    "eventos",
    "Persistidos en Tierra cuyo ACK todavía no confirmó Marte.",
  ),
  metric(
    "gaps_count",
    "estado",
    "count",
    "Gaps",
    "huecos",
    "Huecos internos observados. gaps = 0 no implica completitud.",
  ),
  metric(
    "completeness",
    "estado",
    "ratio",
    "Completitud en Tierra",
    "fracción",
    "Persistencia única en Tierra sobre los eventos generados.",
  ),
  metric(
    "confirmation_ratio",
    "estado",
    "ratio",
    "Confirmación en origen",
    "fracción",
    "Fracción de eventos generados cuyo ApplicationAck fue aplicado en Marte.",
  ),
  metric(
    "not_persisted_ratio",
    "estado",
    "ratio",
    "Fracción no persistida",
    "fracción",
    "Fracción almacenada de generados que Tierra no persistió. No se recalcula en el visor.",
  ),
  metric(
    "persisted_unconfirmed_ratio",
    "estado",
    "ratio",
    "Fracción persistida sin confirmar",
    "fracción",
    "Fracción almacenada de generados que están en Tierra y Marte todavía no confirmó.",
  ),
  metric(
    "duplicates_received",
    "estado",
    "count",
    "Duplicados recibidos",
    "eventos",
    "Recepciones duplicadas registradas en la corrida.",
  ),
  metric(
    "duplicates_stored",
    "estado",
    "count",
    "Duplicados almacenados",
    "eventos",
    "Duplicados que además quedaron almacenados.",
  ),
  metric(
    "retry_attempts_total",
    "estado",
    "count",
    "Reintentos",
    "intentos",
    "Intentos de retransmisión contabilizados en la corrida.",
  ),
  metric(
    "converged",
    "estado",
    "boolean",
    "Convergió",
    "booleano",
    "Verdadero solo si hay carga, backlog cero y ningún hueco interno.",
  ),
  metric("freshness.count", "temporalidad", "count", "Muestra de frescura", "eventos", "Eventos persistidos que entran en la distribución de frescura."),
  metric(
    "freshness_coverage",
    "temporalidad",
    "ratio",
    "Cobertura de frescura",
    "fracción",
    "Muestra de frescura sobre generados. No rellena los percentiles de los eventos que no llegaron a Tierra.",
  ),
  metric("freshness.min_seconds", "temporalidad", "seconds", "Frescura mínima", "s", "Mínimo almacenado de la muestra de frescura."),
  metric("freshness.p50_seconds", "temporalidad", "seconds", "Frescura p50", "s", "Percentil 50 de la muestra de frescura."),
  metric("freshness.p95_seconds", "temporalidad", "seconds", "Frescura p95", "s", "Percentil 95 de la muestra de frescura."),
  metric("freshness.max_seconds", "temporalidad", "seconds", "Frescura máxima", "s", "Máximo almacenado de la muestra de frescura."),
  metric("freshness.mean_seconds", "temporalidad", "seconds", "Frescura media", "s", "Media almacenada de la muestra de frescura."),
  metric(
    "time_to_convergence_seconds",
    "temporalidad",
    "seconds",
    "Tiempo hasta convergencia (TTC)",
    "s",
    "Segundos desde la referencia de convergencia hasta el instante en que la corrida converge. null: no convergió dentro del criterio observado.",
  ),
  metric(
    "converged_at_sim",
    "temporalidad",
    "instant",
    "Instante de convergencia",
    "s sim",
    "Instante de simulación en que la corrida quedó convergida. null si no convergió.",
  ),
  metric(
    "convergence_reference_at_sim",
    "temporalidad",
    "instant",
    "Referencia de convergencia",
    "s sim",
    "Instante después del cual no se espera más telemetría de la carga. Es el máximo generated_at_sim ya ocurrido.",
  ),
  metric("time_sim", "temporalidad", "instant", "Tiempo de simulación", "s sim", "Reloj de simulación al cierre de la corrida."),
  metric(
    "scenario_completed_at_sim",
    "temporalidad",
    "instant",
    "Fin de escenario",
    "s sim",
    "Instante almacenado al completar el escenario.",
  ),
  metric(
    "view_age_seconds",
    "temporalidad",
    "seconds",
    "Edad de la vista",
    "s",
    "Edad de la telemetría más nueva visible en Tierra: time_sim menos el máximo generated_at_sim ya persistido. No es frescura.",
  ),
  metric("sync_units_created", "trafico", "count", "SyncUnits", "unidades", "SyncUnits de telemetría creadas en la corrida."),
  metric(
    "traffic.telemetry_syncunit_bytes_created",
    "trafico",
    "bytes",
    "Bytes de telemetría creados",
    "B",
    TRAFFIC_CREATED,
  ),
  metric(
    "traffic.telemetry_initial_syncunit_bytes_created",
    "trafico",
    "bytes",
    "Bytes iniciales de telemetría",
    "B",
    "Bytes de telemetría del primer intento, al crear la unidad.",
  ),
  metric(
    "traffic.telemetry_retry_syncunit_bytes_created",
    "trafico",
    "bytes",
    "Bytes de reintento de telemetría",
    "B",
    "Bytes de telemetría creados en reintentos.",
  ),
  metric(
    "traffic.ack_syncunit_bytes_created",
    "trafico",
    "bytes",
    "Bytes de ACK creados",
    "B",
    "Bytes de ApplicationAck al crear la unidad, sin hops.",
  ),
  metric(
    "traffic.telemetry_transport_bytes",
    "trafico",
    "bytes",
    "Transporte de telemetría",
    "B",
    "Bytes de telemetría serializados en los hops.",
  ),
  metric(
    "traffic.ack_transport_bytes",
    "trafico",
    "bytes",
    "Transporte de ACK",
    "B",
    "Bytes de ApplicationAck serializados en los hops.",
  ),
  metric(
    "traffic.total_transport_application_bytes",
    "trafico",
    "bytes",
    "Transporte total de aplicación",
    "B",
    "Suma almacenada de bytes_transmitted de todos los hops. No se reconstruye en el visor.",
  ),
  metric("traffic.mars_to_relay_bytes", "trafico", "bytes", "Marte → relé", "B", TRAFFIC_HOP),
  metric("traffic.relay_to_earth_bytes", "trafico", "bytes", "Relé → Tierra", "B", TRAFFIC_HOP),
  metric("traffic.earth_to_relay_bytes", "trafico", "bytes", "Tierra → relé", "B", TRAFFIC_HOP),
  metric("traffic.relay_to_mars_bytes", "trafico", "bytes", "Relé → Marte", "B", TRAFFIC_HOP),
  metric(
    "traffic.forward_bytes_transmitted",
    "trafico",
    "bytes",
    "Forward almacenado",
    "B",
    "Campo almacenado de bytes hacia Tierra. El visor no lo vuelve a sumar.",
  ),
  metric(
    "traffic.reverse_bytes_transmitted",
    "trafico",
    "bytes",
    "Reverse almacenado",
    "B",
    "Campo almacenado de bytes de retorno. El visor no lo vuelve a sumar.",
  ),
  metric(
    "traffic.retry_transport_bytes",
    "trafico",
    "bytes",
    "Transporte de reintento",
    "B",
    "Hops con attempt_number mayor que 1. El primer intento no entra.",
  ),
  metric(
    "traffic.interrupted_transport_bytes",
    "trafico",
    "bytes",
    "Transporte interrumpido",
    "B",
    "Bytes de hops cortados.",
  ),
  metric(
    "recovery.episode_count",
    "recovery",
    "count",
    "Episodios",
    "episodios",
    "Episodios de recuperación escritos en la corrida.",
  ),
  metric(
    "recovery.loss_to_trigger_seconds",
    "recovery",
    "seconds",
    "Pérdida → disparo",
    "s",
    "Latencia almacenada desde la pérdida hasta el disparo de la política.",
  ),
  metric(
    "recovery.trigger_to_earth_recovery_seconds",
    "recovery",
    "seconds",
    "Disparo → Tierra",
    "s",
    "Latencia almacenada desde el disparo hasta la recuperación en Tierra.",
  ),
  metric(
    "recovery.loss_to_earth_recovery_seconds",
    "recovery",
    "seconds",
    "Pérdida → Tierra",
    "s",
    "Latencia almacenada desde la pérdida hasta la recuperación en Tierra.",
  ),
  metric(
    "recovery.earth_recovery_to_origin_confirmation_seconds",
    "recovery",
    "seconds",
    "Tierra → origen",
    "s",
    "Latencia almacenada desde la recuperación en Tierra hasta la confirmación en Marte.",
  ),
  metric(
    "recovery.loss_to_origin_confirmation_seconds",
    "recovery",
    "seconds",
    "Pérdida → origen",
    "s",
    "Latencia almacenada desde la pérdida hasta la confirmación en Marte.",
  ),
  metric(
    "recovery.sender_ack_timeout_count",
    "recovery",
    "count",
    "Timeouts del emisor",
    "eventos",
    "Timeouts de ACK del sender contabilizados en el resumen de recuperación.",
  ),
  metric(
    "recovery.sender_retry_attempt_count",
    "recovery",
    "count",
    "Reintentos del emisor",
    "intentos",
    "Reintentos del sender contabilizados en el resumen de recuperación.",
  ),
  metric(
    "recovery.receiver_gap_request_logical_count",
    "recovery",
    "count",
    "GapRequests",
    "pedidos",
    "GapRequests lógicos del receptor.",
  ),
  metric(
    "recovery.receiver_repair_attempt_count",
    "recovery",
    "count",
    "Intentos de reparación",
    "intentos",
    "Intentos de reparación del receptor.",
  ),
  metric(
    "recovery.policy_recovery_forward_bytes",
    "recovery",
    "bytes",
    "Recovery forward",
    "B",
    "Bytes forward de la política de recuperación. No incluyen el intento perdido común.",
  ),
  metric(
    "recovery.policy_recovery_reverse_bytes",
    "recovery",
    "bytes",
    "Recovery reverse",
    "B",
    "Bytes reverse de la política de recuperación.",
  ),
  metric(
    "recovery.policy_recovery_network_bytes_total",
    "recovery",
    "bytes",
    "Recovery total",
    "B",
    "Total de red de la política, tal como está almacenado.",
  ),
  metric("recovery.recovered_count", "recovery", "count", "Recuperados", "eventos", "Eventos recuperados según el resumen de la corrida."),
  metric(
    "recovery.confirmed_count",
    "recovery",
    "count",
    "Confirmados del episodio",
    "eventos",
    "Confirmaciones contadas en el resumen de recuperación.",
  ),
  metric(
    "recovery.duplicates_received_after_loss",
    "recovery",
    "count",
    "Duplicados recibidos tras la pérdida",
    "eventos",
    "Duplicados recibidos después de la pérdida, en el resumen de recuperación.",
  ),
  metric(
    "recovery.duplicates_stored_after_loss",
    "recovery",
    "count",
    "Duplicados almacenados tras la pérdida",
    "eventos",
    "Duplicados almacenados después de la pérdida, en el resumen de recuperación.",
  ),
  metric(
    "recovery.gap_observed_at_sim",
    "recovery",
    "instant",
    "Gap observado",
    "s sim",
    "Instante de simulación en que Tierra observa el hueco, en el resumen de recuperación.",
  ),
  metric(
    "recovery.gap_request_transport_attempt_count",
    "recovery",
    "count",
    "Intentos de transporte del GapRequest",
    "intentos",
    "Intentos de transporte del pedido de hueco.",
  ),
  metric("contacts.contacts_total", "contactos", "count", "Contactos del plan", "contactos", "Ventanas definidas en el plan."),
  metric("contacts.contacts_used", "contactos", "count", "Contactos usados", "contactos", "Ventanas con bytes de aplicación transmitidos."),
  metric("contacts.contacts_forced_cut", "contactos", "count", "Cortes forzados", "contactos", "Ventanas cortadas por el plan de fallas."),
  metric(
    "contacts.contact_utilization_mean",
    "contactos",
    "ratio",
    "Utilización media",
    "fracción",
    "Media de utilización de las ventanas ya iniciadas. No es la carga ofrecida.",
  ),
  metric(
    "contacts.contact_utilization_weighted",
    "contactos",
    "ratio",
    "Utilización ponderada",
    "fracción",
    "Utilización ponderada por la capacidad de las ventanas ya iniciadas. No es la carga ofrecida.",
  ),
  metric(
    "contacts.forward_contact_utilization_weighted",
    "contactos",
    "ratio",
    "Utilización forward",
    "fracción",
    "Utilización ponderada de los contactos hacia Tierra.",
  ),
  metric(
    "contacts.reverse_contact_utilization_weighted",
    "contactos",
    "ratio",
    "Utilización reverse",
    "fracción",
    "Utilización ponderada de los contactos de retorno.",
  ),
  metric(
    "execution_identity",
    "identidad",
    "text",
    "execution_identity",
    "UUID",
    "Identifica una combinación reproducible. No es necesariamente una fila única de la campaña.",
    "run",
  ),
  metric(
    "dataset_identity",
    "identidad",
    "text",
    "dataset_identity",
    "UUID",
    "Identidad del dataset materializado.",
    "run",
  ),
  metric(
    "configuration_hash",
    "identidad",
    "text",
    "configuration_hash",
    "sha256",
    "Resume la especificación de la corrida. No incluye software_version, source_revision ni source_state.",
    "run",
  ),
  metric(
    "dataset_fingerprint",
    "identidad",
    "text",
    "dataset_fingerprint",
    "sha256",
    "Huella del dataset materializado.",
    "run",
  ),
  metric("seed", "identidad", "count", "Semilla", "entero", "Semilla almacenada de la corrida.", "run"),
  metric("scenario_id", "identidad", "text", "Escenario", "id", "scenario_id almacenado.", "run"),
];

export const METRIC_BY_ID: ReadonlyMap<string, LabMetricDef> = new Map(
  LAB_METRICS.map((item) => [item.id, item]),
);

/** Hojas de metrics que duplican otro campo ya mostrado. Quedan en el JSON. */
export const OMITTED_METRICS: Readonly<Record<string, string>> = {
  confirmed_ratio: "Mismo cociente almacenado que confirmation_ratio.",
  freshness_sample_count: "Duplica freshness.count.",
  freshness_min_seconds: "Duplica freshness.min_seconds.",
  freshness_p50_seconds: "Duplica freshness.p50_seconds.",
  freshness_p95_seconds: "Duplica freshness.p95_seconds.",
  freshness_max_seconds: "Duplica freshness.max_seconds.",
  freshness_mean_seconds: "Duplica freshness.mean_seconds.",
  "traffic.application_bytes_transmitted_total":
    "Mismo total almacenado que traffic.total_transport_application_bytes.",
};

export const EPISODE_LABEL: Readonly<Record<string, string>> = {
  episode_id: "Id de episodio",
  episode_status: "Estado",
  event_id: "Evento",
  sequence_number: "Secuencia",
  source_id: "Fuente",
  hop: "Hop",
  failure_type: "Tipo de falla",
  failure_occurrence: "Ocurrencia",
  recovery_policy: "Política",
  recovery_trigger: "Disparo",
  telemetry_attempt_number: "Intento de telemetría",
  earth_recovered: "Tierra recuperó",
  origin_confirmed: "Origen confirmó",
  loss_at_sim: "Pérdida",
  gap_observed_at_sim: "Gap observado",
  gap_closed_at_sim: "Gap cerrado",
  recovery_triggered_at_sim: "Disparo",
  first_recovery_data_departed_mars_at_sim: "Salida desde Marte",
  earth_recovered_at_sim: "Recuperación en Tierra",
  origin_confirmed_at_sim: "Confirmación en origen",
  loss_to_trigger_seconds: "Pérdida → disparo",
  loss_to_gap_observed_seconds: "Pérdida → gap",
  loss_to_earth_recovery_seconds: "Pérdida → Tierra",
  loss_to_origin_confirmation_seconds: "Pérdida → origen",
  trigger_to_earth_recovery_seconds: "Disparo → Tierra",
  earth_recovery_to_origin_confirmation_seconds: "Tierra → origen",
  sender_ack_timeout_count: "Timeouts del emisor",
  sender_retry_attempt_count: "Reintentos del emisor",
  receiver_gap_request_logical_count: "GapRequests",
  receiver_repair_attempt_count: "Intentos de reparación",
  gap_request_transport_attempt_count: "Intentos de transporte del GapRequest",
  policy_recovery_forward_bytes: "Recovery forward",
  policy_recovery_reverse_bytes: "Recovery reverse",
  policy_recovery_network_bytes: "Recovery de red del episodio",
  common_lost_attempt_bytes_mars_relay: "Intento perdido Marte → relé",
  common_lost_attempt_bytes_relay_earth: "Intento perdido relé → Tierra",
  recovery_data_bytes_mars_relay: "Dato de recuperación Marte → relé",
  recovery_data_bytes_relay_earth: "Dato de recuperación relé → Tierra",
  recovery_ack_bytes_earth_relay: "ACK de recuperación Tierra → relé",
  recovery_ack_bytes_relay_mars: "ACK de recuperación relé → Marte",
  gap_request_bytes_earth_relay: "GapRequest Tierra → relé",
  gap_request_bytes_relay_mars: "GapRequest relé → Marte",
  duplicates_received_after_loss: "Duplicados recibidos tras la pérdida",
  duplicates_stored_after_loss: "Duplicados almacenados tras la pérdida",
};

export const TRAFFIC_SECTIONS: readonly { title: string; ids: readonly string[] }[] = [
  {
    title: "Telemetría",
    ids: [
      "sync_units_created",
      "traffic.telemetry_syncunit_bytes_created",
      "traffic.telemetry_initial_syncunit_bytes_created",
      "traffic.telemetry_retry_syncunit_bytes_created",
      "traffic.telemetry_transport_bytes",
    ],
  },
  {
    title: "Control",
    ids: ["traffic.ack_syncunit_bytes_created", "traffic.ack_transport_bytes"],
  },
  {
    title: "Por hop",
    ids: [
      "traffic.mars_to_relay_bytes",
      "traffic.relay_to_earth_bytes",
      "traffic.earth_to_relay_bytes",
      "traffic.relay_to_mars_bytes",
    ],
  },
  {
    title: "Sentido almacenado",
    ids: ["traffic.forward_bytes_transmitted", "traffic.reverse_bytes_transmitted"],
  },
  {
    title: "Total",
    ids: ["traffic.total_transport_application_bytes"],
  },
  {
    title: "Reintento e interrupción",
    ids: ["traffic.retry_transport_bytes", "traffic.interrupted_transport_bytes"],
  },
];

export const GLOSSARY = {
  syncunit: {
    label: "SyncUnit",
    text: "Unidad de sincronización de la aplicación. El conteo y los bytes creados salen del artefacto.",
  },
  applicationAck: {
    label: "ApplicationAck",
    text: "Confirmación de aplicación. Confirma en Marte que Tierra persistió el evento.",
  },
  backlog: {
    label: "backlog",
    text: "Eventos generados que Marte todavía no tiene confirmados.",
  },
  gap: {
    label: "gap",
    text: "Hueco interno de secuencia. Cero huecos no alcanza para decir que la carga está completa.",
  },
  offeredLoad: {
    label: "offered load",
    text: "Fracción de carga de telemetría ofrecida respecto de la capacidad de referencia. No es la utilización de contacto.",
  },
  contactUtilization: {
    label: "contact utilization",
    text: "Bytes usados sobre la capacidad de las ventanas ya iniciadas. Es otra variable, distinta de la carga ofrecida.",
  },
  freshnessCoverage: {
    label: "freshness coverage",
    text: "Cuántos eventos generados entran en los percentiles de frescura. Si es menor que 1, p50 y p95 no describen el dataset completo.",
  },
  ttc: {
    label: "TTC",
    text: "Tiempo hasta convergencia. Si el artefacto guarda null, la corrida no convergió dentro del criterio observado.",
  },
  mu: {
    label: "M/U",
    text: "M es not_persisted_on_earth. U es persisted_on_earth_but_unconfirmed. El backlog total es el campo backlog.",
  },
  sender: {
    label: "sender-driven",
    text: "Marte reenvía cuando vence el timeout de ACK. No observa el hueco en Tierra.",
  },
  receiver: {
    label: "receiver-driven",
    text: "Tierra pide la secuencia ausente con un GapRequest.",
  },
} as const;

export type GlossaryId = keyof typeof GLOSSARY;

export function uiReference(experimentId: string, index: number): string {
  return `${experimentId}:${index}`;
}

export function strategyLabel(strategy: string | null, batch: number | null): string {
  if (strategy === "individual") {
    return "Individual";
  }
  if (strategy === "fixed_batch" && batch !== null) {
    return `Batch${batch}`;
  }
  if (batch !== null) {
    return `Batch${batch}`;
  }
  return strategy ?? "—";
}

export function loadLabel(fraction: number | null): string {
  if (fraction === null) {
    return "—";
  }
  const percent = Math.round(fraction * 1000) / 10;
  const text = Number.isInteger(percent)
    ? percent.toLocaleString("es-AR", { maximumFractionDigits: 0 })
    : percent.toLocaleString("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${text} %`;
}

export function presentStored(def: LabMetricDef, stored: LabStored | undefined): { text: string; title: string } {
  if (!stored || stored.status === "missing") {
    return { text: "No disponible", title: def.path };
  }
  if (stored.value === null) {
    if (def.id === "time_to_convergence_seconds" || def.id === "converged_at_sim") {
      return { text: "No convergió dentro del criterio observado", title: "null" };
    }
    return { text: "—", title: "null" };
  }
  if (typeof stored.value === "boolean") {
    return { text: stored.value ? "sí" : "no", title: String(stored.value) };
  }
  if (typeof stored.value === "string") {
    return { text: stored.value, title: stored.value };
  }
  const raw = String(stored.value);
  switch (def.kind) {
    case "count":
      return { text: formatCount(stored.value), title: raw };
    case "bytes":
      return {
        text: stored.value >= 1_000_000 ? formatMegabytes(stored.value) : formatBytes(stored.value),
        title: `${formatBytes(stored.value)} · ${raw} B`,
      };
    case "ratio":
      return { text: formatPercent(stored.value, 2), title: raw };
    case "instant":
      return { text: formatSimSeconds(stored.value), title: `${raw} s` };
    case "seconds":
      return { text: formatSecondsDetail(stored.value), title: `${raw} s` };
    default:
      return { text: raw, title: raw };
  }
}

export function storedNumber(run: LabRun, id: string): number | null {
  const item = run.metrics[id];
  if (!item || item.status !== "stored" || typeof item.value !== "number") {
    return null;
  }
  return item.value;
}

export function metricDef(id: string): LabMetricDef {
  const def = METRIC_BY_ID.get(id);
  if (!def) {
    throw new Error(`métrica de laboratorio desconocida: ${id}`);
  }
  return def;
}

export function catalogStoredCount(lab: LabExperiment): { present: number; numeric: number } {
  const scientific = LAB_METRICS.filter((item) => item.group !== "identidad");
  const present = scientific.filter((item) =>
    lab.runs.some((run) => run.metrics[item.id]?.status === "stored"),
  ).length;
  const numeric = scientific.filter((item) =>
    lab.runs.some((run) => storedNumber(run, item.id) !== null),
  ).length;
  return { present, numeric };
}

export function findLabRun(lab: LabExperiment, experimentId: string, runRef: string): LabRun | undefined {
  if (/^\d+$/.test(runRef)) {
    const index = Number(runRef);
    return lab.runs.find((run) => run.index === index);
  }
  const direct = lab.runs.find((run) => run.uiReference === runRef);
  if (direct) {
    return direct;
  }
  const prefixed = lab.runs.find((run) => run.uiReference === `${experimentId}:${runRef}`);
  if (prefixed) {
    return prefixed;
  }
  const byHash = lab.runs.filter((run) => run.configurationHash === runRef);
  return byHash.length === 1 ? byHash[0] : undefined;
}

export function runJsonDocument(source: Record<string, unknown>): unknown {
  return {
    index: source.index,
    label: source.label,
    completed: source.completed,
    failed: source.failed,
    configuration_hash: source.configuration_hash,
    dataset_fingerprint: source.dataset_fingerprint,
    dataset_identity: source.dataset_identity,
    execution_identity: source.execution_identity,
    manifest: source.manifest,
  };
}

export function defenseHref(experimentId: string): string {
  if (experimentId === "e3-sensitivity") {
    return "/defensa/e3?vista=sensitivity";
  }
  if (experimentId === "e1" || experimentId === "e2" || experimentId === "e3") {
    return `/defensa/${experimentId}`;
  }
  return "/defensa/problem";
}

export function buildDesign(experimentId: string, runs: readonly LabRun[]): DesignBlock {
  const controls = sharedControls(runs);
  if (experimentId === "e1") {
    return {
      factors: [{ name: "Granularidad", levels: unique(runs.map((run) => strategyLabel(run.config.strategyType, run.config.batchSizeEvents))) }],
      controls,
      note: null,
    };
  }
  if (experimentId === "e2") {
    return {
      factors: [
        { name: "Carga ofrecida", levels: unique(runs.map((run) => loadLabel(run.config.offeredLoadFraction))) },
        { name: "Estrategia", levels: unique(runs.map((run) => strategyLabel(run.config.strategyType, run.config.batchSizeEvents))) },
      ],
      controls,
      note: null,
    };
  }
  if (experimentId === "e3") {
    return {
      factors: [
        { name: "Política", levels: unique(runs.map((run) => run.config.recoveryPolicy)) },
        { name: "Falla", levels: unique(runs.map((run) => (run.config.failure.enabled ? "on" : "off"))) },
        { name: "Celda", levels: unique(runs.map((run) => run.label)) },
      ],
      controls,
      note: failureNote(runs),
    };
  }
  return {
    factors: [
      {
        name: "Secuencia objetivo",
        levels: unique(runs.map((run) => run.config.failure.sequences.join(", ") || "—")),
      },
      { name: "Política", levels: unique(runs.map((run) => run.config.recoveryPolicy)) },
    ],
    controls,
    note: "3 posiciones deterministas. No es un promedio ni un experimento E4.",
  };
}

function failureNote(runs: readonly LabRun[]): string | null {
  const withLoss = runs.filter((run) => run.config.failure.sequences.length > 0);
  if (withLoss.length === 0) {
    return null;
  }
  const sequences = unique(withLoss.map((run) => run.config.failure.sequences.join(", ")));
  return `Pérdida silenciosa almacenada en las celdas con falla: secuencia ${sequences.join(" · ")}.`;
}

function sharedControls(runs: readonly LabRun[]): DesignControl[] {
  const controls: DesignControl[] = [];
  const scenario = same(runs.map((run) => run.config.scenarioId));
  const seed = same(runs.map((run) => String(run.config.seed)));
  const horizon = same(runs.map((run) => String(run.config.horizonSeconds)));
  const stop = same(runs.map((run) => run.config.stopPolicy));
  const workload = same(runs.map((run) => run.config.workloadId));
  const events = same(runs.map((run) => String(run.config.datasetEventCount)));
  const trace = same(runs.map((run) => run.config.traceLevel));
  const policy = same(runs.map((run) => run.config.recoveryPolicy));
  const failure = same(runs.map((run) => (run.config.failure.enabled ? "on" : "off")));
  const load = same(runs.map((run) => (run.config.offeredLoadFraction === null ? "null" : loadLabel(run.config.offeredLoadFraction))));
  push(controls, "Escenario", scenario);
  push(controls, "Semilla", seed);
  push(controls, "Horizonte", horizon === null ? null : `${Number(horizon).toLocaleString("es-AR")} s`);
  push(controls, "Stop policy", stop);
  push(controls, "Workload", workload);
  push(controls, "Eventos del dataset", events);
  push(controls, "Trace level", trace);
  if (policy && runs.length > 0 && new Set(runs.map((run) => run.config.recoveryPolicy)).size === 1) {
    push(controls, "Política de recuperación", policy);
  }
  if (failure === "off") {
    push(controls, "Falla", "off");
  }
  if (load === "null") {
    push(controls, "Carga ofrecida", "null en el artefacto");
  }
  return controls;
}

function push(target: DesignControl[], name: string, value: string | null): void {
  if (value !== null) {
    target.push({ name, value });
  }
}

function same(values: string[]): string | null {
  if (values.length === 0) {
    return null;
  }
  return values.every((item) => item === values[0]) ? values[0] : null;
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}
