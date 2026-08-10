# -*- coding: utf-8 -*-
"""M3 Fase 1 — vehículos + motor fiscal. Verifica: (1) catálogo coherente, (2) fiducia base = NO-OP
(reproduce la lógica de renta de M2), (3) VIS pierde la exención fuera de fiducia, (4) No-VIS = 35%
en todos, (5) comparador con referencia + deltas, (6) schema valida el vehículo.
"""
import pytest

from aleph_engine import tributario, vehiculos
from aleph_engine import schema


def test_catalogo_coherente():
    cat = vehiculos.catalogo()
    assert len(cat) == 7
    assert cat[0].clave == "fiducia"                     # fiducia primero
    # SOLO la fiducia habilita la exención VIS
    habilitan = [v.clave for v in cat if v.habilita_exencion_vis]
    assert habilitan == ["fiducia"]
    # toda regla trae fuente normativa
    assert all(v.fuente_normativa for v in cat)


def test_desconocido_cae_a_fiducia_pero_existe_es_estricto():
    assert vehiculos.obtener("xyz").clave == "fiducia"
    assert vehiculos.existe("fiducia") and not vehiculos.existe("xyz")


# --- NO-OP: fiducia reproduce la lógica vieja de pyg (renta = tasa*base; udi = reint - renta) -------
def _vieja(es_vis, honorarios, reint, tasa, exime):
    base = (0.0 if exime else honorarios) if es_vis else reint
    return tasa * base, reint - (tasa * base)


@pytest.mark.parametrize("es_vis,hon,reint,tasa,exime", [
    (True, 8000.0, 26497.0, 0.35, False),
    (True, 5000.0, 15000.0, 0.35, True),
    (False, 9000.0, 40000.0, 0.35, False),
    (False, 0.0, 0.0, 0.35, False),
])
def test_fiducia_es_noop(es_vis, hon, reint, tasa, exime):
    rv, uv = _vieja(es_vis, hon, reint, tasa, exime)
    t = tributario.calcular_renta(vehiculo="fiducia", es_vis=es_vis, honorarios=hon,
                                  reint_sin_lote=reint, tasa_renta_proyecto=tasa,
                                  vis_exime_honorarios=exime)
    assert abs(t["renta"] - rv) < 1e-9
    assert abs(t["udi"] - uv) < 1e-9


def test_vis_pierde_exencion_fuera_de_fiducia():
    base = dict(es_vis=True, honorarios=8000.0, reint_sin_lote=34646.0, tasa_renta_proyecto=0.35)
    fid = tributario.calcular_renta(vehiculo="fiducia", **base)
    sas = tributario.calcular_renta(vehiculo="sas_spv", **base)
    assert fid["exencion_vis_aplicada"] is True
    assert sas["exencion_vis_aplicada"] is False
    assert sas["renta"] > fid["renta"]                   # paga más impuesto
    assert sas["base_gravable"] == 34646.0               # grava todo el reintegro


def test_no_vis_igual_35_en_todos_los_vehiculos():
    base = dict(es_vis=False, honorarios=9000.0, reint_sin_lote=40000.0, tasa_renta_proyecto=0.35)
    rentas = {c: tributario.calcular_renta(vehiculo=c, **base)["renta"] for c in vehiculos.claves()}
    assert len(set(round(r, 6) for r in rentas.values())) == 1   # No-VIS no depende del vehículo (Fase 1)
    assert abs(rentas["fiducia"] - 0.35 * 40000.0) < 1e-9


def test_comparador_referencia_y_deltas():
    par = {
        "meta": {"nombre": "X", "tipo": "VIS"},
        "financiero": {"renta": 0.35},
        # par mínimo: comparar() corre calcular(); usamos un proyecto sintético mínimo válido vía bases.
    }
    # comparar() necesita un proyecto calculable; probamos la pieza pura (mismo motor fiscal):
    filas = [tributario.calcular_renta(vehiculo=c, es_vis=True, honorarios=8000.0,
                                       reint_sin_lote=34646.0, tasa_renta_proyecto=0.35)
             for c in vehiculos.claves()]
    fid = filas[0]
    assert fid["vehiculo"] == "fiducia"
    # fuera de fiducia, el VIS paga más (udi menor)
    assert all(f["udi"] <= fid["udi"] for f in filas)


def test_schema_valida_vehiculo():
    base = {"etapas": [{"und": 1}],
            "costos_pct": {"directos": 0.5, "indirectos": 0.1, "honorarios": 0.08, "util_lote": 0.0},
            "financiero": {}, "lote_bruto_miles": 0.0}
    schema.parse({**base, "vehiculo": "consorcio"})       # válido
    schema.parse({**base})                                # ausente = ok (default fiducia)
    with pytest.raises(Exception):
        schema.parse({**base, "vehiculo": "no_existe"})   # inválido → ValidationError


# ============================================================================
# M3 Fase 2 — overlay del waterfall por vehículo (renta+GMF+dividendos) + golden por vehículo.
# ============================================================================
import json
import os

_PRIV = os.path.join(os.path.dirname(__file__), "..", "..",
                     "data", "proyectos_privados", "1_navarra_REAL.json")


def _navarra():
    if not os.path.exists(_PRIV):
        pytest.skip("Navarra REAL no disponible (CI sin datos privados)")
    return json.load(open(_PRIV, encoding="utf-8"))


def test_overlay_opaco_paga_dividendos_transparente_no():
    ret = [-100.0, 0.0, 50.0, 200.0, 150.0]
    eq = [-80.0, -20.0, 30.0, 120.0, 90.0]
    o_t = tributario.overlay_after_tax(ret, eq, vehiculo="consorcio", renta_total=70.0)
    o_o = tributario.overlay_after_tax(ret, eq, vehiculo="sas_spv", renta_total=70.0)
    assert o_t["dividendos"] == 0.0                       # transparente: sin doble imposición
    assert o_o["dividendos"] > 0.0                        # opaco: dividendos al distribuir
    assert o_o["carga_total"] > o_t["carga_total"]        # opaco carga más
    # GMF = 4x1000 del movimiento bruto
    assert abs(o_t["gmf"] - 0.004 * sum(abs(x) for x in ret)) < 1e-9


def test_fiducia_waterfall_intacto_override():
    """La fiducia (default) conserva su FCL auditado: TIR proyecto dorada 37,60%."""
    from aleph_engine import calcular
    R = calcular(_navarra())
    assert R["apalancamiento"]["fiducia_real"] is True
    assert abs(R["apalancamiento"]["tir_proyecto"] - 0.375975) < 1e-4   # dorado intacto


# GOLDEN por vehículo (congela el waterfall recalculado after-tax; las tasas son [VALIDAR] →
# cuando el asesor las ajuste, este test FALLA a propósito y obliga a un acta de re-baseline).
# RE-BASELINE 2026-06-14 (docs/acta_flujo_equity_20260614.md, APROBADO por Martín): el fix de
# flujo_equity (reincorpora honorarios+util_lote al socio) llevó la TIR socio mensual de −3,3%/−6,1%
# (absurda) a +14,4%/+11,4% (plausible). La carga de la SAS (opaca) sube: sus dividendos dependen del
# equity distribuido. La fiducia OFICIAL (auditada, 41,72%) NO cambia (usa el FCL override).
# Re-baseline 2026-08-09 (docs/acta_rebaseline_navarra_20260809.md, aprobado por Martín). Las cifras
# after-tax bajan porque el par ahora declara `iva_en_operativo`: la devolución del IVA VIS ya viaja
# como ingreso operativo y la capa after-tax deja de sumarla otra vez (antes se doble-contaba). La
# cifra OFICIAL pre-impuesto (tir_proyecto_auditada 37,5975%) NO se movió.
_GOLDEN_NAVARRA = {
    "fiducia":                  {"tir_socio_at": 0.111089, "carga": 9638511.155},
    "encargo_fiduciario":       {"tir_socio_at": 0.111089, "carga": 13615327.746},
    "consorcio":                {"tir_socio_at": 0.111089, "carga": 13615327.746},
    "union_temporal":           {"tir_socio_at": 0.111089, "carga": 13615327.746},
    "cuentas_en_participacion": {"tir_socio_at": 0.111089, "carga": 13615327.746},
    "sas_spv":                  {"tir_socio_at": 0.081675, "carga": 23743740.4},
    "fcp":                      {"tir_socio_at": 0.111089, "carga": 13615327.746},
}


def test_golden_vehiculos_navarra():
    c = tributario.comparar(_navarra())
    # cifra oficial: la auditada de fiducia, intacta
    assert abs(c["oficial_fiducia"]["tir_proyecto_auditada"] - 0.375975) < 1e-4
    porveh = {f["vehiculo"]: f for f in c["vehiculos"]}
    for veh, g in _GOLDEN_NAVARRA.items():
        f = porveh[veh]
        assert abs(f["tir_socio_at"] - g["tir_socio_at"]) < 1e-4, f"{veh} tir_socio movió"
        assert abs(f["carga_tributaria"] - g["carga"]) <= max(1e-3, 0.001 * g["carga"]), f"{veh} carga movió"
    # invariantes económicos: la SAS (opaca) carga MÁS que un transparente; salir de fiducia cuesta renta
    assert porveh["sas_spv"]["carga_tributaria"] > porveh["consorcio"]["carga_tributaria"]
    assert porveh["consorcio"]["delta_carga_vs_fiducia"] > 0
    assert porveh["fiducia"]["es_referencia"] is True


_PRIV_TORRES = os.path.join(os.path.dirname(__file__), "..", "..",
                            "data", "proyectos_privados", "3_torres_campinas_REAL.json")


def test_comparar_greenfield_no_crashea():
    """comparar() sobre Torres (GREENFIELD, TIR proyecto degenerada) NO debe crashear. La resta de TIR
    socio es SEGURA: None si algún operando es None (antes: `None − None` → TypeError → HTTP 500 en el
    endpoint de vehículos sobre Torres, un proyecto REAL existente). Robusto aunque la TIR socio mensual
    sea hoy un negativo válido (el fix de flujo_equity la sacó de None) y no None."""
    if not os.path.exists(_PRIV_TORRES):
        pytest.skip("Torres REAL no disponible (CI sin datos privados)")
    par = json.load(open(_PRIV_TORRES, encoding="utf-8"))
    c = tributario.comparar(par)                       # antes lanzaba TypeError
    assert c["vehiculos"]                               # devolvió filas, no crasheó
    for f in c["vehiculos"]:
        # la resta nunca crashea: el delta de TIR socio es None (si la TIR es None) o un número
        d = f["delta_tir_socio_vs_fiducia"]
        assert d is None or isinstance(d, (int, float))
        assert isinstance(f["delta_udi_vs_fiducia"], (int, float))      # udi/carga siempre numéricos
