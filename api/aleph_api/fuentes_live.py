# -*- coding: utf-8 -*-
"""Valores macro EN VIVO de las fuentes externas, para CONTRASTAR con la calibración del modelo en la
pestaña "Fuentes" (Fase 2). Hoy: Damodaran (CRP → `rp`, ERP de mercado maduro → `pm`) de Colombia, y la
TRM oficial del Banco de la República (dato de mercado de REFERENCIA, no entra al WACC).

SOLO REFERENCIA — NO alimenta el WACC ni mueve cifras (eso sería Fase 3, con re-baseline y aprobación).
Cacheado por DÍA (Damodaran se actualiza ~anual; la TRM, a diario; evita pegarle a la fuente en cada
request). Tolerante a fallos: si la fuente no responde, `disponible=False` y la web degrada limpio.
"""
from __future__ import annotations

import datetime

from .conectores import banrep, damodaran

_cache: dict[str, dict] = {}

# Página oficial de la TRM (Banco de la República). El VALOR se lee en vivo del conector SDMX.
URL_TRM = "https://www.banrep.gov.co/es/estadisticas/trm"
URL_IBR = "https://www.banrep.gov.co/es/estadisticas/ibr"


def _hoy() -> str:
    return datetime.date.today().isoformat()


def damodaran_colombia(*, fetch=damodaran.fetch_damodaran) -> dict:
    """CRP/ERP de Colombia en vivo → {rp, pm} (cacheado por día). `fetch` inyectable para pruebas.

    `pm` (prima de mercado del WACC) = ERP de mercado MADURO = ERP total del país − CRP del país.
    `rp` (riesgo país del WACC) = CRP del país. Ambos como fracción (0.0285 = 2.85%), igual que el motor.
    """
    hoy = _hoy()
    if hoy in _cache:
        return _cache[hoy]

    payload = {"disponible": False, "fuente": "Damodaran (NYU Stern)", "url": damodaran.URL}
    try:
        por_clave = {v.clave.split(":")[1]: v for v in fetch("Colombia")}
        crp = por_clave.get("crp")
        erp = por_clave.get("erp_total")
        if crp is not None and erp is not None:
            mature = round(erp.valor - crp.valor, 6)  # ERP de mercado maduro = ERP total − CRP
            fila = (crp.detalle or {}).get("fila") or []
            payload = {
                "disponible": True,
                "fuente": "Damodaran (NYU Stern)",
                "url": damodaran.URL,
                "nota": crp.fuente_normativa,  # "Country Risk Premiums (anual)"
                "rating": fila[1] if len(fila) > 1 else None,
                "datos": {
                    "rp": {"valor": crp.valor},
                    "pm": {"valor": mature},
                },
            }
    except Exception:  # noqa: BLE001 — cualquier fallo de red/parseo → degrada a no-disponible
        pass

    _cache[hoy] = payload
    return payload


def banrep_trm(*, fetch=banrep.fetch_serie) -> dict:
    """TRM oficial (COP/USD) en vivo del Banco de la República, cacheada por día. `fetch` inyectable
    para pruebas. Dato de mercado de REFERENCIA — no alimenta el WACC. Degrada a `disponible=False` si
    Banrep no responde."""
    clave = f"trm:{_hoy()}"
    if clave in _cache:
        return _cache[clave]

    payload = {"disponible": False, "fuente": "Banco de la República", "url": URL_TRM}
    try:
        v = fetch("trm")
        if v is not None:
            payload = {
                "disponible": True,
                "fuente": v.fuente,
                "url": URL_TRM,
                "valor": v.valor,
                "unidad": v.unidad,
                "periodo": (v.detalle or {}).get("periodo"),
            }
    except Exception:  # noqa: BLE001 — cualquier fallo de red/parseo → degrada a no-disponible
        pass

    _cache[clave] = payload
    return payload


def banrep_ibr(*, fetch=banrep.fetch_serie) -> dict:
    """IBR overnight (tasa de referencia) en vivo de Banrep, cacheado por día. Degrada a
    `disponible=False` si Banrep no responde. Sirve para anclar la senda base de la tasa en el abanico."""
    clave = f"ibr:{_hoy()}"
    if clave in _cache:
        return _cache[clave]

    payload = {"disponible": False, "fuente": "Banco de la República", "url": URL_IBR}
    try:
        v = fetch("ibr")
        if v is not None:
            payload = {"disponible": True, "fuente": v.fuente, "url": URL_IBR,
                       "valor": v.valor, "unidad": v.unidad, "periodo": (v.detalle or {}).get("periodo")}
    except Exception:  # noqa: BLE001 — cualquier fallo de red/parseo → degrada a no-disponible
        pass

    _cache[clave] = payload
    return payload


def abanico_macro(*, anio: int | None = None) -> dict:
    """Escenarios macro (abanico forward): ancla la senda BASE a los datos vivos de Banrep (TRM, IBR)
    cuando están disponibles y delega la proyección al motor puro `macro_forward`. La inflación usa el
    default grounded (meta Banrep). Robusto: si una fuente no responde, ese driver usa su default."""
    import datetime as _dt

    from aleph_engine import macro_forward as mf

    anclas: dict[str, float] = {}
    trm = banrep_trm()
    if trm.get("disponible") and trm.get("valor"):
        anclas["trm"] = float(trm["valor"])
    ibr = banrep_ibr()
    if ibr.get("disponible") and ibr.get("valor") is not None:
        v = float(ibr["valor"])
        anclas["tasa"] = v / 100.0 if v > 1 else v   # normaliza % (9.25) → ratio (0.0925)

    anio = anio or _dt.date.today().year
    r = mf.proyectar(anio_inicio=anio, anclas=anclas)
    r["anclas_vivas"] = {"trm": trm, "ibr": ibr}     # procedencia para la UI (fuente + periodo)
    return r
