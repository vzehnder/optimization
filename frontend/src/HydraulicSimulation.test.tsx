import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { App } from "./App";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { HydraulicSimulationForm } from "./hydro/HydraulicSimulationForm";
import type { ScenarioVersionDetail } from "./api/client";
import { CaseHierarchyProvenanceSummary } from "./CaseHierarchyProvenance";

it("prepares a promoted hydraulic network with CMg, range and resolution before running", async () => {
  window.history.replaceState({}, "", "/react/scenario-versions/73");
  const version = {
    id: 73,
    scenario_id: 788,
    version_number: 2,
    case_name: "Laja",
    schema_version: "bess_system_dispatch.v3",
    period_count: 4,
    asset_counts: { hydraulic_reservoir: 1 },
    generation_metadata: {},
    system_case_json: {
      time_series: [0, 1, 2, 3].map((hour) => ({
        timestamp: `2026-08-01T0${hour}:00:00+00:00`,
        duration_hours: 1,
        natural_inflow_m3s: { reservoir: 2 },
      })),
      solver: { options: { mip_rel_gap: 0.02 } },
      hydraulic_network: {
        nodes: [
          {
            id: "reservoir",
            type: "reservoir",
            reservoir: { terminal_water_value_usd_per_hm3: 2500 },
          },
          {
            id: "lower",
            type: "reservoir",
            reservoir: { terminal_condition: "equal_initial" },
          },
          { id: "intake", type: "junction" },
        ],
      },
    },
    validation_payload: {},
  };
  const requests: { path: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const reply = (body: unknown) =>
        new Response(JSON.stringify(body), {
          headers: { "Content-Type": "application/json" },
        });
      if (path === "/api/auth/me")
        return reply({
          user: { id: 7, role: "analyst", display_name: "Analyst" },
          bootstrap_required: false,
        });
      if (path === "/api/auth/csrf") return reply({ csrf_token: "test" });
      if (
        path === "/api/scenario-versions/73" ||
        path === "/api/scenario-versions/74"
      )
        return reply({ scenario_version: version });
      if (path === "/api/scenarios/788")
        return reply({ scenario: { id: 788, project_id: 900, name: "Laja" } });
      if (path === "/api/projects/900")
        return reply({ project: { id: 900, name: "Laja" } });
      if (
        path === "/api/scenarios/788/hydraulic-simulation/prices" &&
        (!init?.method || init.method === "GET")
      )
        return reply({
          time_series_sets: [
            {
              id: 90,
              name: "CMg agosto",
              version_number: 1,
              revision_number: 1,
              signals: [{ signal_key: "price_usd_per_mwh" }],
              horizon: {
                start: "2026-08-01T00:00:00+00:00",
                end: "2026-08-01T04:00:00+00:00",
              },
            },
          ],
        });
      if (path.endsWith("/hydraulic-simulation/preview")) {
        requests.push({ path, body: JSON.parse(String(init?.body)) });
        return reply({
          preparation_hash: "reviewed",
          period_count: 8,
          preview_periods: [],
          generation_metadata: {},
        });
      }
      if (path.endsWith("/hydraulic-simulation/run")) {
        requests.push({ path, body: JSON.parse(String(init?.body)) });
        return reply({ id: 91, scenario_version_id: 74, status: "queued" });
      }
      if (path === "/api/runs/91")
        return reply({
          run: { id: 91, scenario_version_id: 74, status: "queued" },
        });
      return new Response("{}", { status: 404 });
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  expect(
    await screen.findByRole("heading", {
      name: "Preparar simulación hidráulica",
    }),
  ).toBeVisible();
  await screen.findByRole("option", { name: "CMg agosto · v1 · CMg" });
  await user.selectOptions(
    screen.getByLabelText("CMg (USD/MWh)"),
    "90:price_usd_per_mwh",
  );
  const water = screen.getByLabelText("Valor del agua · reservoir (USD/hm³)");
  const lowerWater = screen.getByLabelText("Valor del agua · lower (USD/hm³)");
  const gap = screen.getByLabelText("Gap relativo de parada (%)");
  expect(water).toHaveValue(2500);
  expect(lowerWater).toHaveValue(0);
  expect(gap).toHaveValue(2);
  expect(
    screen.queryByLabelText("Valor del agua · intake (USD/hm³)"),
  ).not.toBeInTheDocument();
  expect(screen.getByText(/su valor terminal es constante/)).toBeVisible();
  for (const input of [water, gap]) {
    for (const value of ["", "-1"]) {
      fireEvent.change(input, { target: { value } });
      expect(
        screen.getByRole("button", { name: "Revisar simulación" }),
      ).toBeDisabled();
    }
    fireEvent.change(input, { target: { value: "0" } });
    expect(
      screen.getByRole("button", { name: "Revisar simulación" }),
    ).toBeEnabled();
  }
  fireEvent.change(water, { target: { value: "50000" } });
  fireEvent.change(lowerWater, { target: { value: "1500" } });
  fireEvent.change(gap, { target: { value: "1" } });
  await user.selectOptions(screen.getByLabelText("Objetivo"), "energy");
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Para usar valores del agua positivos",
  );
  expect(
    screen.getByRole("button", { name: "Revisar simulación" }),
  ).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Objetivo"), "market_value");
  fireEvent.change(screen.getByLabelText("Inicio (UTC)"), {
    target: { value: "2026-08-01T01:00" },
  });
  fireEvent.change(screen.getByLabelText("Fin excluido (UTC)"), {
    target: { value: "2026-08-01T03:00" },
  });
  fireEvent.change(screen.getByLabelText("Resolución (horas)"), {
    target: { value: "0.25" },
  });
  expect(
    screen.getByRole("button", { name: "Ejecutar simulación" }),
  ).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Revisar simulación" }));
  expect(await screen.findByText("8 períodos preparados")).toBeVisible();
  for (const [input, value] of [
    [water, "51000"],
    [gap, "0.5"],
  ] as const) {
    fireEvent.change(input, { target: { value } });
    expect(
      screen.getByRole("button", { name: "Ejecutar simulación" }),
    ).toBeDisabled();
    await user.click(
      screen.getByRole("button", { name: "Revisar simulación" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Ejecutar simulación" }),
      ).toBeEnabled(),
    );
  }
  fireEvent.change(water, { target: { value: "50000" } });
  fireEvent.change(gap, { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("Resolución (horas)"), {
    target: { value: "0.5" },
  });
  expect(
    screen.getByRole("button", { name: "Ejecutar simulación" }),
  ).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Resolución (horas)"), {
    target: { value: "0.25" },
  });
  await user.click(screen.getByRole("button", { name: "Revisar simulación" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Ejecutar simulación" }),
    ).toBeEnabled(),
  );
  await user.click(screen.getByRole("button", { name: "Ejecutar simulación" }));
  expect(
    await screen.findByRole("heading", { name: "Ejecución 91" }),
  ).toBeVisible();
  expect(requests.at(-1)?.body).toMatchObject({
    range_start: "2026-08-01T01:00:00.000Z",
    range_end: "2026-08-01T03:00:00.000Z",
    resolution_hours: 0.25,
    objective: "market_value",
    price_time_series_set_id: 90,
    price_signal_key: "price_usd_per_mwh",
    expected_preparation_hash: "reviewed",
    terminal_water_values_usd_per_hm3: { reservoir: 50000, lower: 1500 },
    mip_rel_gap: 0.01,
  });
});

it("imports a CMg spreadsheet and selects its saved catalog series", async () => {
  const version = {
    id: 73,
    scenario_id: 788,
    version_number: 2,
    system_case_json: {},
  } as ScenarioVersionDetail;
  let imported = false;
  let uploaded: FormData | undefined;
  const series = {
    id: 95,
    name: "Precios octubre",
    version_number: 1,
    signals: [{ signal_key: "price_usd_per_mwh" }],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const reply = (data: unknown) =>
        new Response(JSON.stringify(data), {
          headers: { "Content-Type": "application/json" },
        });
      if (path === "/api/auth/csrf") return reply({ csrf_token: "test" });
      if (
        path === "/api/scenarios/788/hydraulic-simulation/prices" &&
        (!init?.method || init.method === "GET")
      )
        return reply({ time_series_sets: imported ? [series] : [] });
      if (path === "/api/scenarios/788/hydraulic-simulation/prices") {
        imported = true;
        uploaded = init?.body as FormData;
        return reply({ time_series_set: series });
      }
      return new Response("{}", { status: 404 });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <HydraulicSimulationForm version={version} projectId={900} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  expect(screen.getByLabelText("Gap relativo de parada (%)")).toHaveValue(0.01);
  await user.click(screen.getByText("Importar CMg desde Excel o CSV"));
  await user.type(
    screen.getByLabelText("Nombre de la serie de CMg"),
    "Precios octubre",
  );
  await user.upload(
    screen.getByLabelText("Archivo de CMg"),
    new File(["fixture"], "cmg.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }),
  );
  await user.click(
    screen.getByRole("button", { name: "Guardar CMg en catálogo" }),
  );
  await screen.findByRole("option", { name: "Precios octubre · v1 · CMg" });
  expect(screen.getByLabelText("CMg (USD/MWh)")).toHaveValue(
    "95:price_usd_per_mwh",
  );
  expect(uploaded?.get("set_name")).toBe("Precios octubre");
  expect((uploaded?.get("source_file") as File).name).toBe("cmg.xlsx");
});

it("shows the source version, objective and resolution in run provenance", () => {
  render(
    <MemoryRouter>
      <CaseHierarchyProvenanceSummary
        provenance={{
          kind: "hydraulic_simulation",
          source_scenario_version_id: 73,
          source_version_number: 2,
          hydraulic_simulation: {
            objective: "market_value",
            resolution_hours: 0.5,
            mip_rel_gap: 0,
            terminal_water_values_usd_per_hm3: { reservoir: 10000, lower: 0 },
          },
        }}
      />
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: "Versión 2" })).toHaveAttribute(
    "href",
    "/scenario-versions/73",
  );
  expect(screen.getByText("Ingresos con CMg")).toBeVisible();
  expect(screen.getByText("0.5 h")).toBeVisible();
  expect(screen.getByText("0 %")).toBeVisible();
  expect(screen.getByText("10000 USD/hm³")).toBeVisible();
  expect(screen.getByText("0 USD/hm³")).toBeVisible();
});
