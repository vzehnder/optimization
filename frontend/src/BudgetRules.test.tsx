import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { App } from "./App";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RuleApplications } from "./RuleApplications";

const json = (value: unknown) =>
  new Response(JSON.stringify(value), {
    headers: { "Content-Type": "application/json" },
  });

it("enables publication after saving an existing window policy returned in canonical key order", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/projects/1/linkable-objects/7/rules?rule=r1&scenario_id=4",
  );
  let draft = {
    id: "r1",
    revision: 1,
    name: "Agua",
    code: "def construir(ctx): pass",
    parameters: [],
    windows: { kind: "horizon", partial: "reject", timezone: "UTC" },
  };
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
      if (path.endsWith("/rules/r1")) {
        if (init?.method === "PUT") {
          const body = JSON.parse(String(init.body));
          draft = {
            ...draft,
            ...body,
            revision: 2,
            windows: {
              kind: body.windows.kind,
              partial: body.windows.partial,
              timezone: body.windows.timezone,
            },
          };
        }
        return json(draft);
      }
      if (path.endsWith("/rules"))
        return json({
          object: { display_name: "Unidad" },
          items: [draft],
          runtime: null,
        });
      if (path.endsWith("/scope"))
        return json({ variants: [], range_start: "", range_end: "" });
      return json({ items: [] });
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await user.selectOptions(
    await screen.findByLabelText("Ventanas de presupuesto"),
    "civil_day",
  );
  await user.click(
    screen.getByLabelText("Acepto días parciales con el presupuesto completo"),
  );
  await user.click(screen.getByRole("button", { name: "Guardar borrador" }));
  await screen.findByText(/Borrador guardado · revisión 2/);
  expect(
    screen.getByRole("button", { name: "Publicar revisión" }),
  ).toBeEnabled();
});

it("previews actual window duration, full budget and component terms with bounded pagination", async () => {
  const scope = {
    scenario_id: 4,
    variant_id: 2,
    range_start: "2024-11-03T04:00:00Z",
    range_end: "2024-11-04T05:00:00Z",
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/applications")) return json({ items: [] });
      if (path.endsWith("/scope"))
        return json({ ...scope, variants: [{ id: 2, display_name: "Base" }] });
      if (path.endsWith("/tests/j1"))
        return json({
          id: "j1",
          status: "succeeded",
          compilation_scope: scope,
          objects: [
            {
              id: 7,
              display_name: "Unidad Norte",
              variables: { potencia: "mw" },
            },
          ],
          grid: Array.from({ length: 25 }, (_, i) => ({
            timestamp: new Date(
              Date.parse(scope.range_start) + i * 3600000,
            ).toISOString(),
          })),
          result: {
            windows: {
              kind: "civil_day",
              timezone: "America/New_York",
              partial: "reject",
            },
            ir: {
              rows: [
                {
                  name: "energia",
                  period: 24,
                  line: 3,
                  relation: "<=",
                  unit: "mwh",
                  constant: -12,
                  window: {
                    start: scope.range_start,
                    end: scope.range_end,
                    duration_hours: 25,
                    periods: Array.from({ length: 25 }, (_, i) => i),
                    partial: false,
                  },
                  terms: Array.from({ length: 25 }, (_, i) => ({
                    object_id: 7,
                    variable: "potencia",
                    period: i,
                    coefficient: 1,
                    unit: "h",
                  })),
                },
              ],
            },
          },
        });
      return json({});
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
  expect(await screen.findByText(/Duración real: 25 h/)).toBeVisible();
  expect(screen.getByText(/Día completo · America\/New_York/)).toBeVisible();
  expect(screen.getByText(/Presupuesto efectivo: ≤ 12 MWh/)).toBeVisible();
  expect(screen.getByText(/25 períodos · 25 términos/)).toBeVisible();
  expect(screen.getByText(/Inicio UTC: 2024-11-03T04:00:00Z/)).toBeVisible();
  expect(screen.getByText(/Fin UTC: 2024-11-04T05:00:00Z/)).toBeVisible();
  expect(
    screen.queryByText(/Unidad Norte.potencia\[25/),
  ).not.toBeInTheDocument();
  await user.click(
    screen.getByRole("button", { name: "Más términos de energia" }),
  );
  expect(screen.getByText(/Unidad Norte.potencia\[25/)).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Aplicar a variante" }),
  ).toBeDisabled();
});

it("saves the civil timezone and explicit partial-day consent without applying on edit", async () => {
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
      if (path.endsWith("/object-candidates")) return json({ items: [] });
      if (path.endsWith("/rules") && init?.method === "POST") {
        saved = JSON.parse(String(init.body));
        return json({ ...saved, id: "r1", revision: 1 });
      }
      if (path.endsWith("/rules/r1"))
        return json({ ...saved, id: "r1", revision: 1 });
      if (path.endsWith("/rules"))
        return json({
          object: { display_name: "Unidad" },
          items: saved ? [{ ...saved, id: "r1", revision: 1 }] : [],
          runtime: null,
        });
      if (path.endsWith("/applications")) return json({ items: [] });
      if (path.endsWith("/scope"))
        return json({ variants: [], range_start: "", range_end: "" });
      return json({});
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await user.selectOptions(
    await screen.findByLabelText("Ventanas de presupuesto"),
    "civil_day",
  );
  await user.clear(screen.getByLabelText("Zona horaria IANA"));
  await user.type(
    screen.getByLabelText("Zona horaria IANA"),
    "America/Santiago",
  );
  expect(
    screen.getByLabelText("Acepto días parciales con el presupuesto completo"),
  ).not.toBeChecked();
  await user.click(
    screen.getByLabelText("Acepto días parciales con el presupuesto completo"),
  );
  expect(saved).toBeUndefined();
  await user.click(screen.getByRole("button", { name: "Guardar borrador" }));
  await waitFor(() =>
    expect(saved?.windows).toEqual({
      kind: "civil_day",
      timezone: "America/Santiago",
      partial: "allow",
    }),
  );
  expect(
    screen.getByRole("link", { name: "Volver a la unidad" }),
  ).toHaveAttribute("href", "/react/scenarios/4/hydraulic-diagram");
});
