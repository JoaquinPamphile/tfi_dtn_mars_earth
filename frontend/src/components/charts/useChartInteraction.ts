import { useRef, useState } from "react";
import type { ChartDatum, ChartSeries } from "./types";

export function useChartInteraction(series: readonly ChartSeries[]) {
  const [seriesId, setSeriesId] = useState<string | null>(null);
  const [hoveredMark, setHoveredMark] = useState<string | null>(null);
  const [pinnedMark, setPinnedMark] = useState<string | null>(null);
  const anchors = useRef(new Map<string, { x: number; y: number; placement: "above" | "below" }>());
  const markId = hoveredMark ?? pinnedMark;
  const datum = markId ? findDatum(series, markId) : null;
  const anchor = (markId ? anchors.current.get(markId) : undefined) ?? {
    x: 16,
    y: 16,
    placement: "below" as const,
  };

  function remember(id: string, element: Element, plot: HTMLElement) {
    const mark = element.getBoundingClientRect();
    const box = plot.getBoundingClientRect();
    const rawX = mark.left + mark.width / 2 - box.left;
    const top = mark.top - box.top;
    const bottom = mark.bottom - box.top;
    const spaceAbove = top;
    const spaceBelow = box.height - bottom;
    const placement =
      spaceBelow >= 96 || (spaceBelow >= spaceAbove && spaceBelow >= 48) ? "below" : "above";
    const x = Math.min(Math.max(8, rawX - 8), Math.max(8, box.width - 220));
    const y = placement === "below" ? bottom + 6 : Math.max(8, top - 6);
    anchors.current.set(id, { x, y, placement });
  }

  return {
    seriesId,
    setSeriesId,
    markId,
    tooltip: datum?.tooltip ?? null,
    anchor,
    show(id: string, element: Element, plot: HTMLElement) {
      remember(id, element, plot);
      setHoveredMark(id);
    },
    hide() {
      setHoveredMark(null);
    },
    pin(id: string, element: Element, plot: HTMLElement) {
      remember(id, element, plot);
      setPinnedMark((current) => (current === id ? null : id));
    },
  };
}

export function chartPlot(element: SVGElement): HTMLElement | null {
  const parent = element.ownerSVGElement?.parentElement;
  return parent instanceof HTMLElement ? parent : null;
}

function findDatum(series: readonly ChartSeries[], markId: string): ChartDatum | null {
  for (const item of series) {
    for (const datum of item.data) {
      if (`${item.id}:${datum.categoryId}` === markId) {
        return datum;
      }
    }
  }
  return null;
}
