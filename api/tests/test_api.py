# -*- coding: utf-8 -*-
"""Tests de la API (Fase 4a). Contrato dorado + fidelidad al motor + humo de endpoints.

La API NO debe alterar las cifras del motor: expone exactamente lo que `aleph_engine.calcular()`
produce. El test de contrato dorado (datos REALES de Navarra, solo en local) clava TIR proyecto ~37.60%.
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from aleph_engine import calcular

from aleph_api import repo, write
from aleph_api.main import app

client = TestClient(app)
SLUGS = repo.listar()
NAV = "1_navarra"


def test_version():
    j = client.get("/version").json()
    assert j["version"] and j["engine_version"]


@pytest.mark.skipif(not SLUGS, reason="no hay proyectos disponibles")
def test_portfolio():
    r = client.get("/v1/portfolio")
    assert r.status_code == 200
    j = r.json()
    assert "consolidado" in j and "embudo" in j
    assert len(j["items"]) == len(SLUGS)
    # el embudo cubre los estados del ciclo de vida
    assert {e["estado"] for e in j["embudo"]}
    # mapa de valor: cada item trae margen (TIR/margen/ventas/tipo ya presentes)
    assert all({"nombre", "tir", "margen", "ventas", "tipo"} <= it.keys() for it in j["items"])


@pytest.mark.skipif(not SLUGS, reason="no hay proyectos disponibles")
def test_veredicto_valor_eva():
    """Veredicto de Valor (EVA) — ADITIVO: en el portafolio (item + consolidado) y en los indicadores
    del proyecto, con etiqueta de base. Navarra genera valor (TIR proyecto > WACC)."""
    p = client.get("/v1/portfolio").json()
    c = p["consolidado"]
    assert {"crea_valor", "valor_creado", "n_genera", "n_evaluados"} <= c.keys()
    assert all("crea_valor" in it and "valor_creado" in it for it in p["items"])
    if NAV in SLUGS:
        ind = client.get(f"/v1/scenarios/{NAV}:base/results").json()["indicadores"]
        assert {"crea_valor", "valor_creado", "spread_valor", "crea_valor_label", "valor_metodo"} <= ind.keys()
        assert "Veredicto de valor" in ind["crea_valor_label"]
        if ind["tir_proyecto"] and ind["tir_proyecto"] > -0.5:   # Navarra: 37.60% > WACC → genera
            assert ind["crea_valor"] is True and ind["spread_valor"] > 0 and ind["valor_creado"] > 0
            assert ind["spread_valor"] == pytest.approx(ind["tir_proyecto"] - ind["wacc"], abs=1e-6)


@pytest.mark.skipif(NAV not in SLUGS, reason="Navarra no disponible")
def test_project_y_results_fieles_al_motor():
    pj = client.get(f"/v1/projects/{NAV}").json()
    assert pj["id"] == NAV and "kpis_cabecera" in pj and "estado_label" in pj

    res = client.get(f"/v1/scenarios/{NAV}:base/results").json()
    ind = res["indicadores"]
    # Gobernanza de cifras: etiqueta de base presente y TIR doble DISTINTA.
    assert ind["tir_proyecto_label"] and ind["tir_socio_label"]
    assert ind["tir_proyecto_label"] != ind["tir_socio_label"]
    # Fidelidad: la API expone EXACTAMENTE lo que calcula el motor.
    R = calcular(repo.cargar(NAV))
    assert ind["tir_proyecto"] == R["apalancamiento"]["tir_proyecto"]
    assert ind["tir_socio"] == R["apalancamiento"]["tir_equity"]
    assert ind["vpn_proyecto"] == R["apalancamiento"]["vpn_proyecto"]
    # Checks de cuadre presentes y todos OK.
    assert res["checks"] and all(c["ok"] for c in res["checks"])
    # Cierre financiero (Fuentes=Usos) presente y cuadra (fuentes = usos operativos + utilidad).
    ci = res["cierre"]
    assert ci and ci["cuadre"]["ok"]
    assert ci["fuentes_total"] == pytest.approx(ci["usos_total"] + ci["utilidad_operativa"], rel=1e-6)
    # Due diligence (B1): veredicto cualitativo + checklist + matriz de riesgos (probabilidad × impacto).
    ddv = res["due_diligence"]
    assert ddv and ddv["veredicto"]["nivel"] in ("verde", "ambar", "rojo")
    assert ddv["veredicto"]["n_items"] >= 16
    assert {f["clave"] for f in ddv["frentes"]} == {"legal", "ambiental", "urbanistico", "tecnico", "comercial", "bancario"}
    assert set(ddv["severidad_resumen"]) == {"alto", "medio", "bajo"}   # matriz de riesgos (Fase 1)
    assert all("probabilidad" in i and "severidad" in i for i in ddv["items"])
    # Viabilidad urbanística (B2): cumplimiento POT.
    urv = res["urbanismo"]
    assert urv and urv["veredicto"]["nivel"] in ("cumple", "al_limite", "excede", "sin_pot")
    # Estudio de mercado (B3): contraste de supuestos.
    mkv = res["mercado"]
    assert mkv and mkv["veredicto"]["nivel"] in ("en_mercado", "revisar", "sin_datos")


@pytest.mark.skipif(not repo.es_real(NAV), reason="datos REALES de Navarra no presentes (p.ej. CI)")
def test_contrato_dorado_navarra():
    res = client.get(f"/v1/scenarios/{NAV}:base/results").json()
    # Cifra dorada de Navarra (datos reales): TIR proyecto 37.60%.
    assert 0.37 <= res["indicadores"]["tir_proyecto"] <= 0.385


@pytest.mark.skipif(NAV not in SLUGS, reason="Navarra no disponible")
def test_sensitivity_y_run():
    s = client.get(f"/v1/scenarios/{NAV}:base/sensitivity").json()
    assert len(s["matriz_2d"]["margen_pct"]) == 5
    assert "escenarios" in s and "tornado" in s
    r = client.post(f"/v1/scenarios/{NAV}:base/run", json={"tipo": "margen", "n": 50, "seed": 1})
    assert r.status_code == 200


@pytest.mark.skipif(NAV not in SLUGS, reason="Navarra no disponible")
def test_schedule_fiel_al_motor():
    """El cronograma expone EXACTAMENTE los hitos/recaudo del motor; la absorción reconcilia."""
    sc = client.get(f"/v1/scenarios/{NAV}:base/schedule").json()
    R = calcular(repo.cargar(NAV))
    # Una etapa por cada hito del motor; fechas presentes y la etapa raíz arranca en mes 0.
    assert sc["etapas"] and len(sc["etapas"]) == len(R["hitos"])
    e0 = sc["etapas"][0]
    assert all(e0[k] for k in ("iv", "pe", "fv", "ic", "fc"))
    assert e0["iv_mes"] == 0 and sc["base_date"]
    # Series alineadas al horizonte recortado.
    H = sc["horizonte"]
    assert H > 0 and len(sc["recaudo"]["total"]) == H == len(sc["absorcion"]["ventas"])
    # La absorción reconcilia: el acumulado de ventas llega a las unidades del proyecto.
    assert abs(sc["absorcion"]["acum_ventas"][-1] - sc["unidades_total"]) <= 1
    # Recaudo con caja real (separación + cuota inicial + subrogación).
    assert sum(sc["recaudo"]["total"]) > 0


@pytest.mark.skipif(NAV not in SLUGS, reason="Navarra no disponible")
def test_wacc_fiel_al_motor():
    """El build-up CAPM expone lo que el motor calcula; WACC Navarra ~17.66% (beta Homebuilding 0.91 + rp BB-)."""
    w = client.get(f"/v1/scenarios/{NAV}:base/wacc").json()
    assert w["disponible"] is True
    # WACC Navarra ~17.66% (re-baseline beta→Homebuilding, acta beta_homebuilding 20260616; rp 3.43% sin cambio).
    assert 0.17 <= w["wacc"] <= 0.18
    # Cadena coherente: reapalancada > desapalancada > 0; Ke COP > Ke USD (riesgo país + inflación).
    assert w["beta_l"] > w["beta_u"] > 0
    assert w["ke_cop"] > w["ke_usd"]
    # Pesos suman 1 y las contribuciones suman el WACC.
    assert abs(w["we"] + w["wd"] - 1.0) < 1e-9
    assert abs(w["aporte_equity"] + w["aporte_deuda"] - w["wacc"]) < 1e-9
    # Fidelidad: el WACC expuesto == el del motor (apalancamiento).
    R = calcular(repo.cargar(NAV))
    assert abs(w["wacc"] - R["apalancamiento"]["wacc"]) < 1e-9


def test_tesoreria_consolidada():
    """Tesorería consolidada del portafolio: caja + financiación de todos los proyectos en el tiempo."""
    from aleph_api import build
    j = client.get("/v1/portfolio/tesoreria").json()
    if not j.get("disponible"):
        pytest.skip("ningún proyecto con cronograma datado")
    assert len(j["caja"]) == j["horizonte"] and len(j["credito"]) == j["horizonte"]
    assert j["base_date"] and j["n"] >= 1
    assert j["exposicion_maxima"]["valor"] <= 0      # valle de caja = financiación (negativo)
    assert j["credito_maximo"]["valor"] >= 0
    # Fidelidad: la API expone EXACTAMENTE lo que el motor agrega (no recalcula).
    t = build.tesoreria(build.items_portafolio())
    assert j["exposicion_maxima"]["valor"] == pytest.approx(t["exposicion_maxima"]["valor"])
    assert j["credito_maximo"]["valor"] == pytest.approx(t["credito_maximo"]["valor"])


def test_asignacion_capital():
    """Asignación de capital: equity/crédito/EVA/eficiencia por proyecto, rankeado por eficiencia."""
    from aleph_api import build
    j = client.get("/v1/portfolio/capital").json()
    if not j.get("filas"):
        pytest.skip("sin proyectos")
    for f in j["filas"]:
        assert {"slug", "nombre", "equity_pico", "credito_max", "valor_creado", "eficiencia"} <= set(f)
        assert f["equity_pico"] >= 0
        if f["crea_valor"] is None:                   # greenfield → sin veredicto de valor
            assert f["valor_creado"] is None and f["eficiencia"] is None
    # Rankeado por eficiencia descendente (greenfield al final).
    con = [f["eficiencia"] for f in j["filas"] if f["eficiencia"] is not None]
    assert con == sorted(con, reverse=True)
    # Fidelidad con el motor.
    c = build.capital(build.items_portafolio())
    assert j["equity_total"] == pytest.approx(c["equity_total"])


def test_estres_tesoreria():
    """Estrés de la tesorería consolidada: base + escenarios alineados, deltas, fidelidad con el motor."""
    from aleph_api import build
    j = client.get("/v1/portfolio/tesoreria/estres").json()
    if not j.get("disponible"):
        pytest.skip("ningún proyecto con cronograma datado")
    H = j["horizonte"]
    assert len(j["base"]["caja"]) == H and len(j["base"]["credito"]) == H
    assert len(j["escenarios"]) == len(build.ESCENARIOS_ESTRES)
    for es in j["escenarios"]:
        assert len(es["caja"]) == H and len(es["credito"]) == H        # base y escenario alineados
        assert {"nombre", "shock", "exposicion_maxima", "delta_exposicion", "delta_credito"} <= set(es)
        # El valle es negativo; el crédito no negativo. (El delta puede ir en cualquier dirección por
        # efectos de timing: un ritmo más lento desincroniza los picos — no se asume signo.)
        assert es["exposicion_maxima"]["valor"] <= 0 and es["credito_maximo"]["valor"] >= 0
    # Fidelidad con el motor.
    e = build.estres(build.items_portafolio())
    assert j["base"]["exposicion_maxima"]["valor"] == pytest.approx(e["base"]["exposicion_maxima"]["valor"])


def test_concentracion():
    """Concentración por dimensión: shares suman 1, HHI coherente, fidelidad con el motor."""
    from aleph_api import build
    j = client.get("/v1/portfolio/concentracion").json()
    if not j.get("dimensiones"):
        pytest.skip("sin proyectos")
    claves = {d["clave"] for d in j["dimensiones"]}
    assert {"proyecto", "ubicacion", "tipo", "fase"} <= claves
    for d in j["dimensiones"]:
        shares = [cat["share"] for cat in d["categorias"]]
        assert sum(shares) == pytest.approx(1.0)
        assert d["hhi"] == pytest.approx(sum(s ** 2 for s in shares))
    c = build.concentracion(build.items_portafolio())
    assert j["total_ventas"] == pytest.approx(c["total_ventas"])


def test_salud_cabina():
    """Cabina del CEO: salud + alertas estructuradas, resumen consistente, fidelidad con el motor."""
    from aleph_api import build
    j = client.get("/v1/portfolio/salud").json()
    if "alertas" not in j:
        pytest.skip("sin proyectos")
    assert set(j["resumen"]) == {"critico", "alerta", "info"}
    assert sum(j["resumen"].values()) == len(j["alertas"])
    for a in j["alertas"]:
        assert a["nivel"] in ("critico", "alerta", "info")
        assert a["tipo"] and isinstance(a["datos"], dict)
    s = build.salud(build.items_portafolio())
    assert j["valor_creado"] == pytest.approx(s["valor_creado"])


def test_404_proyecto_inexistente():
    assert client.get("/v1/projects/no_existe").status_code == 404
    assert client.get("/v1/scenarios/no_existe:base/results").status_code == 404


class _FakeTable:
    """Encadena select/insert/update/upsert + filtros como el cliente de supabase (ignora filtros).
    `select` devuelve el store del nombre de tabla; `insert` devuelve la fila con un id; `update`/
    `upsert` registran la llamada. Los `_calls` permiten asertar auditoría/cache."""
    def __init__(self, store, name):
        self._store, self._name, self._op = store, name, None

    def select(self, *a, **k):
        self._op = ("select", None); return self

    def insert(self, payload):
        self._op = ("insert", payload); return self

    def update(self, payload):
        self._op = ("update", payload); return self

    def upsert(self, payload, **k):
        self._op = ("upsert", payload); return self

    def delete(self):
        self._op = ("delete", None); return self

    def eq(self, *a, **k):
        return self

    in_ = order = limit = eq

    def execute(self):
        import types as _t
        op, payload = self._op or ("select", None)
        if op == "select":
            return _t.SimpleNamespace(data=self._store.get(self._name, []))
        self._store.setdefault("_calls", []).append((self._name, op, payload))
        if op == "insert":
            rows = payload if isinstance(payload, list) else [payload]
            return _t.SimpleNamespace(data=[{**r, "id": r.get("id", f"{self._name}-id")} for r in rows])
        return _t.SimpleNamespace(data=[])


class _FakeSB:
    def __init__(self, tablas=None):
        self.store = dict(tablas or {})

    def table(self, nombre):
        return _FakeTable(self.store, nombre)

    def calls(self, accion=None):
        return [c for c in self.store.get("_calls", []) if accion is None or c[1] == accion]


def test_fase1_cut_over_lectura_a_scenarios(monkeypatch):
    """Fase 1: con Supabase, cargar() lee el snapshot del escenario (modelo objetivo); la palanca
    ALEPH_READ_SCENARIOS=false revierte a `proyectos.data` (espejo de respaldo)."""
    snap = {"meta": {"nombre": "X"}, "etapas": [{"und": 1}]}
    monkeypatch.setattr(repo, "_usa_supabase", lambda: True)

    # cut-over ON (default): lee de projects→scenarios.snapshot
    monkeypatch.delenv("ALEPH_READ_SCENARIOS", raising=False)
    monkeypatch.setattr(repo, "_cliente", lambda: _FakeSB(
        {"projects": [{"id": "p1", "slug": "x", "es_real": True}],
         "scenarios": [{"snapshot": snap, "status": "approved", "version": 1}]}))
    assert repo.cargar("x") == snap          # snapshot del escenario
    assert repo.es_real("x") is True         # projects.es_real
    assert repo.listar() == ["x"]            # projects.slug

    # palanca de rollback: lee de `proyectos.data`
    monkeypatch.setenv("ALEPH_READ_SCENARIOS", "false")
    monkeypatch.setattr(repo, "_cliente", lambda: _FakeSB({"proyectos": [{"data": {"viejo": True}}]}))
    assert repo.cargar("x") == {"viejo": True}


def _par_min() -> dict:
    """`par` mínimo que PASA el contrato (schema.parse): etapas≥1, costos_pct, financiero,
    lote_bruto_miles, meta. Suficiente para crear/editar draft (no se recalcula)."""
    return {
        "meta": {"nombre": "Prueba", "estado": "prefactibilidad"},
        "etapas": [{"cod": 1, "und": 10, "vmes": 5, "frec": 1, "pe_pct": 0.6, "fecha_inicio": "2026-01-01"}],
        "costos_pct": {"directos": 0.5, "indirectos": 0.1, "honorarios": 0.05, "util_lote": 0.1},
        "financiero": {},
        "lote_bruto_miles": 1000.0,
    }


def _fake_write(monkeypatch, tablas):
    fake = _FakeSB(tablas)
    monkeypatch.setattr(repo, "_usa_supabase", lambda: True)
    monkeypatch.setattr(repo, "_cliente", lambda: fake)
    return fake


def test_write_crear_proyecto_draft_y_audita(monkeypatch):
    fake = _fake_write(monkeypatch, {"projects": [], "companies": [{"id": "c1"}]})
    out = write.crear_proyecto(_par_min(), slug="prueba", nombre="Prueba", es_real=False, actor="me@cg.com")
    assert out["status"] == "draft" and out["version"] == 1 and out["slug"] == "prueba"
    assert any(c[0] == "scenarios" and c[1] == "insert" for c in fake.calls())
    assert any(c[0] == "audit_log" and c[1] == "insert" for c in fake.calls())


def test_write_crear_slug_duplicado_409(monkeypatch):
    _fake_write(monkeypatch, {"projects": [{"id": "p1"}], "companies": [{"id": "c1"}]})
    with pytest.raises(HTTPException) as ei:
        write.crear_proyecto(_par_min(), slug="prueba", nombre="X", es_real=False, actor="me")
    assert ei.value.status_code == 409


def test_write_par_invalido_422(monkeypatch):
    _fake_write(monkeypatch, {"projects": [], "companies": [{"id": "c1"}]})
    with pytest.raises(HTTPException) as ei:  # sin etapas/costos_pct/financiero/lote → contrato falla
        write.crear_proyecto({"meta": {"nombre": "X"}}, slug="x", nombre="X", es_real=False, actor="me")
    assert ei.value.status_code == 422


def test_write_tipologias_malformadas_422(monkeypatch):
    """La compuerta de tipologías rechaza la tabla malformada (precio en miles → gotcha 10x)."""
    _fake_write(monkeypatch, {"projects": [], "companies": [{"id": "c1"}]})
    par = _par_min()
    par["tipologias"] = [{"etapa": 1, "nombre": "A", "clase": "apartamento", "und": 5,
                          "metodo": "$/und", "precio": 200_000}]   # precio en MILES, no PESOS
    with pytest.raises(HTTPException) as ei:
        write.crear_proyecto(par, slug="t", nombre="T", es_real=False, actor="me")
    assert ei.value.status_code == 422 and "Tipolog" in str(ei.value.detail)


def test_write_editar_solo_draft_409(monkeypatch):
    _fake_write(monkeypatch, {"scenarios": [
        {"id": "s1", "project_id": "p1", "version": 1, "status": "approved", "snapshot": {}}]})
    with pytest.raises(HTTPException) as ei:
        write.editar_draft("s1", _par_min(), actor="me")
    assert ei.value.status_code == 409   # un approved es inmutable


def test_write_editar_draft_ok(monkeypatch):
    fake = _fake_write(monkeypatch, {"scenarios": [
        {"id": "s1", "project_id": "p1", "version": 1, "status": "draft", "snapshot": {}}]})
    out = write.editar_draft("s1", _par_min(), actor="me")        # sin If-Match → no chequea concurrencia
    assert out["status"] == "draft" and out["version"] == 1
    assert any(c[0] == "audit_log" for c in fake.calls())


def test_write_editar_if_match_conflicto_409(monkeypatch):
    # Fase 3: con If-Match y la fila cambió (el fake update no afecta filas) → conflicto.
    _fake_write(monkeypatch, {"scenarios": [
        {"id": "s1", "project_id": "p1", "version": 1, "status": "draft", "snapshot": {}}]})
    with pytest.raises(HTTPException) as ei:
        write.editar_draft("s1", _par_min(), actor="me", if_match="2026-01-01T00:00:00Z")
    assert ei.value.status_code == 409


@pytest.mark.skipif(not SLUGS, reason="sin proyectos para un par real")
def test_write_aprobar_recalcula_cache_y_audita(monkeypatch):
    par = repo.cargar(SLUGS[0])           # par REAL (local) → el motor calcula sin problema
    fake = _fake_write(monkeypatch, {"scenarios": [
        {"id": "s1", "project_id": "p1", "version": 1, "status": "draft", "snapshot": par}]})
    out = write.aprobar("s1", actor="me")
    assert out["status"] == "approved" and "tir_proyecto" in out and "checks_ok" in out
    assert any(c[0] == "results_cache" for c in fake.calls())     # guardó el cache
    assert any(c[0] == "audit_log" and c[1] == "insert" for c in fake.calls())


def test_write_aprobar_par_incalculable_422(monkeypatch):
    """Un par que PASA schema.parse pero CRASHEA calcular() (financiero sin wacc) → 422 LEGIBLE,
    no un 500 opaco. El formulario nunca lo dispara (siempre manda WACC); blinda el API directo."""
    _fake_write(monkeypatch, {"scenarios": [
        {"id": "s1", "project_id": "p1", "version": 1, "status": "draft", "snapshot": _par_min()}]})
    with pytest.raises(HTTPException) as ei:
        write.aprobar("s1", actor="me")
    assert ei.value.status_code == 422


def test_write_eliminar_proyecto_borra_y_audita(monkeypatch):
    """Borrado de proyecto por slug: audita ANTES + borra scenarios + projects (cache por escenario)."""
    fake = _fake_write(monkeypatch, {
        "projects": [{"id": "p1", "slug": "x", "nombre": "X", "es_real": False}],
        "scenarios": [{"id": "s1"}, {"id": "s2"}]})
    out = write.eliminar_proyecto("x", actor="me@cg.com")
    assert out["deleted"] is True and out["slug"] == "x" and out["scenarios_borrados"] == 2
    assert any(c[0] == "audit_log" and c[1] == "insert" for c in fake.calls())  # auditó el borrado
    assert any(c[0] == "results_cache" and c[1] == "delete" for c in fake.calls())
    assert any(c[0] == "scenarios" and c[1] == "delete" for c in fake.calls())
    assert any(c[0] == "projects" and c[1] == "delete" for c in fake.calls())


def test_write_eliminar_proyecto_inexistente_404(monkeypatch):
    _fake_write(monkeypatch, {"projects": []})
    with pytest.raises(HTTPException) as ei:
        write.eliminar_proyecto("nope", actor="me")
    assert ei.value.status_code == 404


def test_write_marcar_real(monkeypatch):
    fake = _fake_write(monkeypatch, {"projects": [{"id": "p1", "slug": "x"}]})
    out = write.marcar_real("x", es_real=True, actor="me")
    assert out["es_real"] is True and out["slug"] == "x"
    assert any(c[0] == "projects" and c[1] == "update" for c in fake.calls())
    assert any(c[0] == "audit_log" and c[1] == "insert" for c in fake.calls())


def test_write_obtener_para_editar(monkeypatch):
    """Devuelve el par crudo del escenario vigente + project_id/versión (para pre-llenar el form)."""
    snap = {"meta": {"nombre": "X"}, "etapas": [{"und": 10}]}
    _fake_write(monkeypatch, {
        "projects": [{"id": "p1", "slug": "x", "nombre": "X", "es_real": False}],
        "scenarios": [{"snapshot": snap, "version": 1, "status": "approved"}]})
    out = write.obtener_para_editar("x")
    assert out["project_id"] == "p1" and out["par"] == snap and out["version"] == 1 and out["es_real"] is False


def test_write_obtener_para_editar_404(monkeypatch):
    _fake_write(monkeypatch, {"projects": []})
    with pytest.raises(HTTPException) as ei:
        write.obtener_para_editar("nope")
    assert ei.value.status_code == 404


def test_health_data():
    """Salud de datos público (no sensible): fuente + nº de proyectos. Sirve para verificar el deploy."""
    j = client.get("/health/data").json()
    assert j["data_source"] in ("supabase", "local")
    assert j["project_count"] == len(SLUGS)
    # diagnóstico de Fase 1: de dónde lee el API (local en tests; scenarios/proyectos en prod).
    assert j["read_model"] in ("scenarios", "proyectos", "local")


def test_portfolio_fail_loud_503_si_data_required_y_sin_datos(monkeypatch):
    """En prod la imagen NO trae respaldo local: 0 proyectos = la fuente cayó → 503, no 200 vacío."""
    monkeypatch.setattr(repo, "listar", lambda: [])
    monkeypatch.setenv("ALEPH_DATA_REQUIRED", "true")
    assert client.get("/v1/portfolio").status_code == 503


def test_portfolio_sin_data_required_sigue_devolviendo_vacio(monkeypatch):
    """Sin el flag (dev/CI), 0 proyectos sigue dando 200 con portafolio vacío (comportamiento previo)."""
    monkeypatch.setattr(repo, "listar", lambda: [])
    monkeypatch.delenv("ALEPH_DATA_REQUIRED", raising=False)
    r = client.get("/v1/portfolio")
    assert r.status_code == 200
    assert r.json()["consolidado"]["n"] == 0


def test_macro_rutas_registradas_y_gate_sin_supabase():
    # GET /v1/macro existe (no 404) y, sin Supabase en dev, devuelve 503 (la lectura exige tabla).
    r = client.get("/v1/macro")
    assert r.status_code in (200, 503)
    # la ruta está en el OpenAPI
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/macro" in paths and "/v1/macro/refresh" in paths and "/v1/macro/aprobar" in paths


def test_cron_refresh_token_gate(monkeypatch):
    # sin token configurado en el servidor -> 401 (deshabilitado)
    monkeypatch.delenv("ALEPH_REFRESH_TOKEN", raising=False)
    assert client.post("/macro/cron-refresh", headers={"X-Refresh-Token": "x"}).status_code == 401
    # con token configurado pero header equivocado -> 401
    monkeypatch.setenv("ALEPH_REFRESH_TOKEN", "secreto")
    assert client.post("/macro/cron-refresh", headers={"X-Refresh-Token": "malo"}).status_code == 401
    # token correcto -> pasa el gate y llama refrescar (monkeypatch: sin red/Supabase)
    monkeypatch.setattr("aleph_api.macro_store.refrescar", lambda *a, **k: {"propuestos": 0, "recolectados": 0})
    r = client.post("/macro/cron-refresh", headers={"X-Refresh-Token": "secreto"})
    assert r.status_code == 200 and r.json()["propuestos"] == 0


def test_montecarlo_crystal_ball():
    if NAV not in SLUGS:
        import pytest as _pt; _pt.skip("Navarra no disponible")
    r = client.post(f"/v1/scenarios/{NAV}:base/montecarlo",
                    json={"n": 40, "seed": 3, "incluir_valores": False})
    assert r.status_code == 200
    j = r.json()
    assert "forecasts" in j and "tir_proyecto" in j["forecasts"]
    fc = j["forecasts"]["tir_proyecto"]
    assert "stats" in fc and "tornado" in fc
    assert fc["stats"]["p10"] <= fc["stats"]["p50"] <= fc["stats"]["p90"]   # percentiles ordenados
    cert = fc.get("certeza")
    assert cert is None or 0.0 <= cert["prob"] <= 1.0
    suma = sum(v["contribucion_pct"] for v in fc["tornado"].values())
    assert 99.0 <= suma <= 101.0    # el tornado suma ~100%


def test_goal_seek_devolvernos():
    if NAV not in SLUGS:
        import pytest as _pt; _pt.skip("Navarra no disponible")
    r = client.post(f"/v1/scenarios/{NAV}:base/goal-seek",
                    json={"objetivo": "margen", "meta": 0.07, "driver": "precio"})
    assert r.status_code == 200
    j = r.json()
    assert j["alcanzable"] in (True, False)
    if j["alcanzable"]:
        assert abs(j["valor"] - 0.07) < 1e-2 and "delta" in j


@pytest.mark.skipif(NAV not in SLUGS, reason="Navarra no disponible")
def test_recalc_forward_sliders():
    """M4b — /recalc aplica deltas de precio/costo/ritmo y devuelve indicadores. +5% precio sube margen."""
    r = client.post(f"/v1/scenarios/{NAV}:base/recalc", json={"precio": 0.05})
    assert r.status_code == 200
    j = r.json()
    assert j["deltas"] == {"precio": 0.05, "costo": 0.0, "ritmo": 0.0}
    assert "base" in j and "resultado" in j
    assert j["resultado"]["margen"] > j["base"]["margen"]          # +precio → +margen (exacto)
    assert {"tir_proyecto", "tir_equity", "vpn_proyecto", "margen"} <= j["resultado"].keys()


@pytest.mark.skipif(NAV not in SLUGS, reason="Navarra no disponible")
def test_opciones_fasing_por_etapa():
    """Opciones reales: /opciones lista las etapas + base + resultado. Quitar una etapa no sube unidades."""
    r = client.post(f"/v1/scenarios/{NAV}:base/opciones", json={"mods": {}})
    assert r.status_code == 200
    j = r.json()
    assert j["etapas"] and all("cod" in e and "nombre" in e for e in j["etapas"])
    base = j["base"]
    assert base["indicadores"]["unidades"] > 0 and len(base["caja"]) > 0
    assert base["caja"][0]["m"] == 0
    # quitar la última etapa → no más unidades que la base (directo por etapa)
    cod = j["etapas"][-1]["cod"]
    r2 = client.post(f"/v1/scenarios/{NAV}:base/opciones", json={"mods": {str(cod): {"quitar": True}}})
    assert r2.status_code == 200
    assert r2.json()["resultado"]["indicadores"]["unidades"] <= base["indicadores"]["unidades"]
