import { openRc1Evidence, type LabSession } from "./rc1/openRc1Evidence";
import { openRc1Scenario, type ScenarioSession } from "./rc1/openRc1Scenario";

export type { EvidenceAdapter } from "./EvidenceAdapter";
export type { LabSession } from "./rc1/openRc1Evidence";
export type { ScenarioSession } from "./rc1/openRc1Scenario";
export type { ScenarioAdapter } from "./ScenarioAdapter";
export { StaticEvidenceAdapter } from "./StaticEvidenceAdapter";
export { Rc1EvidenceAdapter } from "./rc1/Rc1EvidenceAdapter";
export { openRc1Evidence } from "./rc1/openRc1Evidence";
export {
  EvidenceAccessError,
  EvidenceIdentityError,
  EvidenceLoadError,
  EvidenceSchemaError,
} from "./errors";

/** Sesión activa del visor. No cae a metadatos estáticos si la evidence falta. */
export const labSession: LabSession = openRc1Evidence();

/** Escenario congelado RC1. Si no se puede leer, no se inventan ventanas. */
export const scenarioSession: ScenarioSession = openRc1Scenario();
