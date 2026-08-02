"use client";

import { useCallback } from "react";
import type { EChartsOption } from "echarts";
import { EChart } from "@/components/charts/echart";
import type { ChartTokens } from "@/lib/chart-tokens";
import type { MacroPunto } from "@/lib/api";

type AxisParam = { value: number[] };

/**
 * Abanico macro (fan chart): la senda BASE (línea teal) dentro de un CONO de incertidumbre (banda
 * sombreada bajo–alto). La banda se pinta con dos series apiladas: `bajo` (transparente, fija la línea
 * base del apilado) + `banda = alto − bajo` (área rellena). Puro presentación — los puntos vienen del
 * motor `macro_forward` vía el API.
 */
export function MacroFanChart({ puntos, unidad, height = 220 }: { puntos: MacroPunto[]; unidad: string; height?: number }) {
  const esPct = unidad === "pct_ea";

  const buildOption = useCallback(
    (t: ChartTokens): EChartsOption => {
      const fmtVal = (v: number) => (esPct ? `${(v * 100).toFixed(1)}%` : `$${Math.round(v).toLocaleString("es-CO")}`);
      const fmtTick = (v: number) => (esPct ? `${(v * 100).toFixed(0)}%` : `${(v / 1000).toFixed(1)}k`);
      const anios = puntos.map((p) => p.anio);
      const min = anios[0];
      const max = anios[anios.length - 1];
      const bajo = puntos.map((p) => [p.anio, p.bajo]);
      const banda = puntos.map((p) => [p.anio, p.alto - p.bajo]); // apilado sobre `bajo` → llega a `alto`
      const base = puntos.map((p) => [p.anio, p.base]);

      return {
        backgroundColor: "transparent",
        animationDuration: 420,
        grid: { top: 14, right: 14, bottom: 26, left: 8, containLabel: true },
        tooltip: {
          trigger: "axis",
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          borderWidth: 1,
          textStyle: { color: t.tooltipText, fontSize: 12 },
          padding: [6, 10],
          formatter: (params) => {
            const arr = params as unknown as AxisParam[];
            const anio = arr[0]?.value?.[0];
            const p = puntos.find((x) => x.anio === anio);
            if (!p) return "";
            return (
              `<div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:.04em;color:${t.axisLabel}">${anio}</div>` +
              `<div style="margin-top:2px;font-weight:600">base ${fmtVal(p.base)}</div>` +
              `<div style="color:${t.axisLabel}">rango ${fmtVal(p.bajo)} – ${fmtVal(p.alto)}</div>`
            );
          },
        },
        xAxis: {
          type: "value",
          min,
          max,
          interval: 2,
          axisLabel: { color: t.axisLabel, fontSize: 11, formatter: (v: number) => `${Math.round(v)}` },
          axisLine: { lineStyle: { color: t.axisLine } },
          axisTick: { show: false },
          splitLine: { show: false },
        },
        yAxis: {
          type: "value",
          scale: true,
          axisLabel: { color: t.axisLabel, fontSize: 11, formatter: (v: number) => fmtTick(v) },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { lineStyle: { color: t.grid } },
        },
        series: [
          {
            name: "_bajo",
            type: "line",
            data: bajo,
            stack: "banda",
            showSymbol: false,
            silent: true,
            lineStyle: { opacity: 0 },
            areaStyle: { opacity: 0 },
            z: 1,
          },
          {
            name: "Rango",
            type: "line",
            data: banda,
            stack: "banda",
            showSymbol: false,
            silent: true,
            lineStyle: { opacity: 0 },
            areaStyle: { color: t.primary, opacity: t.areaOpacity * 0.9 },
            z: 1,
          },
          {
            name: "Base",
            type: "line",
            data: base,
            showSymbol: false,
            lineStyle: { color: t.primary, width: 2.25 },
            z: 3,
          },
        ],
      };
    },
    [puntos, esPct],
  );

  return <EChart buildOption={buildOption} height={height} exportName="aleph-macro" />;
}
