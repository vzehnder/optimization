import { fireEvent, render, screen, within } from "@testing-library/react";
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
    init?: RequestInit,
  ) => Response | undefined,
) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const method = init?.method || "GET";
      const body = init?.body
        ? (JSON.parse(String(init.body)) as Record<string, unknown>)
        : undefined;
      const handled = handler(path, method, body, init);
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

    const column = await screen.findByRole("group", {
      name: "Columna demanda",
    });
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

    const column = await screen.findByRole("group", {
      name: "Columna demanda",
    });
    await user.selectOptions(
      within(column).getByLabelText("Senal canonica"),
      "hydro_inflow_m3s",
    );
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );

    await vi.waitFor(() => expect(saves).toHaveLength(1));
    const document = (saves[0] as { document: typeof consoleDocument })
      .document;
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

    const column = await screen.findByRole("group", {
      name: "Columna demanda",
    });
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

const editableGroup = {
  id: "potencia",
  label: "Potencia",
  granularities: ["day", "full_horizon"],
  columns: [
    {
      id: "demanda",
      label: "Demanda",
      unit: "MW",
      nonnegative: true,
      editable: true,
    },
  ],
};

function consoleShellPayload() {
  return {
    console: {
      id: 4,
      name: "Plan diario Planta Norte",
      description: "Ajuste diario",
      prepared_by: "Ada Analyst",
      updated_at: "2026-08-23T12:00:00Z",
    },
    period: {
      available_start: "2026-01-01T00:00:00-03:00",
      available_end: "2026-01-01T04:00:00-03:00",
      selected_start: "2026-01-01T00:00:00-03:00",
      selected_end: "2026-01-01T04:00:00-03:00",
    },
    parameters: [],
    groups: [editableGroup],
    run_gate: {
      can_run: true,
      reason: null,
      message: "",
      contact: null,
      editing_locked_by: null,
    },
    history: [],
  };
}

function groupValuesPayload(demand: number[]) {
  return {
    group_values: {
      group_id: "potencia",
      granularity: "day",
      range: {
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T04:00:00-03:00",
      },
      columns: editableGroup.columns,
      rows: demand.map((value, index) => ({
        index,
        timestamp: `2026-01-01T0${index}:00:00-03:00`,
        values: { demanda: value },
      })),
    },
  };
}

const leasePayload = {
  lease: {
    token: "lease-1",
    expires_at: "2026-08-24T10:05:00Z",
    holder_name: "Olga Operadora",
  },
};

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

  it("saves a scalar override before enabling and enqueueing a run", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    const writes: unknown[] = [];
    const runs: unknown[] = [];
    let effectiveValue = 4;
    stubApi(operatorIdentity, (path, method, body) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json({
          console: {
            id: 4,
            name: "Plan diario Planta Norte",
            description: "Ajuste diario",
            prepared_by: "Ada Analyst",
            updated_at: "2026-08-23T12:00:00Z",
          },
          period: {
            available_start: "2026-01-01T00:00:00+00:00",
            available_end: "2026-01-01T03:00:00+00:00",
            selected_start: "2026-01-01T00:00:00+00:00",
            selected_end: "2026-01-01T03:00:00+00:00",
          },
          parameters: [
            {
              id: "potencia_bess",
              label: "Potencia maxima BESS",
              unit: "MW",
              min: 0,
              max: 100,
              default: 40,
              value: effectiveValue,
            },
          ],
          run_gate: {
            can_run: true,
            reason: null,
            message: "",
            contact: null,
            editing_locked_by: null,
          },
        });
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: runs });
      }
      if (path === "/api/console/4/parameters" && method === "PUT") {
        writes.push(body);
        effectiveValue = 6.5;
        return Response.json({
          parameters: [
            {
              id: "potencia_bess",
              label: "Potencia maxima BESS",
              unit: "MW",
              min: 0,
              max: 100,
              default: 40,
              value: effectiveValue,
            },
          ],
        });
      }
      if (path === "/api/console/4/runs" && method === "POST") {
        writes.push(body);
        const run = {
          id: 88,
          started_at: "2026-08-24T10:00:00Z",
          state: "en_espera",
          duration_seconds: null,
          triggered_by: "Olga Operadora",
        };
        runs.splice(0, runs.length, run);
        return Response.json({ run }, { status: 201 });
      }
      if (path === "/api/console/4/runs/88" && method === "GET") {
        return Response.json({
          run: runs[0],
          failure: null,
          results_block: null,
        });
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const parameter = await screen.findByRole("spinbutton", {
      name: "Potencia maxima BESS (MW)",
    });
    const runButton = screen.getByRole("button", { name: "Ejecutar" });
    expect(screen.getByLabelText("Inicio")).toHaveValue("2026-01-01T00:00");
    expect(screen.getByLabelText("Fin")).toHaveValue("2026-01-01T03:00");
    expect(runButton).toBeEnabled();

    await user.clear(parameter);
    await user.type(parameter, "6.5");
    expect(runButton).toBeDisabled();
    await user.click(
      screen.getByRole("button", { name: "Guardar parametros" }),
    );
    await vi.waitFor(() => expect(runButton).toBeEnabled());
    await user.click(runButton);

    expect(await screen.findByText("En espera")).toBeVisible();
    expect(writes).toEqual([
      { parameters: [{ id: "potencia_bess", value: 6.5 }] },
      {
        range_start: "2026-01-01T00:00:00+00:00",
        range_end: "2026-01-01T03:00:00+00:00",
      },
    ]);
  });

  it("opens one completed run and renders its configured result block", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    let detailReads = 0;
    const completed = {
      id: 90,
      started_at: "2026-08-24T10:00:00Z",
      state: "lista",
      duration_seconds: 2.5,
      triggered_by: "Olga Operadora",
    };
    stubApi(operatorIdentity, (path, method) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json({
          console: {
            id: 4,
            name: "Plan diario Planta Norte",
            description: "Ajuste diario",
            prepared_by: "Ada Analyst",
            updated_at: "2026-08-23T12:00:00Z",
          },
          period: {
            available_start: null,
            available_end: null,
            selected_start: null,
            selected_end: null,
          },
          parameters: [],
          run_gate: {
            can_run: false,
            reason: "dependencia_movida",
            message: "Solicita revision.",
            contact: "Ada Analyst",
            editing_locked_by: null,
          },
        });
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: [completed] });
      }
      if (path === "/api/console/4/runs/90" && method === "GET") {
        detailReads += 1;
        return Response.json({
          run: completed,
          failure: null,
          results_block: {
            labels: {
              kpis: "Indicadores",
              charts: "",
              tables: "",
              downloads: "",
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
            charts: [],
            tables: [],
          },
        });
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("button", {
        name: "Abrir resultados de corrida 90",
      }),
    );

    expect(
      await screen.findByRole("heading", { name: "Indicadores" }),
    ).toBeVisible();
    expect(screen.getByText("Beneficio total")).toBeVisible();
    expect(screen.getByText("1250.5")).toBeVisible();
    await new Promise((resolve) => window.setTimeout(resolve, 1100));
    expect(detailReads).toBe(1);
  });

  it("switches a named series source and reloads the table", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    const writes: Array<Record<string, unknown>> = [];
    let selectedSource = "base";
    let demand = [10, 11, 12, 13];
    const optionsPayload = () => ({
      selections: [
        {
          group_id: "potencia",
          column_id: "demanda",
          selected_source_option_id: selectedSource,
          options: [
            { id: "base", label: "Demanda base" },
            { id: "pronostico", label: "Pronostico actualizado" },
          ],
        },
      ],
    });
    stubApi(operatorIdentity, (path, method, body) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json(consoleShellPayload());
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: [] });
      }
      if (path === "/api/console/4/series-options" && method === "GET") {
        return Response.json(optionsPayload());
      }
      if (path === "/api/console/4/series-selections" && method === "PUT") {
        writes.push(body as Record<string, unknown>);
        selectedSource = "pronostico";
        demand = [20, 21, 22, 23];
        return Response.json(optionsPayload());
      }
      if (path.startsWith("/api/console/4/groups/potencia/values")) {
        return Response.json(groupValuesPayload(demand), {
          headers: { ETag: '"token-1"' },
        });
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const source = await screen.findByRole("combobox", {
      name: "Fuente de Demanda",
    });
    expect(source).toHaveValue("base");

    await user.selectOptions(source, "pronostico");

    await vi.waitFor(() => expect(source).toHaveValue("pronostico"));
    expect(writes).toEqual([
      {
        selections: [
          {
            group_id: "potencia",
            column_id: "demanda",
            source_option_id: "pronostico",
          },
        ],
      },
    ]);
    const table = await screen.findByRole("table", { name: "Potencia" });
    await vi.waitFor(() => expect(within(table).getByText("20")).toBeVisible());
  });

  it("edits one exposed series and only then re-enables running", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    const writes: Array<Record<string, unknown>> = [];
    const sentTokens: Array<string | null> = [];
    let demand = [10, 11, 12, 13];
    let token = "token-1";
    stubApi(operatorIdentity, (path, method, body, init) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json(consoleShellPayload());
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: [] });
      }
      if (path.startsWith("/api/console/4/groups/potencia/values")) {
        if (method === "PUT") {
          writes.push(body as Record<string, unknown>);
          sentTokens.push(new Headers(init?.headers).get("if-match"));
          demand = [10, 99.5, 12, 13];
          token = "token-2";
        }
        return Response.json(groupValuesPayload(demand), {
          headers: { ETag: `"${token}"` },
        });
      }
      if (
        path === "/api/console/4/groups/potencia/lease" &&
        method === "POST"
      ) {
        return Response.json(leasePayload);
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    const table = await screen.findByRole("table", { name: "Potencia" });
    expect(
      within(table).getByRole("columnheader", { name: "Demanda (MW)" }),
    ).toBeVisible();
    expect(
      within(table).getByRole("rowheader", {
        name: "2026-01-01T01:00:00-03:00",
      }),
    ).toBeVisible();
    expect(within(table).getByText("11")).toBeVisible();
    expect(
      screen.getByTestId("console-group-series-potencia"),
    ).toHaveTextContent("Demanda");

    const runButton = screen.getByRole("button", { name: "Ejecutar" });
    expect(runButton).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Editar valores" }));
    const cell = await screen.findByRole("spinbutton", {
      name: "Demanda 2026-01-01T01:00:00-03:00",
    });
    await user.clear(cell);
    await user.type(cell, "99.5");
    expect(runButton).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Guardar valores" }));

    await vi.waitFor(() => expect(runButton).toBeEnabled());
    expect(writes).toEqual([
      {
        range_start: "2026-01-01T00:00:00-03:00",
        range_end: "2026-01-01T04:00:00-03:00",
        granularity: "day",
        lease_token: "lease-1",
        note: "",
        cells: [{ column_id: "demanda", row_index: 1, value: 99.5 }],
      },
    ]);
    expect(sentTokens).toEqual(['"token-1"']);
    expect(
      await screen.findByRole("spinbutton", {
        name: "Demanda 2026-01-01T01:00:00-03:00",
      }),
    ).toHaveValue(99.5);
  });

  it("pastes a rectangular block from the anchored cell and normalizes unambiguous numbers", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    const columns = [
      ...editableGroup.columns,
      {
        id: "precio",
        label: "Precio",
        unit: "USD/MWh",
        nonnegative: false,
        editable: true,
      },
    ];
    const group = { ...editableGroup, columns };
    const valuesPayload = {
      group_values: {
        group_id: "potencia",
        granularity: "day",
        range: {
          start: "2026-01-01T00:00:00-03:00",
          end: "2026-01-01T04:00:00-03:00",
        },
        columns,
        rows: [
          {
            index: 0,
            timestamp: "2026-01-01T00:00:00-03:00",
            values: { demanda: 10, precio: 50 },
          },
          {
            index: 1,
            timestamp: "2026-01-01T01:00:00-03:00",
            values: { demanda: 11, precio: 51 },
          },
          {
            index: 2,
            timestamp: "2026-01-01T02:00:00-03:00",
            values: { demanda: 12, precio: 52 },
          },
        ],
      },
    };
    const writes: Array<Record<string, unknown>> = [];
    stubApi(operatorIdentity, (path, method, body) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json({ ...consoleShellPayload(), groups: [group] });
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: [] });
      }
      if (path.startsWith("/api/console/4/groups/potencia/values")) {
        if (method === "PUT") writes.push(body as Record<string, unknown>);
        return Response.json(valuesPayload, { headers: { ETag: '"token-1"' } });
      }
      if (
        path === "/api/console/4/groups/potencia/lease" &&
        method === "POST"
      ) {
        return Response.json(leasePayload);
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("button", { name: "Editar valores" }),
    );
    const anchor = await screen.findByRole("spinbutton", {
      name: "Demanda 2026-01-01T00:00:00-03:00",
    });
    await user.click(anchor);
    await user.paste("1.234,5\t1,234.5\n1234,567\t0,001\n1.234.567\t52.5");
    await user.click(screen.getByRole("button", { name: "Guardar valores" }));

    await vi.waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      cells: [
        { column_id: "demanda", row_index: 0, value: 1234.5 },
        { column_id: "precio", row_index: 0, value: 1234.5 },
        { column_id: "demanda", row_index: 1, value: 1234.567 },
        { column_id: "precio", row_index: 1, value: 0.001 },
        { column_id: "demanda", row_index: 2, value: 1234567 },
        { column_id: "precio", row_index: 2, value: 52.5 },
      ],
    });
  });

  it("rejects structurally ambiguous pasted numbers without staging a partial block", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    const writes: Array<Record<string, unknown>> = [];
    stubApi(operatorIdentity, (path, method, body) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json(consoleShellPayload());
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: [] });
      }
      if (path.startsWith("/api/console/4/groups/potencia/values")) {
        if (method === "PUT") writes.push(body as Record<string, unknown>);
        return Response.json(groupValuesPayload([10, 11, 12, 13]), {
          headers: { ETag: '"token-1"' },
        });
      }
      if (
        path === "/api/console/4/groups/potencia/lease" &&
        method === "POST"
      ) {
        return Response.json(leasePayload);
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("button", { name: "Editar valores" }),
    );
    const anchor = await screen.findByRole("spinbutton", {
      name: "Demanda 2026-01-01T00:00:00-03:00",
    });
    await user.click(anchor);
    await user.paste("1.234\n12,345");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Demanda fila 1");
    expect(alert).toHaveTextContent("Demanda fila 2");
    expect(alert).toHaveTextContent("ambiguo");
    expect(
      screen.getByRole("button", { name: "Guardar valores" }),
    ).toBeDisabled();
    expect(anchor).toHaveValue(10);
    expect(writes).toEqual([]);
  });

  it("skips an accidental header and locked columns while pasting", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    const columns = [
      editableGroup.columns[0],
      {
        id: "precio",
        label: "Precio bloqueado",
        unit: "USD/MWh",
        nonnegative: false,
        editable: false,
      },
      {
        id: "solar",
        label: "Solar",
        unit: "MW",
        nonnegative: true,
        editable: true,
      },
    ];
    const group = { ...editableGroup, columns };
    const valuesPayload = {
      group_values: {
        group_id: "potencia",
        granularity: "day",
        range: {
          start: "2026-01-01T00:00:00-03:00",
          end: "2026-01-01T04:00:00-03:00",
        },
        columns,
        rows: [0, 1].map((index) => ({
          index,
          timestamp: `2026-01-01T0${index}:00:00-03:00`,
          values: { demanda: 10 + index, precio: 50 + index, solar: 5 + index },
        })),
      },
    };
    const writes: Array<Record<string, unknown>> = [];
    stubApi(operatorIdentity, (path, method, body) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json({ ...consoleShellPayload(), groups: [group] });
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: [] });
      }
      if (path.startsWith("/api/console/4/groups/potencia/values")) {
        if (method === "PUT") writes.push(body as Record<string, unknown>);
        return Response.json(valuesPayload, { headers: { ETag: '"token-1"' } });
      }
      if (
        path === "/api/console/4/groups/potencia/lease" &&
        method === "POST"
      ) {
        return Response.json(leasePayload);
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("button", { name: "Editar valores" }),
    );
    const anchor = await screen.findByRole("spinbutton", {
      name: "Demanda 2026-01-01T00:00:00-03:00",
    });
    await user.click(anchor);
    await user.paste("Demanda\tPrecio\tSolar\n100\t200\t300\n101\t201\t301");

    expect(await screen.findByText(/primera fila.*encabezado/i)).toBeVisible();
    expect(screen.getByText(/Precio bloqueado.*omitida/i)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Guardar valores" }));
    await vi.waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      cells: [
        { column_id: "demanda", row_index: 0, value: 100 },
        { column_id: "solar", row_index: 0, value: 300 },
        { column_id: "demanda", row_index: 1, value: 101 },
        { column_id: "solar", row_index: 1, value: 301 },
      ],
    });
  });

  it("truncates paste overflow at the configured range and warns until save", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    const writes: Array<Record<string, unknown>> = [];
    stubApi(operatorIdentity, (path, method, body) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json(consoleShellPayload());
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: [] });
      }
      if (path.startsWith("/api/console/4/groups/potencia/values")) {
        if (method === "PUT") writes.push(body as Record<string, unknown>);
        return Response.json(groupValuesPayload([10, 11, 12, 13]), {
          headers: { ETag: '"token-1"' },
        });
      }
      if (
        path === "/api/console/4/groups/potencia/lease" &&
        method === "POST"
      ) {
        return Response.json(leasePayload);
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("button", { name: "Editar valores" }),
    );
    const anchor = await screen.findByRole("spinbutton", {
      name: "Demanda 2026-01-01T02:00:00-03:00",
    });
    await user.click(anchor);
    await user.paste("100\n101\n102");

    expect(await screen.findByText(/excedente.*truncado/i)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Guardar valores" }));
    await vi.waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      cells: [
        { column_id: "demanda", row_index: 2, value: 100 },
        { column_id: "demanda", row_index: 3, value: 101 },
      ],
    });
    expect(screen.queryByText(/excedente.*truncado/i)).toBeNull();
  });

  it("offers an optional review diff without making it a save prerequisite", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    stubApi(operatorIdentity, (path, method) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json(consoleShellPayload());
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: [] });
      }
      if (path.startsWith("/api/console/4/groups/potencia/values")) {
        return Response.json(groupValuesPayload([10, 11, 12, 13]), {
          headers: { ETag: '"token-1"' },
        });
      }
      if (
        path === "/api/console/4/groups/potencia/lease" &&
        method === "POST"
      ) {
        return Response.json(leasePayload);
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("button", { name: "Editar valores" }),
    );
    const cell = await screen.findByRole("spinbutton", {
      name: "Demanda 2026-01-01T01:00:00-03:00",
    });
    await user.clear(cell);
    await user.type(cell, "99.5");

    expect(
      screen.getByRole("button", { name: "Guardar valores" }),
    ).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Revisar cambios" }));
    const review = await screen.findByRole("dialog", {
      name: "Revision de cambios",
    });
    expect(review).toHaveTextContent("Demanda");
    expect(review).toHaveTextContent("2026-01-01T01:00:00-03:00");
    expect(review).toHaveTextContent("11");
    expect(review).toHaveTextContent("99.5");
  });

  it("virtualizes all 8760 full-horizon rows and can scroll to the last one", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    const fullHorizonGroup = {
      ...editableGroup,
      granularities: ["full_horizon"],
    };
    const rows = Array.from({ length: 8760 }, (_, index) => ({
      index,
      timestamp: `period-${index}`,
      values: { demanda: index },
    }));
    stubApi(operatorIdentity, (path, method) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json({
          ...consoleShellPayload(),
          groups: [fullHorizonGroup],
        });
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: [] });
      }
      if (path.startsWith("/api/console/4/groups/potencia/values")) {
        return Response.json(
          {
            group_values: {
              group_id: "potencia",
              granularity: "full_horizon",
              range: {
                start: "2026-01-01T00:00:00-03:00",
                end: "2027-01-01T00:00:00-03:00",
              },
              columns: fullHorizonGroup.columns,
              rows,
            },
          },
          { headers: { ETag: '"token-full"' } },
        );
      }
      return undefined;
    });

    render(<App />);

    const table = await screen.findByRole("table", { name: "Potencia" });
    const viewport = await screen.findByTestId(
      "console-group-table-viewport-potencia",
    );
    expect(within(table).getAllByRole("row").length).toBeLessThan(200);
    expect(
      within(table).getByRole("rowheader", { name: "period-0" }),
    ).toBeVisible();
    expect(
      within(table).queryByRole("rowheader", { name: "period-8759" }),
    ).toBeNull();

    fireEvent.scroll(viewport, { target: { scrollTop: 8760 * 42 } });

    expect(
      await within(table).findByRole("rowheader", { name: "period-8759" }),
    ).toBeVisible();
  });

  it("names the cells a refused save rejected and keeps running disabled", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    stubApi(operatorIdentity, (path, method) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json(consoleShellPayload());
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: [] });
      }
      if (path.startsWith("/api/console/4/groups/potencia/values")) {
        if (method === "GET") {
          return Response.json(groupValuesPayload([10, 11, 12, 13]), {
            headers: { ETag: '"token-1"' },
          });
        }
        return Response.json(
          {
            save_error: {
              message: "el bloque tiene celdas invalidas y no se guardo nada",
              cells: [
                {
                  group_id: "potencia",
                  column_id: "demanda",
                  row_index: 1,
                  message: "el valor no admite negativos",
                },
              ],
              total_cells: 1,
              shown_cells: 1,
            },
          },
          { status: 400 },
        );
      }
      if (
        path === "/api/console/4/groups/potencia/lease" &&
        method === "POST"
      ) {
        return Response.json(leasePayload);
      }
      return undefined;
    });
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("button", { name: "Editar valores" }),
    );
    const cell = await screen.findByRole("spinbutton", {
      name: "Demanda 2026-01-01T01:00:00-03:00",
    });
    await user.clear(cell);
    await user.type(cell, "-3");
    await user.click(screen.getByRole("button", { name: "Guardar valores" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Demanda");
    expect(alert).toHaveTextContent("fila 2");
    expect(alert).toHaveTextContent("el valor no admite negativos");
    expect(screen.getByRole("button", { name: "Ejecutar" })).toBeDisabled();
  });

  it("keeps the table read-only while another operator holds the lock", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    stubApi(operatorIdentity, (path, method) => {
      if (path === "/api/console/4" && method === "GET") {
        return Response.json({
          ...consoleShellPayload(),
          run_gate: {
            can_run: false,
            reason: "edicion_de_otro_usuario",
            message: "Otro Operador esta editando este grupo.",
            contact: null,
            editing_locked_by: "Otro Operador",
          },
        });
      }
      if (path === "/api/console/4/runs" && method === "GET") {
        return Response.json({ history: [] });
      }
      if (path.startsWith("/api/console/4/groups/potencia/values")) {
        return Response.json(groupValuesPayload([10, 11, 12, 13]), {
          headers: { ETag: '"token-1"' },
        });
      }
      return undefined;
    });

    render(<App />);

    expect(
      await screen.findByText(
        "Solo lectura: Otro Operador tiene la edicion de este grupo.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText("Otro Operador esta editando este grupo."),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Editar valores" })).toBeNull();
    expect(screen.queryByRole("spinbutton")).toBeNull();
    expect(screen.getByRole("button", { name: "Ejecutar" })).toBeDisabled();
  });
});
