import { EvidenceSchemaError } from "../errors";
import {
  LAB_METRICS,
  OMITTED_METRICS,
  buildDesign,
  uiReference,
  type AuditRow,
  type LabConfig,
  type LabEpisodeField,
  type LabExperiment,
  type LabFailure,
  type LabRun,
  type LabStored,
  type LabWorkload,
} from "../../domain/lab";

/**
 * Arma la inspección de laboratorio desde el paquete ya cargado.
 * No calcula métricas: copia hojas almacenadas.
 */

export function buildLabExperiment(experimentId: string, packageData: unknown): LabExperiment {
  const root = asRecord(packageData, "paquete");
  const manifest = asRecord(root.campaign_manifest, "campaign_manifest");
  const reproducibility = asRecord(root.reproducibility, "reproducibility");
  const runsValue = asArray(manifest.runs, "campaign_manifest.runs");
  const runs = runsValue.map((item, index) => readLabRun(experimentId, item, index));
  const audit = auditMetrics(runsValue);
  return {
    evidenceSchemaVersion: scalarText(root.evidence_schema_version),
    manifestSchemaVersion: scalarText(manifest.manifest_schema_version),
    sourceState: requireText(manifest, "source_state", "campaign_manifest"),
    hashAlgorithm: requireText(reproducibility, "hash_algorithm", "reproducibility"),
    reproNote: requireText(reproducibility, "note", "reproducibility"),
    datasetFingerprintFields: stringList(
      reproducibility.dataset_fingerprint_fields,
      "reproducibility.dataset_fingerprint_fields",
    ),
    executionIdentityInputs: stringList(
      reproducibility.execution_identity_inputs,
      "reproducibility.execution_identity_inputs",
    ),
    datasetIdentityInputs: stringList(
      reproducibility.dataset_identity_inputs,
      "reproducibility.dataset_identity_inputs",
    ),
    wallClockInIdentity: requireBool(
      reproducibility,
      "wall_clock_in_scientific_identity",
      "reproducibility",
    ),
    traceLevelIsFactor: requireBool(
      reproducibility,
      "trace_level_is_scientific_factor",
      "reproducibility",
    ),
    runs,
    design: buildDesign(experimentId, runs),
    audit,
  };
}

function readLabRun(experimentId: string, value: unknown, index: number): LabRun {
  const run = asRecord(value, `runs[${index}]`);
  const manifest = asRecord(run.manifest, `runs[${index}].manifest`);
  const metrics = asRecord(manifest.metrics, `runs[${index}].manifest.metrics`);
  const config = readConfig(manifest, index);
  const stored: Record<string, LabStored> = {};
  for (const def of LAB_METRICS) {
    stored[def.id] = def.source === "metrics" ? readMetric(metrics, def.path) : readRunField(run, manifest, def.path);
  }
  return {
    uiReference: uiReference(experimentId, index),
    referenceKind: "UI_REFERENCE",
    index,
    label: requireText(run, "label", `runs[${index}]`),
    completed: requireBool(run, "completed", `runs[${index}]`),
    failed: requireBool(run, "failed", `runs[${index}]`),
    executionIdentity: requireText(run, "execution_identity", `runs[${index}]`),
    datasetIdentity: requireText(run, "dataset_identity", `runs[${index}]`),
    configurationHash: requireText(run, "configuration_hash", `runs[${index}]`),
    datasetFingerprint: requireText(run, "dataset_fingerprint", `runs[${index}]`),
    config,
    metrics: stored,
    episode: readEpisode(metrics, index),
    source: run,
  };
}

function readRunField(
  run: Record<string, unknown>,
  manifest: Record<string, unknown>,
  path: string,
): LabStored {
  if (path === "seed") {
    return { status: "stored", path: "manifest.seed", value: requireNumber(manifest, "seed", "manifest") };
  }
  if (path === "scenario_id") {
    return { status: "stored", path: "manifest.scenario_id", value: requireText(manifest, "scenario_id", "manifest") };
  }
  const value = run[path];
  if (typeof value === "string") {
    return { status: "stored", path, value };
  }
  return { status: "missing", path };
}

function readConfig(manifest: Record<string, unknown>, index: number): LabConfig {
  const path = `runs[${index}].manifest`;
  const workload = readWorkload(manifest, path);
  const retry = asRecord(manifest.retry_policy, `${path}.retry_policy`);
  const terminal = asRecord(manifest.terminal, `${path}.terminal`);
  return {
    scenarioId: requireText(manifest, "scenario_id", path),
    workloadId: requireText(manifest, "workload_id", path),
    strategyType: requireText(manifest, "strategy_type", path),
    batchSizeEvents: requireNullableNumber(manifest, "batch_size_events", path),
    seed: requireNumber(manifest, "seed", path),
    offeredLoadFraction: workload.offeredLoadFraction,
    recoveryPolicy: requireText(manifest, "recovery_policy", path),
    stopPolicy: requireText(manifest, "stop_policy", path),
    horizonSeconds: requireNumber(manifest, "horizon_seconds", path),
    traceLevel: requireText(manifest, "trace_level", path),
    ackTimeoutSeconds: requireNumber(retry, "ack_timeout_seconds", `${path}.retry_policy`),
    gapRequestTimeoutSeconds: requireNullableNumber(manifest, "gap_request_timeout_seconds", path),
    datasetEventCount: requireNumber(manifest, "dataset_event_count", path),
    sourceState: requireText(manifest, "source_state", path),
    engineStatus: requireText(terminal, "engine_status", `${path}.terminal`),
    workload,
    failure: readFailure(manifest.failure_plan, `${path}.failure_plan`),
  };
}

function readWorkload(manifest: Record<string, unknown>, path: string): LabWorkload {
  const workload = asRecord(manifest.workload, `${path}.workload`);
  return {
    workloadId: requireText(workload, "workload_id", `${path}.workload`),
    eventType: requireText(workload, "event_type", `${path}.workload`),
    flow: requireText(workload, "flow", `${path}.workload`),
    maxEvents: requireNumber(workload, "max_events", `${path}.workload`),
    rateEventsPerSecond: requireNumber(workload, "rate_events_per_second", `${path}.workload`),
    priority: requireText(workload, "priority", `${path}.workload`),
    sourceId: requireText(workload, "source_id", `${path}.workload`),
    canonicalBytes: requireNumber(workload, "canonical_individual_syncunit_bytes", `${path}.workload`),
    startTimeSim: requireNumber(workload, "start_time_sim", `${path}.workload`),
    offeredLoadFraction: requireNullableNumber(workload, "offered_load_fraction", `${path}.workload`),
  };
}

function readFailure(value: unknown, path: string): LabFailure {
  const plan = asRecord(value, path);
  const losses = asArray(plan.silent_forward_delivery_losses, `${path}.silent_forward_delivery_losses`);
  const drops = asArray(plan.ack_drops, `${path}.ack_drops`);
  const cuts = asArray(plan.contact_cuts, `${path}.contact_cuts`);
  const sequences = losses.map((item, index) => {
    const loss = asRecord(item, `${path}.silent_forward_delivery_losses[${index}]`);
    return requireNumber(loss, "sequence_number", `${path}.silent_forward_delivery_losses[${index}]`);
  });
  return {
    enabled: losses.length > 0 || drops.length > 0 || cuts.length > 0,
    silentLosses: losses.length,
    sequences,
    ackDrops: drops.length,
    contactCuts: cuts.length,
  };
}

function readEpisode(metrics: Record<string, unknown>, index: number): LabEpisodeField[] | null {
  const recovery = metrics.recovery;
  if (!recovery || typeof recovery !== "object" || Array.isArray(recovery)) {
    return null;
  }
  const episodes = (recovery as Record<string, unknown>).episodes;
  if (!Array.isArray(episodes) || episodes.length === 0) {
    return null;
  }
  const episode = episodes[0];
  if (episodes.length !== 1 || !episode || typeof episode !== "object" || Array.isArray(episode)) {
    throw new EvidenceSchemaError(`runs[${index}] tiene un episodio que el laboratorio no puede listar`);
  }
  return Object.keys(episode as Record<string, unknown>).map((key) => {
    const value = (episode as Record<string, unknown>)[key];
    return {
      key,
      path: `metrics.recovery.episodes[0].${key}`,
      value: scalarOrNull(value),
    };
  });
}

function readMetric(metrics: Record<string, unknown>, path: string): LabStored {
  const parts = path.split(".");
  let current: unknown = metrics;
  for (const part of parts) {
    if (!current || typeof current !== "object" || Array.isArray(current)) {
      return { status: "missing", path: `metrics.${path}` };
    }
    const record = current as Record<string, unknown>;
    if (!Object.prototype.hasOwnProperty.call(record, part)) {
      return { status: "missing", path: `metrics.${path}` };
    }
    current = record[part];
  }
  if (current === null || typeof current === "number" || typeof current === "boolean" || typeof current === "string") {
    if (typeof current === "number" && !Number.isFinite(current)) {
      return { status: "missing", path: `metrics.${path}` };
    }
    return { status: "stored", path: `metrics.${path}`, value: current };
  }
  return { status: "missing", path: `metrics.${path}` };
}

function auditMetrics(runs: unknown[]): AuditRow[] {
  const leaves = new Set<string>();
  const episodeKeys = new Set<string>();
  for (const item of runs) {
    const run = asRecord(item, "runs");
    const manifest = asRecord(run.manifest, "manifest");
    const metrics = asRecord(manifest.metrics, "metrics");
    collectLeaves(metrics, "", leaves, episodeKeys);
  }
  const catalog = new Set(LAB_METRICS.filter((item) => item.source === "metrics").map((item) => item.path));
  const rows: AuditRow[] = [];
  for (const path of [...leaves].sort()) {
    if (path === "recovery.episodes") {
      rows.push({
        field: "metrics.recovery.episodes",
        shown: true,
        surface: "Detalle · tabla de episodio",
        reason: "La lista no se aplana en el catálogo.",
      });
      continue;
    }
    if (catalog.has(path)) {
      rows.push({
        field: `metrics.${path}`,
        shown: true,
        surface: "Catálogo · detalle · gráficos si aplica",
        reason: "",
      });
      continue;
    }
    const reason = OMITTED_METRICS[path];
    rows.push({
      field: `metrics.${path}`,
      shown: false,
      surface: "Raw JSON",
      reason: reason ?? "Campo de metrics sin lectura en el catálogo.",
    });
  }
  for (const key of [...episodeKeys].sort()) {
    rows.push({
      field: `metrics.recovery.episodes[].${key}`,
      shown: true,
      surface: "Tabla de episodio",
      reason: "Escalar del episodio. No se promociona a métrica nueva de campaña.",
    });
  }
  return rows;
}

function collectLeaves(
  value: unknown,
  prefix: string,
  leaves: Set<string>,
  episodeKeys: Set<string>,
): void {
  if (!value || typeof value !== "object") {
    if (prefix) {
      leaves.add(prefix);
    }
    return;
  }
  if (Array.isArray(value)) {
    if (prefix) {
      leaves.add(prefix);
    }
    if (prefix === "recovery.episodes") {
      for (const item of value) {
        if (item && typeof item === "object" && !Array.isArray(item)) {
          for (const key of Object.keys(item as Record<string, unknown>)) {
            episodeKeys.add(key);
          }
        }
      }
    }
    return;
  }
  for (const [key, child] of Object.entries(value)) {
    collectLeaves(child, prefix ? `${prefix}.${key}` : key, leaves, episodeKeys);
  }
}

function scalarOrNull(value: unknown): number | boolean | string | null {
  if (value === null || typeof value === "number" || typeof value === "boolean" || typeof value === "string") {
    return value;
  }
  return null;
}

function scalarText(value: unknown): string {
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  throw new EvidenceSchemaError("version de schema ausente");
}

function asRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new EvidenceSchemaError(`${path} debe ser un objeto`);
  }
  return value as Record<string, unknown>;
}

function asArray(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new EvidenceSchemaError(`${path} debe ser una lista`);
  }
  return value;
}

function requireText(record: Record<string, unknown>, key: string, path: string): string {
  const value = record[key];
  if (typeof value !== "string" || value.length === 0) {
    throw new EvidenceSchemaError(`${path}.${key} debe ser texto`);
  }
  return value;
}

function requireBool(record: Record<string, unknown>, key: string, path: string): boolean {
  const value = record[key];
  if (typeof value !== "boolean") {
    throw new EvidenceSchemaError(`${path}.${key} debe ser booleano`);
  }
  return value;
}

function requireNumber(record: Record<string, unknown>, key: string, path: string): number {
  const value = record[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new EvidenceSchemaError(`${path}.${key} debe ser un número`);
  }
  return value;
}

function requireNullableNumber(
  record: Record<string, unknown>,
  key: string,
  path: string,
): number | null {
  const value = record[key];
  if (value === null) {
    return null;
  }
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new EvidenceSchemaError(`${path}.${key} debe ser un número o null`);
  }
  return value;
}

function stringList(value: unknown, path: string): string[] {
  const list = asArray(value, path);
  return list.map((item, index) => {
    if (typeof item !== "string") {
      throw new EvidenceSchemaError(`${path}[${index}] debe ser texto`);
    }
    return item;
  });
}
