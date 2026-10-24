import { useState } from "react";
import { defenseContent } from "../../../defense/content";
import {
  formatAxisNumber,
  formatCount,
  formatOriginalNumber,
  formatPercent,
} from "../../../domain/metricFormat";
import {
  isStoredNumber,
  type E2PointMetrics,
  type E2PresentationMetrics,
  type E2StrategyPanel,
  type MetricGap,
  type ScientificValue,
} from "../../../domain/metrics";
import { CategoricalBarChart } from "../../charts/CategoricalBarChart";
import { ExperimentFinding } from "../../charts/ExperimentFinding";
import { MetricToggle } from "../../charts/MetricToggle";
import { ObservedPointChart } from "../../charts/ObservedPointChart";
import { axisFromZero } from "../../charts/scale";
import type { ChartCategory, ChartSeries, TooltipModel } from "../../charts/types";
import { ValuesTable, type ValueColumn } from "../../charts/ValuesTable";
import {
  ariaStored,
  cellCount,
  cellPercent,
  cellSeconds,
  plotNumber,
  tooltipCount,
  tooltipRatio,
} from "./metricReading";
import { EvidenceMissing, LabLink, Slide, SlideTitle, useEvidenceAdapter } from "./slide";
import styles from "./experimentVisual.module.css";

const relato = defenseContent.e2;
type Vista = "estados" | "composicion";

const PERCENT_TICKS = [0, 25, 50, 75, 100];

const COLUMNS: ValueColumn[] = [
  { key: "load", label: "Carga ofrecida" },
  { key: "strategy", label: "Estrategia" },
  { key: "generated", label: "Generados" },
  { key: "persisted", label: "Persistidos" },
  { key: "confirmed", label: "Confirmados" },
  { key: "completeness", label: "Persistencia" },
  { key: "confirmation", label: "Confirmación" },
  { key: "backlog", label: "Backlog" },
  { key: "missing", label: "No persistidos (M)" },
  { key: "unconfirmed", label: "Persistidos sin confirmar (U)" },
  { key: "coverage", label: "Cobertura de frescura" },
  { key: "ttc", label: "TTC" },
  { key: "utilization", label: "Utilización de contacto" },
];

export function E2Step() {
  const adapter = useEvidenceAdapter();
  const presentation = adapter?.getE2Presentation() ?? null;
  const [vista, setVista] = useState<Vista>("estados");
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

  const categories = presentation.loads.map((load) => ({
    id: String(load.fraction),
    label: load.label,
  }));

  return (
    <Slide fill>
      <div className={styles.visual}>
        <header className={styles.head}>
          <div>
            <SlideTitle lines={relato.question} />
            <p className={styles.axisLabel}>{relato.axisLabel}</p>
          </div>
          <MetricToggle
            label="Vista de E2"
            value={vista}
            onChange={setVista}
            options={[
              { id: "estados", label: relato.views.states },
              { id: "composicion", label: relato.views.composition },
            ]}
          />
        </header>
        <div className={styles.stage}>
          {valores ? (
            <ValuesTable
              caption="Valores leídos de evidence RC1. La utilización de contacto no es la carga ofrecida."
              columns={COLUMNS}
              rows={tableRows(presentation)}
            />
          ) : vista === "estados" ? (
            <StateCharts presentation={presentation} categories={categories} />
          ) : (
            <CompositionCharts presentation={presentation} categories={categories} />
          )}
        </div>
        {!valores ? (
          <footer className={styles.foot}>
            <p className={styles.readout}>{observedLevelsNote(presentation.levelCount)}</p>
            {vista === "estados" && presentation.pattern.length > 0 ? (
              <ul className={styles.pattern}>
                {presentation.pattern.map((item) => (
                  <li key={item.rangeLabel} className={styles.patternItem}>
                    <span className={styles.patternRange}>{item.rangeLabel}</span>
                    <span>{item.earth}</span>
                    <span>{item.origin}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            <ExperimentFinding title={relato.conclusion} note={relato.conclusionNote} />
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

function StateCharts({
  presentation,
  categories,
}: {
  presentation: E2PresentationMetrics;
  categories: ChartCategory[];
}) {
  return (
    <div className={styles.pair}>
      {presentation.panels.map((panel) => (
        <ObservedPointChart
          key={panel.key}
          title={panel.label}
          summary={panelSummary(panel, "persistencia y confirmación")}
          yLabel="%"
          categories={categories}
          series={stateSeries(panel, categories)}
          formatTick={formatAxisNumber}
          domainMax={100}
          ticks={PERCENT_TICKS}
        />
      ))}
    </div>
  );
}

function CompositionCharts({
  presentation,
  categories,
}: {
  presentation: E2PresentationMetrics;
  categories: ChartCategory[];
}) {
  const plots = presentation.panels.flatMap((panel) =>
    panel.points.flatMap((point) =>
      [point.generated, point.earthPersistedUnique, point.confirmed].flatMap((value) => {
        const plot = plotNumber(value);
        return plot === null ? [] : [plot];
      }),
    ),
  );
  const axis = axisFromZero(plots);
  return (
    <div className={styles.pair}>
      {presentation.panels.map((panel) => (
        <CategoricalBarChart
          key={panel.key}
          title={panel.label}
          summary={panelSummary(panel, "generados, persistidos y confirmados")}
          yLabel="eventos"
          categories={categories}
          series={compositionSeries(panel, categories)}
          formatTick={formatAxisNumber}
          domainMax={axis.max}
          ticks={axis.ticks}
        />
      ))}
    </div>
  );
}

function stateSeries(panel: E2StrategyPanel, categories: readonly ChartCategory[]): ChartSeries[] {
  const tooltipFor = (point: E2PointMetrics): TooltipModel => ({
    title: `${point.strategyLabel} · ${point.loadLabel}`,
    rows: [
      ratioRow(relato.series.earth, point.completeness),
      ratioRow(relato.series.origin, point.confirmationRatio),
    ],
  });
  return [
    ratioSeries(
      panel,
      categories,
      "earth",
      relato.series.earth,
      "circle",
      (point) => point.completeness,
      tooltipFor,
    ),
    ratioSeries(
      panel,
      categories,
      "origin",
      relato.series.origin,
      "square",
      (point) => point.confirmationRatio,
      tooltipFor,
    ),
  ];
}

function compositionSeries(panel: E2StrategyPanel, categories: readonly ChartCategory[]): ChartSeries[] {
  return [
    countSeries(panel, categories, "generated", relato.series.generated, "circle", (point) => point.generated),
    countSeries(
      panel,
      categories,
      "persisted",
      relato.series.persisted,
      "square",
      (point) => point.earthPersistedUnique,
    ),
    countSeries(
      panel,
      categories,
      "confirmed",
      relato.series.confirmed,
      "diamond",
      (point) => point.confirmed,
    ),
  ];
}

function ratioSeries(
  panel: E2StrategyPanel,
  categories: readonly ChartCategory[],
  id: string,
  label: string,
  symbol: ChartSeries["symbol"],
  pick: (point: E2PointMetrics) => ScientificValue,
  tooltipFor?: (point: E2PointMetrics) => TooltipModel,
): ChartSeries {
  return {
    id,
    label,
    symbol,
    data: categories.map((category) => {
      const point = findPoint(panel, category.id);
      const value = point ? pick(point) : null;
      const title = point ? `${point.strategyLabel} · ${point.loadLabel}` : panel.label;
      const plot = value ? percentPlot(value) : null;
      return {
        categoryId: category.id,
        plot,
        tooltip:
          point && tooltipFor
            ? tooltipFor(point)
            : value
              ? tooltipRatio(title, label, value)
              : { title, rows: [{ label, values: ["No disponible"] }] },
        ariaLabel: ratioAria(title, label, value),
      };
    }),
  };
}

function countSeries(
  panel: E2StrategyPanel,
  categories: readonly ChartCategory[],
  id: string,
  label: string,
  symbol: ChartSeries["symbol"],
  pick: (point: E2PointMetrics) => ScientificValue,
): ChartSeries {
  return {
    id,
    label,
    symbol,
    data: categories.map((category) => {
      const point = findPoint(panel, category.id);
      const value = point ? pick(point) : null;
      const title = point ? `${point.strategyLabel} · ${point.loadLabel}` : panel.label;
      return {
        categoryId: category.id,
        plot: value ? plotNumber(value) : null,
        tooltip: value
          ? tooltipCount(title, label, value)
          : { title, rows: [{ label, values: ["No disponible"] }] },
        ariaLabel:
          value && isStoredNumber(value)
            ? ariaStored(title, label, formatCount(value.value))
            : `${title}. ${label}: no disponible en evidence.`,
      };
    }),
  };
}

function findPoint(panel: E2StrategyPanel, categoryId: string): E2PointMetrics | undefined {
  return panel.points.find((point) => String(point.loadFraction) === categoryId);
}

function ratioRow(label: string, value: ScientificValue): TooltipModel["rows"][number] {
  if (!isStoredNumber(value)) {
    return { label, values: [value.status === "missing" ? "No disponible" : "—"] };
  }
  return {
    label,
    values: [formatOriginalNumber(value.value), formatPercent(value.value)],
  };
}

function percentPlot(value: ScientificValue): number | null {
  const stored = plotNumber(value);
  return stored === null ? null : stored * 100;
}

function ratioAria(title: string, metric: string, value: ScientificValue | null): string {
  if (!value || !isStoredNumber(value)) {
    return `${title}. ${metric}: no disponible en evidence.`;
  }
  return ariaStored(title, metric, `${formatPercent(value.value)}. Razón almacenada ${value.value}`);
}

function tableRows(presentation: E2PresentationMetrics) {
  const rows: { key: string; cells: Record<string, { text: string; title?: string }> }[] = [];
  for (const load of presentation.loads) {
    for (const panel of presentation.panels) {
      const point = panel.points.find((item) => item.loadFraction === load.fraction);
      if (!point) {
        continue;
      }
      rows.push({
        key: `${panel.key}-${load.fraction}`,
        cells: {
          load: { text: point.loadLabel },
          strategy: { text: point.strategyLabel, title: point.runLabel },
          generated: cellCount(point.generated),
          persisted: cellCount(point.earthPersistedUnique),
          confirmed: cellCount(point.confirmed),
          completeness: cellPercent(point.completeness),
          confirmation: cellPercent(point.confirmationRatio),
          backlog: cellCount(point.finalBacklog),
          missing: cellCount(point.notPersistedOnEarth),
          unconfirmed: cellCount(point.persistedOnEarthButUnconfirmed),
          coverage: cellPercent(point.freshnessCoverage),
          ttc: cellSeconds(point.timeToConvergenceSeconds),
          utilization: cellPercent(point.contactUtilizationWeighted),
        },
      });
    }
  }
  return rows;
}

function panelSummary(panel: E2StrategyPanel, metric: string): string {
  const loads = panel.points.map((point) => point.loadLabel).join(", ");
  return `${panel.label}. ${metric}. Cargas ofrecidas: ${loads}.`;
}

function observedLevelsNote(count: number): string {
  const cantidad = count === 6 ? "seis" : String(count);
  const niveles = count === 1 ? "nivel observado" : "niveles observados";
  return `Se muestran ${cantidad} ${niveles}; no se estima un umbral continuo.`;
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
