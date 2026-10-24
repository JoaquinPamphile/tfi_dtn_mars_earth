import { projectConfig } from "../../config/project";
import type {
  E1PresentationMetrics,
  E2PresentationMetrics,
  E3RecoveryPresentation,
  EvidenceSource,
  ExperimentDetail,
  ExperimentSummary,
  LabDataset,
  RunSummary,
  ScientificRelease,
} from "../../domain";
import type { EvidenceAdapter } from "../EvidenceAdapter";
import { mapE1MetricsForPresentation } from "./presentE1";
import { mapE2MetricsForPresentation } from "./presentE2";
import { mapE3Recovery } from "./presentE3";

/**
 * Lectura ya normalizada de los cuatro paquetes RC1.
 * No abre archivos y no recalcula métricas.
 */
export class Rc1EvidenceAdapter implements EvidenceAdapter {
  private readonly details: readonly ExperimentDetail[];

  constructor(details: readonly ExperimentDetail[]) {
    this.details = details;
  }

  getRelease(): ScientificRelease {
    const identity = this.details[0]?.identity;
    if (!identity) {
      throw new Error("la evidence RC1 no tiene identidad");
    }
    const version = identity.softwareVersion.startsWith("v")
      ? identity.softwareVersion
      : `v${identity.softwareVersion}`;
    return {
      version,
      softwareVersion: identity.softwareVersion,
      sourceRevision: identity.sourceRevision,
    };
  }

  getExperiments(): ExperimentSummary[] {
    return this.details.map(toSummary);
  }

  getExperiment(id: string): ExperimentSummary | undefined {
    const detail = this.getExperimentDetail(id);
    return detail ? toSummary(detail) : undefined;
  }

  getExperimentDetail(id: string): ExperimentDetail | undefined {
    return this.details.find((item) => item.id === id);
  }

  getRuns(experimentId: string): RunSummary[] {
    return this.getExperimentDetail(experimentId)?.runs ?? [];
  }

  getE1Presentation(): E1PresentationMetrics | null {
    const detail = this.getExperimentDetail("e1");
    return detail ? mapE1MetricsForPresentation(detail.measurements) : null;
  }

  getE2Presentation(): E2PresentationMetrics | null {
    const detail = this.getExperimentDetail("e2");
    return detail ? mapE2MetricsForPresentation(detail.measurements) : null;
  }

  getE3Presentation(): E3RecoveryPresentation | null {
    const official = this.getExperimentDetail("e3");
    if (!official) {
      return null;
    }
    const sensitivity = this.getExperimentDetail("e3-sensitivity") ?? null;
    return mapE3Recovery(official, sensitivity);
  }

  getDataset(): LabDataset {
    const experiments = this.getExperiments();
    const runCount = experiments.reduce((total, item) => total + item.runCount, 0);
    const source: EvidenceSource = {
      kind: "rc1-evidence",
      label: "RC1 EVIDENCE",
      stateLabel: projectConfig.readOnlyStateLabel,
      integrationNote: "Evidence RC1 cargada",
      artifactCount: experiments.length,
      runCount,
    };
    return {
      release: this.getRelease(),
      experiments,
      source,
    };
  }
}

function toSummary(detail: ExperimentDetail): ExperimentSummary {
  return {
    id: detail.id,
    code: detail.code,
    name: detail.name,
    objective: detail.objective,
    scopeNote: detail.scopeNote,
    runCount: detail.runCount,
    presentation: detail.presentation,
    identity: detail.identity,
    campaignStatus: detail.campaignStatus,
  };
}
