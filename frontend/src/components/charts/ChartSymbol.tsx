import type { ChartSymbol as ChartSymbolName } from "./types";

export function ChartSymbol({
  symbol,
  cx,
  cy,
  size,
  fill,
  stroke,
}: {
  symbol: ChartSymbolName;
  cx: number;
  cy: number;
  size: number;
  fill: string;
  stroke: string;
}) {
  if (symbol === "square") {
    return (
      <rect
        x={cx - size}
        y={cy - size}
        width={size * 2}
        height={size * 2}
        fill={fill}
        stroke={stroke}
        strokeWidth={1.5}
      />
    );
  }
  if (symbol === "diamond") {
    return (
      <polygon
        points={`${cx},${cy - size} ${cx + size},${cy} ${cx},${cy + size} ${cx - size},${cy}`}
        fill={fill}
        stroke={stroke}
        strokeWidth={1.5}
      />
    );
  }
  return <circle cx={cx} cy={cy} r={size} fill={fill} stroke={stroke} strokeWidth={1.5} />;
}

export function seriesStroke(index: number): string {
  return `var(--chart-series-${index + 1})`;
}

export function seriesDash(index: number): string | undefined {
  if (index === 1) {
    return "6 4";
  }
  if (index === 2) {
    return "2 3";
  }
  return undefined;
}
