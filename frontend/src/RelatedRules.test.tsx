import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { App } from "./App";

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const objects = [
  {
    id: 7,
    key: "unit",
    display_name: "Unidad Norte",
    kind: "hydraulic_unit",
    variables: { caudal: "m3_per_s", potencia: "mw" },
  },
  {
    id: 9,
    key: "plant",
    display_name: "Central completa",
    kind: "hydraulic_plant",
    variables: { potencia: "mw" },
    member_ids: [7, 8],
  },
  {
    id: 10,
    key: "reservoir",
    display_name: "Embalse",
    kind: "hydraulic_node",
    variables: { almacenamiento: "hm3", vertimiento: "m3_per_s" },
  },
];

it("discovers real variables and saves a plant alias without applying it", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/projects/1/linkable-objects/7/rules?scenario_id=4&return_to=/scenarios/4/hydraulic-diagram",
  );
  let saved: Record<string, unknown> | undefined;
  let inputObject: string | null = null;
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
      if (path.endsWith("/object-candidates")) return json({ items: objects });
      if (path.endsWith("/input-candidates")) {
        inputObject = new URL(
          String(input),
          "http://localhost",
        ).searchParams.get("reference_object_id");
        return json({ items: [], next_cursor: null });
      }
      if (path.endsWith("/rules") && init?.method === "POST") {
        saved = JSON.parse(String(init.body));
        return json({ ...saved, id: "r1", revision: 1 }, 201);
      }
      if (path.endsWith("/rules/r1") && init?.method === "PUT")
        return json(
          {
            detail: {
              alias: "central",
              line: 3,
              message: "El objeto ya no pertenece al modelo",
            },
          },
          422,
        );
      if (path.endsWith("/rules/r1"))
        return json({ ...saved, id: "r1", revision: 1 });
      if (path.endsWith("/rules"))
        return json({
          object: { id: 7, display_name: "Unidad Norte" },
          items: saved ? [{ ...saved, id: "r1", revision: 1 }] : [],
          runtime: null,
        });
      if (path.endsWith("/applications")) return json({ items: [] });
      if (path.endsWith("/scope"))
        return json({ variants: [], range_start: "", range_end: "" });
      return json({ detail: path }, 404);
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole(
    "option",
    { name: "Central completa · plant" },
    { timeout: 5000 },
  );
  await user.selectOptions(screen.getByLabelText("Objeto a relacionar"), "9");
  await user.type(screen.getByLabelText("Alias del objeto"), "central");
  await user.click(screen.getByRole("button", { name: "Agregar alias" }));
  expect(
    screen.getByText("ctx.objetos.central.potencia[t] · MW"),
  ).toBeVisible();
  expect(screen.queryByText(/\.cota\[t\]/)).not.toBeInTheDocument();
  expect(saved).toBeUndefined();
  await user.selectOptions(
    screen.getByLabelText("Objeto del parámetro capacidad"),
    "9",
  );
  await user.click(screen.getByRole("button", { name: "Seleccionar entrada" }));
  await user.selectOptions(screen.getByLabelText("Objeto de la entrada"), "9");
  await user.click(screen.getByRole("button", { name: "Continuar selección" }));
  await screen.findByText("No hay entradas compatibles en esta página.");
  expect(inputObject).toBe("9");
  await user.click(screen.getByRole("button", { name: "Guardar borrador" }));
  await screen.findByText(/Borrador guardado/);
  expect(saved?.aliases).toEqual([{ alias: "central", object_id: 9 }]);
  expect(saved?.scenario_id).toBe(4);
  expect((saved?.parameters as { object_id?: number }[])[0].object_id).toBe(9);
  expect(
    screen.getByRole("link", { name: "Volver a la unidad" }),
  ).toHaveAttribute("href", "/react/scenarios/4/hydraulic-diagram");
  await screen.findByRole("button", { name: "Capacidad por disponibilidad" });
  await user.click(screen.getByRole("button", { name: "Guardar borrador" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "central · línea 3: El objeto ya no pertenece al modelo",
  );
});

it("identifies both affected units and the power unit in the compiled preview", async () => {
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
      if (path.endsWith("/object-candidates")) return json({ items: objects });
      if (path.endsWith("/rules"))
        return json({
          object: { id: 7, display_name: "Unidad Norte" },
          items: [{ id: "r1", name: "Conjunto", revision: 1 }],
          runtime: null,
        });
      if (path.endsWith("/rules/r1"))
        return json({
          id: "r1",
          revision: 1,
          name: "Conjunto",
          code: "def construir(ctx): pass",
          parameters: [],
          aliases: [{ alias: "central", object_id: 9 }],
        });
      if (path.endsWith("/applications")) return json({ items: [] });
      if (path.endsWith("/scope"))
        return json({
          variants: [{ id: 2, display_name: "Base" }],
          range_start: "2026-01-01T00:00:00",
          range_end: "2026-01-01T04:00:00",
        });
      if (path.endsWith("/tests/j1"))
        return json({
          id: "j1",
          status: "succeeded",
          publication_id: "pub",
          compilation_scope: {
            scenario_id: 4,
            variant_id: 2,
            range_start: "2026-01-01T00:00:00",
            range_end: "2026-01-01T04:00:00",
          },
          objects: [...objects, { id: 8, display_name: "Unidad Sur" }],
          result: {
            ir: {
              rows: [
                {
                  name: "conjunto",
                  period: 0,
                  line: 3,
                  relation: "<=",
                  unit: "mw",
                  constant: -10,
                  terms: [
                    { object_id: 7, variable: "potencia", coefficient: 1 },
                    { object_id: 8, variable: "potencia", coefficient: 1 },
                  ],
                },
              ],
            },
          },
        });
      return json({ detail: path }, 404);
    }),
  );
  render(<App />);
  expect(
    await screen.findByText(
      "1 × Unidad Norte.potencia + 1 × Unidad Sur.potencia <= 10 MW",
    ),
  ).toBeVisible();
});
