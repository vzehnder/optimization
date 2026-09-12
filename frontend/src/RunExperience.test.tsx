import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

const period = {
  start: "2026-01-01T00:00:00-03:00",
  end: "2026-01-01T02:00:00-03:00",
};
const project = { id: 1, name: "Planta Norte", description: "" };
const scenario = { id: 10, project_id: 1, name: "Invierno", description: "" };
const version = {
  id: 41,
  scenario_id: 10,
  version_number: 3,
  case_name: "Caso de invierno",
  schema_version: "bess_system_dispatch.v2",
  period_count: 2,
  asset_counts: { battery: 1 },
  created_at: "2026-09-12T12:00:00Z",
  system_case_json: { case_name: "Snapshot de invierno" },
  validation_payload: { status: "ok" },
  generation_metadata: {
    kind: "case_input_variant",
    date_range: period,
    input_variant: { id: 5, display_name: "Base de invierno" },
  },
};
const run = {
  id: 99,
  scenario_version_id: 41,
  status: "succeeded",
  created_at: "2026-09-12T12:00:00Z",
  started_at: "2026-09-12T12:00:01Z",
  finished_at: "2026-09-12T12:00:03Z",
  duration_seconds: 2,
  exit_code: 0,
  error_message: "",
  error_payload: {},
  stdout: "",
  stderr: "",
};
const results = {
  summary: {
    case_name: "Caso de invierno",
    objective_value_usd: 1250.5,
    solver_status: "OPTIMAL",
  },
  charts: {},
  dispatch_table: { columns: [], rows: [] },
  asset_dispatch_table: { columns: [], rows: [] },
};
const candidateVersion = {
  ...version,
  id: 42,
  generation_metadata: {
    ...version.generation_metadata,
    input_variant: { id: 6, display_name: "Alternativa de invierno" },
  },
};
const candidateRun = { ...run, id: 98, scenario_version_id: 42 };
const comparison = {
  baseline: {
    run_id: 99,
    scenario_version_id: 41,
    input_variant: version.generation_metadata.input_variant,
    date_range: period,
  },
  candidate: {
    run_id: 98,
    scenario_version_id: 42,
    input_variant: candidateVersion.generation_metadata.input_variant,
    date_range: period,
  },
  kpis: [
    { key: "objective_value_usd", baseline: 1000, candidate: 1500, delta: 500 },
  ],
  available_signal_keys: ["grid_import_power_mw"],
  selected_series: "grid_import_power_mw",
  series_periods: [
    { timestamp: period.start, baseline: 2, candidate: 3, delta: 1 },
  ],
};

function serveResults(
  handler: (
    path: string,
    init?: RequestInit,
  ) => Response | Promise<Response> | undefined = () => undefined,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const handled = handler(path, init);
      if (handled) return handled;
      if (path === "/api/auth/me")
        return Response.json({
          user: {
            id: 7,
            email: "analyst@example.local",
            role: "analyst",
            is_active: true,
          },
          bootstrap_required: false,
          landing_path: "/react/projects",
        });
      if (path === "/api/runs/99") return Response.json({ run });
      if (path === "/api/runs/99/results") return Response.json({ results });
      if (path === "/api/runs/99/artifacts")
        return Response.json({
          artifacts: [
            {
              id: 11,
              display_name: "summary.json",
              artifact_type: "summary_json",
              media_type: "application/json",
              byte_size: 92,
              download_url: "/api/run-artifacts/11/download",
            },
          ],
        });
      if (path === "/api/runs/99/publications")
        return Response.json({ publications: [] });
      if (path === "/api/scenario-versions/41")
        return Response.json({ scenario_version: version });
      if (path === "/api/scenarios/10") return Response.json({ scenario });
      if (path === "/api/scenarios/10/versions")
        return Response.json({ versions: [version] });
      if (path === "/api/scenarios/10/runs")
        return Response.json({ runs: [run] });
      if (path === "/api/projects/1") return Response.json({ project });
      if (path === "/api/projects/1/dashboard-templates")
        return Response.json({ dashboard_templates: [] });
      return Response.json({ detail: `Unhandled ${path}` }, { status: 404 });
    }),
  );
}

describe("results experience", () => {
  it("keeps comparison and artifact access when a successful execution has no result sections", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    serveResults((path) =>
      path === "/api/runs/99/results"
        ? Response.json({
            results: {
              summary: null,
              charts: {},
              dispatch_table: null,
              asset_dispatch_table: null,
            },
          })
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    expect(
      await screen.findByRole("link", { name: "Comparar esta ejecución" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "No hay secciones de resultados disponibles para esta ejecución.",
      ),
    ).toBeVisible();
    await user.click(screen.getByText("Detalle técnico y auditoría"));
    expect(screen.getByRole("link", { name: "summary.json" })).toBeVisible();
  });

  it("chooses an available series when changing to executions with different indexed signals", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/runs/compare?baseline=99&candidate=98",
    );
    serveResults((path) => {
      if (path === "/api/scenarios/10/runs")
        return Response.json({
          runs: [run, candidateRun, { ...candidateRun, id: 97 }],
        });
      if (path === "/api/scenarios/10/versions")
        return Response.json({ versions: [candidateVersion, version] });
      if (path.startsWith("/api/run-comparisons?")) {
        const params = new URL(path, "http://localhost").searchParams;
        const available =
          params.get("candidate_run_id") === "97"
            ? ["grid_import_power_mw"]
            : ["grid_import_power_mw", "energy_price_usd_per_mwh"];
        return Response.json({
          comparison: {
            ...comparison,
            available_signal_keys: available,
            selected_series: available.includes(params.get("series") || "")
              ? params.get("series")
              : available[0],
          },
        });
      }
    });
    const user = userEvent.setup();
    render(<App />);
    await user.selectOptions(
      await screen.findByLabelText("Serie"),
      "energy_price_usd_per_mwh",
    );
    expect(await screen.findByText("USD/MWh", { exact: true })).toBeVisible();
    await user.selectOptions(screen.getByLabelText("Corrida candidata"), "97");
    expect(await screen.findByLabelText("Serie")).toHaveValue(
      "grid_import_power_mw",
    );
    expect(screen.getByText("MW", { exact: true })).toBeVisible();
  });

  it("starts a fresh comparison after returning from a candidate without selecting that execution twice", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/runs/99?origin=review&baseline=98&candidate=99",
    );
    serveResults((path) => {
      if (path === "/api/scenarios/10/runs")
        return Response.json({ runs: [candidateRun, run] });
      if (path === "/api/scenarios/10/versions")
        return Response.json({ versions: [candidateVersion, version] });
      if (path.startsWith("/api/run-comparisons?"))
        return Response.json({ comparison });
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("link", { name: "Comparar esta ejecución" }),
    );
    expect(await screen.findByLabelText("Corrida base")).toHaveValue("99");
    expect(screen.getByLabelText("Corrida candidata")).toHaveValue("98");
    expect(
      await screen.findByRole("region", { name: "Diferencias en KPIs" }),
    ).toBeVisible();
    expect(new URLSearchParams(window.location.search).get("origin")).toBe(
      "review",
    );
  });

  it("removes a previously visible result when the server rejects further access", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    let revoked = false;
    serveResults((path) =>
      path === "/api/runs/99/results" && revoked
        ? Response.json({ detail: "Acceso revocado" }, { status: 403 })
        : undefined,
    );
    render(<App />);
    expect(await screen.findByText("1.250,5 USD")).toBeVisible();
    revoked = true;
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 31_000);
    await act(async () => {
      window.dispatchEvent(new Event("visibilitychange"));
    });
    expect(await screen.findByText("Acceso revocado")).toBeVisible();
    expect(screen.queryByText("1.250,5 USD")).not.toBeInTheDocument();
    expect(screen.queryByText("Ver resumen completo")).not.toBeInTheDocument();
  });

  it("recovers artifact downloads from audit without losing the result", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    let available = false;
    serveResults((path) =>
      path === "/api/runs/99/artifacts" && !available
        ? Response.json(
            { detail: "Inventario temporalmente no disponible" },
            { status: 503 },
          )
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("1.250,5 USD")).toBeVisible();
    await user.click(screen.getByText("Detalle técnico y auditoría"));
    available = true;
    await user.click(
      screen.getByRole("button", { name: "Reintentar archivos" }),
    );
    expect(
      await screen.findByRole("link", { name: "summary.json" }),
    ).toBeVisible();
    expect(screen.getByText("1.250,5 USD")).toBeVisible();
  });

  it("keeps the result while recovering its unavailable version context without inventing a manual origin", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    let available = false;
    serveResults((path) =>
      path === "/api/scenario-versions/41" && !available
        ? Response.json({ detail: "Version unavailable" }, { status: 503 })
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("1.250,5 USD")).toBeVisible();
    expect(
      await screen.findByText(
        "No se pudo consultar el contexto de esta ejecución.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByText("Ejecución manual sin variante"),
    ).not.toBeInTheDocument();
    available = true;
    await user.click(
      screen.getByRole("button", { name: "Reintentar contexto" }),
    );
    expect(
      await within(
        screen.getByRole("region", { name: "Contexto de la ejecución" }),
      ).findByText("Base de invierno"),
    ).toBeVisible();
  });

  it("explains an API comparison rejection and retries without losing the selected executions", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/runs/compare?baseline=99&candidate=98",
    );
    let indexed = false;
    serveResults((path) => {
      if (path === "/api/scenarios/10/runs")
        return Response.json({ runs: [candidateRun, run] });
      if (path === "/api/scenarios/10/versions")
        return Response.json({ versions: [candidateVersion, version] });
      if (path.startsWith("/api/run-comparisons?"))
        return indexed
          ? Response.json({ comparison })
          : Response.json(
              { detail: "La candidata todavía no tiene resultados indexados" },
              { status: 409 },
            );
    });
    const user = userEvent.setup();
    render(<App />);
    expect(
      await screen.findByText(
        "La candidata todavía no tiene resultados indexados",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("region", { name: "Diferencias en KPIs" }),
    ).not.toBeInTheDocument();
    indexed = true;
    await user.click(
      screen.getByRole("button", { name: "Reintentar comparación" }),
    );
    expect(
      await screen.findByRole("region", { name: "Diferencias en KPIs" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Corrida base")).toHaveValue("99");
    expect(screen.getByLabelText("Corrida candidata")).toHaveValue("98");
  });

  it("requires a new selection when a linked baseline is unavailable instead of comparing another run silently", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/runs/compare?baseline=777&candidate=98",
    );
    serveResults((path) => {
      if (path === "/api/scenarios/10/runs")
        return Response.json({ runs: [candidateRun, run] });
      if (path === "/api/scenarios/10/versions")
        return Response.json({ versions: [candidateVersion, version] });
      if (path.startsWith("/api/run-comparisons?"))
        return Response.json({ comparison });
    });
    const user = userEvent.setup();
    render(<App />);
    expect(
      await screen.findByText(
        "La ejecución base del enlace no está disponible para comparar. Selecciona otra ejecución.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("region", { name: "Diferencias en KPIs" }),
    ).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Corrida base"), "99");
    expect(
      await screen.findByRole("region", { name: "Diferencias en KPIs" }),
    ).toBeVisible();
    expect(new URLSearchParams(window.location.search).get("baseline")).toBe(
      "99",
    );
  });

  it("warns about different comparison periods and leaves nonoverlapping values unavailable", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/scenarios/10/runs/compare?baseline=99&candidate=98",
    );
    serveResults((path) => {
      if (path === "/api/scenarios/10/runs")
        return Response.json({ runs: [candidateRun, run] });
      if (path === "/api/scenarios/10/versions")
        return Response.json({ versions: [candidateVersion, version] });
      if (path.startsWith("/api/run-comparisons?"))
        return Response.json({
          comparison: {
            ...comparison,
            candidate: {
              ...comparison.candidate,
              date_range: {
                start: "2026-01-01T01:00:00-03:00",
                end: "2026-01-01T03:00:00-03:00",
              },
            },
            series_periods: [
              {
                timestamp: period.start,
                baseline: 2,
                candidate: null,
                delta: null,
              },
            ],
          },
        });
    });
    render(<App />);
    expect(await screen.findByText(/Los períodos son distintos/)).toBeVisible();
    expect(
      screen.getByText(
        "[2026-01-01T01:00:00-03:00, 2026-01-01T03:00:00-03:00)",
      ),
    ).toBeVisible();
    const series = screen.getByRole("region", {
      name: "Diferencias por periodo",
    });
    expect(
      within(series).getByRole("row", {
        name: "2026-01-01T00:00:00-03:00 2 No disponible No disponible",
      }),
    ).toBeVisible();
  });

  it("lets the analyst consult table rows beyond the first page and preserves the page when closing details", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    serveResults((path) =>
      path === "/api/runs/99/results"
        ? Response.json({
            results: {
              ...results,
              dispatch_table: {
                columns: ["timestamp", "grid_import_mw"],
                rows: [
                  ...Array.from({ length: 25 }, (_, index) => ({
                    timestamp: `Período ${index + 1}`,
                    grid_import_mw: 2,
                  })),
                  { timestamp: "Último período", grid_import_mw: 987.65 },
                ],
              },
            },
          })
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByText("Ver tablas de resultados"));
    const table = screen.getByRole("region", { name: "Despacho del sistema" });
    expect(within(table).queryByText("Último período")).not.toBeInTheDocument();
    await user.click(
      within(table).getByRole("button", { name: "Página siguiente" }),
    );
    expect(
      within(table).getByRole("row", { name: "Último período 987.65" }),
    ).toBeVisible();
    await user.click(screen.getByText("Ver tablas de resultados"));
    await user.click(screen.getByText("Ver tablas de resultados"));
    expect(within(table).getByText("Último período")).toBeVisible();
    await user.click(
      within(table).getByRole("button", { name: "Página anterior" }),
    );
    expect(within(table).getByText("Período 1", { exact: true })).toBeVisible();
  });

  it("distinguishes missing legacy results from zero and preserves available hydro results and downloads", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    serveResults((path) =>
      path === "/api/runs/99/results"
        ? Response.json({
            results: {
              ...results,
              summary: {
                objective_value_usd: null,
                total_market_value_usd: 0,
                hydro_totals: { total_hydro_generation_mwh: 5 },
                notes: ["Serie histórica conservada"],
              },
              charts: {
                price: {
                  id: "price",
                  title: "Energy Price",
                  available: false,
                  labels: [],
                  series: [],
                  missing_columns: ["price_usd_per_mwh"],
                  message: "Missing columns: price_usd_per_mwh",
                },
              },
            },
          })
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    const kpis = await screen.findByLabelText("Indicadores principales");
    expect(within(kpis).getByText("No disponible")).toBeVisible();
    expect(within(kpis).getByText("0 USD")).toBeVisible();
    expect(within(kpis).getByText("5 MWh")).toBeVisible();
    expect(
      screen.getByText("Missing columns: price_usd_per_mwh"),
    ).toBeVisible();
    await user.click(screen.getByText("Ver resumen completo"));
    expect(screen.getByText(/Serie histórica conservada/)).toBeVisible();
    await user.click(screen.getByText("Detalle técnico y auditoría"));
    expect(screen.getByRole("link", { name: "summary.json" })).toBeVisible();
  });

  it("starts comparison from the chosen execution with known differences, units and return links", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/runs/99?origin=review&section=runs",
    );
    serveResults((path) => {
      if (path === "/api/scenarios/10/runs")
        return Response.json({ runs: [candidateRun, run] });
      if (path === "/api/scenarios/10/versions")
        return Response.json({ versions: [candidateVersion, version] });
      if (path.startsWith("/api/run-comparisons?")) {
        const params = new URL(path, "http://localhost").searchParams;
        return params.get("baseline_run_id") === "99" &&
          params.get("candidate_run_id") === "98"
          ? Response.json({ comparison })
          : Response.json(
              { detail: "Unexpected comparison selection" },
              { status: 422 },
            );
      }
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("link", { name: "Comparar esta ejecución" }),
    );
    expect(await screen.findByLabelText("Corrida base")).toHaveValue("99");
    expect(screen.getByLabelText("Corrida candidata")).toHaveValue("98");
    const kpis = await screen.findByRole("region", {
      name: "Diferencias en KPIs",
    });
    expect(
      within(kpis).getByRole("row", {
        name: "Valor objetivo USD 1.000 1.500 500",
      }),
    ).toBeVisible();
    const series = screen.getByRole("region", {
      name: "Diferencias por periodo",
    });
    expect(within(series).getByText("MW", { exact: true })).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Ver ejecución candidata" }),
    ).toHaveAttribute("href", expect.stringContaining("/runs/98"));
    await user.click(screen.getByRole("link", { name: "Ver ejecución base" }));
    expect(
      await screen.findByText("Finalizada", { exact: true }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/runs/99");
    expect(new URLSearchParams(window.location.search).get("origin")).toBe(
      "review",
    );
  });

  it("keeps an accepted result visible when a background refresh fails", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    let unavailable = false;
    serveResults((path) =>
      path === "/api/runs/99/results" && unavailable
        ? Response.json({ detail: "Consulta interrumpida" }, { status: 503 })
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("1.250,5 USD")).toBeVisible();
    unavailable = true;
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 31_000);
    await act(async () => {
      window.dispatchEvent(new Event("visibilitychange"));
    });
    expect(await screen.findByText("Consulta interrumpida")).toBeVisible();
    expect(screen.getByText("1.250,5 USD")).toBeVisible();
    unavailable = false;
    await user.click(
      screen.getByRole("button", { name: "Reintentar resultados" }),
    );
    expect(
      await screen.findByRole("region", { name: "Resumen de resultados" }),
    ).toBeVisible();
  });

  it("follows a running execution and retries unavailable results without launching another execution", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    let completed = false;
    let available = false;
    let writes = 0;
    serveResults((path, init) => {
      if (init?.method && init.method !== "GET") writes++;
      if (path === "/api/runs/99")
        return Response.json({
          run: { ...run, status: completed ? "succeeded" : "running" },
        });
      if (path === "/api/runs/99/results" && !available)
        return Response.json(
          { detail: "Servicio de resultados temporalmente no disponible" },
          { status: 503 },
        );
    });
    const user = userEvent.setup();
    render(<App />);
    expect(
      await screen.findByText("En ejecución", { exact: true }),
    ).toBeVisible();
    completed = true;
    expect(
      await screen.findByText("Finalizada", { exact: true }, { timeout: 3000 }),
    ).toBeVisible();
    expect(
      await screen.findByText(
        "Servicio de resultados temporalmente no disponible",
      ),
    ).toBeVisible();
    available = true;
    await user.click(
      screen.getByRole("button", { name: "Reintentar resultados" }),
    );
    expect(await screen.findByText("1.250,5 USD")).toBeVisible();
    expect(writes).toBe(0);
  });

  it("explains a failed execution before opening its diagnostic logs", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    serveResults((path) =>
      path === "/api/runs/99"
        ? Response.json({
            run: {
              ...run,
              status: "failed",
              error_message: "No existe una solución factible para el período.",
              stderr: "solver diagnostic marker",
            },
          })
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("Fallida", { exact: true })).toBeVisible();
    expect(
      screen.getByText("No existe una solución factible para el período.", {
        exact: true,
      }),
    ).toBeVisible();
    expect(screen.getByText("solver diagnostic marker")).not.toBeVisible();
    await user.click(screen.getByRole("button", { name: "Ver diagnóstico" }));
    expect(screen.getByText("solver diagnostic marker")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Diagnóstico de la ejecución" }),
    ).toHaveFocus();
  });

  it("shows the successful result and exact period with its immutable snapshot available on demand", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    serveResults();
    const user = userEvent.setup();
    render(<App />);

    expect(
      await screen.findByText("Finalizada", { exact: true }),
    ).toBeVisible();
    const context = screen.getByRole("region", {
      name: "Contexto de la ejecución",
    });
    expect(await within(context).findByText("Base de invierno")).toBeVisible();
    expect(
      within(context).getByText(`[${period.start}, ${period.end})`),
    ).toBeVisible();
    const summary = await screen.findByRole("region", {
      name: "Resumen de resultados",
    });
    expect(within(summary).getByText("Valor objetivo")).toBeVisible();
    expect(within(summary).getByText("1.250,5 USD")).toBeVisible();
    expect(screen.queryByText(/Snapshot de invierno/)).not.toBeInTheDocument();
    await user.click(
      screen.getByText("Detalle técnico y auditoría", { exact: true }),
    );
    await user.click(screen.getByText("Ver snapshot tecnico", { exact: true }));
    expect(await screen.findByText(/Snapshot de invierno/)).toBeVisible();
    expect(screen.getByRole("link", { name: "summary.json" })).toHaveAttribute(
      "href",
      "/api/run-artifacts/11/download",
    );
  });
});
