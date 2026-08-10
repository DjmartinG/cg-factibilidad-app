# -*- coding: utf-8 -*-
"""Golden / regression tests — CLAVAN las cifras que produce el motor.

Esta es la RED DE SEGURIDAD de toda la reestructuración: ninguna refactorización del motor
puede cambiar estos números sin que un test se ponga en rojo.

Dos grupos:
  • AUDITADAS  — cifras de los proyectos REALES (Navarra/Dominica/Torres), las que el comité
                 usa para decidir inversiones. Los JSON reales viven en `proyectos_privados/`
                 (gitignored, confidenciales) → estos tests SOLO corren donde existan esos
                 archivos; en CI (GitHub) se saltan automáticamente.
  • REGRESION  — cifras de los proyectos ILUSTRATIVOS (en el repo). Son la red de seguridad
                 que SÍ corre en CI: cualquier cambio de comportamiento del motor las rompe.

Regla de oro: NO cambies un valor esperado sin entender y justificar por qué cambió el motor.
Si una ancla AUDITADA cambia, es un bug — se revierte el cambio.
"""
import os
import json
import copy

import pytest

from aleph_engine import calcular

# Los datos (proyectos/ + proyectos_privados/) viven en data/ (raíz), reubicados al retirar Streamlit.
RAIZ = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
_MONEY = {"util_oper", "ventas", "ap_vpn_proyecto", "ap_credito_max"}


def _run(rel_path):
    """Corre calcular() sobre un proyecto y devuelve las métricas clave (contrato real del motor)."""
    par = json.load(open(os.path.join(RAIZ, rel_path), encoding="utf-8"))
    R = calcular(copy.deepcopy(par))
    pg = R["pyg"]
    ap = R.get("apalancamiento", {}) or {}
    fl = R.get("flujo", {}) or {}
    return {
        "util_oper": pg["util_oper"],
        "margen_oper": pg["margen_oper"],
        "ventas": pg["ventas"],
        "ap_tir_proyecto": ap.get("tir_proyecto"),
        "ap_vpn_proyecto": ap.get("vpn_proyecto"),
        "ap_tir_equity": ap.get("tir_equity"),
        "ap_credito_max": ap.get("credito_max"),
        "ap_fiducia_real": ap.get("fiducia_real", False),
        "fl_tir_proyecto": fl.get("tir_proyecto"),
    }


def _assert_cifras(got, exp):
    for k, v in exp.items():
        g = got[k]
        if v is None:
            assert g is None, f"{k}: esperado None, obtenido {g}"
        elif isinstance(v, bool):
            assert g == v, f"{k}: esperado {v}, obtenido {g}"
        elif k in _MONEY:                       # montos (miles COP): tolerancia relativa
            assert g == pytest.approx(v, rel=1e-5), f"{k}: esperado {v}, obtenido {g}"
        else:                                   # fracciones (TIR, margen): tolerancia absoluta
            assert g == pytest.approx(v, abs=1e-5), f"{k}: esperado {v}, obtenido {g}"


# ----------------------------- ANCLAS AUDITADAS (proyectos reales) -----------------------------
# NOTA 2026-06-14: los `ap_tir_equity` de los proyectos NO-fiducia se sincronizaron a la baseline
# YA APROBADA del fix de flujo_equity (PR #22, docs/acta_flujo_equity_20260614.md). PR #22 regeneró
# los snapshots pero dejó esta copia con valores viejos (el suite app_streamlit quedó rojo). El WACC
# (beta_d/rp) NO toca tir_equity; estos valores == los snapshots commiteados. Navarra REAL (fiducia
# override 41,72%) no cambia.
AUDITADAS = {
    # Navarra: re-baseline 2026-08-09 (docs/acta_rebaseline_navarra_20260809.md, aprobado por Martín).
    # Recalibración contra el Excel de factibilidad: el local comercial pasa de "otros ingresos" a
    # VENTAS (+1,374%), el recaudo usa la cuota inicial y la separación reales, y las cubetas de
    # honorarios suman el 10% del total. Las TRES cifras de decisión NO se movieron (salen del override
    # `fiducia`): tir_proyecto 37,5975% · vpn_proyecto 18.280.688 · tir_equity 41,7189%.
    "proyectos_privados/1_navarra_REAL.json": {
        "util_oper": 11362333.12, "margen_oper": 0.048799, "ventas": 232838874.45,
        "ap_tir_proyecto": 0.375975, "ap_vpn_proyecto": 18280687.67, "ap_tir_equity": 0.417189,
        "ap_credito_max": 48623715.5, "ap_fiducia_real": True, "fl_tir_proyecto": 0.01585,
    },
    "proyectos_privados/2_dominica_REAL.json": {
        "util_oper": 11250275.94, "margen_oper": 0.086214, "ventas": 130492117.68,
        "ap_tir_proyecto": 0.565495, "ap_vpn_proyecto": 14618570.85, "ap_tir_equity": 0.688779,
        "ap_credito_max": 28656605.22, "ap_fiducia_real": False, "fl_tir_proyecto": 0.227671,
    },
    "proyectos_privados/3_torres_campinas_REAL.json": {
        "util_oper": 6168954.37, "margen_oper": 0.025616, "ventas": 240822586.45,
        "ap_tir_proyecto": -0.993595, "ap_vpn_proyecto": -6021481.08, "ap_tir_equity": -0.236457,
        "ap_credito_max": 44520453.32, "ap_fiducia_real": False, "fl_tir_proyecto": -0.093104,
    },
}

# ----------------------------- REGRESIÓN (proyectos ilustrativos, en el repo) -----------------------------
REGRESION = {
    "proyectos/1_navarra.json": {
        "util_oper": 11077849.5, "margen_oper": 0.056003, "ventas": 197808500,
        "ap_tir_proyecto": -0.999974, "ap_vpn_proyecto": 7882913.89, "ap_tir_equity": -0.339514,
        "ap_credito_max": 31208497.89, "ap_fiducia_real": False, "fl_tir_proyecto": 0.073032,
    },
    "proyectos/2_dominica.json": {
        "util_oper": 7367968.0, "margen_oper": 0.070477, "ventas": 104544000,
        "ap_tir_proyecto": 0.227289, "ap_vpn_proyecto": 4737027.6, "ap_tir_equity": 0.284826,
        "ap_credito_max": 33414522.81, "ap_fiducia_real": False, "fl_tir_proyecto": 0.10234,
    },
    "proyectos/3_torres_campinas.json": {
        "util_oper": 11914741.4, "margen_oper": 0.062743, "ventas": 189896200,
        "ap_tir_proyecto": -0.997034, "ap_vpn_proyecto": 9653588.09, "ap_tir_equity": -0.286135,
        "ap_credito_max": 21756832.57, "ap_fiducia_real": False, "fl_tir_proyecto": 0.091906,
    },
}


@pytest.mark.parametrize("path,exp", list(AUDITADAS.items()), ids=lambda x: x if isinstance(x, str) else "")
def test_anclas_auditadas(path, exp):
    """Las cifras de decisión (proyectos reales) deben reproducirse EXACTAS. Skip si no hay datos reales."""
    if not os.path.exists(os.path.join(RAIZ, path)):
        pytest.skip(f"datos reales no presentes (gitignored): {path}")
    _assert_cifras(_run(path), exp)


@pytest.mark.parametrize("path,exp", list(REGRESION.items()), ids=lambda x: x if isinstance(x, str) else "")
def test_regresion_ilustrativos(path, exp):
    """Red de seguridad en CI: el motor no cambia de comportamiento sobre los proyectos del repo."""
    _assert_cifras(_run(path), exp)
