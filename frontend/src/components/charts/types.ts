export type ChartSymbol = "circle" | "square" | "diamond";

export interface ChartCategory {
  id: string;
  label: string;
}

export interface TooltipRow {
  label: string;
  values: readonly string[];
}

export interface TooltipModel {
  title: string;
  rows: readonly TooltipRow[];
}

export interface ChartDatum {
  categoryId: string;
  /** Posición en la unidad del eje. null: el punto no se dibuja. */
  plot: number | null;
  tooltip: TooltipModel;
  ariaLabel: string;
  valueLabel?: string;
}

export interface ChartSeries {
  id: string;
  label: string;
  symbol: ChartSymbol;
  data: readonly ChartDatum[];
}

export interface ChartGeometry {
  width: number;
  height: number;
  plotX: number;
  plotY: number;
  plotW: number;
  plotH: number;
  domainMax: number;
  uid: string;
}
