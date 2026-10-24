/**
 * Modelo del Modo Defensa.
 * DefenseSpeakerNotes es contenido editorial del presentador.
 * La secuencia pública no lo renderiza y no forma parte de la evidence.
 */

export type DefenseStepId =
  | "problem"
  | "core-idea"
  | "application-model"
  | "architecture"
  | "scenario"
  | "e1"
  | "e2"
  | "e3"
  | "validity"
  | "conclusions";

export interface DefenseStep {
  id: DefenseStepId;
  /** Número visible, por ejemplo 06. Sale de la posición en la secuencia. */
  number: string;
  title: string;
  subtitle?: string;
  /** Rótulo corto del encabezado, por ejemplo E1 · GRANULARIDAD. */
  section: string;
  /**
   * Reservado para un anfitrión que quiera colgar las notas del paso.
   * DEFENSE_STEPS no lo llena: el texto vive en speakerNotes.ts.
   */
  speakerNotes?: DefenseSpeakerNotes;
}

export interface SpeakerLink {
  label: string;
  href: string;
}

export interface SpeakerQuestion {
  prompt: string;
  answer: string;
  links?: readonly SpeakerLink[];
}

/** Cierre recomendado. Solo lo muestra el presentador en la última etapa. */
export interface SpeakerClosing {
  ideas: readonly string[];
  phrase: string;
}

/**
 * Notas privadas del presentador.
 * No son evidence, no copian métricas y no se muestran en la pantalla pública.
 * La duración objetivo sale de timing.ts, no de este texto.
 */
export interface DefenseSpeakerNotes {
  stepId: DefenseStepId;
  objective: string;
  say: readonly string[];
  /** Puente hacia la etapa siguiente. La última etapa no lo tiene. */
  transition?: string;
  remember: readonly string[];
  questions: readonly SpeakerQuestion[];
  closing?: SpeakerClosing;
}

export interface DefenseNavigationState {
  step: DefenseStep | undefined;
  index: number;
  total: number;
  hasPrevious: boolean;
  hasNext: boolean;
  goTo: (id: DefenseStepId) => void;
  goPrevious: () => void;
  goNext: () => void;
  goFirst: () => void;
  goLast: () => void;
}
