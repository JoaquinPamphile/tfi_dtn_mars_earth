import { axisFromZero, yAt } from "./scale";
import { seriesStroke } from "./ChartSymbol";
import { categoryCenter, categorySlot, ChartFrame, seriesFill } from "./ChartFrame";
import { ChartUnavailable, ScientificChart } from "./ScientificChart";
import type { ChartCategory, ChartSeries } from "./types";
import { chartPlot, useChartInteraction } from "./useChartInteraction";
import { usePlotSize } from "./usePlotSize";
import styles from "./charts.module.css";

function activate(
  handler: (id: string, element: Element, plot: HTMLElement) => void,
  id: string,
  element: SVGElement,
) {
  const plot = chartPlot(element);
  if (plot) {
    handler(id, element, plot);
  }
}

export function CategoricalBarChart({
  title,
  summary,
  yLabel,
  categories,
  series,
  formatTick,
  domainMax,
  ticks,
}: {
  title: string;
  summary: string;
  yLabel: string;
  categories: readonly ChartCategory[];
  series: readonly ChartSeries[];
  formatTick: (value: number) => string;
  domainMax?: number;
  ticks?: readonly number[];
}) {
  const { ref, width, height } = usePlotSize<HTMLDivElement>();
  const interaction = useChartInteraction(series);
  const plots = series.flatMap((item) =>
    item.data.flatMap((datum) => (datum.plot === null ? [] : [datum.plot])),
  );
  if (plots.length === 0) {
    return <ChartUnavailable title={title} summary={summary} />;
  }
  const auto = axisFromZero(plots);
  const max = domainMax ?? auto.max;
  const axisTicks = ticks ?? auto.ticks;

  return (
    <ScientificChart
      title={title}
      summary={summary}
      series={series}
      categories={categories}
      marker="bar"
      activeSeries={interaction.seriesId}
      onActiveSeries={interaction.setSeriesId}
      tooltip={interaction.tooltip}
      anchor={interaction.anchor}
      plotRef={ref}
    >
      {width > 0 && height > 0 ? (
        <ChartFrame
          width={width}
          height={height}
          yLabel={yLabel}
          domainMax={max}
          ticks={axisTicks}
          formatTick={formatTick}
          categories={categories}
        >
          {(geo) =>
            categories.map((category, index) => {
              const center = categoryCenter(index, categories.length, geo);
              const slot = categorySlot(categories.length, geo);
              const groupWidth = slot * (series.length === 1 ? 0.56 : 0.8);
              const barWidth = groupWidth / series.length;
              const groupLeft = center - groupWidth / 2;
              return (
                <g key={category.id}>
                  {series.map((item, seriesIndex) => {
                const datum = item.data.find((entry) => entry.categoryId === category.id);
                if (!datum || datum.plot === null) {
                  return null;
                }
                const y = yAt(datum.plot, geo.domainMax, geo.plotY, geo.plotH);
                const baseline = yAt(0, geo.domainMax, geo.plotY, geo.plotH);
                const barHeight = Math.max(datum.plot > 0 ? 1 : 0, baseline - y);
                const markId = `${item.id}:${datum.categoryId}`;
                const dim = interaction.seriesId !== null && interaction.seriesId !== item.id;
                return (
                  <g
                    key={markId}
                    className={styles.mark}
                    tabIndex={0}
                    role="button"
                    aria-label={datum.ariaLabel}
                    data-active={interaction.markId === markId ? "true" : "false"}
                    opacity={dim ? 0.35 : 1}
                    onMouseEnter={(event) => activate(interaction.show, markId, event.currentTarget)}
                    onMouseLeave={() => interaction.hide()}
                    onFocus={(event) => activate(interaction.show, markId, event.currentTarget)}
                    onBlur={() => interaction.hide()}
                    onClick={(event) => activate(interaction.pin, markId, event.currentTarget)}
                  >
                    <rect
                      x={groupLeft + seriesIndex * barWidth + 1.5}
                      y={y}
                      width={Math.max(2, barWidth - 3)}
                      height={barHeight}
                      fill={seriesFill(seriesIndex, geo.uid)}
                      stroke={seriesStroke(seriesIndex)}
                      strokeWidth={interaction.markId === markId ? 2.4 : 1.25}
                    />
                    {series.length === 1 && datum.valueLabel && y > 18 ? (
                      <text
                        x={center}
                        y={y - 6}
                        textAnchor="middle"
                        fill="var(--color-text)"
                        fontSize="13"
                        fontFamily="var(--font)"
                      >
                        {datum.valueLabel}
                      </text>
                    ) : null}
                  </g>
                );
                  })}
                </g>
              );
            })
          }
        </ChartFrame>
      ) : null}
    </ScientificChart>
  );
}
