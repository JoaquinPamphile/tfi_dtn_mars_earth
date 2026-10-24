import type { ReactNode, Ref } from "react";
import { ChartLegend } from "./ChartLegend";
import { ChartTooltip } from "./ChartTooltip";
import type { ChartCategory, ChartSeries, TooltipModel } from "./types";
import styles from "./charts.module.css";

export function ScientificChart({
  title,
  summary,
  series,
  categories,
  marker,
  activeSeries,
  onActiveSeries,
  tooltip,
  anchor,
  plotRef,
  children,
}: {
  title: string;
  summary: string;
  series: readonly ChartSeries[];
  categories: readonly ChartCategory[];
  marker: "bar" | "point";
  activeSeries: string | null;
  onActiveSeries: (id: string | null) => void;
  tooltip: TooltipModel | null;
  anchor: { x: number; y: number; placement: "above" | "below" };
  plotRef: Ref<HTMLDivElement>;
  children: ReactNode;
}) {
  return (
    <figure className={styles.chart} aria-label={summary}>
      <div className={styles.chartHead}>
        <figcaption className={styles.chartTitle}>{title}</figcaption>
        <ChartLegend
          series={series}
          activeId={activeSeries}
          onActiveChange={onActiveSeries}
          marker={marker}
        />
      </div>
      <div className={styles.plot} ref={plotRef}>
        {children}
        {tooltip ? (
          <ChartTooltip model={tooltip} x={anchor.x} y={anchor.y} placement={anchor.placement} />
        ) : null}
      </div>
      <table className="srOnly">
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">Serie</th>
            {categories.map((category) => (
              <th key={category.id} scope="col">
                {category.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {series.map((item) => (
            <tr key={item.id}>
              <th scope="row">{item.label}</th>
              {categories.map((category) => {
                const datum = item.data.find((entry) => entry.categoryId === category.id);
                return <td key={category.id}>{datum?.ariaLabel ?? "No disponible en evidence"}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

export function ChartUnavailable({ title, summary }: { title: string; summary: string }) {
  return (
    <figure className={styles.chart} aria-label={summary}>
      <figcaption className={styles.chartTitle}>{title}</figcaption>
      <p className={styles.unavailable} role="status">
        No disponible en evidence
      </p>
    </figure>
  );
}
