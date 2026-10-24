import type { EvidencePresentation } from "./types";

export function presentationLabel(presentation: EvidencePresentation): string {
  switch (presentation) {
    case "rc1-canonical":
      return "RC1 · CANÓNICA";
    case "artifact-loaded":
      return "ARTEFACTO CARGADO";
    case "static-metadata":
      return "METADATOS ESTÁTICOS";
  }
}

export function presentationTone(
  presentation: EvidencePresentation,
): "canonical" | "pending" | "neutral" {
  switch (presentation) {
    case "rc1-canonical":
      return "canonical";
    case "artifact-loaded":
      return "pending";
    case "static-metadata":
      return "neutral";
  }
}
