import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

const emptyConfiguration = {
  portal_configuration: {
    project_id: 1,
    status: "draft",
    document: {
      schema_version: "portal_config.v1",
      display_name: "",
      sections: {
        kpis: { enabled: false, label: "Resumen", items: [] },
        charts: { enabled: false, label: "Resultados", items: [] },
        tables: { enabled: false, label: "Detalle", items: [] },
        downloads: { enabled: false, label: "Descargas" },
      },
    },
    revision: 0,
    has_logo: false,
    updated_at: null,
    updated_by: null,
  },
};

const portalCatalogs = {
  charts: [
    {
      key: "grid_import_export",
      label: "Intercambio con la red",
      series: [
        { key: "grid_import_mw", label: "Grid import mw", unit: "MW" },
        { key: "grid_export_mw", label: "Grid export mw", unit: "MW" },
      ],
    },
    {
      key: "period_profit",
      label: "Beneficio por periodo",
      series: [
        { key: "period_profit_usd", label: "Period profit usd", unit: "USD" },
      ],
    },
  ],
  tables: [
    {
      key: "system_dispatch",
      label: "Despacho del sistema",
      columns: [
        { key: "timestamp", label: "Timestamp", unit: null },
        { key: "grid_import_mw", label: "Grid import mw", unit: "MW" },
      ],
    },
  ],
};

function stubProjectWorkspace(
  handler: (
    path: string,
    method: string,
    body: unknown,
  ) => Response | undefined = () => undefined,
) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const method = init?.method || "GET";
      const body =
        init?.body instanceof FormData
          ? init.body
          : init?.body
            ? JSON.parse(String(init.body))
            : undefined;
      const handled = handler(path, method, body);
      if (handled) return handled;
      if (path === "/api/auth/me") {
        return Response.json({
          user: {
            id: 1,
            email: "analyst@example.local",
            display_name: "Analyst",
            role: "analyst",
            is_active: true,
          },
          bootstrap_required: false,
        });
      }
      if (path === "/api/auth/csrf") {
        return Response.json({ csrf_token: "test-token" });
      }
      if (path === "/api/projects/1") {
        return Response.json({
          project: {
            id: 1,
            name: "Hybrid PMGD",
            description: "",
            created_at: "",
            created_by: "",
          },
        });
      }
      if (path === "/api/projects/1/scenarios") {
        return Response.json({ scenarios: [] });
      }
      if (path === "/api/projects/1/dashboard-templates") {
        return Response.json({ dashboard_templates: [] });
      }
      if (path === "/api/projects/1/portal-configuration") {
        return Response.json(emptyConfiguration);
      }
      if (path === "/api/portal-catalogs") {
        return Response.json(portalCatalogs);
      }
      return Response.json(
        { detail: `unhandled ${method} ${path}` },
        { status: 500 },
      );
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("portal configuration workspace", () => {
  it("lets an analyst upload a PNG logo at the current revision", async () => {
    window.history.replaceState({}, "", "/react/projects/1");
    const uploads: FormData[] = [];
    stubProjectWorkspace((path, method, body) => {
      if (
        path === "/api/projects/1/portal-configuration/logo" &&
        method === "PUT" &&
        body instanceof FormData
      ) {
        uploads.push(body);
        return Response.json({
          portal_configuration: {
            ...emptyConfiguration.portal_configuration,
            revision: 1,
            has_logo: true,
            updated_by: "analyst@example.local",
          },
        });
      }
      return undefined;
    });
    const user = userEvent.setup();
    const logo = new File(["png-bytes"], "cliente.png", {
      type: "image/png",
    });

    render(<App />);

    const section = await screen.findByRole("region", {
      name: "Portal del cliente",
    });
    await user.upload(
      await within(section).findByLabelText("Logo del portal"),
      logo,
    );
    await user.click(
      within(section).getByRole("button", { name: "Subir logo" }),
    );

    expect(await within(section).findByText("Logo configurado")).toBeVisible();
    expect(uploads).toHaveLength(1);
    expect(uploads[0].get("expected_revision")).toBe("0");
    expect(uploads[0].get("logo")).toEqual(logo);
  });

  it("lets an analyst remove the current logo at the current revision", async () => {
    window.history.replaceState({}, "", "/react/projects/1");
    const removals: unknown[] = [];
    stubProjectWorkspace((path, method, body) => {
      if (path === "/api/projects/1/portal-configuration" && method === "GET") {
        return Response.json({
          portal_configuration: {
            ...emptyConfiguration.portal_configuration,
            revision: 3,
            has_logo: true,
          },
        });
      }
      if (
        path === "/api/projects/1/portal-configuration/logo" &&
        method === "DELETE"
      ) {
        removals.push(body);
        return Response.json({
          portal_configuration: {
            ...emptyConfiguration.portal_configuration,
            revision: 4,
            has_logo: false,
          },
        });
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const section = await screen.findByRole("region", {
      name: "Portal del cliente",
    });
    await user.click(
      await within(section).findByRole("button", { name: "Quitar logo" }),
    );

    expect(await within(section).findByText("Sin logo")).toBeVisible();
    expect(removals).toEqual([{ expected_revision: 3 }]);
  });

  it("lets an analyst declare a display name, a KPI label and one KPI", async () => {
    window.history.replaceState({}, "", "/react/projects/1");
    const saved: unknown[] = [];
    stubProjectWorkspace((path, method, body) => {
      if (path === "/api/projects/1/portal-configuration" && method === "PUT") {
        saved.push(body);
        return Response.json({
          portal_configuration: {
            ...emptyConfiguration.portal_configuration,
            status: "active",
            revision: 1,
            updated_by: "analyst@example.local",
          },
        });
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const section = await screen.findByRole("region", {
      name: "Portal del cliente",
    });
    await within(section).findByLabelText("Nombre publico");
    await user.type(
      within(section).getByLabelText("Nombre publico"),
      "Plan operativo Cliente Norte",
    );
    await user.click(within(section).getByLabelText("Mostrar KPIs"));
    await user.clear(
      within(section).getByLabelText("Titulo de la seccion KPI"),
    );
    await user.type(
      within(section).getByLabelText("Titulo de la seccion KPI"),
      "Resumen",
    );
    await user.click(
      within(section).getByRole("button", { name: "Agregar KPI" }),
    );
    await user.type(
      within(section).getByLabelText("Id publico"),
      "beneficio_total",
    );
    await user.type(
      within(section).getByLabelText("Ruta canonica"),
      "objective_value_usd",
    );
    await user.type(
      within(section).getByLabelText("Etiqueta publica"),
      "Beneficio total",
    );
    await user.type(within(section).getByLabelText("Unidad"), "USD");
    await user.selectOptions(
      within(section).getByLabelText("Estado"),
      "active",
    );
    await user.click(
      within(section).getByRole("button", { name: "Guardar portal" }),
    );

    expect(await screen.findByText("Revision 1")).toBeVisible();
    expect(saved).toEqual([
      {
        status: "active",
        expected_revision: 0,
        document: {
          schema_version: "portal_config.v1",
          display_name: "Plan operativo Cliente Norte",
          sections: {
            kpis: {
              enabled: true,
              label: "Resumen",
              items: [
                {
                  id: "beneficio_total",
                  path: "objective_value_usd",
                  label: "Beneficio total",
                  unit: "USD",
                  decimals: 0,
                  sign: "auto",
                  emphasis: "normal",
                },
              ],
            },
            charts: { enabled: false, label: "Resultados", items: [] },
            tables: { enabled: false, label: "Detalle", items: [] },
            downloads: { enabled: false, label: "Descargas" },
          },
        },
      },
    ]);
  });

  it("surfaces a rejected document without clearing the analyst's edits", async () => {
    window.history.replaceState({}, "", "/react/projects/1");
    stubProjectWorkspace((path, method) => {
      if (path === "/api/projects/1/portal-configuration" && method === "PUT") {
        return Response.json(
          {
            detail:
              "sections.kpis.items[0].id is not a valid id: 'beneficio total'",
          },
          { status: 400 },
        );
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const section = await screen.findByRole("region", {
      name: "Portal del cliente",
    });
    await within(section).findByLabelText("Nombre publico");
    await user.type(
      within(section).getByLabelText("Nombre publico"),
      "Plan operativo",
    );
    await user.click(
      within(section).getByRole("button", { name: "Guardar portal" }),
    );

    expect(await within(section).findByRole("alert")).toHaveTextContent(
      "is not a valid id",
    );
    expect(within(section).getByLabelText("Nombre publico")).toHaveValue(
      "Plan operativo",
    );
  });

  it("lets an analyst publish a chart, a table and the downloads from the catalog", async () => {
    window.history.replaceState({}, "", "/react/projects/1");
    const saved: unknown[] = [];
    stubProjectWorkspace((path, method, body) => {
      if (path === "/api/projects/1/portal-configuration" && method === "PUT") {
        saved.push(body);
        return Response.json({
          portal_configuration: {
            ...emptyConfiguration.portal_configuration,
            status: "active",
            revision: 1,
            updated_by: "analyst@example.local",
          },
        });
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const section = await screen.findByRole("region", {
      name: "Portal del cliente",
    });
    await within(section).findByLabelText("Nombre publico");

    await user.click(within(section).getByLabelText("Mostrar graficos"));
    await user.selectOptions(
      within(section).getByLabelText("Grafico del catalogo"),
      "grid_import_export",
    );
    await user.click(
      within(section).getByRole("button", { name: "Agregar grafico" }),
    );
    const chart = within(section).getByTestId(
      "portal-chart-item-grid_import_export",
    );
    await user.clear(within(chart).getByLabelText("Etiqueta publica"));
    await user.type(
      within(chart).getByLabelText("Etiqueta publica"),
      "Intercambio",
    );
    const series = within(chart).getByTestId("portal-series-grid_export_mw");
    await user.clear(within(series).getByLabelText("Etiqueta de la serie"));
    await user.type(
      within(series).getByLabelText("Etiqueta de la serie"),
      "Venta",
    );

    await user.click(within(section).getByLabelText("Mostrar tablas"));
    await user.selectOptions(
      within(section).getByLabelText("Tabla del catalogo"),
      "system_dispatch",
    );
    await user.click(
      within(section).getByRole("button", { name: "Agregar tabla" }),
    );
    const table = within(section).getByTestId(
      "portal-table-item-system_dispatch",
    );
    await user.clear(within(table).getByLabelText("Filas visibles"));
    await user.type(within(table).getByLabelText("Filas visibles"), "24");
    await user.selectOptions(
      within(table).getByLabelText("Columna del catalogo"),
      "grid_import_mw",
    );
    await user.click(
      within(table).getByRole("button", { name: "Agregar columna" }),
    );

    await user.click(within(section).getByLabelText("Mostrar descargas"));
    await user.selectOptions(
      within(section).getByLabelText("Estado"),
      "active",
    );
    await user.click(
      within(section).getByRole("button", { name: "Guardar portal" }),
    );

    expect(await screen.findByText("Revision 1")).toBeVisible();
    expect(saved).toHaveLength(1);
    const document = (saved[0] as { document: { sections: unknown } }).document;
    expect(document.sections).toEqual({
      kpis: { enabled: false, label: "Resumen", items: [] },
      charts: {
        enabled: true,
        label: "Resultados",
        items: [
          {
            id: "grid_import_export",
            chart_key: "grid_import_export",
            label: "Intercambio",
            series: [
              { key: "grid_import_mw", label: "Grid import mw" },
              { key: "grid_export_mw", label: "Venta" },
            ],
          },
        ],
      },
      tables: {
        enabled: true,
        label: "Detalle",
        items: [
          {
            id: "system_dispatch",
            table_key: "system_dispatch",
            label: "Despacho del sistema",
            row_limit: 24,
            columns: [
              {
                key: "grid_import_mw",
                id: "grid_import_mw",
                label: "Grid import mw",
                unit: "MW",
              },
            ],
          },
        ],
      },
      downloads: { enabled: true, label: "Descargas" },
    });
  });

  it("never offers a chart or column outside the backend catalog", async () => {
    window.history.replaceState({}, "", "/react/projects/1");
    stubProjectWorkspace();
    const user = userEvent.setup();

    render(<App />);

    const section = await screen.findByRole("region", {
      name: "Portal del cliente",
    });
    await within(section).findByLabelText("Nombre publico");
    await user.click(within(section).getByLabelText("Mostrar graficos"));

    const options = within(section)
      .getAllByRole("option")
      .map((option) => (option as HTMLOptionElement).value);
    expect(options).toContain("grid_import_export");
    expect(options).not.toContain("all_series");
    expect(options).not.toContain("plot_series");
  });
});
