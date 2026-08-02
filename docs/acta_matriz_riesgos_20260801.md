# Acta — Matriz de riesgos (probabilidad × impacto) en la ficha · Fase 1

**Fecha:** 2026-08-01
**Alcance:** enriquecer el registro de riesgos existente (`due_diligence`) con **probabilidad** y una **matriz visual probabilidad × impacto** en la pestaña Viabilidad. **Aditivo — `calcular()` no lo toca → dorado INTACTO** (todos los proyectos, incluidas las anclas de Navarra).
**Estado:** rama `feat/matriz-riesgos` → PR (Martín mergea con el gate verde).

---

## Qué cambia (3 capas)

- **Motor** (`due_diligence.py`, aditivo): cada riesgo gana `probabilidad` (alta/media/baja) y `severidad` = probabilidad × impacto (pesos 3/2/1; producto ≥6 alto, 3–4 medio, ≤2 bajo). Nuevo `severidad_resumen` = conteo por severidad de los riesgos **calificados y abiertos**. Se agrega el frente **"comercial / mercado"** + 2 ítems de plantilla (absorción, precio vs competencia). `calcular()` sigue ignorando el bloque → dorado intacto.
- **API**: sin cambio de código — `build.due_diligence` ya devuelve `due_diligence.evaluar(par)` tal cual; los campos nuevos fluyen solos (requiere **redeploy del API** para el motor nuevo; el web degrada limpio mientras tanto).
- **Web** (pestaña Viabilidad): **matriz 3×3** (probabilidad Y × impacto X), celdas teñidas por severidad (verde/ámbar/rojo = estado, legítimo aquí), cada riesgo como punto numerado con tooltip, + leyenda ordenada por severidad con su mitigación. Tipos `probabilidad`/`severidad`/`severidad_resumen` en `api.ts`.

## Decisión de diseño clave

La matriz y el `severidad_resumen` **solo ubican riesgos CALIFICADOS por el analista** (`del_analista=True`). Los ítems de la plantilla que aún no se revisaron (pendientes, `del_analista=False`) toman probabilidad "media" por defecto y **falsearían** el mapa (aparecerían como "alto" sin que nadie los evaluara). Quedan como pendientes en el checklist (`veredicto.n_pendientes`), no en la matriz. La matriz refleja el **registro real de riesgos**, no el backlog sin evaluar.

## Registro de riesgos de Argos (sembrado, validado con Martín)

8 riesgos (suelo **BAJO** por experiencia en Navarra). Abiertos calificados: **4 altos** (absorción, TdR pendiente, exención renta VIS, cesión parque año 28), **2 medios** (crédito constructor, valoración lote en especie), **1 bajo** (acuerdo Conaltura). El par (`4_argos_cvp_REAL.json`) es **gitignored** → se sube a prod con `db/push_proyecto.py --apply` (lo corre Martín).

## Verificación

- engine **suite completa verde** incl. dorado (TIR Argos 28.04% intacta) · ruff limpio.
- web: `tsc` + `eslint` + `next build` verdes.
- +4 tests nuevos de due_diligence (severidad, probabilidad inválida→media, resumen ignora plantilla no calificada).

## Rollout

1. Merge del PR → web auto-despliega en Vercel.
2. **Redeploy del API** (`az acr build` tag=SHA) para el motor con `probabilidad`/`severidad`.
3. **Push del par de Argos** a Supabase (`push_proyecto.py --apply`) para los riesgos reales.
   El web degrada limpio hasta (2)+(3): sin datos calificados, la matriz no aparece y se ve el checklist como antes.

## Pendiente / Fase 2

- Captura/edición de riesgos en el Ingreso de datos (/web admin) — hoy se LEE del par.
- **Abanico macro forward** (inflación / tasa / TRM proyectadas) — la 2ª mitad de lo que pidió Martín.
