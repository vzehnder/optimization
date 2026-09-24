import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { App } from "./App";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RuleLibrary } from "./RuleLibrary";
import { RuleInputs } from "./RuleInputs";

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });

it("offers hydro templates only when the contextual object supports their variables", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      json({
        items: [
          {
            rule_id: "h",
            publication_id: "h1",
            revision: 1,
            name: "Volumen hidro",
            compatible_types: ["hydro"],
            required_capabilities: ["affine_hydraulic.v1"],
            parameters: [],
            aliases: [],
            inputs: [],
          },
          {
            rule_id: "u",
            publication_id: "u1",
            revision: 1,
            name: "Otra capacidad",
            compatible_types: ["battery"],
            required_capabilities: [],
            parameters: [],
            aliases: [],
            inputs: [],
          },
        ],
      }),
    ),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RuleLibrary
        root="/api/projects/1/linkable-objects/7/rules"
        scenarioId={4}
        objectKind="hydro"
        onCreated={vi.fn()}
      />
    </QueryClientProvider>,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Biblioteca del proyecto" }),
  );
  expect(
    await screen.findByRole("button", {
      name: "Usar Volumen hidro · revisión 1",
    }),
  ).toBeEnabled();
  expect(
    screen.getByRole("button", { name: "Usar Otra capacidad · revisión 1" }),
  ).toBeDisabled();
});

it("filters series candidates by the required template port and uses its alias", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      json({
        items: [
          {
            signal_id: 10,
            display_name: "Disponibilidad",
            set_name: "Programa",
            series_kind: "catalog",
            object_id: 7,
            unit_key: "dimensionless",
            dimension_key: "dimensionless",
            semantic_type_key: "availability_factor",
            binding_role_key: "rule_availability",
          },
          {
            signal_id: 11,
            display_name: "Afluente ajeno al puerto",
            set_name: "Afluente",
            series_kind: "catalog",
            object_id: 7,
            unit_key: "m3_per_s",
            dimension_key: "flow",
            semantic_type_key: "natural_inflow",
            binding_role_key: "rule_inflow",
          },
        ],
        next_cursor: null,
      }),
    ),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RuleInputs
        root="/api/projects/1/linkable-objects/7/rules"
        scenarioId={4}
        inputs={[]}
        onChange={vi.fn()}
        objects={[{ id: 7, label: "Actual" }]}
        requiredPorts={[
          {
            alias: "factor",
            object_id: 7,
            semantic_type_key: "availability_factor",
            dimension_key: "dimensionless",
            binding_role_key: "rule_availability",
          },
        ]}
      />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Seleccionar entrada" }));
  await user.click(screen.getByRole("button", { name: "Continuar selección" }));
  await user.click(await screen.findByLabelText(/Disponibilidad · Programa/));
  expect(
    screen.queryByLabelText(/Afluente ajeno al puerto/),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Alias de entrada")).toHaveValue("factor");
});

it("compares local values and shows the compiled rows of each instance", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/rule-library"))
        return json({
          items: [
            {
              rule_id: "source",
              publication_id: "p1",
              revision: 1,
              name: "Caudal reutilizable",
              compatible_types: ["hydraulic_unit"],
              required_capabilities: ["affine_flow.v1"],
              parameters: [],
              aliases: [],
              inputs: [],
            },
          ],
        });
      if (path.endsWith("/p1/instances"))
        return json({
          items: [
            {
              id: "a",
              name: "Norte",
              object_id: 7,
              variant_id: 2,
              activation: "active",
              validation_status: "valid",
              aliases: [],
              inputs: [],
              parameters: [{ name: "limite", value: 5, unit: "m3_per_s" }],
              preview: {
                row_count: 4,
                rows: [
                  {
                    name: "maximo",
                    period: 0,
                    relation: "<=",
                    constant: -5,
                    unit: "m3_per_s",
                    terms: [
                      { object_id: 7, variable: "caudal", coefficient: 1 },
                    ],
                  },
                ],
              },
            },
            {
              id: "b",
              name: "Sur",
              object_id: 8,
              variant_id: 2,
              activation: "inactive",
              validation_status: "pending",
              aliases: [],
              inputs: [],
              parameters: [{ name: "limite", value: 12, unit: "m3_per_s" }],
              preview: null,
            },
          ],
        });
      return json({}, 404);
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RuleLibrary
        root="/api/projects/1/linkable-objects/7/rules"
        scenarioId={4}
        onCreated={vi.fn()}
      />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(
    screen.getByRole("button", { name: "Biblioteca del proyecto" }),
  );
  await user.click(
    await screen.findByRole("button", {
      name: "Comparar instancias · Caudal reutilizable · revisión 1",
    }),
  );
  expect(await screen.findByText("limite: 5 m³/s")).toBeVisible();
  expect(screen.getByText("limite: 12 m³/s")).toBeVisible();
  await user.click(screen.getByText("Ver filas de Norte (4)"));
  expect(screen.getByText(/maximo · período 1:/)).toHaveTextContent(
    "<= 5 m³/s",
  );
  expect(screen.getByText("Sin prueba vigente")).toBeVisible();
});

it("requires compatible aliases and new initial conditions for a temporal template", async () => {
  let submitted: Record<string, unknown> | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/rule-library"))
        return json({
          items: [
            {
              rule_id: "source",
              publication_id: "ramp",
              revision: 2,
              name: "Rampa",
              compatible_types: ["hydraulic_unit"],
              required_capabilities: ["affine_temporal.v1"],
              parameters: [],
              inputs: [],
              aliases: [{ alias: "central", kind: "hydraulic_plant" }],
              temporal: {
                first_period: "initial",
                initial_values: [
                  { owner: "self", variable: "caudal", unit: "m3_per_s" },
                ],
              },
              windows: null,
            },
          ],
        });
      if (path.endsWith("/scope"))
        return json({ variants: [{ id: 2, display_name: "Base" }] });
      if (path.endsWith("/object-candidates"))
        return json({
          items: [
            {
              id: 9,
              key: "plant",
              kind: "hydraulic_plant",
              display_name: "Central",
            },
            {
              id: 10,
              key: "reservoir",
              kind: "hydraulic_node",
              display_name: "Embalse",
            },
          ],
        });
      if (path.endsWith("/csrf")) return json({ csrf_token: "test" });
      if (path.endsWith("/instances")) {
        submitted = JSON.parse(String(init?.body));
        return json({ id: "local" }, 201);
      }
      return json({}, 404);
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RuleLibrary
        root="/api/projects/1/linkable-objects/7/rules"
        scenarioId={4}
        onCreated={vi.fn()}
      />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(
    screen.getByRole("button", { name: "Biblioteca del proyecto" }),
  );
  await user.click(
    await screen.findByRole("button", { name: "Usar Rampa · revisión 2" }),
  );
  await screen.findByRole("option", { name: "Central · plant" });
  expect(
    screen.queryByRole("option", { name: "Embalse · reservoir" }),
  ).not.toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Referencia central"), "9");
  await user.type(
    screen.getByLabelText("Motivo de reutilización"),
    "Nueva central",
  );
  expect(
    screen.getByRole("button", { name: "Crear instancia" }),
  ).toBeDisabled();
  await user.type(screen.getByLabelText("Valor inicial self.caudal"), "3");
  await user.type(
    screen.getByLabelText("Instante inicial self.caudal"),
    "2025-12-31T23:00:00Z",
  );
  await user.click(screen.getByRole("button", { name: "Crear instancia" }));
  expect(submitted?.temporal).toEqual({
    first_period: "initial",
    initial_values: [
      {
        object_id: 7,
        variable: "caudal",
        unit: "m3_per_s",
        value: 3,
        timestamp: "2025-12-31T23:00:00Z",
      },
    ],
  });
});

it("creates a local instance from the project library with explicit typed values", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/projects/1/linkable-objects/7/rules?scenario_id=4&return_to=/scenarios/4/hydraulic-diagram",
  );
  let created: Record<string, unknown> | undefined;
  const code =
    'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= ctx.parametros.limite)';
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
      if (path.endsWith("/rule-library"))
        return json({
          items: [
            {
              rule_id: "source",
              publication_id: "p1",
              revision: 1,
              name: "Caudal reutilizable",
              compatible_types: ["hydraulic_unit"],
              required_capabilities: ["affine_flow.v1"],
              parameters: [
                {
                  name: "limite",
                  type: "number",
                  unit: "m3_per_s",
                  min: 0,
                  max: 40,
                  owner: null,
                },
              ],
              aliases: [],
              inputs: [],
            },
          ],
        });
      if (path.endsWith("/object-candidates"))
        return json({
          items: [
            {
              id: 7,
              key: "unit",
              kind: "hydraulic_unit",
              display_name: "Unidad Norte",
              variables: { caudal: "m3_per_s" },
            },
          ],
        });
      if (path.endsWith("/scope"))
        return json({
          variants: [{ id: 2, display_name: "Base" }],
          range_start: "2026-01-01T00:00:00",
          range_end: "2026-01-01T04:00:00",
        });
      if (path.endsWith("/instances") && init?.method === "POST") {
        created = JSON.parse(String(init.body));
        return json(
          {
            ...created,
            id: "local",
            code,
            revision: 1,
            template: { rule_id: "source", publication_id: "p1" },
          },
          201,
        );
      }
      if (path.endsWith("/rules/local"))
        return json({
          ...created,
          id: "local",
          code,
          revision: 1,
          template: { rule_id: "source", publication_id: "p1" },
        });
      if (path.endsWith("/rules"))
        return json({
          object: { id: 7, display_name: "Unidad Norte" },
          items: created
            ? [{ id: "local", name: "Límite Norte", revision: 1 }]
            : [],
          runtime: null,
        });
      if (
        path.endsWith("/applications") ||
        path.endsWith("/series-publications")
      )
        return json({ items: [] });
      return json({ detail: path }, 404);
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await user.click(
    await screen.findByRole("button", { name: "Biblioteca del proyecto" }),
  );
  await user.click(
    await screen.findByRole("button", {
      name: "Usar Caudal reutilizable · revisión 1",
    }),
  );
  expect(
    screen.getByRole("button", { name: "Crear instancia" }),
  ).toBeDisabled();
  await user.clear(screen.getByLabelText("Nombre de la instancia"));
  await user.type(
    screen.getByLabelText("Nombre de la instancia"),
    "Límite Norte",
  );
  await user.type(screen.getByLabelText("Valor local limite"), "12");
  await user.type(
    screen.getByLabelText("Motivo de reutilización"),
    "Capacidad de esta unidad",
  );
  await user.click(screen.getByRole("button", { name: "Crear instancia" }));
  await screen.findByText(/Revisión compartida fijada: p1/);
  expect(created?.parameters).toEqual([
    {
      name: "limite",
      type: "number",
      unit: "m3_per_s",
      min: 0,
      max: 40,
      object_id: null,
      value: 12,
    },
  ]);
  expect(created?.variant_id).toBe(2);
  expect(created?.aliases).toEqual([]);
  expect(
    screen.getByRole("link", { name: "Volver a la unidad" }),
  ).toHaveAttribute("href", "/react/scenarios/4/hydraulic-diagram");
  expect(
    screen.queryByRole("textbox", { name: "Código Python" }),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Tipo limite")).toBeDisabled();
  expect(screen.getByLabelText("Unidad limite")).toBeDisabled();
});
