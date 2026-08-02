# -*- coding: utf-8 -*-
"""Escenarios macro (abanico forward) — proyección de inflación/tasa/TRM como cono de incertidumbre.

Es ADITIVO y PURO: `calcular()` no lo importa → dorado intacto. Verifica la forma del cono, la
convergencia a la meta, el drift de la TRM, el ensanchamiento de la banda y el anclaje a datos vivos.
"""
from aleph_engine import macro_forward as mf


def test_estructura_tres_variables_y_horizonte():
    r = mf.proyectar(anio_inicio=2026, horizonte=10)
    claves = {v["clave"] for v in r["variables"]}
    assert claves == {"inflacion", "tasa", "trm"}
    for v in r["variables"]:
        assert len(v["puntos"]) == 11               # horizonte + 1 (2026..2036)
        assert v["puntos"][0]["anio"] == 2026 and v["puntos"][-1]["anio"] == 2036


def test_cono_bajo_le_base_le_alto():
    r = mf.proyectar()
    for v in r["variables"]:
        for p in v["puntos"]:
            assert p["bajo"] <= p["base"] <= p["alto"]


def test_banda_se_ensancha_con_el_tiempo():
    r = mf.proyectar()
    for v in r["variables"]:
        ancho0 = v["puntos"][0]["alto"] - v["puntos"][0]["bajo"]
        anchoN = v["puntos"][-1]["alto"] - v["puntos"][-1]["bajo"]
        assert anchoN > ancho0                       # cono de incertidumbre


def test_inflacion_converge_a_la_meta():
    v = next(x for x in mf.proyectar()["variables"] if x["clave"] == "inflacion")
    assert abs(v["puntos"][0]["base"] - 0.051) < 1e-9   # arranca en hoy
    assert abs(v["puntos"][-1]["base"] - 0.030) < 1e-6  # termina en la meta (3%)


def test_trm_crece_por_drift():
    v = next(x for x in mf.proyectar()["variables"] if x["clave"] == "trm")
    bases = [p["base"] for p in v["puntos"]]
    assert all(b < a for b, a in zip(bases, bases[1:]))  # estrictamente creciente
    assert v["puntos"][0]["base"] == 4000.0


def test_anclas_clavan_el_punto_inicial():
    r = mf.proyectar(anclas={"trm": 4250.0, "tasa": 0.088})
    trm = next(x for x in r["variables"] if x["clave"] == "trm")
    tasa = next(x for x in r["variables"] if x["clave"] == "tasa")
    assert trm["puntos"][0]["base"] == 4250.0 and trm["anclado"] is True
    assert abs(tasa["puntos"][0]["base"] - 0.088) < 1e-9 and tasa["anclado"] is True
    # sin ancla → default grounded
    infl = next(x for x in r["variables"] if x["clave"] == "inflacion")
    assert infl["anclado"] is False and abs(infl["puntos"][0]["base"] - 0.051) < 1e-9


def test_tasas_no_negativas_en_la_banda_baja():
    # el cono de inflación/tasa no cae por debajo de 0 aunque la banda crezca
    r = mf.proyectar(horizonte=10)
    for clave in ("inflacion", "tasa"):
        v = next(x for x in r["variables"] if x["clave"] == clave)
        assert all(p["bajo"] >= 0.0 for p in v["puntos"])
