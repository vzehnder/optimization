import { useRef, useState, type ReactNode } from "react";
import { MesaInputEditor } from "./MesaInputEditor";
import { MesaManualCreate } from "./MesaManualSeries";
import { MesaManualEditor } from "./MesaManualEditor";
import { MesaPreferences } from "./MesaPreferences";
import { MesaExecution } from "./MesaExecution";
import { MesaHydraulicExecution } from "./MesaHydraulicExecution";
import { MesaHydraulicAssets } from "./MesaHydraulicAssets";
import { MesaHistory } from "./MesaHistory";
import { MesaExport } from "./MesaExport";
import { MesaHelp } from "./MesaHelp";
import { MesaComparisonRange } from "./MesaComparisonRange";
import {
  MesaComparisonSignal,
  type Comparison,
  type ComparisonMode,
} from "./MesaComparison";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { requestJson } from "./api/client";
import type { components } from "./api/schema";
import "./optimizationMesa.css";
import { MesaChart, type MesaChartSeries } from "./MesaChart";
import type { ChartRange } from "./mesaChartAggregation";
import {
  executionChartRange,
  initialExecutionWindow,
} from "./mesaExecutionRange";
import {
  comparisonSides,
  comparisonUnaligned,
  type MesaAxis,
} from "./mesaChartData";

type Mesa = components["schemas"]["MesaResponse"];
type Series = components["schemas"]["MesaSeries"];

function positiveId(value: string | null | undefined) {
  return value &&
    /^[1-9]\d*$/.test(value) &&
    Number.isSafeInteger(Number(value))
    ? Number(value)
    : null;
}

function SeriesPanel({
  component,
  title,
  mode,
  setMode,
  actions,
  seriesKeys,
  seriesAxes,
  chartRange,
  onEdit,
  comparison,
  comparisonMode,
  editingDisabled = false,
}: {
  component: Mesa["components"][number];
  title: string;
  mode: "chart" | "table";
  setMode: (mode: "chart" | "table") => void;
  actions: ReactNode;
  seriesKeys: string[];
  seriesAxes?: Record<string, MesaAxis>;
  chartRange: ChartRange | null;
  onEdit: (series: Series) => void;
  editingDisabled?: boolean;
  comparison?: Comparison;
  comparisonMode?: ComparisonMode;
}) {
  const available = [component.series, ...(component.additional_series ?? [])];
  const family =
    {
      "component:load": "Demanda",
      "component:battery": "BESS",
      "component:renewable": "Renovable",
      "component:hydro": "Hidro simple",
      manual_series: "Serie manual",
      hydraulic_plant: "Central",
      hydraulic_unit: "Unidad",
      hydraulic_reach: "Tramo",
      hydraulic_node:
        component.component_type === "reservoir"
          ? "Embalse"
          : "Nodo hidráulico",
    }[component.entity_type] ?? "Componente";
  const historicalSeries = (key: string) =>
    comparison?.series.find(
      (s) =>
        s.entity_id === component.entity_id &&
        s.entity_type === component.entity_type &&
        s.signal_key === key &&
        (s.linkable_object_id == null ||
          s.linkable_object_id === component.linkable_object_id),
    );
  const chartEntries: MesaChartSeries[] = seriesKeys.flatMap((key) => {
    if (comparisonMode) {
      const historical = historicalSeries(key);
      if (!historical || comparisonUnaligned(historical, comparisonMode))
        return [];
      return comparisonSides(historical, comparisonMode).map(
        ({ label, series }) => ({
          id: `${key}:${label}`,
          signalKey: key,
          series,
          side: label,
        }),
      );
    }
    const series = available.find((s) => s.signal_key === key);
    return series ? [{ id: key, signalKey: key, series }] : [];
  });
  const seriesDetails = seriesKeys.map((key) => {
    if (comparisonMode) {
      const historical = historicalSeries(key);
      return historical ? (
        <MesaComparisonSignal
          key={key}
          comparison={historical}
          mode={comparisonMode}
          presentation={mode}
          detailsOnly
        />
      ) : (
        <p key={key} role="status">
          Serie no disponible en esta comparación · {key}.
        </p>
      );
    }
    const series = available.find((item) => item.signal_key === key);
    if (!series)
      return (
        <p key={key} role="status">
          Serie no disponible · {key}. Reconfigura la vista.
        </p>
      );
    return (
      <div className="mesa-signal" key={key}>
        <div
          className={
            series.role === "support" ? "mesa-manual-summary" : undefined
          }
        >
          {(mode === "table" ||
            seriesKeys.length > 1 ||
            series.status !== "available" ||
            !series.points?.length ||
            series.role === "support") && (
            <p className="mesa-series-label">
              {series.name} · {series.unit} ·{" "}
              {series.role === "output"
                ? "Salida"
                : series.role === "support"
                  ? "Apoyo manual"
                  : "Entrada"}{" "}
              ·{" "}
              {series.editable || series.role === "support"
                ? "Editable"
                : "Solo lectura"}
            </p>
          )}
          {series.role === "support" && (
            <button
              data-mesa-manual-manage={series.signal_id}
              type="button"
              disabled={editingDisabled}
              onClick={() => onEdit(series)}
            >
              Gestionar serie manual
            </button>
          )}
        </div>
        {series.role === "support" && (
          <p className="mesa-manual-status" role="status">
            {series.message}
          </p>
        )}
        {mode === "table" && series.editable && (
          <button
            type="button"
            className="mesa-edit-entry"
            disabled={editingDisabled}
            onClick={() => onEdit(series)}
          >
            Editar entrada
          </button>
        )}
        {series.status !== "available" || !series.points?.length ? (
          (mode === "table" || seriesKeys.length > 1) && (
            <p role="status">{series.message || "Sin datos disponibles."}</p>
          )
        ) : mode === "chart" ? null : (
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
                  <th>
                    {series.name} ({series.unit})
                  </th>
                </tr>
              </thead>
              <tbody>
                {series.points.map((point) => (
                  <tr key={point.start}>
                    <td>{point.start}</td>
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
  });
  return (
    <section className="mesa-panel" aria-label={`${family} · ${title}`}>
      <header className="mesa-panel-heading">
        <div>
          <h2>{title}</h2>
          <p>
            {component.entity_id} ·{" "}
            {comparisonMode
              ? `Entidad ejecutada: ${component.name}`
              : `Objeto ${component.linkable_object_id ?? "no disponible"}`}
            {!comparisonMode &&
              component.entity_type === "manual_series" &&
              ` · Propietario: ${component.parent_entity_id}`}
          </p>
          {!comparisonMode &&
            component.parent_entity_id &&
            component.entity_type !== "manual_series" && (
              <p>Central: {component.parent_entity_id}</p>
            )}
          {!comparisonMode &&
            (component.from_entity_id || component.to_entity_id) && (
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
            ? `Series del gráfico · ${title} · ${component.entity_id}`
            : undefined
        }
      >
        {!!component.parameters?.length &&
          (!comparisonMode ||
            component.parameters.some(
              (p) => p.source === "executed_snapshot",
            )) && (
            <details className="mesa-parameters">
              <summary>
                {comparisonMode
                  ? "Parámetros ejecutados"
                  : "Parámetros actuales"}
              </summary>
              <p>
                {comparisonMode
                  ? `Snapshot #${comparison?.selected_run.scenario_version_id} · valores escalares; no son trayectorias`
                  : "Preparación actual · valores escalares · solo lectura"}
              </p>
              {comparisonMode && component.parent_entity_id && (
                <p>Central: {component.parent_entity_id}</p>
              )}
              {comparisonMode &&
                (component.from_entity_id || component.to_entity_id) && (
                  <p>
                    Conexión: {component.from_entity_id ?? "sin toma"} →{" "}
                    {component.to_entity_id ?? "sin descarga"}
                  </p>
                )}
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
        {mode === "chart" && chartEntries.length > 0 && (
          <MesaChart
            entries={chartEntries}
            axes={seriesAxes}
            range={chartRange}
          />
        )}
        {mode === "chart" && seriesKeys.length > 1 ? (
          <details className="mesa-series-details">
            <summary>Detalle y procedencia de las series</summary>
            {seriesDetails}
          </details>
        ) : (
          <div
            className={
              mode === "chart" ? "mesa-series-details" : "mesa-series-tables"
            }
          >
            {seriesDetails}
          </div>
        )}
      </div>
    </section>
  );
}

function MesaContent({ data, busy }: { data: Mesa; busy: boolean }) {
  const [chartRange, setChartRange] = useState<ChartRange | null>(() =>
    data.context.model_contract === "bess_system_dispatch.v3"
      ? null
      : executionChartRange(initialExecutionWindow(data)),
  );
  const [manualCreate, setManualCreate] = useState(false);
  const [hydraulicEditor, setHydraulicEditor] = useState(false);
  const hydraulicTrigger = useRef<HTMLButtonElement>(null);
  const [hydraulicRevision, setHydraulicRevision] = useState(0);
  const context = data.context;
  const queryClient = useQueryClient();
  const [editor, setEditor] = useState<{
    objectId: number;
    series: Series;
  } | null>(null);
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useSearchParams();
  const runId = positiveId(search.get("run"));
  const referenceId = positiveId(search.get("reference"));
  const rangeStart = search.get("range_start");
  const rangeEnd = search.get("range_end");
  const requestedMode = search.get("comparison");
  const comparisonMode =
    runId && ["before", "compare", "after"].includes(requestedMode ?? "")
      ? (requestedMode as ComparisonMode)
      : undefined;
  const comparison = useQuery({
    queryKey: [
      "optimization-mesa-comparison",
      context.scenario_id,
      context.case_id,
      context.variant_id,
      runId,
      referenceId,
      rangeStart,
      rangeEnd,
    ],
    queryFn: ({ signal }) => {
      const query = new URLSearchParams({
        case_id: String(context.case_id),
        variant_id: String(context.variant_id),
        run_id: String(runId),
      });
      if (referenceId) query.set("reference_run_id", String(referenceId));
      if (rangeStart !== null) query.set("range_start", rangeStart);
      if (rangeEnd !== null) query.set("range_end", rangeEnd);
      return requestJson<Comparison>(
        `/api/scenarios/${context.scenario_id}/mesa/comparison?${query}`,
        { signal },
      );
    },
    enabled: !!comparisonMode,
    retry: false,
    refetchOnWindowFocus: false,
  });
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
        <MesaHistory
          context={context}
          editing={!!editor || hydraulicEditor || manualCreate}
        />
        <p>
          Caso #{context.case_id} · Variante {context.variant_name} ·{" "}
          {context.model_contract ?? "Modelo no disponible"}
        </p>
        {context.model_contract !== "bess_system_dispatch.v3" && (
          <MesaExecution
            data={data}
            onRangeChange={setChartRange}
            editing={!!editor || hydraulicEditor || manualCreate}
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
            onRangeChange={setChartRange}
            caseRevision={hydraulicRevision}
            editing={!!editor || hydraulicEditor || manualCreate}
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
          <button
            className="mesa-hydraulic-trigger"
            ref={hydraulicTrigger}
            type="button"
            disabled={!!editor || hydraulicEditor}
            onClick={() => setHydraulicEditor(true)}
          >
            Editar activos hidráulicos
          </button>
        )}
      </div>
      {manualCreate && (
        <MesaManualCreate
          context={context}
          onClose={() => setManualCreate(false)}
          onSaved={() => {
            setManualCreate(false);
            setNotice(
              "Serie de apoyo publicada. Puedes agregarla a una vista; no participa en la simulación hasta vincularla.",
            );
            void queryClient.invalidateQueries({
              queryKey: ["optimization-mesa"],
            });
          }}
        />
      )}
      {hydraulicEditor && (
        <MesaHydraulicAssets
          scenarioId={context.scenario_id}
          onClose={() => {
            setHydraulicEditor(false);
            requestAnimationFrame(() => hydraulicTrigger.current?.focus());
          }}
          onSaved={() => {
            setHydraulicRevision((revision) => revision + 1);
            setNotice(
              "Activos guardados. Preparación pendiente de revalidación; promueve una versión para incluir los cambios. Ejecuciones históricas conservadas.",
            );
          }}
        />
      )}
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
                next.delete("reference");
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
          <>
            <div
              className="mesa-modes mesa-comparison-modes"
              aria-label="Modo de comparación"
            >
              {(
                [
                  ["", "Preparación actual"],
                  ["before", "Antes"],
                  ["compare", "Comparar"],
                  ["after", "Después"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  disabled={!!value && !runId}
                  aria-pressed={(comparisonMode ?? "") === value}
                  onClick={() => {
                    const next = new URLSearchParams(search);
                    if (value) next.set("comparison", value);
                    else next.delete("comparison");
                    setSearch(next);
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            {comparisonMode && (
              <label>
                Ejecución de referencia
                <select
                  value={search.get("reference") ?? ""}
                  onChange={(event) => {
                    const next = new URLSearchParams(search);
                    if (event.target.value)
                      next.set("reference", event.target.value);
                    else next.delete("reference");
                    setSearch(next);
                  }}
                >
                  <option value="">Sin referencia previa</option>
                  {referenceId &&
                    !comparison.data?.references?.some(
                      (r) => r.id === referenceId,
                    ) && (
                      <option value={referenceId}>Run #{referenceId}</option>
                    )}
                  {comparison.data?.references?.map((r) => (
                    <option key={r.id} value={r.id}>
                      Run #{r.id} · Snapshot #{r.scenario_version_id}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </>
        </div>
      )}
      <MesaPreferences
        data={data}
        creationAction={
          <button
            type="button"
            disabled={!!editor || hydraulicEditor || manualCreate}
            onClick={() => setManualCreate(true)}
          >
            Crear serie manual
          </button>
        }
        renderSelectionActions={(panels) => {
          if (!comparisonMode || !runId) return null;
          const selection = {
            case_id: context.case_id,
            variant_id: context.variant_id,
            run_id: runId,
            reference_run_id: referenceId,
            range_start: rangeStart,
            range_end: rangeEnd,
            mode: comparisonMode,
            panels: panels.map((panel) => ({
              title: panel.title,
              entity_id: panel.component.entity_id,
              entity_type: panel.component.entity_type,
              series_keys: panel.series_keys,
            })),
          };
          return (
            <>
              {comparison.data && (
                <MesaComparisonRange
                  key={`${runId}:${rangeStart}:${rangeEnd}`}
                  comparison={comparison.data}
                  disabled={busy || comparison.isFetching}
                />
              )}
              <MesaExport
                key={JSON.stringify(selection)}
                scenarioId={context.scenario_id}
                selection={selection}
                disabled={
                  busy ||
                  comparison.isFetching ||
                  comparison.isError ||
                  !comparison.data
                }
              />
            </>
          );
        }}
        renderPanel={(panel, onMode, actions) => {
          if (busy || (comparisonMode && comparison.isFetching))
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
          if (comparisonMode && comparison.isError)
            return (
              <section className="mesa-panel" aria-label={panel.title}>
                <h2>{panel.title}</h2>
                <p role="alert">
                  No se pudo comparar. {comparison.error.message}
                </p>
                <button type="button" onClick={() => void comparison.refetch()}>
                  Reintentar comparación
                </button>
              </section>
            );
          const historical = !!comparisonMode && !!comparison.data;
          if (historical && panel.component.entity_type === "manual_series") {
            return (
              <section
                className="mesa-panel"
                aria-label={`Serie manual · ${panel.title}`}
              >
                <header className="mesa-panel-heading">
                  <h2>{panel.title}</h2>
                  {actions}
                </header>
                <p role="status">
                  Esta vista de apoyo no tiene resultados ni diferencias.
                  Consulta la entrada del objeto ejecutado para ver la revisión
                  utilizada.
                </p>
                <p>
                  Los datos manuales actuales se consultan en Preparación
                  actual.
                </p>
              </section>
            );
          }
          const component = (
            historical ? (comparison.data!.components ?? []) : data.components
          ).find(
            (c) =>
              c.entity_id === panel.component.entity_id &&
              c.entity_type === panel.component.entity_type &&
              (historical ||
                c.linkable_object_id === panel.component.linkable_object_id),
          );
          return component ? (
            <SeriesPanel
              component={component}
              title={panel.title}
              mode={panel.mode}
              setMode={onMode}
              actions={actions}
              seriesKeys={panel.series_keys}
              seriesAxes={panel.series_axes}
              chartRange={chartRange}
              comparison={comparison.data}
              comparisonMode={comparisonMode}
              editingDisabled={hydraulicEditor}
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
      {editor?.series.role === "support" && (
        <MesaManualEditor
          context={context}
          series={editor.series}
          onClose={() => setEditor(null)}
          onChanged={() => {
            setNotice(
              "Serie manual guardada. Revisa su vínculo y valida la preparación antes de ejecutar. Ejecuciones históricas conservadas.",
            );
            void queryClient.invalidateQueries({
              queryKey: ["optimization-mesa"],
            });
          }}
        />
      )}
      {editor && editor.series.role !== "support" && (
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
        {comparisonMode
          ? "Comparación histórica de solo lectura. Entradas del snapshot ejecutado; la preparación actual se valida por separado. Δ no disponible se muestra como —."
          : "Entradas y parámetros de la preparación actual. Las salidas pertenecen a la ejecución seleccionada."}
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
        <MesaHelp />
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
