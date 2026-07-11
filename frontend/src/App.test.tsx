import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { AdminUser } from "./api/client";

// Select a diagram node on the canvas so the contextual properties panel
// renders its editors (pointer down + up focuses without moving it).
function selectDiagramNode(technicalKey: string) {
  const node = screen.getByTestId(`hydraulic-canvas-node-${technicalKey}`);
  fireEvent.pointerDown(node, {
    button: 0,
    clientX: 12,
    clientY: 12,
    pointerId: 1,
  });
  fireEvent.pointerUp(node, { clientX: 12, clientY: 12, pointerId: 1 });
}

describe("application shell", () => {
  it("renders succeeded run results with Plotly charts, bounded tables, and safe artifacts", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const version = {
      id: 41,
      scenario_id: 10,
      version_number: 3,
      case_name: "dispatch_case",
      schema_version: "bess_system_dispatch.v2",
      period_count: 2,
      asset_counts: { battery: 1, hydro: 1 },
      created_at: "2026-06-23T12:14:00Z",
      system_case_json: { case_name: "dispatch_case" },
      validation_payload: { status: "ok" },
      generation_metadata: {},
    };
    const run = {
      id: 99,
      scenario_version_id: 41,
      status: "succeeded",
      created_at: "2026-06-23T12:15:00Z",
      started_at: "2026-06-23T12:15:01Z",
      finished_at: "2026-06-23T12:15:03Z",
      duration_seconds: 2,
      exit_code: 0,
      error_message: "",
      stdout: "",
      stderr: "",
      trigger_type: "manual",
      triggered_by: "internal_analyst",
    };
    const results = {
      summary: {
        case_name: "hybrid_system",
        solver_name: "HiGHS",
        solver_status: "OPTIMAL",
        termination_status: "OPTIMAL",
        objective_value_usd: 1250.5,
        total_market_value_usd: 1500,
        hydro_totals: {
          total_hydro_generation_mwh: 5,
        },
      },
      dispatch_table: {
        columns: [
          "timestamp",
          "price_usd_per_mwh",
          "grid_import_mw",
          "grid_export_mw",
          "renewable_used_mw",
          "battery_energy_mwh",
          "period_profit_usd",
        ],
        rows: [
          {
            timestamp: "2026-01-01T00:00:00",
            price_usd_per_mwh: "45.0",
            grid_import_mw: "2.5",
            grid_export_mw: "0.0",
            renewable_used_mw: "4.0",
            battery_energy_mwh: "20.0",
            period_profit_usd: "-112.5",
          },
        ],
      },
      asset_dispatch_table: {
        columns: [
          "timestamp",
          "asset_id",
          "asset_type",
          "grid_import_mw",
          "battery_energy_mwh",
        ],
        rows: [
          {
            timestamp: "2026-01-01T00:00:00",
            asset_id: "grid_1",
            asset_type: "grid",
            grid_import_mw: "2.5",
            battery_energy_mwh: "0.0",
          },
        ],
      },
      charts: {
        price: {
          id: "price",
          title: "Energy Price",
          available: true,
          labels: ["2026-01-01T00:00:00"],
          series: [
            {
              key: "price_usd_per_mwh",
              label: "Price USD/MWh",
              unit: "USD/MWh",
              values: [45],
            },
          ],
          missing_columns: [],
          message: "",
        },
        grid_import_export: {
          id: "grid-import-export",
          title: "Grid Import / Export",
          available: true,
          labels: ["2026-01-01T00:00:00"],
          series: [
            {
              key: "grid_import_mw",
              label: "Grid Import MW",
              unit: "MW",
              values: [2.5],
            },
          ],
          missing_columns: [],
          message: "",
        },
        hydro_power: {
          id: "hydro-power",
          title: "Hydro Power",
          available: false,
          labels: [],
          series: [],
          missing_columns: ["total_hydro_power_mw"],
          message: "Missing columns: total_hydro_power_mw",
        },
      },
      plot_series: [],
    };
    const artifacts = [
      {
        id: 11,
        run_id: 99,
        artifact_type: "summary_json",
        path: "safe/artifacts/runs/99/outputs/summary.json",
        display_name: "summary.json",
        media_type: "application/json",
        byte_size: 92,
        created_at: "2026-06-23T12:15:03Z",
        download_url: "/api/run-artifacts/11/download",
      },
    ];
    const plotlyMock = {
      react: vi.fn().mockResolvedValue(undefined),
      purge: vi.fn(),
    };
    vi.stubGlobal("Plotly", plotlyMock);
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/runs/99") {
          return new Response(JSON.stringify({ run }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/runs/99/results") {
          return new Response(JSON.stringify({ results }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/runs/99/artifacts") {
          return new Response(JSON.stringify({ artifacts }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenario-versions/41" && method === "GET") {
          return new Response(JSON.stringify({ scenario_version: version }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects") {
          return new Response(JSON.stringify({ projects: [project] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Run Results" }),
    ).toBeVisible();
    expect(await screen.findByText("hybrid_system")).toBeVisible();
    expect(screen.getByText("Nombre del caso")).toBeVisible();
    expect(screen.queryByText("Case Name")).not.toBeInTheDocument();
    expect(screen.getByText("1250.5")).toBeVisible();
    expect(screen.getByText("total_market_value_usd")).toBeVisible();
    expect(screen.getByText("total_hydro_generation_mwh")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "System Dispatch" }),
    ).toBeVisible();
    expect(screen.getAllByText("grid_import_mw").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2.5").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("heading", { name: "Asset Dispatch" }),
    ).toBeVisible();
    expect(screen.getByText("grid_1")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Energy Price" })).toBeVisible();
    expect(screen.getByText("Price USD/MWh")).toBeVisible();
    expect(screen.getAllByText("Hydro Power").length).toBeGreaterThan(0);
    expect(
      screen.getByText("Missing columns: total_hydro_power_mw"),
    ).toBeVisible();
    const artifactLink = screen.getByRole("link", { name: "summary.json" });
    expect(artifactLink).toHaveAttribute(
      "href",
      "/api/run-artifacts/11/download",
    );
    await waitFor(() => expect(plotlyMock.react).toHaveBeenCalled());
    expect(plotlyMock.react.mock.calls[0][1][0]).toMatchObject({
      name: "Price USD/MWh",
      y: [45],
    });

    await user.click(screen.getByRole("link", { name: "Analista" }));
    expect(
      await screen.findByRole("heading", { name: "Proyectos" }),
    ).toBeVisible();
    await waitFor(() => expect(plotlyMock.purge).toHaveBeenCalled());
  });

  it("launches one manual run from an immutable version and navigates before completion", async () => {
    window.history.replaceState({}, "", "/react/scenario-versions/41");
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const version = {
      id: 41,
      scenario_id: 10,
      version_number: 3,
      case_name: "dispatch_case",
      schema_version: "bess_system_dispatch.v1",
      period_count: 2,
      asset_counts: { battery: 1 },
      created_at: "2026-06-23T12:14:00Z",
      system_case_json: { case_name: "dispatch_case" },
      validation_payload: { status: "ok" },
      generation_metadata: {},
    };
    const run = {
      id: 99,
      scenario_version_id: 41,
      status: "queued",
      created_at: "2026-06-23T12:15:00Z",
      started_at: null,
      finished_at: null,
      duration_seconds: null,
      exit_code: null,
      error_message: "",
      stdout: "",
      stderr: "",
    };
    let launchCalls = 0;
    let resolveLaunch: ((response: Response) => void) | undefined;
    const launchPromise = new Promise<Response>((resolve) => {
      resolveLaunch = resolve;
    });
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenario-versions/41" && method === "GET") {
          return new Response(JSON.stringify({ scenario_version: version }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenario-versions/41/runs" && method === "POST") {
          launchCalls += 1;
          return launchPromise;
        }
        if (path === "/api/runs/99") {
          return new Response(JSON.stringify({ run }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Version 3" }),
    ).toBeVisible();
    const launchButton = screen.getByRole("button", { name: "Lanzar run" });
    await user.click(launchButton);
    await waitFor(() => expect(launchButton).toBeDisabled());
    await user.click(launchButton);
    await waitFor(() => expect(launchCalls).toBe(1));
    resolveLaunch!(
      new Response(JSON.stringify(run), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    expect(
      await screen.findByRole("heading", { name: "Run 99" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/runs/99");
    expect(screen.getByText("queued")).toBeVisible();
    expect(screen.getAllByText("Version 3").length).toBeGreaterThan(0);
    expect(screen.getByText("Creado")).toBeVisible();
    expect(screen.getByText("2026-06-23T12:15:00Z")).toBeVisible();
  });

  it("labels the version's case name as a name, not as a separate case entity, in version metadata", async () => {
    // BESS-TS5-006: `scenario_versions.case_name` is a frozen free-text label
    // from the payload at promotion time (it can differ between versions of
    // the same scenario), not the stable `OptimizationCase` this scenario
    // owns one-to-one. An unqualified "Case" label next to "Scenario ID"
    // reads as if versions could belong to different case entities.
    window.history.replaceState({}, "", "/react/scenario-versions/41");
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const version = {
      id: 41,
      scenario_id: 10,
      version_number: 3,
      case_name: "dispatch_case",
      schema_version: "bess_system_dispatch.v1",
      period_count: 2,
      asset_counts: { battery: 1 },
      created_at: "2026-06-23T12:14:00Z",
      system_case_json: { case_name: "dispatch_case" },
      validation_payload: { status: "ok" },
      generation_metadata: {},
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenario-versions/41" && method === "GET") {
          return new Response(JSON.stringify({ scenario_version: version }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Version 3" }),
    ).toBeVisible();
    expect(screen.getByText("Nombre del caso")).toBeVisible();
    expect(screen.queryByText("Case")).not.toBeInTheDocument();
  });

  it("polls nonterminal runs, recovers from a temporary polling failure, and shows failure logs", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const version = {
      id: 41,
      scenario_id: 10,
      version_number: 3,
      case_name: "dispatch_case",
      schema_version: "bess_system_dispatch.v1",
      period_count: 2,
      asset_counts: { battery: 1 },
      created_at: "2026-06-23T12:14:00Z",
      system_case_json: { case_name: "dispatch_case" },
      validation_payload: { status: "ok" },
      generation_metadata: {},
    };
    const runStates = [
      {
        id: 99,
        scenario_version_id: 41,
        status: "queued",
        created_at: "2026-06-23T12:15:00Z",
        started_at: null,
        finished_at: null,
        duration_seconds: null,
        exit_code: null,
        error_message: "",
        stdout: "",
        stderr: "",
      },
      {
        id: 99,
        scenario_version_id: 41,
        status: "running",
        created_at: "2026-06-23T12:15:00Z",
        started_at: "2026-06-23T12:15:01Z",
        finished_at: null,
        duration_seconds: null,
        exit_code: null,
        error_message: "",
        stdout: "",
        stderr: "",
      },
      {
        id: 99,
        scenario_version_id: 41,
        status: "failed",
        created_at: "2026-06-23T12:15:00Z",
        started_at: "2026-06-23T12:15:01Z",
        finished_at: "2026-06-23T12:15:03Z",
        duration_seconds: 2.0,
        exit_code: 23,
        error_message: "optimization failed before solve",
        error_payload: {
          status: "error",
          message: "optimization failed before solve",
        },
        stdout: "solver stdout\nsecond line\n",
        stderr:
          '{"status":"error","message":"optimization failed before solve"}\n',
      },
    ];
    let runGetCount = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/runs/99") {
          runGetCount += 1;
          if (runGetCount === 2) {
            return new Response(
              JSON.stringify({ detail: "temporary outage" }),
              {
                status: 503,
                headers: { "Content-Type": "application/json" },
              },
            );
          }
          const run =
            runGetCount === 1
              ? runStates[0]
              : runGetCount === 3
                ? runStates[1]
                : runStates[2];
          return new Response(JSON.stringify({ run }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenario-versions/41" && method === "GET") {
          return new Response(JSON.stringify({ scenario_version: version }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText("queued")).toBeVisible();
    expect(
      await screen.findByText("Reintentando actualizacion de run.", undefined, {
        timeout: 2500,
      }),
    ).toBeVisible();
    expect(
      await screen.findByText("running", undefined, { timeout: 4000 }),
    ).toBeVisible();
    expect(
      await screen.findByText("failed", undefined, { timeout: 4000 }),
    ).toBeVisible();
    expect(
      screen.getAllByText("optimization failed before solve").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/solver stdout/)).toBeVisible();
    expect(screen.getByText(/second line/)).toBeVisible();
    expect(screen.getByText(/"status":"error"/)).toBeVisible();
    const requestsAtTerminal = runGetCount;
    await new Promise((resolve) => setTimeout(resolve, 1300));
    expect(runGetCount).toBe(requestsAtTerminal);
  });

  it("lets analysts create, edit, save, recover, remove, and reopen a structured draft", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    let draft: unknown = null;
    let failNextSave = true;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "GET") {
          if (!draft) {
            return new Response(JSON.stringify({ detail: "not found" }), {
              status: 404,
              headers: { "Content-Type": "application/json" },
            });
          }
          return new Response(JSON.stringify({ draft }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "POST") {
          draft = {
            id: 3,
            scenario_id: 10,
            source_version_id: null,
            created_at: "2026-06-23T12:10:00Z",
            updated_at: "2026-06-23T12:10:00Z",
            document: {
              schema_version: "bess_editor_draft.v1",
              case: { name: "Base case" },
              source: null,
              pcc: { id: "bus_1", type: "bus" },
              grid: {
                id: "grid_1",
                import_power_max_mw: null,
                export_power_max_mw: null,
                prevent_simultaneous_grid_import_export: true,
              },
              assets: [],
              time_series: { sources: [] },
              solver: { name: "HiGHS", options: {} },
            },
          };
          return new Response(JSON.stringify(draft), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "PUT") {
          if (failNextSave) {
            failNextSave = false;
            return new Response(
              JSON.stringify({ detail: "database unavailable" }),
              {
                status: 503,
                headers: { "Content-Type": "application/json" },
              },
            );
          }
          const body = JSON.parse(String(init?.body));
          draft = {
            ...(draft as object),
            updated_at: "2026-06-23T12:12:00Z",
            document: body.document,
          };
          return new Response(JSON.stringify(draft), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Base case" }),
    ).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Abrir draft" }));

    expect(
      await screen.findByRole("heading", { name: "Draft estructurado" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Crear draft" }));
    expect(await screen.findByText("Guardado")).toBeVisible();

    await user.clear(screen.getByLabelText("Nombre del caso"));
    await user.type(screen.getByLabelText("Nombre del caso"), "PMGD verano");
    await user.click(screen.getByRole("button", { name: "Agregar BESS" }));
    await user.clear(screen.getByLabelText("BESS asset ID"));
    await user.type(screen.getByLabelText("BESS asset ID"), "battery_alpha");
    await user.click(screen.getByRole("button", { name: "Agregar hydro" }));
    await user.clear(screen.getByLabelText("Hydro asset ID"));
    await user.type(screen.getByLabelText("Hydro asset ID"), "hydro_north");
    expect(screen.getByText("Cambios sin guardar")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Guardar draft" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "database unavailable",
    );
    expect(screen.getByLabelText("Nombre del caso")).toHaveValue("PMGD verano");

    await user.click(screen.getByRole("button", { name: "Guardar draft" }));
    expect(await screen.findByText("Guardado")).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Quitar battery_alpha" }),
    );
    expect(
      screen.getByText("Confirma para quitar battery_alpha"),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Confirmar quitar battery_alpha" }),
    );
    await user.click(screen.getByRole("button", { name: "Guardar draft" }));
    expect(await screen.findByText("Guardado")).toBeVisible();

    await user.click(screen.getByRole("link", { name: "Base case" }));
    await user.click(screen.getByRole("link", { name: "Abrir draft" }));
    expect(await screen.findByLabelText("Nombre del caso")).toHaveValue(
      "PMGD verano",
    );
    expect(screen.queryByLabelText("BESS asset ID")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Hydro asset ID")).toHaveValue("hydro_north");
  });

  it("binds a price series to the default input variant and runs it from the scenario page", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const priceSet = {
      id: 5,
      project_id: 1,
      name: "Spot price",
      version_number: 1,
      version_label: "v1",
      revision_number: 1,
      data_kind: "real",
      timezone: "America/Santiago",
      status: "validated",
      content_hash: "hash-5",
      signal_count: 1,
      period_count: 3,
    };
    const priceSetDetail = {
      ...priceSet,
      source_checksum: null,
      revision_metadata: {},
      source: null,
      horizon: {
        period_count: 3,
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T03:00:00-03:00",
      },
      signals: [
        {
          signal_key: "price_usd_per_mwh",
          unit: "USD/MWh",
          entity_type: null,
          entity_key: null,
        },
      ],
      periods: [
        {
          period_index: 0,
          timestamp_start: "2026-01-01T00:00:00-03:00",
          timestamp_end: "2026-01-01T01:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 1,
          timestamp_start: "2026-01-01T01:00:00-03:00",
          timestamp_end: "2026-01-01T02:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 2,
          timestamp_start: "2026-01-01T02:00:00-03:00",
          timestamp_end: "2026-01-01T03:00:00-03:00",
          duration_hours: 1,
        },
      ],
      values: [],
    };
    const run = {
      id: 77,
      scenario_version_id: 55,
      status: "queued",
      created_at: "2026-07-06T12:15:00Z",
      started_at: null,
      finished_at: null,
      duration_seconds: null,
      exit_code: null,
      error_message: "",
      stdout: "",
      stderr: "",
    };
    let bindCalls = 0;
    let runCalls = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/case/variants") {
          return new Response(
            JSON.stringify({
              case: {
                id: 1,
                scenario_id: 10,
                case_key: "scenario_10_case",
                display_name: "Base case",
                updated_at: "2026-07-06T12:00:00Z",
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
                    created_at: "2026-07-06T12:00:00Z",
                    updated_at: "2026-07-06T12:00:00Z",
                  },
                  bindings: [],
                  required_signals: [
                    {
                      entity_type: "grid",
                      entity_id: "grid_1",
                      signal_key: "price_usd_per_mwh",
                      bound: false,
                      bound_signal_key: null,
                      time_series_set_id: null,
                    },
                  ],
                  staleness: { validated: false, stale: false, reasons: [] },
                },
              ],
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets") {
          return new Response(
            JSON.stringify({ time_series_sets: [priceSet] }),
            {
              headers: { "Content-Type": "application/json" },
            },
          );
        }
        if (path === "/api/projects/1/time-series-sets/5") {
          return new Response(
            JSON.stringify({ time_series_set: priceSetDetail }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/scenarios/10/case/variants/3/bindings" &&
          method === "POST"
        ) {
          bindCalls += 1;
          const body = JSON.parse(String(init?.body));
          expect(body).toEqual({
            signal_key: "price_usd_per_mwh",
            time_series_set_id: 5,
          });
          return new Response(
            JSON.stringify({
              id: 9,
              case_input_variant_id: 3,
              signal_key: "price_usd_per_mwh",
              time_series_set_id: 5,
              required: true,
              created_at: "2026-07-06T12:16:00Z",
              updated_at: "2026-07-06T12:16:00Z",
            }),
            { status: 201, headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/scenarios/10/case/variants/3/run" &&
          method === "POST"
        ) {
          runCalls += 1;
          const body = JSON.parse(String(init?.body));
          expect(body).toEqual({
            range_start: "2026-01-01T00:00:00-03:00",
            range_end: "2026-01-01T03:00:00-03:00",
          });
          return new Response(JSON.stringify(run), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/runs/77") {
          return new Response(JSON.stringify({ run }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByText("Aun no hay una serie de precio vinculada."),
    ).toBeVisible();
    expect(
      screen.getByText("price_usd_per_mwh (grid_1): falta vincular"),
    ).toBeVisible();
    await user.selectOptions(
      screen.getByLabelText("Serie de precio (price_usd_per_mwh)"),
      "5",
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Inicio de rango")).toHaveValue(
        "2026-01-01T00:00:00-03:00",
      ),
    );
    expect(screen.getByLabelText("Fin de rango")).toHaveValue(
      "2026-01-01T03:00:00-03:00",
    );
    expect(screen.getByText("Rango valido para correr.")).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Vincular y correr variante" }),
    );

    await waitFor(() => expect(bindCalls).toBe(1));
    await waitFor(() => expect(runCalls).toBe(1));
    expect(
      await screen.findByRole("heading", { name: "Run 77" }),
    ).toBeVisible();
  });

  function mockVariantRunLineage() {
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const run = {
      id: 99,
      scenario_version_id: 41,
      status: "queued",
      created_at: "2026-07-24T12:15:00Z",
      started_at: null,
      finished_at: null,
      duration_seconds: null,
      exit_code: null,
      error_message: "",
      stdout: "",
      stderr: "",
    };
    const version = {
      id: 41,
      scenario_id: 10,
      version_number: 3,
      case_name: "dispatch_case",
      schema_version: "bess_system_dispatch.v2",
      period_count: 2,
      asset_counts: { battery: 1 },
      created_at: "2026-07-24T12:14:00Z",
      system_case_json: {
        case_name: "dispatch_case",
        solver: { name: "HiGHS-TS3-007-MARKER" },
      },
      validation_payload: { status: "ok" },
      generation_metadata: {
        kind: "case_input_variant",
        topology: { content_hash: "topohash1234567890" },
        parameters: { content_hash: "paramhash1234567890" },
        input_variant: { id: 7, display_name: "Stress prices" },
        date_range: {
          start: "2026-01-01T00:00:00-03:00",
          end: "2026-01-02T00:00:00-03:00",
        },
        series_bindings: [
          {
            signal_key: "import_price_usd_per_mwh",
            entity_type: null,
            entity_id: null,
            time_series_set_id: 16,
            version_number: 2,
            version_label: "v2",
            revision_number: 3,
            content_hash: "sha256:abcdef1234567890",
            validated_range: {
              start: "2026-01-01T00:00:00-03:00",
              end: "2026-01-02T00:00:00-03:00",
            },
          },
        ],
      },
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/runs/99") {
          return new Response(JSON.stringify({ run }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenario-versions/41") {
          return new Response(JSON.stringify({ scenario_version: version }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    return fetchMock;
  }

  it("shows the selected variant name and run date range in run detail lineage", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    vi.stubGlobal("fetch", mockVariantRunLineage());

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Run 99" }),
    ).toBeVisible();
    expect(await screen.findByText("Stress prices")).toBeVisible();
    expect(screen.getByText(/2026-01-01T00:00:00-03:00/)).toBeVisible();
    expect(screen.getByText(/2026-01-02T00:00:00-03:00/)).toBeVisible();
  });

  it("shows per-binding input set revisions and content hashes in run detail lineage", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    vi.stubGlobal("fetch", mockVariantRunLineage());

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Run 99" }),
    ).toBeVisible();
    expect(
      await screen.findByText(/import_price_usd_per_mwh/),
    ).toBeVisible();
    expect(screen.getByText(/revision 3/)).toBeVisible();
    expect(screen.getByText(/sha256:abcde/)).toBeVisible();
  });

  it("hides the generated technical snapshot by default and reveals it on demand from run detail", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    vi.stubGlobal("fetch", mockVariantRunLineage());
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Run 99" }),
    ).toBeVisible();
    await screen.findByText("Ver snapshot tecnico");
    expect(screen.queryByText(/HiGHS-TS3-007-MARKER/)).not.toBeInTheDocument();

    await user.click(screen.getByText("Ver snapshot tecnico"));

    expect(await screen.findByText(/HiGHS-TS3-007-MARKER/)).toBeVisible();
  });

  it("binds entity-scoped required signals independently before running", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const buildSet = (id: number, name: string, signalKey: string) => ({
      id,
      project_id: 1,
      name,
      version_number: 1,
      version_label: "v1",
      revision_number: 1,
      data_kind: "real",
      timezone: "America/Santiago",
      status: "validated",
      content_hash: `hash-${id}`,
      signal_count: 1,
      period_count: 3,
      signalKey,
    });
    const buildSetDetail = (
      set: ReturnType<typeof buildSet>,
      entityType: string | null,
    ) => ({
      ...set,
      source_checksum: null,
      revision_metadata: {},
      source: null,
      horizon: {
        period_count: 3,
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T03:00:00-03:00",
      },
      signals: [
        {
          signal_key: set.signalKey,
          unit: set.signalKey === "price_usd_per_mwh" ? "USD/MWh" : "MW",
          entity_type: entityType,
          entity_key: null,
        },
      ],
      periods: [
        {
          period_index: 0,
          timestamp_start: "2026-01-01T00:00:00-03:00",
          timestamp_end: "2026-01-01T01:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 1,
          timestamp_start: "2026-01-01T01:00:00-03:00",
          timestamp_end: "2026-01-01T02:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 2,
          timestamp_start: "2026-01-01T02:00:00-03:00",
          timestamp_end: "2026-01-01T03:00:00-03:00",
          duration_hours: 1,
        },
      ],
      values: [],
    });
    const priceSet = buildSet(5, "Spot price", "price_usd_per_mwh");
    const loadAlphaSet = buildSet(6, "Load alpha", "load_demand_mw");
    const loadBetaSet = buildSet(7, "Load beta", "load_demand_mw");
    const run = {
      id: 78,
      scenario_version_id: 56,
      status: "queued",
      created_at: "2026-07-06T12:15:00Z",
      started_at: null,
      finished_at: null,
      duration_seconds: null,
      exit_code: null,
      error_message: "",
      stdout: "",
      stderr: "",
    };
    const bindPayloads: unknown[] = [];
    let runCalls = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/case/variants") {
          return new Response(
            JSON.stringify({
              case: {
                id: 1,
                scenario_id: 10,
                case_key: "scenario_10_case",
                display_name: "Base case",
                updated_at: "2026-07-06T12:00:00Z",
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
                    created_at: "2026-07-06T12:00:00Z",
                    updated_at: "2026-07-06T12:00:00Z",
                  },
                  bindings: [],
                  required_signals: [
                    {
                      entity_type: "grid",
                      entity_id: "grid_1",
                      signal_key: "price_usd_per_mwh",
                      bound: false,
                      bound_signal_key: null,
                      time_series_set_id: null,
                    },
                    {
                      entity_type: "component:load",
                      entity_id: "load_1",
                      signal_key: "load_demand_mw",
                      bound: false,
                      bound_signal_key: null,
                      time_series_set_id: null,
                    },
                    {
                      entity_type: "component:load",
                      entity_id: "load_2",
                      signal_key: "load_demand_mw",
                      bound: false,
                      bound_signal_key: null,
                      time_series_set_id: null,
                    },
                  ],
                  staleness: { validated: false, stale: false, reasons: [] },
                },
              ],
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets") {
          return new Response(
            JSON.stringify({
              time_series_sets: [priceSet, loadAlphaSet, loadBetaSet],
            }),
            {
              headers: { "Content-Type": "application/json" },
            },
          );
        }
        if (path === "/api/projects/1/time-series-sets/5") {
          return new Response(
            JSON.stringify({
              time_series_set: buildSetDetail(priceSet, null),
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets/6") {
          return new Response(
            JSON.stringify({
              time_series_set: buildSetDetail(loadAlphaSet, "component:load"),
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets/7") {
          return new Response(
            JSON.stringify({
              time_series_set: buildSetDetail(loadBetaSet, "component:load"),
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/scenarios/10/case/variants/3/bindings" &&
          method === "POST"
        ) {
          const body = JSON.parse(String(init?.body));
          bindPayloads.push(body);
          return new Response(
            JSON.stringify({
              id: 9 + bindPayloads.length,
              case_input_variant_id: 3,
              signal_key: body.signal_key,
              entity_type: body.entity_type ?? null,
              entity_id: body.entity_id ?? null,
              time_series_set_id: body.time_series_set_id,
              required: true,
              created_at: "2026-07-06T12:16:00Z",
              updated_at: "2026-07-06T12:16:00Z",
            }),
            { status: 201, headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/scenarios/10/case/variants/3/run" &&
          method === "POST"
        ) {
          runCalls += 1;
          return new Response(JSON.stringify(run), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/runs/78") {
          return new Response(JSON.stringify({ run }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await user.selectOptions(
      await screen.findByLabelText("Serie de precio (price_usd_per_mwh)"),
      "5",
    );
    await user.selectOptions(
      screen.getByLabelText("Serie load_demand_mw (load_1)"),
      "6",
    );
    await user.selectOptions(
      screen.getByLabelText("Serie load_demand_mw (load_2)"),
      "7",
    );

    await waitFor(() =>
      expect(screen.getByText("Rango valido para correr.")).toBeVisible(),
    );
    await user.click(
      screen.getByRole("button", { name: "Vincular y correr variante" }),
    );

    await waitFor(() => expect(runCalls).toBe(1));
    expect(bindPayloads).toEqual([
      {
        signal_key: "price_usd_per_mwh",
        time_series_set_id: 5,
      },
      {
        signal_key: "load_demand_mw",
        entity_type: "component:load",
        entity_id: "load_1",
        time_series_set_id: 6,
      },
      {
        signal_key: "load_demand_mw",
        entity_type: "component:load",
        entity_id: "load_2",
        time_series_set_id: 7,
      },
    ]);
    expect(
      await screen.findByRole("heading", { name: "Run 78" }),
    ).toBeVisible();
  });

  it("clones variants, switches them from dropdown, and persists active selection", async () => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/react/scenarios/10");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const caseRecord = {
      id: 1,
      scenario_id: 10,
      case_key: "scenario_10_case",
      display_name: "Base case",
      updated_at: "2026-07-06T12:00:00Z",
    };
    const requiredSignals = [
      {
        entity_type: "grid",
        entity_id: "grid_1",
        signal_key: "price_usd_per_mwh",
        bound: true,
        bound_signal_key: "price_usd_per_mwh",
        time_series_set_id: 5,
      },
    ];
    const priceSet = {
      id: 5,
      project_id: 1,
      name: "Spot price",
      version_number: 1,
      version_label: "v1",
      revision_number: 1,
      data_kind: "real",
      timezone: "America/Santiago",
      status: "validated",
      content_hash: "hash-5",
      signal_count: 1,
      period_count: 3,
    };
    const stressSet = {
      id: 6,
      project_id: 1,
      name: "Stress price",
      version_number: 1,
      version_label: "dry-year",
      revision_number: 1,
      data_kind: "real",
      timezone: "America/Santiago",
      status: "validated",
      content_hash: "hash-6",
      signal_count: 1,
      period_count: 3,
    };
    const buildSetDetail = (set: typeof priceSet) => ({
      ...set,
      source_checksum: null,
      revision_metadata: {},
      source: null,
      horizon: {
        period_count: 3,
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T03:00:00-03:00",
      },
      signals: [
        {
          signal_key: "price_usd_per_mwh",
          unit: "USD/MWh",
          entity_type: null,
          entity_key: null,
        },
      ],
      periods: [
        {
          period_index: 0,
          timestamp_start: "2026-01-01T00:00:00-03:00",
          timestamp_end: "2026-01-01T01:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 1,
          timestamp_start: "2026-01-01T01:00:00-03:00",
          timestamp_end: "2026-01-01T02:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 2,
          timestamp_start: "2026-01-01T02:00:00-03:00",
          timestamp_end: "2026-01-01T03:00:00-03:00",
          duration_hours: 1,
        },
      ],
      values: [],
    });
    const run = {
      id: 88,
      scenario_version_id: 56,
      status: "queued",
      created_at: "2026-07-06T12:20:00Z",
      started_at: null,
      finished_at: null,
      duration_seconds: null,
      exit_code: null,
      error_message: "",
      stdout: "",
      stderr: "",
    };
    let nextVariantId = 4;
    let bindCalls = 0;
    let runCalls = 0;
    const variantEntries = [
      {
        variant: {
          id: 3,
          case_id: 1,
          variant_key: "default",
          display_name: "Default",
          is_default: true,
          created_at: "2026-07-06T12:00:00Z",
          updated_at: "2026-07-06T12:00:00Z",
        },
        bindings: [
          {
            id: 9,
            case_input_variant_id: 3,
            signal_key: "price_usd_per_mwh",
            time_series_set_id: 5,
            required: true,
            created_at: "2026-07-06T12:16:00Z",
            updated_at: "2026-07-06T12:16:00Z",
          },
        ],
        required_signals: requiredSignals,
        staleness: { validated: false, stale: false, reasons: [] },
      },
    ];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/case/variants" && method === "GET") {
          return new Response(
            JSON.stringify({
              case: caseRecord,
              default_variant_id: 3,
              variants: variantEntries,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets") {
          return new Response(
            JSON.stringify({ time_series_sets: [priceSet, stressSet] }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets/5") {
          return new Response(
            JSON.stringify({ time_series_set: buildSetDetail(priceSet) }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets/6") {
          return new Response(
            JSON.stringify({ time_series_set: buildSetDetail(stressSet) }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/scenarios/10/case/variants/3/clone" &&
          method === "POST"
        ) {
          const body = JSON.parse(String(init?.body));
          expect(body).toEqual({ display_name: "Stress prices" });
          const source = variantEntries[0];
          const clonedVariant = {
            variant: {
              ...source.variant,
              id: nextVariantId,
              variant_key: "stress_prices",
              display_name: "Stress prices",
              is_default: false,
            },
            bindings: source.bindings.map((binding) => ({
              ...binding,
              id: binding.id + 100,
              case_input_variant_id: nextVariantId,
            })),
            required_signals: source.required_signals.map((signal) => ({
              ...signal,
            })),
            staleness: { validated: false, stale: false, reasons: [] },
          };
          variantEntries.push(clonedVariant);
          nextVariantId += 1;
          return new Response(JSON.stringify(clonedVariant.variant), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/case/variants/4/bindings" &&
          method === "POST"
        ) {
          bindCalls += 1;
          const body = JSON.parse(String(init?.body));
          expect(body).toEqual({
            signal_key: "price_usd_per_mwh",
            time_series_set_id: 6,
          });
          const entry = variantEntries.find(
            (variant) => variant.variant.id === 4,
          );
          if (!entry) throw new Error("cloned variant missing");
          entry.bindings = [
            {
              id: 111,
              case_input_variant_id: 4,
              signal_key: "price_usd_per_mwh",
              time_series_set_id: 6,
              required: true,
              created_at: "2026-07-06T12:25:00Z",
              updated_at: "2026-07-06T12:25:00Z",
            },
          ];
          entry.required_signals = [
            {
              ...requiredSignals[0],
              time_series_set_id: 6,
            },
          ];
          return new Response(JSON.stringify(entry.bindings[0]), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/case/variants/4/run" &&
          method === "POST"
        ) {
          runCalls += 1;
          const body = JSON.parse(String(init?.body));
          expect(body).toEqual({
            range_start: "2026-01-01T00:00:00-03:00",
            range_end: "2026-01-01T03:00:00-03:00",
          });
          return new Response(JSON.stringify(run), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/runs/88") {
          return new Response(JSON.stringify({ run }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    const firstRender = render(<App />);

    expect(await screen.findByText("Precio vinculado: set #5.")).toBeVisible();
    await waitFor(() =>
      expect(screen.getByLabelText("Inicio de rango")).toHaveValue(
        "2026-01-01T00:00:00-03:00",
      ),
    );
    expect(screen.getByLabelText("Fin de rango")).toHaveValue(
      "2026-01-01T03:00:00-03:00",
    );

    await user.type(
      screen.getByLabelText("Nombre nueva variante"),
      "Stress prices",
    );
    await user.click(
      screen.getByRole("button", { name: "Clonar variante activa" }),
    );

    await waitFor(() =>
      expect(
        screen.getByRole("heading", {
          name: "Variante de entrada: Stress prices",
        }),
      ).toBeVisible(),
    );
    expect(screen.getByLabelText("Variante activa")).toHaveValue("4");
    expect(screen.getByText("Precio vinculado: set #5.")).toBeVisible();

    await user.selectOptions(
      screen.getByLabelText("Serie de precio (price_usd_per_mwh)"),
      "6",
    );
    await user.click(
      screen.getByRole("button", { name: "Vincular y correr variante" }),
    );

    await waitFor(() => expect(bindCalls).toBe(1));
    await waitFor(() => expect(runCalls).toBe(1));
    expect(
      await screen.findByRole("heading", { name: "Run 88" }),
    ).toBeVisible();

    firstRender.unmount();
    window.history.replaceState({}, "", "/react/scenarios/10");
    render(<App />);

    await waitFor(() =>
      expect(screen.getByLabelText("Variante activa")).toHaveValue("4"),
    );
    expect(
      screen.getByRole("heading", {
        name: "Variante de entrada: Stress prices",
      }),
    ).toBeVisible();
    expect(screen.getByText("Precio vinculado: set #6.")).toBeVisible();
  });

  it("surfaces input variant coverage errors before launching", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const priceSet = {
      id: 5,
      project_id: 1,
      name: "Spot price",
      version_number: 1,
      version_label: "v1",
      revision_number: 1,
      data_kind: "real",
      timezone: "America/Santiago",
      status: "validated",
      content_hash: "hash-5",
      signal_count: 1,
      period_count: 3,
    };
    const priceSetDetail = {
      ...priceSet,
      source_checksum: null,
      revision_metadata: {},
      source: null,
      horizon: {
        period_count: 3,
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T03:00:00-03:00",
      },
      signals: [
        {
          signal_key: "price_usd_per_mwh",
          unit: "USD/MWh",
          entity_type: null,
          entity_key: null,
        },
      ],
      periods: [
        {
          period_index: 0,
          timestamp_start: "2026-01-01T00:00:00-03:00",
          timestamp_end: "2026-01-01T01:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 1,
          timestamp_start: "2026-01-01T01:00:00-03:00",
          timestamp_end: "2026-01-01T02:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 2,
          timestamp_start: "2026-01-01T02:00:00-03:00",
          timestamp_end: "2026-01-01T03:00:00-03:00",
          duration_hours: 1,
        },
      ],
      values: [],
    };
    let runCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/case/variants") {
          return new Response(
            JSON.stringify({
              case: {
                id: 1,
                scenario_id: 10,
                case_key: "scenario_10_case",
                display_name: "Base case",
                updated_at: "2026-07-06T12:00:00Z",
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
                    created_at: "2026-07-06T12:00:00Z",
                    updated_at: "2026-07-06T12:00:00Z",
                  },
                  bindings: [],
                  required_signals: [
                    {
                      entity_type: "grid",
                      entity_id: "grid_1",
                      signal_key: "price_usd_per_mwh",
                      bound: false,
                      bound_signal_key: null,
                      time_series_set_id: null,
                    },
                  ],
                  staleness: { validated: false, stale: false, reasons: [] },
                },
              ],
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets") {
          return new Response(
            JSON.stringify({ time_series_sets: [priceSet] }),
            {
              headers: { "Content-Type": "application/json" },
            },
          );
        }
        if (path === "/api/projects/1/time-series-sets/5") {
          return new Response(
            JSON.stringify({ time_series_set: priceSetDetail }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/scenarios/10/case/variants/3/run") {
          runCalls += 1;
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      }),
    );
    const user = userEvent.setup();

    render(<App />);

    await user.selectOptions(
      await screen.findByLabelText("Serie de precio (price_usd_per_mwh)"),
      "5",
    );
    await user.clear(screen.getByLabelText("Fin de rango"));
    await user.type(
      screen.getByLabelText("Fin de rango"),
      "2026-01-01T04:00:00-03:00",
    );

    expect(screen.getByText(/Cobertura incompleta/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Vincular y correr variante" }),
    ).toBeDisabled();
    expect(runCalls).toBe(0);
  });

  it("surfaces input variant horizon mismatches before launching", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const priceSet = {
      id: 5,
      project_id: 1,
      name: "Spot price",
      version_number: 1,
      version_label: "v1",
      revision_number: 1,
      data_kind: "real",
      timezone: "America/Santiago",
      status: "validated",
      content_hash: "hash-5",
      signal_count: 1,
      period_count: 3,
    };
    const priceSetDetail = {
      ...priceSet,
      source_checksum: null,
      revision_metadata: {},
      source: null,
      horizon: {
        period_count: 3,
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T03:00:00-03:00",
      },
      signals: [
        {
          signal_key: "price_usd_per_mwh",
          unit: "USD/MWh",
          entity_type: null,
          entity_key: null,
        },
      ],
      periods: [
        {
          period_index: 0,
          timestamp_start: "2026-01-01T00:00:00-03:00",
          timestamp_end: "2026-01-01T01:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 1,
          timestamp_start: "2026-01-01T01:00:00-03:00",
          timestamp_end: "2026-01-01T02:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 2,
          timestamp_start: "2026-01-01T02:00:00-03:00",
          timestamp_end: "2026-01-01T03:00:00-03:00",
          duration_hours: 1,
        },
      ],
      values: [],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/case/variants") {
          return new Response(
            JSON.stringify({
              case: {
                id: 1,
                scenario_id: 10,
                case_key: "scenario_10_case",
                display_name: "Base case",
                updated_at: "2026-07-06T12:00:00Z",
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
                    created_at: "2026-07-06T12:00:00Z",
                    updated_at: "2026-07-06T12:00:00Z",
                  },
                  bindings: [],
                  required_signals: [
                    {
                      entity_type: "grid",
                      entity_id: "grid_1",
                      signal_key: "price_usd_per_mwh",
                      bound: false,
                      bound_signal_key: null,
                      time_series_set_id: null,
                    },
                  ],
                  staleness: { validated: false, stale: false, reasons: [] },
                },
              ],
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets") {
          return new Response(
            JSON.stringify({ time_series_sets: [priceSet] }),
            {
              headers: { "Content-Type": "application/json" },
            },
          );
        }
        if (path === "/api/projects/1/time-series-sets/5") {
          return new Response(
            JSON.stringify({ time_series_set: priceSetDetail }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(JSON.stringify({ detail: `unhandled ${path}` }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
    const user = userEvent.setup();

    render(<App />);

    await user.selectOptions(
      await screen.findByLabelText("Serie de precio (price_usd_per_mwh)"),
      "5",
    );
    await user.clear(screen.getByLabelText("Inicio de rango"));
    await user.type(
      screen.getByLabelText("Inicio de rango"),
      "2026-01-01T00:30:00-03:00",
    );

    expect(screen.getByText(/Horizonte incompatible/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Vincular y correr variante" }),
    ).toBeDisabled();
  });

  it("shows a stale input variant, blocks the run button, and clears the marker after revalidating", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const priceSet = {
      id: 5,
      project_id: 1,
      name: "Spot price",
      version_number: 1,
      version_label: "v1",
      revision_number: 2,
      data_kind: "real",
      timezone: "America/Santiago",
      status: "validated",
      content_hash: "hash-5-b",
      signal_count: 1,
      period_count: 3,
    };
    const priceSetDetail = {
      ...priceSet,
      source_checksum: null,
      revision_metadata: {},
      source: null,
      horizon: {
        period_count: 3,
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T03:00:00-03:00",
      },
      signals: [
        {
          signal_key: "price_usd_per_mwh",
          unit: "USD/MWh",
          entity_type: null,
          entity_key: null,
        },
      ],
      periods: [
        {
          period_index: 0,
          timestamp_start: "2026-01-01T00:00:00-03:00",
          timestamp_end: "2026-01-01T01:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 1,
          timestamp_start: "2026-01-01T01:00:00-03:00",
          timestamp_end: "2026-01-01T02:00:00-03:00",
          duration_hours: 1,
        },
        {
          period_index: 2,
          timestamp_start: "2026-01-01T02:00:00-03:00",
          timestamp_end: "2026-01-01T03:00:00-03:00",
          duration_hours: 1,
        },
      ],
      values: [],
    };
    let stale = true;
    let validateCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/case/variants" && method === "GET") {
          return new Response(
            JSON.stringify({
              case: {
                id: 1,
                scenario_id: 10,
                case_key: "scenario_10_case",
                display_name: "Base case",
                updated_at: "2026-07-06T12:00:00Z",
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
                    created_at: "2026-07-06T12:00:00Z",
                    updated_at: "2026-07-06T12:00:00Z",
                  },
                  bindings: [
                    {
                      id: 9,
                      case_input_variant_id: 3,
                      signal_key: "price_usd_per_mwh",
                      entity_type: null,
                      entity_id: null,
                      time_series_set_id: 5,
                      required: true,
                      created_at: "2026-07-06T12:16:00Z",
                      updated_at: "2026-07-06T12:16:00Z",
                    },
                  ],
                  required_signals: [
                    {
                      entity_type: "grid",
                      entity_id: "grid_1",
                      signal_key: "price_usd_per_mwh",
                      bound: true,
                      bound_signal_key: "price_usd_per_mwh",
                      time_series_set_id: 5,
                    },
                  ],
                  staleness: stale
                    ? {
                        validated: true,
                        stale: true,
                        reasons: [
                          {
                            dependency_type: "time_series_set",
                            dependency_id: "5",
                            detail: "time-series set 5 changed since last validation",
                          },
                        ],
                      }
                    : { validated: true, stale: false, reasons: [] },
                },
              ],
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets") {
          return new Response(
            JSON.stringify({ time_series_sets: [priceSet] }),
            {
              headers: { "Content-Type": "application/json" },
            },
          );
        }
        if (path === "/api/projects/1/time-series-sets/5") {
          return new Response(
            JSON.stringify({ time_series_set: priceSetDetail }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/scenarios/10/case/variants/3/validate" &&
          method === "POST"
        ) {
          validateCalls += 1;
          stale = false;
          return new Response(
            JSON.stringify({ status: "valid", series_bindings: [] }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      }),
    );
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByText(/Variante desactualizada/),
    ).toBeVisible();
    expect(screen.getByText(/time-series set 5 changed/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Vincular y correr variante" }),
    ).toBeDisabled();

    await user.click(
      screen.getByRole("button", { name: "Revalidar variante" }),
    );

    await waitFor(() => {
      expect(screen.queryByText(/Variante desactualizada/)).toBeNull();
    });
    expect(validateCalls).toBe(1);
    expect(
      screen.getByRole("button", { name: "Vincular y correr variante" }),
    ).toBeEnabled();
  });

  it("saves the draft and opens the hydraulic diagram when editing a hydro component", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Hydro modeling branch",
      created_at: "2026-06-30T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-30T12:00:00Z",
    };
    let draft: unknown = null;
    let savedHydroAsset = false;
    const diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Base case",
        updated_at: "2026-06-30T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-30T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "GET") {
          if (!draft) {
            return new Response(JSON.stringify({ detail: "not found" }), {
              status: 404,
              headers: { "Content-Type": "application/json" },
            });
          }
          return new Response(JSON.stringify({ draft }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "POST") {
          draft = {
            id: 3,
            scenario_id: 10,
            source_version_id: null,
            created_at: "2026-06-30T12:10:00Z",
            updated_at: "2026-06-30T12:10:00Z",
            document: {
              schema_version: "bess_editor_draft.v1",
              case: { name: "Base case" },
              source: null,
              pcc: { id: "bus_1", type: "bus" },
              grid: {
                id: "grid_1",
                import_power_max_mw: null,
                export_power_max_mw: null,
                prevent_simultaneous_grid_import_export: true,
              },
              assets: [],
              time_series: { sources: [] },
              solver: { name: "HiGHS", options: {} },
            },
          };
          return new Response(JSON.stringify(draft), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "PUT") {
          const body = JSON.parse(String(init?.body));
          savedHydroAsset = Boolean(
            body.document?.assets?.some(
              (asset: { type?: string }) => asset.type === "hydro",
            ),
          );
          draft = {
            ...(draft as object),
            updated_at: "2026-06-30T12:12:00Z",
            document: body.document,
          };
          return new Response(JSON.stringify(draft), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Draft estructurado" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Crear draft" }));
    expect(await screen.findByText("Guardado")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Agregar hydro" }));
    await user.click(
      screen.getByRole("button", { name: "Editar diagrama hidraulico" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    expect(savedHydroAsset).toBe(true);
  });

  it("opens a persisted hydraulic diagram, saves visible nodes, recovers from save failure, and reloads server data", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Hydraulic branch",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    let diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Base case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [] as Array<{
        layout_item_id: number;
        entity_type: string;
        entity_id: number;
        component_type: "reservoir" | "junction" | "plant";
        technical_key: string;
        display_name: string;
        x: number;
        y: number;
        z_index: number;
      }>,
    };
    let failNextSave = true;
    let reloadCount = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "GET"
        ) {
          reloadCount += 1;
          return new Response(JSON.stringify({ diagram }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "PUT"
        ) {
          if (failNextSave) {
            failNextSave = false;
            return new Response(
              JSON.stringify({ detail: "database unavailable" }),
              {
                status: 503,
                headers: { "Content-Type": "application/json" },
              },
            );
          }
          const body = JSON.parse(String(init?.body));
          diagram = {
            ...diagram,
            revision: "2",
            layout: {
              ...diagram.layout,
              layout_version: 2,
              revision: "2",
              layout_engine: "manual",
              updated_at: "2026-06-26T12:12:00Z",
            },
            nodes: body.nodes.map(
              (
                node: {
                  component_type: "reservoir" | "junction" | "plant";
                  technical_key: string;
                  display_name: string;
                  x: number;
                  y: number;
                },
                index: number,
              ) => ({
                ...node,
                layout_item_id: index + 1,
                entity_type:
                  node.component_type === "plant"
                    ? "case_hydraulic_plant"
                    : "case_hydraulic_node",
                entity_id: index + 1,
                z_index: index,
              }),
            ),
          };
          return new Response(JSON.stringify({ diagram }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    expect(screen.getByText("Estado: saved")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Agregar embalse" }));
    await user.click(screen.getByRole("button", { name: "Agregar union" }));
    await user.click(screen.getByRole("button", { name: "Agregar central" }));
    selectDiagramNode("plant_1");
    await user.clear(screen.getByLabelText("Etiqueta plant_1"));
    await user.type(screen.getByLabelText("Etiqueta plant_1"), "Plant Laja");
    expect(screen.getByText("Estado: dirty")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Guardar diagrama" }));
    expect(await screen.findByText("Estado: failed")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("database unavailable");
    expect(screen.getByLabelText("Etiqueta plant_1")).toHaveValue("Plant Laja");

    await user.click(screen.getByRole("button", { name: "Guardar diagrama" }));
    expect(await screen.findByText("Estado: saved")).toBeVisible();
    // The plant label now appears both in the node list and the plant panel.
    expect(screen.getAllByText("Plant Laja").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Recargar diagrama" }));
    await waitFor(() => expect(reloadCount).toBeGreaterThan(0));
    selectDiagramNode("plant_1");
    expect(screen.getByLabelText("Etiqueta plant_1")).toHaveValue("Plant Laja");
  });

  it("moves a node, saves the layout, and reloads the persisted position", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Layout case",
      description: "Hydraulic layout branch",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    let diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Layout case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [] as Array<{
        layout_item_id: number;
        entity_type: string;
        entity_id: number;
        component_type: "reservoir" | "junction" | "plant";
        technical_key: string;
        display_name: string;
        x: number;
        y: number;
        z_index: number;
      }>,
    };
    let savedRevision = 1;
    let reloadCount = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "GET"
        ) {
          reloadCount += 1;
          return new Response(JSON.stringify({ diagram }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "PUT"
        ) {
          const body = JSON.parse(String(init?.body));
          savedRevision += 1;
          diagram = {
            ...diagram,
            revision: String(savedRevision),
            layout: {
              ...diagram.layout,
              layout_version: savedRevision,
              revision: String(savedRevision),
              layout_engine: "manual",
              viewport: body.viewport,
              updated_at: "2026-06-26T12:12:00Z",
            },
            nodes: body.nodes.map(
              (
                node: {
                  component_type: "reservoir" | "junction" | "plant";
                  technical_key: string;
                  display_name: string;
                  x: number;
                  y: number;
                },
                index: number,
              ) => ({
                ...node,
                layout_item_id: index + 1,
                entity_type:
                  node.component_type === "plant"
                    ? "case_hydraulic_plant"
                    : "case_hydraulic_node",
                entity_id: index + 1,
                z_index: index,
              }),
            ),
          };
          return new Response(JSON.stringify({ diagram }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Agregar union" }));
    // Move the new node on the visual canvas to a deliberate position.
    const canvasNode = screen.getByTestId("hydraulic-canvas-node-junction_1");
    fireEvent.pointerDown(canvasNode, {
      button: 0,
      clientX: 140,
      clientY: 100,
      pointerId: 1,
    });
    fireEvent.pointerMove(canvasNode, {
      buttons: 1,
      clientX: 660,
      clientY: 380,
      pointerId: 1,
    });
    fireEvent.pointerUp(canvasNode, {
      clientX: 660,
      clientY: 380,
      pointerId: 1,
    });
    expect(screen.getByText("Estado: dirty")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Guardar diagrama" }));
    expect(await screen.findByText("Estado: saved")).toBeVisible();
    // Position is edited only on the diagram, so it is reflected by the node's
    // canvas placement rather than by x/y form fields.
    expect(screen.getByTestId("hydraulic-canvas-node-junction_1")).toHaveStyle({
      left: "640px",
      top: "360px",
    });

    await user.click(screen.getByRole("button", { name: "Recargar diagrama" }));
    await waitFor(() => expect(reloadCount).toBeGreaterThan(0));
    // The persisted position survives a reload from the server.
    expect(screen.getByTestId("hydraulic-canvas-node-junction_1")).toHaveStyle({
      left: "640px",
      top: "360px",
    });
  });

  it("creates directed hydraulic reaches by drag, edits them through the fallback form, and displays validation errors", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Reach case",
      description: "Hydraulic reach branch",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    let diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Reach case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [] as Array<{
        layout_item_id: number;
        entity_type: string;
        entity_id: number;
        component_type: "reservoir" | "junction" | "plant";
        technical_key: string;
        display_name: string;
        x: number;
        y: number;
        z_index: number;
      }>,
      reaches: [] as Array<{
        layout_item_id: number;
        entity_type: string;
        entity_id: number;
        technical_key: string;
        display_name: string;
        from_node_key: string;
        to_node_key: string;
        reach_type: string;
        z_index: number;
      }>,
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "PUT"
        ) {
          const body = JSON.parse(String(init?.body));
          diagram = {
            ...diagram,
            revision: "2",
            layout: {
              ...diagram.layout,
              layout_version: 2,
              revision: "2",
              layout_engine: "manual",
            },
            nodes: body.nodes.map(
              (
                node: {
                  component_type: "reservoir" | "junction" | "plant";
                  technical_key: string;
                  display_name: string;
                  x: number;
                  y: number;
                },
                index: number,
              ) => ({
                ...node,
                layout_item_id: index + 1,
                entity_type:
                  node.component_type === "plant"
                    ? "case_hydraulic_plant"
                    : "case_hydraulic_node",
                entity_id: index + 1,
                z_index: index,
              }),
            ),
            reaches: body.reaches.map(
              (
                reach: {
                  technical_key: string;
                  display_name: string;
                  from_node_key: string;
                  to_node_key: string;
                  reach_type: string;
                },
                index: number,
              ) => ({
                ...reach,
                layout_item_id: 100 + index,
                entity_type: "case_hydraulic_reach",
                entity_id: 200 + index,
                z_index: 10 + index,
              }),
            ),
          };
          return new Response(JSON.stringify({ diagram }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram/validate" &&
          method === "POST"
        ) {
          return new Response(
            JSON.stringify({
              validation: {
                ok: false,
                summary: "Hydraulic topology has errors",
                errors: [
                  {
                    code: "inactive_or_missing_endpoint",
                    message:
                      "Reach reach_reservoir_1_junction_1 must connect active hydraulic nodes in this case.",
                    entity_type: "case_hydraulic_reach",
                    entity_id: 200,
                    technical_key: "reach_reservoir_1_junction_1",
                  },
                ],
                warnings: [],
              },
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agregar embalse" }));
    await user.click(screen.getByRole("button", { name: "Agregar union" }));

    const dataTransfer = {
      source: "",
      setData: vi.fn((_: string, value: string) => {
        dataTransfer.source = value;
      }),
      getData: vi.fn(() => dataTransfer.source),
    };
    fireEvent.dragStart(screen.getByTestId("hydraulic-node-out-reservoir_1"), {
      dataTransfer,
    });
    fireEvent.dragOver(screen.getByTestId("hydraulic-node-in-junction_1"));
    fireEvent.drop(screen.getByTestId("hydraulic-node-in-junction_1"), {
      dataTransfer,
    });

    expect(screen.getByText("reach_reservoir_1_junction_1")).toBeVisible();
    await user.selectOptions(
      screen.getByLabelText("Origen reach_reservoir_1_junction_1"),
      "junction_1",
    );
    await user.selectOptions(
      screen.getByLabelText("Destino reach_reservoir_1_junction_1"),
      "reservoir_1",
    );
    await user.selectOptions(
      screen.getByLabelText("Tipo reach_reservoir_1_junction_1"),
      "spillway",
    );
    await user.clear(
      screen.getByLabelText("Etiqueta reach_reservoir_1_junction_1"),
    );
    await user.type(
      screen.getByLabelText("Etiqueta reach_reservoir_1_junction_1"),
      "Spillway A",
    );
    await user.type(
      screen.getByLabelText("Caudal minimo m3/s reach_reservoir_1_junction_1"),
      "4",
    );
    await user.type(
      screen.getByLabelText(
        "Penalidad vertedero USD/hm3 reach_reservoir_1_junction_1",
      ),
      "120",
    );
    expect(
      screen.getByTestId("reach-minimum-flow-reach_reservoir_1_junction_1"),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Guardar diagrama" }));
    expect(await screen.findByText("Estado: saved")).toBeVisible();
    // Saving resets the selection, so re-select the reach on the canvas to
    // confirm the edited values were persisted.
    fireEvent.click(
      screen.getByTestId("hydraulic-link-reach_reservoir_1_junction_1"),
    );
    expect(screen.getByDisplayValue("Spillway A")).toBeVisible();
    expect(
      screen.getByLabelText("Caudal minimo m3/s reach_reservoir_1_junction_1"),
    ).toHaveValue(4);
    expect(
      screen.getByLabelText(
        "Penalidad vertedero USD/hm3 reach_reservoir_1_junction_1",
      ),
    ).toHaveValue(120);

    await user.click(screen.getByRole("button", { name: "Validar topologia" }));
    expect(
      await screen.findByText("Hydraulic topology has errors"),
    ).toBeVisible();
    expect(
      screen.getByText(/must connect active hydraulic nodes/),
    ).toBeVisible();
    expect(screen.getByDisplayValue("Spillway A")).toBeVisible();

    // Selecting another node hides the reach editor; the validation message can
    // re-focus the reach so its properties panel returns.
    selectDiagramNode("reservoir_1");
    expect(screen.queryByDisplayValue("Spillway A")).toBeNull();
    await user.click(
      screen.getByRole("button", {
        name: "Enfocar reach_reservoir_1_junction_1",
      }),
    );
    expect(
      screen.getByTestId("hydraulic-properties-reach_reservoir_1_junction_1"),
    ).toBeVisible();
    expect(screen.getByDisplayValue("Spillway A")).toBeVisible();
  });

  it("wires a plant through ports: intake from the input port, discharge from the output port, auto-creating a unit", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Plant ports case",
      description: "Plant port wiring",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    const diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Plant ports case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [],
      reaches: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agregar embalse" }));
    await user.click(screen.getByRole("button", { name: "Agregar central" }));
    await user.click(screen.getByRole("button", { name: "Agregar union" }));

    const dataTransfer = {
      source: "",
      setData: vi.fn((_: string, value: string) => {
        dataTransfer.source = value;
      }),
      getData: vi.fn(() => dataTransfer.source),
    };

    // Reservoir output -> plant input wires the intake on an auto-created unit.
    fireEvent.dragStart(screen.getByTestId("hydraulic-node-out-reservoir_1"), {
      dataTransfer,
    });
    fireEvent.dragOver(screen.getByTestId("hydraulic-node-in-plant_1"));
    fireEvent.drop(screen.getByTestId("hydraulic-node-in-plant_1"), {
      dataTransfer,
    });

    expect(screen.getByLabelText("Nodo de toma unit_1")).toHaveValue(
      "reservoir_1",
    );

    // Plant output -> junction input wires the discharge on the same unit.
    fireEvent.dragStart(screen.getByTestId("hydraulic-node-out-plant_1"), {
      dataTransfer,
    });
    fireEvent.dragOver(screen.getByTestId("hydraulic-node-in-junction_1"));
    fireEvent.drop(screen.getByTestId("hydraulic-node-in-junction_1"), {
      dataTransfer,
    });

    expect(screen.getByLabelText("Nodo de descarga unit_1")).toHaveValue(
      "junction_1",
    );
    expect(screen.getByLabelText("Nodo de toma unit_1")).toHaveValue(
      "reservoir_1",
    );
    // No second unit was created by the second connection.
    expect(screen.queryByLabelText("Nodo de toma unit_2")).toBeNull();
  });

  it("only links output ports to input ports and allows fan-in and fan-out", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Port rules case",
      description: "Port direction rules",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    const diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Port rules case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [],
      reaches: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agregar embalse" }));
    await user.click(screen.getByRole("button", { name: "Agregar embalse" }));
    await user.click(screen.getByRole("button", { name: "Agregar union" }));

    const dataTransfer = {
      source: "",
      setData: vi.fn((_: string, value: string) => {
        dataTransfer.source = value;
      }),
      getData: vi.fn(() => dataTransfer.source),
    };
    const link = (fromKey: string, toKey: string) => {
      fireEvent.dragStart(screen.getByTestId(`hydraulic-node-out-${fromKey}`), {
        dataTransfer,
      });
      fireEvent.dragOver(screen.getByTestId(`hydraulic-node-in-${toKey}`));
      fireEvent.drop(screen.getByTestId(`hydraulic-node-in-${toKey}`), {
        dataTransfer,
      });
    };

    // Fan-in: two outputs into one input.
    link("reservoir_1", "junction_1");
    link("reservoir_2", "junction_1");
    expect(
      screen.getByTestId("hydraulic-link-reach_reservoir_1_junction_1"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("hydraulic-link-reach_reservoir_2_junction_1"),
    ).toBeInTheDocument();

    // Fan-out: one output into a second input.
    link("reservoir_1", "reservoir_2");
    expect(
      screen.getByTestId("hydraulic-link-reach_reservoir_1_reservoir_2"),
    ).toBeInTheDocument();

    // Output-to-output is rejected: dropping on an output port does nothing.
    dataTransfer.source = "";
    fireEvent.dragStart(screen.getByTestId("hydraulic-node-out-junction_1"), {
      dataTransfer,
    });
    fireEvent.drop(screen.getByTestId("hydraulic-node-out-reservoir_1"), {
      dataTransfer,
    });
    expect(
      screen.queryByTestId("hydraulic-link-reach_junction_1_reservoir_1"),
    ).toBeNull();
  });

  it("shows a contextual properties panel for the selected object and never exposes x/y there", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Panel case",
      description: "Contextual panel",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    const diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Panel case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [],
      reaches: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agregar union" }));

    // Nothing is selected yet: the panel prompts for a selection.
    expect(
      screen.getByText(
        "Selecciona un objeto del diagrama para editar sus propiedades.",
      ),
    ).toBeVisible();

    // Select the node on the canvas.
    const canvasNode = screen.getByTestId("hydraulic-canvas-node-junction_1");
    fireEvent.pointerDown(canvasNode, {
      button: 0,
      clientX: 140,
      clientY: 100,
      pointerId: 1,
    });
    fireEvent.pointerUp(canvasNode, {
      clientX: 140,
      clientY: 100,
      pointerId: 1,
    });

    // The panel now edits the selected node's label, but never its x/y.
    expect(screen.getByLabelText("Etiqueta junction_1")).toBeVisible();
    expect(screen.queryByLabelText("X junction_1")).toBeNull();
    expect(screen.queryByLabelText("Y junction_1")).toBeNull();
  });

  it("deletes the selected component and removes its connections", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Delete case",
      description: "Component deletion",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    const diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Delete case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [],
      reaches: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agregar embalse" }));
    await user.click(screen.getByRole("button", { name: "Agregar union" }));

    const dataTransfer = {
      source: "",
      setData: vi.fn((_: string, value: string) => {
        dataTransfer.source = value;
      }),
      getData: vi.fn(() => dataTransfer.source),
    };
    fireEvent.dragStart(screen.getByTestId("hydraulic-node-out-reservoir_1"), {
      dataTransfer,
    });
    fireEvent.dragOver(screen.getByTestId("hydraulic-node-in-junction_1"));
    fireEvent.drop(screen.getByTestId("hydraulic-node-in-junction_1"), {
      dataTransfer,
    });
    expect(
      screen.getByTestId("hydraulic-link-reach_reservoir_1_junction_1"),
    ).toBeInTheDocument();

    // Select the reservoir and delete it through the properties panel.
    selectDiagramNode("reservoir_1");
    await user.click(
      screen.getByRole("button", { name: "Eliminar componente" }),
    );

    // The node, its reach, and the panel selection are all gone.
    expect(
      screen.queryByTestId("hydraulic-canvas-node-reservoir_1"),
    ).toBeNull();
    expect(
      screen.queryByTestId("hydraulic-link-reach_reservoir_1_junction_1"),
    ).toBeNull();
    expect(
      screen.getByTestId("hydraulic-canvas-node-junction_1"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Selecciona un objeto del diagrama para editar sus propiedades.",
      ),
    ).toBeVisible();
  });

  it("draws plant connection edges and routes edges between the node ports", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Edges case",
      description: "Edge routing",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    const diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Edges case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [],
      reaches: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agregar embalse" }));
    await user.click(screen.getByRole("button", { name: "Agregar union" }));
    await user.click(screen.getByRole("button", { name: "Agregar central" }));

    const dataTransfer = {
      source: "",
      setData: vi.fn((_: string, value: string) => {
        dataTransfer.source = value;
      }),
      getData: vi.fn(() => dataTransfer.source),
    };
    const link = (fromKey: string, toKey: string) => {
      fireEvent.dragStart(screen.getByTestId(`hydraulic-node-out-${fromKey}`), {
        dataTransfer,
      });
      fireEvent.dragOver(screen.getByTestId(`hydraulic-node-in-${toKey}`));
      fireEvent.drop(screen.getByTestId(`hydraulic-node-in-${toKey}`), {
        dataTransfer,
      });
    };

    // Reservoir output -> junction input draws a reach edge. Default positions:
    // reservoir_1 (120,80), junction_1 (300,110); node is 150x76. The edge must
    // leave the source's bottom port (195,156) and reach the target's top port
    // (375,110), not the node centers.
    link("reservoir_1", "junction_1");
    const reachPath = screen.getByTestId(
      "hydraulic-link-reach_reservoir_1_junction_1",
    );
    expect(reachPath.getAttribute("d")).toMatch(/^M 195 156/);
    expect(reachPath.getAttribute("d")).toMatch(/375 110$/);

    // Reservoir output -> plant input draws a visible intake edge from the
    // reservoir to the plant (the plant has no reach, only a unit intake).
    link("reservoir_1", "plant_1");
    const plantPath = screen.getByTestId(
      "hydraulic-plant-link-reservoir_1-plant_1",
    );
    expect(plantPath).toBeInTheDocument();
    expect(plantPath.getAttribute("d")).toMatch(/^M 195 156/);
    expect(plantPath.getAttribute("d")).toMatch(/555 180$/);
  });

  it("selects a plant connection edge and deletes only that link", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Plant link case",
      description: "Plant link deletion",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    const diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Plant link case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [],
      reaches: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agregar embalse" }));
    await user.click(screen.getByRole("button", { name: "Agregar central" }));

    const dataTransfer = {
      source: "",
      setData: vi.fn((_: string, value: string) => {
        dataTransfer.source = value;
      }),
      getData: vi.fn(() => dataTransfer.source),
    };
    fireEvent.dragStart(screen.getByTestId("hydraulic-node-out-reservoir_1"), {
      dataTransfer,
    });
    fireEvent.dragOver(screen.getByTestId("hydraulic-node-in-plant_1"));
    fireEvent.drop(screen.getByTestId("hydraulic-node-in-plant_1"), {
      dataTransfer,
    });

    // Clicking the plant edge selects the connection itself, not the plant.
    fireEvent.click(
      screen.getByTestId("hydraulic-plant-link-reservoir_1-plant_1"),
    );
    expect(
      screen.getByTestId("hydraulic-properties-plant-link-reservoir_1-plant_1"),
    ).toBeInTheDocument();

    // Deleting removes only the connection: both nodes stay on the canvas.
    await user.click(screen.getByRole("button", { name: "Eliminar conexion" }));
    expect(
      screen.queryByTestId("hydraulic-plant-link-reservoir_1-plant_1"),
    ).toBeNull();
    expect(
      screen.getByTestId("hydraulic-canvas-node-reservoir_1"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("hydraulic-canvas-node-plant_1"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Selecciona un objeto del diagrama para editar sus propiedades.",
      ),
    ).toBeVisible();
  });

  it("anchors reaches at the exact border point where the connection is dropped", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Anchor case",
      description: "Reach anchors",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    const diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Anchor case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [],
      reaches: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agregar embalse" }));
    await user.click(screen.getByRole("button", { name: "Agregar union" }));

    // reservoir_1 sits at (120,80) and junction_1 at (300,110); nodes are
    // 150x76. Starting the connection at x=150 on the source's bottom border
    // (anchor 0.2) and completing it at x=420 on the target's top border
    // (anchor 0.8) must pin the edge to those exact points instead of the
    // port centers.
    fireEvent.click(screen.getByTestId("hydraulic-node-out-reservoir_1"), {
      clientX: 150,
      clientY: 156,
    });
    fireEvent.click(screen.getByTestId("hydraulic-node-in-junction_1"), {
      clientX: 420,
      clientY: 110,
    });

    const reachPath = screen.getByTestId(
      "hydraulic-link-reach_reservoir_1_junction_1",
    );
    expect(reachPath.getAttribute("d")).toMatch(/^M 150 156/);
    expect(reachPath.getAttribute("d")).toMatch(/420 110$/);

    // Plant links anchor the same way: plant_1 sits at (480,180), so
    // completing the connection at x=600 on its top border pins the intake
    // edge at anchor 0.8 (x=600) instead of the port center (x=555).
    await user.click(screen.getByRole("button", { name: "Agregar central" }));
    fireEvent.click(screen.getByTestId("hydraulic-node-out-reservoir_1"), {
      clientX: 150,
      clientY: 156,
    });
    fireEvent.click(screen.getByTestId("hydraulic-node-in-plant_1"), {
      clientX: 600,
      clientY: 180,
    });
    const plantPath = screen.getByTestId(
      "hydraulic-plant-link-reservoir_1-plant_1",
    );
    expect(plantPath.getAttribute("d")).toMatch(/^M 150 156/);
    expect(plantPath.getAttribute("d")).toMatch(/600 180$/);
  });

  it("colors reaches by type and shows a reach type legend", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Reach colors case",
      description: "Reach type colors",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    const diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Reach colors case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [],
      reaches: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agregar embalse" }));
    await user.click(screen.getByRole("button", { name: "Agregar union" }));

    const dataTransfer = {
      source: "",
      setData: vi.fn((_: string, value: string) => {
        dataTransfer.source = value;
      }),
      getData: vi.fn(() => dataTransfer.source),
    };
    fireEvent.dragStart(screen.getByTestId("hydraulic-node-out-reservoir_1"), {
      dataTransfer,
    });
    fireEvent.dragOver(screen.getByTestId("hydraulic-node-in-junction_1"));
    fireEvent.drop(screen.getByTestId("hydraulic-node-in-junction_1"), {
      dataTransfer,
    });

    // A new reach defaults to river and is tinted with the river color.
    const reachPath = screen.getByTestId(
      "hydraulic-link-reach_reservoir_1_junction_1",
    );
    expect(reachPath).toHaveAttribute("data-reach-type", "river");
    expect(reachPath).toHaveAttribute("stroke", "#0072b2");

    // Changing the reach type through the panel recolors the edge.
    fireEvent.click(reachPath);
    await user.selectOptions(
      screen.getByLabelText("Tipo reach_reservoir_1_junction_1"),
      "spillway",
    );
    expect(reachPath).toHaveAttribute("data-reach-type", "spillway");

    // The canvas shows a legend for every reach type plus plant links.
    const legend = screen.getByTestId("hydraulic-reach-legend");
    expect(legend).toHaveTextContent("Rio");
    expect(legend).toHaveTextContent("Vertedero");
    expect(legend).toHaveTextContent("Central");
  });

  it("edits reservoir parameters and a storage-elevation curve, then shows reservoir validation errors", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    type CurvePoint = { x_value: number; y_value: number };
    type CurveSummary = {
      curve_set_id: number;
      version_number: number;
      version_label: string;
      points: CurvePoint[];
    };
    type ReservoirParams = {
      storage_min_hm3: number;
      storage_max_hm3: number;
      initial_storage_hm3: number;
      terminal_condition: string;
      terminal_storage_min_hm3: number | null;
      terminal_water_value_usd_per_hm3: number;
    };
    type DiagramNode = {
      layout_item_id: number;
      entity_type: string;
      entity_id: number;
      component_type: "reservoir" | "junction" | "plant";
      technical_key: string;
      display_name: string;
      x: number;
      y: number;
      z_index: number;
      reservoir?: ReservoirParams | null;
      storage_elevation_curve?: CurveSummary | null;
      available_curves?: CurveSummary[];
    };
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Reservoir case",
      description: "Hydraulic reservoir branch",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    let diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Reservoir case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [] as DiagramNode[],
      reaches: [] as Array<unknown>,
    };
    let lastPutBody: { nodes: DiagramNode[] } | null = null;
    const versions: unknown[] = [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "PUT"
        ) {
          const body = JSON.parse(String(init?.body)) as {
            nodes: DiagramNode[];
          };
          lastPutBody = body;
          diagram = {
            ...diagram,
            revision: "2",
            layout: {
              ...diagram.layout,
              layout_version: 2,
              revision: "2",
              layout_engine: "manual",
            },
            nodes: body.nodes.map((node, index) => {
              const base: DiagramNode = {
                ...node,
                layout_item_id: index + 1,
                entity_type:
                  node.component_type === "plant"
                    ? "case_hydraulic_plant"
                    : "case_hydraulic_node",
                entity_id: index + 1,
                z_index: index,
              };
              if (node.component_type !== "reservoir") return base;
              const points = node.storage_elevation_curve?.points ?? [];
              const summary: CurveSummary | null = points.length
                ? {
                    curve_set_id: 900,
                    version_number: 1,
                    version_label: "v1",
                    points,
                  }
                : null;
              return {
                ...base,
                reservoir: node.reservoir ?? null,
                storage_elevation_curve: summary,
                available_curves: summary ? [summary] : [],
              };
            }),
            reaches: [],
          };
          return new Response(JSON.stringify({ diagram }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram/validate" &&
          method === "POST"
        ) {
          return new Response(
            JSON.stringify({
              validation: {
                ok: false,
                summary: "Hydraulic topology has errors",
                errors: [
                  {
                    code: "storage_bounds_outside_curve_domain",
                    message:
                      "Reservoir reservoir_1 storage bounds fall outside the curve domain.",
                    entity_type: "case_hydraulic_node",
                    entity_id: 1,
                    technical_key: "reservoir_1",
                  },
                ],
                warnings: [],
              },
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agregar embalse" }));
    selectDiagramNode("reservoir_1");

    expect(screen.getByTestId("hydraulic-reservoir-reservoir_1")).toBeVisible();
    await user.clear(
      screen.getByLabelText("Almacenamiento minimo reservoir_1"),
    );
    await user.type(
      screen.getByLabelText("Almacenamiento minimo reservoir_1"),
      "5",
    );
    await user.clear(
      screen.getByLabelText("Almacenamiento maximo reservoir_1"),
    );
    await user.type(
      screen.getByLabelText("Almacenamiento maximo reservoir_1"),
      "50",
    );
    await user.clear(
      screen.getByLabelText("Almacenamiento inicial reservoir_1"),
    );
    await user.type(
      screen.getByLabelText("Almacenamiento inicial reservoir_1"),
      "20",
    );
    await user.selectOptions(
      screen.getByLabelText("Condicion terminal reservoir_1"),
      "min_terminal",
    );
    await user.type(
      screen.getByLabelText("Almacenamiento terminal minimo reservoir_1"),
      "10",
    );

    await user.click(
      screen.getByRole("button", {
        name: "Agregar punto de curva reservoir_1",
      }),
    );
    await user.type(
      screen.getByLabelText("Almacenamiento punto 1 reservoir_1"),
      "5",
    );
    await user.type(screen.getByLabelText("Cota punto 1 reservoir_1"), "700");
    await user.click(
      screen.getByRole("button", {
        name: "Agregar punto de curva reservoir_1",
      }),
    );
    await user.type(
      screen.getByLabelText("Almacenamiento punto 2 reservoir_1"),
      "50",
    );
    await user.type(screen.getByLabelText("Cota punto 2 reservoir_1"), "760");

    await user.click(screen.getByRole("button", { name: "Guardar diagrama" }));
    expect(await screen.findByText("Estado: saved")).toBeVisible();

    expect(lastPutBody).not.toBeNull();
    const savedNode = lastPutBody!.nodes[0];
    expect(savedNode.reservoir?.storage_max_hm3).toBe(50);
    expect(savedNode.reservoir?.terminal_condition).toBe("min_terminal");
    expect(savedNode.reservoir?.terminal_storage_min_hm3).toBe(10);
    expect(savedNode.storage_elevation_curve?.points).toEqual([
      { x_value: 5, y_value: 700 },
      { x_value: 50, y_value: 760 },
    ]);

    // The saved version is now selectable as an existing curve version.
    selectDiagramNode("reservoir_1");
    expect(screen.getByLabelText("Version de curva reservoir_1")).toHaveValue(
      "900",
    );

    await user.click(screen.getByRole("button", { name: "Validar topologia" }));
    expect(
      await screen.findByText("Hydraulic topology has errors"),
    ).toBeVisible();
    expect(
      screen.getByText(/storage bounds fall outside the curve domain/),
    ).toBeVisible();
  });

  it("edits a plant panel with a generation unit and flow-power curve, then shows unit validation errors", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    type CurvePoint = { x_value: number; y_value: number };
    type CurveSummary = {
      curve_set_id: number;
      version_number: number;
      version_label: string;
      points: CurvePoint[];
    };
    type Unit = {
      technical_key: string;
      display_name: string;
      is_active: boolean;
      intake_node_key: string | null;
      discharge_node_key: string | null;
      min_power_mw: number | null;
      max_power_mw: number | null;
      min_flow_m3s: number | null;
      max_flow_m3s: number | null;
      flow_power_curve?: (CurveSummary | { points: CurvePoint[] }) | null;
      available_curves?: CurveSummary[];
    };
    type DiagramNode = {
      layout_item_id: number;
      entity_type: string;
      entity_id: number;
      component_type: "reservoir" | "junction" | "plant";
      technical_key: string;
      display_name: string;
      x: number;
      y: number;
      z_index: number;
      plant?: {
        non_modeled: boolean;
        min_power_mw: number | null;
        max_power_mw: number | null;
      } | null;
      units?: Unit[];
    };
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Plant case",
      description: "Hydraulic plant branch",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    let diagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Plant case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [] as DiagramNode[],
      reaches: [] as Array<unknown>,
    };
    let lastPutBody: { nodes: DiagramNode[] } | null = null;
    let promoteCalls = 0;
    const versions: Array<{
      id: number;
      scenario_id: number;
      version_number: number;
      case_name: string;
      schema_version: string;
      period_count: number;
      asset_counts: Record<string, number>;
      created_at: string;
    }> = [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ diagram }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "PUT"
        ) {
          const body = JSON.parse(String(init?.body)) as {
            nodes: DiagramNode[];
          };
          lastPutBody = body;
          diagram = {
            ...diagram,
            revision: "2",
            layout: {
              ...diagram.layout,
              layout_version: 2,
              revision: "2",
              layout_engine: "manual",
            },
            nodes: body.nodes.map((node, index) => {
              const base: DiagramNode = {
                ...node,
                layout_item_id: index + 1,
                entity_type:
                  node.component_type === "plant"
                    ? "case_hydraulic_plant"
                    : "case_hydraulic_node",
                entity_id: index + 1,
                z_index: index,
              };
              if (node.component_type !== "plant") return base;
              const units = (node.units ?? []).map((unit) => {
                const points = unit.flow_power_curve?.points ?? [];
                const summary: CurveSummary | null = points.length
                  ? {
                      curve_set_id: 910,
                      version_number: 1,
                      version_label: "v1",
                      points,
                    }
                  : null;
                return {
                  ...unit,
                  flow_power_curve: summary,
                  available_curves: summary ? [summary] : [],
                };
              });
              return {
                ...base,
                plant: node.plant ?? {
                  non_modeled: false,
                  min_power_mw: null,
                  max_power_mw: null,
                },
                units,
              };
            }),
            reaches: [],
          };
          return new Response(JSON.stringify({ diagram }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram/validate" &&
          method === "POST"
        ) {
          return new Response(
            JSON.stringify({
              validation: {
                ok: false,
                summary: "Hydraulic topology has errors",
                errors: [
                  {
                    code: "inactive_or_equal_unit_nodes",
                    message:
                      "Unit unit_1 requires distinct active intake and discharge nodes.",
                    entity_type: "case_hydraulic_unit",
                    entity_id: 1,
                    technical_key: "unit_1",
                  },
                ],
                warnings: [],
              },
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram/v3-preview" &&
          method === "POST"
        ) {
          return new Response(
            JSON.stringify({
              validation: {
                ok: true,
                stale: false,
                summary: "Hydraulic v3 payload validated",
                errors: [],
                warnings: [],
                system_case: {
                  schema_version: "bess_system_dispatch.v3",
                  hydraulic_network: {
                    units: [{ id: "unit_1", plant_id: "plant_1" }],
                  },
                },
                julia_validation: { status: "ok" },
              },
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram/promote" &&
          method === "POST"
        ) {
          promoteCalls += 1;
          const version = {
            id: 81,
            scenario_id: 10,
            version_number: 1,
            case_name: "scenario_10_hydraulic_case",
            schema_version: "bess_system_dispatch.v3",
            period_count: 1,
            asset_counts: {},
            created_at: "2026-06-26T12:30:00Z",
          };
          versions.push(version);
          return new Response(JSON.stringify(version), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agregar union" }));
    await user.click(screen.getByRole("button", { name: "Agregar union" }));
    await user.click(screen.getByRole("button", { name: "Agregar central" }));
    selectDiagramNode("plant_1");

    expect(screen.getByTestId("hydraulic-plant-plant_1")).toBeVisible();
    await user.clear(screen.getByLabelText("Potencia maxima central plant_1"));
    await user.type(
      screen.getByLabelText("Potencia maxima central plant_1"),
      "60",
    );

    await user.click(
      screen.getByRole("button", { name: "Agregar unidad plant_1" }),
    );
    await user.selectOptions(
      screen.getByLabelText("Nodo de toma unit_1"),
      "junction_1",
    );
    await user.selectOptions(
      screen.getByLabelText("Nodo de descarga unit_1"),
      "junction_2",
    );
    await user.clear(screen.getByLabelText("Potencia maxima unit_1"));
    await user.type(screen.getByLabelText("Potencia maxima unit_1"), "30");
    await user.clear(screen.getByLabelText("Caudal maximo unit_1"));
    await user.type(screen.getByLabelText("Caudal maximo unit_1"), "40");

    await user.click(
      screen.getByRole("button", { name: "Agregar punto de curva unit_1" }),
    );
    await user.type(screen.getByLabelText("Caudal punto 1 unit_1"), "0");
    await user.type(screen.getByLabelText("Potencia punto 1 unit_1"), "0");
    await user.click(
      screen.getByRole("button", { name: "Agregar punto de curva unit_1" }),
    );
    await user.type(screen.getByLabelText("Caudal punto 2 unit_1"), "40");
    await user.type(screen.getByLabelText("Potencia punto 2 unit_1"), "30");

    await user.click(screen.getByRole("button", { name: "Guardar diagrama" }));
    expect(await screen.findByText("Estado: saved")).toBeVisible();

    expect(lastPutBody).not.toBeNull();
    const plantNode = lastPutBody!.nodes.find(
      (node) => node.component_type === "plant",
    )!;
    expect(plantNode.plant?.max_power_mw).toBe(60);
    expect(plantNode.units).toHaveLength(1);
    const savedUnit = plantNode.units![0];
    expect(savedUnit.technical_key).toBe("unit_1");
    expect(savedUnit.intake_node_key).toBe("junction_1");
    expect(savedUnit.discharge_node_key).toBe("junction_2");
    expect(savedUnit.max_power_mw).toBe(30);
    expect(savedUnit.max_flow_m3s).toBe(40);
    expect(savedUnit.flow_power_curve?.points).toEqual([
      { x_value: 0, y_value: 0 },
      { x_value: 40, y_value: 30 },
    ]);

    // Saved curve is now selectable as an existing version.
    selectDiagramNode("plant_1");
    expect(screen.getByLabelText("Version de curva unit_1")).toHaveValue("910");

    await user.click(
      screen.getByRole("button", { name: "Generar preview v3" }),
    );
    expect(
      await screen.findByText("Hydraulic v3 payload validated"),
    ).toBeVisible();
    expect(screen.getByText(/bess_system_dispatch\.v3/)).toBeVisible();
    expect(screen.getByText(/"id": "unit_1"/)).toBeVisible();

    const promoteButton = screen.getByRole("button", {
      name: "Promover version v3",
    });
    expect(promoteButton).toBeEnabled();
    await user.click(promoteButton);
    expect(await screen.findByText("Version v3 promovida: 1")).toBeVisible();
    expect(promoteCalls).toBe(1);

    await user.click(screen.getByRole("button", { name: "Validar topologia" }));
    expect(
      await screen.findByText("Hydraulic topology has errors"),
    ).toBeVisible();
    expect(
      screen.getByText(/distinct active intake and discharge nodes/),
    ).toBeVisible();
  });

  it("keeps newer local draft edits when an older save response arrives late", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const draft = {
      id: 3,
      scenario_id: 10,
      source_version_id: null,
      created_at: "2026-06-23T12:10:00Z",
      updated_at: "2026-06-23T12:10:00Z",
      document: {
        schema_version: "bess_editor_draft.v1",
        case: { name: "Base case" },
        source: null,
        pcc: { id: "bus_1", type: "bus" },
        grid: {
          id: "grid_1",
          import_power_max_mw: null,
          export_power_max_mw: null,
          prevent_simultaneous_grid_import_export: true,
        },
        assets: [],
        time_series: { sources: [] },
        solver: { name: "HiGHS", options: {} },
      },
    };
    let resolveSave: (response: Response) => void = () => undefined;
    let savedDocument = draft.document;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "GET") {
          return new Response(JSON.stringify({ draft }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "PUT") {
          savedDocument = JSON.parse(String(init?.body)).document;
          return new Promise<Response>((resolve) => {
            resolveSave = resolve;
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Draft estructurado" }),
    ).toBeVisible();
    await user.clear(screen.getByLabelText("Nombre del caso"));
    await user.type(screen.getByLabelText("Nombre del caso"), "First save");
    await user.click(screen.getByRole("button", { name: "Guardar draft" }));
    expect(await screen.findByText("Guardando")).toBeVisible();

    await user.clear(screen.getByLabelText("Nombre del caso"));
    await user.type(screen.getByLabelText("Nombre del caso"), "Newer local");
    resolveSave(
      new Response(
        JSON.stringify({
          ...draft,
          updated_at: "2026-06-23T12:11:00Z",
          document: savedDocument,
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Nombre del caso")).toHaveValue(
        "Newer local",
      );
    });
    expect(screen.getByText("Cambios sin guardar")).toBeVisible();
  });

  it("imports an uploaded CSV source into the TS-2 catalog with multiple mapped signals and shows the created set confirmation", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Catalog branch",
      created_at: "2026-07-04T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-07-04T12:00:00Z",
    };
    const draft = {
      id: 3,
      scenario_id: 10,
      source_version_id: null,
      created_at: "2026-07-04T12:10:00Z",
      updated_at: "2026-07-04T12:10:00Z",
      document: {
        schema_version: "bess_editor_draft.v1",
        case: { name: "Base case" },
        source: null,
        pcc: { id: "bus_1", type: "bus" },
        grid: {
          id: "grid_1",
          import_power_max_mw: null,
          export_power_max_mw: null,
          prevent_simultaneous_grid_import_export: true,
        },
        assets: [],
        time_series: { sources: [] },
        solver: { name: "HiGHS", options: {} },
      },
    };
    const uploadedSource = {
      id: "csv_source_1",
      kind: "csv",
      original_filename: "price.csv",
      media_type: "text/csv",
      checksum: "sha256:source123",
      columns: ["period_start", "hours", "buy_price", "sell_price"],
      preview_rows: [
        {
          period_start: "2026-01-01T00:00:00",
          hours: "1.0",
          buy_price: "55.0",
          sell_price: "45.0",
        },
      ],
      validation: { ok: true },
      validated_rows: [],
    };
    let lastImportBody: unknown = null;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "GET") {
          return new Response(JSON.stringify({ draft }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/draft/time-series-sources/upload" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ source: uploadedSource }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path ===
            "/api/scenarios/10/draft/time-series-sources/csv_source_1/catalog-import" &&
          method === "POST"
        ) {
          lastImportBody = JSON.parse(String(init?.body));
          return new Response(
            JSON.stringify({
              time_series_set: {
                id: 91,
                project_id: 1,
                name: "Dual price Jan 2026",
                version_number: 1,
                version_label: "v1",
                revision_number: 1,
                data_kind: "real",
                timezone: "America/Santiago",
                status: "validated",
                content_hash: "sha256:cataloghash123",
                source_checksum: "sha256:source123",
                signal_count: 1,
                revision_metadata: {
                  mapping: {
                    timestamp_column: "period_start",
                    duration_hours_column: "hours",
                    signals: [
                      {
                        source_column: "buy_price",
                        signal_key: "import_price_usd_per_mwh",
                        source_unit: "USD/MWh",
                        canonical_unit: "USD/MWh",
                      },
                      {
                        source_column: "sell_price",
                        signal_key: "export_price_usd_per_mwh",
                        source_unit: "USD/MWh",
                        canonical_unit: "USD/MWh",
                      },
                    ],
                  },
                },
                period_count: 2,
                source: {
                  original_filename: "price.csv",
                  media_type: "text/csv",
                  checksum: "sha256:source123",
                },
                signals: [
                  {
                    signal_key: "import_price_usd_per_mwh",
                    source_column: "buy_price",
                    source_unit: "USD/MWh",
                    unit: "USD/MWh",
                    entity_type: null,
                    entity_key: null,
                  },
                  {
                    signal_key: "export_price_usd_per_mwh",
                    source_column: "sell_price",
                    source_unit: "USD/MWh",
                    unit: "USD/MWh",
                    entity_type: null,
                    entity_key: null,
                  },
                ],
                periods: [
                  {
                    period_index: 0,
                    timestamp_start: "2026-01-01T00:00:00-03:00",
                    timestamp_end: "2026-01-01T01:00:00-03:00",
                    duration_hours: 1,
                  },
                  {
                    period_index: 1,
                    timestamp_start: "2026-01-01T01:00:00-03:00",
                    timestamp_end: "2026-01-01T02:00:00-03:00",
                    duration_hours: 1,
                  },
                ],
                values: [
                  {
                    period_index: 0,
                    signal_key: "import_price_usd_per_mwh",
                    value_numeric: 55,
                  },
                  {
                    period_index: 0,
                    signal_key: "export_price_usd_per_mwh",
                    value_numeric: 45,
                  },
                  {
                    period_index: 1,
                    signal_key: "import_price_usd_per_mwh",
                    value_numeric: 60,
                  },
                  {
                    period_index: 1,
                    signal_key: "export_price_usd_per_mwh",
                    value_numeric: 48,
                  },
                ],
              },
            }),
            {
              status: 201,
              headers: { "Content-Type": "application/json" },
            },
          );
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Draft estructurado" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        /embedded time series is this draft's legacy storage/,
      ),
    ).toBeVisible();
    await user.upload(
      screen.getByLabelText("Source file"),
      new File(
        ["period_start,hours,spot_price\n2026-01-01T00:00:00,1.0,55.0\n"],
        "price.csv",
        { type: "text/csv" },
      ),
    );
    await user.click(screen.getByRole("button", { name: "Upload source" }));
    expect(await screen.findByText("price.csv")).toBeVisible();

    expect(
      screen.getByRole("heading", { name: "Import mapped columns to catalog" }),
    ).toBeVisible();
    expect(
      screen.queryByText("TS-2 catalog import"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Extract legacy series to catalog" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Extraction set name")).toBeVisible();

    await user.clear(screen.getByLabelText("Catalog set name"));
    await user.type(
      screen.getByLabelText("Catalog set name"),
      "Dual price Jan 2026",
    );
    await user.clear(screen.getByLabelText("Catalog version label"));
    await user.type(screen.getByLabelText("Catalog version label"), "v1");
    await user.selectOptions(
      screen.getByLabelText("Catalog timestamp column"),
      "period_start",
    );
    await user.selectOptions(
      screen.getByLabelText("Catalog duration column"),
      "hours",
    );
    await user.selectOptions(
      screen.getByLabelText("Mapped source column 1"),
      "buy_price",
    );
    await user.selectOptions(
      screen.getByLabelText("Canonical signal 1"),
      "import_price_usd_per_mwh",
    );
    await user.clear(screen.getByLabelText("Source unit 1"));
    await user.type(screen.getByLabelText("Source unit 1"), "USD/MWh");
    await user.click(
      screen.getByRole("button", { name: "Add signal mapping" }),
    );
    await user.selectOptions(
      screen.getByLabelText("Mapped source column 2"),
      "sell_price",
    );
    await user.selectOptions(
      screen.getByLabelText("Canonical signal 2"),
      "export_price_usd_per_mwh",
    );
    await user.clear(screen.getByLabelText("Source unit 2"));
    await user.type(screen.getByLabelText("Source unit 2"), "USD/MWh");
    await user.click(screen.getByRole("button", { name: "Import to catalog" }));

    expect(lastImportBody).toEqual({
      set_name: "Dual price Jan 2026",
      version_label: "v1",
      data_kind: "real",
      timezone: "America/Santiago",
      timestamp_column: "period_start",
      duration_hours_column: "hours",
      signal_mappings: [
        {
          source_column: "buy_price",
          signal_key: "import_price_usd_per_mwh",
          source_unit: "USD/MWh",
        },
        {
          source_column: "sell_price",
          signal_key: "export_price_usd_per_mwh",
          source_unit: "USD/MWh",
        },
      ],
    });
    expect(await screen.findByText("Catalog import created")).toBeVisible();
    expect(screen.getByText("Dual price Jan 2026")).toBeVisible();
    expect(screen.getByText("import_price_usd_per_mwh")).toBeVisible();
    expect(screen.getByText("2 periods")).toBeVisible();
    expect(screen.getByText("Revision 1")).toBeVisible();
    expect(screen.getByText("America/Santiago (IANA)")).toBeVisible();
  });

  it("lists available XLSX sheets after upload and re-imports the preview when the analyst picks another one", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Catalog branch",
      created_at: "2026-07-04T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-07-04T12:00:00Z",
    };
    const draft = {
      id: 3,
      scenario_id: 10,
      source_version_id: null,
      created_at: "2026-07-04T12:10:00Z",
      updated_at: "2026-07-04T12:10:00Z",
      document: {
        schema_version: "bess_editor_draft.v1",
        case: { name: "Base case" },
        source: null,
        pcc: { id: "bus_1", type: "bus" },
        grid: {
          id: "grid_1",
          import_power_max_mw: null,
          export_power_max_mw: null,
          prevent_simultaneous_grid_import_export: true,
        },
        assets: [],
        time_series: { sources: [] },
        solver: { name: "HiGHS", options: {} },
      },
    };
    const sheet1Source = {
      id: "xlsx_source_1",
      kind: "xlsx",
      original_filename: "prices.xlsx",
      media_type:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      checksum: "sha256:xlsx1",
      selected_sheet: "Sheet1",
      available_sheets: ["Sheet1", "Sheet2"],
      columns: ["period_start", "hours", "spot_price"],
      preview_rows: [
        {
          period_start: "2026-01-01T00:00:00",
          hours: "1.0",
          spot_price: "55.0",
        },
      ],
    };
    const sheet2Source = {
      id: "xlsx_source_2",
      kind: "xlsx",
      original_filename: "prices.xlsx",
      media_type:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      checksum: "sha256:xlsx2",
      selected_sheet: "Sheet2",
      available_sheets: ["Sheet1", "Sheet2"],
      columns: ["period_start", "hours", "demand"],
      preview_rows: [
        { period_start: "2026-01-01T00:00:00", hours: "1.0", demand: "12.5" },
      ],
    };
    const uploadedSheetNames: (string | null)[] = [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "GET") {
          return new Response(JSON.stringify({ draft }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/draft/time-series-sources/upload" &&
          method === "POST"
        ) {
          const body = init?.body as FormData;
          const sheetName = String(body.get("sheet_name") || "") || null;
          uploadedSheetNames.push(sheetName);
          const source = sheetName === "Sheet2" ? sheet2Source : sheet1Source;
          return new Response(JSON.stringify({ source }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Draft estructurado" }),
    ).toBeVisible();
    await user.upload(
      screen.getByLabelText("Source file"),
      new File(["xlsx-bytes"], "prices.xlsx", {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Upload source" }));
    expect(await screen.findByText("prices.xlsx")).toBeVisible();
    expect(screen.getByText("Selected sheet: Sheet1")).toBeVisible();

    const sheetSelect = screen.getByLabelText("Sheet") as HTMLSelectElement;
    expect(
      Array.from(sheetSelect.options).map((option) => option.value),
    ).toEqual(["Sheet1", "Sheet2"]);
    expect(sheetSelect.value).toBe("Sheet1");

    await user.selectOptions(sheetSelect, "Sheet2");

    expect(await screen.findByText("Selected sheet: Sheet2")).toBeVisible();
    expect(
      screen.getByText("Detected columns: period_start, hours, demand"),
    ).toBeVisible();
    expect(uploadedSheetNames).toEqual([null, "Sheet2"]);
  });

  it("lets analysts inspect, validate, stale, and promote a generated system_case once", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const generatedCase = {
      schema_version: "bess_system_dispatch.v1",
      case_name: "Base case",
      time_series: [{ duration_hours: 1, price_usd_per_mwh: 55 }],
      assets: [{ type: "battery", id: "battery_1" }],
    };
    let draft = {
      id: 3,
      scenario_id: 10,
      source_version_id: null,
      created_at: "2026-06-23T12:10:00Z",
      updated_at: "2026-06-23T12:10:00Z",
      document: {
        schema_version: "bess_editor_draft.v1",
        case: { name: "Base case" },
        source: null,
        pcc: { id: "bus_1", type: "bus" },
        grid: {
          id: "grid_1",
          import_power_max_mw: null,
          export_power_max_mw: null,
          prevent_simultaneous_grid_import_export: true,
        },
        assets: [
          {
            id: "battery_1",
            type: "battery",
            charge_power_max_mw: 4,
            discharge_power_max_mw: 4,
            energy_min_mwh: 0,
            energy_max_mwh: 8,
            initial_energy_mwh: 4,
            charge_efficiency: 0.95,
            discharge_efficiency: 0.95,
            degradation_cost_per_mwh_delta_soc: 0,
            terminal_condition: "equal_initial",
            terminal_energy_min_mwh: null,
            prevent_simultaneous_charge_discharge: true,
            degradation_linear_delta_soc: true,
          },
        ],
        time_series: { sources: [] },
        solver: { name: "HiGHS", options: {} },
        generated_system_case: {
          system_case: generatedCase,
          validation: {
            ok: true,
            phase: "julia",
            message: "Validation succeeded",
            payload: { status: "ok", case_name: "Base case" },
          },
        },
      },
    };
    let promotedVersions: unknown[] = [];
    let promoteCalls = 0;
    let resolvePromote: () => void = () => undefined;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "GET") {
          return new Response(JSON.stringify({ draft }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "PUT") {
          const body = JSON.parse(String(init?.body));
          draft = {
            ...draft,
            updated_at: "2026-06-23T12:12:00Z",
            document: body.document,
          };
          return new Response(JSON.stringify(draft), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft/generated-system-case") {
          return new Response(JSON.stringify({ system_case: generatedCase }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/draft/generated-system-case/validate" &&
          method === "POST"
        ) {
          const currentCase = {
            ...generatedCase,
            case_name: draft.document.case.name,
          };
          const generated_system_case = {
            system_case: currentCase,
            validation: {
              ok: true,
              phase: "julia",
              message: "Validation succeeded",
              payload: { status: "ok", case_name: currentCase.case_name },
            },
          };
          draft = {
            ...draft,
            document: { ...draft.document, generated_system_case },
          };
          return new Response(
            JSON.stringify({
              status: "ok",
              phase: "julia",
              message: "Validation succeeded",
              validation: generated_system_case.validation.payload,
              system_case: currentCase,
              generated_system_case,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/scenarios/10/draft/generated-system-case/promote" &&
          method === "POST"
        ) {
          promoteCalls += 1;
          return new Promise<Response>((resolve) => {
            resolvePromote = () => {
              const version = {
                id: 41,
                scenario_id: 10,
                version_number: 1,
                case_name: draft.document.case.name,
                schema_version: "bess_system_dispatch.v1",
                period_count: 1,
                asset_counts: { battery: 1 },
                created_at: "2026-06-23T12:13:00Z",
              };
              promotedVersions = [version];
              resolve(
                new Response(JSON.stringify(version), {
                  status: 201,
                  headers: { "Content-Type": "application/json" },
                }),
              );
            };
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: promotedVersions }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Draft estructurado" }),
    ).toBeVisible();
    expect(screen.getByText("Ultima validacion guardada")).toBeVisible();
    expect(screen.getByText("Validation succeeded")).toBeVisible();
    expect(
      (screen.getByLabelText("Generated system_case") as HTMLTextAreaElement)
        .value,
    ).toContain('"case_name": "Base case"');

    await user.clear(screen.getByLabelText("Nombre del caso"));
    await user.type(screen.getByLabelText("Nombre del caso"), "Summer case");
    expect(
      screen.getByText("Validacion stale; valida de nuevo antes de promover."),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Guardar draft" }));
    expect(await screen.findByText("Guardado")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Generar preview" }));
    expect(
      (screen.getByLabelText("Generated system_case") as HTMLTextAreaElement)
        .value,
    ).toContain('"time_series"');
    await user.click(screen.getByRole("button", { name: "Validar con Julia" }));
    expect(await screen.findByText("Validacion vigente")).toBeVisible();

    const promoteButton = screen.getByRole("button", {
      name: "Promover version",
    });
    await user.click(promoteButton);
    await user.click(promoteButton);
    expect(promoteCalls).toBe(1);
    resolvePromote();

    expect(
      await screen.findByRole("heading", { name: "Base case" }),
    ).toBeVisible();
    expect(screen.getByText("Version 1")).toBeVisible();
    expect(screen.getByText(/Summer case/)).toBeVisible();
  });

  it("shows topology and parameter provenance on the generated system_case panel", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const generatedCase = {
      schema_version: "bess_system_dispatch.v1",
      case_name: "Base case",
      time_series: [{ duration_hours: 1, price_usd_per_mwh: 55 }],
      assets: [{ type: "battery", id: "battery_1" }],
    };
    const draft = {
      id: 3,
      scenario_id: 10,
      source_version_id: null,
      created_at: "2026-06-23T12:10:00Z",
      updated_at: "2026-06-23T12:10:00Z",
      document: {
        schema_version: "bess_editor_draft.v1",
        case: { name: "Base case" },
        source: null,
        pcc: { id: "bus_1", type: "bus" },
        grid: {
          id: "grid_1",
          import_power_max_mw: null,
          export_power_max_mw: null,
          prevent_simultaneous_grid_import_export: true,
        },
        assets: [
          {
            id: "battery_1",
            type: "battery",
            charge_power_max_mw: 4,
            discharge_power_max_mw: 4,
            energy_min_mwh: 0,
            energy_max_mwh: 8,
            initial_energy_mwh: 4,
            charge_efficiency: 0.95,
            discharge_efficiency: 0.95,
            degradation_cost_per_mwh_delta_soc: 0,
            terminal_condition: "equal_initial",
            terminal_energy_min_mwh: null,
            prevent_simultaneous_charge_discharge: true,
            degradation_linear_delta_soc: true,
          },
        ],
        time_series: { sources: [] },
        solver: { name: "HiGHS", options: {} },
        generated_system_case: {
          system_case: generatedCase,
          validation: {
            ok: true,
            phase: "julia",
            message: "Validation succeeded",
            payload: { status: "ok", case_name: "Base case" },
          },
          topology: { content_hash: "topo1111hash2222aaaa3333" },
          parameters: { content_hash: "param4444hash5555bbbb6666" },
        },
      },
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/draft" && method === "GET") {
          return new Response(JSON.stringify({ draft }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Draft estructurado" }),
    ).toBeVisible();
    expect(screen.getByText("Validation succeeded")).toBeVisible();
    expect(screen.getByText("topo1111hash")).toBeVisible();
    expect(screen.getByText("param4444has")).toBeVisible();
  });

  it("keeps expert version paste/upload, immutable detail, and protected delete visible", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const validCase = {
      schema_version: "bess_system_dispatch.v1",
      case_name: "expert_case",
      time_series: [{ duration_hours: 1, price_usd_per_mwh: 55 }],
      assets: [{ type: "battery", id: "battery_1" }],
    };
    const versions: Array<{
      id: number;
      scenario_id: number;
      version_number: number;
      case_name: string;
      schema_version: string;
      period_count: number;
      asset_counts: Record<string, number>;
      created_at: string;
      system_case_json: unknown;
      validation_payload: unknown;
      generation_metadata: Record<string, unknown>;
    }> = [];
    let runs: Array<{
      id: number;
      scenario_version_id: number;
      status: string;
      created_at: string;
    }> = [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions" && method === "GET") {
          return new Response(JSON.stringify({ versions }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions" && method === "POST") {
          const body = JSON.parse(String(init?.body));
          try {
            JSON.parse(String(body.system_case_json));
          } catch {
            return new Response(
              JSON.stringify({
                status: "error",
                phase: "json",
                message: "Malformed JSON: expected value",
              }),
              {
                status: 400,
                headers: { "Content-Type": "application/json" },
              },
            );
          }
          const version = {
            id: 41,
            scenario_id: 10,
            version_number: 1,
            case_name: "expert_case",
            schema_version: "bess_system_dispatch.v1",
            period_count: 1,
            asset_counts: { battery: 1 },
            created_at: "2026-06-23T12:13:00Z",
            system_case_json: validCase,
            validation_payload: { status: "ok", case_name: "expert_case" },
            generation_metadata: {},
          };
          versions.push(version);
          return new Response(JSON.stringify(version), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions/upload" && method === "POST") {
          const version = {
            id: 42,
            scenario_id: 10,
            version_number: 2,
            case_name: "uploaded_case",
            schema_version: "bess_system_dispatch.v1",
            period_count: 1,
            asset_counts: { battery: 1 },
            created_at: "2026-06-23T12:14:00Z",
            system_case_json: { ...validCase, case_name: "uploaded_case" },
            validation_payload: { status: "ok", case_name: "uploaded_case" },
            generation_metadata: {},
          };
          versions.push(version);
          runs = [
            {
              id: 99,
              scenario_version_id: 42,
              status: "queued",
              created_at: "2026-06-23T12:15:00Z",
            },
          ];
          return new Response(JSON.stringify(version), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path.startsWith("/api/scenario-versions/") && method === "GET") {
          const id = Number(path.split("/").at(-1));
          const version = versions.find((item) => item.id === id);
          return new Response(JSON.stringify({ scenario_version: version }), {
            headers: { "Content-Type": "application/json" },
            status: version ? 200 : 404,
          });
        }
        if (path.startsWith("/api/scenario-versions/") && method === "DELETE") {
          const id = Number(path.split("/").at(-1));
          if (runs.some((run) => run.scenario_version_id === id)) {
            return new Response(
              JSON.stringify({
                detail:
                  "scenario versions referenced by runs cannot be deleted",
              }),
              {
                status: 409,
                headers: { "Content-Type": "application/json" },
              },
            );
          }
          const index = versions.findIndex((version) => version.id === id);
          const [deleted] = versions.splice(index, 1);
          return new Response(JSON.stringify({ deleted_version: deleted }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Base case" }),
    ).toBeVisible();
    await user.click(screen.getByLabelText("system_case JSON"));
    await user.paste("{bad");
    await user.click(screen.getByRole("button", { name: "Crear version" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Malformed JSON",
    );
    expect(screen.getByText("Aun no hay versiones inmutables.")).toBeVisible();

    await user.clear(screen.getByLabelText("system_case JSON"));
    await user.click(screen.getByLabelText("system_case JSON"));
    await user.paste(JSON.stringify(validCase));
    await user.click(screen.getByRole("button", { name: "Crear version" }));
    expect(await screen.findByText("Version 1")).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Version 1" }));
    expect(
      await screen.findByRole("heading", { name: "Version 1" }),
    ).toBeVisible();
    expect(screen.getAllByText("expert_case").length).toBeGreaterThan(0);
    expect(screen.queryByText(/"time_series"/)).not.toBeInTheDocument();
    await user.click(screen.getByText("Ver snapshot tecnico"));
    expect(await screen.findByText(/"time_series"/)).toBeVisible();

    await user.click(screen.getByRole("link", { name: "Base case" }));
    await screen.findByRole("heading", { name: "Base case" });
    await user.upload(
      screen.getByLabelText("Subir system_case JSON"),
      new File(
        [JSON.stringify({ ...validCase, case_name: "uploaded_case" })],
        "uploaded.json",
        {
          type: "application/json",
        },
      ),
    );
    await user.click(screen.getByRole("button", { name: "Subir version" }));
    expect(await screen.findByText("Version 2")).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Eliminar version 2" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Confirmar eliminar version 2" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "referenced by runs",
    );
    expect(screen.getByText("Version 2")).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Eliminar version 1" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Confirmar eliminar version 1" }),
    );
    await waitFor(() => {
      expect(screen.queryByText("Version 1")).not.toBeInTheDocument();
    });
  });

  it("shows topology and parameter provenance on scenario version detail, with graceful fallback for versions without it", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const versionWithProvenance = {
      id: 41,
      scenario_id: 10,
      version_number: 1,
      case_name: "structured_case",
      schema_version: "bess_system_dispatch.v1",
      period_count: 1,
      asset_counts: { battery: 1 },
      created_at: "2026-06-23T12:13:00Z",
      system_case_json: { case_name: "structured_case" },
      validation_payload: { status: "ok" },
      generation_metadata: {
        kind: "structured_draft",
        topology: { content_hash: "aaaa1111bbbb2222cccc3333" },
        parameters: { content_hash: "dddd4444eeee5555ffff6666" },
      },
    };
    const legacyVersion = {
      id: 42,
      scenario_id: 10,
      version_number: 2,
      case_name: "legacy_case",
      schema_version: "bess_system_dispatch.v1",
      period_count: 1,
      asset_counts: { battery: 1 },
      created_at: "2026-06-23T12:14:00Z",
      system_case_json: { case_name: "legacy_case" },
      validation_payload: { status: "ok" },
      generation_metadata: {},
    };
    const versions = [versionWithProvenance, legacyVersion];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path.startsWith("/api/scenario-versions/") && method === "GET") {
          const id = Number(path.split("/").at(-1));
          const version = versions.find((item) => item.id === id);
          return new Response(JSON.stringify({ scenario_version: version }), {
            headers: { "Content-Type": "application/json" },
            status: version ? 200 : 404,
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(await screen.findByText("Version 1")).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Version 1" }));
    expect(
      await screen.findByRole("heading", { name: "Version 1" }),
    ).toBeVisible();
    expect(screen.getByText("Draft estructurado")).toBeVisible();
    expect(screen.getByText("aaaa1111bbbb")).toBeVisible();
    expect(screen.getByText("dddd4444eeee")).toBeVisible();

    await user.click(screen.getByRole("link", { name: "Base case" }));
    await screen.findByRole("heading", { name: "Base case" });
    await user.click(screen.getByRole("link", { name: "Version 2" }));
    expect(
      await screen.findByRole("heading", { name: "Version 2" }),
    ).toBeVisible();
    expect(screen.getAllByText("Sin datos de procedencia").length).toBe(2);
  });

  it("shows which input variant produced each run in the case run list", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const defaultVersion = {
      id: 41,
      scenario_id: 10,
      version_number: 1,
      case_name: "dispatch_case",
      schema_version: "bess_system_dispatch.v1",
      period_count: 3,
      asset_counts: { battery: 1 },
      created_at: "2026-07-28T12:00:00Z",
      generation_metadata: {
        kind: "case_input_variant",
        input_variant: { id: 5, display_name: "Default" },
      },
    };
    const stressVersion = {
      id: 42,
      scenario_id: 10,
      version_number: 2,
      case_name: "dispatch_case",
      schema_version: "bess_system_dispatch.v1",
      period_count: 3,
      asset_counts: { battery: 1 },
      created_at: "2026-07-28T12:05:00Z",
      generation_metadata: {
        kind: "case_input_variant",
        input_variant: { id: 6, display_name: "Stress prices" },
      },
    };
    const legacyVersion = {
      id: 43,
      scenario_id: 10,
      version_number: 3,
      case_name: "legacy_case",
      schema_version: "bess_system_dispatch.v1",
      period_count: 3,
      asset_counts: { battery: 1 },
      created_at: "2026-07-28T12:10:00Z",
      generation_metadata: {},
    };
    const versions = [defaultVersion, stressVersion, legacyVersion];
    const runs = [
      {
        id: 101,
        scenario_version_id: 41,
        status: "succeeded",
        created_at: "2026-07-28T12:01:00Z",
        started_at: null,
        finished_at: null,
        duration_seconds: null,
        exit_code: null,
        error_message: "",
        stdout: "",
        stderr: "",
      },
      {
        id: 102,
        scenario_version_id: 42,
        status: "succeeded",
        created_at: "2026-07-28T12:06:00Z",
        started_at: null,
        finished_at: null,
        duration_seconds: null,
        exit_code: null,
        error_message: "",
        stdout: "",
        stderr: "",
      },
      {
        id: 103,
        scenario_version_id: 43,
        status: "succeeded",
        created_at: "2026-07-28T12:11:00Z",
        started_at: null,
        finished_at: null,
        duration_seconds: null,
        exit_code: null,
        error_message: "",
        stdout: "",
        stderr: "",
      },
    ];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/case/variants") {
          return new Response(
            JSON.stringify({
              case: {
                id: 1,
                scenario_id: 10,
                case_key: "scenario_10_case",
                display_name: "Base case",
                updated_at: "2026-07-06T12:00:00Z",
              },
              default_variant_id: null,
              variants: [],
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets") {
          return new Response(JSON.stringify({ time_series_sets: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText("Run 101")).toBeVisible();
    const defaultItem = screen.getByText("Run 101").closest("li")!;
    const stressItem = screen.getByText("Run 102").closest("li")!;
    const legacyItem = screen.getByText("Run 103").closest("li")!;
    expect(within(defaultItem).getByText(/Variante: Default/)).toBeVisible();
    expect(
      within(stressItem).getByText(/Variante: Stress prices/),
    ).toBeVisible();
    expect(within(legacyItem).queryByText(/Variante:/)).not.toBeInTheDocument();
  });

  it("shows run detail provenance inherited from its scenario version", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Initial modeling branch",
      created_at: "2026-06-23T12:05:00Z",
    };
    const version = {
      id: 41,
      scenario_id: 10,
      version_number: 3,
      case_name: "hydraulic_case",
      schema_version: "bess_system_dispatch.v3",
      period_count: 2,
      asset_counts: { hydro: 1 },
      created_at: "2026-06-23T12:14:00Z",
      system_case_json: { case_name: "hydraulic_case" },
      validation_payload: { status: "ok" },
      generation_metadata: {
        kind: "hydraulic_diagram_v3",
        topology: { content_hash: "1111aaaa2222bbbb3333cccc" },
        parameters: { content_hash: "4444dddd5555eeee6666ffff" },
      },
    };
    const run = {
      id: 99,
      scenario_version_id: 41,
      status: "failed",
      created_at: "2026-06-23T12:15:00Z",
      started_at: "2026-06-23T12:15:01Z",
      finished_at: "2026-06-23T12:15:03Z",
      duration_seconds: 1,
      exit_code: 1,
      error_message: "solver failed",
      stdout: "",
      stderr: "",
      trigger_type: "manual",
      triggered_by: "internal_analyst",
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/runs/99") {
          return new Response(JSON.stringify({ run }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenario-versions/41" && method === "GET") {
          return new Response(JSON.stringify({ scenario_version: version }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Run 99" }),
    ).toBeVisible();
    expect(await screen.findByText("Diagrama hidraulico v3")).toBeVisible();
    expect(screen.getByText("1111aaaa2222")).toBeVisible();
    expect(screen.getByText("4444dddd5555")).toBeVisible();
  });

  it("visually distinguishes topology-stale from parameters-stale hydraulic v3 validation", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/hydraulic-diagram",
    );
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Hydraulic branch",
      created_at: "2026-06-26T12:05:00Z",
    };
    const project = {
      id: 1,
      name: "Hydro PMGD",
      description: "Hydraulic workspace",
      created_at: "2026-06-26T12:00:00Z",
    };
    let getCount = 0;
    const baseDiagram = {
      scenario_id: 10,
      optimization_case: {
        id: 4,
        scenario_id: 10,
        case_key: "scenario_10_hydraulic_case",
        display_name: "Base case",
        updated_at: "2026-06-26T12:10:00Z",
      },
      hydraulic_system: {
        id: 5,
        project_id: 1,
        system_key: "default_hydraulic_system",
        display_name: "Default hydraulic system",
      },
      layout: {
        id: 6,
        case_id: 4,
        layout_key: "default",
        layout_engine: "auto_dag",
        layout_version: 1,
        revision: "1",
        viewport: { x: 0, y: 0, zoom: 1 },
        updated_at: "2026-06-26T12:10:00Z",
        updated_by: "internal_analyst",
      },
      revision: "1",
      nodes: [] as unknown[],
      reaches: [] as unknown[],
    };
    const topologyStaleValidation = {
      kind: "hydraulic_v3_preview",
      ok: false,
      stale: true,
      status: "stale",
      summary: "Hydraulic v3 validation is stale after topology edits",
      errors: [],
      warnings: [],
      topology_stale: true,
      parameters_stale: false,
    };
    const parametersStaleValidation = {
      kind: "hydraulic_v3_preview",
      ok: false,
      stale: true,
      status: "stale",
      summary: "Hydraulic v3 validation is stale after parameters edits",
      errors: [],
      warnings: [],
      topology_stale: false,
      parameters_stale: true,
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "POST"
        ) {
          return new Response(
            JSON.stringify({
              diagram: { ...baseDiagram, validation: topologyStaleValidation },
            }),
            { status: 201, headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/scenarios/10/hydraulic-diagram" &&
          method === "GET"
        ) {
          getCount += 1;
          return new Response(
            JSON.stringify({
              diagram: {
                ...baseDiagram,
                validation: parametersStaleValidation,
              },
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Diagrama hidraulico" }),
    ).toBeVisible();
    expect(await screen.findByText("Topologia desactualizada")).toBeVisible();
    expect(
      screen.queryByText("Parametros desactualizados"),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Recargar diagrama" }));
    expect(await screen.findByText("Parametros desactualizados")).toBeVisible();
    expect(
      screen.queryByText("Topologia desactualizada"),
    ).not.toBeInTheDocument();
    expect(getCount).toBe(1);
  });

  it("lets internal users create projects and scenarios, then refresh a direct scenario link", async () => {
    window.history.replaceState({}, "", "/react/projects");
    const projects: Array<{
      id: number;
      name: string;
      description: string;
      created_at: string;
    }> = [];
    const scenarios: Array<{
      id: number;
      project_id: number;
      name: string;
      description: string;
      created_at: string;
    }> = [];
    let transientProjectFailure = true;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects" && method === "GET") {
          return new Response(JSON.stringify({ projects }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects" && method === "POST") {
          if (transientProjectFailure) {
            transientProjectFailure = false;
            return new Response(
              JSON.stringify({ detail: "temporary outage" }),
              {
                status: 503,
                headers: { "Content-Type": "application/json" },
              },
            );
          }
          const body = JSON.parse(String(init?.body));
          const project = {
            id: 1,
            name: body.name,
            description: body.description,
            created_at: "2026-06-23T12:00:00Z",
          };
          projects.push(project);
          return new Response(JSON.stringify(project), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project: projects[0] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/scenarios" && method === "GET") {
          return new Response(JSON.stringify({ scenarios }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/scenarios" && method === "POST") {
          const body = JSON.parse(String(init?.body));
          const scenario = {
            id: 10,
            project_id: 1,
            name: body.name,
            description: body.description,
            created_at: "2026-06-23T12:05:00Z",
          };
          scenarios.push(scenario);
          return new Response(JSON.stringify(scenario), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario: scenarios[0] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Proyectos" }),
    ).toBeVisible();
    expect(
      screen.getByText("Crea un proyecto para comenzar a modelar escenarios."),
    ).toBeVisible();

    await user.type(
      screen.getByLabelText("Nombre del proyecto"),
      "Hybrid PMGD",
    );
    await user.type(
      screen.getByLabelText("Descripcion del proyecto"),
      "Analyst workspace",
    );
    await user.click(screen.getByRole("button", { name: "Crear proyecto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "temporary outage",
    );
    expect(screen.getByLabelText("Nombre del proyecto")).toHaveValue(
      "Hybrid PMGD",
    );

    await user.click(screen.getByRole("button", { name: "Crear proyecto" }));
    expect(
      await screen.findByRole("link", { name: "Hybrid PMGD" }),
    ).toBeVisible();

    await user.click(screen.getByRole("link", { name: "Hybrid PMGD" }));
    expect(
      await screen.findByRole("heading", { name: "Hybrid PMGD" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Crea un escenario para guardar variantes del proyecto.",
      ),
    ).toBeVisible();

    await user.type(screen.getByLabelText("Nombre del escenario"), "Base case");
    await user.type(
      screen.getByLabelText("Descripcion del escenario"),
      "Initial modeling branch",
    );
    await user.click(screen.getByRole("button", { name: "Crear escenario" }));

    expect(
      await screen.findByRole("heading", { name: "Base case" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/scenarios/10");
    expect(screen.getByText("Aun no hay versiones inmutables.")).toBeVisible();
    expect(
      screen.getByText("Aun no hay corridas para este escenario."),
    ).toBeVisible();

    window.history.pushState({}, "", "/react/scenarios/10");
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Base case" })).toBeVisible();
    });
  });

  it("lets admins manage users and project client access without a document reload", async () => {
    window.history.replaceState({}, "", "/react/admin/users");
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Client assignment workspace",
      created_at: "2026-06-24T12:00:00Z",
    };
    const users: AdminUser[] = [
      {
        id: 7,
        email: "admin@example.local",
        display_name: "Admin User",
        role: "admin",
        is_active: true,
        created_at: "2026-06-24T11:00:00Z",
        updated_at: "2026-06-24T11:00:00Z",
        created_by: "system",
        deactivated_at: null,
      },
    ];
    const assignments: Array<{
      project_id: number;
      user_id: number;
      email: string;
      display_name: string;
      role: string;
      is_active: boolean;
      assigned_at: string;
      assigned_by: string;
    }> = [];
    const schedules = [
      {
        id: 31,
        scenario_id: 10,
        case_id: 20,
        case_input_variant_id: 30,
        display_name: "Daily API schedule",
        range_start: "2026-08-01T00:00:00-04:00",
        range_end: "2026-08-02T00:00:00-04:00",
        cadence: "daily",
        next_run_at: "2026-08-06T09:00:00+00:00",
        topology_hash: "sha256:topology",
        parameter_hash: "sha256:parameters",
        is_active: true,
        last_fired_at: null,
        created_at: "2026-08-05T12:00:00Z",
        updated_at: "2026-08-05T12:00:00Z",
        created_by: "admin@example.local",
        updated_by: "admin@example.local",
      },
    ];
    let scheduleTicks: Array<{
      id: number;
      schedule_id: number;
      due_at: string;
      fired_at: string;
      range_start: string;
      range_end: string;
      status: string;
      scenario_version_id: number | null;
      run_id: number | null;
      error_message: string;
      created_at: string;
      updated_at: string;
    }> = [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "admin@example.local",
                display_name: "Admin User",
                role: "admin",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/admin/users" && method === "GET") {
          return new Response(JSON.stringify({ users }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/admin/schedules" && method === "GET") {
          return new Response(
            JSON.stringify({ schedules, ticks: scheduleTicks }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/admin/schedules/run-due" && method === "POST") {
          scheduleTicks = [
            {
              id: 99,
              schedule_id: 31,
              due_at: "2026-08-06T09:00:00+00:00",
              fired_at: "2026-08-06T10:00:00+00:00",
              range_start: "2026-08-01T00:00:00-04:00",
              range_end: "2026-08-02T00:00:00-04:00",
              status: "queued",
              scenario_version_id: 44,
              run_id: 55,
              error_message: "",
              created_at: "2026-08-06T10:00:00+00:00",
              updated_at: "2026-08-06T10:00:00+00:00",
            },
          ];
          return new Response(
            JSON.stringify({
              now: "2026-08-06T10:00:00+00:00",
              due_count: 1,
              ticks: scheduleTicks,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/admin/users" && method === "POST") {
          const body = JSON.parse(String(init?.body));
          const created = {
            id: users.length + 7,
            email: String(body.email).trim().toLowerCase(),
            display_name: body.display_name,
            role: body.role,
            is_active: true,
            created_at: "2026-06-24T12:05:00Z",
            updated_at: "2026-06-24T12:05:00Z",
            created_by: "admin@example.local",
            deactivated_at: null,
          };
          users.push(created);
          return new Response(JSON.stringify({ user: created }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/admin/users/8/deactivate" && method === "POST") {
          users[1] = {
            ...users[1],
            is_active: false,
            deactivated_at: "2026-06-24T12:10:00Z",
          };
          return new Response(JSON.stringify({ user: users[1] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects" && method === "GET") {
          return new Response(JSON.stringify({ projects: [project] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/scenarios") {
          return new Response(JSON.stringify({ scenarios: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/dashboard-templates") {
          return new Response(JSON.stringify({ dashboard_templates: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/admin/projects/1/client-access" &&
          method === "GET"
        ) {
          return new Response(JSON.stringify({ client_access: assignments }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/admin/projects/1/client-access" &&
          method === "POST"
        ) {
          const body = JSON.parse(String(init?.body));
          const client = users.find(
            (candidate) => candidate.id === body.user_id,
          );
          if (!client) {
            return new Response(JSON.stringify({ detail: "user not found" }), {
              status: 404,
              headers: { "Content-Type": "application/json" },
            });
          }
          const assignment = {
            project_id: 1,
            user_id: client.id,
            email: client.email,
            display_name: client.display_name,
            role: client.role,
            is_active: client.is_active,
            assigned_at: "2026-06-24T12:06:00Z",
            assigned_by: "admin@example.local",
          };
          assignments.push(assignment);
          return new Response(JSON.stringify({ client_access: assignment }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/admin/projects/1/client-access/8" &&
          method === "DELETE"
        ) {
          assignments.splice(0, assignments.length);
          return new Response(JSON.stringify({ removed: true }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Administracion" }),
    ).toBeVisible();
    expect(screen.getByText("admin@example.local")).toBeVisible();
    expect(await screen.findByText("Daily API schedule")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Ejecutar vencidos" }));
    expect(await screen.findByText("1 schedule(s) evaluados.")).toBeVisible();
    expect(await screen.findByText(/ultimo tick queued/)).toBeVisible();

    await user.type(screen.getByLabelText("Email"), "client@example.local");
    await user.type(screen.getByLabelText("Nombre"), "Client User");
    await user.type(screen.getByLabelText("Password"), "client pass");
    await user.selectOptions(screen.getByLabelText("Rol"), "client");
    await user.click(screen.getByRole("button", { name: "Crear usuario" }));
    expect(await screen.findByText("client@example.local")).toBeVisible();
    expect(screen.getByText("client@example.local creado.")).toBeVisible();
    expect(screen.getByLabelText("Email")).toHaveFocus();

    await user.click(screen.getByRole("link", { name: "Analista" }));
    await user.click(await screen.findByRole("link", { name: "Hybrid PMGD" }));
    expect(
      await screen.findByRole("heading", { name: "Hybrid PMGD" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Acceso cliente" }),
    ).toBeVisible();

    await user.selectOptions(screen.getByLabelText("Cliente elegible"), "8");
    await user.click(screen.getByRole("button", { name: "Asignar cliente" }));
    expect(
      await screen.findByText("client@example.local asignado a Hybrid PMGD."),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Quitar client@example.local" }),
    ).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Quitar client@example.local" }),
    );
    expect(
      screen.getByText("Confirma quitar client@example.local"),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", {
        name: "Confirmar quitar client@example.local",
      }),
    );
    expect(
      await screen.findByText("client@example.local sin acceso a Hybrid PMGD."),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Quitar client@example.local" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Admin" }));
    await user.click(
      await screen.findByRole("button", {
        name: "Desactivar client@example.local",
      }),
    );
    expect(
      screen.getByText("Confirma desactivar client@example.local"),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", {
        name: "Confirmar desactivar client@example.local",
      }),
    );
    expect(
      await screen.findByText("client@example.local desactivado."),
    ).toHaveFocus();
    expect(screen.getByText("deactivated")).toBeVisible();
  });

  it("renders the read-only client portal and clears protected data after authorization failure", async () => {
    window.history.replaceState({}, "", "/react/client");
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Client assignment workspace",
      created_at: "2026-06-24T12:00:00Z",
    };
    const scenario = {
      id: 10,
      project_id: 1,
      name: "Base case",
      description: "Published scenario",
      created_at: "2026-06-24T12:01:00Z",
    };
    const version = {
      id: 41,
      scenario_id: 10,
      version_number: 3,
      case_name: "dispatch_case",
      schema_version: "bess_system_dispatch.v2",
      period_count: 1,
      asset_counts: { battery: 1 },
      created_at: "2026-06-24T12:02:00Z",
    };
    const run = {
      id: 99,
      scenario_version_id: 41,
      status: "succeeded",
      created_at: "2026-06-24T12:03:00Z",
      started_at: "2026-06-24T12:03:01Z",
      finished_at: "2026-06-24T12:03:03Z",
      duration_seconds: 2,
      exit_code: 0,
      error_message: "",
      stdout: "",
      stderr: "",
    };
    const publication = {
      id: 9,
      project_id: 1,
      scenario_id: 10,
      scenario_version_id: 41,
      run_id: 99,
      dashboard_template_id: 5,
      public_title: "Client Dispatch Review",
      analyst_notes: "Approved for client.",
      allowed_artifact_types: ["summary_json"],
      status: "published",
      created_at: "2026-06-24T12:04:00Z",
      updated_at: "2026-06-24T12:05:00Z",
      published_at: "2026-06-24T12:05:00Z",
    };
    const template = {
      id: 5,
      project_id: 1,
      name: "Client Summary",
      show_summary: true,
      show_price_chart: true,
      show_grid_chart: true,
      show_renewable_chart: false,
      show_bess_chart: false,
      show_hydro_chart: false,
      show_profit_chart: false,
      show_system_dispatch_table: true,
      show_asset_dispatch_table: false,
      table_preview_limit: 1,
      created_at: "2026-06-24T12:04:00Z",
      updated_at: "2026-06-24T12:04:00Z",
    };
    const results = {
      summary: {
        case_name: "hybrid_system",
        objective_value_usd: 1250.5,
      },
      dispatch_table: {
        columns: ["timestamp", "grid_import_mw"],
        rows: [{ timestamp: "2026-01-01T00:00:00", grid_import_mw: "2.5" }],
      },
      asset_dispatch_table: null,
      charts: {
        price: {
          id: "price",
          title: "Energy Price",
          available: true,
          labels: ["2026-01-01T00:00:00"],
          series: [
            {
              key: "price_usd_per_mwh",
              label: "Price USD/MWh",
              unit: "USD/MWh",
              values: [45],
            },
          ],
        },
      },
    };
    const downloads = [
      {
        artifact_type: "summary_json",
        display_name: "summary.json",
        media_type: "application/json",
        byte_size: 92,
        download_url:
          "/api/client/projects/1/publications/9/artifacts/summary_json/download",
      },
    ];
    const plotlyMock = {
      react: vi.fn().mockResolvedValue(undefined),
      purge: vi.fn(),
    };
    let revoked = false;
    vi.stubGlobal("Plotly", plotlyMock);
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 8,
                email: "client@example.local",
                display_name: "Client User",
                role: "client",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (revoked && path.startsWith("/api/client")) {
          return new Response(JSON.stringify({ detail: "forbidden" }), {
            status: 403,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/client/projects") {
          return new Response(JSON.stringify({ projects: [project] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/client/projects/1/publications") {
          return new Response(
            JSON.stringify({ project, publications: [publication] }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/client/projects/1/publications/9") {
          return new Response(
            JSON.stringify({
              project,
              scenario,
              scenario_version: version,
              run,
              publication,
              template,
              results,
              results_error: "",
              downloads,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Portal cliente" }),
    ).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Hybrid PMGD" }));
    expect(
      await screen.findByRole("heading", { name: "Hybrid PMGD" }),
    ).toBeVisible();
    expect(screen.getByText("Client Dispatch Review")).toBeVisible();

    await user.click(
      screen.getByRole("link", { name: "Client Dispatch Review" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Client Dispatch Review" }),
    ).toBeVisible();
    expect(screen.getByText("Approved for client.")).toBeVisible();
    expect(screen.getByText("succeeded")).toBeVisible();
    expect(screen.getByText("1250.5")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "System Dispatch" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Energy Price" })).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Asset Dispatch" }),
    ).toBeNull();
    const downloadLink = screen.getByRole("link", { name: "summary.json" });
    expect(downloadLink).toHaveAttribute(
      "href",
      "/api/client/projects/1/publications/9/artifacts/summary_json/download",
    );
    expect(screen.queryByText("Publication Drafts")).not.toBeInTheDocument();
    expect(screen.queryByText("Crear publicacion")).not.toBeInTheDocument();
    expect(screen.queryByText("Lanzar run")).not.toBeInTheDocument();

    revoked = true;
    await user.click(screen.getByRole("link", { name: "Cliente" }));

    expect(
      await screen.findByRole("heading", { name: "No se pudo cargar" }),
    ).toBeVisible();
    expect(
      screen.queryByText("Client Dispatch Review"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Hybrid PMGD")).not.toBeInTheDocument();
  });

  it("bootstraps the first admin through the JSON contract", async () => {
    window.history.replaceState({}, "", "/react");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ user: null, bootstrap_required: true }), {
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrf_token: "csrf-bootstrap" }), {
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user: {
              id: 1,
              email: "admin@example.local",
              display_name: "Admin User",
              role: "admin",
              is_active: true,
            },
            redirect_path: "/react/projects",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ projects: [] }), {
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Crear admin" }),
    ).toBeVisible();
    await user.type(screen.getByLabelText("Email"), "admin@example.local");
    await user.type(screen.getByLabelText("Nombre"), "Admin User");
    await user.type(screen.getByLabelText("Password"), "admin pass");
    await user.click(screen.getByRole("button", { name: "Crear admin" }));

    expect(
      await screen.findByRole("heading", { name: "Proyectos" }),
    ).toBeVisible();
    expect(screen.getByText("Admin User")).toBeVisible();
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/auth/bootstrap",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "admin@example.local",
          display_name: "Admin User",
          password: "admin pass",
        }),
      }),
    );
    const bootstrapHeaders = new Headers(fetchMock.mock.calls[2][1].headers);
    expect(bootstrapHeaders.get("X-CSRF-Token")).toBe("csrf-bootstrap");
  });

  it("logs in to the safe pre-login destination and logs out immediately", async () => {
    window.history.replaceState({}, "", "/react/system");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user: null, bootstrap_required: false }),
          { headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrf_token: "csrf-login" }), {
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user: {
              id: 7,
              email: "ada@example.local",
              display_name: "Ada Analyst",
              role: "analyst",
              is_active: true,
            },
            redirect_path: "/react/system",
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrf_token: "csrf-logout" }), {
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Iniciar sesion" }),
    ).toBeVisible();
    await user.type(screen.getByLabelText("Email"), "ada@example.local");
    await user.type(screen.getByLabelText("Password"), "smoke-test-password");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(
      await screen.findByRole("heading", { name: "Estado del sistema" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/system");

    await user.click(screen.getByRole("button", { name: "Salir" }));

    expect(
      await screen.findByRole("heading", { name: "Iniciar sesion" }),
    ).toBeVisible();
    expect(screen.queryByText("Ada Analyst")).not.toBeInTheDocument();
    const loginHeaders = new Headers(fetchMock.mock.calls[2][1].headers);
    expect(loginHeaders.get("X-CSRF-Token")).toBe("csrf-login");
    expect(JSON.parse(String(fetchMock.mock.calls[2][1].body))).toMatchObject({
      next: "/react/system",
    });
    const logoutHeaders = new Headers(fetchMock.mock.calls[4][1].headers);
    expect(logoutHeaders.get("X-CSRF-Token")).toBe("csrf-logout");
  });

  it("lands clients in the client area and blocks internal routes", async () => {
    window.history.replaceState({}, "", "/react/projects");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              user: {
                id: 8,
                email: "client@example.local",
                display_name: "Client User",
                role: "client",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          ),
      ),
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Forbidden" }),
    ).toBeVisible();
    expect(screen.getByText("Client User")).toBeVisible();
  });

  it("loads current identity and renders the authenticated user", async () => {
    window.history.replaceState({}, "", "/react");
    let resolveRequest: (response: Response) => void = () => undefined;
    const response = new Promise<Response>((resolve) => {
      resolveRequest = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => response),
    );

    render(<App />);

    expect(screen.getByRole("status")).toHaveTextContent("Cargando sesion");

    resolveRequest(
      new Response(
        JSON.stringify({
          user: {
            id: 7,
            email: "ada@example.local",
            display_name: "Ada Analyst",
            role: "analyst",
            is_active: true,
          },
          bootstrap_required: false,
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );

    expect(await screen.findByText("Ada Analyst")).toBeVisible();
    expect(screen.getByText("analyst")).toBeVisible();
  });

  it("renders login when no server session exists", async () => {
    window.history.replaceState({}, "", "/react");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ user: null, bootstrap_required: false }),
            { headers: { "Content-Type": "application/json" } },
          ),
      ),
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Iniciar sesion" }),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a recoverable error state when identity loading fails", async () => {
    window.history.replaceState({}, "", "/react");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "service unavailable" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user: null, bootstrap_required: false }),
          { headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudo cargar la sesion",
    );
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(
      await screen.findByRole("heading", { name: "Iniciar sesion" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("navigates within the shell without a document reload", async () => {
    window.history.replaceState({}, "", "/react");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/projects") {
        return new Response(JSON.stringify({ projects: [] }), {
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(
        JSON.stringify({
          user: {
            id: 7,
            email: "ada@example.local",
            display_name: "Ada Analyst",
            role: "analyst",
            is_active: true,
          },
          bootstrap_required: false,
        }),
        { headers: { "Content-Type": "application/json" } },
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Ada Analyst");

    await user.click(screen.getByRole("link", { name: "Sistema" }));

    expect(
      screen.getByRole("heading", { name: "Estado del sistema" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/system");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("browses the project time-series catalog and opens a set's detail", async () => {
    window.history.replaceState({}, "", "/react/projects/1");
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const catalogSet = {
      id: 501,
      project_id: 1,
      name: "Spot price Jan 2026",
      version_number: 1,
      version_label: "v1",
      revision_number: 1,
      data_kind: "real",
      timezone: "America/Santiago",
      status: "validated",
      content_hash: "sha256:abc123",
      signal_count: 1,
      period_count: 2,
      created_at: "2026-07-04T12:00:00Z",
      updated_at: "2026-07-04T12:00:00Z",
    };
    const setDetail = {
      ...catalogSet,
      source_checksum: "sha256:def456",
      revision_metadata: {},
      source: {
        original_filename: "price.csv",
        media_type: "text/csv",
        checksum: "sha256:def456",
        selected_sheet: null,
      },
      horizon: {
        period_count: 2,
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T02:00:00-03:00",
      },
      signals: [
        {
          signal_key: "price_usd_per_mwh",
          unit: "USD/MWh",
          source_column: "spot_price",
          source_unit: "USD/MWh",
          entity_type: null,
          entity_key: null,
        },
      ],
      periods: [],
      values: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/scenarios") {
          return new Response(JSON.stringify({ scenarios: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/dashboard-templates") {
          return new Response(JSON.stringify({ dashboard_templates: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/time-series-sets" && method === "GET") {
          return new Response(
            JSON.stringify({ time_series_sets: [catalogSet] }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets/hydraulic") {
          return new Response(
            JSON.stringify({ hydraulic_time_series_sets: [] }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets/501") {
          return new Response(JSON.stringify({ time_series_set: setDetail }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/time-series-sets/501/revisions") {
          return new Response(
            JSON.stringify({
              time_series_set_revisions: [
                {
                  revision_number: 1,
                  content_hash: "sha256:abc123",
                  change_summary: "Initial CSV/XLSX catalog import",
                  created_at: "2026-07-04T12:00:00Z",
                  created_by: "internal_analyst",
                },
              ],
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Hybrid PMGD" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("link", { name: "Ver catalogo de series de tiempo" }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Catalogo de series de tiempo",
      }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/projects/1/time-series-sets");
    expect(
      screen.getByRole("link", { name: "Spot price Jan 2026 (v1)" }),
    ).toBeVisible();
    expect(
      screen.getByText(/real \| validated \| America\/Santiago/),
    ).toBeVisible();
    expect(screen.getByText("sha256:abc123")).toBeVisible();

    await user.click(
      screen.getByRole("link", { name: "Spot price Jan 2026 (v1)" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Spot price Jan 2026 (v1)" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe(
      "/react/projects/1/time-series-sets/501",
    );
    expect(screen.getByText("price_usd_per_mwh")).toBeVisible();
    expect(screen.getByText(/USD\/MWh \| Global/)).toBeVisible();
    expect(screen.getByText("2 periodos")).toBeVisible();
    expect(
      screen.getByText("2026-01-01T00:00:00-03:00 - 2026-01-01T02:00:00-03:00"),
    ).toBeVisible();
    expect(screen.getByText(/price\.csv \(text\/csv\)/)).toBeVisible();
    const revisionHistorySection = await screen.findByRole("region", {
      name: "Historial de revisiones",
    });
    expect(
      within(revisionHistorySection).getByText("Revision 1"),
    ).toBeVisible();
  });

  it("labels an extracted set's legacy origin distinctly from its source-file origin", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/projects/1/time-series-sets/501",
    );
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const setDetail = {
      id: 501,
      project_id: 1,
      name: "Draft prices extracted",
      version_number: 1,
      version_label: "v1",
      revision_number: 1,
      data_kind: "real",
      timezone: "America/Santiago",
      status: "validated",
      content_hash: "sha256:abc123",
      signal_count: 1,
      period_count: 2,
      created_at: "2026-07-04T12:00:00Z",
      updated_at: "2026-07-04T12:00:00Z",
      source_checksum: "sha256:def456",
      revision_metadata: {
        origin: {
          kind: "legacy_draft_extraction",
          scenario_id: 10,
          source_id: "csv_source_1",
          source_filename: "price.csv",
          extracted_by: "internal_analyst",
          extracted_at: "2026-07-08T12:00:00Z",
        },
      },
      source: {
        original_filename: "price.csv",
        media_type: "text/csv",
        checksum: "sha256:def456",
        selected_sheet: null,
      },
      horizon: {
        period_count: 2,
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T02:00:00-03:00",
      },
      signals: [
        {
          signal_key: "price_usd_per_mwh",
          unit: "USD/MWh",
          source_column: "spot_price",
          source_unit: "USD/MWh",
          entity_type: null,
          entity_key: null,
        },
      ],
      periods: [],
      values: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/time-series-sets/501") {
          return new Response(JSON.stringify({ time_series_set: setDetail }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/time-series-sets/501/revisions") {
          return new Response(
            JSON.stringify({ time_series_set_revisions: [] }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Draft prices extracted (v1)",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Origen legacy" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Origen" })).toBeVisible();
    expect(
      screen.getByText(/Extraido desde borrador legacy/),
    ).toBeVisible();
    expect(screen.getByText(/price\.csv \(text\/csv\)/)).toBeVisible();
  });

  it("labels a migrated set's legacy origin distinctly from its source-file origin", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/projects/1/time-series-sets/502",
    );
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const setDetail = {
      id: 502,
      project_id: 1,
      name: "hydro_hydraulic_node_124_natural_inflow_m3s",
      version_number: 1,
      version_label: "migrated-v1-legacy",
      revision_number: 1,
      data_kind: "real",
      timezone: "UTC",
      status: "validated",
      content_hash: "sha256:migrated123",
      signal_count: 1,
      period_count: 3,
      created_at: "2026-07-09T12:00:00Z",
      updated_at: "2026-07-09T12:00:00Z",
      source_checksum: null,
      revision_metadata: {
        origin: {
          kind: "hydraulic_legacy_migration",
          hydraulic_time_series_set_id: 10,
          legacy_version_label: "v1-legacy",
          legacy_content_hash: "sha256:legacyhash",
          migrated_by: "internal_analyst",
          migrated_at: "2026-07-09T12:05:00Z",
        },
      },
      source: null,
      horizon: {
        period_count: 3,
        start: "2026-01-01T00:00:00Z",
        end: "2026-01-01T03:00:00Z",
      },
      signals: [
        {
          signal_key: "natural_inflow_m3s",
          unit: "m3/s",
          source_column: null,
          source_unit: null,
          entity_type: "hydraulic_node",
          entity_key: "reservoir_alpha",
        },
      ],
      periods: [],
      values: [],
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/time-series-sets/502") {
          return new Response(JSON.stringify({ time_series_set: setDetail }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/time-series-sets/502/revisions") {
          return new Response(
            JSON.stringify({ time_series_set_revisions: [] }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "hydro_hydraulic_node_124_natural_inflow_m3s (migrated-v1-legacy)",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Origen legacy" }),
    ).toBeVisible();
    expect(
      screen.getByText(/Migrado desde el set hidraulico legacy 10/),
    ).toBeVisible();
  });

  it("lists a legacy hydraulic series set in the project catalog and opens its detail", async () => {
    window.history.replaceState({}, "", "/react/projects/1");
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const hydraulicSummary = {
      id: 77,
      project_id: 1,
      name: "Laja System / Reservoir Alpha (natural_inflow_m3s)",
      entity_type: "hydraulic_node",
      entity_id: 3,
      entity_key: "reservoir_alpha",
      entity_display_name: "Reservoir Alpha",
      hydraulic_system_name: "Laja System",
      signal_key: "natural_inflow_m3s",
      unit: "m3/s",
      version_number: 1,
      version_label: "v1",
      status: "draft",
      content_hash: "sha256:hydraulic-abc",
      period_count: 2,
      created_at: "2026-07-09T12:00:00Z",
      updated_at: "2026-07-09T12:00:00Z",
      origin: {
        kind: "hydraulic_legacy",
        entity_type: "hydraulic_node",
        entity_id: 3,
        signal_key: "natural_inflow_m3s",
      },
    };
    const hydraulicDetail = {
      ...hydraulicSummary,
      signals: [
        {
          signal_key: "natural_inflow_m3s",
          unit: "m3/s",
          entity_type: "hydraulic_node",
          entity_key: "reservoir_alpha",
        },
      ],
      periods: [
        {
          period_index: 0,
          timestamp_start: "2026-01-01T00:00:00",
          timestamp_end: "2026-01-01T01:00:00",
          duration_hours: 1.0,
        },
      ],
      values: [
        { period_index: 0, signal_key: "natural_inflow_m3s", value_numeric: 5.0 },
      ],
      horizon: {
        period_count: 1,
        start: "2026-01-01T00:00:00",
        end: "2026-01-01T01:00:00",
      },
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/scenarios") {
          return new Response(JSON.stringify({ scenarios: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/dashboard-templates") {
          return new Response(JSON.stringify({ dashboard_templates: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/time-series-sets" && method === "GET") {
          return new Response(JSON.stringify({ time_series_sets: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/time-series-sets/hydraulic") {
          return new Response(
            JSON.stringify({ hydraulic_time_series_sets: [hydraulicSummary] }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets/hydraulic/77") {
          return new Response(
            JSON.stringify({ hydraulic_time_series_set: hydraulicDetail }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Hybrid PMGD" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("link", { name: "Ver catalogo de series de tiempo" }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Series hidraulicas (origen legacy)",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: "Laja System / Reservoir Alpha (natural_inflow_m3s)",
      }),
    ).toBeVisible();
    expect(screen.getByText(/Origen hidraulico \| draft/)).toBeVisible();

    await user.click(
      screen.getByRole("link", {
        name: "Laja System / Reservoir Alpha (natural_inflow_m3s)",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Laja System / Reservoir Alpha (natural_inflow_m3s)",
      }),
    ).toBeVisible();
    expect(window.location.pathname).toBe(
      "/react/projects/1/time-series-sets/hydraulic/77",
    );
    expect(screen.getByText("natural_inflow_m3s")).toBeVisible();
    expect(screen.getByText(/m3\/s \| hydraulic_node:reservoir_alpha/)).toBeVisible();
    expect(
      screen.getByText(/Laja System \/ Reservoir Alpha \(hydraulic_node\)/),
    ).toBeVisible();
  });

  it("shows a legacy hydraulic set's migration status on load, without needing to click migrate again", async () => {
    window.history.replaceState({}, "", "/react/projects/1");
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const migration = {
      time_series_set_id: 91,
      time_series_set_name: "hydro_hydraulic_node_3_natural_inflow_m3s",
      version_label: "migrated-v1-legacy",
      migrated_by: "internal_analyst",
      migrated_at: "2026-07-09T12:05:00Z",
    };
    const hydraulicSummary = {
      id: 77,
      project_id: 1,
      name: "Laja System / Reservoir Alpha (natural_inflow_m3s)",
      entity_type: "hydraulic_node",
      entity_id: 3,
      entity_key: "reservoir_alpha",
      entity_display_name: "Reservoir Alpha",
      hydraulic_system_name: "Laja System",
      signal_key: "natural_inflow_m3s",
      unit: "m3/s",
      version_number: 1,
      version_label: "v1",
      status: "draft",
      content_hash: "sha256:hydraulic-abc",
      period_count: 1,
      created_at: "2026-07-09T12:00:00Z",
      updated_at: "2026-07-09T12:00:00Z",
      origin: {
        kind: "hydraulic_legacy",
        entity_type: "hydraulic_node",
        entity_id: 3,
        signal_key: "natural_inflow_m3s",
      },
      migration,
    };
    const hydraulicDetail = {
      ...hydraulicSummary,
      signals: [
        {
          signal_key: "natural_inflow_m3s",
          unit: "m3/s",
          entity_type: "hydraulic_node",
          entity_key: "reservoir_alpha",
        },
      ],
      periods: [
        {
          period_index: 0,
          timestamp_start: "2026-01-01T00:00:00",
          timestamp_end: "2026-01-01T01:00:00",
          duration_hours: 1.0,
        },
      ],
      values: [
        { period_index: 0, signal_key: "natural_inflow_m3s", value_numeric: 5.0 },
      ],
      horizon: {
        period_count: 1,
        start: "2026-01-01T00:00:00",
        end: "2026-01-01T01:00:00",
      },
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/scenarios") {
          return new Response(JSON.stringify({ scenarios: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/dashboard-templates") {
          return new Response(JSON.stringify({ dashboard_templates: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/time-series-sets" && method === "GET") {
          return new Response(JSON.stringify({ time_series_sets: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/time-series-sets/hydraulic") {
          return new Response(
            JSON.stringify({ hydraulic_time_series_sets: [hydraulicSummary] }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets/hydraulic/77") {
          return new Response(
            JSON.stringify({ hydraulic_time_series_set: hydraulicDetail }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Hybrid PMGD" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("link", { name: "Ver catalogo de series de tiempo" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Series hidraulicas (origen legacy)",
      }),
    ).toBeVisible();
    expect(screen.getByText("Ya migrado a")).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: /hydro_hydraulic_node_3_natural_inflow_m3s/,
      }),
    ).toBeVisible();

    await user.click(
      screen.getByRole("link", {
        name: "Laja System / Reservoir Alpha (natural_inflow_m3s)",
      }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Laja System / Reservoir Alpha (natural_inflow_m3s)",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: /hydro_hydraulic_node_3_natural_inflow_m3s/,
      }),
    ).toHaveAttribute("href", "/react/projects/1/time-series-sets/91");
    expect(
      screen.queryByRole("button", { name: "Migrar al catalogo generico" }),
    ).not.toBeInTheDocument();
  });

  it("edits a time-series set value and creates a new auditable revision", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/projects/1/time-series-sets/501",
    );
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const baseSetDetail = {
      id: 501,
      project_id: 1,
      name: "Spot price Jan 2026",
      version_number: 1,
      version_label: "v1",
      revision_number: 1,
      data_kind: "real",
      timezone: "America/Santiago",
      status: "validated",
      content_hash: "sha256:abc123",
      source_checksum: "sha256:def456",
      signal_count: 1,
      period_count: 1,
      revision_metadata: {},
      source: {
        original_filename: "price.csv",
        media_type: "text/csv",
        checksum: "sha256:def456",
        selected_sheet: null,
      },
      horizon: {
        period_count: 1,
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T01:00:00-03:00",
      },
      signals: [
        {
          signal_key: "price_usd_per_mwh",
          unit: "USD/MWh",
          source_column: "spot_price",
          source_unit: "USD/MWh",
          entity_type: null,
          entity_key: null,
        },
      ],
      periods: [
        {
          period_index: 0,
          timestamp_start: "2026-01-01T00:00:00-03:00",
          timestamp_end: "2026-01-01T01:00:00-03:00",
          duration_hours: 1.0,
        },
      ],
      values: [
        {
          period_index: 0,
          signal_key: "price_usd_per_mwh",
          value_numeric: 55.0,
        },
      ],
    };
    const editedSetDetail = {
      ...baseSetDetail,
      revision_number: 2,
      content_hash: "sha256:def789",
      values: [
        {
          period_index: 0,
          signal_key: "price_usd_per_mwh",
          value_numeric: 57.5,
        },
      ],
    };
    let editApplied = false;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/projects/1/time-series-sets/501" &&
          method === "GET"
        ) {
          return new Response(
            JSON.stringify({
              time_series_set: editApplied ? editedSetDetail : baseSetDetail,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/projects/1/time-series-sets/501/values" &&
          method === "PUT"
        ) {
          const body = JSON.parse(String(init?.body));
          expect(body).toEqual({
            edits: [
              {
                period_index: 0,
                signal_key: "price_usd_per_mwh",
                value: "57.5",
              },
            ],
            change_summary: "Corrected spike",
          });
          editApplied = true;
          return new Response(
            JSON.stringify({ time_series_set: editedSetDetail }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets/501/revisions") {
          return new Response(
            JSON.stringify({
              time_series_set_revisions: editApplied
                ? [
                    {
                      revision_number: 2,
                      content_hash: "sha256:def789",
                      change_summary: "Corrected spike",
                      created_at: "2026-07-06T12:00:00Z",
                      created_by: "ada@example.local",
                    },
                    {
                      revision_number: 1,
                      content_hash: "sha256:abc123",
                      change_summary: "Initial CSV/XLSX catalog import",
                      created_at: "2026-07-04T12:00:00Z",
                      created_by: "internal_analyst",
                    },
                  ]
                : [
                    {
                      revision_number: 1,
                      content_hash: "sha256:abc123",
                      change_summary: "Initial CSV/XLSX catalog import",
                      created_at: "2026-07-04T12:00:00Z",
                      created_by: "internal_analyst",
                    },
                  ],
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Spot price Jan 2026 (v1)" }),
    ).toBeVisible();
    const revisionSection = screen.getByRole("region", { name: "Revision" });
    expect(within(revisionSection).getByText("Revision 1")).toBeVisible();

    const valueInput = screen.getByLabelText(
      "Periodo 2026-01-01T00:00:00-03:00 price_usd_per_mwh",
    );
    await user.clear(valueInput);
    await user.type(valueInput, "57.5");
    await user.type(
      screen.getByLabelText("Resumen del cambio (opcional)"),
      "Corrected spike",
    );
    await user.click(
      screen.getByRole("button", { name: "Guardar correcciones" }),
    );

    await waitFor(() =>
      expect(within(revisionSection).getByText("Revision 2")).toBeVisible(),
    );
    expect(within(revisionSection).getByText("sha256:def789")).toBeVisible();

    const revisionHistorySection = await screen.findByRole("region", {
      name: "Historial de revisiones",
    });
    await waitFor(() =>
      expect(
        within(revisionHistorySection).getByText("Revision 2"),
      ).toBeVisible(),
    );
    expect(
      within(revisionHistorySection).getByText("Revision 1"),
    ).toBeVisible();
  });

  it("replaces a time-series set with a corrected file upload and keeps its identity stable", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/projects/1/time-series-sets/501",
    );
    const project = {
      id: 1,
      name: "Hybrid PMGD",
      description: "Analyst workspace",
      created_at: "2026-06-23T12:00:00Z",
    };
    const baseSetDetail = {
      id: 501,
      project_id: 1,
      name: "Spot price Jan 2026",
      version_number: 1,
      version_label: "v1",
      revision_number: 1,
      data_kind: "real",
      timezone: "America/Santiago",
      status: "validated",
      content_hash: "sha256:abc123",
      source_checksum: "sha256:def456",
      signal_count: 1,
      period_count: 1,
      revision_metadata: {},
      source: {
        original_filename: "price.csv",
        media_type: "text/csv",
        checksum: "sha256:def456",
        selected_sheet: null,
      },
      horizon: {
        period_count: 1,
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T01:00:00-03:00",
      },
      signals: [
        {
          signal_key: "price_usd_per_mwh",
          unit: "USD/MWh",
          source_column: "spot_price",
          source_unit: "USD/MWh",
          entity_type: null,
          entity_key: null,
        },
      ],
      periods: [
        {
          period_index: 0,
          timestamp_start: "2026-01-01T00:00:00-03:00",
          timestamp_end: "2026-01-01T01:00:00-03:00",
          duration_hours: 1.0,
        },
      ],
      values: [
        {
          period_index: 0,
          signal_key: "price_usd_per_mwh",
          value_numeric: 55.0,
        },
      ],
    };
    const replacementSource = {
      id: "csv_replace_1",
      kind: "csv",
      original_filename: "price_corrected.csv",
      media_type: "text/csv",
      checksum: "sha256:replace1",
      stored_path: "/tmp/csv_replace_1_price_corrected.csv",
      columns: ["period_start", "hours", "spot_price"],
      preview_rows: [
        {
          period_start: "2026-01-01T00:00:00",
          hours: "1.0",
          spot_price: "57.5",
        },
      ],
    };
    const replacedSetDetail = {
      ...baseSetDetail,
      revision_number: 2,
      content_hash: "sha256:def789",
      source: {
        original_filename: "price_corrected.csv",
        media_type: "text/csv",
        checksum: "sha256:replace1",
        selected_sheet: null,
      },
      values: [
        {
          period_index: 0,
          signal_key: "price_usd_per_mwh",
          value_numeric: 57.5,
        },
      ],
    };
    let replaceApplied = false;
    let lastReplaceBody: unknown = null;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/projects/1/time-series-sets/501" &&
          method === "GET"
        ) {
          return new Response(
            JSON.stringify({
              time_series_set: replaceApplied
                ? replacedSetDetail
                : baseSetDetail,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          path === "/api/projects/1/time-series-sets/501/replace/upload" &&
          method === "POST"
        ) {
          return new Response(JSON.stringify({ source: replacementSource }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          path === "/api/projects/1/time-series-sets/501/replace" &&
          method === "POST"
        ) {
          lastReplaceBody = JSON.parse(String(init?.body));
          replaceApplied = true;
          return new Response(
            JSON.stringify({ time_series_set: replacedSetDetail }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/projects/1/time-series-sets/501/revisions") {
          return new Response(
            JSON.stringify({
              time_series_set_revisions: replaceApplied
                ? [
                    {
                      revision_number: 2,
                      content_hash: "sha256:def789",
                      change_summary: "Corrected Jan 1st spike",
                      created_at: "2026-07-06T12:00:00Z",
                      created_by: "ada@example.local",
                    },
                    {
                      revision_number: 1,
                      content_hash: "sha256:abc123",
                      change_summary: "Initial CSV/XLSX catalog import",
                      created_at: "2026-07-04T12:00:00Z",
                      created_by: "internal_analyst",
                    },
                  ]
                : [
                    {
                      revision_number: 1,
                      content_hash: "sha256:abc123",
                      change_summary: "Initial CSV/XLSX catalog import",
                      created_at: "2026-07-04T12:00:00Z",
                      created_by: "internal_analyst",
                    },
                  ],
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Spot price Jan 2026 (v1)" }),
    ).toBeVisible();

    await user.upload(
      screen.getByLabelText("Archivo de reemplazo"),
      new File(
        ["period_start,hours,spot_price\n2026-01-01T00:00:00,1.0,57.5\n"],
        "price_corrected.csv",
        { type: "text/csv" },
      ),
    );
    await user.click(
      screen.getByRole("button", { name: "Subir archivo de reemplazo" }),
    );
    expect(await screen.findByText("price_corrected.csv")).toBeVisible();

    await user.selectOptions(
      screen.getByLabelText("Columna de marca de tiempo"),
      "period_start",
    );
    await user.selectOptions(
      screen.getByLabelText("Columna de duracion (horas)"),
      "hours",
    );
    await user.selectOptions(
      screen.getByLabelText("Columna de origen 1"),
      "spot_price",
    );
    await user.selectOptions(
      screen.getByLabelText("Senal canonica 1"),
      "price_usd_per_mwh",
    );
    await user.type(
      screen.getByLabelText("Resumen del reemplazo (opcional)"),
      "Corrected Jan 1st spike",
    );
    await user.click(screen.getByRole("button", { name: "Reemplazar set" }));

    await waitFor(() => expect(replaceApplied).toBe(true));
    expect(lastReplaceBody).toMatchObject({
      source: { id: "csv_replace_1" },
      data_kind: "real",
      timezone: "America/Santiago",
      timestamp_column: "period_start",
      duration_hours_column: "hours",
      change_summary: "Corrected Jan 1st spike",
      signal_mappings: [
        { source_column: "spot_price", signal_key: "price_usd_per_mwh" },
      ],
    });

    const revisionSection = screen.getByRole("region", { name: "Revision" });
    await waitFor(() =>
      expect(within(revisionSection).getByText("Revision 2")).toBeVisible(),
    );
    expect(within(revisionSection).getByText("sha256:def789")).toBeVisible();
    expect(screen.getByText(/price_corrected\.csv/)).toBeVisible();

    const revisionHistorySection = await screen.findByRole("region", {
      name: "Historial de revisiones",
    });
    await waitFor(() =>
      expect(
        within(revisionHistorySection).getByText("Revision 2"),
      ).toBeVisible(),
    );
    expect(
      within(revisionHistorySection).getByText("Revision 1"),
    ).toBeVisible();
  });
});
