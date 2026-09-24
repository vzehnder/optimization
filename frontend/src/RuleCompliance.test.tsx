import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { RuleCompliance } from "./RuleCompliance";

const row = {
  row_index: 0,
  name: "máximo",
  rule_id: "r1",
  revision_id: "pub1",
  application_id: "a1",
  definition_id: "definition1",
  instance_revision: 2,
  rule_name: "Límite histórico",
  rule_url: "/react/projects/1/linkable-objects/7/rules?rule=r1",
  components: [{ id: 7, display_name: "Unidad histórica" }],
  period: 0,
  affected_periods: [0],
  timestamp: "2026-01-01T00:00:00",
  line: 3,
  unit: "m3_per_s",
  relation: "<=",
  lhs: 5,
  rhs: 5,
  margin: 0,
  residual: null,
  absolute_tolerance: 1e-7,
  relative_tolerance: 1e-7,
  tolerance: 6e-7,
  status: "satisfied",
  window: null,
};
const report = {
  version: "rule_compliance.v1",
  run_id: 99,
  solution_state: "optimal",
  termination_status: "OPTIMAL",
  counts: {
    total: 30,
    evaluated: 30,
    satisfied: 29,
    violated: 1,
    unavailable: 0,
  },
  rows: [row],
  rules: [
    {
      rule_id: "r1",
      name: "Límite histórico",
      application_id: "a1",
      revision_id: "pub1",
      url: row.rule_url,
    },
  ],
  page: { offset: 0, limit: 25, total: 30, next_offset: 25 },
  period_count: 4,
  samples: [row],
  diagnostics: [],
};
function show(handler: (url: URL) => unknown, status = "succeeded") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      const result = handler(new URL(path, "http://localhost"));
      return result instanceof Response ? result : Response.json(result);
    }),
  );
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <RuleCompliance runId={99} status={status} />
    </QueryClientProvider>,
  );
}

it("removes previously displayed technical data if access is denied on reconstruction", async () => {
  let reads = 0;
  show(() =>
    ++reads === 1
      ? report
      : Response.json({ detail: "Acceso denegado" }, { status: 403 }),
  );
  await screen.findByRole("table", { name: "Detalle de cumplimiento" });
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "Reconstruir informe" }));
  await screen.findByRole("alert");
  expect(
    screen.queryByRole("table", { name: "Detalle de cumplimiento" }),
  ).not.toBeInTheDocument();
});

it("shows frozen compliance, full counts, sample labels and server-side filters and pages", async () => {
  const requests: URL[] = [];
  show((url) => {
    requests.push(url);
    return url.searchParams.get("offset") === "25"
      ? {
          ...report,
          rows: [{ ...row, name: "última fila" }],
          page: { ...report.page, offset: 25, next_offset: null },
        }
      : report;
  });
  const user = userEvent.setup();
  expect(await screen.findByText("Solución óptima")).toBeVisible();
  expect(screen.getByText(/30 evaluadas.*1 incumplida/)).toBeVisible();
  expect(screen.getByText(/Muestra de 1 de 30 filas/)).toBeVisible();
  const table = screen.getByRole("table", { name: "Detalle de cumplimiento" });
  expect(within(table).getByText("Unidad histórica")).toBeVisible();
  expect(
    within(table).getByRole("link", { name: "Límite histórico" }),
  ).toHaveAttribute("href", row.rule_url);
  await user.click(screen.getByRole("button", { name: "Página siguiente" }));
  expect(await screen.findByText("última fila")).toBeVisible();
  await user.selectOptions(screen.getByLabelText("Filtrar regla"), "r1");
  await user.selectOptions(screen.getByLabelText("Filtrar período"), "1");
  expect(requests.at(-1)?.searchParams.get("offset")).toBe("0");
  expect(requests.at(-1)?.searchParams.get("rule_id")).toBe("r1");
  expect(requests.at(-1)?.searchParams.get("period")).toBe("1");
});

it("explains absence of primal values and links evidence without claiming a unique cause", async () => {
  let requests = 0;
  show(() => {
    requests++;
    return {
      ...report,
      solution_state: "no_primal",
      termination_status: "INFEASIBLE",
      counts: {
        total: 1,
        evaluated: 0,
        satisfied: 0,
        violated: 0,
        unavailable: 1,
      },
      rows: [
        {
          ...row,
          lhs: null,
          margin: null,
          tolerance: null,
          status: "unavailable",
        },
      ],
      samples: [],
      diagnostics: [
        {
          category: "infeasible",
          message: "Sin causa única ni IIS disponible.",
          action: "Revisar balances y reglas.",
        },
        {
          category: "bounds_conflict",
          message: "Mínimo mayor que máximo",
          action: "Corregir las cotas.",
          conflicts: [
            {
              name: "mínimo",
              period: 0,
              application_id: "a1",
              rule_url: row.rule_url,
            },
          ],
        },
      ],
    };
  }, "failed");
  expect(
    await screen.findByText("Sin solución primal disponible"),
  ).toBeVisible();
  expect(screen.getByText("Sin causa única ni IIS disponible.")).toBeVisible();
  expect(
    screen.getByRole("link", { name: "mínimo · período 1" }),
  ).toHaveAttribute("href", row.rule_url);
  expect(screen.getByText("Sin evaluar")).toBeVisible();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "Reconstruir informe" }));
  expect(requests).toBe(2);
});
