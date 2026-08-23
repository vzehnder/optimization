import { render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { PortalPublicationReport, PortalResultsBlock } from "./PortalResults";
import type {
  ClientPublicationDetail,
  PortalResultsBlockPayload,
} from "./api/client";

function emptyLabels(): PortalResultsBlockPayload["labels"] {
  return { kpis: "", charts: "", tables: "", downloads: "" };
}

function block(
  partial: Partial<PortalResultsBlockPayload>,
): PortalResultsBlockPayload {
  return {
    labels: emptyLabels(),
    kpis: [],
    charts: [],
    tables: [],
    ...partial,
  };
}

function blockWithKpis(
  kpis: PortalResultsBlockPayload["kpis"],
): PortalResultsBlockPayload {
  return block({ labels: { ...emptyLabels(), kpis: "Resumen" }, kpis });
}

const configuredChart: PortalResultsBlockPayload["charts"][number] = {
  id: "intercambio_red",
  label: "Intercambio con la red",
  x_labels: ["2026-01-01T00:00:00", "2026-01-01T01:00:00"],
  series: [
    { label: "Compra", unit: "MW", values: [2.5, 0] },
    { label: "Venta", unit: "MW", values: [0, 1.5] },
  ],
};

const configuredTable: PortalResultsBlockPayload["tables"][number] = {
  id: "despacho_sistema",
  label: "Despacho del sistema",
  row_limit: 24,
  columns: [
    { id: "periodo", label: "Periodo", unit: null },
    { id: "compra", label: "Compra", unit: "MW" },
  ],
  rows: [
    { periodo: "2026-01-01T00:00:00", compra: 2.5 },
    { periodo: "2026-01-01T01:00:00", compra: 0 },
  ],
};

function stubPlotly() {
  const plotly = { react: vi.fn(), purge: vi.fn() };
  vi.stubGlobal("Plotly", plotly);
  return plotly;
}

describe("configured portal KPIs", () => {
  it("renders the configured section label and KPI presentation", () => {
    render(
      <PortalResultsBlock
        block={blockWithKpis([
          {
            id: "beneficio_total",
            label: "Beneficio total",
            value: 1250.5,
            unit: "USD",
            decimals: 1,
            sign: "auto",
            emphasis: "strong",
          },
        ])}
      />,
    );

    expect(screen.getByRole("heading", { name: "Resumen" })).toBeVisible();
    expect(screen.getByText("Beneficio total")).toBeVisible();
    expect(screen.getByText("1250.5")).toBeVisible();
    expect(screen.getByText("USD")).toBeVisible();
  });

  it("applies the configured decimals and sign", () => {
    render(
      <PortalResultsBlock
        block={blockWithKpis([
          {
            id: "redondeado",
            label: "Redondeado",
            value: 1250.5,
            unit: null,
            decimals: 0,
            sign: "auto",
            emphasis: "normal",
          },
          {
            id: "con_signo",
            label: "Con signo",
            value: 42,
            unit: null,
            decimals: 0,
            sign: "always",
            emphasis: "normal",
          },
          {
            id: "sin_signo",
            label: "Sin signo",
            value: -42,
            unit: null,
            decimals: 0,
            sign: "never",
            emphasis: "normal",
          },
        ])}
      />,
    );

    expect(screen.getByText("1251")).toBeVisible();
    expect(screen.getByText("+42")).toBeVisible();
    expect(screen.getByText("42")).toBeVisible();
  });

  it("marks an emphasized KPI so the portal can highlight it", () => {
    render(
      <PortalResultsBlock
        block={blockWithKpis([
          {
            id: "beneficio_total",
            label: "Beneficio total",
            value: 10,
            unit: null,
            decimals: 0,
            sign: "auto",
            emphasis: "strong",
          },
        ])}
      />,
    );

    expect(screen.getByTestId("portal-kpi-beneficio_total")).toHaveAttribute(
      "data-emphasis",
      "strong",
    );
  });

  it("renders nothing when no section is configured", () => {
    const { container } = render(<PortalResultsBlock block={block({})} />);

    expect(container).toBeEmptyDOMElement();
  });
});

describe("configured portal charts", () => {
  it("renders the configured chart under its section label", async () => {
    const plotly = stubPlotly();

    render(
      <PortalResultsBlock
        block={block({
          labels: { ...emptyLabels(), charts: "Resultados" },
          charts: [configuredChart],
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: "Resultados" })).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Intercambio con la red" }),
    ).toBeVisible();
    await waitFor(() => expect(plotly.react).toHaveBeenCalled());
    expect(plotly.react.mock.calls[0][1]).toEqual([
      expect.objectContaining({
        name: "Compra",
        x: configuredChart.x_labels,
        y: [2.5, 0],
      }),
      expect.objectContaining({ name: "Venta", y: [0, 1.5] }),
    ]);
  });

  it("lists each configured series with its public label and unit", () => {
    stubPlotly();

    render(
      <PortalResultsBlock
        block={block({
          labels: { ...emptyLabels(), charts: "Resultados" },
          charts: [configuredChart],
        })}
      />,
    );

    const summary = screen.getByTestId("portal-chart-series-intercambio_red");
    expect(within(summary).getByText("Compra")).toBeVisible();
    expect(within(summary).getByText("Venta")).toBeVisible();
    expect(within(summary).getAllByText(/MW/)).not.toHaveLength(0);
  });

  it("shows an empty state when the section has no available chart", () => {
    render(
      <PortalResultsBlock
        block={block({
          labels: { ...emptyLabels(), charts: "Resultados" },
          charts: [],
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: "Resultados" })).toBeVisible();
    expect(
      screen.getByText("No hay graficos disponibles para esta publicacion."),
    ).toBeVisible();
  });
});

describe("configured portal tables", () => {
  it("renders the configured columns and rows", () => {
    render(
      <PortalResultsBlock
        block={block({
          labels: { ...emptyLabels(), tables: "Detalle" },
          tables: [configuredTable],
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: "Detalle" })).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Despacho del sistema" }),
    ).toBeVisible();
    const table = screen.getByTestId("portal-table-despacho_sistema");
    expect(within(table).getByText("Periodo")).toBeVisible();
    expect(within(table).getByText("Compra")).toBeVisible();
    expect(within(table).getByText("MW")).toBeVisible();
    expect(within(table).getByText("2026-01-01T01:00:00")).toBeVisible();
    expect(within(table).getByText("2.5")).toBeVisible();
  });

  it("shows an empty state when a configured table has no rows", () => {
    render(
      <PortalResultsBlock
        block={block({
          labels: { ...emptyLabels(), tables: "Detalle" },
          tables: [{ ...configuredTable, rows: [] }],
        })}
      />,
    );

    expect(screen.getByText("No hay filas para mostrar.")).toBeVisible();
  });

  it("shows an empty state when the section has no available table", () => {
    render(
      <PortalResultsBlock
        block={block({
          labels: { ...emptyLabels(), tables: "Detalle" },
          tables: [],
        })}
      />,
    );

    expect(
      screen.getByText("No hay tablas disponibles para esta publicacion."),
    ).toBeVisible();
  });
});

const fullBlock: PortalResultsBlockPayload = {
  labels: {
    kpis: "Resumen",
    charts: "Resultados",
    tables: "Detalle",
    downloads: "Descargas",
  },
  kpis: [
    {
      id: "beneficio_total",
      label: "Beneficio total",
      value: 1250.5,
      unit: "USD",
      decimals: 1,
      sign: "auto",
      emphasis: "strong",
    },
  ],
  charts: [configuredChart],
  tables: [configuredTable],
};

function publicationDetail(
  overrides: Partial<ClientPublicationDetail> = {},
): ClientPublicationDetail {
  return {
    project: { id: 1, name: "Hybrid PMGD" },
    publication: {
      id: 9,
      project_id: 1,
      public_title: "Plan operativo enero",
      analyst_notes: "Aprobado.",
      published_at: "2026-08-23T12:00:00+00:00",
      status: "published",
    },
    period: { start: "2026-01-01T00:00:00", end: "2026-01-01T01:00:00" },
    results_state: "available",
    results_block: fullBlock,
    downloads: [
      {
        label: "summary.json",
        media_type: "application/json",
        byte_size: 128,
        download_url:
          "/api/client/projects/1/publications/9/artifacts/summary_json/download",
      },
    ],
    ...overrides,
  };
}

describe("the configured publication report", () => {
  it("keeps the fixed macro order of the portal shell", () => {
    stubPlotly();

    render(<PortalPublicationReport detail={publicationDetail()} />);

    const headings = screen
      .getAllByRole("heading", { level: 2 })
      .map((heading) => heading.textContent);
    expect(headings).toEqual(["Resumen", "Resultados", "Detalle", "Descargas"]);
  });

  it("offers every configured download", () => {
    stubPlotly();

    render(<PortalPublicationReport detail={publicationDetail()} />);

    const link = screen.getByRole("link", { name: "summary.json" });
    expect(link).toHaveAttribute(
      "href",
      "/api/client/projects/1/publications/9/artifacts/summary_json/download",
    );
  });

  it("says the results are unavailable without naming an artifact", () => {
    render(
      <PortalPublicationReport
        detail={publicationDetail({
          results_state: "unavailable",
          results_block: null,
          downloads: [],
        })}
      />,
    );

    expect(
      screen.getByText(
        "Los resultados de esta publicacion no estan disponibles.",
      ),
    ).toBeVisible();
    expect(screen.queryByText(/summary\.json/)).toBeNull();
    expect(screen.queryByText(/artifact/i)).toBeNull();
  });
});

function stubPortalFetch(path: string, detail: ClientPublicationDetail) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const requested = String(input);
      if (requested === "/api/auth/me") {
        return Response.json({
          user: {
            id: 7,
            email: "viewer@example.local",
            display_name: "External Viewer",
            role: path.startsWith("/api/client") ? "external" : "analyst",
            is_active: true,
          },
          bootstrap_required: false,
        });
      }
      if (requested === path) return Response.json(detail);
      return Response.json(
        { detail: `unhandled GET ${requested}` },
        { status: 500 },
      );
    }),
  );
}

describe("client portal publication", () => {
  it("shows the whole configured report to the external viewer", async () => {
    stubPlotly();
    window.history.replaceState(
      {},
      "",
      "/react/client/projects/1/publications/9",
    );
    stubPortalFetch(
      "/api/client/projects/1/publications/9",
      publicationDetail(),
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Plan operativo enero" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Resumen" })).toBeVisible();
    expect(screen.getByText("Beneficio total")).toBeVisible();
    expect(screen.getByText("1250.5")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Intercambio con la red" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Despacho del sistema" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "summary.json" })).toBeVisible();
  });

  it("never shows the client a run, a template or a scenario version", async () => {
    stubPlotly();
    window.history.replaceState(
      {},
      "",
      "/react/client/projects/1/publications/9",
    );
    stubPortalFetch(
      "/api/client/projects/1/publications/9",
      publicationDetail(),
    );

    render(<App />);

    await screen.findByRole("heading", { name: "Plan operativo enero" });
    expect(screen.queryByText(/Template/i)).toBeNull();
    expect(screen.queryByText(/Run Status/i)).toBeNull();
    expect(screen.queryByText(/Scenario Version/i)).toBeNull();
  });
});

describe("internal publication preview", () => {
  it("shows the analyst exactly the report the client will see", async () => {
    stubPlotly();
    window.history.replaceState({}, "", "/react/publications/9/preview");
    stubPortalFetch("/api/publications/9/preview", {
      ...publicationDetail(),
      preview_context: {
        run_id: 4,
        scenario_version_number: 1,
        results_error: "",
      },
    });

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Plan operativo enero" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Resumen" })).toBeVisible();
    expect(screen.getByText("Beneficio total")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Intercambio con la red" }),
    ).toBeVisible();
  });
});
