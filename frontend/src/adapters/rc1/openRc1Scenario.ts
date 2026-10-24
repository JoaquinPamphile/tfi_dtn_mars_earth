import { rc1Artifacts, type Rc1ArtifactFile } from "virtual:rc1-evidence";
import { EvidenceAccessError, EvidenceLoadError } from "../errors";
import type { ScenarioAdapter } from "../ScenarioAdapter";
import type { ScenarioDefinition } from "../../domain/scenario";
import { Rc1ScenarioAdapter } from "./Rc1ScenarioAdapter";
import { mapRc1Scenario } from "./mapScenario";

export type ScenarioSession =
  | { kind: "ready"; adapter: ScenarioAdapter; scenario: ScenarioDefinition }
  | { kind: "unavailable"; error: EvidenceAccessError };

/** Abre el escenario congelado de la evidence RC1. Si falta, no inventa ventanas. */
export function openRc1Scenario(): ScenarioSession {
  try {
    const files = rc1Artifacts.files;
    const scenario = mapRc1Scenario({
      e1: loaded(files.e1Package),
      e1Path: files.e1Package.logicalPath,
      e2: loaded(files.e2Package),
      e2Path: files.e2Package.logicalPath,
      e3: loaded(files.e3Package),
      e3Path: files.e3Package.logicalPath,
    });
    return { kind: "ready", adapter: new Rc1ScenarioAdapter(scenario), scenario };
  } catch (error) {
    if (error instanceof EvidenceAccessError) {
      return { kind: "unavailable", error };
    }
    const message = error instanceof Error ? error.message : "no se pudo leer el escenario RC1";
    return { kind: "unavailable", error: new EvidenceLoadError(message) };
  }
}

function loaded(file: Rc1ArtifactFile): unknown {
  if (file.error || file.data === null) {
    throw new EvidenceLoadError(file.error ?? `no se pudo leer ${file.logicalPath}`);
  }
  return file.data;
}
