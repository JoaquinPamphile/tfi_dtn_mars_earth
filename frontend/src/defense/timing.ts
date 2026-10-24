import { DEFENSE_STEPS } from "./defenseSteps";
import type { DefenseStepId } from "./types";

/**
 * Presupuesto de la exposición oral.
 * Los pesos fijan la proporción. Ninguna cuenta asume el valor por defecto.
 */

export const DEFAULT_TOTAL_DURATION_MS = 20 * 60 * 1000;

export const MIN_TOTAL_DURATION_MS = 60 * 1000;

export const MAX_TOTAL_DURATION_MS = 180 * 60 * 1000;

/** Margen en el que el ritmo se considera en tiempo. */
export const PACE_BAND_MS = 10_000;

/**
 * Reparto inicial, en milisegundos:
 * Problema 1:30, Idea 1:30, Modelo 2:00, Arquitectura 2:00, Escenario 2:00,
 * E1 2:00, E2 2:30, E3 3:00, Validez 1:30, Conclusiones 2:00.
 */
export const STAGE_WEIGHT_MS: Record<DefenseStepId, number> = {
  problem: 90_000,
  "core-idea": 90_000,
  "application-model": 120_000,
  architecture: 120_000,
  scenario: 120_000,
  e1: 120_000,
  e2: 150_000,
  e3: 180_000,
  validity: 90_000,
  conclusions: 120_000,
};

export type PaceStatus = "ahead" | "on-time" | "behind";

export function clampTotalDuration(totalMs: number): number {
  if (!Number.isFinite(totalMs)) {
    return DEFAULT_TOTAL_DURATION_MS;
  }
  const rounded = Math.round(totalMs);
  if (rounded < MIN_TOTAL_DURATION_MS) {
    return MIN_TOTAL_DURATION_MS;
  }
  if (rounded > MAX_TOTAL_DURATION_MS) {
    return MAX_TOTAL_DURATION_MS;
  }
  return rounded;
}

/** Reparte el presupuesto según los pesos. La suma coincide con el total. */
export function stageTargetMs(totalMs: number): Record<DefenseStepId, number> {
  const ids = DEFENSE_STEPS.map((step) => step.id);
  const safeTotal = clampTotalDuration(totalMs);
  const weightSum = ids.reduce((sum, id) => sum + STAGE_WEIGHT_MS[id], 0);
  const targets = {} as Record<DefenseStepId, number>;
  if (ids.length === 0) {
    return targets;
  }
  if (weightSum <= 0) {
    const equal = Math.floor(safeTotal / ids.length);
    let assigned = 0;
    ids.forEach((id, index) => {
      const slice = index === ids.length - 1 ? safeTotal - assigned : equal;
      targets[id] = slice;
      assigned += slice;
    });
    return targets;
  }
  let assigned = 0;
  ids.forEach((id, index) => {
    if (index === ids.length - 1) {
      targets[id] = Math.max(0, safeTotal - assigned);
      return;
    }
    const raw = Math.round((STAGE_WEIGHT_MS[id] / weightSum) * safeTotal);
    const slice = Math.max(0, Math.min(raw, safeTotal - assigned));
    targets[id] = slice;
    assigned += slice;
  });
  return targets;
}

/**
 * Margen de la exposición, en milisegundos.
 * Positivo: las etapas ya cerradas dejaron tiempo a favor.
 * El tramo todavía no usado de la etapa actual no cuenta como adelanto.
 * Superar su objetivo sí cuenta como atraso.
 * Una etapa no visitada no entra en la cuenta.
 */
export function exposureMarginMs(input: {
  ledger: readonly { stepId: DefenseStepId; elapsedMs: number }[];
  currentId: DefenseStepId;
  currentElapsedMs: number;
  targets: Readonly<Record<DefenseStepId, number>>;
}): number {
  let margin = 0;
  let priorCurrent = 0;
  for (const entry of input.ledger) {
    if (entry.stepId === input.currentId) {
      priorCurrent += entry.elapsedMs;
      continue;
    }
    margin += input.targets[entry.stepId] - entry.elapsedMs;
  }
  const spent = priorCurrent + Math.max(0, input.currentElapsedMs);
  margin -= Math.max(0, spent - input.targets[input.currentId]);
  return margin;
}

export function paceOf(marginMs: number, bandMs = PACE_BAND_MS): PaceStatus {
  if (marginMs > bandMs) {
    return "ahead";
  }
  if (marginMs < -bandMs) {
    return "behind";
  }
  return "on-time";
}

export function paceLabel(pace: PaceStatus): string {
  if (pace === "ahead") {
    return "Adelantado";
  }
  if (pace === "behind") {
    return "Atrasado";
  }
  return "En tiempo";
}

export function formatClock(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const clock = `${minutes}:${String(seconds).padStart(2, "0")}`;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return clock;
}

/** +45 s, +1:10 o −1:10. El signo menos es el tipográfico. */
export function formatSignedDuration(ms: number): string {
  const sign = ms < 0 ? "\u2212" : "+";
  const absSeconds = Math.abs(Math.round(ms / 1000));
  const minutes = Math.floor(absSeconds / 60);
  const seconds = absSeconds % 60;
  if (minutes === 0) {
    return `${sign}${seconds} s`;
  }
  return `${sign}${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function formatMinutesInput(totalMs: number): string {
  const minutes = clampTotalDuration(totalMs) / 60_000;
  if (Number.isInteger(minutes)) {
    return String(minutes);
  }
  return minutes.toFixed(1);
}
