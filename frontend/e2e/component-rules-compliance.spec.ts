import { expect, test } from "@playwright/test";

test("REG-010 reconstructs compliance and explains failures using frozen evidence", async ({
  page,
}) => {
  test.skip(!process.env.RULE_ACCEPTANCE_SERVER, "requires real OCI and Julia");
  test.setTimeout(420_000);
  const api = page.request;
  const csrf = async () => ({
    "X-CSRF-Token": (await (await api.get("/api/auth/csrf")).json()).csrf_token,
  });
  const post = async (path: string, data: unknown) => {
    const response = await api.post(path, { headers: await csrf(), data });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };
  await post("/api/auth/bootstrap", {
    email: "admin@example.local",
    display_name: "Analista",
    password: "admin-pass",
    next: "/react/projects",
  });
  const { scenario_id: scenario } = await (
    await api.get("/api/auth/reg004-fixture")
  ).json();
  const context = await (
    await api.get(
      `/api/scenarios/${scenario}/hydraulic-plants/plant_laja/units/unit_1/rule-context`,
    )
  ).json();
  const root = `/api/projects/${context.project_id}/linkable-objects/${context.object_id}/rules`;
  const selected = await (
    await api.get(`${root}/scope?scenario_id=${scenario}`)
  ).json();
  const scope = {
    scenario_id: scenario,
    variant_id: selected.variants[0].id,
    range_start: selected.range_start,
    range_end: selected.range_end,
  };
  const parameters = [
    { name: "limite", type: "number", unit: "m3_per_s", value: 5 },
  ];
  const definition = {
    name: "Límites auditables",
    code: 'def construir(ctx):\n    for t in ctx.periodos:\n        for n in range(8):\n            ctx.restriccion(f"vinculante_{n}", t, ctx.objeto.caudal[t] <= ctx.parametros.limite)\n        ctx.restriccion("holgura", t, ctx.objeto.caudal[t] <= ctx.parametros.limite * 2)\n        ctx.restriccion("igualdad", t, ctx.objeto.caudal[t] == ctx.parametros.limite)\n',
    parameters,
    scenario_id: scenario,
    inputs: [],
    aliases: [],
    expected_revision: 0,
  };
  const apply = async (body: object) => {
    const rule = await post(root, body);
    const path = `${root}/${rule.id}`;
    const publication = await post(`${path}/publications`, {
      expected_revision: 1,
    });
    const job = await post(`${path}/tests`, {
      expected_revision: 1,
      publication_id: publication.id,
      scope,
    });
    await expect
      .poll(
        async () =>
          (await (await api.get(`${path}/tests/${job.id}`)).json()).status,
        { timeout: 40_000 },
      )
      .toBe("succeeded");
    await post(`${path}/applications`, {
      job_id: job.id,
      reason: "Verificar cumplimiento",
    });
    return { rule, path };
  };
  const original = await apply(definition);
  const runPath = `/api/scenarios/${scenario}/case/variants/${scope.variant_id}/run`;
  const range = { range_start: scope.range_start, range_end: scope.range_end };
  const run = await post(runPath, range);
  await expect
    .poll(
      async () =>
        (await (await api.get(`/api/runs/${run.id}`)).json()).run.status,
      { timeout: 100_000 },
    )
    .toBe("succeeded");
  const reportUrl = `/api/runs/${run.id}/rule-compliance?limit=100`;
  const before = await (await api.get(reportUrl)).json();
  expect(before.solution_state).toBe("optimal");
  expect(before.counts).toEqual({
    total: 40,
    evaluated: 40,
    satisfied: 40,
    violated: 0,
    unavailable: 0,
  });
  expect(
    before.rows.find((r: { name: string }) => r.name === "holgura").margin,
  ).toBeCloseTo(5);
  expect(
    before.rows.find((r: { name: string }) => r.name === "igualdad").residual,
  ).toBeCloseTo(0);
  await page.goto(`/react/runs/${run.id}`);
  await expect(
    page.getByText("Solución óptima", { exact: true }),
  ).toBeVisible();
  const panel = page.getByRole("region", { name: "Cumplimiento de reglas" });
  await expect(panel.getByText(/40 evaluadas/)).toBeVisible();
  await expect(panel.getByRole("table").getByRole("row")).toHaveCount(26);
  await panel.getByRole("button", { name: "Página siguiente" }).click();
  await expect(panel.getByRole("table").getByRole("row")).toHaveCount(16);
  await panel.getByLabel("Filtrar período").selectOption("1");
  await expect(panel.getByRole("table").getByRole("row")).toHaveCount(11);
  await page.screenshot({
    path: "test-results/reg010-compliance.png",
    fullPage: true,
  });
  const changed = await api.put(original.path, {
    headers: await csrf(),
    data: {
      ...definition,
      name: "Definición actual editada",
      code: "def construir(ctx):\n    return 0",
      expected_revision: 1,
    },
  });
  expect(changed.ok(), await changed.text()).toBeTruthy();
  await panel.getByRole("button", { name: "Reconstruir informe" }).click();
  expect(await (await api.get(reportUrl)).json()).toEqual(before);
  const candidates = (
    await (
      await api.get(`${root}/object-candidates?scenario_id=${scenario}`)
    ).json()
  ).items;
  const reservoir = candidates.find(
    (o: { kind: string }) => o.kind === "hydraulic_node",
  );
  await apply({
    ...definition,
    name: "Conservar toda el agua",
    code: 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("reserva", t, ctx.objetos.agua.almacenamiento[t] == ctx.parametros.reserva)\n',
    parameters: [{ name: "reserva", type: "number", unit: "hm3", value: 20 }],
    aliases: [{ alias: "agua", object_id: reservoir.id }],
  });
  const failed = await post(runPath, range);
  await expect
    .poll(
      async () =>
        (await (await api.get(`/api/runs/${failed.id}`)).json()).run.status,
      { timeout: 100_000 },
    )
    .toBe("failed");
  const noPrimal = await (
    await api.get(`/api/runs/${failed.id}/rule-compliance`)
  ).json();
  expect(noPrimal.solution_state).toBe("no_primal");
  expect(noPrimal.termination_status).toBe("INFEASIBLE");
  expect(noPrimal.counts.evaluated).toBe(0);
  await page.goto(`/react/runs/${failed.id}`);
  await expect(
    page.getByText("Sin solución primal disponible", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/No se identificó una causa única/),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/reg010-no-primal.png",
    fullPage: true,
  });
  const conflict = await apply({
    ...definition,
    name: "Mínimo incompatible",
    code: 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("minimo", t, ctx.objeto.caudal[t] >= ctx.parametros.limite)\n',
    parameters: [{ ...parameters[0], value: 6 }],
  });
  await page.goto(
    `/react/projects/${context.project_id}/linkable-objects/${context.object_id}/rules?scenario_id=${scenario}&rule=${conflict.rule.id}`,
  );
  await page
    .getByRole("button", { name: "Ejecutar variante con reglas" })
    .click();
  await expect(
    page.getByRole("link", { name: /minimo · período 1/ }),
  ).toBeVisible();
});
