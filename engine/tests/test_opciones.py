# -*- coding: utf-8 -*-
"""Escenarios de fasing por etapa (opciones reales) — retrasar / acelerar / quitar.

Reusa `modelo.calcular` sobre una copia SIN fiducia (TIR direccional). NO muta el par original ni toca
`calcular()` → dorado intacto. El `par` sale del golden (input_par), como en test_simulacion.
"""
import glob
import json
import os

from aleph_engine import opciones


def _par():
    for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "golden", "*_snapshot.json"))):
        return json.load(open(f, encoding="utf-8"))["input_par"]
    raise RuntimeError("sin golden para el test")


def test_base_devuelve_indicadores_y_caja():
    r = opciones.correr_escenario(_par(), {})
    ind = r["indicadores"]
    assert ind["unidades"] > 0
    assert ind["tir"] is not None and ind["margen"] is not None
    assert len(r["caja"]) > 0 and r["caja"][0]["m"] == 0
    assert r["inicio_offset"] == 0 and r["vacio"] is False


def test_no_muta_el_par_original():
    par = _par()
    tenia_fiducia = "fiducia" in par
    fi0 = par["etapas"][0].get("fecha_inicio")
    opciones.correr_escenario(par, {par["etapas"][0].get("cod", 1): {"delay": 12}})
    assert ("fiducia" in par) == tenia_fiducia            # no le quitó la fiducia al ORIGINAL
    assert par["etapas"][0].get("fecha_inicio") == fi0    # no movió la fecha del ORIGINAL


def test_quitar_una_etapa_reduce_unidades():
    par = _par()
    ult = par["etapas"][-1]
    cod = ult.get("cod", len(par["etapas"]))
    base = opciones.correr_escenario(par, {})["indicadores"]["unidades"]
    quit = opciones.correr_escenario(par, {cod: {"quitar": True}})["indicadores"]["unidades"]
    assert quit < base                                    # la última etapa aporta unidades


def test_retrasar_todo_desplaza_el_inicio():
    par = _par()
    mods = {e.get("cod", i + 1): {"delay": 6} for i, e in enumerate(par["etapas"]) if e.get("fecha_inicio")}
    if not mods:
        return
    r = opciones.correr_escenario(par, mods)
    assert r["inicio_offset"] == 6                        # todo desplazado 6 meses


def test_quitar_todas_es_escenario_vacio():
    par = _par()
    mods = {e.get("cod", i + 1): {"quitar": True} for i, e in enumerate(par["etapas"])}
    r = opciones.correr_escenario(par, mods)
    assert r["vacio"] is True
    assert r["indicadores"]["unidades"] == 0 and r["caja"] == []


def test_etapas_info_lista_las_etapas():
    par = _par()
    info = opciones.etapas_info(par)
    assert len(info) == len(par["etapas"])
    assert all("cod" in e and "nombre" in e for e in info)
