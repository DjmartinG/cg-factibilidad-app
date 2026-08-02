# -*- coding: utf-8 -*-
"""Escenarios macro (abanico forward): inflación, tasa (IBR) y TRM proyectadas como un CONO de
incertidumbre (banda baja / base / alta) sobre el horizonte de los proyectos.

HONESTO (regla del proyecto: no fabricar precisión): la senda BASE se ancla a valores REALES (dato
vivo de Banrep, vía `anclas`) o a la META OFICIAL de Banrep (inflación 3%); las BANDAS son escenarios
del comité **[POR VALIDAR]** que se ENSANCHAN con el tiempo (cerca hay visibilidad, lejos no). NO es un
pronóstico de una fuente. Puro: no toca `calcular()` ni el dorado; el motor financiero NO lo consume
(es contexto de decisión de portafolio).
"""
from __future__ import annotations

ANIO_BASE = 2026
HORIZONTE = 10

# Supuestos de trayectoria y banda por variable. [POR VALIDAR con el comité]
# converge: base parte de `hoy` y llega a `objetivo` en `converge_anios`, luego estable.
# drift:    base = hoy·(1+drift)^t (crecimiento compuesto). Banda relativa para la TRM.
SUPUESTOS = {
    "inflacion": {
        "nombre": "Inflación anual", "unidad": "pct_ea", "modo": "converge",
        "hoy": 0.051, "objetivo": 0.030, "converge_anios": 2.0,
        "banda0": 0.004, "banda_slope": 0.0025,
        "fuente": "Banrep (meta 3%) + comité",
        "nota": "Converge a la meta de largo plazo de Banrep (3%).",
    },
    "tasa": {
        "nombre": "Tasa de política (IBR)", "unidad": "pct_ea", "modo": "converge",
        "hoy": 0.0925, "objetivo": 0.060, "converge_anios": 2.5,
        "banda0": 0.005, "banda_slope": 0.005,
        "fuente": "Banrep (IBR vivo) + comité",
        "nota": "Normaliza hacia la tasa neutral (~6%).",
    },
    "trm": {
        "nombre": "TRM (COP/USD)", "unidad": "COP", "modo": "drift",
        "hoy": 4000.0, "drift": 0.02,
        "banda0_rel": 0.03, "banda_slope_rel": 0.02,
        "fuente": "Banrep (TRM vivo) + comité",
        "nota": "Drift por diferencial de inflación; banda amplia (alta incertidumbre cambiaria).",
    },
}


def _serie_converge(cfg: dict, horizonte: int) -> list[dict]:
    hoy, obj, conv = cfg["hoy"], cfg["objetivo"], cfg["converge_anios"]
    pts = []
    for t in range(horizonte + 1):
        frac = max(0.0, 1.0 - t / conv) if conv > 0 else 0.0   # convergencia lineal, luego plana
        base = obj + (hoy - obj) * frac
        banda = cfg["banda0"] + cfg["banda_slope"] * t          # cono que se ensancha
        pts.append({"t": t, "base": base, "bajo": max(0.0, base - banda), "alto": base + banda})
    return pts


def _serie_drift(cfg: dict, horizonte: int) -> list[dict]:
    hoy, drift = cfg["hoy"], cfg["drift"]
    pts = []
    for t in range(horizonte + 1):
        base = hoy * (1 + drift) ** t
        rel = cfg["banda0_rel"] + cfg["banda_slope_rel"] * t
        pts.append({"t": t, "base": base, "bajo": base * (1 - rel), "alto": base * (1 + rel)})
    return pts


def proyectar(anio_inicio: int = ANIO_BASE, horizonte: int = HORIZONTE, anclas: dict | None = None) -> dict:
    """Abanico por variable. `anclas` (opcional) = {clave: valor_hoy} para clavar el punto inicial al
    dato VIVO (p.ej. {'trm': 3990, 'tasa': 0.092}); si falta, usa el default grounded. Cada variable
    devuelve `puntos` = [{anio, base, bajo, alto}] con bajo ≤ base ≤ alto (cono de incertidumbre)."""
    anclas = anclas or {}
    variables = []
    for clave, cfg in SUPUESTOS.items():
        c = dict(cfg)
        if anclas.get(clave):
            c["hoy"] = float(anclas[clave])
        serie = _serie_drift(c, horizonte) if c["modo"] == "drift" else _serie_converge(c, horizonte)
        puntos = [{"anio": anio_inicio + p["t"], "base": p["base"], "bajo": p["bajo"], "alto": p["alto"]} for p in serie]
        variables.append({
            "clave": clave, "nombre": c["nombre"], "unidad": c["unidad"],
            "fuente": c["fuente"], "nota": c["nota"],
            "anclado": bool(anclas.get(clave)), "puntos": puntos,
        })
    return {
        "anio_inicio": anio_inicio, "horizonte": horizonte, "variables": variables,
        "nota": "Senda base anclada a datos vivos / meta de Banrep; las bandas son escenarios del "
                "comité [por validar]. Es un cono de incertidumbre, no un pronóstico de una fuente.",
    }
