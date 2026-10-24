import { DEFENSE_STEPS } from "./defenseSteps";
import { MAX_STORED_REHEARSALS, type StoredRehearsal } from "./rehearsal";
import { clampTotalDuration, DEFAULT_TOTAL_DURATION_MS } from "./timing";
import type { DefenseStepId } from "./types";

/** Preferencias del presentador. No guarda evidence ni resultados. */
export const PRESENTER_PREFS_KEY = "dtn-lab-defense-presenter";

/** Últimos ensayos locales. No sale del navegador. */
export const REHEARSALS_STORAGE_KEY = "dtn-lab-defense-rehearsals";

export interface PresenterPrefs {
  enabled: boolean;
  collapsed: boolean;
  totalDurationMs: number;
  saveHistory: boolean;
}

export const DEFAULT_PRESENTER_PREFS: PresenterPrefs = {
  enabled: false,
  collapsed: false,
  totalDurationMs: DEFAULT_TOTAL_DURATION_MS,
  saveHistory: true,
};

function esRegistro(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null;
}

function esStepId(valor: unknown): valor is DefenseStepId {
  return typeof valor === "string" && DEFENSE_STEPS.some((step) => step.id === valor);
}

export function readPresenterPrefs(): PresenterPrefs {
  try {
    const crudo = localStorage.getItem(PRESENTER_PREFS_KEY);
    if (!crudo) {
      return DEFAULT_PRESENTER_PREFS;
    }
    const parsed: unknown = JSON.parse(crudo);
    if (!esRegistro(parsed)) {
      return DEFAULT_PRESENTER_PREFS;
    }
    return {
      enabled: parsed.enabled === true,
      collapsed: parsed.collapsed === true,
      totalDurationMs:
        typeof parsed.totalDurationMs === "number"
          ? clampTotalDuration(parsed.totalDurationMs)
          : DEFAULT_TOTAL_DURATION_MS,
      saveHistory: parsed.saveHistory !== false,
    };
  } catch {
    return DEFAULT_PRESENTER_PREFS;
  }
}

export function writePresenterPrefs(prefs: PresenterPrefs): void {
  try {
    localStorage.setItem(PRESENTER_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* Si el navegador bloquea el almacenamiento, la sesión sigue en memoria. */
  }
}

function leerEnsayo(valor: unknown): StoredRehearsal | null {
  if (!esRegistro(valor) || typeof valor.finishedAt !== "string") {
    return null;
  }
  if (typeof valor.totalMs !== "number" || !Number.isFinite(valor.totalMs) || valor.totalMs < 0) {
    return null;
  }
  if (!Array.isArray(valor.stages)) {
    return null;
  }
  const stages: StoredRehearsal["stages"] = [];
  for (const item of valor.stages) {
    if (!esRegistro(item) || !esStepId(item.stepId)) {
      continue;
    }
    if (typeof item.elapsedMs !== "number" || !Number.isFinite(item.elapsedMs) || item.elapsedMs < 0) {
      continue;
    }
    stages.push({ stepId: item.stepId, elapsedMs: item.elapsedMs });
  }
  return { finishedAt: valor.finishedAt, totalMs: valor.totalMs, stages };
}

export function readStoredRehearsals(): StoredRehearsal[] {
  try {
    const crudo = localStorage.getItem(REHEARSALS_STORAGE_KEY);
    if (!crudo) {
      return [];
    }
    const parsed: unknown = JSON.parse(crudo);
    if (!Array.isArray(parsed)) {
      return [];
    }
    const ensayos: StoredRehearsal[] = [];
    for (const item of parsed) {
      const ensayo = leerEnsayo(item);
      if (ensayo) {
        ensayos.push(ensayo);
      }
      if (ensayos.length >= MAX_STORED_REHEARSALS) {
        break;
      }
    }
    return ensayos;
  } catch {
    return [];
  }
}

export function writeStoredRehearsals(ensayos: readonly StoredRehearsal[]): void {
  try {
    localStorage.setItem(
      REHEARSALS_STORAGE_KEY,
      JSON.stringify(ensayos.slice(0, MAX_STORED_REHEARSALS)),
    );
  } catch {
    /* El resumen de la sesión sigue visible aunque no se pueda guardar. */
  }
}
