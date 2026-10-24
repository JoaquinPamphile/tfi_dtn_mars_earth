import type { ScenarioDefinition } from "../domain/scenario";

/**
 * Lectura del escenario congelado.
 * Los componentes no ven el formato de la evidence.
 */
export interface ScenarioAdapter {
  readBaseline(): ScenarioDefinition;
}
