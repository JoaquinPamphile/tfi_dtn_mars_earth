import type { EvidenceAdapter } from "../adapters";
import type { EvidencePresentation, RunSummary } from "../domain";
import { abbreviateHash } from "../domain";

/**
 * Lectura de configuración ya expuesta por el adapter.
 * No abre artefactos y no interpreta métricas.
 */

export interface ExperimentFacts {
  id: string;
  code: string;
  name: string;
  runCount: number;
  presentation: EvidencePresentation;
  campaignId: string;
  role: string;
  softwareVersion: string;
  sourceRevision: string;
  releaseVersion: string;
}

export interface ReleaseFacts {
  version: string;
  softwareVersion: string;
  sourceRevision: string;
  abbreviatedRevision: string;
  canonical: boolean;
}

const KNOWN_POLICIES = ["sender-driven", "receiver-driven"] as const;

export function experimentFacts(adapter: EvidenceAdapter, id: string): ExperimentFacts | null {
  const detail = adapter.getExperimentDetail(id);
  if (!detail?.identity) {
    return null;
  }
  const release = adapter.getRelease();
  return {
    id: detail.id,
    code: detail.code,
    name: detail.name,
    runCount: detail.runCount,
    presentation: detail.presentation,
    campaignId: detail.identity.campaignId,
    role: detail.identity.role,
    softwareVersion: detail.identity.softwareVersion,
    sourceRevision: detail.identity.sourceRevision,
    releaseVersion: release.version,
  };
}

export function releaseFacts(adapter: EvidenceAdapter): ReleaseFacts {
  const release = adapter.getRelease();
  const experiments = adapter.getExperiments();
  const canonical =
    experiments.length > 0 && experiments.every((item) => item.presentation === "rc1-canonical");
  return {
    version: release.version,
    softwareVersion: release.softwareVersion,
    sourceRevision: release.sourceRevision,
    abbreviatedRevision: abbreviateHash(release.sourceRevision),
    canonical,
  };
}

export function formatRunCount(count: number): string {
  return count === 1 ? "1 corrida" : `${count} corridas`;
}

/** Etiquetas de tratamiento a partir de strategy y batch. Conserva el orden de las corridas. */
export function e1TreatmentLabels(runs: readonly RunSummary[]): string[] {
  const labels: string[] = [];
  for (const run of runs) {
    const label = treatmentLabel(run);
    if (!labels.includes(label)) {
      labels.push(label);
    }
  }
  return labels;
}

/** Niveles de carga ofrecida, sin repetir la fracción. */
export function e2LoadLabels(runs: readonly RunSummary[]): string[] {
  const labels: string[] = [];
  for (const run of runs) {
    if (run.offeredLoadFraction === null) {
      continue;
    }
    const label = formatLoadPercent(run.offeredLoadFraction);
    if (!labels.includes(label)) {
      labels.push(label);
    }
  }
  return labels;
}

/** Políticas presentes, con sender antes que receiver cuando ambas existen. */
export function e3Policies(runs: readonly RunSummary[]): string[] {
  const found = new Set<string>();
  for (const run of runs) {
    if (run.recoveryPolicy) {
      found.add(run.recoveryPolicy);
    }
  }
  const ordered: string[] = [];
  for (const policy of KNOWN_POLICIES) {
    if (found.has(policy)) {
      ordered.push(policy);
    }
  }
  for (const policy of found) {
    if (!ordered.includes(policy)) {
      ordered.push(policy);
    }
  }
  return ordered;
}

export function formatPolicyLabel(policy: string): string {
  if (policy === "sender-driven") {
    return "SENDER-DRIVEN";
  }
  if (policy === "receiver-driven") {
    return "RECEIVER-DRIVEN";
  }
  return policy;
}

export function policyConcept(
  concepts: { readonly "sender-driven": string; readonly "receiver-driven": string },
  policy: string,
): string | null {
  if (policy === "sender-driven" || policy === "receiver-driven") {
    return concepts[policy];
  }
  return null;
}

/** Secuencias de la sensibilidad, en el orden en que aparecen las corridas. */
export function sensitivitySequenceLabels(runs: readonly RunSummary[]): string[] {
  const labels: string[] = [];
  for (const run of runs) {
    for (const sequence of run.targetSequences ?? []) {
      const label = `seq${sequence}`;
      if (!labels.includes(label)) {
        labels.push(label);
      }
    }
  }
  return labels;
}

function treatmentLabel(run: RunSummary): string {
  if (run.strategyType === "individual" || run.batchSizeEvents === null) {
    return "Individual";
  }
  return `Batch${run.batchSizeEvents}`;
}

function formatLoadPercent(fraction: number): string {
  const percent = Math.round(fraction * 1000) / 10;
  const text = Number.isInteger(percent) ? String(percent) : percent.toFixed(1);
  return `${text} %`;
}
