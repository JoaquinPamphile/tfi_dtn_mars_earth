import type {
  ExperimentSummary,
  LabDataset,
  RunSummary,
  ScientificRelease,
} from "../domain";

/**
 * Puerto de lectura del laboratorio.
 * V0 solo tiene una implementación estática.
 * La lectura de evidence/ queda para V0.1.
 */
export interface EvidenceAdapter {
  getRelease(): ScientificRelease;
  getExperiments(): ExperimentSummary[];
  getExperiment(id: string): ExperimentSummary | undefined;
  getRuns(experimentId: string): RunSummary[];
  getDataset(): LabDataset;
}
