# -*- coding: utf-8 -*-
"""Tests del endpoint de valores macro EN VIVO (Fase 2 de Fuentes). NO toca el motor: solo mapea el
dato vivo de Damodaran (CRP→rp, ERP madura→pm) y degrada limpio si la fuente externa falla. Se inyecta
un `fetch` falso → sin red en CI.
"""
from fastapi.testclient import TestClient

from aleph_api import fuentes_live
from aleph_api.conectores.base import ValorMacro
from aleph_api.main import app

client = TestClient(app)


def _fake_ok(pais="Colombia"):
    return [
        ValorMacro(
            clave="damodaran:crp:colombia", nombre="Riesgo país (CRP)", valor=0.0285, unidad="ratio",
            fuente="Damodaran (NYU Stern)", fuente_normativa="Country Risk Premiums (anual)",
            detalle={"fila": ["Colombia", "Baa3", "1.87%", "2.85%", "7.08%", "35.00%"]},
        ),
        ValorMacro(
            clave="damodaran:erp_total:colombia", nombre="ERP total", valor=0.0708, unidad="ratio",
            fuente="Damodaran (NYU Stern)",
        ),
    ]


def _fake_falla(pais="Colombia"):
    raise RuntimeError("fuente caída")


def _fake_trm(clave="trm"):
    return ValorMacro(
        clave="banrep:trm", nombre="TRM (COP/USD)", valor=3433.71, unidad="COP",
        fuente="Banco de la República (SDMX)", detalle={"periodo": "20260626"},
    )


def _fake_trm_falla(clave="trm"):
    raise RuntimeError("Banrep caído")


def test_mapea_rp_y_pm_madura():
    fuentes_live._cache.clear()
    r = fuentes_live.damodaran_colombia(fetch=_fake_ok)
    assert r["disponible"] is True
    assert r["datos"]["rp"]["valor"] == 0.0285
    assert abs(r["datos"]["pm"]["valor"] - 0.0423) < 1e-9  # ERP total 0.0708 − CRP 0.0285
    assert r["rating"] == "Baa3"
    fuentes_live._cache.clear()


def test_degrada_si_la_fuente_falla():
    fuentes_live._cache.clear()
    r = fuentes_live.damodaran_colombia(fetch=_fake_falla)
    assert r["disponible"] is False
    assert r["fuente"] and r["url"]  # sigue identificando la fuente
    fuentes_live._cache.clear()


def test_cachea_por_dia():
    fuentes_live._cache.clear()
    calls = {"n": 0}

    def _contar(pais="Colombia"):
        calls["n"] += 1
        return _fake_ok(pais)

    fuentes_live.damodaran_colombia(fetch=_contar)
    fuentes_live.damodaran_colombia(fetch=_contar)  # segundo: del caché del día
    assert calls["n"] == 1
    fuentes_live._cache.clear()


def test_trm_banrep():
    fuentes_live._cache.clear()
    r = fuentes_live.banrep_trm(fetch=_fake_trm)
    assert r["disponible"] is True
    assert r["valor"] == 3433.71
    assert r["unidad"] == "COP"
    assert r["periodo"] == "20260626"
    assert r["fuente"] and r["url"]
    fuentes_live._cache.clear()


def test_trm_degrada_si_banrep_falla():
    fuentes_live._cache.clear()
    r = fuentes_live.banrep_trm(fetch=_fake_trm_falla)
    assert r["disponible"] is False
    assert r["fuente"] and r["url"]  # sigue identificando la fuente
    fuentes_live._cache.clear()


def test_endpoint_fuentes_live():
    # Sembramos AMBOS cachés del día para no pegarle a la red en CI (auth deshabilitada en dev/CI).
    fuentes_live._cache.clear()
    fuentes_live._cache[fuentes_live._hoy()] = {
        "disponible": True, "fuente": "Damodaran (NYU Stern)", "url": fuentes_live.damodaran.URL,
        "datos": {"rp": {"valor": 0.0285}, "pm": {"valor": 0.0423}},
    }
    fuentes_live._cache[f"trm:{fuentes_live._hoy()}"] = {
        "disponible": True, "fuente": "Banco de la República (SDMX)", "url": fuentes_live.URL_TRM,
        "valor": 3433.71, "unidad": "COP", "periodo": "20260626",
    }
    j = client.get("/v1/fuentes/live").json()
    assert j["disponible"] is True
    assert j["datos"]["rp"]["valor"] == 0.0285
    assert j["trm"]["disponible"] is True and j["trm"]["valor"] == 3433.71
    fuentes_live._cache.clear()


# ---------- Abanico macro (escenarios forward) ----------

def _seed_banrep(trm=None, ibr=None):
    """Siembra los cachés de TRM/IBR del día → el abanico no le pega a la red en CI."""
    fuentes_live._cache.clear()
    fuentes_live._cache[f"trm:{fuentes_live._hoy()}"] = trm or {
        "disponible": False, "fuente": "Banco de la República", "url": fuentes_live.URL_TRM}
    fuentes_live._cache[f"ibr:{fuentes_live._hoy()}"] = ibr or {
        "disponible": False, "fuente": "Banco de la República", "url": fuentes_live.URL_IBR}


def test_abanico_ancla_a_datos_vivos():
    _seed_banrep(
        trm={"disponible": True, "valor": 4250.0, "unidad": "COP", "fuente": "Banrep", "url": fuentes_live.URL_TRM},
        ibr={"disponible": True, "valor": 9.0, "unidad": "pct_ea", "fuente": "Banrep", "url": fuentes_live.URL_IBR},
    )
    r = fuentes_live.abanico_macro(anio=2026)
    trm = next(v for v in r["variables"] if v["clave"] == "trm")
    tasa = next(v for v in r["variables"] if v["clave"] == "tasa")
    assert trm["puntos"][0]["base"] == 4250.0 and trm["anclado"] is True
    assert abs(tasa["puntos"][0]["base"] - 0.09) < 1e-9 and tasa["anclado"] is True  # 9,0% → 0,09
    assert r["anclas_vivas"]["trm"]["disponible"] is True
    fuentes_live._cache.clear()


def test_abanico_degrada_a_defaults_sin_red():
    _seed_banrep()  # ambas fuentes no disponibles
    r = fuentes_live.abanico_macro(anio=2026)
    assert all(not v["anclado"] for v in r["variables"])  # sin ancla viva → default grounded
    infl = next(v for v in r["variables"] if v["clave"] == "inflacion")
    assert abs(infl["puntos"][0]["base"] - 0.051) < 1e-9
    fuentes_live._cache.clear()


def test_endpoint_fuentes_forward():
    _seed_banrep()
    j = client.get("/v1/fuentes/forward").json()
    assert {v["clave"] for v in j["variables"]} == {"inflacion", "tasa", "trm"}
    assert j["anio_inicio"] >= 2026
    assert all(len(v["puntos"]) == j["horizonte"] + 1 for v in j["variables"])
    fuentes_live._cache.clear()
