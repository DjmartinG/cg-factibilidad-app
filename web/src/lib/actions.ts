"use server";

import { revalidatePath } from "next/cache";
import {
  approveScenario,
  createProject,
  deleteProject,
  getProjectSource,
  nuevoEscenario,
  postRun,
  postMonteCarloCB,
  postRecalc,
  postGoalSeek,
  postOpciones,
  setProjectReal,
  WriteError,
  type MonteCarloParams,
  type MonteCarloResult,
  type MonteCarloCBParams,
  type MonteCarloCBResult,
  type Recalc,
  type GoalSeek,
  type Opciones,
  type EtapaMod,
} from "@/lib/api";

/**
 * Server Action: corre el Monte Carlo en el motor (vía la API), del lado del servidor.
 * Así la URL/token del API quedan server-side (preparado para el login de Entra en /web).
 */
export async function runMonteCarlo(
  slug: string,
  params: MonteCarloParams,
): Promise<MonteCarloResult> {
  return postRun(slug, params);
}


/** Server Action: Monte Carlo Crystal Ball (distribuciones, percentiles, certeza, tornado). */
export async function runMonteCarloCB(
  slug: string,
  params: MonteCarloCBParams,
): Promise<MonteCarloCBResult> {
  return postMonteCarloCB(slug, params);
}


/** Server Action (M4b · forward): recalcula indicadores con deltas de precio/costo/ritmo. */
export async function recalcular(
  slug: string,
  deltas: { precio?: number; costo?: number; ritmo?: number },
): Promise<Recalc> {
  return postRecalc(slug, deltas);
}

/** Server Action (M4b · backward / "devolvernos"): qué driver alcanza la meta del objetivo. */
export async function resolverMeta(
  slug: string,
  objetivo: string,
  meta: number,
): Promise<GoalSeek> {
  return postGoalSeek(slug, { objetivo, meta });
}

/** Server Action: opciones reales por etapa (retrasar/acelerar/quitar) → impacto en caja y retorno. */
export async function evaluarOpciones(
  slug: string,
  mods: Record<string, EtapaMod>,
): Promise<Opciones> {
  return postOpciones(slug, mods);
}

// ---------- Escritura (Fase 5): crear + aprobar un proyecto ----------
// El token de Entra y la URL del API quedan SERVER-SIDE; el API revalida el JWT y exige rol admin
// (defensa real). Esta acción es delgada: arma la secuencia crear→aprobar y traduce el resultado a
// algo que el formulario (client) pueda mostrar SIN volcar excepciones crudas al usuario.

export interface CrearProyectoInput {
  par: Record<string, unknown>;
  slug?: string;
  nombre?: string;
  es_real?: boolean;
}

export type CrearProyectoResult =
  | { ok: true; slug: string; scenario_id: string; tir_proyecto: number | null; checks_ok: boolean }
  | { ok: false; status: number; message: string };

/**
 * Crea un proyecto (escenario v1 borrador) y lo APRUEBA en un paso → queda visible en el portafolio
 * (que lee baseline/approved). Devuelve la TIR proyecto y el estado de los cuadres para feedback.
 * Errores del API (422 validación, 403 sin rol, 409 slug duplicado, 503 sin Supabase) vuelven como
 * `{ok:false, message}` con el `detail` del motor/servidor; el `redirect` de 401 se deja propagar.
 */
export async function crearYAprobarProyecto(
  input: CrearProyectoInput,
): Promise<CrearProyectoResult> {
  // Paso 1: crear (valida `par` con el motor ANTES de persistir → un 422/409 aquí no deja rastro).
  let created;
  try {
    created = await createProject(input.par, {
      slug: input.slug,
      nombre: input.nombre,
      es_real: input.es_real,
    });
  } catch (e) {
    if (e instanceof WriteError) {
      // 409 = el nombre genera un slug ya existente (puede ser un intento previo que no se aprobó).
      const message =
        e.status === 409
          ? `${e.message} Si fue un intento anterior que no se aprobó, usa un nombre distinguible.`
          : e.message;
      return { ok: false, status: e.status, message };
    }
    throw e; // p.ej. el control-flow de redirect() (401) DEBE propagarse
  }

  // Paso 2: aprobar (recalcula con el motor). Si falla aquí, el borrador YA quedó guardado → el
  // mensaje lo dice para que el usuario no reintente con el mismo nombre y choque con un 409.
  try {
    const approved = await approveScenario(created.scenario_id);
    revalidatePath("/");
    revalidatePath(`/proyectos/${created.slug}`);
    return {
      ok: true,
      slug: created.slug,
      scenario_id: created.scenario_id,
      tir_proyecto: approved.tir_proyecto,
      checks_ok: approved.checks_ok,
    };
  } catch (e) {
    if (e instanceof WriteError) {
      return {
        ok: false,
        status: e.status,
        message: `El proyecto se guardó como borrador, pero no se pudo aprobar: ${e.message}`,
      };
    }
    throw e;
  }
}

// ---------- Editar proyecto: nueva versión a partir del par modificado (solo admin) ----------

export interface EditarProyectoInput {
  projectId: string;
  slug: string;
  par: Record<string, unknown>;
}

/**
 * Edita un proyecto creando un escenario NUEVO (siguiente versión) con el par modificado y
 * aprobándolo → pasa a ser el vigente. El aprobado anterior queda INMUTABLE (versionado, no se
 * sobrescribe; trigger 0002). Mismo patrón de 2 pasos y manejo de error que crear+aprobar.
 */
export async function editarYAprobarProyecto(
  input: EditarProyectoInput,
): Promise<CrearProyectoResult> {
  let draft;
  try {
    draft = await nuevoEscenario(input.projectId, input.par);
  } catch (e) {
    if (e instanceof WriteError) return { ok: false, status: e.status, message: e.message };
    throw e;
  }
  try {
    const approved = await approveScenario(draft.scenario_id);
    revalidatePath("/");
    revalidatePath(`/proyectos/${input.slug}`);
    return {
      ok: true,
      slug: input.slug,
      scenario_id: draft.scenario_id,
      tir_proyecto: approved.tir_proyecto,
      checks_ok: approved.checks_ok,
    };
  } catch (e) {
    if (e instanceof WriteError) {
      return {
        ok: false,
        status: e.status,
        message: `Se guardó la nueva versión como borrador, pero no se pudo aprobar: ${e.message}`,
      };
    }
    throw e;
  }
}

// ---------- Editar viabilidad (C2): captura DD / POT / mercado sin tocar las cifras ----------

export interface EditarViabilidadInput {
  slug: string;
  dueDiligence: unknown[];
  pot: Record<string, unknown>;
  mercado: Record<string, unknown>;
}

/**
 * Edita los registros CUALITATIVOS del proyecto (due diligence, límites POT, comparables de mercado)
 * creando una versión nueva. Lee el `par` crudo del escenario vigente SERVER-SIDE (no se pasa por el
 * cliente → a prueba de manipulación) y reemplaza SOLO esas tres claves: el resto del par (etapas,
 * costos, WACC, tipologías…) viaja bit a bit. El motor financiero ignora estos campos → las cifras de
 * decisión NO cambian (dorado intacto). Por eso esquiva el bloqueo de tipologías del formulario simple.
 */
export async function editarViabilidadYAprobar(
  input: EditarViabilidadInput,
): Promise<CrearProyectoResult> {
  let source;
  try {
    source = await getProjectSource(input.slug);
  } catch (e) {
    if (e instanceof WriteError) return { ok: false, status: e.status, message: e.message };
    throw e; // redirect() de 401 debe propagarse
  }
  if (!source) return { ok: false, status: 404, message: "No se encontró el proyecto." };

  const par = {
    ...source.par,
    due_diligence: input.dueDiligence,
    pot: input.pot,
    mercado: input.mercado,
  };
  // Reusa el flujo probado de edición (nueva versión → aprobar → revalidar), que recalcula con el motor.
  return editarYAprobarProyecto({ projectId: source.project_id, slug: input.slug, par });
}

// ---------- Editar tipologías (C·tipologías): edita la mezcla sin corromper cifras ----------

export interface EditarTipologiasInput {
  slug: string;
  tipologias: Record<string, unknown>[];
}

/**
 * Edita la TABLA de tipologías (mezcla de unidades por clase/etapa) creando una versión nueva. Lee el
 * `par` crudo del escenario vigente SERVER-SIDE y reemplaza SOLO la clave `tipologias`. CLAVE anti-bug
 * (2026-06-13): borra los DERIVADOS stale de cada etapa (ventas_miles / ventas_vivienda_miles /
 * ventas_adicional_miles / und) para que el motor (`normalizar_tipologias`) los re-derive de la tabla
 * nueva y no sobrevivan valores viejos. El resto del par viaja bit a bit; el motor es la única fuente de
 * derivación → las cifras las recalcula `aprobar()`. NO pasa por buildPar (origen de los bugs del CRUD).
 */
export async function editarTipologiasYAprobar(
  input: EditarTipologiasInput,
): Promise<CrearProyectoResult> {
  let source;
  try {
    source = await getProjectSource(input.slug);
  } catch (e) {
    if (e instanceof WriteError) return { ok: false, status: e.status, message: e.message };
    throw e; // redirect() de 401 debe propagarse
  }
  if (!source) return { ok: false, status: 404, message: "No se encontró el proyecto." };

  const par: Record<string, unknown> = { ...source.par, tipologias: input.tipologias };
  // Borrar derivados stale por etapa → el motor manda (re-deriva de la tabla nueva).
  const etapas = Array.isArray(par.etapas) ? (par.etapas as Record<string, unknown>[]) : [];
  for (const e of etapas) {
    delete e.ventas_miles;
    delete e.ventas_vivienda_miles;
    delete e.ventas_adicional_miles;
    delete e.und;
  }
  return editarYAprobarProyecto({ projectId: source.project_id, slug: input.slug, par });
}

// ---------- Administración: marcar real / eliminar proyecto (solo admin) ----------

export type MarcarRealResult =
  | { ok: true; es_real: boolean }
  | { ok: false; status: number; message: string };

/** Marca el proyecto como datos reales / ilustrativos (flag de proyecto; no toca cifras). Admin. */
export async function marcarProyectoReal(slug: string, esReal: boolean): Promise<MarcarRealResult> {
  try {
    const res = await setProjectReal(slug, esReal);
    revalidatePath("/");
    revalidatePath(`/proyectos/${slug}`);
    return { ok: true, es_real: res.es_real };
  } catch (e) {
    if (e instanceof WriteError) return { ok: false, status: e.status, message: e.message };
    throw e;
  }
}

export type EliminarProyectoResult =
  | { ok: true; slug: string; scenarios: number }
  | { ok: false; status: number; message: string };

/**
 * Borra un proyecto completo (escenarios + cache). El API revalida el JWT y EXIGE rol admin (gate
 * real); aquí solo orquestamos y traducimos el error. Irreversible: la UI exige confirmación.
 */
export async function eliminarProyecto(slug: string): Promise<EliminarProyectoResult> {
  try {
    const res = await deleteProject(slug);
    revalidatePath("/");
    revalidatePath("/pipeline");
    return { ok: true, slug: res.slug, scenarios: res.scenarios_borrados };
  } catch (e) {
    if (e instanceof WriteError) return { ok: false, status: e.status, message: e.message };
    throw e; // el redirect() de 401 debe propagarse
  }
}
