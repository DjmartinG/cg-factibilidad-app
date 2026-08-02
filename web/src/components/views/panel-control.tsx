"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import type { Recalc, GoalSeek } from "@/lib/api";
import { recalcular, resolverMeta } from "@/lib/actions";
import { fmtPct, fmtCop } from "@/lib/format";
import { Banner } from "@/components/banner";

/** Valores base de los drivers en UNIDADES REALES (no %). Se calculan en la ficha desde lo que ya
 *  carga (ventas, costo directo, unidades, área, absorción). null → ese driver cae a modo % (fallback). */
export type SimBase = {
  precio_und: number | null;      // precio promedio por unidad (miles COP, como el P&G)
  costo_m2: number | null;        // costo directo por m² construido (miles COP)
  ritmo_und_mes: number | null;   // ritmo de ventas promedio (unidades/mes)
};

type DriverKey = "precio" | "costo" | "ritmo";
type DriverCfg = {
  key: DriverKey;
  label: string;
  base: number | null;      // valor base en unidad real (null → modo %)
  step: number;             // paso del slider en la unidad real
  rango: number;            // ± alrededor de la base
  monetario: boolean;       // true → COP (se muestra en millones); false → und/mes
  sufijo: string;           // "" | "/m²" | " und/mes"
};

/** Formatea un valor de driver en su unidad real. Monetario → millones COP; ritmo → und/mes. */
function fmtDriver(cfg: DriverCfg, valorMiles: number): string {
  if (cfg.monetario) {
    const mm = valorMiles / 1000; // miles COP → millones COP
    return `$${mm.toLocaleString("es-CO", { maximumFractionDigits: mm >= 100 ? 0 : 1 })}M${cfg.sufijo}`;
  }
  return `${Math.round(valorMiles)}${cfg.sufijo}`;
}

/** Construye la config de los 3 drivers a partir de las bases (o modo % si falta la base). */
function driversDe(base: SimBase): DriverCfg[] {
  return [
    { key: "precio", label: "Precio de venta", base: base.precio_und, step: 5_000, rango: 60_000, monetario: true, sufijo: "" },
    { key: "costo", label: "Costo directo", base: base.costo_m2, step: 100, rango: 600, monetario: true, sufijo: "/m²" },
    { key: "ritmo", label: "Ritmo de ventas", base: base.ritmo_und_mes, step: 1, rango: 15, monetario: false, sufijo: " und/mes" },
  ];
}

export function PanelControl({ slug, simBase }: { slug: string; simBase: SimBase }) {
  const [precio, setPrecio] = useState(0);
  const [costo, setCosto] = useState(0);
  const [ritmo, setRitmo] = useState(0);
  const [data, setData] = useState<Recalc | null>(null);
  const [pending, start] = useTransition();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const drivers = driversDe(simBase);
  const frac: Record<DriverKey, number> = { precio, costo, ritmo };
  const setFrac: Record<DriverKey, (n: number) => void> = { precio: setPrecio, costo: setCosto, ritmo: setRitmo };

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      start(async () => {
        try {
          setData(await recalcular(slug, { precio, costo, ritmo }));
        } catch {
          /* silencioso: el panel queda con el último valor bueno */
        }
      });
    }, 220);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [precio, costo, ritmo, slug]);

  const r = data?.resultado;
  const b = data?.base;
  const tocado = precio !== 0 || costo !== 0 || ritmo !== 0;

  return (
    <div className="space-y-7">
      <Banner tone="warning" label="Simulador">
        Mueve los drivers en sus <span className="font-medium">unidades reales</span> para ver el impacto. El{" "}
        <span className="font-medium">margen es exacto</span>; la TIR y el VPN son{" "}
        <span className="font-medium">simulados</span> (base mensual, sirven para comparar) — la cifra oficial
        está en la pestaña Resumen.
      </Banner>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.15fr]">
        {/* Drivers */}
        <div className="space-y-5 rounded-[var(--radius-data)] border bg-card p-5">
          <div className="flex items-baseline justify-between">
            <h3 className="text-sm font-semibold">Drivers</h3>
            {tocado ? (
              <button
                type="button"
                onClick={() => { setPrecio(0); setCosto(0); setRitmo(0); }}
                className="text-xs text-muted-foreground underline-offset-2 hover:underline"
              >
                Restablecer
              </button>
            ) : null}
          </div>
          {drivers.map((cfg) => (
            <Driver key={cfg.key} cfg={cfg} frac={frac[cfg.key]} onFrac={setFrac[cfg.key]} />
          ))}
        </div>

        {/* KPIs en vivo */}
        <div className={"grid grid-cols-2 gap-x-6 gap-y-5 rounded-[var(--radius-data)] border bg-card p-5 transition-opacity " + (pending ? "opacity-60" : "")}>
          <Kpi label="Margen" hero value={fmtPct(r?.margen)} delta={pctDelta(r?.margen, b?.margen)} />
          <Kpi label="TIR proyecto · sim." value={fmtPct(r?.tir_proyecto)} delta={pctDelta(r?.tir_proyecto, b?.tir_proyecto)} />
          <Kpi label="TIR socio · sim." value={fmtPct(r?.tir_equity)} delta={pctDelta(r?.tir_equity, b?.tir_equity)} />
          <Kpi label="VPN proyecto · sim." value={fmtCop(r?.vpn_proyecto)} delta={copDelta(r?.vpn_proyecto, b?.vpn_proyecto)} />
          <Kpi label="Exposición máx." value={fmtCop(r?.exposicion_maxima)} delta={copDelta(r?.exposicion_maxima, b?.exposicion_maxima)} />
          <Kpi label="Punto de equilibrio" value={r ? `mes ${r.breakeven_mes}` : "—"} delta={mesDelta(r?.breakeven_mes, b?.breakeven_mes)} />
        </div>
      </div>

      <GoalSeekPanel slug={slug} simBase={simBase} />
    </div>
  );
}

/** Un driver: slider en unidad real (si hay base) o en % (fallback). Guarda el estado como FRACCIÓN
 *  (lo que espera el motor); en modo real, mapea valor↔fracción con la base. */
function Driver({ cfg, frac, onFrac }: { cfg: DriverCfg; frac: number; onFrac: (n: number) => void }) {
  const real = cfg.base != null && isFinite(cfg.base) && cfg.base > 0;

  if (!real) {
    // Fallback %: sin base disponible, se comporta como antes.
    return (
      <div>
        <div className="mb-1 flex items-baseline justify-between">
          <span className="text-sm">{cfg.label}</span>
          <span className={"num text-sm font-medium " + tono(frac)}>
            {frac > 0 ? "+" : ""}{(frac * 100).toFixed(0)}%
          </span>
        </div>
        <input
          type="range" min={-0.3} max={0.3} step={0.01} value={frac}
          onChange={(e) => onFrac(parseFloat(e.target.value))}
          className="w-full accent-[var(--primary)]"
        />
      </div>
    );
  }

  const base = cfg.base as number;
  const valor = base * (1 + frac);
  const min = Math.max(base - cfg.rango, cfg.step);
  const max = base + cfg.rango;

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-sm">{cfg.label}</span>
        <span className="flex items-baseline gap-2">
          <span className="num text-sm font-semibold text-foreground">{fmtDriver(cfg, valor)}</span>
          {frac !== 0 ? (
            <span className={"num text-[0.72rem] font-medium " + tono(frac)}>
              {frac > 0 ? "+" : ""}{fmtDriver(cfg, valor - base)}
            </span>
          ) : null}
        </span>
      </div>
      <input
        type="range" min={min} max={max} step={cfg.step} value={valor}
        onChange={(e) => onFrac(parseFloat(e.target.value) / base - 1)}
        className="w-full accent-[var(--primary)]"
      />
      <div className="mt-0.5 flex justify-between text-[0.65rem] text-muted-foreground">
        <span className="num">{fmtDriver(cfg, min)}</span>
        <span>base <span className="num">{fmtDriver(cfg, base)}</span></span>
        <span className="num">{fmtDriver(cfg, max)}</span>
      </div>
    </div>
  );
}

function tono(v: number): string {
  return v > 0 ? "text-primary" : v < 0 ? "text-[var(--cg-amber)]" : "text-muted-foreground";
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

function pctDelta(a?: number | null, base?: number | null): string | undefined {
  if (a == null || base == null) return undefined;
  const d = (a - base) * 100;
  return `${d >= 0 ? "+" : ""}${d.toFixed(1)} pp vs base`;
}
function copDelta(a?: number | null, base?: number | null): string | undefined {
  if (a == null || base == null) return undefined;
  const d = a - base;
  return `${d >= 0 ? "+" : ""}${fmtCop(d)} vs base`;
}
function mesDelta(a?: number | null, base?: number | null): string | undefined {
  if (a == null || base == null || a === base) return undefined;
  const d = a - base;
  return `${d >= 0 ? "+" : ""}${d} m vs base`;
}

// ---------- Goal-seek ("devolvernos") ----------

type ObjCfg = { key: string; label: string; unidad: string; factor: number; fmt: (v: number) => string; hint: string };

const OBJETIVOS: ObjCfg[] = [
  { key: "margen", label: "Margen", unidad: "%", factor: 0.01, fmt: (v) => fmtPct(v), hint: "8" },
  { key: "tir_proyecto", label: "TIR proyecto", unidad: "%", factor: 0.01, fmt: (v) => fmtPct(v), hint: "30" },
  { key: "tir_equity", label: "TIR socio", unidad: "%", factor: 0.01, fmt: (v) => fmtPct(v), hint: "25" },
  { key: "vpn_proyecto", label: "VPN proyecto", unidad: "mil M", factor: 1_000_000, fmt: (v) => fmtCop(v), hint: "20" },
  { key: "exposicion_maxima", label: "Exposición máx.", unidad: "mil M", factor: 1_000_000, fmt: (v) => fmtCop(v), hint: "-90" },
  { key: "breakeven_mes", label: "Punto de equilibrio", unidad: "mes", factor: 1, fmt: (v) => `mes ${Math.round(v)}`, hint: "60" },
];

function driverCfgDe(key: string, simBase: SimBase): DriverCfg {
  return driversDe(simBase).find((d) => d.key === key)!;
}

function GoalSeekPanel({ slug, simBase }: { slug: string; simBase: SimBase }) {
  const [objetivo, setObjetivo] = useState<string>("margen");
  const [metaInput, setMetaInput] = useState<string>("8");
  const [res, setRes] = useState<GoalSeek | null>(null);
  const [resObj, setResObj] = useState<ObjCfg | null>(null);
  const [pending, start] = useTransition();
  const [err, setErr] = useState<string | null>(null);

  const obj = OBJETIVOS.find((o) => o.key === objetivo)!;

  function cambiarObjetivo(k: string) {
    setObjetivo(k);
    setMetaInput(OBJETIVOS.find((o) => o.key === k)!.hint);
    setRes(null);
    setErr(null);
  }

  function resolver() {
    setErr(null);
    const meta = parseFloat(metaInput) * obj.factor;
    if (!isFinite(meta)) { setErr("Meta inválida"); return; }
    start(async () => {
      try {
        setRes(await resolverMeta(slug, objetivo, meta));
        setResObj(obj);
      } catch {
        setErr("No se pudo resolver. Intenta otra meta.");
      }
    });
  }

  // valor base del objetivo (viene igual en cualquier driver del resultado)
  const valorBase = res ? Object.values(res).find((d) => d.valor_base != null)?.valor_base ?? null : null;

  return (
    <section className="rounded-[var(--radius-data)] border bg-card p-5">
      <h3 className="text-sm font-semibold">Devolverme a una meta (goal-seek)</h3>
      <p className="mb-3 mt-0.5 text-sm text-muted-foreground">
        Fija una meta sobre un indicador y el motor calcula, <strong>por cada driver</strong>, a qué valor
        habría que llevarlo para alcanzarla.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-xs text-muted-foreground">Objetivo</span>
          <select
            value={objetivo}
            onChange={(e) => cambiarObjetivo(e.target.value)}
            className="rounded-[var(--radius-data)] border bg-background px-2 py-1.5 text-sm"
          >
            {OBJETIVOS.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-xs text-muted-foreground">Meta ({obj.unidad})</span>
          <input
            type="number" value={metaInput} onChange={(e) => setMetaInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") resolver(); }}
            className="num w-28 rounded-[var(--radius-data)] border bg-background px-2 py-1.5 text-sm"
          />
        </label>
        <button
          type="button" onClick={resolver} disabled={pending}
          className="rounded-[var(--radius-data)] bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground transition-[opacity,transform] [transition-timing-function:var(--ease-out)] hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
        >
          {pending ? "Resolviendo…" : "Resolver"}
        </button>
      </div>

      {err ? <p className="mt-3 text-sm text-[var(--cg-amber)]">{err}</p> : null}

      {res && resObj ? (
        <div className="mt-4">
          <p className="mb-2 text-sm text-muted-foreground">
            {resObj.label}
            {valorBase != null ? <> hoy <span className="num text-foreground/80">{resObj.fmt(valorBase)}</span></> : null}
            {" → meta "}
            <span className="num text-foreground/80">{resObj.fmt(parseFloat(metaInput) * resObj.factor)}</span>. Moviendo un solo driver:
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            {Object.entries(res).map(([driver, d]) => (
              <DriverResultado key={driver} driver={driver} d={d} simBase={simBase} />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function DriverResultado({
  driver,
  d,
  simBase,
}: {
  driver: string;
  d: GoalSeek[string];
  simBase: SimBase;
}) {
  const cfg = driverCfgDe(driver, simBase);
  const real = cfg.base != null && isFinite(cfg.base) && cfg.base > 0 && d.delta !== undefined;

  return (
    <div className="rounded-[var(--radius-data)] border p-3">
      <div className="text-xs font-medium text-muted-foreground">{cfg.label}</div>
      {!d.alcanzable || d.delta === undefined ? (
        <div className="mt-1 text-sm text-muted-foreground">no alcanzable en ±50%</div>
      ) : real ? (
        <>
          <div className="num mt-1 text-lg font-semibold tracking-tight">
            {fmtDriver(cfg, (cfg.base as number) * (1 + d.delta))}
          </div>
          <div className="num text-[0.72rem] text-muted-foreground">
            de {fmtDriver(cfg, cfg.base as number)}{" "}
            <span className={tono(d.delta)}>
              ({d.delta >= 0 ? "+" : ""}{fmtDriver(cfg, (cfg.base as number) * d.delta)})
            </span>
          </div>
        </>
      ) : (
        <div className="num mt-1 text-lg font-semibold tracking-tight">
          {d.delta >= 0 ? "+" : ""}{(d.delta * 100).toFixed(1)}%
        </div>
      )}
    </div>
  );
}
