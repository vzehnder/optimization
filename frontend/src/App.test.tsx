import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("application shell", () => {
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
    expect(
      (screen.getByLabelText("Immutable system_case") as HTMLTextAreaElement)
        .value,
    ).toContain('"case_name": "expert_case"');

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
});
