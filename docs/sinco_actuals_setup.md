# Conector SINCO — actuals de obra (Fase 1 · Paso 1)

Cimiento de la ingesta de **actuals** (valor ganado) desde el DATAMART de SINCO hacia ALEPH. Es
**aditivo**: no toca `calcular()`, `evm.py` ni el dorado. En el Paso 1 todo se prueba con **fixture**;
la conexión en vivo se enchufa en el Paso 2.

## Piezas

| Pieza | Ubicación |
|---|---|
| Esquema de actuals (migración aditiva) | `db/migrations/0004_actuals_obra.sql` |
| Clave de upsert (columnas planas, ON CONFLICT) | `db/migrations/0005_actuals_obra_clave_upsert.sql` |
| Conector (config-driven, solo lectura) | `api/aleph_api/conectores/sinco.py` |
| Persistencia (upsert idempotente + audit) | `api/aleph_api/actuals.py` |
| Job ETL (SINCO → actuals_obra) | `db/etl_actuals_sinco.py` |
| Muestra para el ETL (sin SINCO) | `db/samples/sinco_control_proyecto_sample.json` |
| Tests con fixture (sin red) | `api/tests/test_conector_sinco.py`, `api/tests/test_actuals.py` |
| Variables de entorno | `.env.example` |

> **Migraciones:** aplica `0004` **y** `0005` (en orden) en el SQL Editor. `0005` cambia el índice único
> de `actuals_obra` a columnas planas `(source, proyecto, nivel, periodo)` para que el ETL pueda hacer
> `UPSERT` idempotente (el índice de expresión de `0004` no es targeteable por `ON CONFLICT`).

> **Nota de gobernanza (decidir en FASE 2):** `0001` ya define `actuals_evm` (grano proyecto·fecha_corte,
> con spi/cpi, `fuente` ∈ manual|excel|erp|crm) y `actuals_recaudo`. `actuals_obra` es el **landing** de
> grano fino (proyecto·nivel/WBS·mes, `source='sinco'`, crudo PV/EV/AC/BAC). La reconciliación (¿el EVM
> rueda `actuals_obra` → `actuals_evm`? ¿se amplía el check de `fuente` para 'sinco'?) se decide al cablear
> `evm.py` al Monitor, con el dato real a la vista.

## Configuración (variables de entorno — nunca en código)

| Variable | Ejemplo | Notas |
|---|---|---|
| `SINCO_SERVER` | `datamart.sincoerp.com,4263` | host,puerto (estilo SQL Server) |
| `SINCO_DB` | `SincoCGDW` | base del DATAMART |
| `SINCO_USER` | — | usuario **read-only** que provee SINCOSOFT |
| `SINCO_PASSWORD` | — | secreto: Key Vault / GitHub Secrets, jamás en git |

Driver SQL Server: **`pymssql`** (dependencia opcional). Instalar solo donde se conecte en vivo:

```
pip install 'aleph-api[sinco]'      # o:  pip install pymssql
```

El `import pymssql` es **perezoso** (solo al conectar), así que el módulo importa y los tests corren
**sin** el driver instalado. CI no lo instala.

## Job ETL — `db/etl_actuals_sinco.py` (SINCO → `actuals_obra`)

Agrega PV/EV/AC/BAC por proyecto·nivel·periodo (`sinco.to_actuals`) y los **upsertea** en Supabase
(`actuals.upsert_actuals`, clave natural `source·proyecto·nivel·periodo` → re-correr **sobreescribe** el
estado actual, idempotente). **DRY-RUN por defecto** (no escribe). Es el "job programado" de FASE 1
(luego correrá en Azure Functions / GitHub Actions cron).

**Ahora (sin SINCO) — ejercita el pipeline completo con la muestra:**
```bash
python db/etl_actuals_sinco.py --fixture db/samples/sinco_control_proyecto_sample.json          # dry-run
python db/etl_actuals_sinco.py --fixture db/samples/sinco_control_proyecto_sample.json --apply   # escribe (requiere Supabase)
```
`--apply` necesita `SUPABASE_URL` + `SUPABASE_KEY` (service_role) en el entorno o en `.streamlit/secrets.toml`,
y las migraciones `0004`+`0005` aplicadas.

**En vivo (Paso 2):** sin `--fixture` lee SINCO directo. Hoy **falla en voz alta** porque
`MAPEO_CONTROL_PROYECTO` está en `# TODO` y faltan credenciales; cuando ambos estén, basta quitar
`--fixture`:
```bash
python db/etl_actuals_sinco.py --apply      # requiere mapeo real + credenciales SINCO (Paso 2)
```

## Smoke test manual (cuando ya haya credenciales) — NO en CI

Lo corre **Martín en local** (no el CI), una vez SINCOSOFT entregue el usuario read-only y el firewall
permita el acceso. Verifica conexión/firewall **e imprime los nombres de columna reales** de la view
(insumo para llenar el mapeo en el Paso 2):

```bash
# 1) define las variables (o usa un .env)
export SINCO_SERVER='datamart.sincoerp.com,4263'
export SINCO_DB='SincoCGDW'
export SINCO_USER='<usuario_readonly>'
export SINCO_PASSWORD='<secreto>'

# 2) SELECT TOP 5 contra ADP_DTM_VFACT.ControlProyecto
pip install pymssql
python -m aleph_api.conectores.sinco
```

Salida esperada: `OK — N filas leídas`, la lista de **columnas** y las 5 filas. Si falla, imprime el
tipo de error (firewall, login, driver) sin tumbar nada.

> En PowerShell (Windows): `$env:SINCO_SERVER='datamart.sincoerp.com,4263'` (y análogos) antes de correr.

## Paso 2 (pendiente — fuera de este alcance)

1. **Llenar `MAPEO_CONTROL_PROYECTO`** en `sinco.py` con las columnas reales que imprimió el smoke
   (hoy está en `# TODO`; `to_actuals(...)` con el mapeo por defecto falla en voz alta a propósito).
2. **Conexión en vivo:** quitar `--fixture` del job (`db/etl_actuals_sinco.py` ya hace el upsert) y
   **programarlo** (Azure Functions Timer / GitHub Actions cron) — depende del firewall/usuario read-only.
3. **Cablear los actuals** a `engine/aleph_engine/evm.py` y al Monitor en `/web` (+ resolver la nota de
   gobernanza `actuals_obra` vs `actuals_evm`).
