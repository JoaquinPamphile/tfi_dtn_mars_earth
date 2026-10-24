import { useState } from "react";
import { defenseContent } from "../../../defense/content";
import {
  formatCount,
  formatMegabytes,
  formatPercent,
  formatSeconds,
} from "../../../domain/metricFormat";
import {
  isStoredNumber,
  type E1PresentationMetrics,
  type E1TreatmentMetrics,
  type MetricGap,
  type ScientificValue,
} from "../../../domain/metrics";
import { CategoricalBarChart } from "../../charts/CategoricalBarChart";
import { ExperimentFinding } from "../../charts/ExperimentFinding";
import { MetricCallout } from "../../charts/MetricCallout";
import { MetricToggle } from "../../charts/MetricToggle";
import { ValuesTable, type ValueColumn } from "../../charts/ValuesTable";
import type { ChartSeries } from "../../charts/types";
import { axisFromZero } from "../../charts/scale";
import { formatAxisNumber } from "../../../domain/metricFormat";
import {
  ariaStored,
  cellBytes,
  cellCount,
  cellMegabytes,
  cellPercent,
  cellSeconds,
  plotNumber,
  tooltipBytes,
  tooltipCount,
  tooltipSeconds,
} from "./metricReading";
import { EvidenceMissing, LabLink, Slide, SlideTitle, useEvidenceAdapter } from "./slide";
import styles from "./experimentVisual.module.css";

const relato = defenseContent.e1;
type Vista = "costo" | "temporalidad";

const COLUMNS: ValueColumn[] = [
  { key: "label", label: "Tratamiento" },
  { key: "strategy", label: "Estrategia" },
  { key: "batch", label: "Batch" },
  { key: "sync", label: "SyncUnits" },
  { key: "bytes", label: "Bytes" },
  { key: "mb", label: "MB" },
  { key: "p50", label: "Frescura p50" },
  { key: "p95", label: "Frescura p95" },
  { key: "ttc", label: "TTC" },
  { key: "completeness", label: "Persistencia" },
  { key: "confirmation", label: "Confirmación" },
  { key: "backlog", label: "Backlog" },
];

export function E1Step() {
  const adapter = useEvidenceAdapter();
  const presentation = adapter?.getE1Presentation() ?? null;
  const [vista, setVista] = useState<Vista>("costo");
  const [valores, setValores] = useState(false);

  if (!adapter) {
    return (
      <Slide fill>
        <SlideTitle lines={relato.question} />
        <EvidenceMissing />
      </Slide>
    );
  }

  if (!presentation?.ok) {
    return (
      <Slide fill>
        <div className={styles.visual}>
          <SlideTitle lines={relato.question} />
          <p className={styles.gaps} role="status">
            No disponible en evidence
          </p>
          <GapNote gaps={presentation?.gaps ?? []} />
          <LabLink to={relato.labPath}>{relato.labLinkLabel}</LabLink>
        </div>
      </Slide>
    );
  }

  const categories = presentation.treatments.map((item) => ({ id: item.key, label: item.label }));

  return (
    <Slide fill>
      <div className={styles.visual}>
        <header className={styles.head}>
          <SlideTitle lines={relato.question} />
          <MetricToggle
            label="Vista de E1"
            value={vista}
            onChange={setVista}
            options={[
              { id: "costo", label: relato.views.cost },
              { id: "temporalidad", label: relato.views.time },
            ]}
          />
        </header>
        <div className={styles.stage}>
          {valores ? (
            <ValuesTable
              caption="Valores leídos de evidence RC1"
              columns={COLUMNS}
              rows={presentation.treatments.map((item) => ({
                key: item.key,
                cells: {
                  label: { text: item.label },
                  strategy: { text: item.strategyType ?? "—" },
                  batch: { text: item.batchSizeEvents === null ? "—" : String(item.batchSizeEvents) },
                  sync: cellCount(item.syncUnitsCreated),
                  bytes: cellBytes(item.telemetryBytes),
                  mb: cellMegabytes(item.telemetryBytes),
                  p50: cellSeconds(item.freshnessP50Seconds),
                  p95: cellSeconds(item.freshnessP95Seconds),
                  ttc: cellSeconds(item.timeToConvergenceSeconds),
                  completeness: cellPercent(item.completeness),
                  confirmation: cellPercent(item.confirmationRatio),
                  backlog: cellCount(item.finalBacklog),
                },
              }))}
            />
          ) : vista === "costo" ? (
            <CostCharts presentation={presentation} categories={categories} />
          ) : (
            <TimeCharts presentation={presentation} categories={categories} />
          )}
        </div>
        {!valores ? (
          <footer className={styles.foot}>
            {vista === "costo" ? (
              <MetricCallout title={relato.costCallout} note={relato.costNote} />
            ) : (
              <>
                <p className={styles.caution}>{relato.timeCaution}</p>
                <p className={styles.readout}>{p95Readout(presentation.treatments)}</p>
              </>
            )}
            <FinalControls presentation={presentation} />
            <ExperimentFinding title={relato.conclusion} />
            <GapNote gaps={presentation.gaps} />
          </footer>
        ) : (
          <GapNote gaps={presentation.gaps} />
        )}
        <div className={styles.links}>
          <LabLink to={relato.labPath}>{relato.labLinkLabel}</LabLink>
          <button
            type="button"
            className={styles.linkButton}
            aria-pressed={valores}
            onClick={() => setValores((current) => !current)}
          >
            {valores ? relato.chartsLabel : relato.valuesLabel}
          </button>
        </div>
      </div>
    </Slide>
  );
}

function CostCharts({
  presentation,
  categories,
}: {
  presentation: E1PresentationMetrics;
  categories: { id: string; label: string }[];
}) {
  const sync = singleSeries(
    "sync",
    "SyncUnits",
    "circle",
    presentation.treatments,
    (item) => plotNumber(item.syncUnitsCreated),
    (item) => (isStoredNumber(item.syncUnitsCreated) ? formatCount(item.syncUnitsCreated.value) : undefined),
    (item) => tooltipCount(item.label, "SyncUnits", item.syncUnitsCreated),
    (item) =>
      ariaStored(
        item.label,
        "SyncUnits",
        isStoredNumber(item.syncUnitsCreated) ? formatCount(item.syncUnitsCreated.value) : "no disponible",
      ),
  );
  const bytes = singleSeries(
    "bytes",
    "Telemetría",
    "circle",
    presentation.treatments,
    (item) => {
      const stored = plotNumber(item.telemetryBytes);
      return stored === null ? null : stored / 1_000_000;
    },
    (item) => (isStoredNumber(item.telemetryBytes) ? formatMegabytes(item.telemetryBytes.value) : undefined),
    (item) => tooltipBytes(item.label, item.telemetryBytes),
    (item) =>
      ariaStored(
        item.label,
        "Telemetría",
        isStoredNumber(item.telemetryBytes)
          ? `${formatCount(item.telemetryBytes.value)} B, ${formatMegabytes(item.telemetryBytes.value)}`
          : "no disponible",
      ),
  );
  return (
    <div className={styles.pair}>
      <CategoricalBarChart
        title="SyncUnits creadas"
        summary={summaryOf("SyncUnits creadas", [sync])}
        yLabel="SyncUnits"
        categories={categories}
        series={[sync]}
        formatTick={formatAxisNumber}
      />
      <CategoricalBarChart
        title="Bytes de telemetría creados"
        summary={summaryOf("Bytes de telemetría creados, en MB decimales", [bytes])}
        yLabel="MB"
        categories={categories}
        series={[bytes]}
        formatTick={formatAxisNumber}
      />
    </div>
  );
}

function TimeCharts({
  presentation,
  categories,
}: {
  presentation: E1PresentationMetrics;
  categories: { id: string; label: string }[];
}) {
  const freshness = [
    seriesFrom(
      "p50",
      "Frescura p50",
      "circle",
      presentation.treatments,
      (item) => plotNumber(item.freshnessP50Seconds),
      (item) => tooltipSeconds(item.label, "Frescura p50", item.freshnessP50Seconds),
      (item) => secondsAria(item.label, "Frescura p50", item.freshnessP50Seconds),
    ),
    seriesFrom(
      "p95",
      "Frescura p95",
      "square",
      presentation.treatments,
      (item) => plotNumber(item.freshnessP95Seconds),
      (item) => tooltipSeconds(item.label, "Frescura p95", item.freshnessP95Seconds),
      (item) => secondsAria(item.label, "Frescura p95", item.freshnessP95Seconds),
    ),
  ];
  const ttc = singleSeries(
    "ttc",
    "TTC",
    "diamond",
    presentation.treatments,
    (item) => plotNumber(item.timeToConvergenceSeconds),
    (item) =>
      isStoredNumber(item.timeToConvergenceSeconds)
        ? formatSeconds(item.timeToConvergenceSeconds.value)
        : undefined,
    (item) => tooltipSeconds(item.label, "Tiempo hasta la convergencia", item.timeToConvergenceSeconds),
    (item) => secondsAria(item.label, "Tiempo hasta la convergencia", item.timeToConvergenceSeconds),
  );
  const shared = axisFromZero(
    freshness.flatMap((item) => item.data.flatMap((datum) => (datum.plot === null ? [] : [datum.plot]))),
  );
  return (
    <div className={styles.pair}>
      <CategoricalBarChart
        title="Frescura p50 y p95"
        summary={summaryOf("Frescura p50 y p95, en segundos", freshness)}
        yLabel="s"
        categories={categories}
        series={freshness}
        formatTick={formatAxisNumber}
        domainMax={shared.max}
        ticks={shared.ticks}
      />
      <CategoricalBarChart
        title="Tiempo hasta la convergencia"
        summary={summaryOf("Tiempo hasta la convergencia, en segundos", [ttc])}
        yLabel="s"
        categories={categories}
        series={[ttc]}
        formatTick={formatAxisNumber}
      />
    </div>
  );
}

function FinalControls({ presentation }: { presentation: E1PresentationMetrics }) {
  const finalState = presentation.finalState;
  if (!finalState) {
    return null;
  }
  return (
    <ul className={styles.controls}>
      <li>
        {relato.controls.earth}: <strong>{formatPercent(finalState.completeness)}</strong>
      </li>
      <li>
        {relato.controls.mars}: <strong>{formatPercent(finalState.confirmationRatio)}</strong>
      </li>
      <li>
        {relato.controls.backlog}: <strong>{formatCount(finalState.finalBacklog)}</strong>
      </li>
    </ul>
  );
}

function GapNote({ gaps }: { gaps: readonly MetricGap[] }) {
  if (gaps.length === 0) {
    return null;
  }
  return (
    <p className={styles.gaps} role="status">
      No disponible en evidence: {gaps.map((gap) => `${gap.runLabel} (${gap.path})`).join("; ")}
    </p>
  );
}

function p95Readout(treatments: readonly E1TreatmentMetrics[]): string {
  const parts = treatments.map((item) => {
    const text = isStoredNumber(item.freshnessP95Seconds)
      ? formatSeconds(item.freshnessP95Seconds.value)
      : "no disponible";
    return `${item.label} ${text}`;
  });
  return `p95: ${parts.join(" · ")}`;
}

function secondsAria(label: string, metric: string, value: ScientificValue): string {
  if (value.status === "stored" && value.value === null) {
    return `${label}. ${metric}: valor almacenado null.`;
  }
  if (!isStoredNumber(value)) {
    return `${label}. ${metric}: no disponible en evidence.`;
  }
  return ariaStored(label, metric, `${formatSeconds(value.value)}. Valor almacenado ${value.value} s`);
}

function singleSeries(
  id: string,
  label: string,
  symbol: ChartSeries["symbol"],
  treatments: readonly E1TreatmentMetrics[],
  plot: (item: E1TreatmentMetrics) => number | null,
  valueLabel: (item: E1TreatmentMetrics) => string | undefined,
  tooltip: (item: E1TreatmentMetrics) => ChartSeries["data"][number]["tooltip"],
  ariaLabel: (item: E1TreatmentMetrics) => string,
): ChartSeries {
  return seriesFrom(id, label, symbol, treatments, plot, tooltip, ariaLabel, valueLabel);
}

function seriesFrom(
  id: string,
  label: string,
  symbol: ChartSeries["symbol"],
  treatments: readonly E1TreatmentMetrics[],
  plot: (item: E1TreatmentMetrics) => number | null,
  tooltip: (item: E1TreatmentMetrics) => ChartSeries["data"][number]["tooltip"],
  ariaLabel: (item: E1TreatmentMetrics) => string,
  valueLabel?: (item: E1TreatmentMetrics) => string | undefined,
): ChartSeries {
  return {
    id,
    label,
    symbol,
    data: treatments.map((item) => ({
      categoryId: item.key,
      plot: plot(item),
      tooltip: tooltip(item),
      ariaLabel: ariaLabel(item),
      valueLabel: valueLabel?.(item),
    })),
  };
}

function summaryOf(title: string, series: readonly ChartSeries[]): string {
  const parts = series.flatMap((item) => item.data.map((datum) => datum.ariaLabel));
  return `${title}. ${parts.join(" ")}`;
}
