import { ChartSymbol, seriesDash, seriesStroke } from "./ChartSymbol";
import type { ChartSeries } from "./types";
import styles from "./charts.module.css";

export function ChartLegend({
  series,
  activeId,
  onActiveChange,
  marker,
}: {
  series: readonly ChartSeries[];
  activeId: string | null;
  onActiveChange: (id: string | null) => void;
  marker: "bar" | "point";
}) {
  if (series.length < 2) {
    return null;
  }
  return (
    <ul className={styles.legend}>
      {series.map((item, index) => (
        <li key={item.id}>
          <button
            type="button"
            className={styles.legendItem}
            data-dim={activeId !== null && activeId !== item.id ? "true" : "false"}
            aria-pressed={activeId === item.id}
            onMouseEnter={() => onActiveChange(item.id)}
            onMouseLeave={() => onActiveChange(null)}
            onFocus={() => onActiveChange(item.id)}
            onBlur={() => onActiveChange(null)}
            onClick={() => onActiveChange(activeId === item.id ? null : item.id)}
          >
            {marker === "bar" ? (
              <span className={styles.swatch} data-series={String(index)} aria-hidden="true" />
            ) : (
              <LegendPoint index={index} symbol={item.symbol} />
            )}
            {item.label}
          </button>
        </li>
      ))}
    </ul>
  );
}

function LegendPoint({
  index,
  symbol,
}: {
  index: number;
  symbol: ChartSeries["symbol"];
}) {
  const stroke = seriesStroke(index);
  const dash = seriesDash(index);
  return (
    <svg className={styles.symbolLine} width="36" height="14" viewBox="0 0 36 14" aria-hidden="true">
      <line
        x1="2"
        y1="7"
        x2="34"
        y2="7"
        stroke={stroke}
        strokeWidth="2"
        strokeDasharray={dash}
      />
      <ChartSymbol symbol={symbol} cx={18} cy={7} size={4} fill={stroke} stroke={stroke} />
    </svg>
  );
}
