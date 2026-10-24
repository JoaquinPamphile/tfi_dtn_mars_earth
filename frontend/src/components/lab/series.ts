import {
  formatAxisNumber,
  formatBytes,
  formatCount,
  formatMegabytes,
  formatPercent,
  formatSecondsDetail,
} from "../../domain/metricFormat";
import { loadLabel, metricDef, presentStored, storedNumber, type LabRun } from "../../domain/lab";
import type { ChartCategory, ChartSeries, ChartSymbol } from "../charts/types";

export function categoriesOf(
  runs: readonly LabRun[],
  label: (run: LabRun) => string,
): ChartCategory[] {
  return runs.map((run) => ({ id: run.uiReference, label: label(run) }));
}

export function seriesFor(
  runs: readonly LabRun[],
  metricId: string,
  symbol: ChartSymbol,
  transform: (value: number) => number,
  display: (value: number) => string,
  titleOf: (run: LabRun) => string = (run) => run.label,
): ChartSeries {
  const def = metricDef(metricId);
  return {
    id: metricId,
    label: def.name,
    symbol,
    data: runs.map((run) => {
      const stored = storedNumber(run, metricId);
      const shown = presentStored(def, run.metrics[metricId]);
      const title = titleOf(run);
      return {
        categoryId: run.uiReference,
        plot: stored === null ? null : transform(stored),
        valueLabel: stored === null ? undefined : display(stored),
        tooltip: {
          title,
          rows: [{ label: def.name, values: uniqueTexts(shown.text, shown.title) }],
        },
        ariaLabel: `${title}. ${def.name}: ${shown.text}. Valor almacenado ${shown.title}.`,
      };
    }),
  };
}

function uniqueTexts(text: string, raw: string): string[] {
  if (text === raw || raw.length === 0) {
    return [text];
  }
  return [text, raw];
}

export function loadCategories(runs: readonly LabRun[]): ChartCategory[] {
  const seen = new Set<string>();
  const categories: ChartCategory[] = [];
  for (const run of runs) {
    const id = String(run.config.offeredLoadFraction);
    if (seen.has(id)) {
      continue;
    }
    seen.add(id);
    categories.push({ id, label: loadLabel(run.config.offeredLoadFraction) });
  }
  return categories;
}

export function seriesOnLoads(
  runs: readonly LabRun[],
  metricId: string,
  seriesId: string,
  seriesLabel: string,
  symbol: ChartSymbol,
  transform: (value: number) => number,
  display: (value: number) => string,
): ChartSeries {
  const def = metricDef(metricId);
  const categories = loadCategories(runs);
  return {
    id: seriesId,
    label: seriesLabel,
    symbol,
    data: categories.map((category) => {
      const run = runs.find((item) => String(item.config.offeredLoadFraction) === category.id);
      if (!run) {
        return {
          categoryId: category.id,
          plot: null,
          tooltip: { title: category.label, rows: [{ label: seriesLabel, values: ["No disponible"] }] },
          ariaLabel: `${category.label}. ${seriesLabel}: no disponible.`,
        };
      }
      const stored = storedNumber(run, metricId);
      const shown = presentStored(def, run.metrics[metricId]);
      return {
        categoryId: category.id,
        plot: stored === null ? null : transform(stored),
        valueLabel: stored === null ? undefined : display(stored),
        tooltip: { title: run.label, rows: [{ label: def.name, values: [shown.text, shown.title] }] },
        ariaLabel: `${run.label}. ${def.name}: ${shown.text}.`,
      };
    }),
  };
}

export function tickCount(value: number): string {
  return formatAxisNumber(value);
}

export function tickMb(value: number): string {
  return formatAxisNumber(value);
}

export function tickPercent(value: number): string {
  return formatAxisNumber(value);
}

export function tickSeconds(value: number): string {
  return formatAxisNumber(value);
}

export const asCount = (value: number) => value;
export const asMegabytes = (value: number) => value / 1_000_000;
export const asPercent = (value: number) => value * 100;
export const showCount = (value: number) => formatCount(value);
export const showMb = (value: number) => formatMegabytes(value);
export const showPercent = (value: number) => formatPercent(value, 2);
export const showSeconds = (value: number) => formatSecondsDetail(value);
export const showBytes = (value: number) => formatBytes(value);
