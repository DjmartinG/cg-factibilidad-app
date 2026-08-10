# Acta de re-baseline — Navarra Apartamentos: recalibración ago-2026

**Fecha:** 2026-08-09
**Proyecto:** Navarra Apartamentos · `1_navarra_REAL` (el proyecto DORADO)
**Fuente del cambio:** `par` recalibrado contra `08062026 FACTIBILIDAD NAVARRA_951aptos.xlsx` (fecha interna 14-abr-2026), hojas PREFACT X ETAPA / DATOS DE ENTRADA / Cronograma Proyecto / FC INVERSION.
**Estado:** ✅ **APROBADA por Martín (2026-08-09) y APLICADA** — opción «sin `inf_col` ni `vmes` 20». Rama `feat/rebaseline-navarra-ago2026`.

> **Alcance aprobado:** se aplicó el paquete **SALVO** los dos puntos de §5.1 y §5.2, que quedan **pendientes** y conservan su valor anterior:
> - `financiero.wacc.inf_col` se queda en **5,1** (input macro común a los 8 proyectos → va como re-baseline macro aparte, con fuente de IPC y no de ICCV).
> - `etapas[2].vmes` se queda en **15** und/mes (el ritmo de la Etapa 3 espera su escenario).
>
> Con eso el **WACC no se mueve (17,6614%)** y los **hitos de la Etapa 3 tampoco** (PE nov-2027, FV jun-2028). El diff baja de 97 a **84 rutas**.

---

## 0. Resumen en una línea

El P&G **total no se mueve** y las **cifras de decisión quedan intactas** (TIR proyecto 37,5975% · VPN@TIO $18.280.688 · TIR socio 41,7189%), pero se re-baselinean **4 anclas auditadas**, **84 rutas del snapshot dorado** y **2 goldens de la capa after-tax**, empujados sobre todo por el recaudo (cuota inicial y separación).

---

## 1. Lo que NO cambia (verificado, dif = 0)

| Cifra | Valor | Nota |
|---|---|---|
| **TIR proyecto** | **37,5975%** | idéntica — sale del override `fiducia.fcl_proyecto`, que no se toca |
| **VPN @TIO** | **$18.280.688** | idéntico |
| **TIR socio / equity** | **41,7189%** | idéntica |
| Total ingresos | $241.477.882 | idéntico |
| Costo lote | $29.104.859 | idéntico |
| Costos directos | $143.473.596 | idéntico (vienen de `directos_cap` bottom-up, que no cambia) |
| Costos indirectos | $34.253.206 | idéntico |
| Honorarios (total) | $23.283.887 | idéntico |
| Utilidad operativa | $11.362.333 | idéntica (dif COP 146, dentro de tolerancia) |
| Renta / UDI | $8.149.361 / $26.496.860 | idénticos |
| `fiducia_real` | `True` | idéntico |

Los **5 checks de cuadre pasan** antes y después (ingresos, recaudo=ingresos, flujo=utilidad, reparto, crédito).
Los otros tres proyectos **no se tocan**: sus dorados siguen verdes.

---

## 2. Qué mueve cada cifra (descomposición por factor, verificada)

Cada grupo se aplicó **aislado** sobre la base y la suma de los grupos reproduce el JSON propuesto **exacto** (control OK en las 6 métricas).

| # | Cambio | Qué mueve |
|---|---|---|
| **A** | **Reclasificar el local comercial** ($3.156.828) de «otros ingresos» a **ventas**, con `tipologias` de la Etapa 3 desagregadas (T4 139 + T4 tipo 3 20 + T5 158 + local) y `costos_pct` recalibrados sobre la base de ventas nueva | ventas **+$3.156.827 (+1,374%)**; `recon_codensa` **−$3.156.827 (−26,8%)**; exposición +$578.189; crédito máx −$668.301. **Total ingresos sin cambio.** |
| **B** | ~~`wacc.inf_col` 5,1 → 6,4~~ **NO APLICADO** (§5.1) | habría movido el WACC 17,6614% → 18,0943% (+0,43 pp), el valor creado −$481.761 y todas las métricas «reales». **Queda en 5,1.** |
| **C** | **Recaudo: `pct_ci` 30% → 9,18% y `sep_und_miles` $5.000 → $1.000** | **Exposición máxima −$19.431.513 (−27,4%)** ← el driver principal |
| **D** | Crédito: `tasa_credito_ea` 13% → 12,3%; `monto_cc_pct` 0,8 → `credito_cap_miles` $50.080.000 | sin efecto en los indicadores de decisión; sí en `flujo.credito_max` ($114,8 mil M → $50,08 mil M, el cupo ahora muerde) |
| **E** | Escalación: `ea_materiales` 6% → 2%, `ea_mano_obra` 12% → 13,3% (DANE ago-2026) | **no toca el P&G** (los directos son bottom-up), pero baja `distribucion.incremento` −40,5% y con eso el flujo desapalancado |
| **F** | ~~`vmes` Etapa 3: 15 → 20 und/mes~~ **NO APLICADO** (§5.2) | habría adelantado los hitos (PE nov-2027 → ago-2027, FV jun-2028 → dic-2027). **Queda en 15.** |
| **G** | Flags: `iva_en_operativo: true`, `vis_exime_honorarios: false`, `tir_apalancada_ref` 0,38 → 0,376 | **capa after-tax** (ver §5.3) |
| **H** | Cubetas de honorarios: `hon_construccion` 3,5% → 5%, `hon_ventas` 1,5% → 2% | `pyg.resultados` **$43,04 → $47,95 mil M (+11,4%)**; corrige que las cubetas sumaban 8% contra un total de 10,14% |

---

## 3. Anclas auditadas a re-baselinear (`engine/tests/test_anclas.py`)

```python
"proyectos_privados/1_navarra_REAL.json": {
    "util_oper": 11362333.116275,      # antes 11362332.97      (+COP 146, dentro de tolerancia)
    "margen_oper": 0.048799,           # antes 0.04947          (-0.0671 pp)   <-- RE-BASELINE
    "ventas": 232838874.450812,        # antes 229682047.11     (+1.374%)      <-- RE-BASELINE
    "ap_tir_proyecto": 0.375975,       # SIN CAMBIO
    "ap_vpn_proyecto": 18280687.66539, # SIN CAMBIO
    "ap_tir_equity": 0.417189,         # SIN CAMBIO
    "ap_credito_max": 48623715.502013, # antes 49292016.2       (-1.356%)      <-- RE-BASELINE
    "ap_fiducia_real": True,           # SIN CAMBIO
    "fl_tir_proyecto": 0.01585,        # antes -0.00329                        <-- RE-BASELINE
},
```

**4 anclas cambian de 9.** Las tres de decisión (TIR proyecto, VPN@TIO, TIR equity) se mantienen.

---

## 4. Snapshot dorado: alcance del diff

`1_navarra_REAL_snapshot.json` — **84 rutas / 1.544 celdas** cambian. Escalares más notorios:

| Ruta | Antes | Después | Δ |
|---|---|---|---|
| `apalancamiento.max_necesidad_caja` | −71.023.597 | **−89.620.308** | −26,2% |
| `apalancamiento.aportes_total` | 44.026.630 | **68.153.071** | +54,8% |
| `apalancamiento.credito_max` | 49.292.016 | 48.623.716 | −1,4% |
| `apalancamiento.credito_prom` | 29.959.056 | 29.339.601 | −2,1% |
| `apalancamiento.intereses_total` | 16.867.740 | 14.820.024 | −12,1% |
| `apalancamiento.iva_vis_devolucion` | 8.727.918 | **0** | −100% |
| `apalancamiento.carga_tributaria_neta_at` | 706.408 | **9.638.511** | +1.264% |
| `apalancamiento.vpn_at` | −2.272.616 | **−11.785.925** | −419% |
| `apalancamiento.tir_proyecto_at` | 13,71% | **9,31%** | −4,4 pp |
| `apalancamiento.tir_equity_at` | 17,58% | **11,11%** | −6,5 pp |
| `distribucion.incremento` | 17.000.441 | 10.111.045 | −40,5% |
| `flujo.credito_max` | 114.778.877 | 50.080.000 | −56,4% |
| `flujo.max_caja` | −133.393.793 | −169.651.500 | −27,2% |
| `pyg.ventas` | 229.682.047 | 232.838.874 | +1,4% |
| `pyg.recon_codensa` | 11.795.835 | 8.639.008 | −26,8% |
| `pyg.resultados` | 43.041.756 | 47.951.080 | +11,4% |
| `pyg.cg` / `pyg.socio` | 29.321.718 / 13.720.038 | 30.627.970 / 17.323.110 | +4,5% / +26,3% |
| `hitos.3.unidades` | 317 | 318 | el local comercial cuenta como unidad escriturable |

**Sin cambio (confirmado):** `apalancamiento.wacc` 17,6614% · `valor_creado` 15.102.627 · `hitos.3.PE` 2027-11-30 · `hitos.3.FV` 2028-06-30 — son las rutas que salieron del diff al excluir §5.1 y §5.2.

**Allowlist completo del test de gobernanza** (84 rutas):

Como este es un cambio de **DATO** (no de motor), el modo *recompute* de `diff_dorado.py` no sirve
—recalcula desde el `input_par` congelado en el snapshot—. Se usa el **modo dos-carpetas**: archivar
los snapshots viejos, regenerar y comparar.

```
apalancamiento.acumulado apalancamiento.anual.2022 apalancamiento.anual.2023 apalancamiento.anual.2024
apalancamiento.anual.2025 apalancamiento.anual.2026 apalancamiento.anual.2027 apalancamiento.anual.2028
apalancamiento.anual.2029 apalancamiento.anual.2030 apalancamiento.aportes_total
apalancamiento.carga_tributaria_neta_at apalancamiento.costos apalancamiento.credito_max
apalancamiento.credito_prom apalancamiento.flujo_equity apalancamiento.gmf_at apalancamiento.ingresos
apalancamiento.intereses_total apalancamiento.iva_vis_devolucion apalancamiento.max_necesidad_caja
apalancamiento.operativo apalancamiento.retorno apalancamiento.saldo_credito
apalancamiento.tir_apalancada_ref apalancamiento.tir_equity_at apalancamiento.tir_proyecto_at
apalancamiento.tir_proyecto_pre_mensual apalancamiento.vpn_at distribucion.acumulada
distribucion.escalada distribucion.incremento escenarios.Base.margen escenarios.Base.ventas
escenarios.Optimista.margen escenarios.Optimista.ventas escenarios.Pesimista.margen
escenarios.Pesimista.ventas flujo.acumulado flujo.costos flujo.credito_max flujo.flujo flujo.ingresos
flujo.intereses_total flujo.max_caja flujo.saldo_credito flujo.tir_apalancada_ref flujo.tir_proyecto
flujo.vpn_proyecto hitos.2.nombre hitos.3.unidades meta.corte_datos meta.fuente meta.socios pyg.cg
pyg.hon_construccion pyg.hon_gerencia pyg.hon_ventas pyg.incidencia_lote pyg.margen_oper
pyg.recon_codensa pyg.resultados pyg.socio pyg.ventas recaudo.cuota_inicial
recaudo.por_etapa.1.cuota_inicial recaudo.por_etapa.1.separacion recaudo.por_etapa.1.subrogacion
recaudo.por_etapa.1.total recaudo.por_etapa.2.cuota_inicial recaudo.por_etapa.2.separacion
recaudo.por_etapa.2.subrogacion recaudo.por_etapa.2.total recaudo.por_etapa.3.contrato_total
recaudo.por_etapa.3.cuota_inicial recaudo.por_etapa.3.entregas recaudo.por_etapa.3.separacion
recaudo.por_etapa.3.subrogacion recaudo.por_etapa.3.total recaudo.por_etapa.3.ventas
recaudo.separacion recaudo.subrogacion recaudo.total urbanistico.precio_m2_vend
```

**Resultado del gate:** `cambios esperados (en el acta): 1544; colaterales: 0` → **`[OK] cero colaterales`**, exit 0.
Verificado además, snapshot por snapshot, que **solo cambió `1_navarra_REAL`**: los otros 6 dieron
`result: 0 celdas / input_par: 0`.

---

## 4b. Goldens adicionales de la capa after-tax (no estaban en el borrador de esta acta)

Al correr la suite aparecieron **dos goldens más** que clavan cifras after-tax de Navarra y que el
borrador no había declarado. Se re-baselinean por la misma causa (§5.3):

**`engine/tests/test_vehiculos_tributario.py::_GOLDEN_NAVARRA`** — `tir_socio_at` y carga por vehículo:

| Vehículo | `tir_socio_at` antes → después | carga antes → después |
|---|---|---|
| fiducia (referencia) | 14,3556% → **11,1089%** | 9.434.326 → **9.638.511** |
| encargo / consorcio / UT / cuentas en participación / FCP | 14,3556% → **11,1089%** | 13.411.143 → **13.615.328** |
| sas_spv | 11,3699% → **8,1675%** | 20.922.140 → **23.743.740** |

La cifra **oficial** del comparador (`tir_proyecto_auditada` 37,5975%) **no se movió**, y los invariantes
económicos del test siguen: la SAS opaca carga más que un transparente, y salir de fiducia cuesta renta.

**`engine/tests/test_tributario_after_tax.py::test_aditivo_no_mueve_dorado_y_expone_at`** — afirmaba
`iva_vis_devolucion > 0` («Navarra es VIS → hay devolución»). Con `iva_en_operativo` el campo es **0 a
propósito**. El test se reescribió para cubrir **los dos regímenes**: con el flag, exige
`iva_vis_devolucion == 0` **y** `pyg.recon_codensa > 0` (la devolución sigue ahí, en el operativo); sin
el flag, exige `> 0` como antes. Queda más fuerte que la aserción original.

---

## 5. Los tres puntos que se separaron (§5.1 y §5.2 quedan PENDIENTES)

Lo demás del paquete es mejora de fidelidad y entró tal cual. Estos tres eran decisiones, no extracciones:

### 5.1 `inf_col` 5,1 → 6,4 — ⛔ **NO APLICADO. Pendiente como re-baseline macro.**

- Es un input **MACRO**, común a todos los proyectos. Los **8 JSON del repo están en 5,1**; moverlo solo en Navarra deja el portafolio con **dos inflaciones y dos WACC** para el mismo entorno macro → rompe la comparabilidad del mapa de valor y del EVA consolidado, y contradice lo que muestra la pestaña **/fuentes**.
- **No trae fuente.** El `_fuente` que sí cita DANE es de **ICCV/ICOCED** (índices de costo de construcción), que no son IPC. Y el propio JSON cita en otro bloque «**BanRep inflación 4,8% en 2027**» — es decir, se contradice internamente.
- **Propuesta:** dejar Navarra en 5,1 en este re-baseline y tratar la inflación como un **re-baseline macro aparte**, aplicado a los 8 proyectos a la vez y con su fuente. Eso saca del diff `apalancamiento.wacc`, `wacc_real`, `inflacion`, `tio_real`, `valor_creado`, `spread_valor`, `tir_*_real`, `flujo.wacc`.

### 5.2 `vmes` Etapa 3: 15 → 20 und/mes — ⛔ **NO APLICADO. Queda en 15.**

El propio `_nota` del JSON dice que **el resumen del Excel declara 12 und/mes y el histórico real del proyecto es ~9,2**, y cierra con «escenario de ritmo pendiente». Baselinear **20** (el más optimista de los tres números disponibles) y a la vez declarar el escenario pendiente es incoherente: adelanta el punto de equilibrio 3 meses y la finalización de ventas 6 meses sobre una etapa **que no tiene licencia ni ventas abiertas**.

### 5.3 `iva_en_operativo: true` — ✅ **APLICADO** (corrección real), pero hay que avisar

Corrige un **doble conteo del IVA**: `recon_codensa` ya incluía la devolución y la capa after-tax la volvía a sumar. Al corregirlo, las cifras after-tax caen fuerte: **VPN after-tax −$2,27 → −$11,79 mil M**, **TIR proyecto after-tax 13,71% → 9,31%** y **TIR socio after-tax 17,58% → 11,11%**. No es que el negocio empeore: estaba **sobreestimado**. Nada de esto toca la cifra pre-impuesto, que es la de decisión.

> **Pendiente de comunicación:** avisar al comité / a Jose Alfonso antes de que las cifras after-tax cambien en pantalla, y llevar el punto al asesor fiscal (gate tributario de la constitución).

### 5.4 Nota adicional (no bloquea) — el reparto de CG queda sobreestimado

El propio JSON lo documenta: el motor solo modela dos beneficiarios y Navarra tiene tres. Con el cambio, `pyg.cg` pasa a **$30,63 mil M** cuando el reparto real de CG es **$23,98 mil M** (la diferencia, $6,65 mil M, es la mitad de la utilidad del lote que le toca a V2K). Hoy ya está mal ($29,32 mil M), así que no es una regresión — pero si la ficha muestra ese número conviene una nota al pie, o postergarlo hasta tener el tercer socio en el motor.

---

## 6. Verificación

| Control | Resultado |
|---|---|
| El motor reproduce el P&G que el propio JSON declara (`_conciliacion_motor_excel`, 8 líneas) y el `retorno_motor` $47.951.080 | ✅ |
| Descomposición por factor: la suma de los 7 grupos aislados = JSON completo, exacto en las 6 métricas de control | ✅ |
| Gate de gobernanza `diff_dorado.py` (dos carpetas, tol. 0,1% rel / 1e-6 abs) con el allowlist de §4 | ✅ **1.544 esperados, 0 colaterales**, exit 0 |
| Solo cambió el snapshot de Navarra REAL (los otros 6: `result` 0 celdas, `input_par` 0) | ✅ |
| Los 5 checks de cuadre (ingresos, recaudo, flujo, reparto, crédito) pasan antes y después | ✅ |
| Suite del motor | ✅ **198 verdes** |
| Suite del API | ✅ **92 verdes** |
| `ruff check engine api` | ✅ limpio |
| `next build` del web | ✅ verde (no se tocó ningún archivo de `web/`) |
| Campos nuevos (`directos_cap`, `credito_cap_miles`, `vis_exime_honorarios`, `iva_en_operativo`, `supuestos_smmlv`) soportados por el motor / admitidos como extra por `schema.py` | ✅ |

**Nota de método:** los 3 snapshots ilustrativos commiteados se restauraron tras regenerar — el
regenerador reescribe el orden de las claves (mismos valores) y ese ruido no pertenece a este cambio.

---

## 7. Lo que sigue

1. **PR** de la rama `feat/rebaseline-navarra-ago2026` con esta acta; Martín mergea con el gate verde.
2. **Prod:** es cambio de **DATO**, no de motor → **no requiere redeploy del API**; hay que **refrescar el
   escenario** en Supabase con `db/refresh_scenarios.py` (crea una versión nueva aprobada; el snapshot
   anterior es inmutable). El gate dorado del script aborta antes de escribir si las cifras no reproducen.
3. **Avisar** del cambio en las cifras after-tax (§5.3) antes de que aparezca en la ficha.

### Pendientes que este re-baseline deja abiertos

| # | Pendiente | Origen |
|---|---|---|
| 1 | **Re-baseline macro de la inflación** sobre los 8 proyectos, con fuente de IPC (no ICCV) | §5.1 |
| 2 | **Escenario de ritmo de la Etapa 3** con los tres valores disponibles (20 / 12 / 9,2 und/mes) | §5.2 |
| 3 | **Validación del asesor fiscal** de la capa after-tax VIS | §5.3 |
| 4 | **Tercer socio en el motor** — hoy `pyg.cg` sobreestima el reparto de CG en $6,65 mil M | §5.4 |
| 5 | **Re-extraer el flujo** de `FLUJO MENSUAL DE FONDOS`: el propio JSON lo marca como pendiente (sobre-amortiza $11.952.762 y tiene seis plugs manuales por $9.505.942) | `fiducia._nota` |
| 6 | Los siete errores del modelo fuente y los escenarios de salario mínimo del informe interno Etapa 4 | `disclaimer` |

---

## 8. Decisión registrada

**Martín, 2026-08-09:** aprobado **sin `inf_col` y sin `vmes` 20** (§5.1 y §5.2 quedan pendientes).
El resto del paquete se aplicó.
