import type { ScenarioDefinition } from "../../domain/scenario";
import type { ScenarioAdapter } from "../ScenarioAdapter";

/** Escenario ya mapeado. No vuelve a leer el disco. */
export class Rc1ScenarioAdapter implements ScenarioAdapter {
  constructor(private readonly scenario: ScenarioDefinition) {}

  readBaseline(): ScenarioDefinition {
    return this.scenario;
  }
}
