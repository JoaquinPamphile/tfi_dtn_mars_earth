import { axisFromZero, yAt } from "./scale";
import { ChartSymbol, seriesDash, seriesStroke } from "./ChartSymbol";
import { categoryCenter, ChartFrame } from "./ChartFrame";
import { ChartUnavailable, ScientificChart } from "./ScientificChart";
import type { ChartCategory, ChartDatum, ChartGeometry, ChartSeries } from "./types";
import { chartPlot, useChartInteraction } from "./useChartInteraction";
import { usePlotSize } from "./usePlotSize";
import styles from "./charts.module.css";

/**
 * Puntos observados unidos por tramos rectos.
 * No suaviza, no rellena área y no inserta valores entre mediciones.
 */
export function ObservedPointChart({
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
      marker="point"
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
            series.map((item, seriesIndex) => {
              const dim = interaction.seriesId !== null && interaction.seriesId !== item.id;
              const stroke = seriesStroke(seriesIndex);
              return (
                <g key={item.id} opacity={dim ? 0.35 : 1}>
                  {segments(item, categories, geo).map((segment) => (
                    <polyline
                      key={segment.key}
                      points={segment.points}
                      fill="none"
                      stroke={stroke}
                      strokeWidth="2"
                      strokeDasharray={seriesDash(seriesIndex)}
                      strokeLinejoin="miter"
                      strokeLinecap="butt"
                    />
                  ))}
                  {categories.map((category, index) => {
                    const datum = item.data.find((entry) => entry.categoryId === category.id);
                    if (!datum || datum.plot === null) {
                      return null;
                    }
                    const cx = categoryCenter(index, categories.length, geo);
                    const cy = yAt(datum.plot, geo.domainMax, geo.plotY, geo.plotH);
                    const markId = `${item.id}:${datum.categoryId}`;
                    return (
                      <g
                        key={markId}
                        className={styles.mark}
                        tabIndex={0}
                        role="button"
                        aria-label={datum.ariaLabel}
                        data-active={interaction.markId === markId ? "true" : "false"}
                        onMouseEnter={(event) => activate(interaction.show, markId, event.currentTarget)}
                        onMouseLeave={() => interaction.hide()}
                        onFocus={(event) => activate(interaction.show, markId, event.currentTarget)}
                        onBlur={() => interaction.hide()}
                        onClick={(event) => activate(interaction.pin, markId, event.currentTarget)}
                      >
                        <circle cx={cx} cy={cy} r="12" fill="transparent" />
                        <ChartSymbol
                          symbol={item.symbol}
                          cx={cx}
                          cy={cy}
                          size={
                            interaction.markId === markId
                              ? seriesIndex === 0
                                ? 8
                                : 6
                              : seriesIndex === 0
                                ? 6.5
                                : 4.5
                          }
                          fill={stroke}
                          stroke={stroke}
                        />
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

function segments(
  series: ChartSeries,
  categories: readonly ChartCategory[],
  geo: ChartGeometry,
): { key: string; points: string }[] {
  const result: { key: string; points: string }[] = [];
  let current: string[] = [];
  let start = 0;
  categories.forEach((category, index) => {
    const datum: ChartDatum | undefined = series.data.find((entry) => entry.categoryId === category.id);
    if (!datum || datum.plot === null) {
      if (current.length > 1) {
        result.push({ key: `${series.id}-${start}`, points: current.join(" ") });
      }
      current = [];
      return;
    }
    if (current.length === 0) {
      start = index;
    }
    const x = categoryCenter(index, categories.length, geo);
    const y = yAt(datum.plot, geo.domainMax, geo.plotY, geo.plotH);
    current.push(`${x},${y}`);
  });
  if (current.length > 1) {
    result.push({ key: `${series.id}-${start}`, points: current.join(" ") });
  }
  return result;
}
