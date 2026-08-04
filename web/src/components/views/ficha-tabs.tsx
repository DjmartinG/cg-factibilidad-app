"use client";

import { Fragment, useMemo, useState } from "react";
import type { ProjectDetail, Results, Sensitivity, Schedule, Wacc, Vehiculos } from "@/lib/api";
import { cn } from "@/lib/utils";
import { FichaResumen } from "@/components/views/ficha-resumen";
import { CierreView } from "@/components/views/ficha-cierre";
import { ViabilidadView } from "@/components/views/ficha-viabilidad";
import { FlujoView } from "@/components/views/ficha-flujo";
import { CronogramaView } from "@/components/views/ficha-cronograma";
import { WaccView } from "@/components/views/ficha-wacc";
import { SensibilidadView } from "@/components/views/ficha-sensibilidad";
import { VehiculosView } from "@/components/views/ficha-vehiculos";
import { PanelControl, type SimBase } from "@/components/views/panel-control";
import { PanelOpciones } from "@/components/views/panel-opciones";

type Tab = "resumen" | "cierre" | "viabilidad" | "flujo" | "cronograma" | "capital" | "sensibilidad" | "vehiculos" | "control" | "opciones";

const TABS: { key: Tab; label: string }[] = [
  { key: "resumen", label: "Resumen" },
  { key: "cierre", label: "Cierre" },
  { key: "viabilidad", label: "Viabilidad" },
  { key: "flujo", label: "Flujo" },
  { key: "cronograma", label: "Cronograma" },
  { key: "capital", label: "Costo de capital" },
  { key: "sensibilidad", label: "Sensibilidad" },
  { key: "vehiculos", label: "Vehículos" },
  { key: "control", label: "Simulador" },
  { key: "opciones", label: "Etapas" },
];

export function FichaTabs({
  project,
  results,
  sensitivity,
  schedule,
  wacc,
  vehiculos,
  isAdmin = false,
}: {
  project: ProjectDetail;
  results: Results;
  sensitivity: Sensitivity | null;
  schedule: Schedule | null;
  wacc: Wacc | null;
  vehiculos: Vehiculos | null;
  isAdmin?: boolean;
}) {
  const [tab, setTab] = useState<Tab>("resumen");

  // Valores base de los drivers del simulador, en unidades reales — desde lo que la ficha ya cargó.
  const simBase: SimBase = useMemo(() => {
    const und = schedule?.unidades_total ?? null;
    const ventas = results.pyg?.ventas ?? null;
    const directos = results.pyg?.directos ?? null;
    const area = project.urbanistico?.area_construida ?? null;
    const abs = schedule?.absorcion?.ventas ?? null;
    let ritmo: number | null = null;
    if (abs && abs.length) {
      const act = abs.filter((v) => v > 0);
      if (act.length) ritmo = act.reduce((a, b) => a + b, 0) / act.length;
    }
    return {
      precio_und: und && ventas ? ventas / und : null,
      costo_m2: area && directos ? directos / area : null,
      ritmo_und_mes: ritmo,
    };
  }, [results, schedule, project]);

  return (
    <div>
      <div role="tablist" className="mb-6 flex gap-1 overflow-x-auto border-b [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {TABS.map((t, i) => {
          const active = tab === t.key;
          return (
            <Fragment key={t.key}>
              {/* Separador: Resumen es el lienzo; el resto son capas para "profundizar". */}
              {i === 1 ? (
                <span aria-hidden className="mx-1 my-2 w-px shrink-0 self-stretch bg-rule" />
              ) : null}
              <button
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setTab(t.key)}
                className={cn(
                  "relative -mb-px whitespace-nowrap px-3 py-2 text-sm font-medium transition-[color,transform] [transition-duration:var(--dur-1)] [transition-timing-function:var(--ease-out)] active:scale-[0.97]",
                  active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {t.label}
                {active ? (
                  <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-primary" aria-hidden />
                ) : null}
              </button>
            </Fragment>
          );
        })}
      </div>

      {tab === "resumen" ? <FichaResumen project={project} results={results} /> : null}
      {tab === "cierre" ? (
        results.cierre ? (
          <CierreView cierre={results.cierre} />
        ) : (
          <div className="rounded-[var(--radius-data)] border border-dashed bg-card p-10 text-center text-sm text-muted-foreground">
            Cierre financiero no disponible.
          </div>
        )
      ) : null}
      {tab === "viabilidad" ? (
        results.due_diligence ? (
          <ViabilidadView dd={results.due_diligence} urb={results.urbanismo} mkt={results.mercado} slug={project.id} isAdmin={isAdmin} />
        ) : (
          <div className="rounded-[var(--radius-data)] border border-dashed bg-card p-10 text-center text-sm text-muted-foreground">
            Viabilidad cualitativa no disponible.
          </div>
        )
      ) : null}
      {tab === "flujo" ? <FlujoView flujo={results.flujo.apalancado} baseDate={schedule?.base_date ?? null} /> : null}
      {tab === "cronograma" ? (
        schedule ? (
          <CronogramaView schedule={schedule} />
        ) : (
          <div className="rounded-[var(--radius-data)] border border-dashed bg-card p-10 text-center text-sm text-muted-foreground">
            Cronograma no disponible.
          </div>
        )
      ) : null}
      {tab === "capital" ? (
        wacc?.disponible ? (
          <WaccView wacc={wacc} />
        ) : (
          <div className="rounded-[var(--radius-data)] border border-dashed bg-card p-10 text-center text-sm text-muted-foreground">
            Costo de capital no disponible.
          </div>
        )
      ) : null}
      {tab === "sensibilidad" ? (
        sensitivity ? (
          <SensibilidadView sensitivity={sensitivity} slug={project.id} />
        ) : (
          <div className="rounded-[var(--radius-data)] border border-dashed bg-card p-10 text-center text-sm text-muted-foreground">
            Sensibilidad no disponible.
          </div>
        )
      ) : null}
      {tab === "vehiculos" ? (
        vehiculos ? (
          <VehiculosView data={vehiculos} />
        ) : (
          <div className="rounded-[var(--radius-data)] border border-dashed bg-card p-10 text-center text-sm text-muted-foreground">
            Comparador de vehículos no disponible.
          </div>
        )
      ) : null}
      {tab === "control" ? <PanelControl slug={project.id} simBase={simBase} /> : null}
      {tab === "opciones" ? <PanelOpciones slug={project.id} /> : null}
    </div>
  );
}
