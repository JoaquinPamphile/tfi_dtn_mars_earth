import { formatOfferedLoad } from "../../domain/metricFormat";
import type {
  E2ObservedPattern,
  E2PointMetrics,
  E2PresentationMetrics,
  E2StrategyPanel,
  MetricGap,
  RunMeasurement,
  ScientificValue,
} from "../../domain/metrics";
import { isStoredNumber } from "../../domain/metrics";
import { treatmentLabel } from "./presentE1";

/**
 * Arma E2 por carga ofrecida almacenada y por estrategia, en el orden del artefacto.
 * El patrón solo agrupa niveles cuyos ratios guardados coinciden.
 * No estima un umbral ni recalcula completeness ni confirmation_ratio.
 */

type Qualitative = "complete" | "incomplete" | "mixed" | "unavailable";

export function mapE2MetricsForPresentation(
  measurements: readonly RunMeasurement[],
): E2PresentationMetrics {
  const gaps: MetricGap[] = [];
  const loadOrder: number[] = [];
  const panelOrder: string[] = [];
  const grouped = new Map<string, E2PointMetrics[]>();
  const seen = new Set<string>();

  for (const measurement of measurements) {
    gaps.push(...measurement.gaps);
    if (measurement.offeredLoadFraction === null) {
      gaps.push({
        runLabel: measurement.label,
        path: "manifest.workload.offered_load_fraction",
      });
      return empty(gaps);
    }
    const strategy = treatmentLabel(measurement.strategyType, measurement.batchSizeEvents);
    const panelKey = `${measurement.strategyType ?? "none"}:${measurement.batchSizeEvents ?? "none"}`;
    const pointKey = `${panelKey}@${measurement.offeredLoadFraction}`;
    if (seen.has(pointKey)) {
      gaps.push({
        runLabel: measurement.label,
        path: `carga repetida: ${formatOfferedLoad(measurement.offeredLoadFraction)} ${strategy}`,
      });
      return empty(gaps);
    }
    seen.add(pointKey);
    if (!loadOrder.includes(measurement.offeredLoadFraction)) {
      loadOrder.push(measurement.offeredLoadFraction);
    }
    if (!grouped.has(panelKey)) {
      grouped.set(panelKey, []);
      panelOrder.push(panelKey);
    }
    grouped.get(panelKey)?.push(toPoint(measurement, strategy));
  }

  if (panelOrder.length === 0 || loadOrder.length === 0) {
    gaps.push({ runLabel: "E2", path: "metrics" });
    return empty(gaps);
  }

  const panels: E2StrategyPanel[] = panelOrder.map((key) => {
    const points = grouped.get(key) ?? [];
    points.sort(
      (left, right) => loadOrder.indexOf(left.loadFraction) - loadOrder.indexOf(right.loadFraction),
    );
    return {
      key,
      label: points[0]?.strategyLabel ?? key,
      points,
    };
  });

  return {
    ok: true,
    panels,
    loads: loadOrder.map((fraction) => ({ fraction, label: formatOfferedLoad(fraction) })),
    pattern: observedPattern(panels, loadOrder),
    gaps,
    levelCount: loadOrder.length,
  };
}

function empty(gaps: MetricGap[]): E2PresentationMetrics {
  return { ok: false, panels: [], loads: [], pattern: [], gaps, levelCount: 0 };
}

function toPoint(measurement: RunMeasurement, strategyLabel: string): E2PointMetrics {
  const metrics = measurement.metrics;
  const loadFraction = measurement.offeredLoadFraction ?? 0;
  return {
    runLabel: measurement.label,
    strategyLabel,
    loadFraction,
    loadLabel: formatOfferedLoad(loadFraction),
    generated: field(metrics?.state.generated, "metrics.generated"),
    earthPersistedUnique: field(
      metrics?.state.earthPersistedUnique,
      "metrics.earth_persisted_unique",
    ),
    confirmed: field(metrics?.state.confirmed, "metrics.confirmed"),
    completeness: field(metrics?.state.completeness, "metrics.completeness"),
    confirmationRatio: field(metrics?.state.confirmationRatio, "metrics.confirmation_ratio"),
    backlog: field(metrics?.state.backlog, "metrics.backlog"),
    finalBacklog: field(metrics?.state.finalBacklog, "metrics.final_backlog"),
    notPersistedOnEarth: field(
      metrics?.state.notPersistedOnEarth,
      "metrics.not_persisted_on_earth",
    ),
    persistedOnEarthButUnconfirmed: field(
      metrics?.state.persistedOnEarthButUnconfirmed,
      "metrics.persisted_on_earth_but_unconfirmed",
    ),
    freshnessCoverage: field(metrics?.freshness.coverage, "metrics.freshness_coverage"),
    timeToConvergenceSeconds: field(
      metrics?.convergence.timeToConvergenceSeconds,
      "metrics.time_to_convergence_seconds",
    ),
    contactUtilizationWeighted: field(
      metrics?.contacts.contactUtilizationWeighted,
      "metrics.contacts.contact_utilization_weighted",
    ),
  };
}

function field(value: ScientificValue | undefined, path: string): ScientificValue {
  return value ?? { status: "missing", path };
}

function observedPattern(
  panels: readonly E2StrategyPanel[],
  loadOrder: readonly number[],
): E2ObservedPattern[] {
  const states = loadOrder.map((fraction) => ({
    fraction,
    state: stateAtLoad(panels, fraction),
  }));
  const groups: { fractions: number[]; state: string }[] = [];
  for (const item of states) {
    const previous = groups[groups.length - 1];
    if (previous && previous.state === item.state && item.state !== "unavailable") {
      previous.fractions.push(item.fraction);
    } else {
      groups.push({ fractions: [item.fraction], state: item.state });
    }
  }
  const pattern: E2ObservedPattern[] = [];
  for (const group of groups) {
    const phrases = patternPhrases(group.state);
    if (!phrases) {
      continue;
    }
    pattern.push({
      loadFractions: group.fractions,
      rangeLabel: rangeLabel(group.fractions),
      earth: phrases.earth,
      origin: phrases.origin,
    });
  }
  return pattern;
}

function stateAtLoad(panels: readonly E2StrategyPanel[], fraction: number): string {
  const points = panels.flatMap((panel) => panel.points.filter((point) => point.loadFraction === fraction));
  if (points.length === 0) {
    return "unavailable";
  }
  const earth = qualitative(points.map((point) => point.completeness));
  const origin = qualitative(points.map((point) => point.confirmationRatio));
  if (earth === "unavailable" || origin === "unavailable" || earth === "mixed" || origin === "mixed") {
    return "unavailable";
  }
  return `${earth}:${origin}`;
}

function qualitative(values: readonly ScientificValue[]): Qualitative {
  if (values.length === 0 || values.some((value) => !isStoredNumber(value))) {
    return "unavailable";
  }
  const numbers = values.map((value) => (isStoredNumber(value) ? value.value : Number.NaN));
  if (numbers.every((value) => value === 1)) {
    return "complete";
  }
  if (numbers.every((value) => value < 1)) {
    return "incomplete";
  }
  return "mixed";
}

function patternPhrases(state: string): { earth: string; origin: string } | null {
  switch (state) {
    case "complete:complete":
      return { earth: "Tierra completa", origin: "Marte confirmado" };
    case "complete:incomplete":
      return { earth: "Tierra completa", origin: "Marte incompleto" };
    case "incomplete:incomplete":
      return { earth: "Tierra incompleta", origin: "Marte incompleto" };
    case "incomplete:complete":
      return { earth: "Tierra incompleta", origin: "Marte confirmado" };
    default:
      return null;
  }
}

function rangeLabel(fractions: readonly number[]): string {
  const labels = fractions.map((fraction) => formatOfferedLoad(fraction));
  const first = labels[0] ?? "";
  const last = labels[labels.length - 1] ?? first;
  if (labels.length < 2) {
    return first;
  }
  return `${first.replace(" %", "")}–${last}`;
}
