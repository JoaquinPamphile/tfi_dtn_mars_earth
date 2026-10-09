import { StaticEvidenceAdapter } from "./StaticEvidenceAdapter";
import type { EvidenceAdapter } from "./EvidenceAdapter";

export type { EvidenceAdapter } from "./EvidenceAdapter";
export { StaticEvidenceAdapter } from "./StaticEvidenceAdapter";

/** Instancia única del visor V0. Sustituible cuando exista lectura de evidence. */
export const evidenceAdapter: EvidenceAdapter = new StaticEvidenceAdapter();
