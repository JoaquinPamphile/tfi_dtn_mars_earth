/** Escala lineal que arranca en cero. No recorta el eje para agrandar una diferencia. */

export interface AxisScale {
  max: number;
  ticks: number[];
}

export function axisFromZero(values: readonly number[]): AxisScale {
  const peak = values.reduce((max, value) => (value > max ? value : max), 0);
  if (peak <= 0) {
    return { max: 1, ticks: [0, 1] };
  }
  const padded = peak * 1.14;
  const step = niceStep(padded / 5);
  const max = Math.ceil((padded - step * 1e-9) / step) * step;
  const intervals = Math.max(1, Math.round(max / step));
  const ticks = Array.from({ length: intervals + 1 }, (_, index) => roundToStep(index * step, step));
  return { max: ticks[ticks.length - 1] ?? max, ticks };
}

export function yAt(value: number, domainMax: number, plotY: number, plotH: number): number {
  const span = domainMax <= 0 ? 1 : domainMax;
  const ratio = Math.min(Math.max(value, 0), span) / span;
  return plotY + plotH - ratio * plotH;
}

function niceStep(rough: number): number {
  if (!Number.isFinite(rough) || rough <= 0) {
    return 1;
  }
  const exponent = Math.floor(Math.log10(rough));
  const base = 10 ** exponent;
  const fraction = rough / base;
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10;
  return nice * base;
}

function roundToStep(value: number, step: number): number {
  const digits = Math.max(0, -Math.floor(Math.log10(step)));
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}
