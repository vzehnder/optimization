import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { App } from "./App";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RuleSeriesPublications } from "./RuleSeriesPublications";

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const scope = {
  scenario_id: 4,
  variant_id: 2,
  range_start: "2026-01-01T00:00:00",
  range_end: "2026-01-01T04:00:00",
};

it("publishes a calculated output through the four protected steps and returns to its catalog", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/projects/1/linkable-objects/7/rules?scenario_id=4&constraint_test=j1",
  );
  let submitted: Record<string, unknown> | undefined;
  let key: string | null = null;
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
      if (path.endsWith("/rules"))
        return json({
          object: { display_name: "Unidad" },
          items: [{ id: "r1", name: "Cálculo", revision: 1 }],
          runtime: { sdk: "reg-006.1" },
        });
      if (path.endsWith("/rules/r1"))
        return json({
          id: "r1",
          revision: 1,
          name: "Cálculo",
          code: "def construir(ctx): pass",
          parameters: [],
        });
      if (path.endsWith("/scope"))
        return json({ variants: [{ id: 2, display_name: "Base" }], ...scope });
      if (path.endsWith("/object-candidates") || path.endsWith("/applications"))
        return json({ items: [] });
      if (path.endsWith("/series-options"))
        return json({
          outputs: [
            {
              name: "potencia",
              unit_key: "mw",
              period_count: 4,
              classifications: [
                {
                  semantic_type_key: "renewable_available_power",
                  display_name: "Potencia renovable disponible",
                  object_roles: [],
                },
              ],
            },
          ],
        });
      if (path.endsWith("/series-publications")) {
        if (init?.method === "POST") {
          submitted = JSON.parse(String(init.body));
          key = new Headers(init.headers).get("Idempotency-Key");
          return json(
            {
              id: "recipe1",
              set_id: 10,
              signal_id: 12,
              revision_id: 21,
              revision_number: 1,
              definition: submitted,
              validation_status: "current",
              lineage: { job_id: "j1" },
            },
            201,
          );
        }
        return json({ items: [] });
      }
      if (path.endsWith("/tests/j1"))
        return json({
          id: "j1",
          status: "succeeded",
          publication_id: "pub1",
          compilation_scope: scope,
          grid: [0, 1, 2, 3].map((t) => ({
            timestamp: `2026-01-01T0${t}:00:00`,
            duration_hours: 1,
          })),
          result: {
            ir: { rows: [] },
            outputs: [20, 10, 15, 20].map((value, period) => ({
              name: "potencia",
              unit: "mw",
              value,
              period,
            })),
          },
        });
      return json({ detail: path }, 404);
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await waitFor(
    () =>
      expect(
        screen.getByRole("button", { name: "Publicar serie calculada" }),
      ).toBeEnabled(),
    { timeout: 5000 },
  );
  await user.click(
    screen.getByRole("button", { name: "Publicar serie calculada" }),
  );
  await user.click(screen.getByLabelText("Catálogo del proyecto"));
  await user.click(
    screen.getByRole("button", { name: "Continuar publicación" }),
  );
  await user.type(
    screen.getByLabelText("Nombre de la serie"),
    "Potencia disponible",
  );
  await user.type(
    screen.getByLabelText("Clave de la serie"),
    "potencia_disponible",
  );
  await user.selectOptions(
    screen.getByLabelText("Clasificación de la salida"),
    "renewable_available_power",
  );
  await user.click(
    screen.getByRole("button", { name: "Continuar publicación" }),
  );
  expect(screen.getByText(/4 intervalos completos/)).toBeVisible();
  await user.click(
    screen.getByRole("button", { name: "Continuar publicación" }),
  );
  expect(submitted).toBeUndefined();
  await user.type(
    screen.getByLabelText("Motivo de publicación"),
    "Disponibilidad revisada",
  );
  await user.click(
    screen.getByRole("button", { name: "Confirmar publicación" }),
  );
  expect(await screen.findByText(/Serie publicada.*revisión 1/)).toBeVisible();
  expect(submitted).toMatchObject({
    job_id: "j1",
    output_name: "potencia",
    name: "Potencia disponible",
    series_key: "potencia_disponible",
    unit_key: "mw",
    semantic_type_key: "renewable_available_power",
    series_kind: "catalog",
    reason: "Disponibilidad revisada",
  });
  expect(key).toBeTruthy();
  expect(
    screen.getByRole("link", { name: "Ver serie publicada" }),
  ).toHaveAttribute("href", expect.stringContaining("inspector=12"));
});

it("reviews a stale recipe and explicitly regenerates it using the new successful test", async () => {
  const definition = {
    name: "Disponibilidad",
    series_key: "factor",
    series_kind: "object_specific",
    output_name: "factor",
    semantic_type_key: "availability_factor",
    unit_key: "dimensionless",
    intended_binding_role_key: "rule_availability",
  };
  const recipe = {
    id: "calc1",
    signal_id: 12,
    revision_id: 21,
    revision_number: 1,
    definition,
    validation_status: "stale",
    validation_error: { message: "Cambió disponibilidad" },
  };
  let request: Record<string, unknown> | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/auth/csrf") return json({ csrf_token: "test" });
      if (path.endsWith("/series-publications"))
        return json({ items: [recipe] });
      if (path.endsWith("/series-options"))
        return json({
          outputs: [
            {
              name: "factor",
              unit_key: "dimensionless",
              period_count: 1,
              classifications: [
                {
                  semantic_type_key: "availability_factor",
                  display_name: "Disponibilidad",
                  object_roles: ["rule_availability"],
                },
              ],
            },
          ],
        });
      if (path.endsWith("/regenerations")) {
        request = JSON.parse(String(init?.body));
        return json(
          {
            ...recipe,
            revision_id: 22,
            revision_number: 2,
            validation_status: "current",
          },
          201,
        );
      }
      return json({ detail: path }, 404);
    }),
  );
  const user = userEvent.setup();
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <RuleSeriesPublications
          path="/api/projects/1/linkable-objects/7/rules/r1"
          disabled={false}
          job={{
            id: "j2",
            status: "succeeded",
            grid: [{ timestamp: scope.range_start }],
            result: {
              outputs: [
                {
                  name: "factor",
                  period: 0,
                  value: 0.5,
                  unit: "dimensionless",
                },
              ],
            },
          }}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(
    await screen.findByText(/Receta obsoleta: Cambió disponibilidad/),
  ).toBeVisible();
  await user.click(
    screen.getByRole("button", { name: "Regenerar Disponibilidad" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Continuar publicación" }),
  );
  expect(screen.getByLabelText("Nombre de la serie")).toBeDisabled();
  await user.click(
    screen.getByRole("button", { name: "Continuar publicación" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Continuar publicación" }),
  );
  expect(screen.getByText(/revalidar.*explícitamente/)).toBeVisible();
  await user.type(
    screen.getByLabelText("Motivo de publicación"),
    "Actualizar disponibilidad",
  );
  await user.click(
    screen.getByRole("button", { name: "Confirmar regeneración" }),
  );
  expect(await screen.findByText(/Serie publicada.*revisión 2/)).toBeVisible();
  expect(request).toEqual({
    job_id: "j2",
    expected_revision_id: 21,
    reason: "Actualizar disponibilidad",
  });
});
