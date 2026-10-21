import { useState, type ReactNode } from "react";
import { MesaInputEditor } from "./MesaInputEditor";
import { MesaPreferences } from "./MesaPreferences";
import { MesaExecution } from "./MesaExecution";
import { MesaHydraulicExecution } from "./MesaHydraulicExecution";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { requestJson } from "./api/client";
import type { components } from "./api/schema";
import "./optimizationMesa.css";

type Mesa = components["schemas"]["MesaResponse"];
type Series = components["schemas"]["MesaSeries"];

function positiveId(value: string | null | undefined) {
  return value &&
    /^[1-9]\d*$/.test(value) &&
    Number.isSafeInteger(Number(value))
    ? Number(value)
    : null;
}

function SeriesChart({ series }: { series: Series }) {
  const points = series.points ?? [];
  const first = Date.parse(points[0].start);
  const last = Date.parse(points[points.length - 1].end);
  const max = Math.max(1, ...points.map((point) => point.value)) * 1.1;
  const x = (instant: string) =>
    60 + ((Date.parse(instant) - first) / (last - first)) * 660;
  const y = (value: number) => 130 - (value / max) * 95;
  return (
    <svg
      className="mesa-chart"
      viewBox="0 0 760 180"
      role="img"
      aria-label={`${series.name} · ${series.unit}`}
    >
      <desc>
        {points
          .map(
            (point) =>
              `${point.start} → ${point.end}: ${point.value} ${series.unit}`,
          )
          .join("; ")}
      </desc>
      {[0, 0.5, 1].map((fraction) => (
        <g key={fraction}>
          <line
            x1="60"
            x2="720"
            y1={y(max * fraction)}
            y2={y(max * fraction)}
            stroke="#dce6eb"
          />
          <text x="48" y={y(max * fraction) + 4} textAnchor="end">
            {(max * fraction).toFixed(1)}
          </text>
        </g>
      ))}
      <text x="60" y="24">
        {series.unit}
      </text>
      <polyline
        points={points
          .map((point) => `${x(point.start)},${y(point.value)}`)
          .join(" ")}
        fill="none"
        stroke="#087f80"
        strokeWidth="3"
      />
      {points.map((point) => (
        <circle
          key={point.start}
          cx={x(point.start)}
          cy={y(point.value)}
          r="4"
          fill="#087f80"
        >
          <title>
            {point.start} → {point.end}: {point.value} {series.unit}
          </title>
        </circle>
      ))}
      <text x="60" y="165">
        {points[0].start.slice(0, 16).replace("T", " ")}
      </text>
      <text x="720" y="165" textAnchor="end">
        {points[points.length - 1].end.slice(0, 16).replace("T", " ")}
      </text>
    </svg>
  );
}

function SeriesPanel({
  component,
  title,
  mode,
  setMode,
  actions,
  seriesKeys,
  onEdit,
}: {
  component: Mesa["components"][number];
  title: string;
  mode: "chart" | "table";
  setMode: (mode: "chart" | "table") => void;
  actions: ReactNode;
  seriesKeys: string[];
  onEdit: (series: Series) => void;
}) {
  const available = [component.series, ...(component.additional_series ?? [])];
  const family =
    {
      "component:load": "Demanda",
      "component:battery": "BESS",
      "component:renewable": "Renovable",
      "component:hydro": "Hidro simple",
      hydraulic_plant: "Central",
      hydraulic_unit: "Unidad",
      hydraulic_reach: "Tramo",
      hydraulic_node:
        component.component_type === "reservoir"
          ? "Embalse"
          : "Nodo hidráulico",
    }[component.entity_type] ?? "Componente";
  return (
    <section className="mesa-panel" aria-label={`${family} · ${title}`}>
      <header className="mesa-panel-heading">
        <div>
          <h2>{title}</h2>
          <p>
            {component.entity_id} · Objeto{" "}
            {component.linkable_object_id ?? "no disponible"}
          </p>
          {component.parent_entity_id && (
            <p>Central: {component.parent_entity_id}</p>
          )}
          {(component.from_entity_id || component.to_entity_id) && (
            <p>
              Conexión: {component.from_entity_id ?? "sin toma"} →{" "}
              {component.to_entity_id ?? "sin descarga"}
            </p>
          )}
        </div>
        <div className="mesa-modes" aria-label="Presentación de series">
          <button
            type="button"
            aria-pressed={mode === "chart"}
            onClick={() => setMode("chart")}
          >
            Gráfico
          </button>
          <button
            type="button"
            aria-pressed={mode === "table"}
            onClick={() => setMode("table")}
          >
            Tabla
          </button>
          {actions}
        </div>
      </header>
      <div
        className="mesa-series-content"
        tabIndex={seriesKeys.length > 1 ? 0 : undefined}
        role={seriesKeys.length > 1 ? "region" : undefined}
        aria-label={
          seriesKeys.length > 1
            ? "Series con escalas independientes"
            : undefined
        }
      >
        {!!component.parameters?.length && (
          <details className="mesa-parameters">
            <summary>Parámetros actuales</summary>
            <p>Preparación actual · valores escalares · solo lectura</p>
            <table aria-label={`Parámetros de ${title}`}>
              <thead>
                <tr>
                  <th>Parámetro</th>
                  <th>Valor</th>
                  <th>Unidad</th>
                </tr>
              </thead>
              <tbody>
                {component.parameters.map((parameter) => (
                  <tr key={parameter.key}>
                    <th>{parameter.name}</th>
                    <td>
                      {typeof parameter.value === "boolean"
                        ? parameter.value
                          ? "Sí"
                          : "No"
                        : parameter.value}
                    </td>
                    <td>{parameter.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        )}
        {seriesKeys.map((key) => {
          const series = available.find((item) => item.signal_key === key);
          if (!series)
            return (
              <p key={key} role="status">
                Serie no disponible · {key}. Reconfigura la vista.
              </p>
            );
          return (
            <div className="mesa-signal" key={key}>
              <p className="mesa-series-label">
                {series.name} · {series.unit} ·{" "}
                {series.role === "output" ? "Salida" : "Entrada"} ·{" "}
                {series.editable ? "Editable" : "Solo lectura"}
              </p>
              {mode === "table" && series.editable && (
                <button
                  type="button"
                  className="mesa-edit-entry"
                  onClick={() => onEdit(series)}
                >
                  Editar entrada
                </button>
              )}
              {series.status !== "available" || !series.points?.length ? (
                <p role="status">
                  {series.message || "Sin datos disponibles."}
                </p>
              ) : mode === "chart" ? (
                <SeriesChart series={series} />
              ) : (
                <div
                  className="mesa-table-scroll"
                  tabIndex={0}
                  role="region"
                  aria-label={`Intervalos de ${series.name}`}
                >
                  <table aria-label={`${series.name} · ${series.unit}`}>
                    <thead>
                      <tr>
                        <th>Inicio</th>
                        <th>Fin (exclusivo)</th>
                        <th>
                          {series.name} ({series.unit})
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {series.points.map((point) => (
                        <tr key={point.start}>
                          <td>{point.start}</td>
                          <td>{point.end}</td>
                          <td>{point.value}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <footer className="mesa-panel-footer">
                <span>
                  Zona:{" "}
                  {series.timezone ??
                    (series.run_id
                      ? "no registrada; horas del snapshot"
                      : "sin fuente")}
                </span>
                <span>
                  {series.run_id
                    ? `Run #${series.run_id} · Snapshot #${series.scenario_version_id}`
                    : series.revision_number
                      ? `Revisión ${series.revision_number} · Fuente #${series.time_series_set_id}`
                      : "Preparación actual"}
                </span>
              </footer>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function MesaContent({ data, busy }: { data: Mesa; busy: boolean }) {
  const context = data.context;
  const queryClient = useQueryClient();
  const [editor, setEditor] = useState<{
    objectId: number;
    series: Series;
  } | null>(null);
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useSearchParams();
  return (
    <>
      <nav className="mesa-context" aria-label="Contexto de la mesa">
        <Link to={`/projects/${context.project_id}`}>
          {context.project_name}
        </Link>
        <span aria-hidden="true">/</span>
        <Link
          to={`/scenarios/${context.scenario_id}?section=data&variant=${context.variant_id}`}
        >
          {context.scenario_name}
        </Link>
      </nav>
      <div className="mesa-case-execution">
        <p>
          Caso #{context.case_id} · Variante {context.variant_name} ·{" "}
          {context.model_contract ?? "Modelo no disponible"}
        </p>
        {context.model_contract !== "bess_system_dispatch.v3" && (
          <MesaExecution
            data={data}
            editing={!!editor}
            onResults={(runId) => {
              void queryClient.invalidateQueries({
                queryKey: ["optimization-mesa"],
              });
              const next = new URLSearchParams(search);
              next.set("run", String(runId));
              setSearch(next);
            }}
          />
        )}
        {context.model_contract === "bess_system_dispatch.v3" && (
          <MesaHydraulicExecution
            data={data}
            editing={!!editor}
            onResults={(runId) => {
              void queryClient.invalidateQueries({
                queryKey: ["optimization-mesa"],
              });
              const next = new URLSearchParams(search);
              next.set("run", String(runId));
              setSearch(next);
            }}
          />
        )}
      </div>
      {!!data.runs?.length && (
        <div className="mesa-toolbar">
          <label>
            Resultados de ejecución
            <select
              value={search.get("run") ?? ""}
              onChange={(event) => {
                const next = new URLSearchParams(search);
                if (event.target.value) next.set("run", event.target.value);
                else next.delete("run");
                setSearch(next);
              }}
            >
              <option value="">Sin ejecución seleccionada</option>
              {data.runs.map((run) => (
                <option key={run.id} value={run.id}>
                  Run #{run.id} · {run.model_contract} · Snapshot #
                  {run.scenario_version_id}
                </option>
              ))}
            </select>
          </label>
          <p>Salidas históricas de solo lectura</p>
        </div>
      )}
      <MesaPreferences
        data={data}
        renderPanel={(panel, onMode, actions) => {
          if (busy)
            return (
              <section
                className="mesa-panel"
                aria-label={panel.title}
                aria-busy="true"
              >
                <h2>{panel.title}</h2>
                <p role="status">Cargando series del contexto seleccionado…</p>
              </section>
            );
          const component = data.components.find(
            (c) =>
              c.entity_id === panel.component.entity_id &&
              c.entity_type === panel.component.entity_type &&
              c.linkable_object_id === panel.component.linkable_object_id,
          );
          return component ? (
            <SeriesPanel
              component={component}
              title={panel.title}
              mode={panel.mode}
              setMode={onMode}
              actions={actions}
              seriesKeys={panel.series_keys}
              onEdit={(series) => {
                if (component.linkable_object_id)
                  setEditor({ objectId: component.linkable_object_id, series });
              }}
            />
          ) : (
            <section className="mesa-panel" aria-label={panel.title}>
              <header className="mesa-panel-heading">
                <h2>{panel.title}</h2>
                {actions}
              </header>
              <p role="status">
                No disponible · {panel.component.entity_id} · Objeto{" "}
                {panel.component.linkable_object_id ?? "sin registro"}
              </p>
            </section>
          );
        }}
      />
      {notice && <p role="status">{notice}</p>}
      {editor && (
        <MesaInputEditor
          context={context}
          {...editor}
          onClose={() => setEditor(null)}
          onSaved={() => {
            setEditor(null);
            setNotice(
              "Entrada guardada. Preparación pendiente de revalidación; ejecuciones históricas conservadas.",
            );
            void queryClient.invalidateQueries({
              queryKey: ["optimization-mesa"],
            });
          }}
        />
      )}
      <p className="mesa-note">
        Entradas y parámetros de la preparación actual. Las salidas pertenecen a
        la ejecución seleccionada.
      </p>
    </>
  );
}

export function OptimizationMesaView() {
  const params = useParams();
  const [search] = useSearchParams();
  const scenarioId = positiveId(params.scenarioId);
  const caseId = positiveId(search.get("case"));
  const variantId = positiveId(search.get("variant"));
  const runId = positiveId(search.get("run"));
  const invalidRun = search.has("run") && !runId;
  const rangeStart = search.get("range_start");
  const rangeEnd = search.get("range_end");
  const query = useQuery({
    queryKey: [
      "optimization-mesa",
      scenarioId,
      caseId,
      variantId,
      runId,
      rangeStart,
      rangeEnd,
    ],
    queryFn: ({ signal }) => {
      const queryParams = new URLSearchParams({
        case_id: String(caseId),
        variant_id: String(variantId),
      });
      if (rangeStart !== null) queryParams.set("range_start", rangeStart);
      if (rangeEnd !== null) queryParams.set("range_end", rangeEnd);
      if (runId !== null) queryParams.set("run_id", String(runId));
      return requestJson<Mesa>(
        `/api/scenarios/${scenarioId}/mesa?${queryParams}`,
        { signal },
      );
    },
    enabled: !!(scenarioId && caseId && variantId && !invalidRun),
    staleTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === scenarioId &&
      previousQuery?.queryKey[2] === caseId &&
      previousQuery?.queryKey[3] === variantId
        ? previous
        : undefined,
  });
  return (
    <section className="workspace-view mesa-view">
      <header className="workspace-heading">
        <h1>Mesa de optimización</h1>
        <p>Consulta componentes, entradas y resultados con su procedencia.</p>
      </header>
      {rangeStart && rangeEnd && (
        <p>
          Período solicitado: {rangeStart} → {rangeEnd} (fin exclusivo)
        </p>
      )}
      {!scenarioId || !caseId || !variantId || invalidRun ? (
        <p role="alert">
          Selecciona un caso y una variante válidos desde el escenario.
        </p>
      ) : query.isError ? (
        <div role="alert">
          <p>No se pudo consultar la mesa. {query.error.message}</p>
          <button type="button" onClick={() => void query.refetch()}>
            Reintentar
          </button>
        </div>
      ) : query.isPending ? (
        <p role="status">Cargando componentes del caso…</p>
      ) : (
        <MesaContent
          key={`${scenarioId}:${caseId}:${variantId}`}
          data={query.data}
          busy={query.isFetching}
        />
      )}
    </section>
  );
}
