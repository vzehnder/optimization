import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

const consoleDocument = {
  schema_version: "operator_console_config.v1",
  public_identity: {
    name: "Plan diario Planta Norte",
    description: "Ajuste de disponibilidad y corrida diaria",
  },
  parameters: [],
  groups: [
    {
      id: "potencia",
      label: "Potencia",
      granularities: ["day", "full_horizon"],
      columns: [
        {
          id: "demanda",
          signal: {
            entity_type: "component:load",
            entity_id: "load_1",
            signal_key: "load_demand_mw",
          },
          label: "Demanda",
          editable: true,
          source_options: [
            { id: "base", label: "Demanda base", time_series_set_id: 5 },
          ],
          default_source_option_id: "base",
        },
      ],
    },
  ],
  results: { kpis: [], charts: [], tables: [] },
};

const draftConsole = {
  id: 4,
  scenario_id: 10,
  case_id: 1,
  status: "draft",
  revision: 1,
  document: consoleDocument,
  owned_variant: { id: 9, display_name: "Consola Plan diario Planta Norte" },
  prepared_by: "ada@example.local",
  created_at: "2026-08-23T12:00:00Z",
  created_by: "ada@example.local",
  updated_at: "2026-08-23T12:00:00Z",
  updated_by: "ada@example.local",
  waiting_since: null,
  blocking: { reason: null, reasons: [] },
};

const analystIdentity = {
  id: 7,
  email: "ada@example.local",
  display_name: "Ada Analyst",
  role: "analyst",
  is_active: true,
};

const operatorIdentity = {
  id: 12,
  email: "olga@example.local",
  display_name: "Olga Operadora",
  role: "external",
  is_active: true,
};

function stubApi(
  identity: typeof analystIdentity,
  handler: (
    path: string,
    method: string,
    body: Record<string, unknown> | undefined,
  ) => Response | undefined,
) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const method = init?.method || "GET";
      const body = init?.body
        ? (JSON.parse(String(init.body)) as Record<string, unknown>)
        : undefined;
      const handled = handler(path, method, body);
      if (handled) return handled;
      if (path === "/api/auth/me") {
        return Response.json({ user: identity, bootstrap_required: false });
      }
      if (path === "/api/auth/csrf") {
        return Response.json({ csrf_token: "csrf-token" });
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

const signalCatalog = [
  {
    signal_key: "price_usd_per_mwh",
    unit: "USD/MWh",
    entity_type: null,
    nonnegative: false,
  },
  {
    signal_key: "load_demand_mw",
    unit: "MW",
    entity_type: "component:load",
    nonnegative: true,
  },
  {
    signal_key: "hydro_inflow_m3s",
    unit: "m3/s",
    entity_type: "component:hydro",
    nonnegative: true,
  },
];

function stubScenarioWorkspace(
  handler: (
    path: string,
    method: string,
    body: Record<string, unknown> | undefined,
  ) => Response | undefined = () => undefined,
) {
  return stubApi(analystIdentity, (path, method, body) => {
    const handled = handler(path, method, body);
    if (handled) return handled;
    if (path === "/api/scenarios/10") {
      return Response.json({
        scenario: {
          id: 10,
          project_id: 1,
          name: "Operacion diaria",
          description: "",
          created_at: "2026-08-23T12:00:00Z",
          created_by: "ada@example.local",
        },
      });
    }
    if (path === "/api/projects/1") {
      return Response.json({
        project: {
          id: 1,
          name: "Planta Norte",
          description: "",
          created_at: "2026-08-23T12:00:00Z",
          created_by: "ada@example.local",
        },
      });
    }
    if (path === "/api/time-series/signal-catalog") {
      return Response.json({ signals: signalCatalog });
    }
    if (path === "/api/scenarios/10/versions") {
      return Response.json({ versions: [] });
    }
    if (path === "/api/scenarios/10/runs") {
      return Response.json({ runs: [] });
    }
    if (path === "/api/projects/1/time-series-sets") {
      return Response.json({ time_series_sets: [] });
    }
    if (path === "/api/scenarios/10/case/variants") {
      return Response.json({
        case: {
          id: 1,
          scenario_id: 10,
          case_key: "scenario_10_case",
          display_name: "Base case",
          updated_at: "2026-08-23T12:00:00Z",
        },
        default_variant_id: 3,
        variants: [
          {
            variant: {
              id: 3,
              case_id: 1,
              variant_key: "default",
              display_name: "Default",
              is_default: true,
              created_at: "2026-08-23T12:00:00Z",
              updated_at: "2026-08-23T12:00:00Z",
            },
            bindings: [],
            required_signals: [],
            staleness: { validated: false, stale: false, reasons: [] },
          },
        ],
      });
    }
    return undefined;
  });
}

describe("operator consoles in the scenario workspace", () => {
  it("creates a draft console from a chosen source variant", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    const created: unknown[] = [];
    let consoles: unknown[] = [];
    stubScenarioWorkspace((path, method, body) => {
      if (path === "/api/scenarios/10/consoles" && method === "GET") {
        return Response.json({ operator_consoles: consoles });
      }
      if (path === "/api/scenarios/10/consoles" && method === "POST") {
        created.push(body);
        consoles = [draftConsole];
        return Response.json(
          { operator_console: draftConsole },
          { status: 201 },
        );
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const section = await screen.findByRole("region", {
      name: "Consolas de operador",
    });
    await user.type(
      within(section).getByLabelText("Nombre de la consola"),
      "Plan diario Planta Norte",
    );
    await user.click(
      within(section).getByRole("button", { name: "Crear consola" }),
    );

    expect(
      await within(section).findByText("Plan diario Planta Norte"),
    ).toBeVisible();
    expect(created).toEqual([
      {
        source_variant_id: 3,
        document: {
          ...consoleDocument,
          public_identity: {
            name: "Plan diario Planta Norte",
            description: "",
          },
          groups: [],
        },
      },
    ]);
  });

  it("shows the console state and links to configure and to test it", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    stubScenarioWorkspace((path, method) => {
      if (path === "/api/scenarios/10/consoles" && method === "GET") {
        return Response.json({ operator_consoles: [draftConsole] });
      }
      return undefined;
    });

    render(<App />);

    const section = await screen.findByRole("region", {
      name: "Consolas de operador",
    });
    const row = await within(section).findByRole("row", {
      name: /Plan diario Planta Norte/,
    });
    expect(within(row).getByText("Borrador")).toBeVisible();
    expect(
      within(row).getByRole("link", { name: "Configurar" }),
    ).toHaveAttribute("href", "/react/scenarios/10/consoles/4");
    expect(within(row).getByRole("link", { name: "Probar" })).toHaveAttribute(
      "href",
      "/react/console/4",
    );
  });

  it("activates a console at its current revision from the configuration editor", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/consoles/4");
    const saves: unknown[] = [];
    stubScenarioWorkspace((path, method, body) => {
      if (path === "/api/scenarios/10/consoles/4" && method === "GET") {
        return Response.json({ operator_console: draftConsole });
      }
      if (path === "/api/scenarios/10/consoles/4" && method === "PUT") {
        saves.push(body);
        return Response.json({
          operator_console: {
            ...draftConsole,
            status: "active",
            revision: 2,
          },
        });
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const editor = await screen.findByRole("region", {
      name: "Configuracion de la consola",
    });
    await user.click(within(editor).getByRole("button", { name: "Activar" }));

    expect(await within(editor).findByText("Activa")).toBeVisible();
    expect(saves).toEqual([
      { document: consoleDocument, status: "active", expected_revision: 1 },
    ]);
  });

  it("reports a stale revision without pretending the console was saved", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/consoles/4");
    stubScenarioWorkspace((path, method) => {
      if (path === "/api/scenarios/10/consoles/4" && method === "GET") {
        return Response.json({ operator_console: draftConsole });
      }
      if (path === "/api/scenarios/10/consoles/4" && method === "PUT") {
        return Response.json(
          { detail: "stale operator console revision" },
          { status: 409 },
        );
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const editor = await screen.findByRole("region", {
      name: "Configuracion de la consola",
    });
    await user.click(within(editor).getByRole("button", { name: "Activar" }));

    expect(await within(editor).findByRole("alert")).toHaveTextContent(
      "stale operator console revision",
    );
    expect(within(editor).getByText("Borrador")).toBeVisible();
  });
});

describe("the console configuration editor and the canonical signal catalog", () => {
  function stubEditor(
    handler: (
      path: string,
      method: string,
      body: Record<string, unknown> | undefined,
    ) => Response | undefined = () => undefined,
  ) {
    window.history.replaceState({}, "", "/react/scenarios/10/consoles/4");
    return stubScenarioWorkspace((path, method, body) => {
      const handled = handler(path, method, body);
      if (handled) return handled;
      if (path === "/api/scenarios/10/consoles/4" && method === "GET") {
        return Response.json({ operator_console: draftConsole });
      }
      return undefined;
    });
  }

  it("presents column choices, units and nonnegative rules from the catalog", async () => {
    stubEditor();

    render(<App />);

    const column = await screen.findByRole("group", { name: "Columna demanda" });
    const signal = within(column).getByLabelText("Senal canonica");
    expect(
      Array.from(signal.querySelectorAll("option")).map(
        (option) => option.textContent,
      ),
    ).toEqual([
      "price_usd_per_mwh (USD/MWh)",
      "load_demand_mw (MW)",
      "hydro_inflow_m3s (m3/s)",
    ]);
    expect(signal).toHaveValue("load_demand_mw");
    expect(
      within(column).getByText("Unidad MW. No admite valores negativos."),
    ).toBeVisible();
  });

  it("takes the entity type of a chosen signal from the catalog", async () => {
    const saves: unknown[] = [];
    stubEditor((path, method, body) => {
      if (path === "/api/scenarios/10/consoles/4" && method === "PUT") {
        saves.push(body);
        return Response.json({
          operator_console: { ...draftConsole, revision: 2 },
        });
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const column = await screen.findByRole("group", { name: "Columna demanda" });
    await user.selectOptions(
      within(column).getByLabelText("Senal canonica"),
      "hydro_inflow_m3s",
    );
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );

    await vi.waitFor(() => expect(saves).toHaveLength(1));
    const document = (saves[0] as { document: typeof consoleDocument }).document;
    expect(document.groups[0].columns[0].signal).toEqual({
      entity_type: "component:hydro",
      entity_id: "load_1",
      signal_key: "hydro_inflow_m3s",
    });
  });

  it("offers a newly declared catalog signal without any editor change", async () => {
    stubEditor((path) => {
      if (path === "/api/time-series/signal-catalog") {
        return Response.json({
          signals: [
            ...signalCatalog,
            {
              signal_key: "load_reactive_power_mvar",
              unit: "MVAr",
              entity_type: "component:load",
              nonnegative: false,
            },
          ],
        });
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const column = await screen.findByRole("group", { name: "Columna demanda" });
    await user.selectOptions(
      within(column).getByLabelText("Senal canonica"),
      "load_reactive_power_mvar",
    );

    expect(within(column).getByLabelText("Senal canonica")).toHaveValue(
      "load_reactive_power_mvar",
    );
    expect(
      within(column).getByText("Unidad MVAr. Admite valores negativos."),
    ).toBeVisible();
  });

  it("refuses to save a column signal the catalog does not declare", async () => {
    const saves: unknown[] = [];
    stubEditor((path, method, body) => {
      if (path === "/api/scenarios/10/consoles/4" && method === "GET") {
        return Response.json({
          operator_console: {
            ...draftConsole,
            document: {
              ...consoleDocument,
              groups: [
                {
                  ...consoleDocument.groups[0],
                  columns: [
                    {
                      ...consoleDocument.groups[0].columns[0],
                      signal: {
                        entity_type: "component:load",
                        entity_id: "load_1",
                        signal_key: "load_retired_mw",
                      },
                    },
                  ],
                },
              ],
            },
          },
        });
      }
      if (path === "/api/scenarios/10/consoles/4" && method === "PUT") {
        saves.push(body);
        return Response.json({ operator_console: draftConsole });
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const editor = await screen.findByRole("region", {
      name: "Configuracion de la consola",
    });
    await user.click(
      within(editor).getByRole("button", { name: "Guardar configuracion" }),
    );

    expect(await within(editor).findByRole("alert")).toHaveTextContent(
      "load_retired_mw",
    );
    expect(saves).toEqual([]);
  });
});

describe("the operator console shell", () => {
  it("lists the operator's consoles across projects and opens one", async () => {
    window.history.replaceState({}, "", "/react/console");
    stubApi(operatorIdentity, (path) => {
      if (path === "/api/console") {
        return Response.json({
          consoles: [
            {
              console: {
                id: 4,
                name: "Plan diario Planta Norte",
                description: "Ajuste diario",
              },
              project: { name: "Planta Norte" },
              state: "active",
            },
          ],
        });
      }
      if (path === "/api/console/4") {
        return Response.json({
          console: {
            id: 4,
            name: "Plan diario Planta Norte",
            description: "Ajuste diario",
            prepared_by: "Ada Analyst",
            updated_at: "2026-08-23T12:00:00Z",
          },
        });
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("link", { name: "Plan diario Planta Norte" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Plan diario Planta Norte" }),
    ).toBeVisible();
    expect(screen.getByText("Preparado por Ada Analyst")).toBeVisible();
    expect(screen.queryByRole("link", { name: "Analista" })).toBeNull();
  });

  it("shows an internal tester their real identity and the way back", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    stubApi(analystIdentity, (path) => {
      if (path === "/api/console/4") {
        return Response.json({
          console: {
            id: 4,
            name: "Plan diario Planta Norte",
            description: "Ajuste diario",
            prepared_by: "Ada Analyst",
            updated_at: "2026-08-23T12:00:00Z",
          },
          internal_test: {
            return_path: "/scenarios/10/consoles/4",
            tester: "ada@example.local",
          },
        });
      }
      return undefined;
    });

    render(<App />);

    const strip = await screen.findByRole("status", {
      name: "Prueba interna",
    });
    expect(strip).toHaveTextContent("ada@example.local");
    expect(
      within(strip).getByRole("link", { name: "Volver al workspace" }),
    ).toHaveAttribute("href", "/react/scenarios/10/consoles/4");
  });
});
