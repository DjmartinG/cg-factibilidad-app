import { unstable_rethrow } from "next/navigation";
import { ExternalLink } from "lucide-react";
import { getPortfolio, getWacc, getFuentesLive, getFuentesForward, type Wacc, type FuentesLive, type MacroForward } from "@/lib/api";
import { fmtPct } from "@/lib/format";
import { FUENTES, MERCADO_TRM } from "@/lib/fuentes";
import { SourceNote } from "@/components/source-note";
import { EscenariosMacro } from "@/components/views/escenarios-macro";

/** Número crudo (betas): 1.29 → "1.29". null → "—". */
function fmtNum(x: number | null): string {
  return x === null || x === undefined || !isFinite(x) ? "—" : x.toFixed(2);
}

/** TRM en pesos: 3433.71 → "$3.433,71". */
function fmtTrm(x: number): string {
  return `$${x.toLocaleString("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Periodo SDMX "20260626" → "26/06/2026". */
function fmtPeriodo(p: string): string {
  const m = /^(\d{4})(\d{2})(\d{2})$/.exec(p);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : p;
}

export default async function FuentesPage() {
  // La calibración macro es común a todos los proyectos; tomamos el WACC del primero que la tenga.
  let wacc: Wacc | null = null;
  let live: FuentesLive | null = null;
  let errMsg: string | null = null;
  try {
    const data = await getPortfolio();
    for (const it of data.items.slice(0, 5)) {
      const w = await getWacc(it.slug);
      if (w?.disponible) {
        wacc = w;
        break;
      }
    }
  } catch (e) {
    unstable_rethrow(e); // re-lanza el redirect a /login; deja pasar errores reales
    errMsg = e instanceof Error ? e.message : "Error desconocido";
  }
  // Dato VIVO de la fuente (opcional): si el API aún no lo expone (sin redeploy) o la fuente externa
  // no responde, queda en null → la página muestra solo-modelo (degrada limpio).
  try {
    live = await getFuentesLive();
  } catch (e) {
    unstable_rethrow(e);
    live = null;
  }
  // Escenarios macro (abanico forward). null si el API aún no lo expone (sin redeploy) → sección oculta.
  let forward: MacroForward | null = null;
  try {
    forward = await getFuentesForward();
  } catch (e) {
    unstable_rethrow(e);
    forward = null;
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-9 sm:px-6 lg:px-8">
      <header className="mb-7">
        <h1 className="text-lg font-semibold tracking-tight">Fuentes y metodología</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          De dónde salen los datos macroeconómicos que alimentan el costo de capital (WACC), más
          referencias de mercado como la tasa de cambio.
        </p>
      </header>

      <section className="mb-8 rounded-[var(--radius-data)] border bg-card p-5">
        <h2 className="text-sm font-semibold tracking-tight">Cómo se construye el costo de capital</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          El WACC usa el método <strong className="text-foreground">build-up CAPM de Aswath Damodaran</strong> para
          mercados emergentes: CAPM en dólares (tasa libre de riesgo + beta × prima de mercado), más el{" "}
          <strong className="text-foreground">riesgo país</strong> de Colombia, llevado a pesos por{" "}
          <strong className="text-foreground">paridad de inflación</strong> CO/US. La estructura de capital
          (equity/deuda) pondera el costo del equity y el de la deuda.
        </p>
        <p className="mt-3 text-xs text-muted-foreground">
          Los valores de abajo son la <strong className="text-foreground">calibración que usa el modelo</strong>,
          común a todos los proyectos, con corte <strong className="text-foreground">junio 2026</strong>.
        </p>
        {live?.disponible ? (
          <p className="mt-3 rounded-[var(--radius-data)] border border-rule bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            Contraste con el <strong className="text-foreground">dato vivo</strong> de la fuente activado (riesgo
            país y prima de mercado).
            {live.rating ? (
              <> Damodaran tiene hoy a Colombia en <strong className="text-foreground">{live.rating}</strong>.</>
            ) : null}
          </p>
        ) : null}
      </section>

      {errMsg ? <ErrorPanel message={errMsg} /> : null}

      {forward ? <EscenariosMacro data={forward} /> : null}

      <div className="mt-8 mb-3">
        <h2 className="text-sm font-semibold tracking-tight">Calibración del costo de capital (WACC)</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Los valores macro puntuales que usa el modelo, agrupados por fuente.
        </p>
      </div>

      <div className="space-y-5">
        {FUENTES.map((g) => (
          <section key={g.fuente} className="rounded-[var(--radius-data)] border bg-card p-5">
            <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h3 className="text-sm font-semibold tracking-tight">{g.fuente}</h3>
              {g.url ? (
                <a
                  href={g.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary transition-colors [transition-timing-function:var(--ease-out)] hover:underline"
                >
                  Ver fuente <ExternalLink className="size-3" aria-hidden />
                </a>
              ) : (
                <span className="text-xs text-muted-foreground">Definición interna</span>
              )}
            </div>
            <p className="mb-3 text-xs text-muted-foreground">{g.nota}</p>
            <dl className="divide-y divide-[var(--rule)]">
              {g.datos.map((d) => {
                const v = wacc ? d.get(wacc) : null;
                const txt = v === null || v === undefined ? "—" : d.fmt === "pct" ? fmtPct(v) : fmtNum(v);
                const liveV = d.clave && live?.disponible ? live.datos?.[d.clave]?.valor ?? null : null;
                const driftPp = v != null && liveV != null ? (v - liveV) * 100 : null;
                return (
                  <div key={d.nombre} className="flex items-baseline justify-between gap-4 py-2.5">
                    <div className="min-w-0">
                      <dt className="text-sm font-medium text-foreground">{d.nombre}</dt>
                      <dd className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{d.descripcion}</dd>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="num text-sm font-semibold tabular-nums text-foreground">{txt}</div>
                      {liveV != null ? (
                        <div className="num mt-0.5 text-[0.7rem] tabular-nums text-muted-foreground">
                          fuente hoy {fmtPct(liveV)}
                          {driftPp != null ? (
                            Math.abs(driftPp) < 0.05 ? (
                              <span className="ml-1 text-success">· al día</span>
                            ) : (
                              <span className="ml-1 text-cg-amber">
                                · Δ {driftPp >= 0 ? "+" : ""}
                                {driftPp.toFixed(2)} pp
                              </span>
                            )
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </dl>
          </section>
        ))}

        {/* Dato de mercado de REFERENCIA (no entra al WACC): la TRM del dólar, en vivo de Banrep.
            La fuente se documenta SIEMPRE; el valor aparece cuando el API expone el dato vivo. */}
        <section className="rounded-[var(--radius-data)] border bg-card p-5">
          <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h3 className="text-sm font-semibold tracking-tight">{MERCADO_TRM.fuente} · Tasa de cambio</h3>
            <a
              href={MERCADO_TRM.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary transition-colors [transition-timing-function:var(--ease-out)] hover:underline"
            >
              Ver fuente <ExternalLink className="size-3" aria-hidden />
            </a>
          </div>
          <p className="mb-3 text-xs text-muted-foreground">{MERCADO_TRM.nota}</p>
          <dl className="divide-y divide-[var(--rule)]">
            <div className="flex items-baseline justify-between gap-4 py-2.5">
              <div className="min-w-0">
                <dt className="text-sm font-medium text-foreground">{MERCADO_TRM.nombre}</dt>
                <dd className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{MERCADO_TRM.descripcion}</dd>
              </div>
              <div className="shrink-0 text-right">
                <div className="num text-sm font-semibold tabular-nums text-foreground">
                  {live?.trm?.disponible && live.trm.valor != null ? fmtTrm(live.trm.valor) : "—"}
                </div>
                {live?.trm?.disponible && live.trm.periodo ? (
                  <div className="num mt-0.5 text-[0.7rem] tabular-nums text-muted-foreground">
                    al {fmtPeriodo(live.trm.periodo)}
                  </div>
                ) : null}
              </div>
            </div>
          </dl>
        </section>
      </div>

      <div className="mt-8">
        <SourceNote>
          Metodología build-up CAPM (Damodaran, mercado emergente). La calibración (corte jun-2026) está
          auditada en el acta de re-baseline del comité. Los valores que ves son los que el modelo usa para
          calcular el WACC de cada proyecto; todavía no son el dato en vivo de la fuente (eso llega en una
          fase futura).
        </SourceNote>
      </div>
    </div>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="mb-5 rounded-[var(--radius-data)] border border-danger/30 bg-danger/5 p-6">
      <h2 className="font-semibold text-danger">No se pudieron cargar los valores de la calibración</h2>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
      <p className="mt-2 text-sm text-muted-foreground">La metodología y las fuentes siguen disponibles arriba.</p>
    </div>
  );
}
