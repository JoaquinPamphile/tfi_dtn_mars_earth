/** Abrevia un hash o UUID largo: abcd1234…ef567890 */
export function abbreviateHash(value: string): string {
  if (value.length <= 20) {
    return value;
  }
  return `${value.slice(0, 8)}…${value.slice(-8)}`;
}

export function formatBatch(value: number | null): string {
  return value === null ? "—" : String(value);
}

export function formatLoad(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatSequences(values: number[] | null): string {
  if (!values || values.length === 0) {
    return "—";
  }
  return values.join(", ");
}

export function formatFailure(enabled: boolean | null): string {
  if (enabled === null) {
    return "—";
  }
  return enabled ? "sí" : "no";
}

export function formatOptional(value: string | number | null): string {
  if (value === null || value === "") {
    return "—";
  }
  return String(value);
}
