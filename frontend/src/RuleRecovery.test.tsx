import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { RuleRecovery } from "./RuleRecovery";
import { RunRuleSummary } from "./RuleApplications";

const scope = {
  scenario_id: 4,
  variant_id: 2,
  range_start: "2026-01-01T00:00:00",
  range_end: "2026-01-01T04:00:00",
};
const parameters = [
  {
    name: "limite",
    value: 5,
    type: "number",
    unit: "m3_per_s",
    min: 0,
    max: null,
  },
];
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

it("compares the applied revision, tests a replacement and requires a reason before confirming", async () => {
  let resolution: Record<string, unknown> | undefined;
  const applied = {
    id: "a1",
    revision: 1,
    status: "active",
    publication_id: "p1",
    variant_id: 2,
    parameters,
    aliases: [],
    inputs: [],
    temporal: null,
    windows: null,
    events: [],
    compilation: { scope },
    validation_status: "stale",
    validation_causes: [
      { code: "RULE_PUBLICATION_CHANGED", message: "Hay una revisión nueva" },
    ],
  };
  const before = {
    publication_id: "p1",
    code: "código anterior",
    sdk: "reg-006.1",
    parameters,
    inputs: [
      {
        alias: "afluente",
        object_id: 7,
        signal_id: 10,
        revision_id: 11,
        content_hash: "fuente-sellada",
        dimension_key: "flow",
        semantic_type_key: "natural_inflow",
        binding_role_key: "rule_inflow",
        unit_key: "m3_per_s",
        timezone: "UTC",
        current_revision_id: 12,
      },
    ],
    aliases: [{ alias: "otra", object_id: 8 }],
    objects: [],
    scope,
    grid: [],
    timezone: "UTC",
    temporal: null,
    windows: null,
  };
  const after = { ...before, publication_id: "p2", code: "código nuevo" };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/csrf")) return json({ csrf_token: "csrf" });
      if (path.endsWith("/history"))
        return json({
          status: "published",
          applications: [applied],
          publications: [
            {
              id: "p2",
              draft_revision: 2,
              code: "código nuevo",
              parameters,
              aliases: [],
              inputs: [],
            },
            {
              id: "p1",
              draft_revision: 1,
              code: "código anterior",
              parameters,
              aliases: [],
              inputs: [],
            },
          ],
        });
      if (path.endsWith("/object-candidates")) return json({ items: [] });
      if (path.endsWith("/comparisons"))
        return json({
          before,
          after,
          changed_fields: ["code"],
          action: "replace",
        });
      if (path.endsWith("/recovery-previews"))
        return json({ id: "j1", status: "queued" });
      if (path.endsWith("/tests/j1"))
        return json({
          id: "j1",
          status: "succeeded",
          result: {
            ir: {
              rows: [
                {
                  name: "maximo",
                  period: 0,
                  relation: "<=",
                  constant: -5,
                  unit: "m3_per_s",
                  terms: [
                    {
                      object_id: 8,
                      variable: "caudal",
                      period: 0,
                      coefficient: 2,
                    },
                  ],
                },
              ],
            },
          },
        });
      if (path.endsWith("/resolutions")) {
        resolution = JSON.parse(String(init?.body));
        return json(
          {
            ...applied,
            id: "a2",
            publication_id: "p2",
            validation_status: "valid",
          },
          201,
        );
      }
      return json({}, 404);
    }),
  );
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <RuleRecovery
        root="/api/projects/1/linkable-objects/7/rules"
        ruleId="r1"
        revision={1}
        scope={scope}
        disabled={false}
        available
        onResolved={vi.fn()}
      />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(
    screen.getByRole("button", { name: "Comparar y recuperar revisiones" }),
  );
  await user.selectOptions(
    await screen.findByLabelText("Revisión a utilizar"),
    "p2",
  );
  await user.click(
    screen.getByRole("button", {
      name: "Comparar con la aplicación histórica",
    }),
  );
  const table = await screen.findByRole("table", {
    name: "Comparación de revisiones",
  });
  expect(within(table).getByText("código anterior")).toBeVisible();
  expect(within(table).getByText("código nuevo")).toBeVisible();
  expect(within(table).getAllByText("otra → objeto 8")).toHaveLength(2);
  expect(
    within(table).getAllByText(/afluente · señal 10 · revisión 11 · m³\/s/),
  ).toHaveLength(2);
  await user.click(screen.getByRole("button", { name: "Probar recuperación" }));
  const confirm = await screen.findByRole("button", {
    name: "Confirmar recuperación",
  });
  await user.click(screen.getByText("Ver restricciones de la recuperación"));
  expect(screen.getByText(/2 × objeto 8.caudal\[1\]/)).toBeVisible();
  expect(confirm).toBeDisabled();
  await user.type(
    screen.getByLabelText("Motivo de recuperación"),
    "Nueva política comprobada",
  );
  await user.click(confirm);
  expect(
    await screen.findByText(
      "Recuperación aplicada. La aplicación anterior permanece en el historial.",
    ),
  ).toBeVisible();
  expect(resolution).toMatchObject({
    job_id: "j1",
    reason: "Nueva política comprobada",
  });
});

it("lets the analyst change local parameters before comparing the replacement", async () => {
  let compared: Record<string, unknown> | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/csrf")) return json({ csrf_token: "csrf" });
      if (path.endsWith("/object-candidates")) return json({ items: [] });
      if (path.endsWith("/history"))
        return json({
          status: "published",
          publications: [
            {
              id: "p1",
              draft_revision: 1,
              parameters,
              aliases: [],
              inputs: [],
              temporal: null,
              windows: null,
            },
          ],
          applications: [
            {
              id: "a1",
              revision: 1,
              status: "active",
              variant_id: 2,
              publication_id: "p1",
              parameters,
              aliases: [],
              inputs: [],
              temporal: null,
              windows: null,
              events: [],
              validation_status: "valid",
            },
          ],
        });
      if (path.endsWith("/comparisons")) {
        compared = JSON.parse(String(init?.body));
        return json({ detail: "Conflicto de revisión" }, 409);
      }
      return json({}, 404);
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RuleRecovery
        root="/api/projects/1/linkable-objects/7/rules"
        ruleId="r1"
        revision={1}
        scope={scope}
        disabled={false}
        available
        onResolved={vi.fn()}
      />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(
    screen.getByRole("button", { name: "Comparar y recuperar revisiones" }),
  );
  const value = await screen.findByLabelText("Valor propuesto limite");
  await user.clear(value);
  await user.type(value, "12");
  await user.click(
    screen.getByRole("button", {
      name: "Comparar con la aplicación histórica",
    }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Conflicto de revisión",
  );
  expect(compared).toMatchObject({
    mappings: { parameters: [{ name: "limite", value: 12, unit: "m3_per_s" }] },
  });
  expect(
    screen.queryByRole("button", { name: "Confirmar recuperación" }),
  ).not.toBeInTheDocument();
});

it("requires an explicit compatible destination for a new alias in the target revision", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/object-candidates"))
        return json({
          items: [
            {
              id: 7,
              display_name: "Norte",
              kind: "hydraulic_unit",
              variables: {},
            },
            {
              id: 8,
              display_name: "Sur",
              kind: "hydraulic_unit",
              variables: {},
            },
            {
              id: 9,
              display_name: "Embalse",
              kind: "hydraulic_reservoir",
              variables: {},
            },
          ],
        });
      if (path.endsWith("/history"))
        return json({
          status: "published",
          publications: [
            {
              id: "p2",
              draft_revision: 2,
              parameters,
              aliases: [{ alias: "otra", object_id: 8 }],
              inputs: [],
              temporal: null,
              windows: null,
              contract: {
                parameters: [{ ...parameters[0], owner: null }],
                aliases: [{ alias: "otra", kind: "hydraulic_unit" }],
                inputs: [],
                temporal: null,
                windows: null,
              },
            },
            {
              id: "p1",
              draft_revision: 1,
              parameters,
              aliases: [],
              inputs: [],
            },
          ],
          applications: [
            {
              id: "a1",
              revision: 1,
              status: "active",
              variant_id: 2,
              publication_id: "p1",
              parameters,
              aliases: [],
              inputs: [],
              temporal: null,
              windows: null,
              events: [],
              validation_status: "stale",
            },
          ],
        });
      return json({}, 404);
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RuleRecovery
        root="/api/projects/1/linkable-objects/7/rules"
        ruleId="r1"
        revision={1}
        scope={scope}
        disabled={false}
        available
        onResolved={vi.fn()}
      />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(
    screen.getByRole("button", { name: "Comparar y recuperar revisiones" }),
  );
  await user.selectOptions(
    await screen.findByLabelText("Revisión a utilizar"),
    "p2",
  );
  const alias = screen.getByLabelText("Destino propuesto otra");
  expect(alias).toHaveValue("0");
  expect(
    within(alias).queryByRole("option", { name: "Embalse" }),
  ).not.toBeInTheDocument();
  const compare = screen.getByRole("button", {
    name: "Comparar con la aplicación histórica",
  });
  expect(compare).toBeDisabled();
  await user.selectOptions(alias, "8");
  expect(compare).toBeEnabled();
});

it("archives a definition with an explicit reason and optimistic revision", async () => {
  let archived: unknown;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/csrf")) return json({ csrf_token: "csrf" });
      if (path.endsWith("/object-candidates")) return json({ items: [] });
      if (path.endsWith("/history"))
        return json({
          status: archived ? "archived" : "published",
          publications: [],
          applications: [],
          consumers: [
            {
              name: "Norte",
              project_id: 1,
              object_id: 7,
              rule_id: "instancia",
              scenario_id: 4,
              variant_id: 2,
              application_id: "a1",
            },
          ],
        });
      if (path.endsWith("/archive")) {
        archived = JSON.parse(String(init?.body));
        return json({ status: "archived", revision: 4 });
      }
      return json({}, 404);
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RuleRecovery
        root="/api/projects/1/linkable-objects/7/rules"
        ruleId="r1"
        revision={3}
        scope={scope}
        disabled={false}
        available
        onResolved={vi.fn()}
      />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(
    screen.getByRole("button", { name: "Comparar y recuperar revisiones" }),
  );
  const archive = await screen.findByRole("button", {
    name: "Archivar definición",
  });
  expect(archive).toBeDisabled();
  expect(
    screen.getByRole("link", { name: "Resolver Norte · variante 2" }),
  ).toHaveAttribute(
    "href",
    "/react/projects/1/linkable-objects/7/rules?rule=instancia&scenario_id=4&variant_id=2",
  );
  await user.type(
    screen.getByLabelText("Motivo de archivo"),
    "Retirada operativa",
  );
  await user.click(archive);
  expect(await screen.findByText(/Definición: Archivada/)).toBeVisible();
  expect(archived).toEqual({
    expected_revision: 3,
    reason: "Retirada operativa",
  });
});

it("shows the exact code and hashes consumed by a historical run without reading current definitions", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  render(
    <RunRuleSummary
      document={{
        component_rules: {
          applications: [
            {
              id: "a1",
              name: "Límite histórico",
              publication_id: "p1",
              code: "def construir(ctx): return 5",
              code_hash: "hash-codigo-original",
              context_hash: "hash-contexto-original",
              ir_hash: "hash-ir-original",
              runtime: { sdk: "reg-006.1", image: "sha256:original" },
              parameters,
              inputs: [],
              aliases: [],
              objects: [],
              events: [
                {
                  action: "retain",
                  actor: 3,
                  reason: "Decisión histórica",
                  at: "2026-01-01",
                },
              ],
            },
          ],
        },
      }}
    />,
  );
  await userEvent
    .setup()
    .click(screen.getByText("Ver revisión exacta consumida"));
  expect(screen.getByText("hash-codigo-original")).toBeVisible();
  expect(screen.getByText("hash-contexto-original")).toBeVisible();
  expect(screen.getByText("hash-ir-original")).toBeVisible();
  expect(screen.getByText("def construir(ctx): return 5")).toBeVisible();
  expect(screen.getByText(/Decisión histórica/)).toBeVisible();
  expect(fetch).not.toHaveBeenCalled();
});
