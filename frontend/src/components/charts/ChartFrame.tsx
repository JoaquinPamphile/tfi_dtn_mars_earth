import { useId, type ReactNode } from "react";
import { yAt } from "./scale";
import type { ChartCategory, ChartGeometry } from "./types";

const MARGIN = { top: 8, right: 14, bottom: 34, left: 86 };

export function ChartFrame({
  width,
  height,
  yLabel,
  domainMax,
  ticks,
  formatTick,
  categories,
  children,
}: {
  width: number;
  height: number;
  yLabel: string;
  domainMax: number;
  ticks: readonly number[];
  formatTick: (value: number) => string;
  categories: readonly ChartCategory[];
  children: (geo: ChartGeometry) => ReactNode;
}) {
  const uid = useId().replace(/:/g, "");
  const plotX = MARGIN.left;
  const plotY = MARGIN.top + 8;
  const plotW = Math.max(1, width - MARGIN.left - MARGIN.right);
  const plotH = Math.max(1, height - plotY - MARGIN.bottom);
  const geo: ChartGeometry = { width, height, plotX, plotY, plotW, plotH, domainMax, uid };
  const baseline = yAt(0, domainMax, plotY, plotH);
  const slot = plotW / Math.max(categories.length, 1);
  const categorySize = slot < 92 ? 11 : 13;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="presentation">
      <defs>
        <pattern id={`${uid}-hatch`} width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="var(--chart-series-2)" opacity="0.28" />
          <path d="M0 6 L6 0 M-1 1 L1 -1 M5 7 L7 5" stroke="var(--chart-series-2)" strokeWidth="1.4" />
        </pattern>
        <pattern id={`${uid}-dots`} width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="var(--chart-series-3)" opacity="0.22" />
          <circle cx="3" cy="3" r="1.15" fill="var(--chart-series-3)" />
        </pattern>
      </defs>
      {ticks.map((tick) => {
        const y = yAt(tick, domainMax, plotY, plotH);
        return (
          <g key={tick}>
            <line
              x1={plotX}
              x2={plotX + plotW}
              y1={y}
              y2={y}
              stroke="var(--chart-grid)"
              strokeWidth={tick === 0 ? 1.25 : 1}
            />
            <text
              x={plotX - 8}
              y={y + 4}
              textAnchor="end"
              fill="var(--chart-axis)"
              fontSize="12"
              fontFamily="var(--font)"
              dominantBaseline="middle"
            >
              {formatTick(tick)}
            </text>
          </g>
        );
      })}
      <line
        x1={plotX}
        x2={plotX}
        y1={plotY}
        y2={baseline}
        stroke="var(--chart-axis)"
        strokeWidth="1.25"
      />
      <text
        x="14"
        y={plotY + plotH / 2}
        fill="var(--chart-axis)"
        fontSize="12"
        fontFamily="var(--font)"
        textAnchor="middle"
        dominantBaseline="middle"
        transform={`rotate(-90 14 ${plotY + plotH / 2})`}
      >
        {yLabel}
      </text>
      {categories.map((category, index) => (
        <text
          key={category.id}
          x={plotX + slot * index + slot / 2}
          y={height - 10}
          textAnchor="middle"
          fill="var(--color-text)"
          fontSize={categorySize}
          fontFamily="var(--font)"
        >
          {category.label}
        </text>
      ))}
      {children(geo)}
    </svg>
  );
}

export function categoryCenter(index: number, count: number, geo: ChartGeometry): number {
  const slot = geo.plotW / Math.max(count, 1);
  return geo.plotX + slot * index + slot / 2;
}

export function categorySlot(count: number, geo: ChartGeometry): number {
  return geo.plotW / Math.max(count, 1);
}

export function seriesFill(index: number, uid: string): string {
  if (index === 1) {
    return `url(#${uid}-hatch)`;
  }
  if (index === 2) {
    return `url(#${uid}-dots)`;
  }
  return "var(--chart-series-1)";
}
