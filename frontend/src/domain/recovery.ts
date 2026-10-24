import type { MetricGap, ScientificValue } from "./metrics";
import { formatBytes, formatCount, formatPercent, formatRawNumber, formatSeconds } from "./metricFormat";
import type { DirectedContact } from "./scenario";
import { formatSimSeconds } from "./scenarioFormat";

/**
 * Lectura y presentación del episodio de recuperación.
 * Los segundos científicos son los del artefacto.
 * El texto es solo de lectura: no es otra métrica.
 */

export type RecoveryEventKind =
  | "loss"
  | "gap-observed"
  | "recovery-trigger"
  | "recovery-departure"
  | "earth-recovered"
  | "origin-confirmed";

export type RecoveryActor = "relay" | "earth" | "mars";

export interface RecoveryEvent {
  id: string;
  kind: RecoveryEventKind;
  scientificSeconds: number;
  displayTime: string;
  actor: RecoveryActor;
  label: string;
  narrative: string;
  sourceRunLabel: string;
  sourcePath: string;
}

export interface DisplayMetric {
  scientific: number | null;
  display: string;
  raw: string;
  path: string;
  /** La clave existe. value null guardado queda con scientific null y present true. */
  present: boolean;
}

export interface RecoveryTrafficView {
  forward: DisplayMetric;
  reverse: DisplayMetric;
  total: DisplayMetric;
  /** El intento perdido común está en otros campos y no entra en el total. */
  separatesCommonLostAttempt: boolean;
}

export interface RecoveryCountsView {
  senderTimeouts: DisplayMetric;
  senderRetries: DisplayMetric;
  gapRequests: DisplayMetric;
  repairAttempts: DisplayMetric;
}

export interface RecoveryLatencyView {
  lossToTrigger: DisplayMetric;
  lossToEarth: DisplayMetric;
  lossToOrigin: DisplayMetric;
}

export interface RecoveryFinalState {
  completeness: DisplayMetric;
  confirmation: DisplayMetric;
  backlog: DisplayMetric;
  converged: boolean | null;
}

export interface RecoveryTimelineRun {
  label: string;
  policy: "sender-driven" | "receiver-driven";
  policyLabel: string;
  failureEnabled: boolean;
  sequenceNumber: number | null;
  events: RecoveryEvent[];
  latencies: RecoveryLatencyView;
  traffic: RecoveryTrafficView;
  counts: RecoveryCountsView;
  finalState: RecoveryFinalState;
}

export interface RecoveryPlaybackStep {
  id: string;
  kind: RecoveryEventKind;
  timeSeconds: number;
  displayTime: string;
  narrative: string;
  scopeLabel: string;
  eventIds: readonly string[];
}

export interface RecoveryControlPair {
  senderLabel: string;
  receiverLabel: string;
  sameFinalState: boolean;
  noRecoveryEpisodes: boolean;
  completeness: string;
  confirmation: string;
  backlog: string;
  episodeCount: string;
}

export interface RecoveryOfficialView {
  sender: RecoveryTimelineRun;
  receiver: RecoveryTimelineRun;
  sameLoss: boolean;
  controls: RecoveryControlPair | null;
  steps: RecoveryPlaybackStep[];
}

export interface RecoverySensitivityPoint {
  sequenceNumber: number;
  sequenceLabel: string;
  officialCase: boolean;
  sender: RecoveryTimelineRun;
  receiver: RecoveryTimelineRun;
}

export interface RecoverySensitivityView {
  points: RecoverySensitivityPoint[];
  receiverTriggersEarlier: boolean;
  receiverRecoversEarthEarlier: boolean;
  receiverUsesLessTraffic: boolean;
  originDirectionStable: boolean;
}

export interface E3RecoveryPresentation {
  ok: boolean;
  gaps: MetricGap[];
  official: RecoveryOfficialView | null;
  sensitivity: RecoverySensitivityView | null;
}

export interface StoredRecoveryEpisode {
  trigger: string | null;
  sequenceNumber: number | null;
  lossAt: ScientificValue;
  gapObservedAt: ScientificValue;
  triggeredAt: ScientificValue;
  departedAt: ScientificValue;
  earthAt: ScientificValue;
  originAt: ScientificValue;
  commonLostMarsRelay: ScientificValue;
  commonLostRelayEarth: ScientificValue;
}

/** Campos ya escritos en metrics.recovery. No incluye intervalos recalculados. */
export interface StoredRecovery {
  episodeCount: ScientificValue;
  latencies: {
    lossToTrigger: ScientificValue;
    triggerToEarth: ScientificValue;
    lossToEarth: ScientificValue;
    earthToOrigin: ScientificValue;
    lossToOrigin: ScientificValue;
  };
  counts: {
    senderTimeouts: ScientificValue;
    senderRetries: ScientificValue;
    gapRequests: ScientificValue;
    repairAttempts: ScientificValue;
  };
  traffic: {
    forward: ScientificValue;
    reverse: ScientificValue;
    total: ScientificValue;
  };
  episode: StoredRecoveryEpisode | null;
  gaps: string[];
}

export const EVENT_LABEL: Record<RecoveryEventKind, string> = {
  loss: "LOSS",
  "gap-observed": "GAP OBSERVABLE",
  "recovery-trigger": "RECOVERY TRIGGER",
  "recovery-departure": "RECOVERY DATA DEPARTURE",
  "earth-recovered": "EARTH RECOVERED",
  "origin-confirmed": "ORIGIN CONFIRMED",
};

export const MILESTONE_ORDER: readonly RecoveryEventKind[] = [
  "loss",
  "gap-observed",
  "recovery-trigger",
  "recovery-departure",
  "earth-recovered",
  "origin-confirmed",
];

export const MILESTONE_LEGEND: Record<RecoveryEventKind, string> = {
  loss: "LOSS",
  "gap-observed": "GAP",
  "recovery-trigger": "TRIGGER",
  "recovery-departure": "SALIDA",
  "earth-recovered": "TIERRA",
  "origin-confirmed": "MARTE",
};

const KIND_RANK: Record<RecoveryEventKind, number> = {
  loss: 0,
  "gap-observed": 1,
  "recovery-trigger": 2,
  "recovery-departure": 3,
  "earth-recovered": 4,
  "origin-confirmed": 5,
};

export function displayDuration(value: number): string {
  if (Math.abs(value) < 1) {
    const text = value.toLocaleString("es-AR", {
      minimumFractionDigits: 3,
      maximumFractionDigits: 3,
    });
    return `${text} s`;
  }
  return formatSeconds(value);
}

export function displayInstant(value: number): string {
  return formatSimSeconds(value);
}

export function displayMetric(
  value: ScientificValue,
  format: (number: number) => string,
  emptyLabel: string,
): DisplayMetric {
  if (value.status === "missing") {
    return {
      scientific: null,
      display: "No disponible en evidence",
      raw: "",
      path: value.path,
      present: false,
    };
  }
  if (value.value === null) {
    return {
      scientific: null,
      display: emptyLabel,
      raw: "null",
      path: value.path,
      present: true,
    };
  }
  return {
    scientific: value.value,
    display: format(value.value),
    raw: formatRawNumber(value.value),
    path: value.path,
    present: true,
  };
}

export function displayCount(value: ScientificValue): DisplayMetric {
  return displayMetric(value, formatCount, "—");
}

export function displayBytes(value: ScientificValue): DisplayMetric {
  return displayMetric(value, formatBytes, "—");
}

export function displayLatency(value: ScientificValue): DisplayMetric {
  return displayMetric(value, displayDuration, "—");
}

export function displayRatio(value: ScientificValue): DisplayMetric {
  return displayMetric(value, (number) => formatPercent(number, 0), "—");
}

export function narrativeFor(kind: RecoveryEventKind, trigger: string | null): string {
  switch (kind) {
    case "loss":
      return "El relay completó el envío, pero Tierra no recibió la entrega de aplicación.";
    case "gap-observed":
      return "Tierra observa una secuencia ausente.";
    case "recovery-trigger":
      if (trigger === "SENDER_ACK_TIMEOUT") {
        return "Marte sólo puede inferir el problema cuando vence el timeout.";
      }
      if (trigger === "RECEIVER_GAP_REQUEST") {
        return "Tierra pide la secuencia ausente con un GapRequest.";
      }
      return "La política dispara la recuperación.";
    case "recovery-departure":
      if (trigger === "SENDER_ACK_TIMEOUT") {
        return "Marte reenvía el dato después del timeout.";
      }
      if (trigger === "RECEIVER_GAP_REQUEST") {
        return "Marte reenvía el dato pedido por el GapRequest.";
      }
      return "El dato de recuperación sale de Marte.";
    case "earth-recovered":
      return "El dato ya vuelve a estar disponible en Tierra.";
    case "origin-confirmed":
      return "Marte finalmente conoce la aceptación terrestre.";
    default: {
      const desconocido: never = kind;
      return desconocido;
    }
  }
}

export function actorFor(kind: RecoveryEventKind, trigger: string | null): RecoveryActor {
  if (kind === "loss") {
    return "relay";
  }
  if (kind === "gap-observed" || kind === "earth-recovered") {
    return "earth";
  }
  if (kind === "origin-confirmed" || kind === "recovery-departure") {
    return "mars";
  }
  if (trigger === "RECEIVER_GAP_REQUEST") {
    return "earth";
  }
  return "mars";
}

export function buildPlaybackSteps(events: readonly RecoveryEvent[]): RecoveryPlaybackStep[] {
  const sorted = [...events].sort((left, right) => {
    if (left.scientificSeconds !== right.scientificSeconds) {
      return left.scientificSeconds - right.scientificSeconds;
    }
    const rank = KIND_RANK[left.kind] - KIND_RANK[right.kind];
    if (rank !== 0) {
      return rank;
    }
    return left.sourceRunLabel.localeCompare(right.sourceRunLabel);
  });
  const steps: RecoveryPlaybackStep[] = [];
  for (const event of sorted) {
    const last = steps[steps.length - 1];
    if (last && last.kind === event.kind && last.timeSeconds === event.scientificSeconds) {
      steps[steps.length - 1] = {
        ...last,
        scopeLabel: event.kind === "loss" ? "Misma pérdida" : "Ambas corridas",
        eventIds: [...last.eventIds, event.id],
      };
      continue;
    }
    steps.push({
      id: `${event.kind}@${event.scientificSeconds}`,
      kind: event.kind,
      timeSeconds: event.scientificSeconds,
      displayTime: event.displayTime,
      narrative: event.narrative,
      scopeLabel: event.sourceRunLabel,
      eventIds: [event.id],
    });
  }
  return steps;
}

/**
 * Elige contactos ya almacenados para señalarlos.
 * No calcula una espera ni una métrica nueva.
 * Previo: el último retorno a Marte que ya cerró antes de todas las recuperaciones en Tierra.
 * Siguiente: el contacto que contiene todas las confirmaciones de origen almacenadas.
 */
export function selectReturnOpportunities(
  contacts: readonly DirectedContact[],
  earthAt: readonly number[],
  originAt: readonly number[],
): { previous: DirectedContact | null; next: DirectedContact | null } {
  if (earthAt.length === 0 || originAt.length === 0 || contacts.length === 0) {
    return { previous: null, next: null };
  }
  const earliestEarth = Math.min(...earthAt);
  const sorted = [...contacts].sort(
    (left, right) => left.startSeconds - right.startSeconds || left.id.localeCompare(right.id),
  );
  const previous =
    [...sorted].reverse().find((contact) => contact.endSeconds <= earliestEarth) ?? null;
  const next =
    sorted.find((contact) =>
      originAt.every(
        (instant) => instant >= contact.startSeconds && instant <= contact.endSeconds,
      ),
    ) ?? null;
  return { previous, next };
}

export function contactWindow(contact: DirectedContact): string {
  return `${formatSimSeconds(contact.startSeconds)} – ${formatSimSeconds(contact.endSeconds)}`;
}

/**
 * Dominio visual. El relleno no cambia las distancias entre hitos.
 * No es una métrica científica.
 */
export function episodeDomain(
  events: readonly RecoveryEvent[],
  bands: readonly DirectedContact[],
  mode: "episode" | "scenario",
  horizonSeconds: number | null,
): { start: number; end: number } {
  if (mode === "scenario" && horizonSeconds !== null && horizonSeconds > 0) {
    return { start: 0, end: horizonSeconds };
  }
  const times = events.map((event) => event.scientificSeconds);
  for (const band of bands) {
    times.push(band.startSeconds, band.endSeconds);
  }
  if (times.length === 0) {
    return { start: 0, end: 1 };
  }
  const min = Math.min(...times);
  const max = Math.max(...times);
  const pad = Math.max(max - min, 1) * 0.04;
  return { start: min - pad, end: max + pad };
}

export function numbersOf(metric: DisplayMetric): number | null {
  return metric.present && metric.scientific !== null ? metric.scientific : null;
}

/** Comprueba el total almacenado. No lo reemplaza por la suma. */
export function stackAgrees(traffic: RecoveryTrafficView): boolean {
  const forward = numbersOf(traffic.forward);
  const reverse = numbersOf(traffic.reverse);
  const total = numbersOf(traffic.total);
  if (forward === null || reverse === null || total === null) {
    return false;
  }
  return forward + reverse === total;
}
