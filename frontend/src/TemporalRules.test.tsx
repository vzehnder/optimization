import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { App } from "./App";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RuleApplications } from "./RuleApplications";

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });

it("shows omitted comparisons and exact term instants and requires a new preview when the horizon changes", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/applications")) return json({ items: [] });
      const scope = {
        scenario_id: 4,
        variant_id: 2,
        range_start: "2026-01-01T00:00:00",
        range_end: "2026-01-01T02:30:00",
      };
      if (path.endsWith("/scope"))
        return json({ ...scope, variants: [{ id: 2, display_name: "Base" }] });
      if (path.endsWith("/tests/j1"))
        return json({
          id: "j1",
          status: "succeeded",
          compilation_scope: scope,
          grid: [
            { timestamp: "2026-01-01T00:00:00Z", duration_hours: 0.5 },
            { timestamp: "2026-01-01T00:30:00Z", duration_hours: 2 },
          ],
          objects: [object],
          result: {
            temporal: {
              first_period: "omit",
              initial_values: [],
              omitted_periods: [0],
            },
            ir: {
              rows: [
                {
                  name: "subida",
                  period: 1,
                  line: 4,
                  relation: "<=",
                  unit: "mw",
                  constant: -2,
                  terms: [
                    {
                      object_id: 7,
                      variable: "potencia",
                      period: 0,
                      coefficient: -1,
                    },
                    {
                      object_id: 7,
                      variable: "potencia",
                      period: 1,
                      coefficient: 1,
                    },
                  ],
                },
              ],
            },
          },
        });
      return json({}, 404);
    }),
  );
  const user = userEvent.setup();
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/?scenario_id=4&constraint_test=j1"]}>
        <RuleApplications
          root="/rules"
          ruleId="r1"
          revision={1}
          disabled={false}
          available
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(
    await screen.findByText(/Primera comparación omitida: período 1/),
  ).toBeVisible();
  expect(
    screen.getByText(/Unidad Norte.potencia\[1 · 2026-01-01T00:00:00Z\]/),
  ).toHaveTextContent("Unidad Norte.potencia[2 · 2026-01-01T00:30:00Z]");
  expect(screen.getByText(/Distancia entre inicios: 0.5 h/)).toBeVisible();
  await user.type(
    screen.getByLabelText("Motivo de aplicación o desactivación"),
    "Rampas",
  );
  expect(
    screen.getByRole("button", { name: "Aplicar a variante" }),
  ).toBeEnabled();
  await user.clear(screen.getByLabelText("Inicio UTC"));
  expect(
    screen.getByRole("button", { name: "Aplicar a variante" }),
  ).toBeDisabled();
  expect(screen.getByText(/El horizonte o la variante cambió/)).toBeVisible();
});
const object = {
  id: 7,
  key: "unit",
  display_name: "Unidad Norte",
  kind: "hydraulic_unit",
  variables: { caudal: "m3_per_s", potencia: "mw" },
};

it("reports a negative reference as its Python index instead of a fictitious period zero", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/applications")) return json({ items: [] });
      if (path.endsWith("/tests/j1"))
        return json({
          id: "j1",
          status: "failed",
          result: {
            error: {
              code: "RULE_CODE_ERROR",
              line: 2,
              period: -1,
              message: "Índice fuera del horizonte",
            },
          },
        });
      return json({}, 404);
    }),
  );
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/?constraint_test=j1"]}>
        <RuleApplications
          root="/rules"
          ruleId="r1"
          revision={1}
          disabled={false}
          available
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("índice -1");
  expect(screen.getByRole("alert")).not.toHaveTextContent("período 0");
});

it("saves an explicit initial value with its unit and instant and preserves the contextual return", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/projects/1/linkable-objects/7/rules?scenario_id=4&return_to=/scenarios/4/hydraulic-diagram",
  );
  let saved: Record<string, unknown> | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/auth/me")
        return json({
          user: { id: 3, role: "analyst", is_active: true },
          bootstrap_required: false,
        });
      if (path === "/api/auth/csrf") return json({ csrf_token: "test" });
      if (path.endsWith("/object-candidates")) return json({ items: [object] });
      if (path.endsWith("/rules") && init?.method === "POST") {
        saved = JSON.parse(String(init.body));
        return json({ ...saved, id: "r1", revision: 1 }, 201);
      }
      if (path.endsWith("/rules/r1"))
        return json({ ...saved, id: "r1", revision: 1 });
      if (path.endsWith("/rules"))
        return json({
          object,
          items: saved ? [{ ...saved, id: "r1", revision: 1 }] : [],
          runtime: null,
        });
      if (path.endsWith("/applications")) return json({ items: [] });
      if (path.endsWith("/scope"))
        return json({ variants: [], range_start: "", range_end: "" });
      return json({}, 404);
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole(
    "option",
    { name: "Unidad Norte · unit" },
    { timeout: 5000 },
  );
  await user.selectOptions(
    screen.getByLabelText("Política del primer período"),
    "initial",
  );
  await user.click(
    screen.getByRole("button", { name: "Agregar valor inicial" }),
  );
  await user.selectOptions(
    screen.getByLabelText("Variable inicial 1"),
    "7:potencia",
  );
  await user.type(screen.getByLabelText("Valor inicial 1"), "2");
  await user.type(
    screen.getByLabelText("Instante inicial 1"),
    "2025-12-31T23:30:00Z",
  );
  expect(saved).toBeUndefined();
  await user.click(screen.getByRole("button", { name: "Guardar borrador" }));
  await waitFor(() =>
    expect(saved?.temporal).toEqual({
      first_period: "initial",
      initial_values: [
        {
          object_id: 7,
          variable: "potencia",
          value: 2,
          unit: "mw",
          timestamp: "2025-12-31T23:30:00Z",
        },
      ],
    }),
  );
  expect(
    screen.getByRole("link", { name: "Volver a la unidad" }),
  ).toHaveAttribute("href", "/react/scenarios/4/hydraulic-diagram");
});
