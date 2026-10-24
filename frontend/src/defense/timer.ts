import type { DefenseStepId } from "./types";

/**
 * Cronómetro de la exposición.
 * Usa el reloj de pared del navegador. No lee el reloj de la simulación.
 */

export type ClockStatus = "idle" | "running" | "paused";

export interface DefenseClock {
  status: ClockStatus;
  totalBankedMs: number;
  stageBankedMs: number;
  segmentStartedAt: number | null;
  stageId: DefenseStepId | null;
}

export function createClock(stageId: DefenseStepId | null = null): DefenseClock {
  return {
    status: "idle",
    totalBankedMs: 0,
    stageBankedMs: 0,
    segmentStartedAt: null,
    stageId,
  };
}

export function clockRead(clock: DefenseClock, now: number): { totalMs: number; stageMs: number } {
  const live =
    clock.status === "running" && clock.segmentStartedAt !== null
      ? Math.max(0, now - clock.segmentStartedAt)
      : 0;
  return {
    totalMs: clock.totalBankedMs + live,
    stageMs: clock.stageBankedMs + live,
  };
}

export function clockStart(clock: DefenseClock, now: number): DefenseClock {
  if (clock.status === "running") {
    return clock;
  }
  return { ...clock, status: "running", segmentStartedAt: now };
}

export function clockPause(clock: DefenseClock, now: number): DefenseClock {
  if (clock.status !== "running") {
    return clock;
  }
  const read = clockRead(clock, now);
  return {
    ...clock,
    status: "paused",
    totalBankedMs: read.totalMs,
    stageBankedMs: read.stageMs,
    segmentStartedAt: null,
  };
}

export function clockToggle(clock: DefenseClock, now: number): DefenseClock {
  return clock.status === "running" ? clockPause(clock, now) : clockStart(clock, now);
}

export function clockChangeStage(
  clock: DefenseClock,
  nextId: DefenseStepId,
  now: number,
): {
  clock: DefenseClock;
  previous: { stageId: DefenseStepId; elapsedMs: number } | null;
} {
  if (clock.stageId === nextId) {
    return { clock, previous: null };
  }
  const read = clockRead(clock, now);
  const previous = clock.stageId === null ? null : { stageId: clock.stageId, elapsedMs: read.stageMs };
  return {
    previous,
    clock: {
      status: clock.status,
      totalBankedMs: read.totalMs,
      stageBankedMs: 0,
      segmentStartedAt: clock.status === "running" ? now : null,
      stageId: nextId,
    },
  };
}
