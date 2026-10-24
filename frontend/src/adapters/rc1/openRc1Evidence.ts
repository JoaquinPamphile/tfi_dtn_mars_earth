import { rc1Artifacts, type Rc1ArtifactFile } from "virtual:rc1-evidence";
import { EvidenceAccessError, EvidenceLoadError } from "../errors";
import type { EvidenceAdapter } from "../EvidenceAdapter";
import { Rc1EvidenceAdapter } from "./Rc1EvidenceAdapter";
import {
  mapE1Evidence,
  mapE2Evidence,
  mapE3Evidence,
  mapE3SensitivityEvidence,
} from "./mapEvidence";

export type LabSession =
  | { kind: "ready"; adapter: EvidenceAdapter }
  | { kind: "unavailable"; error: EvidenceAccessError };

/** Abre la evidence RC1. Si falta un artefacto, no sustituye datos de desarrollo. */
export function openRc1Evidence(): LabSession {
  try {
    const files = rc1Artifacts.files;
    const e1 = mapE1Evidence(
      loaded(files.e1Package),
      loaded(files.e1Provenance),
      files.e1Package.logicalPath,
      files.e1Provenance.logicalPath,
    );
    const e2 = mapE2Evidence(
      loaded(files.e2Package),
      loaded(files.e2Provenance),
      files.e2Package.logicalPath,
      files.e2Provenance.logicalPath,
    );
    const e3 = mapE3Evidence(
      loaded(files.e3Package),
      loaded(files.e3Provenance),
      files.e3Package.logicalPath,
      files.e3Provenance.logicalPath,
    );
    const sensitivity = mapE3SensitivityEvidence(
      loaded(files.sensitivityPackage),
      files.sensitivityPackage.logicalPath,
    );
    return { kind: "ready", adapter: new Rc1EvidenceAdapter([e1, e2, e3, sensitivity]) };
  } catch (error) {
    if (error instanceof EvidenceAccessError) {
      return { kind: "unavailable", error };
    }
    const message = error instanceof Error ? error.message : "no se pudo leer la evidence RC1";
    return { kind: "unavailable", error: new EvidenceLoadError(message) };
  }
}

function loaded(file: Rc1ArtifactFile): unknown {
  if (file.error || file.data === null) {
    throw new EvidenceLoadError(file.error ?? `no se pudo leer ${file.logicalPath}`);
  }
  return file.data;
}
