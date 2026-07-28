# -*- coding: utf-8 -*-
"""Fase 1 (write side) — persistencia de actuals (upsert idempotente + audit). SIN red ni Supabase.

Prueba `actuals.upsert_actuals` con un cliente Supabase FALSO que registra las llamadas. Verifica el
payload, la clave de upsert (on_conflict), la idempotencia, la auditoría y el dry-run. También recorre
el pipeline completo sobre la MUESTRA (sinco.to_actuals → upsert) y blinda que la clave de upsert del
código coincide con el unique index de la migración 0005.
"""
import json
import types
from datetime import date
from pathlib import Path

import pytest

from aleph_api import actuals
from aleph_api.conectores import sinco
from aleph_api.conectores.sinco import ActualObra

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "db" / "samples" / "sinco_control_proyecto_sample.json"
MIGRACION_0005 = REPO / "db" / "migrations" / "0005_actuals_obra_clave_upsert.sql"


class _FakeTable:
    def __init__(self, calls, name):
        self._calls, self._name, self._op = calls, name, None

    def upsert(self, payload, **k):
        self._op = ("upsert", payload, k); return self

    def insert(self, payload):
        self._op = ("insert", payload, {}); return self

    def execute(self):
        op, payload, k = self._op
        self._calls.append((self._name, op, payload, k))
        return types.SimpleNamespace(data=[])


class _FakeSB:
    def __init__(self):
        self.calls = []

    def table(self, name):
        return _FakeTable(self.calls, name)

    def of(self, name, op=None):
        return [c for c in self.calls if c[0] == name and (op is None or c[1] == op)]


def _regs():
    return [
        ActualObra("navarra", "Cimentacion", date(2026, 1, 1), pv=150, ev=130, ac=140, bac=750,
                   corte=date(2026, 1, 31)),
        ActualObra("navarra", "Estructura", date(2026, 1, 1), pv=200, ev=180, ac=210, bac=800),
    ]


def test_upsert_escribe_y_audita():
    sb = _FakeSB()
    res = actuals.upsert_actuals(sb, _regs(), actor="me@cg.com")
    assert res["upserted"] == 2 and res["dry_run"] is False
    assert res["proyectos"] == ["navarra"] and res["fuentes"] == ["sinco"]
    # upsert en actuals_obra con la clave natural y payload = lista de records
    up = sb.of("actuals_obra", "upsert")
    assert len(up) == 1
    _, _, payload, k = up[0]
    assert k.get("on_conflict") == actuals.CLAVE_UPSERT
    assert isinstance(payload, list) and len(payload) == 2
    assert set(payload[0]) == {"proyecto", "nivel", "periodo", "pv", "ev", "ac", "bac", "corte", "source"}
    assert payload[0]["periodo"] == "2026-01-01" and payload[0]["source"] == "sinco"
    # auditó el lote
    aud = sb.of("audit_log", "insert")
    assert len(aud) == 1 and aud[0][2]["action"] == "upsert_actuals" and aud[0][2]["diff"]["n"] == 2


def test_dry_run_no_escribe():
    sb = _FakeSB()
    res = actuals.upsert_actuals(sb, _regs(), dry_run=True)
    assert res["dry_run"] is True and res["upserted"] == 0 and res["recibidos"] == 2
    assert sb.calls == []          # ni upsert ni audit


def test_lista_vacia_no_escribe():
    sb = _FakeSB()
    res = actuals.upsert_actuals(sb, [])
    assert res["recibidos"] == 0 and res["upserted"] == 0 and sb.calls == []


def test_idempotente_mismo_payload_en_cada_corrida():
    # La idempotencia real la garantiza ON CONFLICT en la BD; aquí blindamos que re-correr produce el
    # MISMO payload y la MISMA clave de conflicto (no inserta filas nuevas, sobreescribe).
    p1 = _FakeSB(); actuals.upsert_actuals(p1, _regs())
    p2 = _FakeSB(); actuals.upsert_actuals(p2, _regs())
    assert p1.of("actuals_obra", "upsert")[0][2] == p2.of("actuals_obra", "upsert")[0][2]
    assert p1.of("actuals_obra", "upsert")[0][3] == p2.of("actuals_obra", "upsert")[0][3]


def test_registro_incompleto_falla_en_voz_alta():
    sb = _FakeSB()
    with pytest.raises(ValueError, match="incompleto"):
        actuals.upsert_actuals(sb, [{"nivel": "X", "periodo": "2026-01-01", "pv": 1, "ev": 1, "ac": 1}])  # sin proyecto
    assert sb.calls == []          # no escribió nada


def test_pv_cero_es_valido_no_se_considera_vacio():
    sb = _FakeSB()
    res = actuals.upsert_actuals(sb, [ActualObra("x", "C", date(2026, 1, 1), pv=0.0, ev=0.0, ac=0.0)])
    assert res["upserted"] == 1


def test_acepta_actualobra_y_dict():
    sb = _FakeSB()
    mixto = [_regs()[0], _regs()[1].as_record()]   # un ActualObra + un dict (claves DISTINTAS)
    res = actuals.upsert_actuals(sb, mixto)
    assert res["upserted"] == 2


def test_dedup_lote_por_clave_conserva_ultima():
    """Dos registros con la MISMA clave (source,proyecto,nivel,periodo) colapsan a 1 (la última gana),
    así Postgres no aborta con 'cannot affect row a second time'."""
    sb = _FakeSB()
    a = ActualObra("navarra", "Cimentacion", date(2026, 1, 1), pv=100, ev=90, ac=95, corte=date(2026, 1, 10))
    b = ActualObra("navarra", "Cimentacion", date(2026, 1, 1), pv=150, ev=130, ac=140, corte=date(2026, 1, 31))
    res = actuals.upsert_actuals(sb, [a, b])
    assert res["recibidos"] == 2 and res["upserted"] == 1     # colapsó a una sola clave
    payload = sb.of("actuals_obra", "upsert")[0][2]
    assert len(payload) == 1 and payload[0]["pv"] == 150 and payload[0]["corte"] == "2026-01-31"  # la última


def test_pipeline_muestra_to_actuals_y_upsert():
    """La muestra es válida: to_actuals la transforma y upsert_actuals la persiste."""
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    regs = sinco.to_actuals(d["filas"], d["mapeo"])
    assert regs, "la muestra debe producir registros"
    sb = _FakeSB()
    res = actuals.upsert_actuals(sb, regs)
    assert res["upserted"] == len(regs)
    assert set(res["proyectos"]) == {"navarra", "dominica"}


def test_clave_upsert_coincide_con_migracion_0005():
    """Blindaje: la clave del código == el unique index de la migración (evita drift silencioso)."""
    sql = MIGRACION_0005.read_text(encoding="utf-8").lower()
    cols = "(" + ", ".join(actuals.CLAVE_UPSERT.split(",")) + ")"   # "(source, proyecto, nivel, periodo)"
    assert cols in sql, f"el index de 0005 debe ser sobre {cols}"
