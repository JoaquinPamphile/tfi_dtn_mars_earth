import { projectConfig } from "../config/project";
import type {
  EvidenceSource,
  ExperimentDetail,
  ExperimentSummary,
  LabDataset,
  RunSummary,
  ScientificRelease,
} from "../domain";
import type { EvidenceAdapter } from "./EvidenceAdapter";

/**
 * Catálogo de desarrollo.
 * No abre evidence/ y no es la fuente activa del visor.
 */
const SOURCE: EvidenceSource = {
  kind: "static-metadata",
  label: "METADATOS ESTÁTICOS",
  stateLabel: "DESARROLLO",
  integrationNote: "No es la fuente activa. No lee evidence.",
  artifactCount: null,
  runCount: null,
};

const EXPERIMENTS: ExperimentSummary[] = [
  {
    id: "e1",
    code: "E1",
    name: "Granularidad de sincronización",
    objective:
      "Cómo afecta la estrategia de sincronización cuando la conectividad y el dataset son idénticos y solo cambia la agrupación.",
    runCount: 4,
    presentation: "static-metadata",
    identity: null,
    campaignStatus: null,
  },
  {
    id: "e2",
    code: "E2",
    name: "Carga ofrecida",
    objective:
      "Cómo cambia el comportamiento cuando la carga de telemetría ofrecida se acerca a la capacidad disponible y la supera.",
    runCount: 12,
    presentation: "static-metadata",
    identity: null,
    campaignStatus: null,
  },
  {
    id: "e3",
    code: "E3",
    name: "Recuperación ante pérdida silenciosa",
    objective:
      "Cómo difieren la recuperación sender-driven y la reparación receiver-driven ante la misma pérdida silenciosa.",
    runCount: 4,
    presentation: "static-metadata",
    identity: null,
    campaignStatus: null,
  },
  {
    id: "e3-sensitivity",
    code: "E3 Sensitivity",
    name: "Sensibilidad a posición de pérdida",
    objective:
      "Si el contraste entre sender-driven y receiver-driven se mantiene cuando la pérdida silenciosa cambia de posición.",
    runCount: 6,
    presentation: "static-metadata",
    identity: null,
    campaignStatus: null,
    scopeNote: "Limitada al mismo régimen de contacto. No constituye un experimento E4.",
  },
];

export class StaticEvidenceAdapter implements EvidenceAdapter {
  getRelease(): ScientificRelease {
    return {
      version: projectConfig.releaseVersion,
      softwareVersion: projectConfig.releaseVersion.replace(/^v/, ""),
      sourceRevision: projectConfig.sourceRevision,
    };
  }

  getExperiments(): ExperimentSummary[] {
    return EXPERIMENTS.map(cloneSummary);
  }

  getExperiment(id: string): ExperimentSummary | undefined {
    const found = EXPERIMENTS.find((item) => item.id === id);
    return found ? cloneSummary(found) : undefined;
  }

  getExperimentDetail(id: string): ExperimentDetail | undefined {
    const summary = this.getExperiment(id);
    if (!summary) {
      return undefined;
    }
    return {
      ...summary,
      description: summary.objective,
      locator: {
        logicalPath: "",
        provenancePath: null,
        evidenceFileRef: null,
      },
      runs: this.getRuns(id),
      measurements: [],
      lab: null,
    };
  }

  getE1Presentation() {
    return null;
  }

  getE2Presentation() {
    return null;
  }

  getE3Presentation() {
    return null;
  }

  /** Referencias de UI. No son identidades de los artefactos RC1. */
  getRuns(experimentId: string): RunSummary[] {
    const experiment = this.getExperiment(experimentId);
    if (!experiment) {
      return [];
    }
    return Array.from({ length: experiment.runCount }, (_, index) => ({
      id: `${experiment.id}:${index}`,
      idKind: "derived",
      experimentId: experiment.id,
      index,
      label: `Corrida ${index + 1}`,
      executionIdentity: null,
      configurationHash: null,
      datasetFingerprint: null,
      datasetIdentity: null,
      seed: null,
      strategyType: null,
      batchSizeEvents: null,
      offeredLoadFraction: null,
      recoveryPolicy: null,
      failureEnabled: null,
      targetSequences: null,
    }));
  }

  getDataset(): LabDataset {
    return {
      release: this.getRelease(),
      experiments: this.getExperiments(),
      source: { ...SOURCE },
    };
  }
}

function cloneSummary(item: ExperimentSummary): ExperimentSummary {
  return { ...item };
}
