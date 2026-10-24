import type { DefenseStep, DefenseStepId } from "./types";

/**
 * Secuencia única del Modo Defensa.
 * El relato está en content.ts.
 * Las identidades y los conteos salen del adapter, no de esta lista.
 * No incluye notas del presentador.
 */
const SEQUENCE: readonly Omit<DefenseStep, "number">[] = [
  { id: "problem", title: "Problema", section: "PROBLEMA" },
  { id: "core-idea", title: "Idea central", section: "IDEA CENTRAL" },
  { id: "application-model", title: "Modelo de aplicación", section: "MODELO" },
  { id: "architecture", title: "Arquitectura", section: "ARQUITECTURA" },
  { id: "scenario", title: "Escenario experimental", section: "ESCENARIO" },
  { id: "e1", title: "E1 — Granularidad", section: "E1 · GRANULARIDAD" },
  { id: "e2", title: "E2 — Presión de carga", section: "E2 · CARGA" },
  { id: "e3", title: "E3 — Recuperación", section: "E3 · RECUPERACIÓN" },
  { id: "validity", title: "Validez y reproducibilidad", section: "VALIDEZ" },
  { id: "conclusions", title: "Conclusiones", section: "CONCLUSIONES" },
];

export const DEFENSE_STEPS: readonly DefenseStep[] = SEQUENCE.map((step, index) => ({
  ...step,
  number: String(index + 1).padStart(2, "0"),
}));

export function defensePath(id: DefenseStepId): string {
  return `/defensa/${id}`;
}

export function defenseStepById(id: string | undefined): DefenseStep | undefined {
  if (!id) {
    return undefined;
  }
  return DEFENSE_STEPS.find((step) => step.id === id);
}

export function defenseStepIndex(id: string | undefined): number {
  if (!id) {
    return -1;
  }
  return DEFENSE_STEPS.findIndex((step) => step.id === id);
}
