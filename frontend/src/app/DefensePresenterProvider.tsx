import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { defensePath } from "../defense/defenseSteps";
import { createPresenterState, reducePresenter, type PresenterState } from "../defense/presenterState";
import type { LedgerEntry, RehearsalSummary, StoredRehearsal } from "../defense/rehearsal";
import { readPresenterPrefs, readStoredRehearsals, writePresenterPrefs, writeStoredRehearsals } from "../defense/storage";
import { clampTotalDuration, stageTargetMs } from "../defense/timing";
import type { DefenseClock } from "../defense/timer";
import type { DefenseStepId } from "../defense/types";

/**
 * Estado compartido del presentador.
 * La pantalla pública no lo renderiza.
 * Un PresenterWindow futuro puede consumir este mismo contexto.
 */

interface DefensePresenterContextValue {
  enabled: boolean;
  collapsed: boolean;
  totalDurationMs: number;
  saveHistory: boolean;
  clock: DefenseClock;
  ledger: readonly LedgerEntry[];
  rehearsalActive: boolean;
  summary: RehearsalSummary | null;
  history: readonly StoredRehearsal[];
  helpOpen: boolean;
  confirmRestart: boolean;
  targets: Record<DefenseStepId, number>;
  toggleEnabled: () => void;
  collapse: () => void;
  expand: () => void;
  setTotalDurationMs: (totalMs: number) => void;
  setSaveHistory: (saveHistory: boolean) => void;
  toggleTimer: () => void;
  resetTimer: () => void;
  requestRehearsal: () => void;
  confirmRestartNow: () => void;
  cancelRestart: () => void;
  finishRehearsal: () => void;
  dismissSummary: () => void;
  openHelp: () => void;
  closeHelp: () => void;
  toggleHelp: () => void;
  syncStep: (stepId: DefenseStepId) => void;
}

const DefensePresenterContext = createContext<DefensePresenterContextValue | null>(null);

export function DefensePresenterProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [state, dispatch] = useReducer(reducePresenter, undefined, () =>
    createPresenterState(readPresenterPrefs(), readStoredRehearsals()),
  );
  const estado = useRef(state);
  estado.current = state;
  const pasoSincronizado = useRef<DefenseStepId | null>(null);
  const estabaEnDefensa = useRef(location.pathname.startsWith("/defensa"));

  useEffect(() => {
    writePresenterPrefs({
      enabled: state.enabled,
      collapsed: state.collapsed,
      totalDurationMs: state.totalDurationMs,
      saveHistory: state.saveHistory,
    });
  }, [state.collapsed, state.enabled, state.saveHistory, state.totalDurationMs]);

  useEffect(() => {
    writeStoredRehearsals(state.history);
  }, [state.history]);

  useEffect(() => {
    const enDefensa = location.pathname.startsWith("/defensa");
    if (estabaEnDefensa.current && !enDefensa) {
      dispatch({ type: "pause-if-running", now: Date.now() });
    }
    estabaEnDefensa.current = enDefensa;
  }, [location.pathname]);

  const beginRehearsal = useCallback(() => {
    pasoSincronizado.current = "problem";
    dispatch({
      type: "start-rehearsal",
      now: Date.now(),
      startedAt: new Date().toISOString(),
    });
    navigate(defensePath("problem"));
  }, [navigate]);

  const targets = useMemo(() => stageTargetMs(state.totalDurationMs), [state.totalDurationMs]);

  const valor = useMemo<DefensePresenterContextValue>(() => {
    return {
      enabled: state.enabled,
      collapsed: state.collapsed,
      totalDurationMs: state.totalDurationMs,
      saveHistory: state.saveHistory,
      clock: state.clock,
      ledger: state.ledger,
      rehearsalActive: state.rehearsalActive,
      summary: state.summary,
      history: state.history,
      helpOpen: state.helpOpen,
      confirmRestart: state.confirmRestart,
      targets,
      toggleEnabled: () => dispatch({ type: "toggle-enabled" }),
      collapse: () => dispatch({ type: "set-collapsed", collapsed: true }),
      expand: () => dispatch({ type: "set-collapsed", collapsed: false }),
      setTotalDurationMs: (totalMs: number) =>
        dispatch({ type: "set-duration", totalDurationMs: clampTotalDuration(totalMs) }),
      setSaveHistory: (saveHistory: boolean) => dispatch({ type: "set-save-history", saveHistory }),
      toggleTimer: () => dispatch({ type: "toggle-timer", now: Date.now() }),
      resetTimer: () => dispatch({ type: "reset-timer" }),
      requestRehearsal: () => {
        if (estado.current.rehearsalActive) {
          dispatch({ type: "ask-restart" });
          return;
        }
        beginRehearsal();
      },
      confirmRestartNow: () => beginRehearsal(),
      cancelRestart: () => dispatch({ type: "cancel-restart" }),
      finishRehearsal: () =>
        dispatch({ type: "finish", now: Date.now(), finishedAt: new Date().toISOString() }),
      dismissSummary: () => dispatch({ type: "dismiss-summary" }),
      openHelp: () => dispatch({ type: "open-help" }),
      closeHelp: () => dispatch({ type: "close-help" }),
      toggleHelp: () => dispatch({ type: "toggle-help" }),
      syncStep: (stepId: DefenseStepId) => {
        if (pasoSincronizado.current === stepId) {
          return;
        }
        pasoSincronizado.current = stepId;
        dispatch({ type: "sync-step", stepId, now: Date.now() });
      },
    };
  }, [beginRehearsal, state, targets]);

  return <DefensePresenterContext.Provider value={valor}>{children}</DefensePresenterContext.Provider>;
}

export function useDefensePresenter(): DefensePresenterContextValue {
  const contexto = useContext(DefensePresenterContext);
  if (!contexto) {
    throw new Error("useDefensePresenter debe usarse dentro de DefensePresenterProvider.");
  }
  return contexto;
}

export type { PresenterState };
