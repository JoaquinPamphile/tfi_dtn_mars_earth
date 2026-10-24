import type {
  E1PresentationMetrics,
  E1SharedFinalState,
  E1TreatmentMetrics,
  MetricGap,
  RunMeasurement,
  ScientificValue,
} from "../../domain/metrics";
import { isStoredNumber } from "../../domain/metrics";

/**
 * Ordena los tratamientos de E1 como vienen en la evidence.
 * No calcula porcentajes de reducción ni elige un batch.
 */

export function mapE1MetricsForPresentation(
  measurements: readonly RunMeasurement[],
): E1PresentationMetrics {
  const gaps: MetricGap[] = [];
  const treatments: E1TreatmentMetrics[] = [];
  const seen = new Set<string>();

  for (const measurement of measurements) {
    gaps.push(...measurement.gaps);
    const label = treatmentLabel(measurement.strategyType, measurement.batchSizeEvents);
    const key = treatmentKey(measurement.strategyType, measurement.batchSizeEvents);
    if (seen.has(key)) {
      gaps.push({ runLabel: measurement.label, path: `tratamiento repetido: ${label}` });
      return { ok: false, treatments: [], gaps, finalState: null };
    }
    seen.add(key);
    treatments.push(toTreatment(measurement, key, label));
  }

  if (treatments.length === 0) {
    gaps.push({ runLabel: "E1", path: "metrics" });
    return { ok: false, treatments: [], gaps, finalState: null };
  }

  return {
    ok: true,
    treatments,
    gaps,
    finalState: sharedFinal(treatments),
  };
}

export function treatmentLabel(strategyType: string | null, batchSizeEvents: number | null): string {
  if (strategyType === "individual") {
    return "Individual";
  }
  if (strategyType === "fixed_batch" && batchSizeEvents !== null) {
    return `Batch${batchSizeEvents}`;
  }
  if (batchSizeEvents !== null) {
    return `Batch${batchSizeEvents}`;
  }
  return strategyType ?? "Sin estrategia";
}

function treatmentKey(strategyType: string | null, batchSizeEvents: number | null): string {
  return `${strategyType ?? "none"}:${batchSizeEvents ?? "none"}`;
}

function toTreatment(measurement: RunMeasurement, key: string, label: string): E1TreatmentMetrics {
  const metrics = measurement.metrics;
  return {
    key,
    label,
    strategyType: measurement.strategyType,
    batchSizeEvents: measurement.batchSizeEvents,
    syncUnitsCreated: field(metrics?.traffic.syncUnitsCreated, "metrics.sync_units_created"),
    telemetryBytes: field(
      metrics?.traffic.telemetrySyncunitBytesCreated,
      "metrics.traffic.telemetry_syncunit_bytes_created",
    ),
    freshnessCount: field(metrics?.freshness.count, "metrics.freshness.count"),
    freshnessCoverage: field(metrics?.freshness.coverage, "metrics.freshness_coverage"),
    freshnessP50Seconds: field(metrics?.freshness.p50Seconds, "metrics.freshness.p50_seconds"),
    freshnessP95Seconds: field(metrics?.freshness.p95Seconds, "metrics.freshness.p95_seconds"),
    timeToConvergenceSeconds: field(
      metrics?.convergence.timeToConvergenceSeconds,
      "metrics.time_to_convergence_seconds",
    ),
    completeness: field(metrics?.state.completeness, "metrics.completeness"),
    confirmationRatio: field(metrics?.state.confirmationRatio, "metrics.confirmation_ratio"),
    backlog: field(metrics?.state.backlog, "metrics.backlog"),
    finalBacklog: field(metrics?.state.finalBacklog, "metrics.final_backlog"),
  };
}

function field(value: ScientificValue | undefined, path: string): ScientificValue {
  return value ?? { status: "missing", path };
}

function sharedFinal(treatments: readonly E1TreatmentMetrics[]): E1SharedFinalState | null {
  const completeness = uniform(treatments.map((item) => item.completeness));
  const confirmationRatio = uniform(treatments.map((item) => item.confirmationRatio));
  const finalBacklog = uniform(treatments.map((item) => item.finalBacklog));
  if (completeness === null || confirmationRatio === null || finalBacklog === null) {
    return null;
  }
  return { completeness, confirmationRatio, finalBacklog };
}

function uniform(values: readonly ScientificValue[]): number | null {
  const first = values[0];
  if (!first || !isStoredNumber(first)) {
    return null;
  }
  for (const value of values) {
    if (!isStoredNumber(value) || value.value !== first.value) {
      return null;
    }
  }
  return first.value;
}
