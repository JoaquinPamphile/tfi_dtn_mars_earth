import {
  formatBytes,
  formatCount,
  formatMegabytes,
  formatOriginalNumber,
  formatPercent,
  formatRawNumber,
  formatSeconds,
  formatSecondsDetail,
} from "../../../domain/metricFormat";
import { isStoredNumber, type ScientificValue } from "../../../domain/metrics";
import type { ValueCell } from "../../charts/ValuesTable";
import type { TooltipModel } from "../../charts/types";

const MISSING = "No disponible";

export function plotNumber(value: ScientificValue): number | null {
  return isStoredNumber(value) ? value.value : null;
}

export function cellCount(value: ScientificValue): ValueCell {
  return numberCell(value, formatCount);
}

export function cellBytes(value: ScientificValue): ValueCell {
  if (!isStoredNumber(value)) {
    return emptyCell(value);
  }
  return { text: formatBytes(value.value), title: `${formatRawNumber(value.value)} B` };
}

export function cellMegabytes(value: ScientificValue): ValueCell {
  if (!isStoredNumber(value)) {
    return emptyCell(value);
  }
  return { text: formatMegabytes(value.value), title: `${formatRawNumber(value.value)} B` };
}

export function cellPercent(value: ScientificValue): ValueCell {
  if (!isStoredNumber(value)) {
    return emptyCell(value);
  }
  return {
    text: formatPercent(value.value, 2),
    title: formatOriginalNumber(value.value),
  };
}

export function cellSeconds(value: ScientificValue): ValueCell {
  if (value.status === "missing") {
    return { text: MISSING, title: value.path };
  }
  if (value.value === null) {
    return { text: "—", title: "valor almacenado: null" };
  }
  return {
    text: formatSecondsDetail(value.value),
    title: `${formatRawNumber(value.value)} s`,
  };
}

export function tooltipCount(title: string, metric: string, value: ScientificValue): TooltipModel {
  if (!isStoredNumber(value)) {
    return { title, rows: [{ label: metric, values: [emptyCell(value).text] }] };
  }
  return { title, rows: [{ label: metric, values: [formatCount(value.value)] }] };
}

export function tooltipBytes(title: string, value: ScientificValue): TooltipModel {
  if (!isStoredNumber(value)) {
    return { title, rows: [{ label: "Telemetría", values: [emptyCell(value).text] }] };
  }
  return {
    title,
    rows: [
      {
        label: "Telemetría",
        values: [formatBytes(value.value), formatMegabytes(value.value)],
      },
    ],
  };
}

export function tooltipSeconds(title: string, metric: string, value: ScientificValue): TooltipModel {
  if (value.status === "missing") {
    return { title, rows: [{ label: metric, values: [MISSING] }] };
  }
  if (value.value === null) {
    return { title, rows: [{ label: metric, values: ["valor almacenado: null"] }] };
  }
  return {
    title,
    rows: [
      {
        label: metric,
        values: [formatSeconds(value.value), `${formatRawNumber(value.value)} s`],
      },
    ],
  };
}

export function tooltipRatio(title: string, metric: string, value: ScientificValue): TooltipModel {
  if (!isStoredNumber(value)) {
    return { title, rows: [{ label: metric, values: [emptyCell(value).text] }] };
  }
  return {
    title,
    rows: [
      {
        label: metric,
        values: [formatOriginalNumber(value.value), formatPercent(value.value)],
      },
    ],
  };
}

export function ariaStored(label: string, metric: string, text: string): string {
  return `${label}. ${metric}: ${text}.`;
}

function numberCell(value: ScientificValue, format: (value: number) => string): ValueCell {
  if (!isStoredNumber(value)) {
    return emptyCell(value);
  }
  return { text: format(value.value), title: formatRawNumber(value.value) };
}

function emptyCell(value: ScientificValue): ValueCell {
  if (value.status === "missing") {
    return { text: MISSING, title: value.path };
  }
  return { text: "—", title: "valor almacenado: null" };
}
