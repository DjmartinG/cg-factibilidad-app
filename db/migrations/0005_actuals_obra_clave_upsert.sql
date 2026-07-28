-- 0005_actuals_obra_clave_upsert.sql
-- Ajusta la clave única de `actuals_obra` (de 0004) para que el ETL pueda hacer UPSERT idempotente.
-- ADITIVA / correctiva: no crea tablas nuevas ni mueve datos; solo cambia un índice. Idempotente.
--
-- POR QUÉ:
--   1. 0004 creó un índice de EXPRESIÓN (… coalesce(corte, periodo)). `INSERT … ON CONFLICT` (el upsert
--      de PostgREST/Supabase) NO puede apuntar a un índice de expresión por lista de columnas → el ETL
--      no podría upsertear contra él.
--   2. El Monitor lee el ESTADO ACTUAL por proyecto·nivel·periodo: cada nueva extracción de SINCO debe
--      SOBREESCRIBIR ese estado, no acumular una fila por corte. Por eso la clave NO incluye `corte`
--      (que pasa a ser un atributo de recencia: cuándo se extrajo, junto a fecha_carga/updated_at).
--
-- Si necesitas histórico por corte en el futuro, archiva el crudo aparte (p.ej. ADLS, ver el plan),
-- no en esta tabla de estado.

drop index if exists public.actuals_obra_natural_ux;

-- Saneo DEFENSIVO (no-op en tabla vacía): el index VIEJO de 0004 incluía coalesce(corte,periodo), así
-- que PERMITÍA varias filas por (source,proyecto,nivel,periodo) con distinto `corte`. Si en algún
-- entorno 0004 ya hubiera ingerido filas multi-corte por clave, el `create unique index` de abajo
-- fallaría ("Key is duplicated"). Esto colapsa a la fila del corte MÁS RECIENTE por clave (desempata
-- por id) para que el índice siempre pueda crearse, sin depender del orden de despliegue.
delete from public.actuals_obra a
using public.actuals_obra b
where a.source = b.source and a.proyecto = b.proyecto
  and a.nivel = b.nivel and a.periodo = b.periodo
  and ( coalesce(a.corte, a.periodo) < coalesce(b.corte, b.periodo)
        or (coalesce(a.corte, a.periodo) = coalesce(b.corte, b.periodo) and a.id < b.id) );

create unique index if not exists actuals_obra_clave_ux
    on public.actuals_obra (source, proyecto, nivel, periodo);

comment on index public.actuals_obra_clave_ux is
    'Clave de upsert del ETL (estado actual por proyecto·nivel·periodo). Apta para ON CONFLICT.';
