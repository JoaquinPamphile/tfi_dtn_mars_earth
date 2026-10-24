import type {
  E1PresentationMetrics,
  E2PresentationMetrics,
  E3RecoveryPresentation,
  ExperimentDetail,
  ExperimentSummary,
  LabDataset,
  RunSummary,
  ScientificRelease,
} from "../domain";

/**
 * Puerto de lectura del laboratorio.
 * La fuente activa es Rc1EvidenceAdapter.
 * StaticEvidenceAdapter queda como catálogo de desarrollo y no reemplaza un fallo de carga.
 */
export interface EvidenceAdapter {
  getRelease(): ScientificRelease;
  getExperiments(): ExperimentSummary[];
  getExperiment(id: string): ExperimentSummary | undefined;
  getExperimentDetail(id: string): ExperimentDetail | undefined;
  getRuns(experimentId: string): RunSummary[];
  getDataset(): LabDataset;
  /** Métricas de E1 ya leídas. null si este adapter no tiene esa familia. */
  getE1Presentation(): E1PresentationMetrics | null;
  /** Métricas de E2 ya leídas. null si este adapter no tiene esa familia. */
  getE2Presentation(): E2PresentationMetrics | null;
  /** Episodio E3 y sensibilidad ya leídos. null si este adapter no tiene esa familia. */
  getE3Presentation(): E3RecoveryPresentation | null;
}
