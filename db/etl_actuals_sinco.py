# -*- coding: utf-8 -*-
"""ETL: SINCO `ControlProyecto` → `actuals_obra` (FASE 1, lado de ESCRITURA).

Lee la view de SINCO (o un FIXTURE de muestra), agrega PV/EV/AC/BAC por proyecto·nivel·periodo
(`sinco.to_actuals`) y los UPSERTEA en Supabase (`actuals.upsert_actuals`). Es el "job programado" de
FASE 1 (lo correrá Azure Functions / GitHub Actions cuando haya credenciales). DRY-RUN por defecto.

ESTADO (hasta el Paso 2): el modo EN VIVO falla en voz alta — faltan (a) el mapeo real de columnas
(`MAPEO_CONTROL_PROYECTO` está en `# TODO`) y (b) las credenciales/firewall de SINCO. Usa `--fixture`
para ejercitar el PIPELINE COMPLETO con datos de muestra (sin SINCO): así el camino to_actuals→upsert
queda probado y, cuando lleguen el mapeo y el usuario read-only, solo se quita `--fixture`.

SEGURO: DRY-RUN por defecto (NO escribe). `--apply` escribe en Supabase (requiere SUPABASE_URL/KEY
service_role). Re-ejecutar es idempotente (upsert por clave natural source·proyecto·nivel·periodo).

Uso:
  python db/etl_actuals_sinco.py --fixture db/samples/sinco_control_proyecto_sample.json
  python db/etl_actuals_sinco.py --fixture db/samples/sinco_control_proyecto_sample.json --apply
  python db/etl_actuals_sinco.py --apply            # EN VIVO (Paso 2: mapeo real + credenciales SINCO)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# El motor no se usa aquí, pero `aleph_api` sí (actuals + conector). Añadimos `api/` al path por si el
# paquete no está instalado pero sí en el repo (igual que refresh_scenarios hace con engine/).
for sub in ("api", "engine"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from aleph_api import actuals
    from aleph_api.conectores import sinco
except ImportError as e:
    sys.exit(f"No se pudo importar aleph_api ({e}). Corre desde la raíz del repo (con api/ en el árbol).")


def _config_supabase() -> tuple[str, str]:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    if url and key:
        return url, key
    sec = ROOT / ".streamlit" / "secrets.toml"
    if sec.is_file():
        data = tomllib.loads(sec.read_text(encoding="utf-8"))
        if data.get("SUPABASE_URL") and data.get("SUPABASE_KEY"):
            return data["SUPABASE_URL"], data["SUPABASE_KEY"]
    sys.exit("Faltan SUPABASE_URL/SUPABASE_KEY (entorno o .streamlit/secrets.toml).")


def _leer_fuente(args) -> tuple[dict, list]:
    """Devuelve (mapeo, filas). Desde un fixture (muestra) o desde SINCO en vivo."""
    if args.fixture:
        try:
            d = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        except FileNotFoundError:
            sys.exit(f"Fixture no encontrado: {args.fixture}")
        except json.JSONDecodeError as e:
            sys.exit(f"Fixture malformado ({args.fixture}): {e}")
        if not isinstance(d, dict):
            sys.exit(f"Fixture invalido ({args.fixture}): se esperaba un objeto JSON con 'mapeo' y 'filas'.")
        filas = d.get("filas") or []
        mapeo = d.get("mapeo") or sinco.MAPEO_CONTROL_PROYECTO
        print(f"== Fuente: FIXTURE {args.fixture} ({len(filas)} filas) ==")
        return mapeo, filas
    # EN VIVO: usa el mapeo real del conector (hoy en `# TODO` → to_actuals fallará en voz alta) y lee
    # ControlProyecto (conectar() exige credenciales). Ambos se completan en el Paso 2.
    print("== Fuente: SINCO en vivo (ADP_DTM_VFACT.ControlProyecto) ==")
    filas = sinco.leer_control_proyecto(limit=args.limit)
    return sinco.MAPEO_CONTROL_PROYECTO, filas


def main() -> None:
    try:                                  # consola Windows cp1252: evita UnicodeEncodeError en la salida
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                     # noqa: BLE001 - si no se puede, seguimos (la salida ya es ASCII)
        pass
    pa = argparse.ArgumentParser(description="ETL SINCO ControlProyecto -> actuals_obra (FASE 1).")
    pa.add_argument("--apply", action="store_true", help="Escribe en Supabase (sin esto: dry-run).")
    pa.add_argument("--fixture", metavar="PATH", help="JSON de muestra {mapeo, filas} en vez de SINCO en vivo.")
    pa.add_argument("--limit", type=int, default=None, help="TOP n filas al leer SINCO en vivo (opcional).")
    pa.add_argument("--actor", default="etl_sinco", help="Actor para la auditoría (default: etl_sinco).")
    args = pa.parse_args()

    mapeo, filas = _leer_fuente(args)

    # Transformación (roll-up) — falla en voz alta si el mapeo está sin definir (modo en vivo, Paso 2).
    registros = sinco.to_actuals(filas, mapeo)
    if not registros:
        print("No se produjo ningún registro de actuals (¿filas vacías o sin clave mínima?).")
        return

    proyectos = sorted({r.proyecto for r in registros})
    niveles = sorted({r.nivel for r in registros})
    periodos = sorted({r.periodo.isoformat() for r in registros})
    print(f"   registros agregados: {len(registros)}")
    print(f"   proyectos: {proyectos}")
    print(f"   niveles  : {niveles}")
    print(f"   periodos : {periodos}")
    tot = lambda f: sum(getattr(r, f) for r in registros)  # noqa: E731
    print(f"   totales  : PV={tot('pv'):.1f}  EV={tot('ev'):.1f}  AC={tot('ac'):.1f}")

    modo = "APPLY (escribiendo)" if args.apply else "DRY-RUN (no escribe)"
    print(f"== Persistencia - modo {modo} (clave de upsert: {actuals.CLAVE_UPSERT}) ==")

    if not args.apply:
        res = actuals.upsert_actuals(None, registros, actor=args.actor, dry_run=True)
        print(f"   DRY-RUN: upsertearía {res['recibidos']} registros en actuals_obra. Nada escrito.")
        print("   Vuelve a correr con --apply para aplicar.")
        return

    url, key = _config_supabase()
    try:
        from supabase import create_client
    except ImportError:
        sys.exit("Falta supabase. Instálalo:  pip install supabase")
    sb = create_client(url, key)
    res = actuals.upsert_actuals(sb, registros, actor=args.actor)
    print(f"   OK: upserted {res['upserted']} registros en actuals_obra (fuentes={res['fuentes']}).")
    print("   *** LISTO. El Monitor/EVM (FASE 2) consumirá estos actuals cuando se cablee evm.py. ***")


if __name__ == "__main__":
    main()
