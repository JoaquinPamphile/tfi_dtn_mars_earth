import type {
  MetricGap,
  RunContactMetrics,
  RunConvergenceMetrics,
  RunFreshnessMetrics,
  RunStateMetrics,
  RunTrafficMetrics,
  ScientificValue,
  StoredRunMetrics,
} from "../../domain/metrics";

/**
 * Lee metrics ya escritas en el manifiesto de la corrida.
 * No completa huecos con cero y no deriva una magnitud a partir de otra.
 */

export interface StoredMetricsRead {
  metrics: StoredRunMetrics;
  paths: string[];
}

export function readStoredMetrics(value: unknown, path: string): StoredMetricsRead {
  const gaps: string[] = [];
  const root = asRecord(value);
  if (!root) {
    return { metrics: emptyMetrics(path), paths: [path] };
  }
  const traffic = asRecord(root.traffic);
  const freshness = asRecord(root.freshness);
  const contacts = asRecord(root.contacts);

  const state: RunStateMetrics = {
    generated: take(readRequiredNumber(root, "generated", path), gaps),
    earthPersistedUnique: take(readRequiredNumber(root, "earth_persisted_unique", path), gaps),
    confirmed: take(readRequiredNumber(root, "confirmed", path), gaps),
    backlog: take(readRequiredNumber(root, "backlog", path), gaps),
    finalBacklog: take(readRequiredNumber(root, "final_backlog", path), gaps),
    notPersistedOnEarth: take(readRequiredNumber(root, "not_persisted_on_earth", path), gaps),
    persistedOnEarthButUnconfirmed: take(
      readRequiredNumber(root, "persisted_on_earth_but_unconfirmed", path),
      gaps,
    ),
    gapsCount: take(readRequiredNumber(root, "gaps_count", path), gaps),
    completeness: take(readOptionalNumber(root, "completeness", path), gaps),
    confirmationRatio: take(readOptionalNumber(root, "confirmation_ratio", path), gaps),
  };

  const trafficPath = `${path}.traffic`;
  const trafficMetrics: RunTrafficMetrics = {
    syncUnitsCreated: take(readRequiredNumber(root, "sync_units_created", path), gaps),
    telemetrySyncunitBytesCreated: take(
      readRequiredNumber(
        traffic,
        "telemetry_syncunit_bytes_created",
        traffic ? trafficPath : path,
      ),
      gaps,
    ),
    telemetryTransportBytes: take(
      readRequiredNumber(traffic, "telemetry_transport_bytes", traffic ? trafficPath : path),
      gaps,
    ),
    totalTransportApplicationBytes: take(
      readRequiredNumber(
        traffic,
        "total_transport_application_bytes",
        traffic ? trafficPath : path,
      ),
      gaps,
    ),
  };
  if (!traffic) {
    gaps.push(trafficPath);
  }

  const freshnessMetrics: RunFreshnessMetrics = {
    count: readPaired(root, freshness, "count", "freshness_sample_count", path, gaps),
    coverage: take(readOptionalNumber(root, "freshness_coverage", path), gaps),
    p50Seconds: readPaired(root, freshness, "p50_seconds", "freshness_p50_seconds", path, gaps),
    p95Seconds: readPaired(root, freshness, "p95_seconds", "freshness_p95_seconds", path, gaps),
  };

  const convergence: RunConvergenceMetrics = {
    timeToConvergenceSeconds: take(
      readOptionalNumber(root, "time_to_convergence_seconds", path),
      gaps,
    ),
    converged: readBoolean(root, "converged"),
  };

  const contactMetrics: RunContactMetrics = {
    contactUtilizationWeighted: take(
      readOptionalNumber(
        contacts,
        "contact_utilization_weighted",
        contacts ? `${path}.contacts` : path,
      ),
      gaps,
    ),
  };
  if (!contacts) {
    gaps.push(`${path}.contacts`);
  }

  return {
    metrics: {
      state,
      traffic: trafficMetrics,
      freshness: freshnessMetrics,
      convergence,
      contacts: contactMetrics,
    },
    paths: unique(gaps),
  };
}

export function gapsForRun(runLabel: string, paths: readonly string[]): MetricGap[] {
  return paths.map((path) => ({ runLabel, path }));
}

function readPaired(
  root: Record<string, unknown>,
  nested: Record<string, unknown> | null,
  nestedKey: string,
  flatKey: string,
  path: string,
  gaps: string[],
): ScientificValue {
  const nestedPath = `${path}.freshness.${nestedKey}`;
  const flatPath = `${path}.${flatKey}`;
  const fromNested = nested
    ? readOptionalNumber(nested, nestedKey, `${path}.freshness`)
    : ({ status: "missing", path: nestedPath } as const);
  const fromFlat = readOptionalNumber(root, flatKey, path);
  if (
    fromNested.status === "stored" &&
    fromFlat.status === "stored" &&
    fromNested.value !== fromFlat.value
  ) {
    const disagree = `${nestedPath} ≠ ${flatPath}`;
    gaps.push(disagree);
    return { status: "missing", path: disagree };
  }
  if (fromNested.status === "stored") {
    return fromNested;
  }
  if (fromFlat.status === "stored") {
    return fromFlat;
  }
  gaps.push(nestedPath);
  return { status: "missing", path: nestedPath };
}

function readRequiredNumber(
  record: Record<string, unknown> | null,
  key: string,
  path: string,
): ScientificValue {
  const reading = readOptionalNumber(record, key, path);
  if (reading.status === "stored" && reading.value === null) {
    return { status: "missing", path: reading.path };
  }
  return reading;
}

function readOptionalNumber(
  record: Record<string, unknown> | null,
  key: string,
  path: string,
): ScientificValue {
  const full = `${path}.${key}`;
  if (!record || !Object.prototype.hasOwnProperty.call(record, key)) {
    return { status: "missing", path: full };
  }
  const value = record[key];
  if (value === null) {
    return { status: "stored", path: full, value: null };
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return { status: "stored", path: full, value };
  }
  return { status: "missing", path: full };
}

function readBoolean(record: Record<string, unknown>, key: string): boolean | null {
  const value = record[key];
  return typeof value === "boolean" ? value : null;
}

function take(reading: ScientificValue, gaps: string[]): ScientificValue {
  if (reading.status === "missing") {
    gaps.push(reading.path);
  }
  return reading;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function unique(paths: string[]): string[] {
  return [...new Set(paths)];
}

function missing(path: string): ScientificValue {
  return { status: "missing", path };
}

function emptyMetrics(path: string): StoredRunMetrics {
  return {
    state: {
      generated: missing(path),
      earthPersistedUnique: missing(path),
      confirmed: missing(path),
      backlog: missing(path),
      finalBacklog: missing(path),
      notPersistedOnEarth: missing(path),
      persistedOnEarthButUnconfirmed: missing(path),
      gapsCount: missing(path),
      completeness: missing(path),
      confirmationRatio: missing(path),
    },
    traffic: {
      syncUnitsCreated: missing(path),
      telemetrySyncunitBytesCreated: missing(path),
      telemetryTransportBytes: missing(path),
      totalTransportApplicationBytes: missing(path),
    },
    freshness: {
      count: missing(path),
      coverage: missing(path),
      p50Seconds: missing(path),
      p95Seconds: missing(path),
    },
    convergence: {
      timeToConvergenceSeconds: missing(path),
      converged: null,
    },
    contacts: {
      contactUtilizationWeighted: missing(path),
    },
  };
}
