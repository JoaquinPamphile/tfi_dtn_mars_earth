/** Release científica que el visor identifica. No es el manifiesto. */
export interface ScientificRelease {
  version: string;
  sourceRevision: string;
}

export type ExperimentStatus = "EVIDENCE_VALID";

/** Familia de experimento conocida por el laboratorio. */
export interface ExperimentFamily {
  id: string;
  code: string;
  name: string;
  objective: string;
  runCount: number;
  status: ExperimentStatus;
  scopeNote?: string;
}

/** Resumen de una familia, listo para la UI. Las métricas llegan después. */
export interface ExperimentSummary {
  id: string;
  family: ExperimentFamily;
}

/**
 * Corrida mínima.
 * En V0 el ordinal es del shell: no es un identificador de manifest.
 */
export interface RunSummary {
  id: string;
  experimentId: string;
  ordinal: number;
}

export type EvidenceSourceKind = "static-metadata";

/** Origen de los datos que muestra el visor. */
export interface EvidenceSource {
  kind: EvidenceSourceKind;
  label: string;
  integrationNote: string;
}

/** Conjunto que el shell necesita para las pantallas de V0. */
export interface LabDataset {
  release: ScientificRelease;
  experiments: ExperimentSummary[];
  source: EvidenceSource;
}
