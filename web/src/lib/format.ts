/**
 * Formato único de presentación (moneda y porcentaje) — réplica EXACTA de
 * `app_streamlit/ui/format.py` (fuente de verdad). Convención CG: montos en MILES COP;
 * separador de miles con punto. NO contiene lógica financiera (solo presentación).
 */

/** `f"{v:,.Nf}".replace(",", ".")` de Python: agrupa en en-US y cambia la coma por punto. */
function enDot(v: number, decimals: number): string {
  return v
    .toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
    .replace(/,/g, ".");
}

/**
 * Formatea un monto en MILES COP a pesos legibles (idéntico a `fmt_cop`).
 * - ≥ mil millones → "mil M" (miles de millones), 1 decimal.
 * - si no → "M" (millones), sin decimales.
 * - 0/null/undefined/NaN → "$0".
 */
export function fmtCop(x: number | null | undefined): string {
  if (!x) return "$0";
  if (Math.abs(x) >= 1_000_000) return `$${enDot(x / 1_000_000, 1)} mil M`;
  return `$${enDot(x / 1000, 0)} M`;
}

/** Formatea una fracción como porcentaje (0.2183 → "21.83%"). null/undefined → "n/d". */
export function fmtPct(x: number | null | undefined, dec = 2): string {
  if (x === null || x === undefined || !isFinite(x)) return "n/d";
  return `${(x * 100).toFixed(dec)}%`;
}

/** Entero con separador de miles es-CO (para unidades): 1234 → "1.234". */
export function fmtInt(x: number | null | undefined): string {
  if (x === null || x === undefined || !isFinite(x)) return "—";
  return Math.round(x).toLocaleString("es-CO");
}

/** Igual que fmtCop pero separa [magnitud, unidad] para de-enfatizar el sufijo en la UI. */
export function splitCop(x: number | null | undefined): [string, string] {
  if (!x) return ["$0", ""];
  if (Math.abs(x) >= 1_000_000) return [`$${enDot(x / 1_000_000, 1)}`, "mil M"];
  return [`$${enDot(x / 1000, 0)}`, "M"];
}

/** Igual que fmtPct pero separa [magnitud, "%"]. n/d → ["n/d", ""]. */
export function splitPct(x: number | null | undefined, dec = 2): [string, string] {
  if (x === null || x === undefined || !isFinite(x)) return ["n/d", ""];
  return [(x * 100).toFixed(dec), "%"];
}

/**
 * Umbral de TIR degenerada (IRR sin sentido económico). Una TIR por debajo de esto NO es una tasa
 * real: es un artefacto del solver cuando el flujo no cruza cero (greenfield / proyecto de 1 etapa).
 * Fuente única de verdad del umbral; consúmela, no la repitas con un literal suelto.
 */
export const TIR_DEGENERADA = -0.5;

/** True si una TIR es degenerada (null/no-finita o < umbral): no debe mostrarse como "-99%"/"-100%". */
export function tirEsDegenerada(tir: number | null | undefined): boolean {
  return tir === null || tir === undefined || !isFinite(tir) || tir < TIR_DEGENERADA;
}

/**
 * TIR para PRESENTACIÓN, aplicando la regla de la constitución ("Proyectos greenfield → mostrar
 * '— greenfield', jamás TIR −99%"): una TIR degenerada se muestra como "—" con sufijo "greenfield",
 * nunca como "-100%". El resto se formatea como splitPct. Devuelve [magnitud, sufijo].
 */
export function splitTir(tir: number | null | undefined, dec = 2): [string, string] {
  if (tirEsDegenerada(tir)) return ["—", "greenfield"];
  return splitPct(tir, dec);
}

/**
 * Motivo por el que una TIR de SOCIO/equity sale vacía. Distingue "greenfield" (el PROYECTO no tiene
 * TIR) de "sin aporte" (el proyecto SÍ tiene TIR, pero el socio no aporta capital → no hay TIR de
 * equity; su retorno es por honorarios, no por equity). Ej.: Argos, donde CG no aporta capital.
 */
export function tirSocioVacia(tirProyecto: number | null | undefined): string {
  return tirEsDegenerada(tirProyecto) ? "greenfield" : "sin aporte";
}

/** TIR de socio para el KPI: número si existe; si no, distingue greenfield vs sin aporte de capital. */
export function splitTirSocio(
  tirSocio: number | null | undefined,
  tirProyecto: number | null | undefined,
  dec = 2,
): [string, string] {
  if (tirEsDegenerada(tirSocio)) return ["—", tirSocioVacia(tirProyecto)];
  return splitPct(tirSocio, dec);
}
