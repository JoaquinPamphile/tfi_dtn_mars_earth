const LOCALE = "es-AR";

/** Segundos de simulación, con agrupación es-AR. 86400 → «86.400 s». */
export function formatSimSeconds(value: number): string {
  const text = value.toLocaleString(LOCALE, { maximumFractionDigits: 3 });
  return `${text} s`;
}

/** Tasa en bps, Mbps o kbps decimales, como está definida la línea base. */
export function formatDataRate(bps: number): string {
  if (bps >= 1_000_000 && bps % 1_000_000 === 0) {
    return `${bps / 1_000_000} Mbps`;
  }
  if (bps >= 1_000 && bps % 1_000 === 0) {
    return `${bps / 1_000} kbps`;
  }
  return `${bps.toLocaleString(LOCALE)} bps`;
}
