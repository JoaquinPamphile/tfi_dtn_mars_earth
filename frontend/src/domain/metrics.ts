/**
 * Métricas científicas leídas del artefacto.
 * Un número de este módulo es el valor almacenado.
 * El texto que ve la defensa se arma aparte, en el formato de presentación.
 */

import type { StoredRecovery } from "./recovery";

/** Clave ausente, tipo inválido o par de campos que no coinciden. */
export interface MissingScientificValue {
  status: "missing";
  path: string;
}

/**
 * Clave presente.
 * value null es un null guardado en el artefacto, no un cero inventado.
 */
export interface StoredScientificValue {
  status: "stored";
  path: string;
  value: number | null;
}

export type ScientificValue = MissingScientificValue | StoredScientificValue;

export interface MetricGap {
  runLabel: string;
  path: string;
}

export interface RunStateMetrics {
  generated: ScientificValue;
  earthPersistedUnique: ScientificValue;
  confirmed: ScientificValue;
  backlog: ScientificValue;
  finalBacklog: ScientificValue;
  notPersistedOnEarth: ScientificValue;
  persistedOnEarthButUnconfirmed: ScientificValue;
  gapsCount: ScientificValue;
  completeness: ScientificValue;
  confirmationRatio: ScientificValue;
}

export interface RunTrafficMetrics {
  syncUnitsCreated: ScientificValue;
  telemetrySyncunitBytesCreated: ScientificValue;
  telemetryTransportBytes: ScientificValue;
  totalTransportApplicationBytes: ScientificValue;
}

export interface RunFreshnessMetrics {
  count: ScientificValue;
  coverage: ScientificValue;
  p50Seconds: ScientificValue;
  p95Seconds: ScientificValue;
}

export interface RunConvergenceMetrics {
  timeToConvergenceSeconds: ScientificValue;
  /** Booleano almacenado. null si la clave no está o no es booleana. */
  converged: boolean | null;
}

export interface RunContactMetrics {
  contactUtilizationWeighted: ScientificValue;
}

export interface StoredRunMetrics {
  state: RunStateMetrics;
  traffic: RunTrafficMetrics;
  freshness: RunFreshnessMetrics;
  convergence: RunConvergenceMetrics;
  contacts: RunContactMetrics;
}

/** Corrida ya normalizada. La UI no recorre el JSON. */
export interface RunMeasurement {
  id: string;
  index: number;
  label: string;
  strategyType: string | null;
  batchSizeEvents: number | null;
  offeredLoadFraction: number | null;
  metrics: StoredRunMetrics | null;
  gaps: MetricGap[];
  /** Episodio de recuperación ya escrito en metrics.recovery. null si la corrida no terminó. */
  recovery: StoredRecovery | null;
}

export interface E1TreatmentMetrics {
  key: string;
  label: string;
  strategyType: string | null;
  batchSizeEvents: number | null;
  syncUnitsCreated: ScientificValue;
  telemetryBytes: ScientificValue;
  freshnessCount: ScientificValue;
  freshnessCoverage: ScientificValue;
  freshnessP50Seconds: ScientificValue;
  freshnessP95Seconds: ScientificValue;
  timeToConvergenceSeconds: ScientificValue;
  completeness: ScientificValue;
  confirmationRatio: ScientificValue;
  backlog: ScientificValue;
  finalBacklog: ScientificValue;
}

/** Controles finales, solo si todas las corridas guardan el mismo valor. */
export interface E1SharedFinalState {
  completeness: number;
  confirmationRatio: number;
  finalBacklog: number;
}

export interface E1PresentationMetrics {
  ok: boolean;
  treatments: E1TreatmentMetrics[];
  gaps: MetricGap[];
  finalState: E1SharedFinalState | null;
}

export interface E2PointMetrics {
  runLabel: string;
  strategyLabel: string;
  loadFraction: number;
  loadLabel: string;
  generated: ScientificValue;
  earthPersistedUnique: ScientificValue;
  confirmed: ScientificValue;
  completeness: ScientificValue;
  confirmationRatio: ScientificValue;
  backlog: ScientificValue;
  finalBacklog: ScientificValue;
  notPersistedOnEarth: ScientificValue;
  persistedOnEarthButUnconfirmed: ScientificValue;
  freshnessCoverage: ScientificValue;
  timeToConvergenceSeconds: ScientificValue;
  contactUtilizationWeighted: ScientificValue;
}

export interface E2StrategyPanel {
  key: string;
  label: string;
  points: E2PointMetrics[];
}

/**
 * Lectura de los ratios almacenados en niveles consecutivos.
 * No es un umbral estimado: agrupa puntos ya observados con el mismo estado.
 */
export interface E2ObservedPattern {
  loadFractions: number[];
  rangeLabel: string;
  earth: string;
  origin: string;
}

export interface E2PresentationMetrics {
  ok: boolean;
  panels: E2StrategyPanel[];
  loads: { fraction: number; label: string }[];
  pattern: E2ObservedPattern[];
  gaps: MetricGap[];
  levelCount: number;
}

export function isStoredNumber(
  value: ScientificValue,
): value is StoredScientificValue & { value: number } {
  return value.status === "stored" && value.value !== null;
}
