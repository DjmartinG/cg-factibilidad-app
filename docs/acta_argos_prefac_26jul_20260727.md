# Acta — Argos-CVP: prefactibilidad 26-jul-2026 (lote 50% especie/dinero) + carga v5

**Fecha:** 2026-07-27
**Proyecto:** Argos (CVP/RenoBo) · slug `4_argos_cvp_REAL` · VIS · prefactibilidad
**Fuente:** Excel `26072026 PREFACTIBILIDAD PREDIO ARGOS 20 pisos1420_Conaltura.xlsx`
**Alcance:** mueve cifras de **UN** proyecto (Argos). **Dorado de Navarra/Dominica/Torres INTACTO** (verificado, 28 tests verdes).
**Estado:** ⚠️ **NO APROBADA.** Requiere el OK explícito de Martín ANTES de `--apply`.

---

## Qué cambia

Nueva versión de prefactibilidad de Argos. **Cambio de negocio:** el **lote se paga 50% en especie (unidades VIP construidas para Hábitat) + 50% en dinero** (antes: distinto esquema). Esto **mejora el P&G** (menos financiación → costos financieros más bajos) y sube la utilidad operativa.

### P&G (calibrado al Excel) — v4 (en prod) → **v5**

| Concepto | v4 (24-jun) | **v5 (26-jul)** |
|---|---:|---:|
| Ventas | 459.5 mil M | **469.3 mil M** |
| Total ingresos | 103.80% | 103.80% |
| Costo directo | 60.57% | **59.31%** |
| Indirectos | 17.60% | **15.97%** (financieros 5.96→4.40%) |
| Honorarios | 10.00% | 10.00% |
| Lote | 11.00% | 11.00% |
| **Utilidad operativa** | **4.63% ($21.3 mil M)** | **7.53% ($35.3 mil M)** |
| Renta (VIS exento) | 0 | 0 |

## ⚠️ ADVERTENCIA — FLUJO PROVISIONAL (para Jose Alfonso, Director Nacional de Proyectos)

**El flujo de caja del Excel (hoja `FC INVERSION`, fila 20 "FCL") NO refleja el nuevo P&G.** La utilidad operativa subió +14 mil M (a 7.53%), pero el flujo apenas se movió:

| | v4 | v5 (fila 20 del nuevo Excel) |
|---|---:|---:|
| Suma FCL | +84.1 mil M | +85.1 mil M |
| TIR proyecto | 29.81% | **30.02%** |
| VPN@WACC 17.66% | +11.7 | +12.0 (GENERA VALOR) |

**El flujo debe recalcularse** para incorporar el esquema 50% especie / 50% dinero. Hasta entonces, la TIR/VPN de Argos en ALEPH quedan **PROVISIONALES** (basadas en un flujo que no cuadra con el P&G). Esta advertencia queda visible en el **banner de la ficha** (disclaimer del proyecto).

**Acción pendiente de Jose Alfonso:** ajustar/recalcular el flujo de caja del proyecto en el Excel (FC INVERSION) para que refleje el nuevo P&G y el esquema de pago del lote; luego se re-carga.

## Verificación (gate local — verde)

- P&G reproduce el Excel: **util operativa 7.53% ($35.32 mil M)**, ventas 469.3, directos 59.31%, indirectos 15.97%, lote 11%, renta 0.
- After-tax = titular (VIS exento). Socio CG: TIR None. **5/5 checks verdes.**
- **Dorado de los otros 3: INTACTO.**
- **DRY-RUN `push_proyecto.py`:** crearía `scenarios v5 approved` (TIR 30.02%).

## Acción para Martín (tras aprobar)

```
python db/push_proyecto.py --apply     # ESCRIBE v5 approved en Supabase (prod)
```

Rollback: el v4 queda inmutable.

## Pendientes

- **Ajuste del flujo por Jose Alfonso** (lo principal — ver advertencia arriba).
- Validación fiscal VIS con asesor · TdR oficial (SECOP II) · costos bottom-up reales.
