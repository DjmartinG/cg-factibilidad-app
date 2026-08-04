# Acta — Opciones reales por etapa (fasing) en la ficha

**Fecha:** 2026-08-02
**Alcance:** pestaña nueva **"Etapas"** en la ficha: retrasar / acelerar (ritmo) / quitar cada etapa y ver el impacto en caja, exposición y retorno. La pregunta #1 del desarrollador para un proyecto multietapa.
**Estado:** rama `feat/opciones-etapas` → PR (Martín mergea con el gate verde).

---

## Enfoque (honesto)

Como el Simulador, **suelta el override de fiducia** (`par['fiducia']`, la TIR auditada es fija y no respondería al fasing) → **TIR/VPN DIRECCIONALES** (base mensual); el **margen y la CAJA** (exposición, crédito, timeline) son **EXACTOS**. La cifra oficial de TIR/VPN sigue siendo la de Resumen (fiducia auditada). Banner claro en la pestaña.

**Aditivo:** reusa `modelo.calcular` sobre una COPIA modificada; NO toca `calcular()` → **dorado intacto**.

## Capas

- **Motor** (`opciones.py`, puro): `correr_escenario(par, mods)` — deep-copy, suelta fiducia, aplica `mods={cod:{delay, ritmo_factor, quitar}}` (retrasa `fecha_inicio`, escala `vmes`, excluye la etapa) y re-corre. Devuelve indicadores + serie de caja + `inicio_offset` (para alinear el timeline). `etapas_info` lista las etapas para los controles. +6 tests (no muta el par, quitar reduce unidades, retrasar desplaza el inicio, quitar-todas = vacío).
- **API** (`build.opciones` + `POST /v1/scenarios/{id}/opciones`): etapas + base + resultado + base_date. +1 test.
- **Web** (pestaña "Etapas"): por etapa, control de **Retrasar** (0–24 m) + **Ritmo** (0,5–1,5×) + **Quitar**; KPIs base vs escenario (unidades, margen, TIR/VPN dir., exposición, crédito) con delta; **timeline de caja base vs escenario** (overlay, reusa el patrón del flujo). Server Action `evaluarOpciones` (token server-side).

## Verificación

- engine: suite completa verde **incl. dorado** · ruff limpio · +6 tests.
- api: suite verde · +1 test · ruff limpio.
- web: `tsc` + `eslint` + `next build` verdes.
- Sanity Argos: base 1.420 und / margen 13,1% / exp −106,9; quitar etapas 5+6 + retrasar 3 → 908 und / 8,6% / exp −114,2 (valle más hondo). ✓

## Rollout

1. Merge → web auto-despliega (la pestaña degrada limpio: si el API no expone `/opciones`, el fetch falla y queda "Cargando…").
2. **Redeploy del API** (`az acr build` tag=SHA) para `/v1/scenarios/{id}/opciones`.

## Pendiente / futuro

- Opcional Fase 3: valor de la flexibilidad formal (opción de abandono/deferimiento con probabilidades) — hoy es un explorador de escenarios de fasing (determinista), no una valoración de opción.
