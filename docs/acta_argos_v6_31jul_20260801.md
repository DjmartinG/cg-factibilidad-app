# Acta — Argos-CVP: prefactibilidad 31-jul-2026 (lote a 8%, util oper 13.10%) + carga v6

**Fecha:** 2026-08-01
**Proyecto:** Argos (CVP/RenoBo) · slug `4_argos_cvp_REAL` · VIS · prefactibilidad
**Fuente:** Excel `31072026 PREFACTIBILIDAD PREDIO ARGOS 20 pisos1420_Conaltura.xlsx` + `Cronograma inicial Argos.xlsx` (ZIP `Modelo Argos 1082026`)
**Alcance:** mueve cifras de **UN** proyecto (Argos). **Dorado de Navarra/Dominica/Torres INTACTO** (28 tests verdes).
**Estado:** ✅ **APROBADA por Martín ("adelante") y APLICADA** (2026-08-01). `scenarios v6 approved` en prod.

---

## Qué cambia (el negocio cambió sustancialmente)

Nueva prefactibilidad (31-jul). El cambio de fondo: **la incidencia del lote baja de 11% a 8%** (mejor negocio del lote; sigue pagado 50% en especie/VIP + 50% dinero) y suben las ventas → la **utilidad operativa casi se duplica**.

### P&G (calibrado al Excel) — v5 (prod) → **v6**

| Concepto | v5 (26-jul) | **v6 (31-jul)** |
|---|---:|---:|
| Ventas | 469.3 mil M | **503.2 mil M** |
| Total ingresos | 103.80% | 103.80% |
| Costo directo | 59.31% | **57.64%** |
| Indirectos | 15.97% | **15.06%** |
| Honorarios | 10.00% | 10.00% |
| **Lote** | **11.00%** | **8.00%** |
| **Utilidad operativa** | **7.53% ($35.3)** | **13.10% ($65.9 mil M)** |
| Renta (VIS exento) | 0 | 0 |

## Flujo — ahora SÍ reconcilia (ya no provisional) ✅

A diferencia de v5 (flujo quedado), el FC INVERSION del 31-jul se recalculó de verdad:

- Flujo = `FC INVERSION` fila 20 "FCL", anualizado (2025-2035), suma **+88.48 mil M**.
- **Los positivos del flujo (~115 mil M) reconcilian con los reintegros del P&G (116.2)** → refleja el nuevo P&G.
- **TIR proyecto 28.04%** (v5 30.02%) — MENOR aunque la utilidad subió, porque el cronograma nuevo (4-6 etapas/torres) deja el grueso del flujo en **2034-2035** (back-loaded). Es realista.
- VPN@TIO **+15.51** · VPN@WACC 17.66% **+10.61** · TIR 28.04% > WACC → **GENERA VALOR**.

→ Se retiró la advertencia de "flujo provisional / Jose Alfonso": esta versión reconcilia.

## Verificación (gate local — verde)

- P&G reproduce el Excel: **util operativa 13.10% ($65.93 mil M)**, ventas 503.2, lote 8%, renta 0.
- After-tax = titular (VIS exento). Socio CG: TIR None. **5/5 checks verdes.**
- **Dorado de los otros 3: INTACTO.**
- **DRY-RUN → v6 approved** (TIR 28.04%).

## Cronograma

`Cronograma inicial Argos.xlsx`: línea de tiempo por **4-6 etapas (torres)** — Comercialización → Cuotas iniciales → Punto de equilibrio → Construcción → Escrituración → Entrega, + proyección SMMLV y costos/m². Es la fuente del timing back-loaded que ya viaja en el flujo. (La pestaña Cronograma de la ficha se puede actualizar en un paso aparte; TIR/VPN salen del flujo auditado igual.)

## Pendientes

- Validación fiscal VIS con asesor · TdR oficial de Argos (SECOP II) · costos bottom-up reales.
- Opcional: reflejar las 4-6 etapas del cronograma nuevo en la pestaña Cronograma de la ficha.
