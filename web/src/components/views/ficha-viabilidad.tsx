import { Fragment } from "react";
import Link from "next/link";
import { Check, AlertTriangle, Circle, ShieldCheck, ShieldAlert, ShieldX, Pencil } from "lucide-react";
import type { DueDiligence, DueDiligenceItem, Urbanismo, Mercado } from "@/lib/api";
import { fmtPct } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Viabilidad cualitativa — due diligence (B1) + POT (B2) + contraste de mercado (B3). Camacol M1/M3/M4/M5.
 *  Solo presenta lo que el motor agrega; la captura (C2) vive en /proyectos/{slug}/viabilidad (admin). */
export function ViabilidadView({
  dd,
  urb,
  mkt,
  slug,
  isAdmin = false,
}: {
  dd: DueDiligence;
  urb?: Urbanismo | null;
  mkt?: Mercado | null;
  slug?: string;
  isAdmin?: boolean;
}) {
  const v = dd.veredicto;
  return (
    <div className="space-y-5">
      {isAdmin && slug ? (
        <div className="flex justify-end">
          <Link
            href={`/proyectos/${slug}/viabilidad`}
            className="inline-flex items-center gap-1.5 rounded-[var(--radius-data)] border border-primary/40 px-3 py-1.5 text-sm font-medium text-primary transition-[color,background-color,transform] [transition-timing-function:var(--ease-out)] hover:bg-primary/10 active:scale-[0.98]"
          >
            <Pencil className="size-3.5" aria-hidden /> Editar viabilidad
          </Link>
        </div>
      ) : null}
      <VeredictoBanner nivel={v.nivel} n_items={v.n_items} n_ok={v.n_ok} n_alertas={v.n_alertas} n_pendientes={v.n_pendientes} />

      <RiskMatrix items={dd.items} resumen={dd.severidad_resumen} />

      <div className="grid gap-4 md:grid-cols-2">
        {dd.frentes.map((f) => {
          const items = dd.items.filter((i) => i.frente === f.clave);
          if (items.length === 0) return null;
          return (
            <div key={f.clave} className="rounded-[var(--radius-data)] border bg-card p-4">
              <div className="mb-3 text-sm font-medium text-foreground">{f.nombre}</div>
              <div className="space-y-2.5">
                {items.map((it) => (
                  <ItemRow key={`${it.frente}-${it.item}`} it={it} />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {urb ? <UrbanismoSection urb={urb} /> : null}
      {mkt ? <MercadoSection mkt={mkt} /> : null}

      <p className="text-[0.7rem] text-muted-foreground">
        Due diligence del prefacto (curso Camacol · legal, ambiental/ESG, urbanístico, técnico y bancario).
        El veredicto cualitativo <strong>acompaña</strong> al financiero: rojo = riesgo de impacto alto sin
        mitigar; ámbar = due diligence en proceso; verde = sin riesgos abiertos. La captura de estados se
        hace en el Ingreso de datos; los ítems sin diligenciar aparecen como <em>pendiente</em>.
      </p>
    </div>
  );
}

function VeredictoBanner({
  nivel,
  n_items,
  n_ok,
  n_alertas,
  n_pendientes,
}: {
  nivel: string;
  n_items: number;
  n_ok: number;
  n_alertas: number;
  n_pendientes: number;
}) {
  const map: Record<string, { txt: string; cls: string; Icon: typeof ShieldCheck }> = {
    verde: { txt: "Viabilidad cualitativa: sin riesgos abiertos", cls: "bg-success/10 text-success", Icon: ShieldCheck },
    ambar: {
      txt: "Viabilidad cualitativa: due diligence en proceso",
      cls: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
      Icon: ShieldAlert,
    },
    rojo: { txt: "Viabilidad cualitativa: riesgo alto sin mitigar", cls: "bg-danger/10 text-danger", Icon: ShieldX },
  };
  const f = map[nivel] ?? map.ambar;
  const Icon = f.Icon;
  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-1 rounded-[var(--radius-data)] px-4 py-3", f.cls)}>
      <span className="inline-flex items-center gap-2 text-sm font-semibold">
        <Icon className="size-4" aria-hidden /> {f.txt}
      </span>
      <span className="num text-xs opacity-80">
        {n_items} ítems · {n_ok} ok · {n_alertas} alertas · {n_pendientes} pendientes
      </span>
    </div>
  );
}

function ItemRow({ it }: { it: DueDiligenceItem }) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <EstadoBadge estado={it.estado} />
          <span className="truncate">{it.item}</span>
        </div>
        {it.mitigacion || it.nota ? (
          <div className="mt-0.5 text-[0.7rem] text-muted-foreground">{it.mitigacion || it.nota}</div>
        ) : null}
      </div>
      <ImpactoChip impacto={it.impacto} />
    </div>
  );
}

function EstadoBadge({ estado }: { estado: string }) {
  const map: Record<string, { cls: string; Icon: typeof Check; label: string }> = {
    ok: { cls: "bg-success/10 text-success", Icon: Check, label: "OK" },
    alerta: { cls: "bg-danger/10 text-danger", Icon: AlertTriangle, label: "Alerta" },
    pendiente: { cls: "bg-muted text-muted-foreground", Icon: Circle, label: "Pendiente" },
  };
  const f = map[estado] ?? map.pendiente;
  const Icon = f.Icon;
  return (
    <span className={cn("inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[0.7rem] font-medium", f.cls)}>
      <Icon className="size-3" aria-hidden /> {f.label}
    </span>
  );
}

function ImpactoChip({ impacto }: { impacto: string }) {
  // impacto NO es un estado: chip neutro (alto en tono de marca ámbar, sin usar el rojo semántico).
  const cls =
    impacto === "alto"
      ? "text-amber-700 dark:text-amber-300"
      : impacto === "medio"
        ? "text-muted-foreground"
        : "text-muted-foreground/70";
  return <span className={cn("shrink-0 text-[0.7rem] tabular-nums", cls)}>impacto {impacto}</span>;
}

/* ── Matriz de riesgos (probabilidad × impacto) ─────────────────────────────────
   Severidad = celda de la matriz; verde/ámbar/rojo son legítimos aquí (severidad ES un estado).
   Solo se ubican los riesgos ABIERTOS (estado != ok): son los que exigen gestión. */
const PROBS = ["alta", "media", "baja"] as const; // eje Y (arriba → abajo)
const IMPS = ["bajo", "medio", "alto"] as const; // eje X (izq → der)
const PESO_PROB: Record<string, number> = { alta: 3, media: 2, baja: 1 };
const PESO_IMP: Record<string, number> = { alto: 3, medio: 2, bajo: 1 };

function severidadDe(prob: string, imp: string): "alto" | "medio" | "bajo" {
  const s = (PESO_PROB[prob] ?? 2) * (PESO_IMP[imp] ?? 2);
  return s >= 6 ? "alto" : s >= 3 ? "medio" : "bajo";
}

const SEV_CELL: Record<string, string> = {
  alto: "bg-danger/10 border-danger/25",
  medio: "bg-cg-amber/12 border-cg-amber/25",
  bajo: "bg-success/10 border-success/20",
};
const SEV_DOT: Record<string, string> = {
  alto: "bg-danger text-[oklch(0.99_0.005_196)]",
  medio: "bg-cg-amber text-[oklch(0.2_0.03_200)]",
  bajo: "bg-success text-[oklch(0.99_0.005_196)]",
};

function RiskMatrix({ items, resumen }: { items: DueDiligenceItem[]; resumen?: { alto: number; medio: number; bajo: number } | null }) {
  const orden: Record<string, number> = { alto: 0, medio: 1, bajo: 2 };
  // Solo riesgos CALIFICADOS por el analista y abiertos: la plantilla sin revisar no puebla la matriz.
  const abiertos = items
    .filter((i) => i.estado !== "ok" && i.del_analista)
    .sort((a, b) => (orden[a.severidad ?? "medio"] ?? 1) - (orden[b.severidad ?? "medio"] ?? 1));
  if (abiertos.length === 0) return null;

  // Numera cada riesgo (por severidad desc) para mapear el punto de la celda con la leyenda.
  const num = new Map(abiertos.map((it, i) => [it, i + 1]));
  const sev = resumen ?? { alto: 0, medio: 0, bajo: 0 };

  return (
    <div className="rounded-[var(--radius-data)] border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="text-sm font-medium text-foreground">Matriz de riesgos · probabilidad × impacto</div>
        <div className="flex items-center gap-3 text-[0.7rem] text-muted-foreground">
          <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-danger" />{sev.alto} alto</span>
          <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-cg-amber" />{sev.medio} medio</span>
          <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-success" />{sev.bajo} bajo</span>
          <span className="tabular-nums">· {abiertos.length} abiertos</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <div className="flex gap-2">
          {/* eje Y */}
          <div className="flex flex-col justify-around pb-6 pr-1 text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">
            <span className="[writing-mode:vertical-rl] rotate-180 self-center py-2">Probabilidad</span>
          </div>
          <div className="min-w-[360px] flex-1">
            <div className="grid grid-cols-[auto_repeat(3,1fr)] gap-1">
              {PROBS.map((p) => (
                <Fragment key={p}>
                  <div className="flex w-9 items-center justify-end pr-1.5 text-[0.65rem] capitalize text-muted-foreground">{p}</div>
                  {IMPS.map((im) => {
                    const s = severidadDe(p, im);
                    const enCelda = abiertos.filter((it) => (it.probabilidad ?? "media") === p && it.impacto === im);
                    return (
                      <div key={`${p}-${im}`} className={cn("relative flex min-h-[58px] flex-wrap content-start gap-1 rounded-[var(--radius-data)] border p-1.5", SEV_CELL[s])}>
                        {enCelda.map((it) => (
                          <span key={`${it.frente}-${it.item}`} className="group/dot relative">
                            <span className={cn("flex size-5 cursor-default items-center justify-center rounded-full text-[0.6rem] font-bold tabular-nums shadow-[var(--shadow-card)]", SEV_DOT[s])}>
                              {num.get(it)}
                            </span>
                            <span className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded-[var(--radius-data)] border bg-popover px-2 py-1 text-[0.7rem] text-popover-foreground shadow-[var(--shadow-card)] group-hover/dot:block">
                              {it.item}
                            </span>
                          </span>
                        ))}
                      </div>
                    );
                  })}
                </Fragment>
              ))}
              {/* eje X */}
              <div />
              {IMPS.map((im) => (
                <div key={im} className="pt-1 text-center text-[0.65rem] font-medium capitalize text-muted-foreground">{im}</div>
              ))}
            </div>
            <div className="mt-1.5 text-center text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">Impacto</div>
          </div>
        </div>
      </div>

      {/* Leyenda numerada: los riesgos abiertos ordenados por severidad */}
      <ol className="mt-4 space-y-1.5 border-t border-rule pt-3">
        {abiertos.map((it) => (
          <li key={`${it.frente}-${it.item}`} className="flex items-start gap-2.5 text-sm">
            <span className={cn("mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full text-[0.6rem] font-bold tabular-nums", SEV_DOT[it.severidad ?? "medio"])}>
              {num.get(it)}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-medium">{it.item}</span>
                <span className="text-[0.7rem] tabular-nums text-muted-foreground">
                  prob. {it.probabilidad ?? "media"} · impacto {it.impacto}
                </span>
              </div>
              {it.mitigacion ? <div className="text-[0.72rem] text-muted-foreground">{it.mitigacion}</div> : null}
            </div>
            <EstadoBadge estado={it.estado} />
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Cumplimiento urbanístico (POT) — índices calculados vs límites del POT (B2). */
function UrbanismoSection({ urb }: { urb: Urbanismo }) {
  const nivel = urb.veredicto.nivel;
  const map: Record<string, { txt: string; cls: string }> = {
    cumple: { txt: "Cumple el POT", cls: "bg-success/10 text-success" },
    al_limite: { txt: "Al límite del POT", cls: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300" },
    excede: { txt: "Excede el POT", cls: "bg-danger/10 text-danger" },
    sin_pot: { txt: "Sin límites POT capturados", cls: "bg-muted text-muted-foreground" },
  };
  const f = map[nivel] ?? map.sin_pot;
  const fmt = (n: number) => (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(2));
  return (
    <div className="rounded-[var(--radius-data)] border bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">Cumplimiento urbanístico (POT)</div>
        <span className={cn("rounded-full px-2 py-0.5 text-[0.7rem] font-medium", f.cls)}>{f.txt}</span>
      </div>
      {urb.disponible ? (
        <div className="space-y-1.5">
          <div className="flex items-center gap-3 text-[0.7rem] uppercase tracking-wide text-muted-foreground">
            <span className="flex-1">Indicador</span>
            <span className="num w-16 text-right">Real</span>
            <span className="num w-16 text-right">Máx POT</span>
            <span className="num w-12 text-right">Uso</span>
          </div>
          {urb.items.map((it) => (
            <div key={it.concepto} className="flex items-center gap-3 text-sm">
              <span className="flex-1 text-muted-foreground">{it.concepto}</span>
              <span className="num w-16 text-right tabular-nums">{fmt(it.real)}</span>
              <span className="num w-16 text-right tabular-nums text-muted-foreground">{fmt(it.limite)}</span>
              <span
                className={cn(
                  "num w-12 text-right tabular-nums",
                  !it.cumple ? "text-danger" : it.uso_pct != null && it.uso_pct >= 0.9 ? "text-amber-700 dark:text-amber-300" : "text-success",
                )}
              >
                {it.uso_pct != null ? fmtPct(it.uso_pct, 0) : "—"}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Captura los límites del POT de la zona (índice de construcción, densidad, aprovechamiento) para
          verificar el cumplimiento.
        </p>
      )}
      {Object.keys(urb.referencia).length > 0 ? (
        <p className="mt-2 text-[0.7rem] text-muted-foreground">
          Referencia POT (no comparable por el motor):{" "}
          {Object.entries(urb.referencia).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ")}
        </p>
      ) : null}
    </div>
  );
}

/** Contraste de mercado — supuestos del proyecto (precio, ritmo) vs comparables de la zona (B3). */
function MercadoSection({ mkt }: { mkt: Mercado }) {
  const nivel = mkt.veredicto.nivel;
  const map: Record<string, { txt: string; cls: string }> = {
    en_mercado: { txt: "Supuestos en línea con el mercado", cls: "bg-success/10 text-success" },
    revisar: { txt: "Supuestos a revisar vs mercado", cls: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300" },
    sin_datos: { txt: "Sin comparables de mercado", cls: "bg-muted text-muted-foreground" },
  };
  const f = map[nivel] ?? map.sin_datos;
  // precio en millones COP/m²; ritmo en und/mes (1 decimal).
  const fmtVal = (v: number, sentido: string) => (sentido === "precio" ? `$${(v / 1_000_000).toFixed(2)}M` : v.toFixed(1));
  const hint = (sentido: string, desv: number, estado: string) => {
    if (estado === "ok") return sentido === "ritmo" && desv < 0 ? "conservador" : "en mercado";
    if (sentido === "precio") return desv > 0 ? "sobre el comparable (riesgo de venta lenta)" : "bajo el comparable (valor en la mesa)";
    return "más rápido que la absorción de la zona (optimista)";
  };
  return (
    <div className="rounded-[var(--radius-data)] border bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">Contraste de mercado</div>
        <span className={cn("rounded-full px-2 py-0.5 text-[0.7rem] font-medium", f.cls)}>{f.txt}</span>
      </div>
      {mkt.disponible ? (
        <div className="space-y-1.5">
          <div className="flex items-center gap-3 text-[0.7rem] uppercase tracking-wide text-muted-foreground">
            <span className="flex-1">Supuesto</span>
            <span className="num w-20 text-right">Proyecto</span>
            <span className="num w-20 text-right">Mercado</span>
            <span className="num w-16 text-right">Desv.</span>
          </div>
          {mkt.items.map((it) => (
            <div key={it.dimension} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-sm">
              <span className="flex-1 text-muted-foreground">{it.dimension}</span>
              <span className="num w-20 text-right tabular-nums">{fmtVal(it.proyecto, it.sentido)}</span>
              <span className="num w-20 text-right tabular-nums text-muted-foreground">{fmtVal(it.mercado, it.sentido)}</span>
              <span
                className={cn(
                  "num w-16 text-right tabular-nums",
                  it.estado === "alerta" ? "text-amber-700 dark:text-amber-300" : "text-success",
                )}
              >
                {it.desviacion > 0 ? "+" : ""}{fmtPct(it.desviacion, 0)}
              </span>
              <span className="w-full text-right text-[0.7rem] text-muted-foreground">{hint(it.sentido, it.desviacion, it.estado)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Captura los comparables de la zona (precio /m² de la competencia, absorción esperada) para
          contrastar el precio y el ritmo de ventas del proyecto.
        </p>
      )}
      {Object.keys(mkt.referencia).length > 0 ? (
        <p className="mt-2 text-[0.7rem] text-muted-foreground">
          Contexto de mercado:{" "}
          {Object.entries(mkt.referencia).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ")}
        </p>
      ) : null}
    </div>
  );
}
