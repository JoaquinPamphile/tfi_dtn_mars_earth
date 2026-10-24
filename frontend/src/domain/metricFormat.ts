/**
 * Transformaciones de presentación.
 * No reemplazan el número almacenado: el valor científico sigue en ScientificValue.
 */

const LOCALE = "es-AR";

/** 1 MB decimal = 1 000 000 B. No es mebibyte. */
export const DECIMAL_MEGABYTE = 1_000_000;

export function decimalMegabytes(bytes: number): number {
  return bytes / DECIMAL_MEGABYTE;
}

export function formatCount(value: number): string {
  return Math.round(value).toLocaleString(LOCALE, { maximumFractionDigits: 0 });
}

/** Número almacenado, con agrupación es-AR y sin redondeo agresivo. */
export function formatOriginalNumber(value: number): string {
  if (Number.isInteger(value)) {
    return formatCount(value);
  }
  return value.toLocaleString(LOCALE, { maximumFractionDigits: 12 });
}

/** Texto del JSON numérico, para el detalle. No afirma más precisión física. */
export function formatRawNumber(value: number): string {
  return String(value);
}

export function formatBytes(bytes: number): string {
  return `${formatCount(bytes)} B`;
}

export function formatMegabytes(bytes: number): string {
  const text = decimalMegabytes(bytes).toLocaleString(LOCALE, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${text} MB`;
}

export function formatPercent(ratio: number, digits = 1): string {
  const factor = 10 ** digits;
  const rounded = Math.round(ratio * 100 * factor) / factor;
  const text = Number.isInteger(rounded)
    ? rounded.toLocaleString(LOCALE, { maximumFractionDigits: 0 })
    : rounded.toLocaleString(LOCALE, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
  return `${text} %`;
}

export function formatSeconds(value: number): string {
  const text = value.toLocaleString(LOCALE, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return `${text} s`;
}

export function formatSecondsDetail(value: number): string {
  const text = value.toLocaleString(LOCALE, { maximumFractionDigits: 3 });
  return `${text} s`;
}

export function formatOfferedLoad(fraction: number): string {
  const percent = Math.round(fraction * 1000) / 10;
  const text = Number.isInteger(percent)
    ? percent.toLocaleString(LOCALE, { maximumFractionDigits: 0 })
    : percent.toLocaleString(LOCALE, {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      });
  return `${text} %`;
}

export function formatAxisNumber(value: number): string {
  if (Number.isInteger(value)) {
    return formatCount(value);
  }
  return value.toLocaleString(LOCALE, { maximumFractionDigits: 2 });
}
