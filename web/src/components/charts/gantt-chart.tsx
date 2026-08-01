"use client";

import { useMemo, useRef, useState } from "react";
import type { ScheduleEtapa } from "@/lib/api";

const ROW = 56;
const LAB = 150;
const MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/**
 * Gantt de etapas (HTML/CSS, tokens de ALEPH). Cada etapa muestra sus 6 fases del cronograma:
 * Comercialización y Construcción como barras, Equilibrio / Escrituración / Entrega como marcas, y
 * Cuotas iniciales como línea sutil. Cuadrícula por trimestres, línea de HOY (dinámica) y una guía de
 * mes que sigue el cursor. Fechas exactas del motor (hitos IV/PE/FV/IC/FC + escrituración/entrega).
 */
export function GanttChart({ etapas, baseDate }: { etapas: ScheduleEtapa[]; horizonte: number; baseDate: string | null }) {
  const [cross, setCross] = useState<{ leftPct: number; label: string } | null>(null);
  const trackWrapRef = useRef<HTMLDivElement>(null);

  const g = useMemo(() => {
    const base = baseDate ? new Date(baseDate) : null;
    const baseIdx = base ? base.getFullYear() * 12 + base.getMonth() : 0; // índice absoluto del mes 0
    const fdate = (m: number) => {
      const i = baseIdx + Math.round(m);
      return `${MES[((i % 12) + 12) % 12]} ${Math.floor(i / 12)}`;
    };

    const all: number[] = [];
    for (const e of etapas) {
      all.push(e.iv_mes, e.fv_mes, e.ic_mes, e.fc_mes);
      if (e.esc_mes != null) all.push(e.esc_mes);
      if (e.ent_mes != null) all.push(e.ent_mes);
    }
    const maxM = (all.length ? Math.max(...all) : 12) + 2;

    // HOY relativo al mes 0 (puede ser negativo si el proyecto aún no arranca)
    let hoyM: number | null = null;
    if (base) {
      const now = new Date();
      hoyM = (now.getFullYear() - base.getFullYear()) * 12 + (now.getMonth() - base.getMonth()) + (now.getDate() - 1) / 30;
    }
    const startM = Math.min(0, hoyM != null ? Math.floor(hoyM) - 2 : 0);
    const span = maxM - startM || 1;
    const pos = (m: number) => ((m - startM) / span) * 100;

    // años (etiqueta centrada) + trimestres (líneas)
    const years: { y: number; center: number }[] = [];
    const qlines: { off: number; year: boolean }[] = [];
    if (base) {
      for (let y = base.getFullYear() - 2; y <= base.getFullYear() + 12; y++) {
        const jan = (y - base.getFullYear()) * 12 - base.getMonth();
        if (jan + 6 > startM && jan + 6 < maxM) years.push({ y, center: jan + 6 });
        for (const q of [0, 3, 6, 9]) {
          const off = jan + q;
          if (off > startM && off < maxM) qlines.push({ off, year: q === 0 });
        }
      }
    }
    return { fdate, pos, hoyM, years, qlines, span, startM };
  }, [etapas, baseDate]);

  const height = etapas.length * ROW + 46;

  const onMove = (ev: React.MouseEvent) => {
    const el = trackWrapRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const x = ev.clientX - r.left - LAB;
    const tw = r.width - LAB;
    if (x < 0 || x > tw) { setCross(null); return; }
    const m = g.startM + (x / tw) * g.span;
    setCross({ leftPct: (x / tw) * 100, label: g.fdate(m) });
  };

  if (!etapas.length) return null;

  return (
    <div style={{ height }} className="relative text-[var(--foreground)]">
      {/* eje de años */}
      <div className="relative h-5" style={{ marginLeft: LAB }}>
        {g.years.map((y) => (
          <span
            key={y.y}
            className="num absolute top-0.5 -translate-x-1/2 text-[10.5px] tracking-wide text-muted-foreground"
            style={{ left: `${g.pos(y.center)}%` }}
          >
            {y.y}
          </span>
        ))}
      </div>

      {/* zona de filas: cuadrícula + filas + HOY + crosshair */}
      <div ref={trackWrapRef} className="relative" onMouseMove={onMove} onMouseLeave={() => setCross(null)}>
        {/* cuadrícula por trimestre */}
        <div className="pointer-events-none absolute inset-0" style={{ marginLeft: LAB }}>
          {g.qlines.map((q, i) => (
            <i
              key={i}
              className="absolute bottom-0 top-0 w-px"
              style={{ left: `${g.pos(q.off)}%`, background: q.year ? "var(--border)" : "var(--rule)", opacity: q.year ? 0.9 : 0.6 }}
            />
          ))}
        </div>

        {etapas.map((e) => (
          <Row key={String(e.cod)} e={e} pos={g.pos} fdate={g.fdate} />
        ))}

        {/* línea de HOY */}
        {g.hoyM != null && g.hoyM > g.startM && (
          <div
            className="pointer-events-none absolute top-0 z-[5]"
            style={{ left: `calc(${LAB}px + (100% - ${LAB}px) * ${((g.hoyM - g.startM) / g.span).toFixed(5)})`, bottom: 2 }}
          >
            <div className="absolute inset-y-0 w-0 border-l-[1.5px] border-dashed" style={{ borderColor: "var(--gantt-hoy)" }} />
            <div
              className="absolute -top-px left-[3px] px-[3px] text-[9px] font-bold tracking-wider"
              style={{ color: "var(--gantt-hoy)", background: "var(--card)" }}
            >
              HOY
            </div>
          </div>
        )}

        {/* guía de mes que sigue el cursor */}
        {cross && (
          <div
            className="pointer-events-none absolute top-0 z-[6]"
            style={{ left: `calc(${LAB}px + (100% - ${LAB}px) * ${cross.leftPct / 100})`, bottom: 2 }}
          >
            <div className="absolute inset-y-0 w-0 border-l" style={{ borderColor: "color-mix(in oklab, var(--primary) 45%, transparent)" }} />
            <div
              className="num absolute -top-[18px] -translate-x-1/2 whitespace-nowrap rounded border px-1.5 py-px text-[9.5px] font-semibold"
              style={{ color: "var(--primary)", background: "var(--card)", borderColor: "var(--border)" }}
            >
              {cross.label}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ e, pos, fdate }: { e: ScheduleEtapa; pos: (m: number) => number; fdate: (m: number) => string }) {
  const cuoFin = e.cuo_fin_mes ?? null;
  const esc = e.esc_mes ?? null;
  const ent = e.ent_mes ?? null;
  const tip = (
    <>
      <div className="mb-1 font-semibold">
        {e.nombre} · {e.unidades} und
      </div>
      <TipRow mark={<span className="inline-block size-2 rounded-[2px] bg-primary opacity-85" />} k="Comercialización" v={`${fdate(e.iv_mes)} → ${fdate(e.fv_mes)}`} />
      {cuoFin != null ? <TipRow mark={<span className="inline-block h-0 w-2.5 border-t-2 border-dotted border-primary/40" />} k="Cuotas iniciales" v={`${fdate(e.iv_mes)} → ${fdate(cuoFin)}`} /> : null}
      <TipRow mark={<span className="inline-block size-2 rounded-full border-[1.5px] border-primary bg-card" />} k="Equilibrio" v={fdate(e.pe_mes)} />
      <TipRow mark={<span className="inline-block size-2 rounded-[2px] bg-cg-amber opacity-90" />} k="Construcción" v={`${fdate(e.ic_mes)} → ${fdate(e.fc_mes)}`} />
      {esc != null ? <TipRow mark={<span className="inline-block size-[7px] rotate-45 bg-cg-amber" />} k="Escrituración" v={fdate(esc)} /> : null}
      {ent != null ? <TipRow mark={<span className="inline-block" style={{ width: 0, height: 0, borderLeft: "4px solid transparent", borderRight: "4px solid transparent", borderBottom: "7px solid var(--primary)" }} />} k="Entrega" v={fdate(ent)} /> : null}
    </>
  );

  return (
    <div className="group relative flex items-center border-t border-rule transition-colors first:border-0 hover:bg-[color-mix(in_oklab,var(--primary)_5%,transparent)]" style={{ height: ROW }}>
      <div className="shrink-0 pr-3.5" style={{ width: LAB }}>
        <div className="text-[12.5px] font-semibold">{e.nombre}</div>
        <div className="mt-px num text-[10.5px] text-muted-foreground">{e.unidades} und</div>
      </div>
      <div className="relative h-full flex-1">
        {cuoFin != null ? (
          <div className="absolute top-[25px] h-0 border-t-2 border-dotted border-primary/40" style={{ left: `${pos(e.iv_mes)}%`, width: `${pos(cuoFin) - pos(e.iv_mes)}%` }} />
        ) : null}
        <div className="absolute top-[13px] h-[9px] rounded-[3px] bg-primary opacity-85" style={{ left: `${pos(e.iv_mes)}%`, width: `${Math.max(pos(e.fv_mes) - pos(e.iv_mes), 0.3)}%` }} />
        <div className="absolute top-[14px] size-2 -translate-x-1/2 rounded-full border-[1.5px] border-primary bg-card" style={{ left: `${pos(e.pe_mes)}%` }} />
        <div className="absolute top-[33px] h-[9px] rounded-[3px] bg-cg-amber opacity-90" style={{ left: `${pos(e.ic_mes)}%`, width: `${Math.max(pos(e.fc_mes) - pos(e.ic_mes), 0.3)}%` }} />
        {esc != null ? <div className="absolute top-[34px] size-[7px] -translate-x-1/2 rotate-45 bg-cg-amber" style={{ left: `${pos(esc)}%` }} /> : null}
        {ent != null ? (
          <div className="absolute top-[33px] -translate-x-1/2" style={{ left: `${pos(ent)}%`, width: 0, height: 0, borderLeft: "5px solid transparent", borderRight: "5px solid transparent", borderBottom: "8px solid var(--primary)" }} />
        ) : null}
      </div>
      {/* tooltip */}
      <div className="pointer-events-none absolute left-1/2 top-full z-20 hidden -translate-x-1/2 rounded-[var(--radius-data)] border bg-card p-2.5 text-xs shadow-[var(--shadow-card)] group-hover:block" style={{ minWidth: 250 }}>
        {tip}
      </div>
    </div>
  );
}

function TipRow({ mark, k, v }: { mark: React.ReactNode; k: string; v: string }) {
  return (
    <div className="mt-1 flex items-center gap-2">
      <span className="flex w-2.5 justify-center">{mark}</span>
      <span className="w-[100px] text-muted-foreground">{k}</span>
      <span className="num">{v}</span>
    </div>
  );
}
