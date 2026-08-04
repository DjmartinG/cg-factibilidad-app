# -*- coding: utf-8 -*-
"""App FastAPI de ALEPH (Fase 4a lectura + 4c auth). Expone el motor `aleph_engine` por HTTP.

Contrato §5 de `directives/plan_migracion.md`. La auth (Entra ID) se activa por configuración
(`auth.py`): sin `ENTRA_TENANT_ID`/`API_AUDIENCE` la API queda abierta (dev/CI). La migración de
datos a `projects`/`scenarios` llega en 4b.
"""
from __future__ import annotations

import logging
import os
import secrets

from aleph_engine import __version__ as ENGINE_V
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__, auth, build, fuentes_live, macro_store, repo, write

log = logging.getLogger("aleph_api")

app = FastAPI(
    title="ALEPH API",
    version=__version__,
    description="API de lectura del motor de factibilidad de CG Constructora (sobre aleph_engine).",
)

# CORS: orígenes desde ALEPH_CORS_ORIGINS (coma-separados) o "*" si no se configura (dev).
_origins = [o.strip() for o in os.environ.get("ALEPH_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"],
)

# Aviso de arranque: que no pase desapercibido un despliegue con la auth apagada.
if not auth.auth_enabled():
    if auth.auth_required():
        log.error("ALEPH_AUTH_REQUIRED=true pero la auth NO está configurada: las rutas /v1 devolverán 503.")
    else:
        log.warning("AUTH DESHABILITADA (sin ENTRA_TENANT_ID/API_AUDIENCE): API abierta — solo para dev/CI.")

# Router v1: TODO requiere usuario autenticado (no-op si la auth está deshabilitada en dev/CI).
v1 = APIRouter(prefix="/v1", dependencies=[Depends(auth.current_user)])


def _slug_de_escenario(scenario_id: str) -> str:
    """`{slug}:base|optimista|pesimista` → slug. En Fase 4a solo se sirve la base."""
    return scenario_id.split(":", 1)[0]


def _par_o_404(slug: str):
    par, R = build.cargar_calcular(slug)
    if par is None:
        raise HTTPException(status_code=404, detail=f"Proyecto '{slug}' no encontrado")
    return par, R


@app.get("/version")
def version():
    """Salud + versión (público, sin auth — sirve de health check). No expone el estado de la auth."""
    return {"name": "aleph-api", "version": __version__, "engine_version": ENGINE_V}


@app.get("/health/data")
def health_data():
    """Salud de DATOS (público, sin auth ni cifras sensibles): fuente + nº de proyectos visibles.
    Permite verificar un deploy (`project_count` > 0) AUNQUE la auth de `/v1` esté cerrada — así no hay
    que exponer rutas confidenciales para confirmar que la API lee los datos. `data_source=supabase` con
    `project_count=0` delata una mala config de Supabase (configurada pero la consulta no trae filas)."""
    return {"data_source": repo.fuente(), "project_count": len(repo.listar()),
            "read_model": repo.read_model()}


@v1.get("/portfolio")
def get_portfolio(estado: str | None = Query(default=None)):
    items = build.items_portafolio()
    # Fail-loud en prod: sin la imagen no hay respaldo local, así que 0 proyectos = la fuente de datos
    # no respondió. Con ALEPH_DATA_REQUIRED=true devolvemos 503 en vez de un 200 con portafolio vacío.
    if repo.data_required() and not items:
        log.error("ALEPH_DATA_REQUIRED=true pero 0 proyectos disponibles (fuente=%s) → 503", repo.fuente())
        raise HTTPException(
            status_code=503,
            detail="Sin proyectos disponibles: la fuente de datos no respondió (revisar SUPABASE_URL/KEY).",
        )
    payload = build.portafolio(items)
    if estado:
        payload = {**payload, "items": [d for d in payload["items"] if d.get("estado") == estado]}
    return payload


@v1.get("/portfolio/tesoreria")
def get_portfolio_tesoreria():
    """Tesorería CONSOLIDADA del portafolio: la posición de caja y la financiación (crédito) de TODOS
    los proyectos, alineadas en un calendario común y sumadas mes a mes. Responde la pregunta del CEO:
    ¿cuánta caja necesita la empresa a la vez y cuándo, y cuánto crédito carga? Aditivo (no recalcula)."""
    return build.tesoreria(build.items_portafolio())


@v1.get("/portfolio/capital")
def get_portfolio_capital():
    """Asignación de CAPITAL del portafolio: por proyecto, el equity pico requerido, el crédito máximo,
    el valor creado (EVA) y la EFICIENCIA de capital (valor/equity), rankeado. Responde dónde rinde más
    cada peso de capital escaso. Aditivo (no recalcula)."""
    return build.capital(build.items_portafolio())


@v1.get("/portfolio/tesoreria/estres")
def get_portfolio_tesoreria_estres():
    """ESTRÉS de la tesorería consolidada: cuánto se profundiza el valle de caja combinado y se mueve el
    crédito si las ventas caen/se atrasan y suben los costos en TODA la cartera. Recalcula con el shock
    (reusa la maquinaria del Monte Carlo); el dorado queda intacto."""
    return build.estres(build.items_portafolio())


@v1.get("/portfolio/concentracion")
def get_portfolio_concentracion():
    """CONCENTRACIÓN / diversificación del portafolio por dimensión (proyecto, ubicación, tipo, fase):
    share de cada categoría + HHI (Herfindahl) + número efectivo de categorías. ¿Está la cartera
    demasiado expuesta a una ciudad/segmento/proyecto? Aditivo (no recalcula)."""
    return build.concentracion(build.items_portafolio())


@v1.get("/portfolio/salud")
def get_portfolio_salud():
    """CABINA DEL CEO: la salud del portafolio + ALERTAS accionables (valor, concentración, resiliencia
    ante estrés, capital), priorizadas por nivel. Síntesis de las otras vistas; alertas estructuradas
    (nivel + tipo + datos), el texto lo pone la web. Aditivo (no recalcula cifras de decisión)."""
    return build.salud(build.items_portafolio())


@v1.get("/projects/{slug}")
def get_project(slug: str):
    par, R = _par_o_404(slug)
    return build.project(slug, par, R)


@v1.get("/projects/{slug}/scenarios")
def get_scenarios(slug: str):
    _par_o_404(slug)
    return build.scenarios_list(slug)


@v1.get("/scenarios/{scenario_id}/results")
def get_results(scenario_id: str):
    slug = _slug_de_escenario(scenario_id)
    par, R = _par_o_404(slug)
    return build.results(slug, par, R)


@v1.get("/scenarios/{scenario_id}/sensitivity")
def get_sensitivity(scenario_id: str):
    slug = _slug_de_escenario(scenario_id)
    par, _R = _par_o_404(slug)
    return build.sensitivity(slug, par)


@v1.get("/scenarios/{scenario_id}/schedule")
def get_schedule(scenario_id: str):
    slug = _slug_de_escenario(scenario_id)
    par, R = _par_o_404(slug)
    return build.schedule(slug, par, R)


@v1.get("/scenarios/{scenario_id}/wacc")
def get_wacc(scenario_id: str):
    slug = _slug_de_escenario(scenario_id)
    par, R = _par_o_404(slug)
    return build.wacc(slug, par, R)


@v1.get("/scenarios/{scenario_id}/vehiculos")
def get_vehiculos(scenario_id: str):
    slug = _slug_de_escenario(scenario_id)
    par, _ = build.cargar_calcular(slug)
    return build.vehiculos(slug, par)


@v1.post("/scenarios/{scenario_id}/run")
def post_run(scenario_id: str, req: dict | None = None):
    slug = _slug_de_escenario(scenario_id)
    par, _R = _par_o_404(slug)
    return build.run(par, req or {})


def _calc_o_422(fn, par: dict, req: dict | None):
    """Corre un cálculo de build (Monte Carlo / goal-seek / recalc) traduciendo un input MALFORMADO a un
    422 LEGIBLE en vez de un 500 opaco (el motor puede lanzar ValueError/KeyError ante params raros). Un
    HTTPException (p.ej. el 404 del escenario) se propaga intacto."""
    try:
        return fn(par, req or {})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Parámetros inválidos para el cálculo: {e}") from e


@v1.post("/scenarios/{scenario_id}/montecarlo")
def post_montecarlo(scenario_id: str, req: dict | None = None):
    """Monte Carlo Crystal Ball del escenario: distribuciones, percentiles, certeza y tornado (M5)."""
    slug = _slug_de_escenario(scenario_id)
    par, _R = _par_o_404(slug)
    return _calc_o_422(build.montecarlo_cb, par, req)


@v1.post("/scenarios/{scenario_id}/goal-seek")
def post_goal_seek(scenario_id: str, req: dict | None = None):
    """Goal-seek (M4): resuelve el driver necesario para una meta sobre un indicador (devolvernos)."""
    slug = _slug_de_escenario(scenario_id)
    par, _R = _par_o_404(slug)
    return _calc_o_422(build.goal_seek, par, req)


@v1.post("/scenarios/{scenario_id}/recalc")
def post_recalc(scenario_id: str, req: dict | None = None):
    """Recalculo en vivo (M4b): deltas precio/costo/ritmo -> indicadores (sliders de sensibilidad)."""
    slug = _slug_de_escenario(scenario_id)
    par, _R = _par_o_404(slug)
    return _calc_o_422(build.recalc, par, req)


@v1.post("/scenarios/{scenario_id}/opciones")
def post_opciones(scenario_id: str, req: dict | None = None):
    """Opciones reales por etapa: retrasar/acelerar/quitar cada etapa -> impacto en caja y retorno.
    TIR/VPN direccionales (suelta fiducia); margen y caja exactos (la oficial es la de la ficha)."""
    slug = _slug_de_escenario(scenario_id)
    par, _R = _par_o_404(slug)
    return _calc_o_422(build.opciones, par, req)


# ---------- Escritura (Fase 2): crear/editar borradores → aprobar → baseline ----------
# TODO write exige rol admin (`require_admin`); gerencia es solo-lectura. El `par` se valida con el
# contrato del motor (write._validar) antes de persistir. NO toca el motor (cifras intactas).

class ProjectCreate(BaseModel):
    par: dict
    slug: str | None = None
    nombre: str | None = None
    es_real: bool = False


class ScenarioWrite(BaseModel):
    par: dict


class ProjectPatch(BaseModel):
    es_real: bool


def _actor(user: auth.Principal) -> str | None:
    return user.email or user.oid


@v1.post("/projects")
def post_project(body: ProjectCreate, user: auth.Principal = Depends(auth.require_admin)):
    """Crea un proyecto NUEVO + su escenario v1 en borrador (admin)."""
    return write.crear_proyecto(body.par, slug=body.slug, nombre=body.nombre,
                                es_real=body.es_real, actor=_actor(user))


@v1.post("/projects/{project_id}/scenarios")
def post_scenario(project_id: str, body: ScenarioWrite, user: auth.Principal = Depends(auth.require_admin)):
    """Crea un escenario borrador NUEVO (siguiente versión) sobre un proyecto (admin)."""
    return write.nuevo_draft(project_id, body.par, actor=_actor(user))


@v1.put("/scenarios/{scenario_id}")
def put_scenario(
    scenario_id: str,
    body: ScenarioWrite,
    user: auth.Principal = Depends(auth.require_admin),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    """Reemplaza el snapshot de un borrador (solo si status=draft; approved/baseline → 409). Admin.
    Concurrencia optimista: enviar `If-Match: <updated_at>` → 409 si otro usuario editó entremedio."""
    return write.editar_draft(scenario_id, body.par, actor=_actor(user), if_match=if_match)


@v1.post("/scenarios/{scenario_id}/approve")
def post_approve(scenario_id: str, user: auth.Principal = Depends(auth.require_admin)):
    """Aprueba un borrador: valida → recalcula con el motor → congela snapshot + cache + audita (admin)."""
    return write.aprobar(scenario_id, actor=_actor(user))


@v1.post("/scenarios/{scenario_id}/baseline")
def post_baseline(scenario_id: str, user: auth.Principal = Depends(auth.require_admin)):
    """Fija un escenario aprobado como baseline (la versión oficial; uno por proyecto) (admin)."""
    return write.fijar_baseline(scenario_id, actor=_actor(user))


@v1.delete("/projects/{slug}")
def delete_project(slug: str, user: auth.Principal = Depends(auth.require_admin)):
    """Borra un proyecto COMPLETO (sus escenarios + cache) por slug. Irreversible. Audita. Solo admin."""
    return write.eliminar_proyecto(slug, actor=_actor(user))


@v1.get("/projects/{slug}/source")
def get_project_source(slug: str, user: auth.Principal = Depends(auth.require_admin)):
    """Devuelve el `par` CRUDO del escenario vigente + project_id/versión, para pre-llenar el formulario
    de edición. Solo admin (es el input editable, no las cifras calculadas)."""
    return write.obtener_para_editar(slug)


@v1.patch("/projects/{slug}")
def patch_project(slug: str, body: ProjectPatch, user: auth.Principal = Depends(auth.require_admin)):
    """Marca el proyecto como datos reales / ilustrativos (no toca cifras ni snapshot). Admin."""
    return write.marcar_real(slug, es_real=body.es_real, actor=_actor(user))



# ---------- Supuestos macro (M6): conectores -> tabla con compuerta de revision ----------

class MacroAprobar(BaseModel):
    claves: list[str]


@v1.get("/macro")
def get_macro():
    """Supuestos macro VIGENTES (tasas por banco, EMBI/CRP, TRM/IBR...). Lectura."""
    return {"vigentes": macro_store.listar_vigentes()}


@v1.get("/fuentes/live")
def get_fuentes_live():
    """Valores macro EN VIVO de las fuentes (Damodaran: CRP→rp, ERP madura→pm; Banrep: TRM del dólar),
    cacheado por día. SOLO referencia para contrastar con la calibración del modelo en la pestaña
    Fuentes; NO alimenta el WACC ni mueve cifras. Degrada a `disponible=False` si la fuente no responde."""
    return {**fuentes_live.damodaran_colombia(), "trm": fuentes_live.banrep_trm()}


@v1.get("/fuentes/forward")
def get_fuentes_forward():
    """Escenarios macro (abanico forward): inflación, tasa (IBR) y TRM proyectadas como cono de
    incertidumbre. Senda base anclada a datos vivos de Banrep / meta oficial; bandas = escenarios del
    comité [por validar]. Contexto de portafolio, NO alimenta el modelo. Degrada limpio si no hay red."""
    return fuentes_live.abanico_macro()


@v1.get("/macro/pendientes")
def get_macro_pendientes(user: auth.Principal = Depends(auth.require_admin)):
    """Propuestas pendientes de aprobacion (admin)."""
    return {"pendientes": macro_store.pendientes()}


@v1.post("/macro/refresh")
def post_macro_refresh(user: auth.Principal = Depends(auth.require_admin)):
    """Corre los conectores y PROPONE sus valores (no aplica nada; compuerta de revision). Admin."""
    return macro_store.refrescar()


@v1.post("/macro/aprobar")
def post_macro_aprobar(body: MacroAprobar, user: auth.Principal = Depends(auth.require_admin)):
    """Aprueba propuestas por clave -> pasan a vigentes (admin)."""
    return macro_store.aprobar(body.claves)



@app.post("/macro/cron-refresh", tags=["macro"])
def post_macro_cron_refresh(x_refresh_token: str | None = Header(default=None, alias="X-Refresh-Token")):
    """Refresco MENSUAL para el cron (GitHub Action). Autoriza con TOKEN DE SERVICIO (no Entra) y SOLO
    PROPONE — la compuerta de revision sigue exigiendo aprobacion admin con Entra (/v1/macro/aprobar).
    Deshabilitado (401) si no hay `ALEPH_REFRESH_TOKEN` configurado en el servidor."""
    tok = os.environ.get("ALEPH_REFRESH_TOKEN")
    if not tok or not x_refresh_token or not secrets.compare_digest(x_refresh_token, tok):
        raise HTTPException(status_code=401, detail="token de refresco invalido o no configurado")
    return macro_store.refrescar()


app.include_router(v1)
