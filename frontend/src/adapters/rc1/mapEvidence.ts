import type { EvidenceIdentity, EvidenceLocator, ExperimentDetail, RunMeasurement, RunSummary } from "../../domain";
import type { StoredRunMetrics } from "../../domain/metrics";
import type { StoredRecovery } from "../../domain/recovery";
import { buildLabExperiment } from "./readLab";
import { readStoredRecovery } from "./readRecovery";
import { gapsForRun, readStoredMetrics } from "./readStoredMetrics";
import { EvidenceIdentityError, EvidenceSchemaError } from "../errors";
import {
  RC1_SOFTWARE_VERSION,
  RC1_SOURCE_REVISION,
  RC1_TARGETS,
  type Rc1Target,
} from "./catalog";

interface ProvenanceRun {
  index: number;
  label: string;
  configurationHash: string;
  datasetFingerprint: string;
  datasetIdentity: string;
  executionIdentity: string;
  completed: boolean;
  failed: boolean;
}

interface ProvenanceRecord {
  campaignId: string;
  campaignIdentity: string;
  family: string;
  role: string;
  evidenceFile: string;
  status: string;
  softwareVersion: string;
  sourceRevision: string;
  runs: ProvenanceRun[];
}

interface ParsedRun {
  index: number;
  label: string;
  completed: boolean;
  failed: boolean;
  configurationHash: string;
  datasetFingerprint: string;
  datasetIdentity: string;
  executionIdentity: string;
  seed: number;
  strategyType: string;
  batchSizeEvents: number | null;
  offeredLoadFraction: number | null;
  recoveryPolicy: string;
  failureEnabled: boolean;
  targetSequences: number[];
  metrics: StoredRunMetrics | null;
  metricPaths: string[];
  recovery: StoredRecovery | null;
}

interface ParsedPackage {
  family: string;
  role: string;
  campaignId: string;
  campaignIdentity: string;
  description: string;
  status: string;
  runCount: number;
  softwareVersion: string;
  sourceRevision: string;
  runs: ParsedRun[];
  source: Record<string, unknown>;
}

export function mapE1Evidence(
  packageData: unknown,
  provenanceData: unknown,
  packagePath: string,
  provenancePath: string,
): ExperimentDetail {
  return mapOfficial(targetOf("e1"), packageData, provenanceData, packagePath, provenancePath);
}

export function mapE2Evidence(
  packageData: unknown,
  provenanceData: unknown,
  packagePath: string,
  provenancePath: string,
): ExperimentDetail {
  const detail = mapOfficial(
    targetOf("e2"),
    packageData,
    provenanceData,
    packagePath,
    provenancePath,
  );
  for (const run of detail.runs) {
    if (run.offeredLoadFraction === null) {
      throw new EvidenceSchemaError(
        `${packagePath}: la corrida ${run.index} no trae offered_load_fraction`,
      );
    }
  }
  return detail;
}

export function mapE3Evidence(
  packageData: unknown,
  provenanceData: unknown,
  packagePath: string,
  provenancePath: string,
): ExperimentDetail {
  return mapOfficial(targetOf("e3"), packageData, provenanceData, packagePath, provenancePath);
}

export function mapE3SensitivityEvidence(
  packageData: unknown,
  packagePath: string,
): ExperimentDetail {
  const target = targetOf("e3-sensitivity");
  assertPath(packagePath, target.packageLogicalPath);
  const parsed = readPackage(packageData, packagePath);
  assertPackageIdentity(parsed, target, packagePath);
  return toDetail(target, parsed, {
    logicalPath: packagePath,
    provenancePath: null,
    evidenceFileRef: null,
  });
}

function mapOfficial(
  target: Rc1Target,
  packageData: unknown,
  provenanceData: unknown,
  packagePath: string,
  provenancePath: string,
): ExperimentDetail {
  assertPath(packagePath, target.packageLogicalPath);
  if (target.provenanceLogicalPath === null || target.evidenceFile === null) {
    throw new EvidenceIdentityError(`${target.uiId} no tiene manifiesto de procedencia esperado`);
  }
  assertPath(provenancePath, target.provenanceLogicalPath);
  const parsed = readPackage(packageData, packagePath);
  const provenance = readProvenance(provenanceData, provenancePath);
  assertPackageIdentity(parsed, target, packagePath);
  assertProvenanceLink(parsed, provenance, target, provenancePath);
  return toDetail(target, parsed, {
    logicalPath: packagePath,
    provenancePath,
    evidenceFileRef: provenance.evidenceFile,
  });
}

function toDetail(
  target: Rc1Target,
  parsed: ParsedPackage,
  locator: EvidenceLocator,
): ExperimentDetail {
  const identity: EvidenceIdentity = {
    campaignId: parsed.campaignId,
    campaignIdentity: parsed.campaignIdentity,
    family: parsed.family,
    role: parsed.role,
    softwareVersion: parsed.softwareVersion,
    sourceRevision: parsed.sourceRevision,
  };
  const runs = parsed.runs.map((run) => toRun(target.uiId, run));
  const measurements = parsed.runs.map((run) => toMeasurement(target.uiId, run));
  const scope = scopeNote(parsed.description);
  return {
    id: target.uiId,
    code: target.code,
    name: target.name,
    objective: questionOf(parsed.description),
    description: parsed.description,
    scopeNote: scope,
    runCount: runs.length,
    presentation: "rc1-canonical",
    identity,
    campaignStatus: parsed.status,
    locator,
    runs,
    measurements,
    lab: buildLabExperiment(target.uiId, parsed.source),
  };
}

function toRun(experimentId: string, run: ParsedRun): RunSummary {
  return {
    id: `${experimentId}:${run.index}`,
    idKind: "derived",
    experimentId,
    index: run.index,
    label: run.label,
    executionIdentity: run.executionIdentity,
    configurationHash: run.configurationHash,
    datasetFingerprint: run.datasetFingerprint,
    datasetIdentity: run.datasetIdentity,
    seed: run.seed,
    strategyType: run.strategyType,
    batchSizeEvents: run.batchSizeEvents,
    offeredLoadFraction: run.offeredLoadFraction,
    recoveryPolicy: run.recoveryPolicy,
    failureEnabled: run.failureEnabled,
    targetSequences: run.targetSequences,
  };
}

function toMeasurement(experimentId: string, run: ParsedRun): RunMeasurement {
  return {
    id: `${experimentId}:${run.index}`,
    index: run.index,
    label: run.label,
    strategyType: run.strategyType,
    batchSizeEvents: run.batchSizeEvents,
    offeredLoadFraction: run.offeredLoadFraction,
    metrics: run.metrics,
    gaps: gapsForRun(run.label, run.metricPaths),
    recovery: run.recovery,
  };
}

function questionOf(description: string): string {
  const index = description.indexOf("¿");
  if (index === -1) {
    return description;
  }
  return description.slice(index).trim();
}

function scopeNote(description: string): string | undefined {
  const sentence = "No constituye un experimento E4.";
  return description.includes(sentence) ? sentence : undefined;
}

function targetOf(uiId: Rc1Target["uiId"]): Rc1Target {
  const target = RC1_TARGETS.find((item) => item.uiId === uiId);
  if (!target) {
    throw new EvidenceIdentityError(`el catálogo RC1 no incluye ${uiId}`);
  }
  return target;
}

function assertPath(actual: string, expected: string): void {
  if (actual !== expected) {
    throw new EvidenceIdentityError(`se esperaba ${expected} y se leyó ${actual}`);
  }
}

function assertPackageIdentity(parsed: ParsedPackage, target: Rc1Target, path: string): void {
  const mismatches: string[] = [];
  if (parsed.campaignIdentity !== target.campaignIdentity) {
    mismatches.push(`campaign_identity ${parsed.campaignIdentity}`);
  }
  if (parsed.campaignId !== target.campaignId) {
    mismatches.push(`campaign_id ${parsed.campaignId}`);
  }
  if (parsed.family !== target.family) {
    mismatches.push(`family ${parsed.family}`);
  }
  if (parsed.role !== target.role) {
    mismatches.push(`role ${parsed.role}`);
  }
  if (!sameRelease(parsed.softwareVersion)) {
    mismatches.push(`software_version ${parsed.softwareVersion}`);
  }
  if (parsed.sourceRevision !== RC1_SOURCE_REVISION) {
    mismatches.push(`source_revision ${parsed.sourceRevision}`);
  }
  if (parsed.runCount !== target.runCount || parsed.runs.length !== target.runCount) {
    mismatches.push(`runs ${parsed.runs.length} (run_count ${parsed.runCount})`);
  }
  if (mismatches.length > 0) {
    throw new EvidenceIdentityError(
      `${path} no es la evidence RC1 de ${target.code}: ${mismatches.join("; ")}`,
    );
  }
}

function assertProvenanceLink(
  parsed: ParsedPackage,
  provenance: ProvenanceRecord,
  target: Rc1Target,
  path: string,
): void {
  const mismatches: string[] = [];
  if (provenance.campaignIdentity !== parsed.campaignIdentity) {
    mismatches.push("campaign_identity");
  }
  if (provenance.campaignId !== parsed.campaignId) {
    mismatches.push("campaign_id");
  }
  if (provenance.family !== parsed.family) {
    mismatches.push("family");
  }
  if (provenance.role !== parsed.role) {
    mismatches.push("role");
  }
  if (provenance.evidenceFile !== target.evidenceFile) {
    mismatches.push(`evidence_file ${provenance.evidenceFile}`);
  }
  if (!sameRelease(provenance.softwareVersion)) {
    mismatches.push(`software_version ${provenance.softwareVersion}`);
  }
  if (provenance.sourceRevision !== parsed.sourceRevision) {
    mismatches.push("source_revision");
  }
  if (provenance.status !== parsed.status) {
    mismatches.push("status");
  }
  if (provenance.runs.length !== parsed.runs.length) {
    mismatches.push("run_order");
  }
  provenance.runs.forEach((item, index) => {
    const run = parsed.runs[index];
    if (!run) {
      mismatches.push(`run_order[${index}]`);
      return;
    }
    if (
      item.index !== run.index ||
      item.label !== run.label ||
      item.configurationHash !== run.configurationHash ||
      item.datasetFingerprint !== run.datasetFingerprint ||
      item.datasetIdentity !== run.datasetIdentity ||
      item.executionIdentity !== run.executionIdentity ||
      item.completed !== run.completed ||
      item.failed !== run.failed
    ) {
      mismatches.push(`run_order[${index}] no coincide con la evidence`);
    }
  });
  if (mismatches.length > 0) {
    throw new EvidenceIdentityError(
      `${path} no referencia la evidence de ${target.code}: ${mismatches.join("; ")}`,
    );
  }
}

function sameRelease(value: string): boolean {
  return value.replace(/^v/, "") === RC1_SOFTWARE_VERSION;
}

function readPackage(value: unknown, path: string): ParsedPackage {
  const root = asRecord(value, path);
  const family = requireString(root, "family", path);
  const role = requireString(root, "role", path);
  const campaignId = requireString(root, "campaign_id", path);
  const campaignIdentity = requireString(root, "campaign_identity", path);
  const reproducibility = asRecord(root.reproducibility, `${path}.reproducibility`);
  const manifest = asRecord(root.campaign_manifest, `${path}.campaign_manifest`);
  const manifestCampaignId = requireString(manifest, "campaign_id", `${path}.campaign_manifest`);
  const manifestIdentity = requireString(
    manifest,
    "campaign_identity",
    `${path}.campaign_manifest`,
  );
  if (manifestCampaignId !== campaignId || manifestIdentity !== campaignIdentity) {
    throw new EvidenceSchemaError(`${path}: el manifiesto no coincide con el paquete`);
  }
  const softwareVersion = sameText(
    requireString(manifest, "software_version", `${path}.campaign_manifest`),
    requireString(reproducibility, "software_version", `${path}.reproducibility`),
    `${path} software_version`,
  );
  const sourceRevision = sameText(
    requireString(manifest, "source_revision", `${path}.campaign_manifest`),
    requireString(reproducibility, "source_revision", `${path}.reproducibility`),
    `${path} source_revision`,
  );
  requireString(manifest, "source_state", `${path}.campaign_manifest`);
  requireString(reproducibility, "source_state", `${path}.reproducibility`);
  const runsValue = requireArray(manifest, "runs", `${path}.campaign_manifest`);
  const runCount = requireInteger(manifest, "run_count", `${path}.campaign_manifest`);
  if (runCount !== runsValue.length) {
    throw new EvidenceSchemaError(
      `${path}: run_count es ${runCount} y runs tiene ${runsValue.length}`,
    );
  }
  const runs = runsValue.map((item, index) => readRun(item, index, path));
  return {
    family,
    role,
    campaignId,
    campaignIdentity,
    description: requireString(manifest, "description", `${path}.campaign_manifest`),
    status: requireString(manifest, "status", `${path}.campaign_manifest`),
    runCount,
    softwareVersion,
    sourceRevision,
    runs,
    source: root,
  };
}

function readProvenance(value: unknown, path: string): ProvenanceRecord {
  const root = asRecord(value, path);
  if ("campaign_manifest" in root) {
    throw new EvidenceSchemaError(
      `${path} es un paquete de evidence, no el manifiesto de procedencia`,
    );
  }
  const reproducibility = asRecord(root.reproducibility, `${path}.reproducibility`);
  const order = requireArray(root, "run_order", path);
  return {
    campaignId: requireString(root, "campaign_id", path),
    campaignIdentity: requireString(root, "campaign_identity", path),
    family: requireString(root, "family", path),
    role: requireString(root, "role", path),
    evidenceFile: requireString(root, "evidence_file", path),
    status: requireString(root, "status", path),
    softwareVersion: requireString(reproducibility, "software_version", `${path}.reproducibility`),
    sourceRevision: requireString(reproducibility, "source_revision", `${path}.reproducibility`),
    runs: order.map((item, index) => readProvenanceRun(item, index, path)),
  };
}

function readProvenanceRun(value: unknown, index: number, path: string): ProvenanceRun {
  const runPath = `${path}.run_order[${index}]`;
  const record = asRecord(value, runPath);
  const runIndex = requireInteger(record, "index", runPath);
  if (runIndex !== index) {
    throw new EvidenceSchemaError(`${runPath}.index no sigue el orden`);
  }
  return {
    index: runIndex,
    label: requireString(record, "label", runPath),
    configurationHash: requireString(record, "configuration_hash", runPath),
    datasetFingerprint: requireString(record, "dataset_fingerprint", runPath),
    datasetIdentity: requireString(record, "dataset_identity", runPath),
    executionIdentity: requireString(record, "execution_identity", runPath),
    completed: requireBoolean(record, "completed", runPath),
    failed: requireBoolean(record, "failed", runPath),
  };
}

function readRun(value: unknown, index: number, path: string): ParsedRun {
  const runPath = `${path}.campaign_manifest.runs[${index}]`;
  const record = asRecord(value, runPath);
  const runIndex = requireInteger(record, "index", runPath);
  if (runIndex !== index) {
    throw new EvidenceSchemaError(`${runPath}.index no sigue el orden`);
  }
  const completed = requireBoolean(record, "completed", runPath);
  const failed = requireBoolean(record, "failed", runPath);
  if (failed === completed) {
    throw new EvidenceSchemaError(`${runPath}: completed y failed se contradicen`);
  }
  const manifest = asRecord(record.manifest, `${runPath}.manifest`);
  const configurationHash = sameText(
    requireString(record, "configuration_hash", runPath),
    requireString(manifest, "configuration_hash", `${runPath}.manifest`),
    `${runPath} configuration_hash`,
  );
  const datasetFingerprint = sameText(
    requireString(record, "dataset_fingerprint", runPath),
    requireString(manifest, "dataset_fingerprint", `${runPath}.manifest`),
    `${runPath} dataset_fingerprint`,
  );
  const datasetIdentity = sameText(
    requireString(record, "dataset_identity", runPath),
    requireString(manifest, "dataset_identity", `${runPath}.manifest`),
    `${runPath} dataset_identity`,
  );
  const executionIdentity = sameText(
    requireString(record, "execution_identity", runPath),
    requireString(manifest, "execution_identity", `${runPath}.manifest`),
    `${runPath} execution_identity`,
  );
  const metricsRead = completed
    ? readStoredMetrics(manifest.metrics, `${runPath}.manifest.metrics`)
    : null;
  const recovery = completed
    ? readStoredRecovery(manifest.metrics, `${runPath}.manifest.metrics`)
    : null;
  const failure = readFailure(manifest.failure_plan, `${runPath}.manifest.failure_plan`);
  const workload = asRecord(manifest.workload, `${runPath}.manifest.workload`);
  return {
    index: runIndex,
    label: requireString(record, "label", runPath),
    completed,
    failed,
    configurationHash,
    datasetFingerprint,
    datasetIdentity,
    executionIdentity,
    seed: requireInteger(manifest, "seed", `${runPath}.manifest`),
    strategyType: requireString(manifest, "strategy_type", `${runPath}.manifest`),
    batchSizeEvents: requireNullableInteger(manifest, "batch_size_events", `${runPath}.manifest`),
    offeredLoadFraction: requireNullableNumber(
      workload,
      "offered_load_fraction",
      `${runPath}.manifest.workload`,
    ),
    recoveryPolicy: requireString(manifest, "recovery_policy", `${runPath}.manifest`),
    failureEnabled: failure.enabled,
    targetSequences: failure.sequences,
    metrics: metricsRead?.metrics ?? null,
    metricPaths: metricsRead?.paths ?? [`${runPath}.manifest.metrics`],
    recovery,
  };
}

function readFailure(
  value: unknown,
  path: string,
): { enabled: boolean; sequences: number[] } {
  const plan = asRecord(value, path);
  const losses = requireArray(plan, "silent_forward_delivery_losses", path);
  requireArray(plan, "ack_drops", path);
  requireArray(plan, "contact_cuts", path);
  const sequences = losses.map((item, index) => {
    const loss = asRecord(item, `${path}.silent_forward_delivery_losses[${index}]`);
    return requireInteger(loss, "sequence_number", `${path}.silent_forward_delivery_losses[${index}]`);
  });
  const cuts = plan.contact_cuts;
  const acks = plan.ack_drops;
  const enabled =
    losses.length > 0 ||
    (Array.isArray(cuts) && cuts.length > 0) ||
    (Array.isArray(acks) && acks.length > 0);
  return { enabled, sequences };
}

function sameText(left: string, right: string, label: string): string {
  if (left !== right) {
    throw new EvidenceSchemaError(`${label} no coincide dentro del artefacto`);
  }
  return left;
}

function asRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new EvidenceSchemaError(`${path} debe ser un objeto`);
  }
  return value as Record<string, unknown>;
}

function requireString(record: Record<string, unknown>, key: string, path: string): string {
  const value = record[key];
  if (typeof value !== "string" || value.length === 0) {
    throw new EvidenceSchemaError(`${path}.${key} debe ser texto`);
  }
  return value;
}

function requireBoolean(record: Record<string, unknown>, key: string, path: string): boolean {
  const value = record[key];
  if (typeof value !== "boolean") {
    throw new EvidenceSchemaError(`${path}.${key} debe ser booleano`);
  }
  return value;
}

function requireInteger(record: Record<string, unknown>, key: string, path: string): number {
  const value = requireNumber(record, key, path);
  if (!Number.isInteger(value)) {
    throw new EvidenceSchemaError(`${path}.${key} debe ser un entero`);
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

function requireNullableInteger(
  record: Record<string, unknown>,
  key: string,
  path: string,
): number | null {
  const value = record[key];
  if (value === null) {
    return null;
  }
  if (typeof value !== "number" || !Number.isInteger(value)) {
    throw new EvidenceSchemaError(`${path}.${key} debe ser un entero o null`);
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

function requireArray(record: Record<string, unknown>, key: string, path: string): unknown[] {
  const value = record[key];
  if (!Array.isArray(value)) {
    throw new EvidenceSchemaError(`${path}.${key} debe ser una lista`);
  }
  return value;
}
