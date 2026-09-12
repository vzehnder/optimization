import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import {
  ApiError,
  type DashboardResults,
  getRunResults,
  listRunArtifacts,
  type ResultCell,
  type ResultChart,
  type ResultChartSeries,
  type ResultTable,
  type RunArtifact,
  type ScenarioRun,
} from "./api/client";
import { loadPlotly, type PlotlyTrace } from "./plotly";
import {
  formatResultValue,
  resultLabel,
  resultUnit,
} from "./resultPresentation";

const runResultsQueryKey = (runId: number) => ["run-results", runId] as const;
const runArtifactsQueryKey = (runId: number) =>
  ["run-artifacts", runId] as const;
const terminalRunStatuses = new Set(["succeeded", "failed"]);
const tableRowLimit = 25;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "")
    return "No disponible";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function unitForColumn(column: string): string {
  const units: Array<[string, string]> = [
    ["_usd_per_mwh", "USD/MWh"],
    ["_mwh", "MWh"],
    ["_mw", "MW"],
    ["_m3s", "m3/s"],
    ["_hm3", "hm3"],
    ["_masl", "masl"],
    ["_usd", "USD"],
    ["_hours", "hours"],
  ];
  return units.find(([suffix]) => column.endsWith(suffix))?.[1] || "";
}

function numericValues(series: ResultChartSeries): number[] {
  return series.values.filter(
    (value): value is number => typeof value === "number",
  );
}

function seriesRange(series: ResultChartSeries): string {
  const values = numericValues(series);
  if (!values.length) return "Sin valores numericos";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const latest = [...series.values]
    .reverse()
    .find((value): value is number => typeof value === "number");
  const unit = series.unit ? ` ${series.unit}` : "";
  return `min ${min}${unit} | max ${max}${unit} | ultimo ${latest}${unit}`;
}

function chartIsResultChart(value: unknown): value is ResultChart {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.title === "string" &&
    typeof value.available === "boolean" &&
    Array.isArray(value.labels) &&
    Array.isArray(value.series)
  );
}

function resultCharts(
  results: Pick<DashboardResults, "charts">,
): ResultChart[] {
  return Object.values(results.charts).filter(chartIsResultChart);
}

function errorTitle(error: unknown): string {
  if (!(error instanceof ApiError)) return "No se pudieron cargar resultados";
  if (error.status === 409) return "Ejecución incompleta";
  if (error.status === 404 && /artifact/i.test(error.message)) {
    return "Archivo de resultados faltante";
  }
  if (error.status === 422) return "No se pudo leer el resultado";
  return "No se pudieron cargar resultados";
}

function ResultError({ error }: { error: unknown }) {
  return (
    <div className="result-alert" role="alert">
      <strong>{errorTitle(error)}</strong>
      <p>{error instanceof ApiError ? error.message : "Intenta de nuevo."}</p>
    </div>
  );
}

function SummarySection({ summary }: { summary: Record<string, unknown> }) {
  const scalarEntries = Object.entries(summary).filter(
    ([, value]) => !isRecord(value) && !Array.isArray(value),
  );
  const nestedEntries = Object.entries(summary).filter(([, value]) =>
    isRecord(value),
  );
  const metrics = [
    ...scalarEntries.filter(([key]) => resultUnit(key)),
    ...nestedEntries.flatMap(([group, value]) =>
      group.endsWith("_totals") && isRecord(value)
        ? Object.entries(value).filter(([key]) => resultUnit(key))
        : [],
    ),
  ];

  return (
    <section className="workspace-section" aria-labelledby="run-results">
      <h2 id="run-results">Resumen de resultados</h2>
      {metrics.length ? (
        <dl className="result-kpis" aria-label="Indicadores principales">
          {metrics.map(([key, value], index) => (
            <div key={`${key}-${index}`}>
              <dt>{resultLabel(key)}</dt>
              <dd>
                {formatResultValue(value)}
                {value !== null && value !== undefined && value !== ""
                  ? ` ${resultUnit(key)}`
                  : ""}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="empty-state">
          No hay indicadores disponibles en este resultado.
        </p>
      )}
      <details>
        <summary>Ver resumen completo</summary>
        {scalarEntries.length ? (
          <dl className="source-metadata version-metadata">
            {scalarEntries.map(([key, value]) => (
              <div key={key}>
                <dt>{summaryLabel(key)}</dt>
                <dd>{displayValue(value)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="empty-state">Resumen vacío.</p>
        )}
        {nestedEntries.map(([key, value]) => (
          <NestedKpiBlock key={key} title={key} value={value} />
        ))}
        {Object.entries(summary)
          .filter(([, value]) => Array.isArray(value))
          .map(([key, value]) => (
            <div key={key}>
              <h3>{key}</h3>
              <pre className="json-panel">{JSON.stringify(value, null, 2)}</pre>
            </div>
          ))}
      </details>
    </section>
  );
}

function summaryLabel(key: string): string {
  const labels: Record<string, string> = {
    case_name: "Nombre del caso",
    run_timestamp: "Fecha de ejecución",
    solver_name: "Solver",
    solver_status: "Estado del solver",
    termination_status: "Motivo de finalización",
    objective_value_usd: "Valor objetivo (USD)",
    model_version: "Versión del modelo",
    schema_version: "Versión del esquema",
  };
  return labels[key] || key;
}

function NestedKpiBlock({ title, value }: { title: string; value: unknown }) {
  if (!isRecord(value)) return null;
  const nestedRows: Array<[string, string, unknown]> = [];
  const scalarRows: Array<[string, unknown]> = [];
  for (const [key, nestedValue] of Object.entries(value)) {
    if (isRecord(nestedValue)) {
      for (const [nestedKey, nestedCell] of Object.entries(nestedValue)) {
        nestedRows.push([key, nestedKey, nestedCell]);
      }
    } else {
      scalarRows.push([key, nestedValue]);
    }
  }

  return (
    <div className="kpi-block">
      <h3>{title}</h3>
      {scalarRows.length ? (
        <div
          className="time-series-table-scroll result-table-scroll"
          tabIndex={0}
        >
          <table>
            <thead>
              <tr>
                <th>kpi</th>
                <th>Valor</th>
              </tr>
            </thead>
            <tbody>
              {scalarRows.map(([key, scalarValue]) => (
                <tr key={key}>
                  <td>{key}</td>
                  <td>{displayValue(scalarValue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {nestedRows.length ? (
        <div
          className="time-series-table-scroll result-table-scroll"
          tabIndex={0}
        >
          <table>
            <thead>
              <tr>
                <th>Componente</th>
                <th>kpi</th>
                <th>Valor</th>
              </tr>
            </thead>
            <tbody>
              {nestedRows.map(([assetId, key, nestedValue]) => (
                <tr key={`${assetId}:${key}`}>
                  <td>{assetId}</td>
                  <td>{key}</td>
                  <td>{displayValue(nestedValue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function ResultTableView({
  title,
  table,
}: {
  title: string;
  table: ResultTable;
}) {
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(table.rows.length / tableRowLimit));
  const currentPage = Math.min(page, pageCount - 1);
  const offset = currentPage * tableRowLimit;
  const rows = table.rows.slice(offset, offset + tableRowLimit);
  const titleId = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-table`;

  return (
    <section className="workspace-section" aria-labelledby={titleId}>
      <h2 id={titleId}>{title}</h2>
      {table.rows.length ? (
        <p className="source-note">
          Filas {offset + 1}–{offset + rows.length} de {table.rows.length}.
        </p>
      ) : (
        <p className="empty-state">No hay filas para mostrar.</p>
      )}
      <div
        className="time-series-table-scroll result-table-scroll"
        tabIndex={0}
      >
        <table>
          <thead>
            <tr>
              {table.columns.map((column) => {
                const unit = unitForColumn(column);
                return (
                  <th key={column}>
                    <span>{column}</span>
                    {unit ? <small>{unit}</small> : null}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((row, index) => (
                <tr key={index}>
                  {table.columns.map((column) => (
                    <td key={column}>{displayCell(row[column])}</td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={Math.max(table.columns.length, 1)}>Sin filas.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {pageCount > 1 ? (
        <nav className="inline-actions" aria-label={`Páginas de ${title}`}>
          <button
            type="button"
            disabled={currentPage === 0}
            onClick={() => setPage(currentPage - 1)}
          >
            Página anterior
          </button>
          <span role="status">
            Página {currentPage + 1} de {pageCount}
          </span>
          <button
            type="button"
            disabled={currentPage === pageCount - 1}
            onClick={() => setPage(currentPage + 1)}
          >
            Página siguiente
          </button>
        </nav>
      ) : null}
    </section>
  );
}

function mayRetainResult(error: unknown): boolean {
  return !(error instanceof ApiError && [401, 403, 404].includes(error.status));
}

function displayCell(value: ResultCell | undefined): string {
  if (value === null || value === undefined || value === "")
    return "No disponible";
  return String(value);
}

function PlotlyChart({ chart }: { chart: ResultChart }) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [renderError, setRenderError] = useState("");
  const traces = useMemo<PlotlyTrace[]>(
    () =>
      chart.series.map((series) => ({
        x: chart.labels,
        y: series.values,
        name: series.label,
        type: "scatter",
        mode: "lines+markers",
        connectgaps: false,
        customdata: series.values.map(() => series.unit || ""),
        hovertemplate: `%{x}<br>${series.label}: %{y} %{customdata}<extra></extra>`,
      })),
    [chart],
  );

  useEffect(() => {
    const element = chartRef.current;
    if (!element) return undefined;
    let disposed = false;
    setRenderError("");

    void loadPlotly()
      .then((plotly) => {
        if (disposed) return;
        const units = [
          ...new Set(chart.series.map((series) => series.unit).filter(Boolean)),
        ];
        plotly.react(
          element,
          traces,
          {
            title: { text: chart.title, x: 0.02 },
            autosize: true,
            height: 340,
            hovermode: "closest",
            margin: { l: 62, r: 24, t: 48, b: 92 },
            xaxis: { title: "timestamp" },
            yaxis: { title: units.length === 1 ? units[0] : "value" },
            legend: {
              orientation: "h",
              yanchor: "top",
              y: -0.25,
              itemclick: "toggle",
              itemdoubleclick: "toggleothers",
            },
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            uirevision: chart.id,
          },
          {
            responsive: true,
            displaylogo: false,
            scrollZoom: true,
          },
        );
      })
      .catch((error: Error) => {
        if (!disposed) setRenderError(error.message);
      });

    return () => {
      disposed = true;
      if (window.Plotly) window.Plotly.purge(element);
    };
  }, [chart, traces]);

  return (
    <section className="result-chart" aria-labelledby={`${chart.id}-chart`}>
      <h3 id={`${chart.id}-chart`}>{chart.title}</h3>
      <div ref={chartRef} className="plotly-chart" />
      {renderError ? <p className="field-error">{renderError}</p> : null}
      <SeriesSummary series={chart.series} />
    </section>
  );
}

function SeriesSummary({ series }: { series: ResultChartSeries[] }) {
  if (!series.length) return null;
  return (
    <ul className="series-summary">
      {series.map((item) => (
        <li key={item.key}>
          <strong>{item.label}</strong>
          <span>{seriesRange(item)}</span>
        </li>
      ))}
    </ul>
  );
}

function ChartsSection({
  results,
}: {
  results: Pick<DashboardResults, "charts">;
}) {
  const charts = resultCharts(results);
  const availableCharts = charts.filter(
    (chart) => chart.available && chart.series.length > 0,
  );
  const unavailableCharts = charts.filter((chart) => !chart.available);

  return (
    <section className="workspace-section" aria-labelledby="result-charts">
      <h2 id="result-charts">Gráficos de resultados</h2>
      {availableCharts.length ? (
        <div className="result-chart-grid">
          {availableCharts.map((chart) => (
            <PlotlyChart key={chart.id} chart={chart} />
          ))}
        </div>
      ) : (
        <p className="empty-state">No hay series disponibles para graficar.</p>
      )}
      {unavailableCharts.length ? (
        <div className="unavailable-charts">
          <h3>Gráficos no disponibles</h3>
          <ul>
            {unavailableCharts.map((chart) => (
              <li key={chart.id}>
                <strong>{chart.title}</strong>
                <span>{chart.message || "No disponible."}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

export function DashboardResultsContent({
  results,
  resultsError = "",
  actions,
}: {
  results: DashboardResults | null;
  resultsError?: string;
  actions?: ReactNode;
}) {
  if (resultsError) {
    return (
      <section className="workspace-section" aria-labelledby="dashboard-error">
        <h2 id="dashboard-error">Results Error</h2>
        <div className="result-alert" role="alert">
          <strong>No se pudieron cargar resultados</strong>
          <p>{resultsError}</p>
        </div>
      </section>
    );
  }
  if (results === null) return null;

  const hasCharts = resultCharts(results).length > 0;
  const hasAnySection =
    results.summary !== null ||
    hasCharts ||
    results.dispatch_table !== null ||
    results.asset_dispatch_table !== null;
  if (!hasAnySection) {
    return (
      <>
        <section
          className="workspace-section"
          aria-labelledby="dashboard-empty"
        >
          <h2 id="dashboard-empty">Resultados</h2>
          <p className="empty-state">
            No hay secciones de resultados disponibles para esta ejecución.
          </p>
        </section>
        {actions}
      </>
    );
  }

  return (
    <>
      {results.summary !== null ? (
        <SummarySection summary={results.summary} />
      ) : null}
      {actions}
      {hasCharts ? <ChartsSection results={results} /> : null}
      {results.dispatch_table !== null ||
      results.asset_dispatch_table !== null ? (
        <details className="workspace-section">
          <summary>Ver tablas de resultados</summary>
          {results.dispatch_table !== null ? (
            <ResultTableView
              title="Despacho del sistema"
              table={results.dispatch_table}
            />
          ) : null}
          {results.asset_dispatch_table !== null ? (
            <ResultTableView
              title="Despacho por componente"
              table={results.asset_dispatch_table}
            />
          ) : null}
        </details>
      ) : null}
    </>
  );
}

export function RunResultsSection({
  run,
  children,
}: {
  run: ScenarioRun;
  children?: ReactNode;
}) {
  const results = useQuery({
    queryKey: runResultsQueryKey(run.id),
    queryFn: ({ signal }) => getRunResults(run.id, signal),
    enabled: run.status === "succeeded",
    retry: false,
  });

  if (run.status !== "succeeded") {
    return (
      <section className="workspace-section" aria-labelledby="run-results">
        <h2 id="run-results">Resultados</h2>
        <p className="empty-state">
          Los resultados estarán disponibles cuando finalice la ejecución.
        </p>
      </section>
    );
  }

  if (results.isPending) {
    return (
      <section className="workspace-section" aria-labelledby="run-results">
        <h2 id="run-results">Resultados</h2>
        <p className="inline-status" role="status">
          Cargando resultados
        </p>
      </section>
    );
  }

  return (
    <>
      {results.isError ? (
        <section
          className="workspace-section"
          aria-label="Error de consulta de resultados"
        >
          {results.data && mayRetainResult(results.error) ? (
            <p>Se conserva el último resultado consultado.</p>
          ) : null}
          <ResultError error={results.error} />
          <button
            type="button"
            disabled={results.isFetching}
            onClick={() => void results.refetch()}
          >
            {results.isFetching
              ? "Consultando resultados"
              : "Reintentar resultados"}
          </button>
        </section>
      ) : null}
      {results.data && mayRetainResult(results.error) ? (
        <DashboardResultsContent results={results.data} actions={children} />
      ) : (
        children
      )}
    </>
  );
}

function ArtifactList({ artifacts }: { artifacts: RunArtifact[] }) {
  if (!artifacts.length) {
    return <p className="empty-state">Aún no hay archivos registrados.</p>;
  }

  return (
    <ul className="resource-list artifact-list">
      {artifacts.map((artifact) => (
        <li key={artifact.id}>
          <a href={artifact.download_url} download={artifact.display_name}>
            {artifact.display_name}
          </a>
          <p>
            {artifact.artifact_type} | {artifact.media_type} |{" "}
            {artifact.byte_size} bytes
          </p>
        </li>
      ))}
    </ul>
  );
}

export function RunArtifactsSection({ run }: { run: ScenarioRun }) {
  const artifacts = useQuery({
    queryKey: runArtifactsQueryKey(run.id),
    queryFn: ({ signal }) => listRunArtifacts(run.id, signal),
    enabled: terminalRunStatuses.has(run.status),
    retry: false,
  });

  return (
    <section className="workspace-section" aria-labelledby="run-artifacts">
      <h2 id="run-artifacts">Archivos de la ejecución</h2>
      {!terminalRunStatuses.has(run.status) ? (
        <p className="empty-state">
          Los archivos estarán disponibles cuando termine la ejecución.
        </p>
      ) : artifacts.isPending ? (
        <p className="inline-status" role="status">
          Cargando archivos
        </p>
      ) : artifacts.isError ? (
        <>
          <ResultError error={artifacts.error} />
          <button
            type="button"
            disabled={artifacts.isFetching}
            onClick={() => void artifacts.refetch()}
          >
            {artifacts.isFetching
              ? "Consultando archivos"
              : "Reintentar archivos"}
          </button>
          {artifacts.data && mayRetainResult(artifacts.error) ? (
            <ArtifactList artifacts={artifacts.data} />
          ) : null}
        </>
      ) : (
        <ArtifactList artifacts={artifacts.data} />
      )}
    </section>
  );
}
