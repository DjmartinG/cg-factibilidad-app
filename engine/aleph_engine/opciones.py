# -*- coding: utf-8 -*-
"""Escenarios de FASING por etapa (opciones reales): RETRASAR / ACELERAR (ritmo) / QUITAR cada etapa y
ver el impacto en caja, exposición y retorno.

Como el simulador, SUELTA el override de fiducia (`par['fiducia']`, la TIR auditada es fija y no
respondería) → TIR/VPN son DIRECCIONALES (base mensual); el margen y la CAJA (exposición, crédito,
timeline) son exactos. La cifra oficial de TIR/VPN sigue siendo la de la ficha (fiducia auditada).

Aditivo y PURO salvo por reusar `modelo.calcular`: NO lo modifica → dorado intacto.
"""
from __future__ import annotations

import copy

from . import modelo


def _shift_fecha(iso: str, meses: int) -> str:
    """Desplaza una fecha ISO 'YYYY-MM-DD' en `meses` (día fijo)."""
    y, m, d = (int(x) for x in iso.split("-"))
    idx = y * 12 + (m - 1) + int(meses)
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}-{d:02d}"


def _idx_mes(iso: str | None) -> int | None:
    if not iso:
        return None
    y, m, _ = (int(x) for x in iso.split("-"))
    return y * 12 + (m - 1)


def etapas_info(par: dict) -> list[dict]:
    """[{cod, nombre, und, fecha_inicio, vmes}] por etapa — para pintar los controles del panel."""
    out = []
    for i, e in enumerate(par.get("etapas", [])):
        out.append({
            "cod": e.get("cod", i + 1),
            "nombre": e.get("nom") or f"Etapa {i + 1}",
            "und": e.get("und", 0),
            "fecha_inicio": e.get("fecha_inicio"),
            "vmes": e.get("vmes"),
        })
    return out


def _metricas(R: dict, etapas: list[dict]) -> dict:
    ap = R.get("apalancamiento", {})
    pg = R.get("pyg", {})
    ventas = pg.get("ventas", 0) or 1
    return {
        "tir": ap.get("tir_proyecto"),
        "vpn": ap.get("vpn_proyecto"),
        "margen": pg.get("util_oper", 0) / ventas,
        "exposicion_maxima": ap.get("max_necesidad_caja"),
        "credito_max": ap.get("credito_max"),
        "payback_mes": ap.get("payback_mes"),
        "valor_creado": ap.get("valor_creado"),
        "crea_valor": ap.get("crea_valor"),
        "unidades": sum(e.get("und", 0) for e in etapas),
    }


def _caja(R: dict) -> list[dict]:
    ap = R.get("apalancamiento", {})
    acum = ap.get("acumulado", []) or []
    cred = ap.get("saldo_credito", []) or []
    return [{"m": i, "acum": a, "credito": (cred[i] if i < len(cred) else 0.0)} for i, a in enumerate(acum)]


def _min_fecha(etapas: list[dict]) -> str | None:
    fechas = [e.get("fecha_inicio") for e in etapas if e.get("fecha_inicio")]
    return min(fechas) if fechas else None


def correr_escenario(par: dict, mods: dict | None = None) -> dict:
    """Aplica `mods` por etapa (`{cod: {delay:int, ritmo_factor:float, quitar:bool}}`) sobre una copia
    SIN fiducia y re-corre el motor. Devuelve indicadores (direccionales) + serie de caja + el offset de
    inicio (meses que el escenario arranca DESPUÉS del origen base, para alinear el timeline)."""
    mods = mods or {}
    origen = _min_fecha(par.get("etapas", []))          # ancla común (etapas ORIGINALES)
    p = copy.deepcopy(par)
    p.pop("fiducia", None)                               # TIR del MODELO (la auditada es fija) → direccional

    etapas: list[dict] = []
    for i, e in enumerate(p.get("etapas", [])):
        cod = e.get("cod", i + 1)
        m = mods.get(cod) or mods.get(str(cod)) or {}
        if m.get("quitar"):
            continue
        if m.get("delay") and e.get("fecha_inicio"):
            e["fecha_inicio"] = _shift_fecha(e["fecha_inicio"], int(m["delay"]))
        rf = m.get("ritmo_factor")
        if rf and float(rf) > 0 and e.get("vmes"):
            e["vmes"] = max(1, round(e["vmes"] * float(rf)))
        etapas.append(e)

    if not etapas:                                       # todas quitadas → escenario vacío (sin proyecto)
        return {"indicadores": {"tir": None, "vpn": None, "margen": None, "exposicion_maxima": None,
                                "credito_max": None, "payback_mes": None, "valor_creado": None,
                                "crea_valor": None, "unidades": 0},
                "caja": [], "inicio_offset": 0, "vacio": True}

    p["etapas"] = etapas
    R = modelo.calcular(p)
    scen = _min_fecha(etapas)
    off = 0
    if origen and scen:
        a, b = _idx_mes(origen), _idx_mes(scen)
        off = max(0, (b - a)) if (a is not None and b is not None) else 0
    return {"indicadores": _metricas(R, etapas), "caja": _caja(R), "inicio_offset": off, "vacio": False}
