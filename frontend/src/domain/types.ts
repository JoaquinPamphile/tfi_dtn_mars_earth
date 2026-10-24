import type { LabExperiment } from "./lab";
import type { RunMeasurement } from "./metrics";

/** Release científica que el visor identifica. No es el manifiesto. */
export interface ScientificRelease {
  /** Etiqueta de la release, por ejemplo v1.0.0-rc1. */
  version: string;
  /** Valor de software_version tal como está en el artefacto. */
  softwareVersion: string;
  sourceRevision: string;
}

/**
 * Cómo presenta la UI el origen.
 * rc1-canonical: la identidad leída coincide con la release RC1 esperada.
 * artifact-loaded: el JSON se leyó, sin afirmar que sea la evidence canónica.
 * static-metadata: catálogo de desarrollo, no lee artefactos.
 */
export type EvidencePresentation = "rc1-canonical" | "artifact-loaded" | "static-metadata";

/** Identidad científica leída del artefacto. */
export interface EvidenceIdentity {
  campaignId: string;
  campaignIdentity: string;
  family: string;
  role: string;
  softwareVersion: string;
  sourceRevision: string;
}

/** Familia lista para una tarjeta. Las métricas llegan después. */
export interface ExperimentSummary {
  id: string;
  code: string;
  name: string;
  objective: string;
  scopeNote?: string;
  runCount: number;
  presentation: EvidencePresentation;
  identity: EvidenceIdentity | null;
  /** Estado de campaña del artefacto, si existe. No es un sello de auditoría. */
  campaignStatus: string | null;
}

/** Dónde está el dato, sin copiar el JSON al frontend. */
export interface EvidenceLocator {
  logicalPath: string;
  provenancePath: string | null;
  /** Ruta que el manifiesto declara en evidence_file, si existe. */
  evidenceFileRef: string | null;
}

/** Detalle de una familia. Los componentes no ven el JSON crudo. */
export interface ExperimentDetail extends ExperimentSummary {
  description: string;
  locator: EvidenceLocator;
  runs: RunSummary[];
  /** Métricas almacenadas, en el mismo orden que runs. No incluye texto formateado. */
  measurements: RunMeasurement[];
  /** Inspección de laboratorio. null en el catálogo estático, que no lee artefactos. */
  lab: LabExperiment | null;
}

/**
 * Corrida para la UI.
 * id es una referencia derivada: estos artefactos no traen un UUID único por corrida.
 * executionIdentity es real y puede repetirse entre corridas de la misma campaña.
 * configurationHash identifica la configuración de esa corrida.
 */
export interface RunSummary {
  id: string;
  idKind: "derived";
  experimentId: string;
  index: number;
  label: string;
  executionIdentity: string | null;
  configurationHash: string | null;
  datasetFingerprint: string | null;
  datasetIdentity: string | null;
  seed: number | null;
  strategyType: string | null;
  batchSizeEvents: number | null;
  offeredLoadFraction: number | null;
  recoveryPolicy: string | null;
  failureEnabled: boolean | null;
  targetSequences: number[] | null;
}

export type EvidenceSourceKind = "rc1-evidence" | "static-metadata";

/** Origen de los datos que muestra el visor. */
export interface EvidenceSource {
  kind: EvidenceSourceKind;
  label: string;
  stateLabel: string;
  integrationNote: string;
  artifactCount: number | null;
  runCount: number | null;
}

/** Conjunto que el shell necesita para las pantallas. */
export interface LabDataset {
  release: ScientificRelease;
  experiments: ExperimentSummary[];
  source: EvidenceSource;
}
