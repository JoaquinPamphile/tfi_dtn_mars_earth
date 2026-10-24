import { DEFENSE_STEPS } from "./defenseSteps";
import type { DefenseStepId } from "./types";

/** Una etapa cuenta como fuera de objetivo si se aleja más de un segundo. */
export const STAGE_COMPARE_TOLERANCE_MS = 1000;

export const MAX_STORED_REHEARSALS = 5;

export interface LedgerEntry {
  stepId: DefenseStepId;
  elapsedMs: number;
}

export interface StageResult {
  stepId: DefenseStepId;
  title: string;
  elapsedMs: number;
  targetMs: number;
  deltaMs: number;
}

export interface RehearsalSummary {
  totalMs: number;
  stages: StageResult[];
  overTarget: StageResult[];
  underTarget: StageResult[];
}

export interface StoredRehearsal {
  finishedAt: string;
  totalMs: number;
  stages: { stepId: DefenseStepId; elapsedMs: number }[];
}

export function addLedger(
  entries: readonly LedgerEntry[],
  stepId: DefenseStepId,
  elapsedMs: number,
): LedgerEntry[] {
  if (elapsedMs <= 0) {
    return [...entries];
  }
  const existing = entries.find((entry) => entry.stepId === stepId);
  if (!existing) {
    return [...entries, { stepId, elapsedMs }];
  }
  return entries.map((entry) =>
    entry.stepId === stepId ? { ...entry, elapsedMs: entry.elapsedMs + elapsedMs } : entry,
  );
}

export function elapsedFor(entries: readonly LedgerEntry[], stepId: DefenseStepId): number {
  return entries.find((entry) => entry.stepId === stepId)?.elapsedMs ?? 0;
}

export function buildRehearsalSummary(
  ledger: readonly LedgerEntry[],
  targets: Readonly<Record<DefenseStepId, number>>,
  totalMs: number,
): RehearsalSummary {
  const stages = DEFENSE_STEPS.map((step) => {
    const elapsedMs = elapsedFor(ledger, step.id);
    const targetMs = targets[step.id];
    return {
      stepId: step.id,
      title: step.title,
      elapsedMs,
      targetMs,
      deltaMs: elapsedMs - targetMs,
    };
  });
  return {
    totalMs,
    stages,
    overTarget: stages.filter((stage) => stage.elapsedMs > stage.targetMs + STAGE_COMPARE_TOLERANCE_MS),
    underTarget: stages.filter((stage) => stage.elapsedMs + STAGE_COMPARE_TOLERANCE_MS < stage.targetMs),
  };
}

export function toStoredRehearsal(summary: RehearsalSummary, finishedAt: string): StoredRehearsal {
  return {
    finishedAt,
    totalMs: summary.totalMs,
    stages: summary.stages.map((stage) => ({ stepId: stage.stepId, elapsedMs: stage.elapsedMs })),
  };
}
