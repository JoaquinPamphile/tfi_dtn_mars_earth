/** Modelo de escenario para la UI. No conoce el JSON de evidence. */

export type ContactDirection = "forward" | "return";

/** Procedencia de un contacto, en lenguaje de presentación. */
export type ContactProvenance = "approximated-transformed" | "tfi-assumption";

export interface ScenarioNode {
  id: string;
  label: string;
}

export interface DirectedContact {
  id: string;
  source: string;
  destination: string;
  startSeconds: number;
  endSeconds: number;
  dataRateBps: number;
  propagationDelaySeconds: number;
  provenance: ContactProvenance;
  provenanceLabel: string;
}

export interface ScenarioLink {
  id: string;
  source: string;
  destination: string;
  direction: ContactDirection;
  label: string;
  provenance: ContactProvenance;
  provenanceLabel: string;
  contacts: readonly DirectedContact[];
  dataRateBps: number | null;
  propagationDelaySeconds: number | null;
}

export interface ScenarioParameter {
  id: string;
  label: string;
  value: string;
  detail: string;
  /** Campo del artefacto del que sale el número. No se muestra en la defensa. */
  sourceField: string;
  rawValue: string;
}

export interface ProvenanceEntry {
  id: string;
  term: string;
  meaning: string;
}

/**
 * Banda de generación derivada del workload congelado.
 * El fin no está guardado: es el último evento del perfil.
 */
export interface GenerationSpan {
  workloadId: string;
  /** Campañas cuya especificación trae este mismo workload. */
  campaignNote: string;
  startSeconds: number;
  lastEventSeconds: number;
  periodSeconds: number;
  rateEventsPerSecond: number;
}

export interface ScenarioDefinition {
  scenarioId: string;
  sourcePath: string;
  horizonSeconds: number;
  nodes: readonly ScenarioNode[];
  links: readonly ScenarioLink[];
  parameters: readonly ScenarioParameter[];
  generation: GenerationSpan | null;
  provenance: readonly ProvenanceEntry[];
  figureNote: string | null;
  limitNote: string | null;
  sourceNote: string;
}
