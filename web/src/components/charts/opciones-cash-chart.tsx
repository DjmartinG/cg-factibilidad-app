"use client";

import { useCallback } from "react";
import type { EChartsOption } from "echarts";
import { EChart } from "@/components/charts/echart";
import type { ChartTokens } from "@/lib/chart-tokens";
import { fmtCop } from "@/lib/format";
import type { OpcionesCaja } from "@/lib/api";

type AxisParam = { seriesName?: string; value: number[] };

/** Eje Y compacto: magnitud en "mil M" sin el sufijo. */
function tickY(v: number): string {
  if (v === 0) return "0";
  return `${(v / 1_000_000).toLocaleString("en-US", { maximumFractionDigits: 0 }).replace(/,/g, ".")}`;
}

/**
 * Caja acumulada BASE (teal, área) vs ESCENARIO de fasing (terracota, punteada), sobre un eje temporal
 * común (el escenario se desplaza `offset` meses si su inicio cambió). Marca el valle (exposición máx)
 * del escenario. Reusa el patrón del flujo de caja.
 */
export function OpcionesCashChart({
  base,
  escenario,
  offset,
  height = 300,
}: {
  base: OpcionesCaja[];
  escenario: OpcionesCaja[];
  offset: number;
  height?: number;
}) {
  const buildOption = useCallback(
    (t: ChartTokens): EChartsOption => {
      const baseD = base.map((d) => [d.m, d.acum]);
      const escD = escenario.map((d) => [d.m + offset, d.acum]);
      const maxX = Math.max(base.length - 1, escenario.length - 1 + offset, 1);
      const terracota = t.palette[5];

      let valle: { m: number; v: number } | null = null;
      for (const d of escenario) {
        if (valle == null || d.acum < valle.v) valle = { m: d.m + offset, v: d.acum };
      }

      return {
        backgroundColor: "transparent",
        animationDuration: 420,
        grid: { top: 22, right: 16, bottom: 34, left: 8, containLabel: true },
        legend: {
          data: ["Base", "Escenario"],
          bottom: 0,
          textStyle: { color: t.axisLabel, fontSize: 11 },
          itemWidth: 18,
          itemHeight: 3,
        },
        tooltip: {
          trigger: "axis",
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          borderWidth: 1,
          textStyle: { color: t.tooltipText, fontSize: 12 },
          padding: [6, 10],
          formatter: (params) => {
            const arr = params as unknown as AxisParam[];
            const m = (arr[0]?.value?.[0] ?? 0) as number;
            let html = `<div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:.04em;color:${t.axisLabel}">Año ${Math.floor(m / 12) + 1}, mes ${(m % 12) + 1}</div>`;
            for (const p of arr) {
              const v = p.value?.[1];
              if (v != null) {
                const col = p.seriesName === "Base" ? t.primary : terracota;
                html += `<div style="color:${col}">${p.seriesName} ${fmtCop(v)}</div>`;
              }
            }
            return html;
          },
        },
        xAxis: {
          type: "value",
          min: 0,
          max: maxX,
          axisLabel: { color: t.axisLabel, fontSize: 11, formatter: (v: number) => `${Math.round(v / 12)}a` },
          axisLine: { lineStyle: { color: t.axisLine } },
          axisTick: { show: false },
          splitLine: { show: false },
        },
        yAxis: {
          type: "value",
          axisLabel: { color: t.axisLabel, fontSize: 11, formatter: (v: number) => tickY(v) },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { lineStyle: { color: t.grid } },
        },
        series: [
          {
            name: "Base",
            type: "line",
            smooth: true,
            showSymbol: false,
            data: baseD,
            z: 2,
            lineStyle: { color: t.primary, width: 2 },
            areaStyle: { color: t.primary, opacity: t.areaOpacity * 0.6 },
            markLine: {
              symbol: "none",
              silent: true,
              data: [{ yAxis: 0, label: { show: false }, lineStyle: { color: t.axisLabel, type: "dashed", width: 1, opacity: 0.5 } }],
            },
          },
          {
            name: "Escenario",
            type: "line",
            smooth: true,
            showSymbol: false,
            data: escD,
            z: 3,
            lineStyle: { color: terracota, width: 2, type: "dashed" },
            markPoint: valle
              ? {
                  symbol: "circle",
                  symbolSize: 9,
                  data: [
                    {
                      name: "Exp. máx",
                      coord: [valle.m, valle.v],
                      itemStyle: { color: t.peligro, borderColor: t.tooltipBg, borderWidth: 2 },
                      label: {
                        show: true,
                        formatter: `Exp. máx ${fmtCop(valle.v)}`,
                        position: "bottom",
                        color: t.peligro,
                        fontSize: 10,
                        fontWeight: 600,
                      },
                    },
                  ],
                }
              : undefined,
          },
        ],
      };
    },
    [base, escenario, offset],
  );

  return <EChart buildOption={buildOption} height={height} exportName="aleph-opciones-caja" />;
}
