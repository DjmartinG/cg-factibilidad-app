# -*- coding: utf-8 -*-
"""C1 · capa after-tax de DECISIÓN (aditiva). Verifica: (1) VIS suma devolución de IVA y No-VIS no;
(2) NO se modela retención (anticipo de renta → doble conteo); (3) carga neta = bruta − IVA;
(4) ADITIVO: la TIR/VPN pre-impuesto (dorado) NO se mueven y los campos _at aparecen en el resultado.
"""
import pytest

from aleph_engine import tributario

RET = [-100.0, 0.0, 50.0, 200.0, 150.0]
EQ = [-80.0, -20.0, 30.0, 120.0, 90.0]


def test_vis_suma_devolucion_iva():
    sin = tributario.decision_after_tax(RET, EQ, vehiculo="fiducia", renta_total=20.0, es_vis=False, ventas=1000.0)
    con = tributario.decision_after_tax(RET, EQ, vehiculo="fiducia", renta_total=20.0, es_vis=True, ventas=1000.0)
    assert sin["iva_vis"] == 0.0                                   # No-VIS: sin devolución
    assert con["iva_vis"] == pytest.approx(tributario.IVA_VIS_DEVOLUCION * 1000.0)
    # la devolución es una ENTRADA → mejora el flujo (suma a los retornos positivos)
    assert sum(con["retorno_at"]) > sum(sin["retorno_at"])


def test_iva_solo_si_hay_ventas():
    r = tributario.decision_after_tax(RET, EQ, vehiculo="fiducia", renta_total=10.0, es_vis=True, ventas=0.0)
    assert r["iva_vis"] == 0.0


def test_iva_en_operativo_no_duplica():
    """Si la devolución de IVA YA está contada en los ingresos operativos del P&G, la capa after-tax
    NO la vuelve a sumar (evita el doble conteo). ET 850 par.2: el beneficio es uno solo."""
    con = tributario.decision_after_tax(RET, EQ, vehiculo="fiducia", renta_total=0.0, es_vis=True, ventas=1000.0)
    op = tributario.decision_after_tax(RET, EQ, vehiculo="fiducia", renta_total=0.0, es_vis=True, ventas=1000.0,
                                       iva_en_operativo=True)
    assert con["iva_vis"] > 0.0 and op["iva_vis"] == 0.0          # con flag → no se suma de nuevo
    assert sum(op["retorno_at"]) < sum(con["retorno_at"])         # sin el IVA duplicado, el flujo es menor


def test_carga_neta_descuenta_iva():
    r = tributario.decision_after_tax(RET, EQ, vehiculo="fiducia", renta_total=20.0, es_vis=True, ventas=1000.0)
    assert r["carga_neta"] == pytest.approx(r["carga_bruta"] - r["iva_vis"])
    # la carga BRUTA NO incluye retención (no se modela): es renta + gmf + dividendos
    assert r["carga_bruta"] == pytest.approx(r["renta"] + r["gmf"] + r["dividendos"])


def test_opaco_carga_mas_que_transparente():
    t = tributario.decision_after_tax(RET, EQ, vehiculo="consorcio", renta_total=20.0, es_vis=False, ventas=0.0)
    o = tributario.decision_after_tax(RET, EQ, vehiculo="sas_spv", renta_total=20.0, es_vis=False, ventas=0.0)
    assert o["dividendos"] > 0.0 and t["dividendos"] == 0.0
    assert o["carga_neta"] > t["carga_neta"]


# --- ADITIVO sobre datos reales: el dorado pre-impuesto no se mueve; los campos _at existen ---
import json
import os

_PRIV = os.path.join(os.path.dirname(__file__), "..", "..",
                     "data", "proyectos_privados", "1_navarra_REAL.json")


def test_aditivo_no_mueve_dorado_y_expone_at():
    if not os.path.exists(_PRIV):
        pytest.skip("Navarra REAL no disponible (CI sin datos privados)")
    from aleph_engine import calcular
    par = json.load(open(_PRIV, encoding="utf-8"))
    R = calcular(json.loads(json.dumps(par)))
    ap, pg = R["apalancamiento"], R["pyg"]
    # pre-impuesto INTACTO (dorado)
    assert abs(ap["tir_proyecto"] - 0.375975) < 1e-4
    # campos after-tax presentes y coherentes
    for k in ("tir_proyecto_at", "tir_equity_at", "vpn_at", "iva_vis_devolucion", "carga_tributaria_neta_at"):
        assert k in ap
    # Navarra es VIS → hay devolución de IVA. Desde el re-baseline 2026-08-09 el par declara
    # `iva_en_operativo`: el Excel la registra como INGRESO OPERATIVO (viaja dentro de recon_codensa),
    # así que la capa after-tax NO la vuelve a sumar y el campo queda en 0 A PROPÓSITO. Sin el flag se
    # doble-contaba. Ver docs/acta_rebaseline_navarra_20260809.md §5.3.
    if par["financiero"].get("iva_en_operativo"):
        assert ap["iva_vis_devolucion"] == 0
        assert pg["recon_codensa"] > 0           # la devolución sigue ahí, en el operativo
    else:
        assert ap["iva_vis_devolucion"] > 0
