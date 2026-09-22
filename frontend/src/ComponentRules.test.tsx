import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { App } from "./App";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

it("publishes, previews and applies a flow restriction to the selected variant", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/projects/1/linkable-objects/7/rules?rule=r1&scenario_id=4",
  );
  let applied = false;
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
          items: [{ id: "r1", name: "Máximo", revision: 1 }],
          runtime: { sdk: "reg-002.1" },
        });
      if (path.endsWith("/rules/scope"))
        return json({
          variants: [{ id: 2, display_name: "Invierno" }],
          range_start: "2026-01-01T00:00:00",
          range_end: "2026-01-01T04:00:00",
        });
      if (path.endsWith("/rules/r1"))
        return json({
          id: "r1",
          name: "Máximo",
          revision: 1,
          code: "def construir(ctx): pass",
          parameters: [],
        });
      if (path.endsWith("/publications"))
        return json({ id: "pub1", draft_revision: 1 }, 201);
      if (path.endsWith("/tests")) return json({ id: "job1" }, 202);
      if (path.endsWith("/tests/job1"))
        return json({
          id: "job1",
          status: "succeeded",
          publication_id: "pub1",
          compilation_scope: {
            scenario_id: 4,
            variant_id: 2,
            range_start: "2026-01-01T00:00:00",
            range_end: "2026-01-01T04:00:00",
          },
          result: {
            ir: {
              rows: [
                {
                  name: "maximo",
                  line: 3,
                  period: 0,
                  relation: "<=",
                  constant: -5,
                  unit: "m3_per_s",
                  terms: [{ coefficient: 1 }],
                },
              ],
            },
          },
        });
      if (path.endsWith("/applications")) {
        if (init?.method === "POST") {
          applied = true;
          return json(
            {
              id: "a1",
              status: "active",
              variant_id: 2,
              publication_id: "pub1",
              revision: 1,
            },
            201,
          );
        }
        return json({
          items: applied
            ? [
                {
                  id: "a1",
                  status: "active",
                  variant_id: 2,
                  publication_id: "pub1",
                  revision: 1,
                },
              ]
            : [],
        });
      }
      return json({ detail: path }, 404);
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await user.click(
    await screen.findByRole("button", { name: "Publicar revisión" }),
  );
  await user.click(
    await screen.findByRole("button", { name: "Probar restricciones" }),
  );
  expect(await screen.findByText("maximo")).toBeVisible();
  expect(screen.getByText(/1 restricción/)).toBeVisible();
  expect(applied).toBe(false);
  await user.type(
    screen.getByLabelText("Motivo de aplicación o desactivación"),
    "Límite operativo",
  );
  await user.click(screen.getByRole("button", { name: "Aplicar a variante" }));
  expect(await screen.findByText(/Revisión pub1 aplicada/)).toBeVisible();
});

it.each([
  {
    status: "succeeded",
    result: { output: { value: 60, unit: "m3_per_s" } },
    expected: "60 m³/s",
  },
  {
    status: "failed",
    result: {
      error: {
        code: "RULE_CODE_ERROR",
        line: 2,
        message: "La cantidad debe ser finita",
      },
    },
    expected: "RULE_CODE_ERROR · línea 2: La cantidad debe ser finita",
  },
])(
  "reopens a $status preview with its numerical result or localized error",
  async ({ status, result, expected }) => {
    window.history.replaceState(
      {},
      "",
      "/react/projects/1/linkable-objects/7/rules?rule=r1&test=j1",
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
            items: [{ id: "r1", name: "Máximo", revision: 1 }],
            runtime: null,
          });
        if (path.endsWith("/rules/r1"))
          return json({
            id: "r1",
            name: "Máximo",
            revision: 1,
            code: "def construir(ctx): pass",
            parameters: [],
          });
        if (path.endsWith("/tests/j1"))
          return json({
            id: "j1",
            status,
            result,
            draft_revision: 1,
            code_hash: "abc",
            context_hash: "def",
          });
        return json({ detail: path }, 404);
      }),
    );
    render(<App />);
    expect(await screen.findByText(expected)).toBeVisible();
  },
);

it("saves and reopens a contextual Python draft with units and a return link", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/projects/1/linkable-objects/7/rules?return_to=%2Fscenarios%2F4%2Fhydraulic-diagram",
  );
  let draft: Record<string, unknown> | null = null;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/auth/me")
        return json({
          user: {
            id: 3,
            email: "a@test",
            display_name: "Analista",
            role: "analyst",
            is_active: true,
          },
          bootstrap_required: false,
        });
      if (path === "/api/auth/csrf") return json({ csrf_token: "test" });
      if (path.endsWith("/rules") && init?.method === "POST") {
        draft = {
          ...JSON.parse(String(init.body)),
          id: "r1",
          revision: 1,
          status: "draft",
        };
        return json(draft, 201);
      }
      if (path.endsWith("/rules"))
        return json({
          object: { display_name: "Unidad Norte" },
          items: draft ? [draft] : [],
          runtime: null,
        });
      if (path.endsWith("/rules/r1")) return json(draft);
      return json({ detail: path }, 404);
    }),
  );
  const page = render(<App />);
  const user = userEvent.setup();
  await screen.findByRole("heading", { name: "Cálculos y restricciones" });
  const name = await screen.findByLabelText("Nombre de la regla");
  await user.clear(name);
  await user.type(name, "Máximo disponible");
  await user.click(screen.getByRole("button", { name: "Guardar borrador" }));
  await screen.findByText("Borrador guardado · revisión 1");
  page.unmount();
  render(<App />);
  expect(await screen.findByDisplayValue("Máximo disponible")).toBeVisible();
  expect(
    screen.getByRole("textbox", { name: "Código Python" }),
  ).toHaveTextContent("def construir(ctx)");
  expect(screen.getByDisplayValue("m3_per_s")).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Volver a la unidad" }),
  ).toHaveAttribute("href", "/react/scenarios/4/hydraulic-diagram");
  expect(
    screen.getByText(/Las pruebas no modifican corridas ni series/),
  ).toBeVisible();
});

it("starts an asynchronous preview and lets the analyst cancel it", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/projects/1/linkable-objects/7/rules?rule=r1",
  );
  let cancelled = false;
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
          object: { display_name: "Unidad Norte" },
          items: [{ id: "r1", name: "Máximo", revision: 1 }],
          runtime: { sdk: "reg-001.1" },
        });
      if (path.endsWith("/rules/r1"))
        return json({
          id: "r1",
          name: "Máximo",
          revision: 1,
          code: "def construir(ctx):\n    while True: pass",
          parameters: [],
        });
      if (path.endsWith("/tests") && init?.method === "POST")
        return json({ id: "j1", status: "queued" }, 202);
      if (path.endsWith("/cancel")) {
        cancelled = true;
        return json({ id: "j1", status: "cancelled" });
      }
      if (path.endsWith("/tests/j1"))
        return json({
          id: "j1",
          status: cancelled ? "cancelled" : "running",
          draft_revision: 1,
          code_hash: "abc",
          context_hash: "def",
          result: null,
        });
      return json({ detail: path }, 404);
    }),
  );
  render(<App />);
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: "Probar borrador" }),
  );
  await screen.findByText("Ejecutando");
  await user.click(screen.getByRole("button", { name: "Cancelar prueba" }));
  expect(await screen.findByText("Cancelada")).toBeVisible();
});

it("opens rules from the saved hydraulic unit and retains its diagram as return destination", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/scenarios/4/hydraulic-plants/plant/units/unit/rules",
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
      if (path.endsWith("/rule-context"))
        return json({ project_id: 1, object_id: 7 });
      if (path.endsWith("/rules"))
        return json({
          object: { display_name: "Unidad Norte" },
          items: [],
          runtime: null,
        });
      return json({ detail: path }, 404);
    }),
  );
  render(<App />);
  expect(
    await screen.findByText("Unidad: Unidad Norte · Proyecto 1"),
  ).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Volver a la unidad" }),
  ).toHaveAttribute("href", "/react/scenarios/4/hydraulic-diagram");
});
