import type { ProjectDetail, Pyg, Results, Urbanistico } from "@/lib/api";
import { fmtCop, fmtInt, fmtPct, splitCop, splitPct, splitTir, splitTirSocio, tirEsDegenerada, tirSocioVacia } from "@/lib/format";
import { StatPanel, type StatItem } from "@/components/stat";
import { Figure } from "@/components/figure";
import { ValorBanner } from "@/components/valor-banner";
import { ChecksBadge } from "@/components/checks-badge";
import { SectionTitle } from "@/components/section-title";
import { MiniStat } from "@/components/mini-stat";
import { PygWaterfall } from "@/components/charts/pyg-waterfall";

/** "TIR proyecto · proyecto (desapalancada)" → ["TIR proyecto", "proyecto (desapalancada)"]. */
function splitLabel(s: string): [string, string] {
  const i = s.indexOf(" · ");
  return i >= 0 ? [s.slice(0, i), s.slice(i + 3)] : [s, ""];
}

/** TIR real (precios constantes); greenfield/None → "— greenfield" (jamás −99%). */
function realTir(v: number | null | undefined): string {
  return v == null ? "— greenfield" : fmtPct(v);
}

/** TIR real del SOCIO; vacía → distingue greenfield vs sin aporte de capital (según la TIR del proyecto). */
function realTirSocio(v: number | null | undefined, tirProyecto: number | null | undefined): string {
  return v == null ? `— ${tirSocioVacia(tirProyecto)}` : fmtPct(v);
}

/** TIR (después de imp.); greenfield/degenerada → "— greenfield" (jamás −99%). */
function tirAt(v: number | null | undefined): string {
  return v == null || tirEsDegenerada(v) ? "— greenfield" : fmtPct(v);
}

/** TIR del SOCIO (después de imp.); vacía → distingue greenfield vs sin aporte de capital. */
function tirAtSocio(v: number | null | undefined, tirProyecto: number | null | undefined): string {
  return v == null || tirEsDegenerada(v) ? `— ${tirSocioVacia(tirProyecto)}` : fmtPct(v);
}

export function FichaResumen({ project, results }: { project: ProjectDetail; results: Results }) {
  const ind = results.indicadores;
  const pyg = results.pyg;
  const [tpL, tpB] = splitLabel(ind.tir_proyecto_label);
  const [tsL, tsB] = splitLabel(ind.tir_socio_label);

  const stats: StatItem[] = [
    { label: tpL, parts: splitTir(ind.tir_proyecto), base: tpB || "desapalancada", emphasis: true },
    { label: tsL, parts: splitTirSocio(ind.tir_socio, ind.tir_proyecto), base: tsB || "apalancada" },
    {
      label: ind.vpn_label || "VPN @TIO",
      parts: splitCop(ind.vpn_proyecto),
      base: "sobre la TIO",
      state: ind.vpn_proyecto != null && ind.vpn_proyecto < 0 ? "negative" : "positive",
    },
    { label: "Margen oper.", parts: splitPct(ind.margen_oper), base: "sobre ventas" },
  ];

  const okAll = results.checks.every((c) => c.ok);

  return (
    <div>
      <StatPanel items={stats} />

      {/* Precios constantes (real): TIR deflactada por inflación (Fisher) — curso Camacol §M6.
          Degrada limpio si el API aún no expone `inflacion`. */}
      {ind.inflacion != null ? (
        <p className="mt-2 text-[0.7rem] text-muted-foreground">
          Precios constantes (real · deflactado por inflación {fmtPct(ind.inflacion)}):{" "}
          TIR proyecto <span className="num text-foreground/80">{realTir(ind.tir_proyecto_real)}</span> ·{" "}
          TIR socio <span className="num text-foreground/80">{realTirSocio(ind.tir_socio_real, ind.tir_proyecto)}</span>
        </p>
      ) : null}

      {/* Impacto tributario (after-tax · preliminar) — C1 (Camacol M4/M6). Lente adicional; la cifra
          oficial sigue siendo la pre-impuesto. Degrada limpio si el API aún no expone `after_tax_metodo`. */}
      {ind.after_tax_metodo ? (
        <div className="mt-4 rounded-[var(--radius-data)] border border-dashed bg-card p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-foreground">Impacto tributario (después de imp.)</span>
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[0.7rem] font-medium text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
              preliminar · pendiente asesor
            </span>
          </div>
          <div className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-4">
            <MiniStat label="TIR proyecto desp. imp." value={tirAt(ind.tir_proyecto_at)} note="modelo mensual" />
            <MiniStat label="TIR socio desp. imp." value={tirAtSocio(ind.tir_socio_at, ind.tir_proyecto)} note="modelo mensual" />
            {ind.iva_vis_devolucion ? (
              <MiniStat label="Devolución IVA VIS" value={`+${fmtCop(ind.iva_vis_devolucion)}`} note="3,8% · entrada" />
            ) : null}
            {ind.carga_tributaria_neta_at != null ? (
              <MiniStat label="Carga tributaria neta" value={fmtCop(ind.carga_tributaria_neta_at)} note="renta + GMF − IVA" />
            ) : null}
          </div>
          <p className="mt-2 text-[0.7rem] text-muted-foreground">
            Renta (exención VIS sobre utilidad; honorarios gravados) + GMF − devolución de IVA VIS, sobre el
            modelo mensual. <strong>No</strong> incluye retención (anticipo de renta, no costo) ni ICA. Tasas{" "}
            <em>preliminares, pendientes de ratificación del asesor fiscal</em>; la cifra oficial sigue siendo
            la pre-impuesto.
          </p>
        </div>
      ) : null}

      {/* Veredicto de Valor (EVA): ¿genera o destruye valor sobre el WACC? — junto al héroe.
          Solo si el API ya expone EVA (campo `valor_metodo`): así degrada limpio si el API está atrás. */}
      {ind.valor_metodo ? (
        <div className="mt-6">
          <ValorBanner
            creaValor={ind.crea_valor}
            spread={ind.spread_valor}
            valorCreado={ind.valor_creado}
            metodo={ind.valor_metodo}
          />
        </div>
      ) : null}

      {/* P&G — el lienzo central de la decisión (M7) */}
      <section className="mt-8">
        <SectionTitle
          right={`margen ${fmtPct(ind.margen_oper)}`}
          subtitle="De ingresos a utilidad neta. Honorarios y utilidad del lote retornan al desarrollador."
        >
          Estado de resultados (P&amp;G)
        </SectionTitle>
        <div className="mb-4 rounded-[var(--radius-data)] border bg-card p-4">
          <div className="mb-1 text-xs text-muted-foreground">
            De ingresos a utilidad neta · valores en mil M COP
          </div>
          <PygWaterfall pyg={pyg} />
        </div>
        <Ledger pyg={pyg} margen={ind.margen_oper} />
      </section>

      {/* Costo de capital y financiación — soporte */}
      <div className="mt-9 grid grid-cols-2 gap-x-6 gap-y-3 rounded-[var(--radius-data)] border bg-card p-4 sm:grid-cols-3 lg:grid-cols-5">
        <MiniStat label="WACC" value={fmtPct(ind.wacc)} note="Damodaran" />
        <MiniStat label="TIO" value={fmtPct(ind.tio)} note="costo de oportunidad" />
        <MiniStat label="Crédito máx" value={fmtCop(ind.credito_max)} note="pico" />
        <MiniStat
          label="Payback"
          value={ind.payback_mes != null ? `${fmtInt(ind.payback_mes)} m` : "n/d"}
          note="meses"
        />
        {ind.incidencia_lote != null ? (
          <MiniStat label="Incidencia lote" value={fmtPct(ind.incidencia_lote)} note="lote / ventas" />
        ) : null}
      </div>

      <section className="mt-9">
        <SectionTitle
          right={okAll ? "todos OK" : "revisar"}
          subtitle="Chequeos de consistencia del modelo: recaudo, P&amp;G y crédito deben cuadrar."
        >
          Cuadres
        </SectionTitle>
        <div className="flex flex-wrap gap-2 rounded-[var(--radius-data)] border bg-card p-4">
          {results.checks.map((c) => (
            <ChecksBadge key={c.clave} nombre={c.nombre} ok={c.ok} />
          ))}
        </div>
      </section>

      {project.urbanistico ? (
        <section className="mt-9">
          <SectionTitle right="áreas e índices" subtitle="Áreas, índices urbanísticos y valores por m².">Ficha técnica</SectionTitle>
          <FichaTecnica u={project.urbanistico} />
        </section>
      ) : null}
    </div>
  );
}

/** Precio/costo por m² (valor en COP) → "$X.XM" (millones COP por m²). */
function fmtPorM2(v: number | null): string {
  if (v === null || v === undefined || !isFinite(v)) return "—";
  return `$${(v / 1_000_000).toFixed(2)}M`;
}

function num2(v: number | null): string {
  return v === null || v === undefined || !isFinite(v) ? "—" : v.toFixed(2);
}

function FichaTecnica({ u }: { u: Urbanistico }) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <TechBlock title="Áreas">
        <TechRow label="Lote bruto" value={u.lote_bruta != null ? `${fmtInt(u.lote_bruta)} m²` : "—"} />
        <TechRow label="Lote útil" value={u.lote_util != null ? `${fmtInt(u.lote_util)} m²` : "—"} />
        <TechRow label="Área construida" value={u.area_construida != null ? `${fmtInt(u.area_construida)} m²` : "—"} />
        <TechRow label="Área vendible" value={u.area_vendible != null ? `${fmtInt(u.area_vendible)} m²` : "—"} />
      </TechBlock>
      <TechBlock title="Índices">
        <TechRow label="Ratio bruta / útil" value={num2(u.ratio_bruta_util)} />
        <TechRow label="Índice de construcción" value={num2(u.indice_construccion)} />
        <TechRow label="Aprovechamiento" value={fmtPct(u.aprovechamiento)} />
        <TechRow label="Densidad" value={u.densidad_und_ha != null ? `${fmtInt(u.densidad_und_ha)} und/ha` : "—"} />
      </TechBlock>
      <TechBlock title="Por m²">
        <TechRow label="Precio de venta / m²" value={fmtPorM2(u.precio_m2_vend)} />
        <TechRow label="Costo directo / m²" value={fmtPorM2(u.costo_dir_m2_const)} />
      </TechBlock>
    </div>
  );
}

function TechBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[var(--radius-data)] border bg-card p-4">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
      <dl className="divide-y divide-[var(--rule)]">{children}</dl>
    </div>
  );
}

function TechRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="num text-sm tabular-nums text-foreground/90">{value}</dd>
    </div>
  );
}


function Ledger({ pyg, margen }: { pyg: Pyg; margen: number | null }) {
  const v = pyg.ventas; // base de los porcentajes: todo el P&G se lee como % de las ventas
  return (
    <div className="overflow-hidden rounded-[var(--radius-data)] border bg-card">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-rule text-[0.7rem] font-medium uppercase tracking-wider text-muted-foreground">
            <th className="px-4 py-1.5 text-left"></th>
            <th className="px-4 py-1.5 text-right">% ventas</th>
            <th className="px-4 py-1.5 text-right">Valor</th>
          </tr>
        </thead>
        <tbody>
          <Group>Ingresos</Group>
          <Row label="Ventas" value={pyg.ventas} ventas={v} />
          {pyg.recon_codensa ? <Row label="Reconocimiento" value={pyg.recon_codensa} ventas={v} /> : null}
          <Row label="Total ingresos" value={pyg.total_ingresos} ventas={v} strong />

          <Group>Costos</Group>
          <Row label="Costo directo" value={pyg.directos} ventas={v} muted />
          <Row label="Indirectos" value={pyg.indirectos} ventas={v} muted />
          <Row label="Honorarios" value={pyg.honorarios} ventas={v} muted />
          {pyg.gastos_fijos ? <Row label="Gastos fijos" value={pyg.gastos_fijos} ventas={v} muted /> : null}
          <Row label="Lote" value={pyg.costo_lote} ventas={v} muted />

          <Group>Resultado</Group>
          <Row label="Utilidad operativa" value={pyg.util_oper} ventas={v} strong />
          <RowText label="Margen operativo" text={fmtPct(margen)} />

          <Group>Reparto</Group>
          <Row label="CG Constructora" value={pyg.cg} ventas={v} />
          <Row label="Socio" value={pyg.socio} ventas={v} />
        </tbody>
      </table>
    </div>
  );
}

function Group({ children }: { children: React.ReactNode }) {
  return (
    <tr className="border-b border-rule bg-muted/30">
      <th
        colSpan={3}
        className="px-4 py-1.5 text-left text-[0.7rem] font-semibold uppercase tracking-wider text-muted-foreground"
      >
        {children}
      </th>
    </tr>
  );
}

function Row({
  label,
  value,
  ventas,
  strong,
  muted,
}: {
  label: string;
  value: number;
  /** Base para el % de la fila (ventas). Si se da y > 0, muestra value/ventas en la columna de %. */
  ventas?: number;
  strong?: boolean;
  muted?: boolean;
}) {
  const pct = ventas && ventas > 0 ? value / ventas : null;
  return (
    <tr className="border-b border-rule last:border-0">
      <td className={`px-4 py-2.5 ${strong ? "font-semibold" : ""}`}>{label}</td>
      <td
        className={`num px-4 py-2.5 text-right tabular-nums ${strong ? "font-semibold text-foreground" : "text-muted-foreground"}`}
      >
        {pct != null ? fmtPct(pct) : ""}
      </td>
      <td className="px-4 py-2.5 text-right">
        <Figure
          parts={splitCop(value)}
          className={`${strong ? "font-semibold" : ""} ${muted ? "text-muted-foreground" : ""}`}
        />
      </td>
    </tr>
  );
}

function RowText({ label, text }: { label: string; text: string }) {
  return (
    <tr className="border-b border-rule last:border-0">
      <td className="px-4 py-2.5">{label}</td>
      <td></td>
      <td className="num px-4 py-2.5 text-right">{text}</td>
    </tr>
  );
}
