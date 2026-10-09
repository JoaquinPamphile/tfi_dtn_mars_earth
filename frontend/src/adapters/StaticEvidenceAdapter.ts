import { projectConfig } from "../config/project";
import type {
  EvidenceSource,
  ExperimentSummary,
  LabDataset,
  RunSummary,
  ScientificRelease,
} from "../domain";
import type { EvidenceAdapter } from "./EvidenceAdapter";

/**
 * Metadatos mínimos conocidos de la release RC1.
 * No abre evidence/, manifests ni resultados.
 * Los objetivos cortos resumen la pregunta de cada familia;
 * no agregan métricas.
 */
const SOURCE: EvidenceSource = {
  kind: "static-metadata",
  label: projectConfig.dataSourceLabel,
  integrationNote: projectConfig.evidenceIntegrationNote,
};

const EXPERIMENTS: ExperimentSummary[] = [
  {
    id: "e1",
    family: {
      id: "e1",
      code: "E1",
      name: "Granularidad de sincronización",
      objective:
        "Cómo afecta la estrategia de sincronización cuando la conectividad y el dataset son idénticos y solo cambia la agrupación.",
      runCount: 4,
      status: "EVIDENCE_VALID",
    },
  },
  {
    id: "e2",
    family: {
      id: "e2",
      code: "E2",
      name: "Carga ofrecida",
      objective:
        "Cómo cambia el comportamiento cuando la carga de telemetría ofrecida se acerca a la capacidad disponible y la supera.",
      runCount: 12,
      status: "EVIDENCE_VALID",
    },
  },
  {
    id: "e3",
    family: {
      id: "e3",
      code: "E3",
      name: "Recuperación ante pérdida silenciosa",
      objective:
        "Cómo difieren la recuperación sender-driven y la reparación receiver-driven ante la misma pérdida silenciosa.",
      runCount: 4,
      status: "EVIDENCE_VALID",
    },
  },
  {
    id: "e3-sensitivity",
    family: {
      id: "e3-sensitivity",
      code: "E3 Sensitivity",
      name: "Sensibilidad a posición de pérdida",
      objective:
        "Si el contraste entre sender-driven y receiver-driven se mantiene cuando la pérdida silenciosa cambia de posición.",
      runCount: 6,
      status: "EVIDENCE_VALID",
      scopeNote:
        "Limitada al mismo régimen de contacto. No constituye un experimento E4.",
    },
  },
];

export class StaticEvidenceAdapter implements EvidenceAdapter {
  getRelease(): ScientificRelease {
    return {
      version: projectConfig.releaseVersion,
      sourceRevision: projectConfig.sourceRevision,
    };
  }

  getExperiments(): ExperimentSummary[] {
    return EXPERIMENTS.map(clonarResumen);
  }

  getExperiment(id: string): ExperimentSummary | undefined {
    const encontrado = EXPERIMENTS.find((item) => item.id === id);
    return encontrado ? clonarResumen(encontrado) : undefined;
  }

  /**
   * Ordinales del shell, alineados con el conteo de la familia.
   * No son UUID de manifests y no traen métricas.
   */
  getRuns(experimentId: string): RunSummary[] {
    const experimento = this.getExperiment(experimentId);
    if (!experimento) {
      return [];
    }

    return Array.from({ length: experimento.family.runCount }, (_, index) => ({
      id: `${experimento.id}-ordinal-${index + 1}`,
      experimentId: experimento.id,
      ordinal: index + 1,
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

function clonarResumen(item: ExperimentSummary): ExperimentSummary {
  return {
    id: item.id,
    family: { ...item.family },
  };
}
