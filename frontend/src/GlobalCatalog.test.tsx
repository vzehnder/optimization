import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

const VERIFICATION_IDENTITY = {
  user: {
    id: 3,
    email: "verifier@example.local",
    display_name: "Cuenta de verificacion",
    role: "admin",
    is_active: true,
  },
  bootstrap_required: false,
  landing_path: "/react/projects",
  ts_next_canonical_read: true,
};

const REGULAR_IDENTITY = {
  ...VERIFICATION_IDENTITY,
  user: {
    ...VERIFICATION_IDENTITY.user,
    id: 4,
    email: "ada@example.local",
    display_name: "Ada Analyst",
    role: "analyst",
  },
  ts_next_canonical_read: false,
};

function inputRow(overrides: Record<string, unknown> = {}) {
  return {
    entry_kind: "input",
    signal_id: 41,
    identity: {
      series_key: "energy_price",
      display_name: "Precio de energia",
      description: "Precio spot horario",
      status: "active",
    },
    owner: { project_id: 1, project_name: "Cuenca Norte" },
    set: {
      id: 7,
      name: "Inputs 2026",
      version_number: 1,
      version_label: "v1",
      description: "Senales operativas",
      status: "active",
      visibility_scope: "global",
    },
    classification: {
      semantic_type_key: "energy_price",
      data_class_key: "real",
      unit_key: "usd_per_mwh",
    },
    current_revision: {
      id: 90,
      number: 2,
      sealed: true,
      created_at: "2026-02-01T10:00:00Z",
    },
    coverage_summary: {
      start: "2026-01-01T00:00:00",
      end: "2026-01-02T00:00:00",
      period_count: 24,
      nominal_resolution_seconds: 3600,
      minimum_resolution_seconds: 3600,
      maximum_resolution_seconds: 3600,
      regularity: "regular",
      source_timezone: "UTC",
    },
    origin_summary: { source_kind: "api" },
    link_summary: { association_count: 2, binding_count: 1 },
    capabilities: {
      view_detail: true,
      preview: true,
      associate: true,
      bind: true,
      edit_set: true,
      publish_revision: true,
    },
    resource_version: 12,
    links: {
      detail: "/api/time-series/catalog/inputs/41",
      preview: "/api/time-series/catalog/inputs/41/preview",
      revisions: "/api/time-series/catalog/inputs/41/revisions",
    },
    ...overrides,
  };
}

function inputDetail(overrides: Record<string, unknown> = {}) {
  const row = inputRow();
  return {
    signal_id: 41,
    identity: row.identity,
    owner: row.owner,
    set: { ...row.set, scope_revision: 3 },
    contract: {
      semantic_type: {
        key: "energy_price",
        display_name: "Precio de energia",
        description: "Precio spot",
        status: "active",
        dimension_key: "currency_per_energy",
        value_kind: "continuous",
        default_aggregation: "mean",
      },
      data_class: { key: "real", display_name: "Real", status: "active" },
      unit: {
        key: "usd_per_mwh",
        symbol: "USD/MWh",
        dimension_key: "currency_per_energy",
        status: "active",
      },
      signal_role: "input",
      aggregation: "mean",
    },
    current_revision: {
      id: 90,
      number: 2,
      state: "sealed",
      content_hash: "9f2b7c1de4a05688",
      timezone: "UTC",
      timestamp_convention: "interval_start",
      created_at: "2026-02-01T10:00:00Z",
      created_by: "analyst@example.local",
    },
    coverage_summary: row.coverage_summary,
    origin_summary: row.origin_summary,
    link_summary: row.link_summary,
    provenance: {
      kind: "file",
      source_key: "precios-2026",
      filename: "precios_2026.csv",
      media_type: "text/csv",
      checksum: "sha256:abc123",
    },
    validation_summary: { status: "ok", error_count: 0 },
    ...overrides,
  };
}

function revisionPage() {
  return {
    items: [
      {
        id: 90,
        number: 2,
        state: "sealed",
        content_hash: "9f2b7c1de4a05688",
        created_at: "2026-02-01T10:00:00Z",
        created_by: "analyst@example.local",
        change_summary: "Actualizacion mensual",
        source_kind: "file",
      },
      {
        id: 71,
        number: 1,
        state: "sealed",
        content_hash: "1a0f33ce7788bb21",
        created_at: "2026-01-01T10:00:00Z",
        created_by: "analyst@example.local",
        change_summary: null,
        source_kind: "api",
      },
    ],
    page: { limit: 50, has_more: false, next_cursor: null },
    summary: { total_count: 2 },
    facets: null,
    meta: { section: "input_revisions", signal_id: 41, catalog_generation: 3 },
  };
}

function descriptorPage(kind: string) {
  const items: Record<string, unknown[]> = {
    semantic_type: [
      { id: 1, key: "energy_price", display_name: "Precio de energia", status: "active" },
      { id: 2, key: "hydro_inflow", display_name: "Caudal afluente", status: "active" },
    ],
    data_class: [
      { id: 3, key: "real", display_name: "Real", status: "active" },
      { id: 4, key: "forecast", display_name: "Pronostico", status: "active" },
    ],
    unit: [
      { id: 5, key: "usd_per_mwh", display_name: "USD por MWh", status: "active" },
      { id: 6, key: "m3_per_s", display_name: "Metros cubicos por segundo", status: "active" },
    ],
  };
  return {
    items: items[kind] ?? [],
    page: { limit: 50, has_more: false, next_cursor: null },
    summary: { total_count: (items[kind] ?? []).length },
    facets: null,
    meta: { section: "descriptors", kind, catalog_generation: 5 },
  };
}

function catalogFetch(
  handlers: Record<string, (url: URL) => Response> = {},
  identity: unknown = VERIFICATION_IDENTITY,
) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    void init;
    const url = new URL(String(input), "http://localhost");
    const path = url.pathname;
    const handler = handlers[path];
    if (handler) return handler(url);
    if (path === "/api/auth/me") return json(identity);
    if (path === "/api/time-series/catalog/descriptors")
      return json(descriptorPage(url.searchParams.get("kind") || ""));
    return new Response(JSON.stringify({ detail: `unhandled ${path}` }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  });
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("layered catalog read surface", () => {
  it("lists one row per signal with owner, scope, contract, coverage and resolution", async () => {
    window.history.replaceState({}, "", "/react/time-series/catalog");
    const fetchMock = catalogFetch({
      "/api/time-series/catalog/inputs": () =>
        json({
          items: [inputRow()],
          page: { limit: 50, has_more: false, next_cursor: null },
          summary: { total_count: 1 },
          facets: null,
          meta: {
            section: "inputs",
            catalog_generation: 1842,
            request_id: "req_1",
          },
        }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const table = await screen.findByRole("table", {
      name: "Senales genericas del catalogo",
    });
    const row = within(table).getByRole("row", { name: /Precio de energia/ });
    expect(
      within(row)
        .getAllByRole("cell")
        .slice(0, 7)
        .map((cell) => cell.textContent),
    ).toEqual([
      "Cuenca Norte",
      "global",
      "energy_price",
      "real",
      "usd_per_mwh",
      "2026-01-01T00:00:00 - 2026-01-02T00:00:00",
      "1 h",
    ]);
    expect(within(row).getByText("Precio de energia")).toBeVisible();
  });

  it("sends every filter to the server and shows only what the server answered", async () => {
    window.history.replaceState({}, "", "/react/time-series/catalog");
    const requested: string[] = [];
    const fetchMock = catalogFetch({
      "/api/time-series/catalog/inputs": (url) => {
        requested.push(url.search);
        // The filtered answer carries a signal the first page never held, so a
        // client that filtered its own rows could not produce this table.
        const filtered = url.searchParams.get("semantic_type_key") === "hydro_inflow";
        return json({
          items: filtered
            ? [
                inputRow({
                  signal_id: 77,
                  identity: {
                    series_key: "inflow_node_a",
                    display_name: "Caudal afluente Nodo A",
                    description: null,
                    status: "active",
                  },
                  classification: {
                    semantic_type_key: "hydro_inflow",
                    data_class_key: "real",
                    unit_key: "m3_per_s",
                  },
                }),
              ]
            : [inputRow()],
          page: { limit: 50, has_more: false, next_cursor: null },
          summary: { total_count: 1 },
          facets: null,
          meta: { section: "inputs", catalog_generation: 1842 },
        });
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("table", { name: "Senales genericas del catalogo" });
    await user.type(screen.getByLabelText("Buscar"), "caudal");
    await user.selectOptions(
      screen.getByLabelText("Tipo semantico"),
      "hydro_inflow",
    );
    await user.selectOptions(screen.getByLabelText("Clase"), "real");
    await user.selectOptions(screen.getByLabelText("Unidad"), "m3_per_s");
    await user.selectOptions(screen.getByLabelText("Alcance"), "global");
    await user.click(screen.getByRole("button", { name: "Filtrar" }));

    await waitFor(() =>
      expect(
        screen.getByRole("row", { name: /Caudal afluente Nodo A/ }),
      ).toBeVisible(),
    );
    expect(
      screen.queryByRole("row", { name: /Precio de energia/ }),
    ).not.toBeInTheDocument();
    const query = new URLSearchParams(requested[requested.length - 1]);
    expect(query.get("q")).toBe("caudal");
    expect(query.get("semantic_type_key")).toBe("hydro_inflow");
    expect(query.get("data_class_key")).toBe("real");
    expect(query.get("unit_key")).toBe("m3_per_s");
    expect(query.get("visibility_scope")).toBe("global");
  });

  it("pages forward and back with the server cursor and never in memory", async () => {
    window.history.replaceState({}, "", "/react/time-series/catalog");
    const requested: string[] = [];
    const fetchMock = catalogFetch({
      "/api/time-series/catalog/inputs": (url) => {
        requested.push(url.searchParams.get("cursor") ?? "");
        const second = url.searchParams.get("cursor") === "cursor-page-2";
        return json({
          items: [
            second
              ? inputRow({
                  signal_id: 88,
                  identity: {
                    series_key: "load_forecast",
                    display_name: "Demanda proyectada",
                    description: null,
                    status: "active",
                  },
                })
              : inputRow(),
          ],
          page: {
            limit: 50,
            has_more: !second,
            next_cursor: second ? null : "cursor-page-2",
          },
          summary: { total_count: 2 },
          facets: null,
          meta: { section: "inputs", catalog_generation: 1842 },
        });
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("row", { name: /Precio de energia/ });
    const next = screen.getByRole("button", { name: "Siguiente" });
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();

    await user.click(next);

    await waitFor(() =>
      expect(
        screen.getByRole("row", { name: /Demanda proyectada/ }),
      ).toBeVisible(),
    );
    expect(
      screen.queryByRole("row", { name: /Precio de energia/ }),
    ).not.toBeInTheDocument();
    expect(requested).toEqual(["", "cursor-page-2"]);
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Anterior" }));

    await waitFor(() =>
      expect(
        screen.getByRole("row", { name: /Precio de energia/ }),
      ).toBeVisible(),
    );
  });

  it("inspects contract, provenance, revision hash, coverage and consumers without points", async () => {
    window.history.replaceState({}, "", "/react/time-series/catalog");
    const fetchMock = catalogFetch({
      "/api/time-series/catalog/inputs": () =>
        json({
          items: [inputRow()],
          page: { limit: 50, has_more: false, next_cursor: null },
          summary: { total_count: 1 },
          facets: null,
          meta: { section: "inputs", catalog_generation: 1842 },
        }),
      "/api/time-series/catalog/inputs/41": () => json(inputDetail()),
      "/api/time-series/catalog/inputs/41/revisions": () => json(revisionPage()),
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("row", { name: /Precio de energia/ });
    await user.click(screen.getByRole("button", { name: "Inspeccionar" }));

    const inspector = await screen.findByRole("region", {
      name: "Inspector de senal",
    });
    const block = (name: string) =>
      within(inspector).getByRole("region", { name });

    const contract = block("Contrato");
    expect(within(contract).getByText("USD/MWh")).toBeVisible();
    expect(within(contract).getByText("currency_per_energy")).toBeVisible();
    expect(within(contract).getByText("input / mean")).toBeVisible();

    const provenance = block("Procedencia");
    expect(within(provenance).getByText("precios_2026.csv")).toBeVisible();
    expect(within(provenance).getByText("sha256:abc123")).toBeVisible();

    const revision = block("Revision vigente");
    expect(within(revision).getByText("9f2b7c1de4a05688")).toBeVisible();
    expect(within(revision).getByText("Revision 2")).toBeVisible();
    expect(within(revision).getByText("sealed")).toBeVisible();

    const coverage = block("Cobertura y resolucion");
    expect(
      within(coverage).getByText("2026-01-01T00:00:00 - 2026-01-02T00:00:00"),
    ).toBeVisible();
    expect(within(coverage).getByText("1 h")).toBeVisible();
    expect(within(coverage).getByText("regular")).toBeVisible();

    const consumers = block("Consumidores");
    expect(within(consumers).getByText("2 asociaciones")).toBeVisible();
    expect(
      within(consumers).getByText("1 binding de ejecucion"),
    ).toBeVisible();

    const history = block("Historia de revisiones");
    expect(within(history).getByText("Actualizacion mensual")).toBeVisible();
    expect(within(history).getByText("1a0f33ce7788bb21")).toBeVisible();

    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).includes("/preview"),
      ),
    ).toHaveLength(0);
  });

  it("renders a bounded preview that cites the exact revision it asked for", async () => {
    window.history.replaceState({}, "", "/react/time-series/catalog");
    let previewQuery = "";
    const fetchMock = catalogFetch({
      "/api/time-series/catalog/inputs": () =>
        json({
          items: [inputRow()],
          page: { limit: 50, has_more: false, next_cursor: null },
          summary: { total_count: 1 },
          facets: null,
          meta: { section: "inputs", catalog_generation: 1842 },
        }),
      "/api/time-series/catalog/inputs/41": () => json(inputDetail()),
      "/api/time-series/catalog/inputs/41/revisions": () => json(revisionPage()),
      "/api/time-series/catalog/inputs/41/preview": (url) => {
        previewQuery = url.search;
        return json({
          signal_id: 41,
          revision: { id: 71, content_hash: "1a0f33ce7788bb21" },
          requested_range: {
            from: "2026-01-01T00:00:00Z",
            to: "2026-01-02T00:00:00Z",
          },
          effective_range: {
            from: "2026-01-01T00:00:00",
            to: "2026-01-01T02:00:00",
          },
          sampling: "minmax",
          max_points: 500,
          source_point_count: 24,
          returned_point_count: 2,
          unit: { key: "usd_per_mwh", symbol: "USD/MWh" },
          points: [
            {
              timestamp_start: "2026-01-01T00:00:00",
              timestamp_end: "2026-01-01T01:00:00",
              value: 70.5,
              quality_flag: "ok",
            },
            {
              timestamp_start: "2026-01-01T01:00:00",
              timestamp_end: "2026-01-01T02:00:00",
              value: 72.25,
              quality_flag: "ok",
            },
          ],
        });
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("row", { name: /Precio de energia/ });
    await user.click(screen.getByRole("button", { name: "Inspeccionar" }));
    await screen.findByRole("region", { name: "Inspector de senal" });

    await user.selectOptions(screen.getByLabelText("Revision"), "71");
    await user.click(screen.getByRole("button", { name: "Previsualizar" }));

    const preview = await screen.findByRole("region", {
      name: "Preview acotado",
    });
    const query = new URLSearchParams(previewQuery);
    expect(query.get("revision_id")).toBe("71");
    expect(query.get("sampling")).toBe("minmax");
    expect(query.get("max_points")).toBe("500");
    expect(query.get("from")).toBe("2026-01-01T00:00:00Z");
    expect(query.get("to")).toBe("2026-01-02T00:00:00Z");
    expect(
      within(preview).getByText(
        "Revision 1 (id 71) - hash 1a0f33ce7788bb21 - 2 de 24 puntos - USD/MWh",
      ),
    ).toBeVisible();
    expect(within(preview).getByText("72.25")).toBeVisible();
  });

  it("surfaces an over-limit preview as a readable refusal, never a silent cut", async () => {
    window.history.replaceState({}, "", "/react/time-series/catalog");
    const fetchMock = catalogFetch({
      "/api/time-series/catalog/inputs": () =>
        json({
          items: [inputRow()],
          page: { limit: 50, has_more: false, next_cursor: null },
          summary: { total_count: 1 },
          facets: null,
          meta: { section: "inputs", catalog_generation: 1842 },
        }),
      "/api/time-series/catalog/inputs/41": () => json(inputDetail()),
      "/api/time-series/catalog/inputs/41/revisions": () => json(revisionPage()),
      "/api/time-series/catalog/inputs/41/preview": () =>
        json(
          {
            error: {
              code: "TS_PREVIEW_TOO_LARGE",
              message_key: "timeseries.query.refused",
              message: "La consulta del catalogo no es valida.",
              field: null,
              context: { source_point_count: 9000, max_points: 500 },
              details: [],
            },
            request_id: "req_preview",
          },
          422,
        ),
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("row", { name: /Precio de energia/ });
    await user.click(screen.getByRole("button", { name: "Inspeccionar" }));
    await screen.findByRole("region", { name: "Inspector de senal" });
    await user.selectOptions(screen.getByLabelText("Muestreo"), "none");
    await user.click(screen.getByRole("button", { name: "Previsualizar" }));

    const refusal = await screen.findByRole("alert");
    expect(refusal).toHaveTextContent("TS_PREVIEW_TOO_LARGE");
    expect(refusal).toHaveTextContent(
      "El rango pedido supera el limite del preview",
    );
    expect(refusal).toHaveTextContent("req_preview");
    expect(screen.queryByRole("table", { name: "Preview" })).not.toBeInTheDocument();
  });

  it("offers no mutation affordance and never leaves the read verbs", async () => {
    window.history.replaceState({}, "", "/react/time-series/catalog");
    const fetchMock = catalogFetch({
      "/api/time-series/catalog/inputs": () =>
        json({
          items: [inputRow()],
          page: { limit: 50, has_more: false, next_cursor: null },
          summary: { total_count: 1 },
          facets: null,
          meta: { section: "inputs", catalog_generation: 1842 },
        }),
      "/api/time-series/catalog/inputs/41": () => json(inputDetail()),
      "/api/time-series/catalog/inputs/41/revisions": () => json(revisionPage()),
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("row", { name: /Precio de energia/ });
    await user.click(screen.getByRole("button", { name: "Inspeccionar" }));
    await screen.findByRole("region", { name: "Inspector de senal" });

    const surface = screen.getByRole("main");
    for (const control of [
      ...within(surface).getAllByRole("button"),
      ...within(surface).queryAllByRole("link"),
    ]) {
      expect(control.textContent).not.toMatch(
        /asociar|vincular|publicar|guardar|editar|eliminar|archivar|promover/i,
      );
    }
    for (const [, init] of fetchMock.mock.calls) {
      expect((init?.method ?? "GET").toUpperCase()).toBe("GET");
    }
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).includes("/api/auth/csrf"),
      ),
    ).toHaveLength(0);
  });

  it("keeps the filters, names the request and confirms nothing changed on a refusal", async () => {
    window.history.replaceState({}, "", "/react/time-series/catalog");
    const fetchMock = catalogFetch({
      "/api/time-series/catalog/inputs": (url) =>
        url.searchParams.get("q")
          ? json(
              {
                error: {
                  code: "TS_QUERY_INVALID",
                  message_key: "timeseries.query.refused",
                  message: "La consulta del catalogo no es valida.",
                  field: "q",
                  context: { field: "q" },
                  details: [],
                },
                request_id: "req_rejected",
              },
              400,
            )
          : json({
              items: [inputRow()],
              page: { limit: 50, has_more: false, next_cursor: null },
              summary: { total_count: 1 },
              facets: null,
              meta: { section: "inputs", catalog_generation: 1842 },
            }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("row", { name: /Precio de energia/ });
    await user.type(screen.getByLabelText("Buscar"), "precio");
    await user.click(screen.getByRole("button", { name: "Filtrar" }));

    const refusal = await screen.findByRole("alert");
    expect(refusal).toHaveTextContent("TS_QUERY_INVALID");
    expect(refusal).toHaveTextContent("req_rejected");
    expect(refusal).toHaveTextContent("No se modifico nada");
    expect(screen.getByLabelText("Buscar")).toHaveValue("precio");
  });

  it("keeps the pre-cutover behaviour for an internal user outside verification", async () => {
    window.history.replaceState({}, "", "/react/time-series/catalog");
    const fetchMock = catalogFetch({}, REGULAR_IDENTITY);
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "No encontrado" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Catalogo" }),
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).includes("/api/time-series/catalog"),
      ),
    ).toHaveLength(0);
  });

  it("answers an external identity the way it answers a route that is not there", async () => {
    window.history.replaceState({}, "", "/react/time-series/catalog");
    const fetchMock = catalogFetch({}, {
      ...REGULAR_IDENTITY,
      user: {
        ...REGULAR_IDENTITY.user,
        role: "external",
        email: "client@example.local",
      },
      landing_path: "/react/client",
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "No encontrado" }),
    ).toBeVisible();
    expect(screen.getByText("El recurso solicitado no existe.")).toBeVisible();
  });
});
