import { loadLabel, metricDef, presentStored, storedNumber, strategyLabel, type LabRun } from "../../domain/lab";

export type ColumnId =
  | "label"
  | "index"
  | "strategy"
  | "batch"
  | "load"
  | "policy"
  | "failure"
  | "sequence"
  | "seed"
  | "completed"
  | "failed"
  | "converged"
  | "generated"
  | "persisted"
  | "confirmed"
  | "backlog"
  | "gaps"
  | "completeness"
  | "confirmation"
  | "coverage"
  | "p50"
  | "p95"
  | "ttc"
  | "utilization"
  | "sync"
  | "telemetry"
  | "transport"
  | "hash"
  | "fingerprint";

export type PresetId = "basico" | "estado" | "tiempo" | "trafico" | "repro" | "todas";

export const PRESET_LABEL: Record<PresetId, string> = {
  basico: "Básico",
  estado: "Estado",
  tiempo: "Temporalidad",
  trafico: "Tráfico",
  repro: "Reproducibilidad",
  todas: "Todas",
};

const ALL: ColumnId[] = [
  "label",
  "index",
  "strategy",
  "batch",
  "load",
  "policy",
  "failure",
  "sequence",
  "seed",
  "completed",
  "failed",
  "converged",
  "generated",
  "persisted",
  "confirmed",
  "backlog",
  "gaps",
  "completeness",
  "confirmation",
  "coverage",
  "p50",
  "p95",
  "ttc",
  "utilization",
  "sync",
  "telemetry",
  "transport",
  "hash",
  "fingerprint",
];

export const PRESETS: Record<PresetId, readonly ColumnId[]> = {
  basico: ["label", "index", "strategy", "batch", "load", "policy", "failure", "sequence", "seed"],
  estado: [
    "label",
    "completed",
    "failed",
    "converged",
    "generated",
    "persisted",
    "confirmed",
    "backlog",
    "gaps",
    "completeness",
    "confirmation",
  ],
  tiempo: ["label", "ttc", "coverage", "p50", "p95"],
  trafico: ["label", "sync", "telemetry", "transport", "utilization"],
  repro: ["label", "seed", "hash", "fingerprint"],
  todas: ALL,
};

export function parsePreset(value: string | null): PresetId {
  if (value && value in PRESETS) {
    return value as PresetId;
  }
  return "basico";
}

interface Column {
  id: ColumnId;
  header: string;
  metric?: string;
  help?: "gap" | "offeredLoad" | "contactUtilization" | "freshnessCoverage" | "ttc";
  text: (run: LabRun) => string;
  title: (run: LabRun) => string;
  sortValue: (run: LabRun) => number | string | null;
  available: (runs: readonly LabRun[]) => boolean;
}

function metricText(id: string, run: LabRun): { text: string; title: string } {
  return presentStored(metricDef(id), run.metrics[id]);
}

function numericSort(id: string, run: LabRun): number | null {
  return storedNumber(run, id);
}

function presentColumn(id: string, header: string, help?: Column["help"]): Column {
  return {
    id: headerId(id),
    header,
    metric: id,
    help,
    text: (run) => metricText(id, run).text,
    title: (run) => metricText(id, run).title,
    sortValue: (run) => numericSort(id, run) ?? (run.metrics[id]?.status === "stored" ? -1 : null),
    available: (runs) => runs.some((run) => run.metrics[id]?.status === "stored" && run.metrics[id]?.value !== null),
  };
}

function headerId(metricId: string): ColumnId {
  const map: Record<string, ColumnId> = {
    converged: "converged",
    generated: "generated",
    earth_persisted_unique: "persisted",
    confirmed: "confirmed",
    backlog: "backlog",
    gaps_count: "gaps",
    completeness: "completeness",
    confirmation_ratio: "confirmation",
    freshness_coverage: "coverage",
    "freshness.p50_seconds": "p50",
    "freshness.p95_seconds": "p95",
    time_to_convergence_seconds: "ttc",
    "contacts.contact_utilization_weighted": "utilization",
    sync_units_created: "sync",
    "traffic.telemetry_syncunit_bytes_created": "telemetry",
    "traffic.total_transport_application_bytes": "transport",
    seed: "seed",
  };
  return map[metricId] ?? "label";
}

export const COLUMNS: readonly Column[] = [
  {
    id: "label",
    header: "Corrida",
    text: (run) => run.label,
    title: (run) => `UI_REFERENCE ${run.uiReference}`,
    sortValue: (run) => run.index,
    available: () => true,
  },
  {
    id: "index",
    header: "Índice",
    text: (run) => String(run.index),
    title: (run) => run.uiReference,
    sortValue: (run) => run.index,
    available: () => true,
  },
  {
    id: "strategy",
    header: "Estrategia",
    text: (run) => strategyLabel(run.config.strategyType, run.config.batchSizeEvents),
    title: (run) => run.config.strategyType,
    sortValue: (run) => run.config.strategyType,
    available: (runs) => new Set(runs.map((run) => run.config.strategyType)).size > 1 || runs.length > 0,
  },
  {
    id: "batch",
    header: "Batch",
    text: (run) => (run.config.batchSizeEvents === null ? "—" : String(run.config.batchSizeEvents)),
    title: (run) => (run.config.batchSizeEvents === null ? "null" : String(run.config.batchSizeEvents)),
    sortValue: (run) => run.config.batchSizeEvents,
    available: (runs) => runs.some((run) => run.config.batchSizeEvents !== null),
  },
  {
    id: "load",
    header: "Carga ofrecida",
    help: "offeredLoad",
    text: (run) => loadLabel(run.config.offeredLoadFraction),
    title: (run) =>
      run.config.offeredLoadFraction === null ? "null" : String(run.config.offeredLoadFraction),
    sortValue: (run) => run.config.offeredLoadFraction,
    available: (runs) => runs.some((run) => run.config.offeredLoadFraction !== null),
  },
  {
    id: "policy",
    header: "Política",
    text: (run) => run.config.recoveryPolicy,
    title: (run) => run.config.recoveryPolicy,
    sortValue: (run) => run.config.recoveryPolicy,
    available: (runs) => runs.some((run) => run.config.recoveryPolicy.length > 0),
  },
  {
    id: "failure",
    header: "Falla",
    text: (run) => (run.config.failure.enabled ? "on" : "off"),
    title: (run) => (run.config.failure.enabled ? "on" : "off"),
    sortValue: (run) => (run.config.failure.enabled ? 1 : 0),
    available: () => true,
  },
  {
    id: "sequence",
    header: "Secuencia",
    text: (run) => (run.config.failure.sequences.length === 0 ? "—" : run.config.failure.sequences.join(", ")),
    title: (run) => run.config.failure.sequences.join(", ") || "sin pérdida almacenada",
    sortValue: (run) => run.config.failure.sequences[0] ?? null,
    available: (runs) => runs.some((run) => run.config.failure.sequences.length > 0),
  },
  {
    id: "seed",
    header: "Semilla",
    text: (run) => String(run.config.seed),
    title: (run) => String(run.config.seed),
    sortValue: (run) => run.config.seed,
    available: () => true,
  },
  {
    id: "completed",
    header: "Completada",
    text: (run) => (run.completed ? "sí" : "no"),
    title: (run) => String(run.completed),
    sortValue: (run) => (run.completed ? 1 : 0),
    available: () => true,
  },
  {
    id: "failed",
    header: "Fallida",
    text: (run) => (run.failed ? "sí" : "no"),
    title: (run) => String(run.failed),
    sortValue: (run) => (run.failed ? 1 : 0),
    available: () => true,
  },
  presentColumn("converged", "Convergió"),
  presentColumn("generated", "Generados"),
  presentColumn("earth_persisted_unique", "Persistidos en Tierra"),
  presentColumn("confirmed", "Confirmados"),
  presentColumn("backlog", "Backlog"),
  presentColumn("gaps_count", "Gaps", "gap"),
  presentColumn("completeness", "Completitud"),
  presentColumn("confirmation_ratio", "Confirmación"),
  presentColumn("freshness_coverage", "Cobertura de frescura", "freshnessCoverage"),
  presentColumn("freshness.p50_seconds", "Frescura p50"),
  presentColumn("freshness.p95_seconds", "Frescura p95"),
  {
    ...presentColumn("time_to_convergence_seconds", "TTC", "ttc"),
    available: (runs) => runs.some((run) => run.metrics.time_to_convergence_seconds?.status === "stored"),
  },
  presentColumn("contacts.contact_utilization_weighted", "Utilización de contacto", "contactUtilization"),
  presentColumn("sync_units_created", "SyncUnits"),
  presentColumn("traffic.telemetry_syncunit_bytes_created", "Bytes de telemetría"),
  presentColumn("traffic.total_transport_application_bytes", "Bytes de transporte"),
  {
    id: "hash",
    header: "Configuration hash",
    text: (run) => run.configurationHash,
    title: (run) => run.configurationHash,
    sortValue: (run) => run.configurationHash,
    available: () => true,
  },
  {
    id: "fingerprint",
    header: "Dataset fingerprint",
    text: (run) => run.datasetFingerprint,
    title: (run) => run.datasetFingerprint,
    sortValue: (run) => run.datasetFingerprint,
    available: () => true,
  },
];

export function columnsFor(preset: PresetId, runs: readonly LabRun[]): Column[] {
  const wanted = new Set(PRESETS[preset]);
  return COLUMNS.filter((column) => wanted.has(column.id) && column.available(runs));
}

export function columnById(id: ColumnId): Column {
  const column = COLUMNS.find((item) => item.id === id);
  if (!column) {
    throw new Error(`columna desconocida: ${id}`);
  }
  return column;
}
