/**
 * Cliente tipado del API de ALEPH (`aleph_api`, FastAPI). Solo LECTURA.
 * Contrato §5. La API NO recalcula nada en el cliente: el motor produce las cifras, aquí se consumen.
 *
 * SERVER-ONLY: importa `auth()`/`redirect` (next/headers). Las páginas (Server Components) y el
 * Server Action de Monte Carlo lo usan; los client components solo importan los TIPOS (`import type`).
 *
 * Base URL: env `ALEPH_API_URL` (dev: http://localhost:8000 con la auth apagada).
 * Auth (config-driven, espeja al API): con `AUTH_MICROSOFT_ENTRA_ID_ID` cada `/v1/*` lleva el
 * access_token de Entra como `Authorization: Bearer`; sin esa env (dev local) no se adjunta nada.
 */

import { auth } from "@/auth";
import { redirect } from "next/navigation";

export const API_BASE = process.env.ALEPH_API_URL ?? "http://localhost:8000";

/** Auth encendida sólo si Entra está configurado (mismo gate que el proxy y el provider). */
const AUTH_ON = !!process.env.AUTH_MICROSOFT_ENTRA_ID_ID;

/** Adjunta el access_token de Entra (de la sesión NextAuth) si la auth está encendida. */
async function authHeaders(): Promise<Record<string, string>> {
  if (!AUTH_ON) return {};
  const session = await auth();
  const token = session?.apiToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * `fetch` contra el API con el Bearer adjunto y manejo central de 401/403.
 * En prod (auth on), un 401/403 = token expirado/invalidado → redirige a `/login?reason=expired`
 * (pantalla clara "sesión expirada, vuelve a entrar"). En dev (auth off) lanza un Error normal.
 */
async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = {
    ...(init.headers as Record<string, string> | undefined),
    ...(await authHeaders()),
  };
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init, headers });
  if (res.status === 401 || res.status === 403) {
    if (AUTH_ON) redirect("/login?reason=expired");
    throw new Error(`API respondió ${res.status} (no autorizado) en ${path}`);
  }
  return res;
}

/** Estados del ciclo de vida (deben coincidir con `aleph_engine.config.ESTADOS`). */
export type Estado = "prefactibilidad" | "aprobado" | "construccion" | "entregado";

/** Consolidado del portafolio (números CRUDOS, en miles COP; el cliente formatea). */
export interface PortfolioConsolidado {
  n: number;
  unidades: number;
  ventas: number;
  util_oper: number;
  udi: number;
  vpn: number;
  margen: number;
  tir_ref: number | null;
  tir_eq: number | null;
  credito_max: number;
  // Veredicto de Valor del PORTAFOLIO (Σ valor creado @WACC; excluye greenfield).
  crea_valor: boolean | null;
  valor_creado: number | null;
  n_genera: number;
  n_evaluados: number;
  valor_metodo: string;
}

export interface FunnelStage {
  estado: Estado | string;
  label: string;
  count: number;
}

/** Un proyecto en el pipeline/embudo (de `portfolio.pipeline`). */
export interface ProjectItem {
  slug: string;
  nombre: string;
  estado: Estado | string;
  tir: number | null;
  vpn: number | null;
  ventas: number | null;
  /** Margen operativo (fracción). Para el mapa de valor (TIR × margen). */
  margen: number | null;
  und: number;
  ubicacion: string;
  tipo: string;
  /** Veredicto de Valor del item (null = greenfield). */
  crea_valor: boolean | null;
  valor_creado: number | null;
}

export interface Portfolio {
  consolidado: PortfolioConsolidado;
  embudo: FunnelStage[];
  items: ProjectItem[];
}

/** GET /v1/portfolio. Sin caché (dato dinámico). Lanza Error con el status si la API falla. */
export async function getPortfolio(): Promise<Portfolio> {
  const res = await apiFetch(`/v1/portfolio`);
  if (!res.ok) {
    throw new Error(`API respondió ${res.status} al pedir /v1/portfolio`);
  }
  return res.json() as Promise<Portfolio>;
}

// ---------- Tesorería consolidada del portafolio (Pilar 2) ----------

export interface Tesoreria {
  disponible: boolean;
  base_date: string;
  horizonte: number;
  n: number;
  /** Posición de caja consolidada (miles COP) por mes desde base_date. */
  caja: number[];
  /** Saldo de crédito consolidado (miles COP) por mes. */
  credito: number[];
  /** Valle de caja = máxima necesidad de caja combinada (valor negativo) + su mes. */
  exposicion_maxima: { mes: number; valor: number };
  credito_maximo: { mes: number; valor: number };
  por_proyecto: { nombre: string; caja: number[] }[];
}

/** GET /v1/portfolio/tesoreria. Degrada a `null` si el API aún no lo expone (sin redeploy). */
export async function getTesoreria(): Promise<Tesoreria | null> {
  const res = await apiFetch(`/v1/portfolio/tesoreria`);
  if (!res.ok) return null;
  return res.json() as Promise<Tesoreria>;
}

// ---------- Asignación de capital del portafolio (Pilar 2) ----------

export interface CapitalFila {
  slug: string;
  nombre: string;
  tipo: string | null;
  /** Equity pico = necesidad máxima de caja propia tras el crédito (miles COP). */
  equity_pico: number;
  credito_max: number;
  /** Valor creado (EVA @WACC); null si greenfield (sin veredicto). */
  valor_creado: number | null;
  crea_valor: boolean | null;
  /** Eficiencia = valor creado / equity pico; null si greenfield. */
  eficiencia: number | null;
}

export interface Capital {
  filas: CapitalFila[];
  equity_total: number;
  credito_total: number;
  valor_creado_total: number;
  eficiencia_portafolio: number | null;
  n: number;
}

/** GET /v1/portfolio/capital. Degrada a `null` si el API aún no lo expone (sin redeploy). */
export async function getCapital(): Promise<Capital | null> {
  const res = await apiFetch(`/v1/portfolio/capital`);
  if (!res.ok) return null;
  return res.json() as Promise<Capital>;
}

// ---------- Estrés de la tesorería consolidada (Pilar 2) ----------

export interface EstresResumen {
  caja: number[];
  credito: number[];
  exposicion_maxima: { mes: number; valor: number };
  credito_maximo: { mes: number; valor: number };
}

export interface EstresEscenario extends EstresResumen {
  nombre: string;
  /** Deltas aplicados: precio = ventas, costo = directo, ritmo = ventas/mes. */
  shock: { precio: number; costo: number; ritmo: number };
  /** Cuánto se profundiza el valle (≤ 0) y se mueve el crédito vs la base. */
  delta_exposicion: number;
  delta_credito: number;
}

export interface Estres {
  disponible: boolean;
  base_date: string;
  horizonte: number;
  base: EstresResumen;
  escenarios: EstresEscenario[];
}

/** GET /v1/portfolio/tesoreria/estres. Degrada a `null` si el API aún no lo expone (sin redeploy). */
export async function getEstres(): Promise<Estres | null> {
  const res = await apiFetch(`/v1/portfolio/tesoreria/estres`);
  if (!res.ok) return null;
  return res.json() as Promise<Estres>;
}

// ---------- Concentración / diversificación del portafolio (Pilar 2) ----------

export interface ConcentracionCategoria {
  categoria: string;
  ventas: number;
  share: number;
}

export interface ConcentracionDim {
  clave: string;
  nombre: string;
  categorias: ConcentracionCategoria[];
  /** Índice de Herfindahl = Σ share² (0 → diversificado, 1 → todo en una). */
  hhi: number;
  /** Número EFECTIVO de categorías (1/HHI). */
  n_efectivo: number | null;
  n_categorias: number;
}

export interface Concentracion {
  total_ventas: number;
  n: number;
  dimensiones: ConcentracionDim[];
}

/** GET /v1/portfolio/concentracion. Degrada a `null` si el API aún no lo expone (sin redeploy). */
export async function getConcentracion(): Promise<Concentracion | null> {
  const res = await apiFetch(`/v1/portfolio/concentracion`);
  if (!res.ok) return null;
  return res.json() as Promise<Concentracion>;
}

// ---------- Cabina del CEO: salud + alertas (Pilar 2) ----------

export interface Alerta {
  nivel: "critico" | "alerta" | "info";
  /** Enum estable; la web mapea tipo → mensaje en español. */
  tipo: string;
  datos: Record<string, unknown>;
}

export interface Salud {
  n_proyectos: number;
  valor_creado: number;
  crea_valor: boolean | null;
  n_genera: number;
  n_evaluados: number;
  alertas: Alerta[];
  resumen: { critico: number; alerta: number; info: number };
}

/** GET /v1/portfolio/salud. Degrada a `null` si el API aún no lo expone (sin redeploy). */
export async function getSalud(): Promise<Salud | null> {
  const res = await apiFetch(`/v1/portfolio/salud`);
  if (!res.ok) return null;
  return res.json() as Promise<Salud>;
}

// ---------- Ficha de proyecto + resultados ----------

export interface Meta {
  nombre: string;
  ubicacion?: string;
  zona?: string;
  tipo?: string;
  unidades?: number;
  moneda?: string;
  estado?: string;
  propietario?: string;
}

export interface KpisCabecera {
  ventas: number;
  util_oper: number;
  udi: number;
  margen_oper: number;
  tir_proyecto: number | null;
  tir_socio: number | null;
  vpn_proyecto: number | null;
}

/** Ficha técnica / urbanística (áreas, índices, $/m²). Calculada por el motor. */
export interface Urbanistico {
  lote_bruta: number | null;
  lote_util: number | null;
  ratio_bruta_util: number | null;
  area_construida: number | null;
  area_vendible: number | null;
  indice_construccion: number | null;
  aprovechamiento: number | null;
  densidad_und_ha: number | null;
  precio_m2_vend: number | null;
  costo_dir_m2_const: number | null;
}

export interface ProjectDetail {
  id: string;
  es_real: boolean;
  fuente: string;
  meta: Meta;
  estado: string;
  estado_label: string;
  urbanistico?: Urbanistico | null;
  kpis_cabecera: KpisCabecera;
  /** Aviso de gobernanza opcional (p.ej. escenario PROVISIONAL): se muestra como banner en la ficha. */
  disclaimer?: string | null;
  /** Snapshot del par (el API lo expone como `params`). Respaldo para leer el disclaimer si el API
   * aún no expone el campo dedicado (evita depender del redeploy del API para mostrar el aviso). */
  params?: { disclaimer?: string | null } & Record<string, unknown>;
}

export interface Indicadores {
  base_label: string;
  fiducia_real: boolean;
  tir_proyecto: number | null;
  tir_proyecto_label: string;
  tir_socio: number | null;
  tir_socio_label: string;
  tir_apalancada_ref: number | null;
  vpn_proyecto: number | null;
  vpn_label: string;
  wacc: number | null;
  tio: number | null;
  payback_mes: number | null;
  credito_max: number | null;
  credito_prom: number | null;
  intereses_total: number | null;
  max_necesidad_caja: number | null;
  valor_financiable: number | null;
  margen_oper: number | null;
  // A2 (curso Camacol): incidencia del lote (lote/ventas) + costo de oportunidad explícito (= TIO).
  incidencia_lote?: number | null;
  incidencia_lote_label?: string;
  costo_oportunidad?: number | null;
  costo_oportunidad_label?: string;
  // A3 (curso Camacol): precios constantes — TIR reales deflactadas por inflación (Fisher).
  inflacion?: number | null;
  tir_proyecto_real?: number | null;
  tir_proyecto_real_label?: string;
  tir_socio_real?: number | null;
  tir_socio_real_label?: string;
  // C1 (curso Camacol M4/M6): capa after-tax de DECISIÓN (preliminar [VALIDAR asesor]).
  tir_proyecto_at?: number | null;
  tir_proyecto_at_label?: string;
  tir_socio_at?: number | null;
  tir_socio_at_label?: string;
  vpn_at?: number | null;
  vpn_at_label?: string;
  tir_proyecto_pre_mensual?: number | null;
  impuesto_renta_at?: number | null;
  gmf_at?: number | null;
  iva_vis_devolucion?: number | null;
  carga_tributaria_neta_at?: number | null;
  after_tax_metodo?: string | null;
  // Veredicto de Valor (EVA del proyecto): ¿genera o destruye valor sobre el WACC?
  crea_valor: boolean | null;       // null = greenfield (TIR degenerada) → "— greenfield"
  crea_valor_label: string;
  valor_creado: number | null;      // VPN @WACC (miles COP)
  valor_creado_label: string;
  spread_valor: number | null;      // TIR proyecto − WACC (fracción)
  spread_valor_label: string;
  valor_metodo: string;
}

export interface Pyg {
  ventas: number;
  recon_codensa: number;
  total_ingresos: number;
  directos: number;
  indirectos: number;
  honorarios: number;
  gastos_fijos: number;
  indirectos_otros: number;
  costo_lote: number;
  util_oper: number;
  margen_oper: number;
  /** Impuesto de renta del P&G (0 en proyectos VIS, exentos). */
  renta: number;
  udi: number;
  cg: number;
  socio: number;
  resultados: number;
}

export interface Check {
  clave: string;
  nombre: string;
  ok: boolean;
  detalle?: string;
}

/** Series mensuales del flujo apalancado (180 meses). */
export interface FlujoApalancado {
  operativo: number[];
  acumulado: number[];
  saldo_credito: number[];
  flujo_equity: number[];
  ingresos: number[];
  costos: number[];
  credito_max: number;
  max_necesidad_caja: number;
  aportes_total: number;
  payback_mes: number | null;
}

export interface Flujo {
  apalancado: FlujoApalancado;
  simple: Record<string, unknown>;
}

/** Cierre financiero (Fuentes y Usos) — curso Camacol §M6. Estructura cifras que el motor ya produce. */
export interface CierreLinea {
  concepto: string;
  valor: number;
}
export interface Cierre {
  usos: CierreLinea[];
  usos_total: number;
  fuentes: CierreLinea[];
  fuentes_total: number;
  utilidad_operativa: number;
  financiacion: {
    equity_pico: number | null;
    credito_max: number | null;
    exposicion_maxima: number | null;
    intereses: number;
  };
  cuadre: { clave: string; nombre: string; ok: boolean; detalle: string };
}

/** Due diligence / registro de riesgos → viabilidad cualitativa (curso Camacol M4/M5 · B1). */
export interface DueDiligenceItem {
  frente: string;
  item: string;
  estado: "ok" | "alerta" | "pendiente" | string;
  impacto: "alto" | "medio" | "bajo" | string;
  /** Probabilidad de que el riesgo se materialice (eje Y de la matriz). "media" si no se calificó. */
  probabilidad?: "alta" | "media" | "baja" | string;
  /** Severidad = probabilidad × impacto (celda de la matriz de riesgos). */
  severidad?: "alto" | "medio" | "bajo" | string;
  mitigacion: string;
  nota: string;
  del_analista: boolean;
}
export interface DueDiligence {
  frentes: { clave: string; nombre: string }[];
  items: DueDiligenceItem[];
  /** Conteo de riesgos ABIERTOS (estado != ok) por severidad. null si el API aún no lo expone. */
  severidad_resumen?: { alto: number; medio: number; bajo: number } | null;
  veredicto: {
    nivel: "verde" | "ambar" | "rojo" | string;
    n_items: number;
    n_ok: number;
    n_alertas: number;
    n_pendientes: number;
  };
}

/** Viabilidad urbanística (POT) — índices calculados vs límites del POT (B2). */
export interface UrbanismoItem {
  concepto: string;
  real: number;
  limite: number;
  cumple: boolean;
  uso_pct: number | null;
}
export interface Urbanismo {
  disponible: boolean;
  items: UrbanismoItem[];
  veredicto: { nivel: "cumple" | "al_limite" | "excede" | "sin_pot" | string; n: number; n_excede: number };
  referencia: Record<string, number | string>;
}

/** Estudio de mercado — supuestos del proyecto vs comparables de la zona (B3). */
export interface MercadoItem {
  dimension: string;
  sentido: "precio" | "ritmo" | string;
  proyecto: number;
  mercado: number;
  desviacion: number;
  estado: "ok" | "alerta" | string;
}
export interface Mercado {
  disponible: boolean;
  items: MercadoItem[];
  veredicto: { nivel: "en_mercado" | "revisar" | "sin_datos" | string; n: number; n_alerta: number };
  referencia: Record<string, number | string>;
}

export interface Results {
  scenario_id: string;
  project_id: string;
  base_label: string;
  indicadores: Indicadores;
  pyg: Pyg;
  flujo: Flujo;
  /** Cierre financiero (Fuentes=Usos). null si el API aún no lo expone (degrada limpio). */
  cierre?: Cierre | null;
  /** Due diligence + viabilidad cualitativa (B1). null si el API aún no lo expone. */
  due_diligence?: DueDiligence | null;
  /** Viabilidad urbanística — cumplimiento POT (B2). null si el API aún no lo expone. */
  urbanismo?: Urbanismo | null;
  /** Estudio de mercado — contraste de supuestos (B3). null si el API aún no lo expone. */
  mercado?: Mercado | null;
  checks: Check[];
}

/** GET /v1/projects/{slug}. null si no existe (404). */
export async function getProject(slug: string): Promise<ProjectDetail | null> {
  const res = await apiFetch(`/v1/projects/${encodeURIComponent(slug)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status} en /v1/projects/${slug}`);
  return res.json() as Promise<ProjectDetail>;
}

/** GET /v1/scenarios/{slug}:base/results. null si no existe (404). */
export async function getResults(slug: string): Promise<Results | null> {
  const res = await apiFetch(`/v1/scenarios/${encodeURIComponent(slug)}:base/results`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status} en results de ${slug}`);
  return res.json() as Promise<Results>;
}

// ---------- Sensibilidad (escenarios + tornado + heatmap) ----------

export interface EscenarioVals {
  ventas: number;
  util_oper: number;
  margen: number;
}

export interface Sensitivity {
  scenario_id: string;
  project_id: string;
  /** { Base | Optimista | Pesimista } → métricas. */
  escenarios: Record<string, EscenarioVals>;
  /** { "Precio -10%": Δutil, "Precio +10%": Δutil, ... } impacto sobre la utilidad. */
  tornado: Record<string, number>;
  matriz_2d: { pasos_precio: number[]; pasos_costo: number[]; margen_pct: number[][] };
}

/** GET /v1/scenarios/{slug}:base/sensitivity. null si no existe (404). */
export async function getSensitivity(slug: string): Promise<Sensitivity | null> {
  const res = await apiFetch(`/v1/scenarios/${encodeURIComponent(slug)}:base/sensitivity`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status} en sensitivity de ${slug}`);
  return res.json() as Promise<Sensitivity>;
}

// ---------- Cronograma (hitos + absorción + recaudo) ----------

/** Una etapa con sus hitos (fechas ISO + offset de mes desde base_date para el Gantt). */
export interface ScheduleEtapa {
  cod: number | string;
  nombre: string;
  unidades: number;
  iv: string; pe: string; fv: string; ic: string; fc: string;
  dur_obra: number | null;
  iv_mes: number; pe_mes: number; fv_mes: number; ic_mes: number; fc_mes: number;
  /** Fases extra (meses desde base): escrituración, entrega y fin de cuotas iniciales. null si el API no las expone. */
  esc_mes?: number | null; ent_mes?: number | null; cuo_fin_mes?: number | null;
}

export interface Schedule {
  scenario_id: string;
  project_id: string;
  /** Mes 0 de las series (= IV de la etapa raíz), ISO o null si no hay cronograma. */
  base_date: string | null;
  horizonte: number;
  unidades_total: number;
  etapas: ScheduleEtapa[];
  /** Series mensuales globales de unidades. */
  absorcion: { ventas: number[]; entregas: number[]; acum_ventas: number[]; acum_entregas: number[] };
  /** Series mensuales de caja (miles COP). */
  recaudo: { separacion: number[]; cuota_inicial: number[]; subrogacion: number[]; total: number[] };
}

/** GET /v1/scenarios/{slug}:base/schedule. null si no existe (404). */
export async function getSchedule(slug: string): Promise<Schedule | null> {
  const res = await apiFetch(`/v1/scenarios/${encodeURIComponent(slug)}:base/schedule`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status} en schedule de ${slug}`);
  return res.json() as Promise<Schedule>;
}

// ---------- Costo de capital (WACC build-up CAPM) ----------

export interface WaccInputs {
  rf: number | null; rm: number | null; pm: number | null;
  kd_us: number | null; de_us: number | null; tax_us: number | null;
  de_col: number | null; tax_col: number | null;
  inf_col: number | null; inf_us: number | null;
}

/** Build-up CAPM completo. Tasas como fracción decimal (0.1731 = 17.31%). */
export interface Wacc {
  scenario_id: string;
  project_id: string;
  disponible: boolean;
  wacc?: number;
  tio?: number | null;
  beta_us?: number; beta_d?: number; beta_u?: number; beta_l?: number;
  ke_usd?: number; rp?: number; ke_usd_rp?: number; rplp?: number; ke_cop?: number;
  kd_cop?: number; kd_despues_imp?: number;
  we?: number; wd?: number; t_col?: number;
  /** Contribuciones que suman al WACC: E·Ke y D·Kd·(1−t). */
  aporte_equity?: number; aporte_deuda?: number;
  inputs?: WaccInputs;
}

/** GET /v1/scenarios/{slug}:base/wacc. null si no existe (404). */
export async function getWacc(slug: string): Promise<Wacc | null> {
  const res = await apiFetch(`/v1/scenarios/${encodeURIComponent(slug)}:base/wacc`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status} en wacc de ${slug}`);
  return res.json() as Promise<Wacc>;
}

// ---------- Fuentes en vivo (Fase 2): dato actual de la fuente externa, para contrastar ----------

export interface FuentesLive {
  disponible: boolean;
  fuente: string;
  url: string;
  nota?: string;
  /** Calificación soberana actual según la fuente (p.ej. "Baa3"). */
  rating?: string | null;
  /** Valor vivo (fracción) por clave de input del WACC: { rp: {...}, pm: {...} }. */
  datos?: Record<string, { valor: number }>;
  /** TRM oficial del dólar (COP/USD) en vivo de Banrep — dato de mercado de REFERENCIA (no entra al WACC). */
  trm?: {
    disponible: boolean;
    fuente: string;
    url: string;
    valor?: number;
    unidad?: string;
    periodo?: string | null;
  } | null;
}

/** Valores macro EN VIVO de la fuente (Damodaran), para la pestaña Fuentes. Degrada a `null` si el API
 *  aún no expone el endpoint (sin redeploy) o la fuente externa no responde → la web muestra solo-modelo. */
export async function getFuentesLive(): Promise<FuentesLive | null> {
  const res = await apiFetch(`/v1/fuentes/live`);
  if (!res.ok) return null;
  return res.json() as Promise<FuentesLive>;
}

// ---------- Escenarios macro (abanico forward): cono de incertidumbre inflación/tasa/TRM ----------

export interface MacroPunto {
  anio: number;
  base: number;
  bajo: number;
  alto: number;
}
export interface MacroVariable {
  clave: "inflacion" | "tasa" | "trm" | string;
  nombre: string;
  unidad: "pct_ea" | "COP" | string;
  fuente: string;
  nota: string;
  /** true si la base arranca del dato VIVO de Banrep (TRM/IBR); false si usa el default grounded. */
  anclado: boolean;
  puntos: MacroPunto[];
}
export interface MacroForward {
  anio_inicio: number;
  horizonte: number;
  variables: MacroVariable[];
  nota: string;
  anclas_vivas?: {
    trm?: { disponible?: boolean; valor?: number; periodo?: string | null } | null;
    ibr?: { disponible?: boolean; valor?: number; periodo?: string | null } | null;
  };
}

/** Escenarios macro (abanico forward). Degrada a `null` si el API aún no expone el endpoint (sin
 *  redeploy) → la sección de escenarios simplemente no aparece. */
export async function getFuentesForward(): Promise<MacroForward | null> {
  const res = await apiFetch(`/v1/fuentes/forward`);
  if (!res.ok) return null;
  return res.json() as Promise<MacroForward>;
}

// ---------- Monte Carlo (POST run) ----------

export interface MCStats {
  p10: number;
  p50: number;
  p90: number;
  media: number;
  std: number;
  n: number;
}

export interface MonteCarloResult {
  tir_proyecto: number[];
  tir_equity: number[];
  vpn_proyecto: number[];
  stats_tir: MCStats;
  stats_equity: MCStats;
  stats_vpn: MCStats;
  hurdle: number;
  prob_tir_hurdle: number;
  prob_vpn_pos: number;
  n: number;
  n_validas: number;
}

export interface MonteCarloParams {
  tipo?: "tir" | "margen";
  n?: number;
  seed?: number;
  rango_precio?: [number, number];
  rango_costo?: [number, number];
  rango_ventas?: [number, number];
}

/** POST /v1/scenarios/{slug}:base/run — Monte Carlo (único cálculo intensivo). */
export async function postRun(slug: string, params: MonteCarloParams): Promise<MonteCarloResult> {
  const res = await apiFetch(`/v1/scenarios/${encodeURIComponent(slug)}:base/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`API ${res.status} al correr Monte Carlo de ${slug}`);
  return res.json() as Promise<MonteCarloResult>;
}


// ---------- Monte Carlo Crystal Ball (M5) ----------
export interface MCForecastStats {
  n: number; media: number; mediana: number; std: number; min: number; max: number;
  p5: number; p10: number; p25: number; p50: number; p75: number; p90: number; p95: number;
}
export interface MCCerteza { umbral: number; signo: string; prob: number }
export interface MCTornadoVar { rho: number; contribucion_pct: number }
export interface MCForecast {
  nombre: string;
  stats: MCForecastStats;
  certeza: MCCerteza | null;
  tornado: Record<string, MCTornadoVar>;
  valores?: number[];
}
export interface MonteCarloCBResult {
  n: number; seed: number; hurdle: number;
  supuestos: { variable: string; dist: string; params: Record<string, number>; nombre: string }[];
  forecasts: Record<string, MCForecast>;
}
export interface MonteCarloCBParams { n?: number; seed?: number; hurdle?: number; incluir_valores?: boolean }

/** POST /v1/scenarios/{slug}:base/montecarlo — Crystal Ball (distribuciones, percentiles, certeza, tornado). */
export async function postMonteCarloCB(slug: string, params: MonteCarloCBParams): Promise<MonteCarloCBResult> {
  const res = await apiFetch(`/v1/scenarios/${encodeURIComponent(slug)}:base/montecarlo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`API ${res.status} al correr Monte Carlo de ${slug}`);
  return res.json() as Promise<MonteCarloCBResult>;
}

// ---------- Escritura (Fase 5): crear/aprobar proyectos (SOLO admin) ----------
// El API es el gate autoritativo: valida el `par` con `schema.parse` (422), exige rol admin (403) y
// recalcula con el motor al aprobar. Aquí solo adjuntamos el token y traducimos los errores a algo
// que el formulario pueda mostrar (el `detail` del API), sin redirigir en 403 (ese usuario SÍ está
// autenticado, solo no es admin → mensaje claro, no bucle de login).

/** Error de escritura con el status HTTP y el mensaje legible del API (su campo `detail`). */
export class WriteError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "WriteError";
  }
}

/** Extrae un mensaje legible del cuerpo de error (string `detail`, o lista de errores Pydantic 422). */
async function readDetail(res: Response, fallback: string): Promise<string> {
  try {
    const j = await res.json();
    if (j && typeof j.detail === "string") return j.detail;
    if (j && Array.isArray(j.detail)) {
      return j.detail
        .map((e: { loc?: unknown[]; msg?: string }) =>
          [Array.isArray(e.loc) ? e.loc.slice(1).join(".") : null, e.msg].filter(Boolean).join(": "),
        )
        .filter(Boolean)
        .join(" · ") || fallback;
    }
  } catch {
    /* sin cuerpo JSON */
  }
  return fallback;
}

/**
 * `fetch` de ESCRITURA. Adjunta el Bearer; 401 → sesión expirada (redirige en prod); 403 → sin rol
 * admin (WriteError, NO redirige); 4xx/5xx → WriteError con el `detail` del API (422 validación,
 * 409 conflicto, 503 sin Supabase). Devuelve el JSON parseado en éxito.
 */
async function apiWrite(
  path: string,
  body: unknown,
  init: { method?: "POST" | "PUT" | "PATCH" | "DELETE"; headers?: Record<string, string> } = {},
): Promise<unknown> {
  const headers: Record<string, string> = {
    ...(await authHeaders()),
    ...init.headers,
  };
  const hasBody = body !== undefined && body !== null;
  if (hasBody) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_BASE}${path}`, {
    method: init.method ?? "POST",
    headers,
    body: hasBody ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (res.status === 401) {
    if (AUTH_ON) redirect("/login?reason=expired");
    throw new WriteError(401, "No autorizado (sesión).");
  }
  if (res.status === 403) {
    throw new WriteError(403, "No tienes permiso: esta acción requiere rol de administrador.");
  }
  if (!res.ok) throw new WriteError(res.status, await readDetail(res, `Error ${res.status} del API.`));
  return res.json();
}

export interface CreateProjectResult {
  project_id: string;
  scenario_id: string;
  slug: string;
  version: number;
  status: string;
}

export interface ApproveResult {
  scenario_id: string;
  status: string;
  version: number;
  tir_proyecto: number | null;
  checks_ok: boolean;
  checks: { clave: string; nombre: string; ok: boolean }[];
}

/** POST /v1/projects — crea un proyecto nuevo + su escenario v1 en borrador. Lanza WriteError. */
export async function createProject(
  par: Record<string, unknown>,
  opts?: { slug?: string; nombre?: string; es_real?: boolean },
): Promise<CreateProjectResult> {
  return apiWrite(`/v1/projects`, {
    par,
    slug: opts?.slug ?? null,
    nombre: opts?.nombre ?? null,
    es_real: opts?.es_real ?? false,
  }) as Promise<CreateProjectResult>;
}

/** POST /v1/scenarios/{id}/approve — aprueba un borrador (recalcula + congela). Lanza WriteError. */
export async function approveScenario(scenarioId: string): Promise<ApproveResult> {
  return apiWrite(`/v1/scenarios/${encodeURIComponent(scenarioId)}/approve`, {}) as Promise<ApproveResult>;
}

export interface DeleteProjectResult {
  deleted: boolean;
  slug: string;
  scenarios_borrados: number;
}

/** DELETE /v1/projects/{slug} — borra un proyecto completo (escenarios + cache). Admin. WriteError. */
export async function deleteProject(slug: string): Promise<DeleteProjectResult> {
  return apiWrite(`/v1/projects/${encodeURIComponent(slug)}`, undefined, {
    method: "DELETE",
  }) as Promise<DeleteProjectResult>;
}

export interface ProjectSource {
  project_id: string;
  version: number;
  es_real: boolean;
  /** El `par` crudo del escenario vigente (input editable, para pre-llenar el formulario). */
  par: Record<string, unknown>;
}

/** Una fila de la tabla de tipologías (mezcla de unidades por clase/etapa) — editor de tipologías. */
export interface Tipologia {
  etapa: number;
  nombre?: string;
  clase: "apartamento" | "comercio" | "parqueadero" | "deposito" | string;
  und: number;
  metodo: "$/und" | "$/m²" | string;
  precio: number;
  area_und?: number;
}

/** GET /v1/projects/{slug}/source — el `par` crudo del escenario vigente (admin). null si no existe. */
export async function getProjectSource(slug: string): Promise<ProjectSource | null> {
  const res = await apiFetch(`/v1/projects/${encodeURIComponent(slug)}/source`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status} en source de ${slug}`);
  return res.json() as Promise<ProjectSource>;
}

export interface ScenarioWriteResult {
  scenario_id: string;
  version: number;
  status: string;
}

/** POST /v1/projects/{projectId}/scenarios — crea un escenario borrador NUEVO (siguiente versión). */
export async function nuevoEscenario(
  projectId: string,
  par: Record<string, unknown>,
): Promise<ScenarioWriteResult> {
  return apiWrite(`/v1/projects/${encodeURIComponent(projectId)}/scenarios`, {
    par,
  }) as Promise<ScenarioWriteResult>;
}

export interface SetRealResult {
  slug: string;
  es_real: boolean;
}

/** PATCH /v1/projects/{slug} — marca el proyecto como datos reales / ilustrativos. Admin. */
export async function setProjectReal(slug: string, esReal: boolean): Promise<SetRealResult> {
  return apiWrite(`/v1/projects/${encodeURIComponent(slug)}`, { es_real: esReal }, {
    method: "PATCH",
  }) as Promise<SetRealResult>;
}


// ---------- Comparador de vehículos jurídico-financieros (M3) ----------

export interface VehiculoFila {
  vehiculo: string;
  nombre_vehiculo: string;
  es_vis: boolean;
  renta: number;
  udi: number;
  tasa: number;
  etiqueta: string;
  exencion_vis_aplicada: boolean;
  transparente: boolean;
  tir_proyecto_at: number;
  tir_socio_at: number;
  carga_tributaria: number;
  carga_detalle: { renta: number; gmf: number; dividendos: number };
  delta_udi_vs_fiducia: number;
  delta_tir_socio_vs_fiducia: number;
  delta_carga_vs_fiducia: number;
  es_referencia: boolean;
}

export interface Vehiculos {
  scenario_id: string;
  project_id: string;
  advertencia: string;
  base_comparacion: string;
  oficial_fiducia: { tir_proyecto_auditada: number | null; tir_socio_auditada: number | null; fuente: string };
  nota: string;
  vehiculos: VehiculoFila[];
}

/** GET /v1/scenarios/{slug}:base/vehiculos. null si no existe (404). */
export async function getVehiculos(slug: string): Promise<Vehiculos | null> {
  const res = await apiFetch(`/v1/scenarios/${encodeURIComponent(slug)}:base/vehiculos`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status} en vehiculos de ${slug}`);
  return res.json() as Promise<Vehiculos>;
}


// ---------- M4b: recálculo en vivo (forward) + goal-seek (backward) ----------

export interface RecalcInd {
  tir_proyecto: number;
  tir_equity: number;
  vpn_proyecto: number;
  margen: number;
  exposicion_maxima: number;
  breakeven_mes: number;
}

export interface Recalc {
  deltas: { precio: number; costo: number; ritmo: number };
  base: RecalcInd;
  resultado: RecalcInd;
  nota: string;
}

export async function postRecalc(
  slug: string,
  deltas: { precio?: number; costo?: number; ritmo?: number },
): Promise<Recalc> {
  const res = await apiFetch(`/v1/scenarios/${encodeURIComponent(slug)}:base/recalc`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(deltas),
  });
  if (!res.ok) throw new Error(`API ${res.status} en recalc de ${slug}`);
  return res.json() as Promise<Recalc>;
}

export interface GoalSeekDriver {
  alcanzable: boolean;
  objetivo: string;
  meta: number;
  driver: string;
  delta?: number;
  valor?: number;
  valor_base?: number;
}

/** alcanzar(): un resultado por driver (precio/costo/ritmo). */
export type GoalSeek = Record<string, GoalSeekDriver>;

export async function postGoalSeek(
  slug: string,
  params: { objetivo: string; meta: number },
): Promise<GoalSeek> {
  const res = await apiFetch(`/v1/scenarios/${encodeURIComponent(slug)}:base/goal-seek`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`API ${res.status} en goal-seek de ${slug}`);
  return res.json() as Promise<GoalSeek>;
}
