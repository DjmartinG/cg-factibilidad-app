# -*- coding: utf-8 -*-
"""Due diligence / registro de riesgos — fusión con la plantilla + veredicto cualitativo.

`due_diligence.evaluar` es ADITIVO (no lo llama `calcular()` → dorado intacto). Verifica el merge del
registro del analista con la plantilla canónica y la lógica del semáforo de viabilidad.
"""
from aleph_engine import due_diligence as dd


def test_plantilla_sola_todo_pendiente_ambar():
    r = dd.evaluar({})   # sin registro del analista
    assert r["veredicto"]["n_items"] == len(dd.PLANTILLA)
    assert all(i["estado"] == "pendiente" and not i["del_analista"] for i in r["items"])
    assert r["veredicto"]["n_ok"] == 0
    assert r["veredicto"]["n_pendientes"] == len(dd.PLANTILLA)
    # con pendientes pero sin alerta-alto → ámbar (due diligence en proceso)
    assert r["veredicto"]["nivel"] == "ambar"
    # 6 frentes (incluye comercial / mercado)
    assert [f["clave"] for f in r["frentes"]] == ["legal", "ambiental", "urbanistico", "tecnico", "comercial", "bancario"]


def test_todo_ok_verde():
    reg = [{"frente": t["frente"], "item": t["item"], "estado": "ok"} for t in dd.PLANTILLA]
    r = dd.evaluar({"due_diligence": reg})
    assert r["veredicto"]["nivel"] == "verde"
    assert r["veredicto"]["n_ok"] == len(dd.PLANTILLA)
    assert all(i["del_analista"] for i in r["items"])


def test_alerta_alto_es_rojo():
    reg = [{"frente": "legal", "item": "Estudio de títulos y tradición", "estado": "alerta", "impacto": "alto",
            "mitigacion": "Sanear antes de prometer"}]
    r = dd.evaluar({"due_diligence": reg})
    assert r["veredicto"]["nivel"] == "rojo"
    it = next(i for i in r["items"] if i["item"] == "Estudio de títulos y tradición")
    assert it["estado"] == "alerta" and it["impacto"] == "alto" and it["del_analista"]
    assert "Sanear" in it["mitigacion"]


def test_alerta_medio_sin_alto_es_ambar():
    # una alerta de impacto MEDIO + el resto ok → ámbar (no rojo)
    reg = [{"frente": t["frente"], "item": t["item"], "estado": "ok"} for t in dd.PLANTILLA]
    reg[2] = {**reg[2], "estado": "alerta", "impacto": "medio"}
    r = dd.evaluar({"due_diligence": reg})
    assert r["veredicto"]["nivel"] == "ambar" and r["veredicto"]["n_alertas"] == 1


def test_item_custom_fuera_de_plantilla_se_agrega():
    reg = [{"frente": "legal", "item": "Pleito con vecino colindante", "estado": "alerta", "impacto": "alto"}]
    r = dd.evaluar({"due_diligence": reg})
    assert any(i["item"] == "Pleito con vecino colindante" and i["del_analista"] for i in r["items"])
    assert r["veredicto"]["n_items"] == len(dd.PLANTILLA) + 1
    assert r["veredicto"]["nivel"] == "rojo"


def test_normaliza_estado_e_impacto_invalidos():
    reg = [{"frente": "legal", "item": "Estudio de títulos y tradición", "estado": "raro", "impacto": "xx"}]
    r = dd.evaluar({"due_diligence": reg})
    it = next(i for i in r["items"] if i["item"] == "Estudio de títulos y tradición")
    assert it["estado"] == "pendiente"        # estado inválido → pendiente
    assert it["impacto"] == "alto"            # impacto inválido → defecto de la plantilla


def test_severidad_es_probabilidad_por_impacto():
    # alta × alto = alto; baja × bajo = bajo; media × medio (default) = medio
    reg = [
        {"frente": "legal", "item": "Riesgo grande", "estado": "alerta", "probabilidad": "alta", "impacto": "alto"},
        {"frente": "tecnico", "item": "Riesgo chico", "estado": "alerta", "probabilidad": "baja", "impacto": "bajo"},
        {"frente": "legal", "item": "Riesgo medio", "estado": "alerta"},   # prob/imp por defecto = media/medio
    ]
    r = dd.evaluar({"due_diligence": reg})
    by = {i["item"]: i for i in r["items"]}
    assert by["Riesgo grande"]["severidad"] == "alto" and by["Riesgo grande"]["probabilidad"] == "alta"
    assert by["Riesgo chico"]["severidad"] == "bajo"
    assert by["Riesgo medio"]["probabilidad"] == "media" and by["Riesgo medio"]["severidad"] == "medio"


def test_probabilidad_invalida_cae_a_media():
    reg = [{"frente": "legal", "item": "Riesgo X", "estado": "alerta", "probabilidad": "quizas", "impacto": "alto"}]
    r = dd.evaluar({"due_diligence": reg})
    it = next(i for i in r["items"] if i["item"] == "Riesgo X")
    assert it["probabilidad"] == "media"       # inválida → media
    assert it["severidad"] == "alto"           # media × alto = 6 → alto


def test_severidad_resumen_solo_cuenta_abiertos():
    # toda la plantilla en 'ok' (no cuenta) y UN riesgo abierto alta×alto
    reg = [{"frente": t["frente"], "item": t["item"], "estado": "ok"} for t in dd.PLANTILLA]
    reg[0] = {**reg[0], "estado": "alerta", "probabilidad": "alta", "impacto": "alto"}
    r = dd.evaluar({"due_diligence": reg})
    # los 'ok' NO cuentan como riesgo abierto aunque su prob×impacto sea alto
    assert r["severidad_resumen"]["alto"] == 1
    assert sum(r["severidad_resumen"].values()) == 1   # solo el abierto calificado


def test_resumen_ignora_plantilla_no_calificada():
    # solo plantilla (todo pendiente, del_analista=False) → NO se cuenta en la matriz aunque el impacto sea alto
    r = dd.evaluar({})
    assert r["severidad_resumen"] == {"alto": 0, "medio": 0, "bajo": 0}
    assert r["veredicto"]["n_pendientes"] == len(dd.PLANTILLA)   # sí quedan como pendientes en el checklist
