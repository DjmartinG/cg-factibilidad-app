# Acta — Escenarios macro (abanico forward) en Fuentes · Fase 2

**Fecha:** 2026-08-02
**Alcance:** nueva sección "Escenarios macro" en la página **Fuentes y metodología**: inflación, tasa (IBR) y TRM proyectadas 2026–2036 como **cono de incertidumbre** (banda baja / base / alta). **Aditivo y PURO — `calcular()` no lo importa → dorado INTACTO.** El motor financiero NO lo consume: es contexto de portafolio.
**Estado:** rama `feat/escenarios-macro` → PR (Martín mergea con el gate verde).

---

## Enfoque (honesto — regla del proyecto: no fabricar precisión)

- **Senda base anclada a lo real:** valor de HOY = **dato vivo de Banrep** (TRM, IBR) cuando responde, o la **meta oficial** (inflación → 3%). Etiqueta "dato vivo" vs "supuesto" por variable.
- **Bandas = escenarios del comité `[POR VALIDAR]`**, en un cono que se **ensancha con el tiempo** (cerca hay visibilidad, lejos no). NO se presenta como pronóstico de una fuente.
- Robusto: si Banrep no responde, esa variable usa su default grounded (degrada limpio).

## Supuestos sembrados (para validar con el comité)

| Variable | Hoy | Senda base | Banda 2036 |
|---|---|---|---|
| Inflación | 5,1% | → 3,0% (meta Banrep) en ~2028 | [0,1% .. 5,9%] |
| Tasa (IBR) | 9,25% (o vivo) | → ~6,0% (neutral) en ~2028 | [1,5% .. 10,5%] |
| TRM | ~$4.000 (o vivo) | drift +2%/año | [$3.755 .. $5.997] |

## Capas

- **Motor** (`macro_forward.py`, puro): `proyectar(anio_inicio, horizonte, anclas)` → por variable, `puntos=[{anio, base, bajo, alto}]`. Trayectoria converge (inflación/tasa) o drift (TRM); banda que crece. `anclas` clava el punto inicial al dato vivo. +7 tests.
- **API** (`fuentes_live.abanico_macro` + `GET /v1/fuentes/forward`): arma `anclas` de `banrep_trm()`/`banrep_ibr()` (IBR normaliza % → ratio) y delega al motor. Cacheado por día vía los cachés de Banrep. +3 tests (fetch falso, sin red).
- **Web** (`/fuentes`): sección "Escenarios macro" con 3 **fan charts** (ECharts, banda sombreada = área apilada) + badges dato vivo/supuesto + fuente. Degrada limpio si el API no expone el endpoint.

## Verificación

- engine: suite completa verde **incl. dorado** · ruff limpio · +7 tests macro_forward.
- api: suite verde · +3 tests · ruff limpio.
- web: `tsc` + `eslint` + `next build` verdes.

## Rollout

1. Merge → web auto-despliega (sección **oculta** hasta el redeploy del API — degrada limpio).
2. **Redeploy del API** (`az acr build` tag=SHA) para `/v1/fuentes/forward`.

## Pendiente / futuro

- **Validar los supuestos de banda/trayectoria con el comité** (hoy `[por validar]`).
- Anclar inflación a un dato vivo (DANE) — hoy usa la meta Banrep como base.
- Fase 3 (opcional): conectar el escenario macro a la **sensibilidad del proyecto** (si la inflación corre +Xpp, ¿cómo se mueve el WACC / el veredicto de valor?).
