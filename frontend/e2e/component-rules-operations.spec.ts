import { expect, test } from "@playwright/test";

test("REG-014 runs one pinned hydro rule manually, from its console and from a schedule", async ({
  page,
}) => {
  test.skip(!process.env.RULE_ACCEPTANCE_SERVER, "requires OCI and Julia");
  test.setTimeout(480_000);
  const api = page.request;
  const write = async (path: string, data: unknown, method = "POST") => {
    const csrf = (await (await api.get("/api/auth/csrf")).json()).csrf_token;
    const response = await api.fetch(path, {
      method,
      data,
      headers: { "X-CSRF-Token": csrf },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };
  await write("/api/auth/bootstrap", {
    email: "admin@example.local",
    display_name: "Analista",
    password: "admin-pass",
  });
  const { scenario_id: scenario } = await (
    await api.get("/api/auth/reg011-fixture")
  ).json();
  const context = await (
    await api.get(`/api/scenarios/${scenario}/components/hydro_1/rule-context`)
  ).json();
  const variant = (
    await (
      await api.get(`/api/scenarios/${scenario}/case/default-variant`)
    ).json()
  ).variant;
  const document = {
    schema_version: "operator_console_config.v1",
    public_identity: {
      name: "REG-014 Hidro operativo",
      description: "Regla fijada por ingeniería",
    },
    parameters: [
      {
        id: "caudal",
        pointer: { asset_id: "hydro_1", field: "turbine_flow_max_m3s" },
        label: "Caudal máximo",
        unit: "m3/s",
        min: 1,
        max: 10,
        default: 10,
      },
    ],
    groups: [],
    results: { kpis: [], charts: [], tables: [] },
  };
  const console = (
    await write(`/api/scenarios/${scenario}/consoles`, {
      source_variant_id: variant.id,
      document,
    })
  ).operator_console;
  const root = `/api/projects/${context.project_id}/linkable-objects/${context.object_id}/rules`;
  const saved = await write(root, {
    expected_revision: 0,
    scenario_id: scenario,
    name: "Caudal fijado REG-014",
    code: 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("caudal", t, ctx.objeto.caudal[t] <= ctx.parametros.limite)',
    parameters: [
      { name: "limite", type: "number", unit: "m3_per_s", value: 5 },
    ],
    aliases: [],
    inputs: [],
  });
  const path = `${root}/${saved.id}`;
  const publication = await write(`${path}/publications`, {
    expected_revision: 1,
  });
  const range = {
    range_start: "2026-01-01T00:00:00",
    range_end: "2026-01-01T02:00:00",
  };
  for (const id of [variant.id, console.owned_variant.id]) {
    const job = await write(`${path}/tests`, {
      expected_revision: 1,
      publication_id: publication.id,
      scope: { scenario_id: scenario, variant_id: id, ...range },
    });
    await expect
      .poll(
        async () =>
          (await (await api.get(`${path}/tests/${job.id}`)).json()).status,
        { timeout: 30_000 },
      )
      .toBe("succeeded");
    await write(`${path}/applications`, {
      job_id: job.id,
      reason: "Preparar ejecución operativa",
    });
  }
  const manual = await write(
    `/api/scenarios/${scenario}/case/variants/${variant.id}/run`,
    range,
  );
  await write(
    `/api/scenarios/${scenario}/consoles/${console.id}`,
    { expected_revision: console.revision, status: "active", document },
    "PUT",
  );
  await page.goto(`/react/scenarios/${scenario}/consoles/${console.id}`);
  await expect(
    page.getByRole("heading", { name: "Reglas preparadas" }),
  ).toBeVisible();
  await expect(page.getByText(publication.id)).toBeVisible();
  await page.getByRole("link", { name: "Probar consola" }).click();
  await page.getByLabel("Inicio", { exact: true }).fill("2026-01-01T00:00");
  await page.getByLabel("Fin", { exact: true }).fill("2026-01-01T02:00");
  await page.getByLabel("Caudal máximo (m3/s)").fill("4");
  await page
    .getByRole("button", { name: "Guardar parametros", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Ejecutar", exact: true }),
  ).toBeEnabled();
  const request = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/console/${console.id}/runs`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Ejecutar", exact: true }).click();
  const response = await request;
  expect(response.ok(), await response.text()).toBeTruthy();
  const operational = (await response.json()).run;
  await page.screenshot({
    path: "test-results/reg014-console.png",
    fullPage: true,
  });
  const schedule = (
    await write("/api/admin/schedules", {
      scenario_id: scenario,
      case_input_variant_id: variant.id,
      display_name: "REG-014 Programación hidro",
      range_start: range.range_start + "+00:00",
      range_end: range.range_end + "+00:00",
      cadence: "daily",
      next_run_at: "2026-01-01T00:00:00+00:00",
    })
  ).schedule;
  const due = await write("/api/admin/schedules/run-due", {
    now: "2026-01-01T00:00:00+00:00",
  });
  const tick = due.ticks.find(
    (item: { schedule_id: number }) => item.schedule_id === schedule.id,
  );
  expect(tick.status).toBe("queued");
  expect(
    (
      await write("/api/admin/schedules/run-due", {
        now: "2026-01-01T00:00:00+00:00",
      })
    ).due_count,
  ).toBe(0);
  for (const [id, expectedFlow, origin] of [
    [manual.id, 5, "manual"],
    [operational.id, 4, "operator_console"],
    [tick.run_id, 5, "scheduled"],
  ] as const) {
    await expect
      .poll(
        async () =>
          (await (await api.get(`/api/runs/${id}`)).json()).run.status,
        { timeout: 120_000 },
      )
      .toBe("succeeded");
    const run = (await (await api.get(`/api/runs/${id}`)).json()).run;
    expect(run.trigger_type).toBe(origin);
    const version = (
      await (
        await api.get(`/api/scenario-versions/${run.scenario_version_id}`)
      ).json()
    ).scenario_version;
    expect(
      version.system_case_json.component_rules.applications[0].publication_id,
    ).toBe(publication.id);
    const result = (await (await api.get(`/api/runs/${id}/results`)).json())
      .results;
    expect(
      result.dispatch_table.rows.map((row: Record<string, number>) =>
        Number(row.total_hydro_turbine_flow_m3s),
      ),
    ).toEqual([expectedFlow, expectedFlow]);
    const compliance = await (
      await api.get(`/api/runs/${id}/rule-compliance`)
    ).json();
    expect(compliance.counts.satisfied).toBe(2);
  }
  await page.goto("/react/admin/users?section=schedules");
  await expect(
    page.getByText("REG-014 Programación hidro", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(publication.id)).toBeVisible();
  await page.screenshot({
    path: "test-results/reg014-schedule.png",
    fullPage: true,
  });
});
