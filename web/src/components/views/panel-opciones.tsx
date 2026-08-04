"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import type { Opciones, EtapaMod } from "@/lib/api";
import { evaluarOpciones } from "@/lib/actions";
import { fmtPct, fmtCop, fmtInt } from "@/lib/format";
import { Banner } from "@/components/banner";
import { OpcionesCashChart } from "@/components/charts/opciones-cash-chart";

/** Opciones reales por etapa (fasing): retrasar / acelerar / quitar cada etapa y ver el impacto en caja
 *  y retorno. TIR/VPN DIRECCIONALES (suelta la fiducia); margen y caja EXACTOS. */
export function PanelOpciones({ slug }: { slug: string }) {
  const [mods, setMods] = useState<Record<string, EtapaMod>>({});
  const [data, setData] = useState<Opciones | null>(null);
  const [pending, start] = useTransition();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      start(async () => {
        try {
          setData(await evaluarOpciones(slug, mods));
        } catch {
          /* silencioso: queda el último estado bueno */
        }
      });
    }, 250);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [mods, slug]);

  function setMod(cod: string, patch: EtapaMod) {
    setMods((prev) => {
      const cur = { ...prev[cod], ...patch };
      const clean: EtapaMod = {};
      if (cur.delay) clean.delay = cur.delay;
      if (cur.ritmo_factor && cur.ritmo_factor !== 1) clean.ritmo_factor = cur.ritmo_factor;
      if (cur.quitar) clean.quitar = true;
      const next = { ...prev };
      if (Object.keys(clean).length) next[cod] = clean;
      else delete next[cod];
      return next;
    });
  }

  const tocado = Object.keys(mods).length > 0;
  const base = data?.base.indicadores;
  const res = data?.resultado.indicadores;
  const vacio = data?.resultado.vacio;

  return (
    <div className="space-y-7">
      <Banner tone="warning" label="Opciones por etapa">
        Retrasa, acelera o quita cada etapa para ver el impacto en la <span className="font-medium">caja</span> y
        el retorno. El <span className="font-medium">margen y la caja son exactos</span>; la TIR y el VPN son{" "}
        <span className="font-medium">direccionales</span> (base mensual, para comparar) — la cifra oficial está
        en la pestaña Resumen.
      </Banner>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        {/* Controles por etapa */}
        <div className="space-y-3 rounded-[var(--radius-data)] border bg-card p-5">
          <div className="flex items-baseline justify-between">
            <h3 className="text-sm font-semibold">Etapas</h3>
            {tocado ? (
              <button
                type="button"
                onClick={() => setMods({})}
                className="text-xs text-muted-foreground underline-offset-2 hover:underline"
              >
                Restablecer
              </button>
            ) : null}
          </div>
          {data ? (
            data.etapas.map((e) => (
              <EtapaControl
                key={String(e.cod)}
                nombre={e.nombre}
                und={e.und}
                mod={mods[String(e.cod)] ?? {}}
                onChange={(patch) => setMod(String(e.cod), patch)}
              />
            ))
          ) : (
            <div className="py-6 text-center text-sm text-muted-foreground">Cargando etapas…</div>
          )}
        </div>

        {/* KPIs base vs escenario */}
        <div className={"rounded-[var(--radius-data)] border bg-card p-5 transition-opacity " + (pending ? "opacity-60" : "")}>
          {vacio ? (
            <div className="flex h-full items-center justify-center py-10 text-center text-sm text-muted-foreground">
              Quitaste todas las etapas: no hay proyecto que evaluar.
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-x-6 gap-y-5">
              <Kpi label="Unidades" hero value={res ? fmtInt(res.unidades) : "—"} delta={intDelta(res?.unidades, base?.unidades, "und")} />
              <Kpi label="Margen" value={fmtPct(res?.margen)} delta={ppDelta(res?.margen, base?.margen)} />
              <Kpi label="TIR proyecto · dir." value={fmtPct(res?.tir)} delta={ppDelta(res?.tir, base?.tir)} />
              <Kpi label="VPN · dir." value={fmtCop(res?.vpn)} delta={copDelta(res?.vpn, base?.vpn)} />
              <Kpi label="Exposición máx." value={fmtCop(res?.exposicion_maxima)} delta={copDelta(res?.exposicion_maxima, base?.exposicion_maxima)} />
              <Kpi label="Crédito máx." value={fmtCop(res?.credito_max)} delta={copDelta(res?.credito_max, base?.credito_max)} />
            </div>
          )}
        </div>
      </div>

      {/* Timeline de caja base vs escenario */}
      {data && !vacio && data.resultado.caja.length ? (
        <div className="rounded-[var(--radius-data)] border bg-card p-4">
          <div className="mb-1 text-sm font-medium text-foreground">Caja acumulada · base vs escenario</div>
          <div className="mb-2 text-xs text-muted-foreground">Cuánto profundiza o alivia el valle de caja el fasing elegido · mil M COP</div>
          <OpcionesCashChart base={data.base.caja} escenario={data.resultado.caja} offset={data.resultado.inicio_offset} />
        </div>
      ) : null}
    </div>
  );
}

function EtapaControl({
  nombre,
  und,
  mod,
  onChange,
}: {
  nombre: string;
  und: number;
  mod: EtapaMod;
  onChange: (patch: EtapaMod) => void;
}) {
  const quitar = !!mod.quitar;
  const delay = mod.delay ?? 0;
  const ritmo = mod.ritmo_factor ?? 1;

  return (
    <div className={"rounded-[var(--radius-data)] border border-rule p-3 " + (quitar ? "opacity-55" : "")}>
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <span className="text-sm font-medium">{nombre}</span>
          <span className="num ml-2 text-[0.72rem] text-muted-foreground">{fmtInt(und)} und</span>
        </div>
        <button
          type="button"
          onClick={() => onChange({ quitar: !quitar })}
          className={
            "shrink-0 rounded-full px-2.5 py-0.5 text-[0.7rem] font-medium transition-colors [transition-timing-function:var(--ease-out)] " +
            (quitar
              ? "bg-danger/10 text-danger"
              : "border border-rule text-muted-foreground hover:text-foreground")
          }
        >
          {quitar ? "Quitada · restaurar" : "Quitar"}
        </button>
      </div>

      {!quitar ? (
        <div className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-1">
          <MiniSlider
            label="Retrasar"
            value={delay}
            display={delay > 0 ? `+${delay} m` : "—"}
            min={0}
            max={24}
            step={1}
            onChange={(v) => onChange({ delay: v })}
          />
          <MiniSlider
            label="Ritmo"
            value={ritmo}
            display={`${ritmo.toFixed(1)}×`}
            min={0.5}
            max={1.5}
            step={0.1}
            onChange={(v) => onChange({ ritmo_factor: v })}
          />
        </div>
      ) : null}
    </div>
  );
}

function MiniSlider({
  label,
  value,
  display,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  display: string;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  const activo = display !== "—" && display !== "1.0×";
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-[0.72rem] text-muted-foreground">{label}</span>
        <span className={"num text-[0.72rem] font-medium " + (activo ? "text-primary" : "text-muted-foreground")}>{display}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-[var(--primary)]"
      />
    </div>
  );
}

function Kpi({ label, value, delta, hero }: { label: string; value: string; delta?: string; hero?: boolean }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={"num mt-0.5 font-semibold tracking-tight " + (hero ? "text-2xl" : "text-lg")}>{value}</div>
      {delta ? <div className="num text-[0.72rem] text-muted-foreground">{delta}</div> : null}
    </div>
  );
}

type N = number | null | undefined;

function ppDelta(a: N, b: N): string | undefined {
  if (a == null || b == null) return undefined;
  const d = (a - b) * 100;
  if (Math.abs(d) < 0.05) return "= base";
  return `${d >= 0 ? "+" : ""}${d.toFixed(1)} pp vs base`;
}
function copDelta(a: N, b: N): string | undefined {
  if (a == null || b == null) return undefined;
  const d = a - b;
  if (d === 0) return "= base";
  return `${d >= 0 ? "+" : ""}${fmtCop(d)} vs base`;
}
function intDelta(a: N, b: N, suf: string): string | undefined {
  if (a == null || b == null) return undefined;
  const d = a - b;
  if (d === 0) return "= base";
  return `${d >= 0 ? "+" : ""}${fmtInt(d)} ${suf} vs base`;
}
