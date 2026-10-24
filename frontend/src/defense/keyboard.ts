export type DefenseKeyAction =
  | "previous"
  | "next"
  | "first"
  | "last"
  | "close-menu"
  | "exit-presentation"
  | "toggle-presenter"
  | "toggle-timer"
  | "restart-rehearsal"
  | "toggle-help"
  | "close-help"
  | "cancel-restart"
  | "ignore";

export const DEFENSE_SHORTCUTS: readonly { keys: string; label: string }[] = [
  { keys: "← / →", label: "Etapa anterior / siguiente" },
  { keys: "Home / End", label: "Primera / última etapa" },
  { keys: "Espacio", label: "En E3, reproducir o pausar el episodio" },
  { keys: "J / K", label: "En E3, hito anterior / siguiente" },
  { keys: "P", label: "Activar o desactivar el presentador" },
  { keys: "T", label: "Iniciar o pausar el cronómetro" },
  { keys: "R", label: "Reiniciar el ensayo" },
  { keys: "?", label: "Mostrar u ocultar esta ayuda" },
  { keys: "Esc", label: "Cerrar la ayuda, o salir de la presentación" },
];

export function isEditableEventTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  if (target.isContentEditable) {
    return true;
  }
  const field = target.closest("input, textarea, select, [contenteditable='true']");
  if (!field) {
    return false;
  }
  if (field instanceof HTMLInputElement) {
    const tipo = field.type;
    if (tipo === "button" || tipo === "submit" || tipo === "reset" || tipo === "checkbox" || tipo === "radio") {
      return false;
    }
  }
  return true;
}

/** Botones, enlaces y campos. Las teclas del presentador no los pisan. */
export function isInteractiveEventTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  if (target.isContentEditable) {
    return true;
  }
  return Boolean(target.closest("a, button, input, textarea, select, summary"));
}

function presenterAction(key: string, fullscreen: boolean): DefenseKeyAction {
  if (key === "p" || key === "P") {
    return "toggle-presenter";
  }
  if (key === "t" || key === "T") {
    return "toggle-timer";
  }
  if (key === "r" || key === "R") {
    return fullscreen ? "ignore" : "restart-rehearsal";
  }
  if (key === "?") {
    return fullscreen ? "ignore" : "toggle-help";
  }
  return "ignore";
}

function esTeclaDePresentador(key: string): boolean {
  return key === "p" || key === "P" || key === "t" || key === "T" || key === "r" || key === "R" || key === "?";
}

/**
 * Decide la tecla de la defensa.
 * Escape cierra la ayuda, el aviso de reinicio y el selector antes de salir.
 * Si hay fullscreen, Escape lo deja al navegador.
 * P, T, R y ? no actúan sobre campos, botones ni enlaces.
 */
export function defenseKeyAction(
  key: string,
  options: {
    editable: boolean;
    interactive: boolean;
    modified: boolean;
    repeat: boolean;
    menuOpen: boolean;
    presenting: boolean;
    fullscreen: boolean;
    helpOpen: boolean;
    confirmOpen: boolean;
  },
): DefenseKeyAction {
  if (options.modified || options.repeat || options.editable) {
    return "ignore";
  }
  if (key === "Escape") {
    if (options.fullscreen) {
      return "ignore";
    }
    if (options.helpOpen) {
      return "close-help";
    }
    if (options.confirmOpen) {
      return "cancel-restart";
    }
    if (options.menuOpen) {
      return "close-menu";
    }
    if (options.presenting) {
      return "exit-presentation";
    }
    return "ignore";
  }
  if (options.helpOpen) {
    return key === "?" ? "close-help" : "ignore";
  }
  if (options.confirmOpen) {
    return "ignore";
  }
  if (esTeclaDePresentador(key)) {
    if (options.interactive) {
      return "ignore";
    }
    return presenterAction(key, options.fullscreen);
  }
  if (key === "ArrowRight") {
    return "next";
  }
  if (key === "ArrowLeft") {
    return "previous";
  }
  if (key === "Home") {
    return "first";
  }
  if (key === "End") {
    return "last";
  }
  return "ignore";
}
