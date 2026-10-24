import {
  addLedger,
  buildRehearsalSummary,
  MAX_STORED_REHEARSALS,
  toStoredRehearsal,
  type LedgerEntry,
  type RehearsalSummary,
  type StoredRehearsal,
} from "./rehearsal";
import type { PresenterPrefs } from "./storage";
import { stageTargetMs } from "./timing";
import { clockChangeStage, clockPause, clockRead, clockStart, clockToggle, createClock, type DefenseClock } from "./timer";
import type { DefenseStepId } from "./types";

/**
 * Estado del presentador, sin DOM.
 * Un PresenterWindow futuro puede leer este mismo estado.
 */

export interface PresenterState {
  enabled: boolean;
  collapsed: boolean;
  totalDurationMs: number;
  saveHistory: boolean;
  clock: DefenseClock;
  ledger: LedgerEntry[];
  rehearsalActive: boolean;
  rehearsalStartedAt: string | null;
  summary: RehearsalSummary | null;
  history: StoredRehearsal[];
  helpOpen: boolean;
  confirmRestart: boolean;
}

export type PresenterAction =
  | { type: "toggle-enabled" }
  | { type: "set-collapsed"; collapsed: boolean }
  | { type: "set-duration"; totalDurationMs: number }
  | { type: "set-save-history"; saveHistory: boolean }
  | { type: "toggle-timer"; now: number }
  | { type: "reset-timer" }
  | { type: "pause-if-running"; now: number }
  | { type: "sync-step"; stepId: DefenseStepId; now: number }
  | { type: "start-rehearsal"; now: number; startedAt: string }
  | { type: "ask-restart" }
  | { type: "cancel-restart" }
  | { type: "finish"; now: number; finishedAt: string }
  | { type: "dismiss-summary" }
  | { type: "open-help" }
  | { type: "close-help" }
  | { type: "toggle-help" };

export function createPresenterState(prefs: PresenterPrefs, history: readonly StoredRehearsal[]): PresenterState {
  return {
    enabled: prefs.enabled,
    collapsed: prefs.collapsed,
    totalDurationMs: prefs.totalDurationMs,
    saveHistory: prefs.saveHistory,
    clock: createClock(null),
    ledger: [],
    rehearsalActive: false,
    rehearsalStartedAt: null,
    summary: null,
    history: [...history],
    helpOpen: false,
    confirmRestart: false,
  };
}

function ledgerConEtapaActual(state: PresenterState, now: number): LedgerEntry[] {
  const read = clockRead(state.clock, now);
  if (!state.clock.stageId || read.stageMs <= 0) {
    return state.ledger;
  }
  return addLedger(state.ledger, state.clock.stageId, read.stageMs);
}

export function reducePresenter(state: PresenterState, action: PresenterAction): PresenterState {
  switch (action.type) {
    case "toggle-enabled":
      return {
        ...state,
        enabled: !state.enabled,
        confirmRestart: state.enabled ? false : state.confirmRestart,
      };
    case "set-collapsed":
      return { ...state, collapsed: action.collapsed };
    case "set-duration":
      return { ...state, totalDurationMs: action.totalDurationMs };
    case "set-save-history":
      return { ...state, saveHistory: action.saveHistory };
    case "toggle-timer":
      return { ...state, clock: clockToggle(state.clock, action.now) };
    case "reset-timer":
      return {
        ...state,
        clock: createClock(state.clock.stageId),
        ledger: [],
        summary: null,
      };
    case "pause-if-running":
      return { ...state, clock: clockPause(state.clock, action.now) };
    case "sync-step": {
      const moved = clockChangeStage(state.clock, action.stepId, action.now);
      if (!moved.previous) {
        return { ...state, clock: moved.clock };
      }
      const ledger =
        moved.previous.elapsedMs > 0
          ? addLedger(state.ledger, moved.previous.stageId, moved.previous.elapsedMs)
          : state.ledger;
      return { ...state, clock: moved.clock, ledger };
    }
    case "start-rehearsal":
      return {
        ...state,
        enabled: true,
        collapsed: false,
        confirmRestart: false,
        helpOpen: false,
        summary: null,
        rehearsalActive: true,
        rehearsalStartedAt: action.startedAt,
        ledger: [],
        clock: clockStart(createClock("problem"), action.now),
      };
    case "ask-restart":
      if (!state.rehearsalActive) {
        return state;
      }
      return { ...state, confirmRestart: true, enabled: true, collapsed: false };
    case "cancel-restart":
      return { ...state, confirmRestart: false };
    case "finish": {
      if (!state.rehearsalActive) {
        return state;
      }
      const read = clockRead(state.clock, action.now);
      const summary = buildRehearsalSummary(
        ledgerConEtapaActual(state, action.now),
        stageTargetMs(state.totalDurationMs),
        read.totalMs,
      );
      const entry = toStoredRehearsal(summary, action.finishedAt);
      const history = state.saveHistory ? [entry, ...state.history].slice(0, MAX_STORED_REHEARSALS) : state.history;
      return {
        ...state,
        clock: clockPause(state.clock, action.now),
        rehearsalActive: false,
        summary,
        history,
        confirmRestart: false,
        enabled: true,
        collapsed: false,
      };
    }
    case "dismiss-summary":
      return { ...state, summary: null };
    case "open-help":
      return { ...state, helpOpen: true };
    case "close-help":
      return { ...state, helpOpen: false };
    case "toggle-help":
      return { ...state, helpOpen: !state.helpOpen };
    default: {
      const desconocida: never = action;
      return desconocida;
    }
  }
}
