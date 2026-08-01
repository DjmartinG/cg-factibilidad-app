# Acta — Argos-CVP: cronograma réplica (6 etapas × 6 fases) + Gantt enriquecido — v7

**Fecha:** 2026-08-01
**Proyecto:** Argos (CVP/RenoBo) · slug `4_argos_cvp_REAL`
**Fuente:** `Cronograma inicial Argos.xlsx` (hoja "Cronograma Proyecto"), ZIP `Modelo Argos 1082026`
**Alcance:** replica el cronograma de financiero en la ficha. **Cifras de DECISIÓN sin cambio** (P&G util oper 13.10%, TIR 28.04%, VPN — salen del flujo auditado/fiducia; el cronograma no las toca). **Dorado de los otros 3 INTACTO** (28 tests verdes).
**Estado:** ✅ **APROBADA por Martín ("adelante") y APLICADA** (2026-08-01). `scenarios v7 approved`.

---

## Qué cambia

Réplica **tal cual** del cronograma: **6 etapas** (ETAPA 1 = Torre 1,2), cada una con sus **6 fases** con fechas exactas del Excel:

| Etapa | Comercialización | Equilibrio | Construcción | Escrituración | Entrega |
|---|---|---|---|---|---|
| 1 (276 und) | jul-27 → nov-28 | jul-28 | ago-28 → mar-30 | mar-30 | sep-30 |
| 2 (198) | oct-28 → nov-29 | ago-29 | mar-30 → may-31 | may-31 | ago-31 |
| 3 (158) | oct-29 → jul-30 | jun-30 | may-31 → jun-32 | jun-32 | oct-32 |
| 4 (276) | ago-30 → feb-32 | ago-31 | mar-32 → ago-33 | ago-33 | ene-34 |
| 5 (236) | feb-32 → jun-33 | ene-33 | jul-33 → oct-34 | ago-34 | dic-34 |
| 6 (276) | jun-33 → dic-34 | may-34 | oct-34 → mar-36 | mar-36 | ago-36 |

(1.420 und = suma de la hoja Macros.) **Hitos del motor calzan al mes con el Excel (6/6); escrituración y entrega, 6/6.**

## Cómo se implementó (3 capas)

- **Motor (par, gitignored):** 6 etapas datadas (`fecha_inicio`, `vmes`, `pe_pct`, `dur_obra`, `ic_offset`) que reproducen IV/PE/FV/IC/FC exactos, + offsets nuevos `escrituracion`/`entrega` por etapa. Ventas 503.2 y fiducia (TIR) intactas.
- **API (`build.schedule`, ADITIVO):** expone `esc_mes`, `ent_mes`, `cuo_fin_mes` (fin de cuotas = hasta escrituración) por etapa, calculados de los offsets + IV. No toca `calcular()` ni el dorado.
- **Web:** Gantt reescrito a componente HTML/CSS (tokens de ALEPH) fiel al preview aprobado: 6 fases (Comercialización + Construcción como barras; Equilibrio/Escrituración/Entrega como marcas; Cuotas iniciales como línea sutil), **cuadrícula por trimestres**, **línea de HOY dinámica** y **guía de mes que sigue el cursor**. Token `--gantt-hoy` (terracota) en `globals.css`.

## Verificación

- engine dorado 28 verdes · api 88 verdes · web `next build` verde · ruff limpio.
- schedule: escrituración/entrega **6/6 exactas** vs Excel.
- DRY-RUN → v7 approved (TIR 28.04%).

## Pendientes

- Redeploy del API (para `esc_mes`/`ent_mes` en prod; el Gantt degrada limpio hasta entonces).
- Validación fiscal VIS · TdR oficial (SECOP II) · costos bottom-up.
