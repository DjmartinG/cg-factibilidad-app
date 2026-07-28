# -*- coding: utf-8 -*-
"""Persistencia de actuals de obra (valor ganado) en Supabase — lado de ESCRITURA de FASE 1.

Recibe registros ya transformados (`sinco.to_actuals` → `ActualObra`) y los UPSERTEA idempotentemente
en `actuals_obra` (migraciones 0004/0005) por la clave natural (source, proyecto, nivel, periodo):
re-correr el ETL SOBREESCRIBE el estado de cada proyecto·nivel·mes con la extracción más reciente (el
Monitor lee el estado ACTUAL). Audita un resumen de la carga.

NO toca el motor `aleph_engine` ni el dorado: solo persiste agregados (sin datos personales). Igual que
`write.py`, recibe el cliente Supabase (service_role) que se le pasa → testeable con un cliente falso.

NOTA DE GOBERNANZA (decidir en FASE 2, no aquí): la migración 0001 ya define `actuals_evm`
(grano proyecto·fecha_corte, con spi/cpi derivados, `fuente` ∈ manual|excel|erp|crm) y `actuals_recaudo`.
`actuals_obra` es el LANDING de grano fino (proyecto·nivel/WBS·mes, `source='sinco'`, crudo PV/EV/AC/BAC).
La reconciliación (¿el EVM rueda `actuals_obra` → `actuals_evm`? ¿se amplía el check de `fuente` para
'sinco'?) se define cuando se cablee `evm.py` al Monitor, con el dato real a la vista.
"""
from __future__ import annotations

from .conectores.sinco import ActualObra

# Debe coincidir EXACTAMENTE con el unique index de la migración 0005 (columnas planas).
CLAVE_UPSERT = "source,proyecto,nivel,periodo"

# Campos que un registro DEBE traer para persistirse. pv/ev/ac pueden ser 0.0 (no se consideran "vacíos").
_REQUERIDOS = ("source", "proyecto", "nivel", "periodo", "pv", "ev", "ac")


def _a_record(r) -> dict:
    """`ActualObra` (o dict ya en forma de columnas) → dict listo para upsert. Valida mínimos."""
    rec = r.as_record() if isinstance(r, ActualObra) else dict(r)
    rec.setdefault("source", "sinco")
    faltan = [k for k in _REQUERIDOS if rec.get(k) in (None, "")]
    if faltan:
        raise ValueError(f"Registro de actuals incompleto (faltan {faltan}): {rec}")
    return rec


def upsert_actuals(sb, registros, *, actor: str = "etl_sinco", dry_run: bool = False) -> dict:
    """Upsert idempotente de `registros` (list[ActualObra] o dicts) en `actuals_obra` por CLAVE_UPSERT.
    Devuelve un resumen. `dry_run=True` (o lista vacía) NO escribe: solo reporta qué haría. Cuando
    escribe, audita un resumen del lote en `audit_log`."""
    recs = [_a_record(r) for r in registros]
    recibidos = len(recs)
    # Deduplicar por la CLAVE de conflicto DENTRO del lote (la última ocurrencia gana). Postgres aborta
    # TODO el upsert si un mismo INSERT trae dos filas que colisionan en el arbiter index ("ON CONFLICT
    # DO UPDATE command cannot affect row a second time"). Así el contrato "estado actual por clave" se
    # cumple a nivel de lote, sin depender de que el caller venga sin duplicados.
    cols = CLAVE_UPSERT.split(",")
    recs = list({tuple(r[c] for c in cols): r for r in recs}.values())
    proyectos = sorted({r["proyecto"] for r in recs})
    periodos = sorted({r["periodo"] for r in recs})
    fuentes = sorted({r["source"] for r in recs})
    resumen = {
        "recibidos": recibidos, "upserted": 0, "dry_run": bool(dry_run),
        "proyectos": proyectos, "periodos": periodos, "fuentes": fuentes,
    }
    if not recs or dry_run:
        return resumen
    sb.table("actuals_obra").upsert(recs, on_conflict=CLAVE_UPSERT).execute()
    sb.table("audit_log").insert({
        "entity_type": "actuals_obra", "entity_id": None, "action": "upsert_actuals",
        "actor": actor,
        "diff": {"n": len(recs), "fuentes": fuentes, "proyectos": proyectos, "periodos": periodos},
    }).execute()
    resumen["upserted"] = len(recs)
    return resumen
