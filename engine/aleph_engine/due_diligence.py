# -*- coding: utf-8 -*-
"""Due Diligence + registro de riesgos del prefacto → veredicto de viabilidad CUALITATIVA.

Curso Camacol: M4 (legal), M5 (ambiental), M1/M5 (urbanístico/POT) + técnico y financiero/bancario.
Captura los estudios cualitativos como un registro estructurado (estado + impacto + mitigación) y
deriva un semáforo de viabilidad que ACOMPAÑA al veredicto financiero (no lo reemplaza).

DISEÑO:
  - El registro del analista vive en el `par` del escenario (`par['due_diligence']`), una lista de
    {frente, item, estado, impacto, mitigacion, nota}. Rida la infra de scenarios (versionado/audit);
    el MOTOR financiero lo IGNORA (no es cálculo) → `calcular()` y el dorado intactos.
  - Aquí se FUSIONA ese registro con una PLANTILLA canónica (el checklist estándar del prefacto): los
    ítems que el analista no haya llenado quedan en "pendiente". Es agregación descriptiva, no cálculo.

NOTA: la plantilla es un primer set para refinar con el comité (algunos ítems/impactos `[por validar]`).
La CAPTURA/edición de estados se hará en el Ingreso de datos (/web, fase posterior); hoy se LEE.
"""
from __future__ import annotations

FRENTES = (
    ("legal", "Legal"),
    ("ambiental", "Ambiental / ESG"),
    ("urbanistico", "Urbanístico / POT"),
    ("tecnico", "Técnico"),
    ("comercial", "Comercial / mercado"),
    ("bancario", "Financiero / bancario"),
)

ESTADOS = ("ok", "alerta", "pendiente")
IMPACTOS = ("alto", "medio", "bajo")
PROBABILIDADES = ("alta", "media", "baja")

# Matriz de severidad = probabilidad × impacto (registro de riesgos clásico prob×impacto).
# Pesos alta/alto=3 · media/medio=2 · baja/bajo=1; severidad por el producto: >=6 alto, 3-4 medio, <=2 bajo.
_PESO_PROB = {"alta": 3, "media": 2, "baja": 1}
_PESO_IMP = {"alto": 3, "medio": 2, "bajo": 1}

# Checklist canónico del prefacto. `impacto` = peso por defecto en la viabilidad (si el analista no lo
# fija). Primer set — refinar con el comité.  # TODO [por validar]: lista definitiva por frente.
PLANTILLA = (
    {"frente": "legal", "item": "Estudio de títulos y tradición", "impacto": "alto"},
    {"frente": "legal", "item": "Saneamiento jurídico del predio", "impacto": "alto"},
    {"frente": "legal", "item": "Contratos típicos (promesa, fiducia, encargo)", "impacto": "medio"},
    {"frente": "legal", "item": "Riesgos legales / litigios / servidumbres", "impacto": "alto"},
    {"frente": "ambiental", "item": "Licencia y permisos ambientales", "impacto": "alto"},
    {"frente": "ambiental", "item": "Impactos ambientales y mitigación", "impacto": "medio"},
    {"frente": "ambiental", "item": "Sostenibilidad / ESG", "impacto": "bajo"},
    {"frente": "ambiental", "item": "Normativa ambiental aplicable", "impacto": "medio"},
    {"frente": "urbanistico", "item": "Uso del suelo permitido (POT)", "impacto": "alto"},
    {"frente": "urbanistico", "item": "Índice de construcción / aprovechamiento", "impacto": "alto"},
    {"frente": "urbanistico", "item": "Cesiones y obligaciones urbanísticas", "impacto": "medio"},
    {"frente": "tecnico", "item": "Estudio de suelos / geotecnia", "impacto": "alto"},
    {"frente": "tecnico", "item": "Disponibilidad de servicios públicos", "impacto": "medio"},
    {"frente": "tecnico", "item": "Licencia de construcción / diseños", "impacto": "medio"},
    {"frente": "comercial", "item": "Absorción esperada vs mercado de la zona", "impacto": "alto"},
    {"frente": "comercial", "item": "Precio de venta vs competencia", "impacto": "medio"},
    {"frente": "bancario", "item": "Crédito constructor (aprobación)", "impacto": "alto"},
    {"frente": "bancario", "item": "Estructura fiduciaria / patrimonio autónomo", "impacto": "medio"},
)


def _clave(frente, item) -> str:
    return f"{frente}::{item}".strip().lower()


def _norm_estado(v) -> str:
    return v if v in ESTADOS else "pendiente"


def _norm_impacto(v, defecto) -> str:
    return v if v in IMPACTOS else defecto


def _norm_prob(v) -> str:
    """Probabilidad de que el riesgo se materialice. Sin dato → 'media' (neutro, cae en el centro de la matriz)."""
    return v if v in PROBABILIDADES else "media"


def _severidad(prob: str, impacto: str) -> str:
    """Nivel de severidad = probabilidad × impacto (celda de la matriz de riesgos)."""
    score = _PESO_PROB.get(prob, 2) * _PESO_IMP.get(impacto, 2)
    return "alto" if score >= 6 else ("medio" if score >= 3 else "bajo")


def evaluar(par: dict) -> dict:
    """Fusiona el registro del analista (`par['due_diligence']`) con la plantilla y deriva el veredicto.

    Veredicto (semáforo): rojo = hay un riesgo de impacto ALTO en estado "alerta" (problema confirmado);
    ámbar = hay ítems abiertos (alerta o pendiente) sin rojo; verde = todo "ok".
    """
    reg = par.get("due_diligence") or []
    por_clave: dict[str, dict] = {}
    for r in reg:
        if isinstance(r, dict) and r.get("frente") and r.get("item"):
            por_clave[_clave(r["frente"], r["item"])] = r

    items: list[dict] = []
    usados: set[str] = set()
    for t in PLANTILLA:
        c = _clave(t["frente"], t["item"])
        usados.add(c)
        a = por_clave.get(c)
        items.append({
            "frente": t["frente"], "item": t["item"],
            "estado": _norm_estado(a.get("estado") if a else None),
            "impacto": _norm_impacto(a.get("impacto") if a else None, t["impacto"]),
            "probabilidad": _norm_prob(a.get("probabilidad") if a else None),
            "mitigacion": (a.get("mitigacion") if a else "") or "",
            "nota": (a.get("nota") if a else "") or "",
            "del_analista": a is not None,
        })
    # Ítems adicionales que el analista agregó fuera de la plantilla.
    for r in reg:
        if not (isinstance(r, dict) and r.get("frente") and r.get("item")):
            continue
        c = _clave(r["frente"], r["item"])
        if c in usados:
            continue
        usados.add(c)
        items.append({
            "frente": r["frente"], "item": r["item"],
            "estado": _norm_estado(r.get("estado")), "impacto": _norm_impacto(r.get("impacto"), "medio"),
            "probabilidad": _norm_prob(r.get("probabilidad")),
            "mitigacion": r.get("mitigacion") or "", "nota": r.get("nota") or "", "del_analista": True,
        })

    # Severidad de cada riesgo = probabilidad × impacto (celda de la matriz).
    for i in items:
        i["severidad"] = _severidad(i["probabilidad"], i["impacto"])

    abiertos = [i for i in items if i["estado"] != "ok"]
    n_alertas = sum(1 for i in items if i["estado"] == "alerta")
    n_pendientes = sum(1 for i in items if i["estado"] == "pendiente")
    rojo = any(i["estado"] == "alerta" and i["impacto"] == "alto" for i in items)
    nivel = "rojo" if rojo else ("ambar" if abiertos else "verde")

    # Resumen de la matriz: conteo por severidad de los riesgos CALIFICADOS y ABIERTOS (estado != ok). Los
    # ítems de la plantilla que el analista aún no revisó (del_analista=False) NO se cuentan ni se ubican en la
    # matriz: su probabilidad es "media" por defecto y falsearían el mapa de riesgo. Quedan como pendientes en
    # el checklist (veredicto.n_pendientes). La matriz refleja el registro real, no el backlog sin evaluar.
    calificados_abiertos = [i for i in abiertos if i["del_analista"]]
    sev_abiertos = {s: sum(1 for i in calificados_abiertos if i["severidad"] == s) for s in ("alto", "medio", "bajo")}

    return {
        "frentes": [{"clave": k, "nombre": n} for k, n in FRENTES],
        "items": items,
        "severidad_resumen": sev_abiertos,
        "veredicto": {
            "nivel": nivel,
            "n_items": len(items),
            "n_ok": len(items) - len(abiertos),
            "n_alertas": n_alertas,
            "n_pendientes": n_pendientes,
        },
    }
