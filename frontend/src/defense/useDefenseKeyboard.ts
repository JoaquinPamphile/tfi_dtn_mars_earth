import { useEffect, useRef } from "react";
import { defenseKeyAction, isEditableEventTarget, isInteractiveEventTarget } from "./keyboard";

interface DefenseKeyboardInput {
  menuOpen: boolean;
  presenting: boolean;
  fullscreen: boolean;
  helpOpen: boolean;
  confirmOpen: boolean;
  closeMenu: () => void;
  exitPresentation: () => void;
  goPrevious: () => void;
  goNext: () => void;
  goFirst: () => void;
  goLast: () => void;
  togglePresenter: () => void;
  toggleTimer: () => void;
  restartRehearsal: () => void;
  toggleHelp: () => void;
  closeHelp: () => void;
  cancelRestart: () => void;
}

export function useDefenseKeyboard(input: DefenseKeyboardInput): void {
  const actual = useRef(input);
  actual.current = input;

  useEffect(() => {
    const alPulsar = (event: KeyboardEvent) => {
      const estado = actual.current;
      const accion = defenseKeyAction(event.key, {
        editable: isEditableEventTarget(event.target),
        interactive: isInteractiveEventTarget(event.target),
        modified: event.altKey || event.ctrlKey || event.metaKey,
        repeat: event.repeat,
        menuOpen: estado.menuOpen,
        presenting: estado.presenting,
        fullscreen: estado.fullscreen,
        helpOpen: estado.helpOpen,
        confirmOpen: estado.confirmOpen,
      });
      if (accion === "ignore") {
        return;
      }
      event.preventDefault();
      switch (accion) {
        case "previous":
          estado.goPrevious();
          break;
        case "next":
          estado.goNext();
          break;
        case "first":
          estado.goFirst();
          break;
        case "last":
          estado.goLast();
          break;
        case "close-menu":
          estado.closeMenu();
          break;
        case "exit-presentation":
          estado.exitPresentation();
          break;
        case "toggle-presenter":
          estado.togglePresenter();
          break;
        case "toggle-timer":
          estado.toggleTimer();
          break;
        case "restart-rehearsal":
          estado.restartRehearsal();
          break;
        case "toggle-help":
          estado.toggleHelp();
          break;
        case "close-help":
          estado.closeHelp();
          break;
        case "cancel-restart":
          estado.cancelRestart();
          break;
        default:
          break;
      }
    };
    window.addEventListener("keydown", alPulsar);
    return () => window.removeEventListener("keydown", alPulsar);
  }, []);
}
