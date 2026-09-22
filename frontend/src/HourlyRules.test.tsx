import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { App } from "./App";

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const candidate = {
  signal_id: 12,
  revision_id: 21,
  content_hash: "a".repeat(64),
  object_id: 7,
  semantic_type_key: "availability_factor",
  dimension_key: "dimensionless",
  binding_role_key: "rule_availability",
  unit_key: "dimensionless",
  display_name: "Disponibilidad programada",
  set_name: "Programa semanal",
  series_kind: "catalog",
  revision_number: 2,
};

it("selects an exact input through the protected steps and saves it only in the rule draft", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/projects/1/linkable-objects/7/rules",
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
      if (path.endsWith("/input-candidates"))
        return json({ items: [candidate], next_cursor: null });
      if (path.endsWith("/rules") && init?.method === "POST") {
        saved = JSON.parse(String(init.body));
        return json({ ...saved, id: "r1", revision: 1 }, 201);
      }
      if (path.endsWith("/rules/r1"))
        return json({ ...saved, id: "r1", revision: 1 });
      if (path.endsWith("/rules"))
        return json({
          object: { display_name: "Unidad Norte" },
          items: [],
          runtime: null,
        });
      if (path.endsWith("/applications")) return json({ items: [] });
      return json({ detail: path }, 404);
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await user.click(
    await screen.findByRole("button", { name: "Seleccionar entrada" }),
  );
  await user.click(screen.getByLabelText("Serie genérica del catálogo"));
  await user.click(screen.getByRole("button", { name: "Continuar selección" }));
  await user.click(await screen.findByLabelText(/Disponibilidad programada/));
  await user.click(screen.getByRole("button", { name: "Continuar selección" }));
  expect(screen.getByText(/Revisión 21/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Continuar selección" }));
  expect(saved).toBeUndefined();
  await user.click(
    screen.getByRole("button", { name: "Usar entrada en borrador" }),
  );
  expect(saved).toBeUndefined();
  await user.click(screen.getByRole("button", { name: "Guardar borrador" }));
  await screen.findByText(/Borrador guardado/);
  expect(saved?.inputs).toEqual([
    {
      alias: "disponibilidad",
      object_id: 7,
      signal_id: 12,
      revision_id: 21,
      content_hash: "a".repeat(64),
      dimension_key: "dimensionless",
      semantic_type_key: "availability_factor",
      binding_role_key: "rule_availability",
    },
  ]);
});

it("shows hourly bounds and numeric outputs with units, pagination and stale validation", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/projects/1/linkable-objects/7/rules?scenario_id=4&constraint_test=j1",
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/auth/me")
        return json({
          user: { id: 3, role: "analyst", is_active: true },
          bootstrap_required: false,
        });
      if (path.endsWith("/rules"))
        return json({
          object: { display_name: "Unidad" },
          items: [{ id: "r1", name: "Horario", revision: 1 }],
          runtime: { sdk: "reg-003.1" },
        });
      if (path.endsWith("/rules/r1"))
        return json({
          id: "r1",
          revision: 1,
          name: "Horario",
          code: "def construir(ctx): pass",
          parameters: [],
          inputs: [],
        });
      if (path.endsWith("/scope"))
        return json({
          variants: [{ id: 2, display_name: "Base" }],
          range_start: "2026-01-01T00:00:00",
          range_end: "2026-01-02T00:00:00",
        });
      if (path.endsWith("/applications"))
        return json({
          items: [
            {
              id: "a1",
              status: "active",
              variant_id: 2,
              publication_id: "pub1",
              revision: 1,
              validation_status: "stale",
              validation_error: { message: "Entrada obsoleta: disponibilidad" },
            },
          ],
        });
      if (path.endsWith("/tests/j1"))
        return json({
          id: "j1",
          status: "succeeded",
          publication_id: "pub1",
          compilation_scope: {
            scenario_id: 4,
            variant_id: 2,
            range_start: "2026-01-01T00:00:00",
            range_end: "2026-01-02T00:00:00",
          },
          result: {
            ir: { rows: [] },
            bounds: Array.from({ length: 24 }, (_, period) => ({
              period,
              minimum: 2,
              maximum: 20,
              unit: "m3_per_s",
            })),
            outputs: [
              {
                name: "limite_calculado",
                period: 23,
                value: 17.5,
                unit: "m3_per_s",
              },
            ],
          },
        });
      return json({ detail: path }, 404);
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  expect(
    await screen.findByRole("table", { name: "Límites y salidas horarias" }),
  ).toBeVisible();
  expect(
    screen.getByRole("img", { name: /Curvas horarias.*m³\/s/ }),
  ).toBeVisible();
  expect(screen.queryByRole("cell", { name: "17.5" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Siguientes períodos" }));
  expect(screen.getByRole("cell", { name: "17.5" })).toBeVisible();
  expect(screen.getByText("Entrada obsoleta: disponibilidad")).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Ejecutar variante con reglas" }),
  ).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Probar revisión fijada" }),
  ).toBeVisible();
});

it("locates an input grid refusal by alias and period before application", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/projects/1/linkable-objects/7/rules?scenario_id=4",
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
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
          items: [{ id: "r1", name: "Horario", revision: 1 }],
          runtime: { sdk: "reg-003.1" },
        });
      if (path.endsWith("/rules/r1"))
        return json({
          id: "r1",
          revision: 1,
          name: "Horario",
          code: "def construir(ctx): pass",
          parameters: [],
        });
      if (path.endsWith("/scope"))
        return json({
          variants: [{ id: 2, display_name: "Base" }],
          range_start: "2026-01-01T00:00:00",
          range_end: "2026-01-01T04:00:00",
        });
      if (path.endsWith("/applications")) return json({ items: [] });
      if (path.endsWith("/publications"))
        return json({ id: "pub1", draft_revision: 1 }, 201);
      if (path.endsWith("/tests"))
        return json(
          {
            detail: {
              code: "RULE_INPUT_INVALID",
              alias: "afluente",
              period: 3,
              message: "Falta un intervalo",
            },
          },
          422,
        );
      return json({ detail: path }, 404);
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await user.click(
    await screen.findByRole("button", { name: "Publicar revisión" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Probar restricciones" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "afluente · período 4: Falta un intervalo",
  );
  expect(
    screen.getByRole("button", { name: "Aplicar a variante" }),
  ).toBeDisabled();
});
