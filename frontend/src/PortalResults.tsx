import { useEffect, useMemo, useRef, useState } from "react";

import type {
  ClientPublicationDetail,
  PortalChart,
  PortalKpi,
  PortalResultsBlockPayload,
  PortalTable,
  PublicationDownload,
} from "./api/client";
import { loadPlotly, type PlotlyTrace } from "./plotly";

function formatPortalKpiValue(kpi: PortalKpi): string {
  if (typeof kpi.value !== "number") return String(kpi.value);
  const magnitude = kpi.sign === "never" ? Math.abs(kpi.value) : kpi.value;
  const formatted = magnitude.toFixed(kpi.decimals);
  if (kpi.sign === "always" && magnitude > 0) return `+${formatted}`;
  return formatted;
}

function formatPortalCell(value: number | string | null): string {
  if (value === null) return "";
  return String(value);
}

function PortalSection({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section className="workspace-section" aria-labelledby={id}>
      <h2 id={id}>{label}</h2>
      {children}
    </section>
  );
}

function PortalKpiList({ kpis }: { kpis: PortalKpi[] }) {
  if (!kpis.length) {
    return (
      <p className="empty-state">
        No hay indicadores disponibles para esta publicacion.
      </p>
    );
  }
  return (
    <dl className="portal-kpi-list">
      {kpis.map((kpi) => (
        <div
          key={kpi.id}
          className="portal-kpi"
          data-testid={`portal-kpi-${kpi.id}`}
          data-emphasis={kpi.emphasis}
        >
          <dt>{kpi.label}</dt>
          <dd>
            <span className="portal-kpi-value">
              {formatPortalKpiValue(kpi)}
            </span>
            {kpi.unit ? (
              <span className="portal-kpi-unit"> {kpi.unit}</span>
            ) : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function PortalChartView({ chart }: { chart: PortalChart }) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [renderError, setRenderError] = useState("");
  const traces = useMemo<PlotlyTrace[]>(
    () =>
      chart.series.map((series) => ({
        x: chart.x_labels,
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
            title: { text: chart.label, x: 0.02 },
            autosize: true,
            height: 340,
            hovermode: "closest",
            margin: { l: 62, r: 24, t: 48, b: 92 },
            yaxis: { title: units.length === 1 ? units[0] : "" },
            legend: { orientation: "h", yanchor: "top", y: -0.25 },
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            uirevision: chart.id,
          },
          { responsive: true, displaylogo: false },
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
      <h3 id={`${chart.id}-chart`}>{chart.label}</h3>
      <div ref={chartRef} className="plotly-chart" />
      {renderError ? <p className="field-error">{renderError}</p> : null}
      <ul
        className="series-summary"
        data-testid={`portal-chart-series-${chart.id}`}
      >
        {chart.series.map((series) => (
          <li key={series.label}>
            <strong>{series.label}</strong>
            {series.unit ? <span>{series.unit}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

function PortalTableView({ table }: { table: PortalTable }) {
  return (
    <section className="result-chart" aria-labelledby={`${table.id}-table`}>
      <h3 id={`${table.id}-table`}>{table.label}</h3>
      {table.rows.length ? (
        <p className="source-note">
          Mostrando {table.rows.length} de hasta {table.row_limit} filas.
        </p>
      ) : (
        <p className="empty-state">No hay filas para mostrar.</p>
      )}
      <div
        className="time-series-table-scroll result-table-scroll"
        tabIndex={0}
      >
        <table data-testid={`portal-table-${table.id}`}>
          <thead>
            <tr>
              {table.columns.map((column) => (
                <th key={column.id}>
                  {column.label}
                  {column.unit ? (
                    <span className="column-unit"> {column.unit}</span>
                  ) : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, index) => (
              <tr key={index}>
                {table.columns.map((column) => (
                  <td key={column.id}>{formatPortalCell(row[column.id])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function PortalResultsBlock({
  block,
  resultsState = "available",
  idPrefix = "portal",
  unavailableMessage = "Los resultados de esta publicacion no estan disponibles.",
}: {
  block: PortalResultsBlockPayload | null | undefined;
  resultsState?: "available" | "unavailable";
  // Two blocks share one page when runs are compared, so their section ids and
  // their empty wording belong to the surface that renders them.
  idPrefix?: string;
  unavailableMessage?: string;
}) {
  if (resultsState === "unavailable") {
    return (
      <section
        className="workspace-section"
        aria-labelledby={`${idPrefix}-results`}
      >
        <h2 id={`${idPrefix}-results`}>Resultados</h2>
        <p className="empty-state">{unavailableMessage}</p>
      </section>
    );
  }
  if (!block) return null;

  return (
    <>
      {block.labels.kpis ? (
        <PortalSection id={`${idPrefix}-kpis`} label={block.labels.kpis}>
          <PortalKpiList kpis={block.kpis} />
        </PortalSection>
      ) : null}
      {block.labels.charts ? (
        <PortalSection id={`${idPrefix}-charts`} label={block.labels.charts}>
          {block.charts.length ? (
            <div className="result-chart-grid">
              {block.charts.map((chart) => (
                <PortalChartView key={chart.id} chart={chart} />
              ))}
            </div>
          ) : (
            <p className="empty-state">
              No hay graficos disponibles para esta publicacion.
            </p>
          )}
        </PortalSection>
      ) : null}
      {block.labels.tables ? (
        <PortalSection id={`${idPrefix}-tables`} label={block.labels.tables}>
          {block.tables.length ? (
            block.tables.map((table) => (
              <PortalTableView key={table.id} table={table} />
            ))
          ) : (
            <p className="empty-state">
              No hay tablas disponibles para esta publicacion.
            </p>
          )}
        </PortalSection>
      ) : null}
    </>
  );
}

export function PortalDownloads({
  label,
  downloads,
}: {
  label: string;
  downloads: PublicationDownload[];
}) {
  if (!label) return null;
  return (
    <PortalSection id="portal-downloads" label={label}>
      {downloads.length ? (
        <ul className="resource-list artifact-list">
          {downloads.map((download) => (
            <li key={download.download_url}>
              <a href={download.download_url} download={download.label}>
                {download.label}
              </a>
              <p>
                {download.media_type} | {download.byte_size} bytes
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-state">No hay descargas disponibles.</p>
      )}
    </PortalSection>
  );
}

export function PortalPublicationReport({
  detail,
}: {
  detail: ClientPublicationDetail;
}) {
  return (
    <div className="workspace-stack">
      <PortalResultsBlock
        block={detail.results_block}
        resultsState={detail.results_state}
      />
      <PortalDownloads
        label={detail.results_block?.labels.downloads || ""}
        downloads={detail.downloads}
      />
    </div>
  );
}

export function PortalPublicationHeader({
  detail,
}: {
  detail: ClientPublicationDetail;
}) {
  const { start, end } = detail.period;
  return (
    <header className="workspace-heading">
      <div className="portal-branding">
        {detail.branding.logo_url ? (
          <img
            className="portal-logo"
            src={detail.branding.logo_url}
            alt={`Logo de ${detail.branding.display_name}`}
          />
        ) : null}
        <p className="portal-display-name">{detail.branding.display_name}</p>
      </div>
      <p className="eyebrow">Publicacion</p>
      <h1>{detail.publication.public_title}</h1>
      <p>{detail.publication.analyst_notes || "Sin notas."}</p>
      <dl className="portal-publication-meta">
        <div>
          <dt>Publicado</dt>
          <dd>{detail.publication.published_at || "Pendiente"}</dd>
        </div>
        {start && end ? (
          <div>
            <dt>Periodo</dt>
            <dd>
              {start} - {end}
            </dd>
          </div>
        ) : null}
      </dl>
    </header>
  );
}
