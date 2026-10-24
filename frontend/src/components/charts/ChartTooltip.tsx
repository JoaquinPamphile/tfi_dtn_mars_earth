import type { TooltipModel } from "./types";
import styles from "./charts.module.css";

export function ChartTooltip({
  model,
  x,
  y,
  placement,
}: {
  model: TooltipModel;
  x: number;
  y: number;
  placement: "above" | "below";
}) {
  return (
    <div
      className={styles.tooltip}
      role="tooltip"
      data-placement={placement}
      style={{ left: x, top: y }}
    >
      <p className={styles.tooltipTitle}>{model.title}</p>
      {model.rows.map((row) => (
        <p key={row.label} className={styles.tooltipRow}>
          <span className={styles.tooltipLabel}>{row.label}</span>
          {row.values.map((value) => (
            <span key={value}>{value}</span>
          ))}
        </p>
      ))}
    </div>
  );
}
