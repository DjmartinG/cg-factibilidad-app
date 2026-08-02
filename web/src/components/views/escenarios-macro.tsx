"use client";

import { ExternalLink } from "lucide-react";
import type { MacroForward, MacroVariable } from "@/lib/api";
import { fmtPct } from "@/lib/format";
import { MacroFanChart } from "@/components/charts/macro-fan-chart";

/** Valor "hoy" (primer punto) formateado según la unidad de la variable. */
function fmtHoy(v: MacroVariable): string {
  const x = v.puntos[0]?.base;
  if (x == null) return "—";
  return v.unidad === "pct_ea" ? fmtPct(x) : `$${Math.round(x).toLocaleString("es-CO")}`;
}

/** Valor "fin de horizonte" (último punto base). */
function fmtFin(v: MacroVariable): string {
  const x = v.puntos[v.puntos.length - 1]?.base;
  if (x == null) return "—";
  return v.unidad === "pct_ea" ? fmtPct(x) : `$${Math.round(x).toLocaleString("es-CO")}`;
}

const URL_FUENTE: Record<string, string> = {
  inflacion: "https://www.banrep.gov.co/es/estadisticas/inflacion-total-y-meta",
  tasa: "https://www.banrep.gov.co/es/estadisticas/ibr",
  trm: "https://www.banrep.gov.co/es/estadisticas/trm",
};

/** Escenarios macro (abanico forward) — sección de la página Fuentes. Contexto de portafolio: la senda
 *  base se ancla a datos vivos / meta de Banrep y las bandas son escenarios del comité [por validar]. */
export function EscenariosMacro({ data }: { data: MacroForward }) {
  const finAnio = data.anio_inicio + data.horizonte;
  return (
    <section className="mt-8">
      <div className="mb-3">
        <h2 className="text-sm font-semibold tracking-tight">Escenarios macro · bola de cristal</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          El entorno macroeconómico en el que viven los proyectos, proyectado {data.anio_inicio}–{finAnio} como
          un <strong className="text-foreground">cono de incertidumbre</strong>: la senda base (línea) dentro de
          una banda que se ensancha con el tiempo. Cerca hay visibilidad; lejos, no.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {data.variables.map((v) => (
          <div key={v.clave} className="rounded-[var(--radius-data)] border bg-card p-4">
            <div className="mb-1 flex items-start justify-between gap-2">
              <div>
                <h3 className="text-sm font-medium text-foreground">{v.nombre}</h3>
                <div className="mt-0.5 flex items-baseline gap-1.5">
                  <span className="num text-lg font-semibold tracking-tight">{fmtHoy(v)}</span>
                  <span className="text-[0.7rem] text-muted-foreground">hoy → {fmtFin(v)} ({finAnio})</span>
                </div>
              </div>
              {v.anclado ? (
                <span className="shrink-0 rounded-full bg-success/10 px-2 py-0.5 text-[0.65rem] font-medium text-success">
                  dato vivo
                </span>
              ) : (
                <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[0.65rem] font-medium text-muted-foreground">
                  supuesto
                </span>
              )}
            </div>

            <MacroFanChart puntos={v.puntos} unidad={v.unidad} />

            <p className="mt-1.5 text-[0.7rem] leading-relaxed text-muted-foreground">{v.nota}</p>
            <div className="mt-2 flex items-center justify-between gap-2 border-t border-rule pt-2">
              <span className="text-[0.68rem] text-muted-foreground">{v.fuente}</span>
              {URL_FUENTE[v.clave] ? (
                <a
                  href={URL_FUENTE[v.clave]}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-[0.68rem] text-primary transition-colors [transition-timing-function:var(--ease-out)] hover:underline"
                >
                  Fuente <ExternalLink className="size-3" aria-hidden />
                </a>
              ) : null}
            </div>
          </div>
        ))}
      </div>

      <p className="mt-3 text-[0.7rem] leading-relaxed text-muted-foreground">
        <strong className="text-cg-amber">Escenarios, no pronóstico.</strong> La senda base se ancla a datos
        vivos de Banrep (TRM, IBR) o a su meta oficial (inflación 3%); las bandas optimista/pesimista son
        supuestos del comité <em>[por validar]</em>. No alimentan el modelo financiero — son contexto de
        decisión de portafolio.
      </p>
    </section>
  );
}
