# -*- coding: utf-8 -*-
"""Construcción de los payloads de la API a partir del resultado del motor (contrato §5).

NO calcula fórmulas: arma las respuestas desde `aleph_engine` (`calcular`, `metrics`, `checks`,
`portfolio`, `modelo`). Las cifras salen tal cual del motor; aquí solo se estructuran + se añaden las
**etiquetas de base** (gobernanza de cifras: nunca "TIR" a secas).
"""
from __future__ import annotations

import logging

from aleph_engine import calcular, checks, cierre, config, due_diligence, finanzas, goal_seek as gs, mercado, metrics, modelo, portfolio, simulacion, tributario, urbanismo

from . import repo

_log = logging.getLogger("aleph_api.build")


def _estado(par: dict) -> str:
    e = (par.get("meta") or {}).get("estado") or config.ESTADO_DEFAULT
    return e if e in config.ESTADOS else config.ESTADO_DEFAULT


def _base_label(ap: dict) -> str:
    """Etiqueta de base del proyecto: si el waterfall de fiducia corrió, las cifras son auditadas."""
    return "auditado_fiducia" if ap.get("fiducia_real") else "modelo_aprobado"


def indicadores(R: dict) -> dict:
    """Indicadores de rentabilidad/caja CON etiqueta de base (TIR proyecto vs TIR socio, etc.)."""
    ap = R.get("apalancamiento") or {}
    pg = R.get("pyg") or {}
    return {
        "base_label": _base_label(ap),
        "fiducia_real": bool(ap.get("fiducia_real")),
        "tir_proyecto": ap.get("tir_proyecto"), "tir_proyecto_label": metrics.etiqueta("tir_proyecto"),
        "tir_socio": ap.get("tir_equity"), "tir_socio_label": metrics.etiqueta("tir_socio"),
        "tir_apalancada_ref": ap.get("tir_apalancada_ref"),
        "vpn_proyecto": ap.get("vpn_proyecto"), "vpn_label": metrics.etiqueta("vpn_proyecto"),
        "wacc": ap.get("wacc"), "tio": ap.get("tio"), "payback_mes": ap.get("payback_mes"),
        "credito_max": ap.get("credito_max"), "credito_prom": ap.get("credito_prom"),
        "intereses_total": ap.get("intereses_total"), "max_necesidad_caja": ap.get("max_necesidad_caja"),
        "valor_financiable": ap.get("valor_financiable"), "margen_oper": pg.get("margen_oper"),
        # --- A2 (curso Camacol): incidencia del lote + costo de oportunidad explícito ---
        "incidencia_lote": pg.get("incidencia_lote"), "incidencia_lote_label": metrics.etiqueta("incidencia_lote"),
        "costo_oportunidad": ap.get("tio"), "costo_oportunidad_label": metrics.etiqueta("costo_oportunidad"),
        # --- A3 (curso Camacol): precios constantes (tasas REALES deflactadas por inflación, Fisher) ---
        "inflacion": ap.get("inflacion"),
        "tir_proyecto_real": ap.get("tir_proyecto_real"), "tir_proyecto_real_label": metrics.etiqueta("tir_proyecto_real"),
        "tir_socio_real": ap.get("tir_equity_real"), "tir_socio_real_label": metrics.etiqueta("tir_socio_real"),
        # --- C1 (curso Camacol M4/M6): capa after-tax de DECISIÓN (preliminar [VALIDAR asesor]) ---
        "tir_proyecto_at": ap.get("tir_proyecto_at"), "tir_proyecto_at_label": metrics.etiqueta("tir_proyecto_at"),
        "tir_socio_at": ap.get("tir_equity_at"), "tir_socio_at_label": metrics.etiqueta("tir_socio_at"),
        "vpn_at": ap.get("vpn_at"), "vpn_at_label": metrics.etiqueta("vpn_at"),
        "tir_proyecto_pre_mensual": ap.get("tir_proyecto_pre_mensual"),   # base mensual pre-imp. (delta limpio)
        "impuesto_renta_at": ap.get("impuesto_renta_at"), "gmf_at": ap.get("gmf_at"),
        "iva_vis_devolucion": ap.get("iva_vis_devolucion"),
        "carga_tributaria_neta_at": ap.get("carga_tributaria_neta_at"),
        "after_tax_metodo": ap.get("after_tax_metodo"),
        # --- Veredicto de Valor (EVA del proyecto) — ADITIVO: ¿genera o destruye valor sobre el WACC? ---
        "crea_valor": ap.get("crea_valor"), "crea_valor_label": metrics.etiqueta("crea_valor"),
        "valor_creado": ap.get("valor_creado"), "valor_creado_label": metrics.etiqueta("valor_creado"),
        "spread_valor": ap.get("spread_valor"), "spread_valor_label": metrics.etiqueta("spread_valor"),
        "valor_metodo": "Valor sobre el costo del capital (WACC). Veredicto = TIR proyecto vs WACC.",
    }


def _checks(R: dict) -> list[dict]:
    return [{"clave": c.clave, "nombre": c.nombre, "ok": c.ok, "detalle": c.detalle}
            for c in checks.correr(R)]


def project(slug: str, par: dict, R: dict) -> dict:
    """Ficha del proyecto (§5 GET /projects/{id})."""
    pg = R.get("pyg") or {}
    ap = R.get("apalancamiento") or {}
    estado = _estado(par)
    return {
        "id": slug, "es_real": repo.es_real(slug), "fuente": repo.fuente(),
        "meta": R.get("meta"), "estado": estado, "estado_label": config.ESTADO_LABEL.get(estado, estado),
        "disclaimer": par.get("disclaimer"),   # aviso de gobernanza opcional (escenario PROVISIONAL → banner)
        "urbanistico": R.get("urbanistico"),
        "kpis_cabecera": {
            "ventas": pg.get("ventas"), "util_oper": pg.get("util_oper"), "udi": pg.get("udi"),
            "margen_oper": pg.get("margen_oper"), "tir_proyecto": ap.get("tir_proyecto"),
            "tir_socio": ap.get("tir_equity"), "vpn_proyecto": ap.get("vpn_proyecto"),
        },
        "params": par,
    }


def results(slug: str, par: dict, R: dict) -> dict:
    """Payload central (§5 GET /scenarios/{id}/results): indicadores + P&G + flujo + crédito + checks."""
    return {
        "scenario_id": f"{slug}:base", "project_id": slug, "es_base": True,
        "base_label": _base_label(R.get("apalancamiento") or {}),
        "indicadores": indicadores(R),
        "pyg": R.get("pyg"),
        "flujo": {"apalancado": R.get("apalancamiento"), "simple": R.get("flujo")},
        "distribucion": R.get("distribucion"),
        "cierre": cierre.cierre_financiero(R),   # Fuentes y Usos (curso Camacol §M6)
        "due_diligence": due_diligence.evaluar(par),   # registro de riesgos + viabilidad cualitativa (B1)
        "urbanismo": urbanismo.evaluar(R.get("urbanistico"), par.get("pot")),   # cumplimiento POT (B2)
        "mercado": mercado.evaluar(par, R),   # contraste de supuestos vs comparables de la zona (B3)
        "checks": _checks(R),
    }


def scenarios_list(slug: str) -> dict:
    """Escenarios deterministas del proyecto (§5 GET /projects/{id}/scenarios)."""
    return {
        "project_id": slug, "default": "base",
        "scenarios": [
            {"id": f"{slug}:base", "tipo": "guardado", "d_precio": 0.0, "d_costo": 0.0, "es_base": True},
            {"id": f"{slug}:optimista", "d_precio": 0.05, "d_costo": -0.02, "es_base": False},
            {"id": f"{slug}:pesimista", "d_precio": -0.10, "d_costo": 0.05, "es_base": False},
        ],
    }


def sensitivity(slug: str, par: dict) -> dict:
    """Sensibilidad determinista (§5 GET /scenarios/{id}/sensitivity): escenarios + tornado + heatmap."""
    pasos = [-0.10, -0.05, 0.0, 0.05, 0.10]
    return {
        "scenario_id": f"{slug}:base", "project_id": slug,
        "escenarios": modelo.escenarios(par),
        "tornado": modelo.sensibilidades(par),
        "matriz_2d": {
            "pasos_precio": [p * 100 for p in pasos], "pasos_costo": [p * 100 for p in pasos],
            "margen_pct": modelo.heatmap_sensibilidad(par, pasos),
        },
    }


def _iso(d):
    """Fecha (date) → ISO 'YYYY-MM-DD', o None."""
    return d.isoformat() if hasattr(d, "isoformat") else None


def _mes_offset(d, base) -> int:
    """Meses entre `base` y `d` (mismo criterio que ingresos.recaudo_portafolio)."""
    return (d.year - base.year) * 12 + (d.month - base.month)


def schedule(slug: str, par: dict, R: dict) -> dict:
    """Cronograma + absorción + recaudo (§5 GET /scenarios/{id}/schedule).

    Expone TAL CUAL lo que el motor ya calcula: hitos por etapa (IV/PE/FV/IC/FC → Gantt), la curva de
    absorción de ventas (unidades vendidas/entregadas por mes + acumulado) y el recaudo mensual
    (separación / cuota inicial / subrogación). No recalcula nada. Las series viven en una línea de
    tiempo GLOBAL (mes 0 = `base_date` = IV de la etapa raíz) y se recortan a la ventana activa.
    """
    hitos = R.get("hitos") or {}
    recaudo = R.get("recaudo") or {}
    vacio = {
        "scenario_id": f"{slug}:base", "project_id": slug, "base_date": None, "horizonte": 0,
        "unidades_total": 0, "etapas": [],
        "absorcion": {"ventas": [], "entregas": [], "acum_ventas": [], "acum_entregas": []},
        "recaudo": {"separacion": [], "cuota_inicial": [], "subrogacion": [], "total": []},
    }
    if not hitos:
        return vacio   # proyecto sin etapas datadas (p.ej. greenfield): la UI muestra "sin cronograma"

    base = min(h["IV"] for h in hitos.values())
    # Offsets de escrituración / entrega por etapa (fases del Gantt que no viven en los hitos IV/PE/FV/IC/FC).
    _off = {e.get("cod", i + 1): (e.get("escrituracion"), e.get("entrega"))
            for i, e in enumerate(par.get("etapas", []))}
    etapas = []
    for cod, h in sorted(hitos.items(), key=lambda kv: (kv[1]["IV"], str(kv[0]))):
        iv_mes = _mes_offset(h["IV"], base)
        esc_off, ent_off = _off.get(cod, (None, None))
        esc_mes = iv_mes + esc_off if esc_off is not None else None
        ent_mes = iv_mes + ent_off if ent_off is not None else None
        etapas.append({
            "cod": cod, "nombre": h.get("nombre"), "unidades": h.get("unidades", 0),
            "iv": _iso(h["IV"]), "pe": _iso(h["PE"]), "fv": _iso(h["FV"]),
            "ic": _iso(h["IC"]), "fc": _iso(h["FC"]), "dur_obra": h.get("dur_obra"),
            "iv_mes": iv_mes, "pe_mes": _mes_offset(h["PE"], base),
            "fv_mes": _mes_offset(h["FV"], base), "ic_mes": _mes_offset(h["IC"], base),
            "fc_mes": _mes_offset(h["FC"], base),
            # escrituración, entrega y fin de cuotas iniciales (= hasta escrituración) — meses desde base
            "esc_mes": esc_mes, "ent_mes": ent_mes, "cuo_fin_mes": esc_mes,
        })

    sep = list(recaudo.get("separacion", [])); ci = list(recaudo.get("cuota_inicial", []))
    sub = list(recaudo.get("subrogacion", [])); tot = list(recaudo.get("total", []))
    horizonte = len(tot)
    ventas_g = [0.0] * horizonte; entregas_g = [0.0] * horizonte
    for _cod, e in (recaudo.get("por_etapa") or {}).items():
        off = int(e.get("offset", 0))
        for m, v in enumerate(e.get("ventas", [])):
            if 0 <= off + m < horizonte:
                ventas_g[off + m] += v
        for m, v in enumerate(e.get("entregas", [])):
            if 0 <= off + m < horizonte:
                entregas_g[off + m] += v

    activos = [i for i in range(horizonte) if ventas_g[i] or entregas_g[i] or tot[i]]
    fin = max((max(activos) + 2 if activos else 0),
              max((et["fc_mes"] for et in etapas), default=0) + 2)
    fin = min(max(fin, 1), horizonte) if horizonte else 0

    def _acum(s):
        out, a = [], 0.0
        for x in s:
            a += x; out.append(round(a))
        return out

    def _r(s):
        return [round(x, 2) for x in s[:fin]]

    return {
        "scenario_id": f"{slug}:base", "project_id": slug,
        "base_date": _iso(base), "horizonte": fin,
        "unidades_total": sum(h.get("unidades", 0) for h in hitos.values()),
        "etapas": etapas,
        "absorcion": {
            "ventas": [round(x) for x in ventas_g[:fin]],
            "entregas": [round(x) for x in entregas_g[:fin]],
            "acum_ventas": _acum(ventas_g[:fin]), "acum_entregas": _acum(entregas_g[:fin]),
        },
        "recaudo": {"separacion": _r(sep), "cuota_inicial": _r(ci), "subrogacion": _r(sub), "total": _r(tot)},
    }


def wacc(slug: str, par: dict, R: dict) -> dict:
    """Costo de capital (§5 GET /scenarios/{id}/wacc): build-up CAPM de mercado emergente.

    Expone TODA la cadena que el motor (`finanzas.calcular_wacc(detalle=True)`) ya calcula —
    beta des/reapalancada → Ke USD → +EMBI → paridad de inflación → Ke COP, Kd y escudo fiscal,
    WACC = E·Ke + D·Kd·(1−t) — SIN recalcular. Tasas como fracción decimal (0.1731 = 17.31%).
    `disponible=False` si el proyecto no trae parámetros de WACC (greenfield).
    """
    base = {"scenario_id": f"{slug}:base", "project_id": slug}
    wp = (par.get("financiero") or {}).get("wacc")
    if not wp:
        return {**base, "disponible": False}

    d = finanzas.calcular_wacc(wp, detalle=True)
    ap = R.get("apalancamiento") or {}

    def _pct(k):
        v = wp.get(k)
        return v / 100 if v is not None else None

    return {
        **base, "disponible": True,
        "wacc": d["wacc"], "tio": ap.get("tio"),
        "beta_us": wp.get("beta_us"), "beta_d": d["beta_d"], "beta_u": d["beta_u"], "beta_l": d["beta_l"],
        "ke_usd": d["ke_usd"], "rp": d["rp"], "ke_usd_rp": d["ke_usd_rp"],
        "rplp": d["rplp"], "ke_cop": d["ke_cop"],
        "kd_cop": d["kd_cop"], "kd_despues_imp": d["kd_cop"] * (1 - d["t_col"]),
        "we": d["we"], "wd": d["wd"], "t_col": d["t_col"],
        # Contribuciones al WACC (suman al WACC): E·Ke_cop y D·Kd·(1−t).
        "aporte_equity": d["we"] * d["ke_cop"],
        "aporte_deuda": d["wd"] * d["kd_cop"] * (1 - d["t_col"]),
        "inputs": {
            "rf": _pct("rf"), "rm": _pct("rm"), "pm": d["pm"],
            "kd_us": _pct("kd_us"), "de_us": _pct("de_us"), "tax_us": _pct("tax_us"),
            "de_col": _pct("de_col"), "tax_col": _pct("tax_col"),
            "inf_col": _pct("inf_col"), "inf_us": _pct("inf_us"),
        },
    }


def portafolio(items) -> dict:
    """Consolidado + embudo + items (§5 GET /portfolio). `items` = [(slug, par, R)]."""
    cons = portfolio.consolidar(items)
    pipe = portfolio.pipeline(items)
    cuenta: dict[str, int] = {}
    for d in pipe:
        cuenta[d["estado"]] = cuenta.get(d["estado"], 0) + 1
    embudo = [{"estado": e, "label": config.ESTADO_LABEL.get(e, e), "count": cuenta.get(e, 0)}
              for e in config.ESTADOS]
    consolidado = {k: v for k, v in cons.items() if k != "filas"}
    # Enriquecer cada item con su margen operativo → habilita el mapa de valor (TIR × margen) en la UI.
    # Se reusa la MISMA TIR de los items (apal. ref. / proyecto), consistente con la tabla y sin el
    # TIR degenerado -99% de proyectos greenfield (la constitución prohíbe mostrarlo).
    margen = {s: (R.get("pyg") or {}).get("margen_oper") for s, _p, R in items}
    # Veredicto de Valor por item + CONSOLIDADO del portafolio (¿genera valor sobre el WACC?).
    ver = {s: (R.get("apalancamiento") or {}) for s, _p, R in items}
    for d in pipe:
        apx = ver.get(d["slug"]) or {}
        d["margen"] = margen.get(d["slug"])
        d["crea_valor"] = apx.get("crea_valor")
        d["valor_creado"] = apx.get("valor_creado")
    evaluados = [a for a in ver.values() if a.get("crea_valor") is not None]   # excluye greenfield
    total_vc = sum(a.get("valor_creado") or 0.0 for a in evaluados) if evaluados else None
    consolidado["valor_creado"] = total_vc
    consolidado["crea_valor"] = (total_vc > 0) if total_vc is not None else None
    consolidado["n_genera"] = sum(1 for a in evaluados if a.get("crea_valor") is True)
    consolidado["n_evaluados"] = len(evaluados)
    consolidado["valor_metodo"] = "Veredicto del portafolio = Σ valor creado @WACC (excluye greenfield)."
    return {"consolidado": consolidado, "embudo": embudo, "items": pipe}


def tesoreria(items) -> dict:
    """Tesorería consolidada del portafolio (§5 GET /portfolio/tesoreria): caja y financiación de TODOS
    los proyectos alineadas en el tiempo. Expone lo que `portfolio.tesoreria` agrega; no recalcula."""
    return portfolio.tesoreria(items)


def capital(items) -> dict:
    """Asignación de capital del portafolio (§5 GET /portfolio/capital): equity pico, crédito, valor
    creado (EVA) y eficiencia de capital por proyecto, rankeado. Expone lo que `portfolio.capital`
    agrega; no recalcula."""
    return portfolio.capital(items)


# Escenarios de ESTRÉS ofrecidos al usuario (deltas vs el caso base): precio = ventas, costo = directo,
# ritmo = ventas/mes. Son SUPUESTOS de negocio (no cálculo financiero) — ajustables sin tocar el motor.
ESCENARIOS_ESTRES = [
    {"nombre": "Recesión leve", "precio": -0.07, "costo": 0.03, "ritmo": -0.15},
    {"nombre": "Recesión severa", "precio": -0.15, "costo": 0.05, "ritmo": -0.30},
]


def estres(items) -> dict:
    """Estrés de la tesorería consolidada (§5 GET /portfolio/tesoreria/estres): cuánto se profundiza el
    valle de caja y se mueve el crédito si las ventas caen/se atrasan y suben los costos en TODA la
    cartera. Recalcula cada proyecto con el shock (reusa la maquinaria del Monte Carlo); dorado intacto."""
    return portfolio.estres_tesoreria(items, ESCENARIOS_ESTRES)


def concentracion(items) -> dict:
    """Concentración/diversificación del portafolio (§5 GET /portfolio/concentracion): share + HHI por
    dimensión (proyecto, ubicación, tipo, fase). Expone lo que `portfolio.concentracion` agrega."""
    return portfolio.concentracion(items)


def salud(items) -> dict:
    """Cabina del CEO (§5 GET /portfolio/salud): salud del portafolio + ALERTAS estructuradas (valor,
    concentración, resiliencia, capital). Expone lo que `portfolio.salud` sintetiza; no recalcula
    cifras de decisión (las alertas derivan de las otras vistas + un escenario de estrés severo)."""
    return portfolio.salud(items)


def run(par: dict, req: dict) -> dict:
    """Monte Carlo (§5 POST /scenarios/{id}/run): el único cálculo intensivo. No muta `par`."""
    tipo = (req or {}).get("tipo", "tir")
    n = int((req or {}).get("n", 300))
    seed = (req or {}).get("seed", 42)
    rp = tuple((req or {}).get("rango_precio", (-0.15, 0.15)))
    rc = tuple((req or {}).get("rango_costo", (-0.10, 0.10)))
    if tipo == "margen":
        return modelo.montecarlo(par, n=n, rango_precio=rp, rango_costo=rc, seed=seed)
    rv = tuple((req or {}).get("rango_ventas", (-0.30, 0.30)))
    sigue = bool((req or {}).get("escrituracion_sigue_obra", True))
    return modelo.montecarlo_tir(par, n=n, rango_precio=rp, rango_costo=rc, rango_ventas=rv,
                                 seed=seed, escrituracion_sigue_obra=sigue)



def montecarlo_cb(par: dict, req: dict) -> dict:
    """Monte Carlo Crystal Ball (M5): distribuciones por variable, percentiles, bandas de certeza y
    tornado de contribucion a la varianza. No muta `par`. `req` puede traer n/seed/hurdle y una lista
    `supuestos` [{variable,dist,params,nombre}]; si no, usa las distribuciones por defecto."""
    req = req or {}
    sup = None
    if req.get("supuestos"):
        sup = [simulacion.Supuesto(x["variable"], x["dist"], x.get("params", {}), x.get("nombre", ""))
               for x in req["supuestos"]]
    return simulacion.simular(
        par, supuestos=sup, n=int(req.get("n", 1000)), seed=req.get("seed", 42),
        hurdle=req.get("hurdle"), incluir_valores=bool(req.get("incluir_valores", True)))


def goal_seek(par: dict, req: dict) -> dict:
    """Goal-seek (M4): resuelve que driver (precio/costo/ritmo) lleva a una meta. `req`: objetivo, meta,
    y `driver` (uno) o `drivers` (varios, por defecto los tres). No muta `par`."""
    req = req or {}
    objetivo = req.get("objetivo", "margen")
    meta = float(req.get("meta", 0.0))
    rango = tuple(req.get("rango", (-0.5, 0.5)))
    if req.get("driver"):
        return gs.resolver(par, objetivo, meta, req["driver"], rango=rango)
    drivers = tuple(req.get("drivers", gs.DRIVERS))
    return gs.alcanzar(par, objetivo, meta, drivers=drivers, rango=rango)

# ---------- helpers de carga ----------

def cargar_calcular(slug: str):
    """(par, R) del proyecto, o (None, None) si no existe."""
    par = repo.cargar(slug)
    if par is None:
        return None, None
    return par, calcular(par)


def items_portafolio():
    """[(slug, par, R)] de todos los proyectos disponibles (omite los que fallan)."""
    out = []
    for slug in repo.listar():
        try:
            par = repo.cargar(slug)
            out.append((slug, par, calcular(par)))
        except Exception as e:
            _log.warning("Proyecto '%s' omitido del portafolio (%s)", slug, e.__class__.__name__)
            continue
    return out


def vehiculos(slug: str, par: dict) -> dict:
    """Comparador de vehiculos juridico-financieros (M3 GET /scenarios/{id}/vehiculos).

    Efecto FISCAL (renta por vehiculo + VIS/No-VIS) y del WATERFALL (after-tax: renta+GMF+dividendos)
    de cada estructura, en base mensual CONSISTENTE; la TIR auditada de la fiducia se reporta aparte
    como cifra oficial. Las tasas de GMF (4x1000) y dividendos son PLACEHOLDERS [VALIDAR asesor fiscal].
    """
    c = tributario.comparar(par)
    return {
        "scenario_id": f"{slug}:base", "project_id": slug,
        "advertencia": "Cifras DIRECCIONALES de apoyo a la decision, no asesoria tributaria. Las tasas "
                       "de GMF (4x1000) y dividendos son supuestos POR VALIDAR con el asesor fiscal; la "
                       "TIR de comparacion es mensual (la oficial de la fiducia es la auditada anual).",
        **c,
    }


def recalc(par: dict, req: dict) -> dict:
    """Recalculo EN VIVO (M4b · forward): aplica deltas de precio/costo/ritmo y devuelve los indicadores.
    Reutiliza `modelo.mc_contexto`+`mc_trial` (determinista, rapido). No muta `par`.

    OJO base: como `mc_trial` ignora el override de fiducia (la cifra auditada es fija), las TIR/VPN
    aqui estan en BASE MENSUAL (direccionales); el `margen` SI es exacto. La cifra oficial es la de la
    ficha (auditada). Pensado para sliders de sensibilidad, no para reemplazar la TIR oficial.
    """
    req = req or {}
    dp = float(req.get("precio", 0.0))
    dc = float(req.get("costo", 0.0))
    dv = float(req.get("ritmo", 0.0))
    ctx = modelo.mc_contexto(par)
    base = modelo.mc_trial(ctx, 0.0, 0.0, 0.0)
    res = modelo.mc_trial(ctx, dp, dc, dv)
    return {
        "deltas": {"precio": dp, "costo": dc, "ritmo": dv},
        "base": base,
        "resultado": res,
        "nota": "Simulacion en base mensual: el margen es exacto; TIR/VPN son DIRECCIONALES "
                "(la oficial es la auditada de la ficha).",
    }
