import { expect, test } from "@playwright/test";

test("REG-011 applies hourly hydro rules from the editor and preserves physical balances", async ({
  page,
}) => {
  test.skip(!process.env.RULE_ACCEPTANCE_SERVER, "requires real OCI and Julia");
  test.setTimeout(360_000);
  page.setDefaultTimeout(15_000);
  const api = page.request;
  const post = async (path: string, data: unknown) => {
    const csrf = (await (await api.get("/api/auth/csrf")).json()).csrf_token;
    const response = await api.post(path, {
      data,
      headers: { "X-CSRF-Token": csrf },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };
  await post("/api/auth/bootstrap", {
    email: "admin@example.local",
    display_name: "Analista",
    password: "admin-pass",
  });
  const { scenario_id: scenario, source } = await (
    await api.get("/api/auth/reg011-fixture")
  ).json();
  await page.goto(`/react/scenarios/${scenario}/draft`);
  await page.getByRole("button", { name: "Editar Hidro · hydro_1" }).click();
  await page
    .getByRole("link", { name: "Cálculos y restricciones · hydro_1" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Cálculos y restricciones" }),
  ).toBeVisible();
  const context = await (
    await api.get(`/api/scenarios/${scenario}/components/hydro_1/rule-context`)
  ).json();
  const root = `/api/projects/${context.project_id}/linkable-objects/${context.object_id}/rules`;
  const saved = await post(root, {
    name: "Hidro con caudal horario",
    expected_revision: 0,
    scenario_id: scenario,
    code: 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("caudal", t, ctx.objeto.caudal[t] <= ctx.entradas.limite[t])\n        ctx.restriccion("potencia", t, ctx.objeto.potencia[t] >= ctx.parametros.potencia)\n        ctx.restriccion("volumen", t, ctx.objeto.almacenamiento[t] >= ctx.parametros.volumen)\n        ctx.restriccion("vertimiento", t, ctx.objeto.vertimiento[t] <= ctx.entradas.limite[t])\n',
    parameters: [
      { name: "potencia", type: "number", unit: "mw", value: 0.1 },
      { name: "volumen", type: "number", unit: "hm3", value: 2.5 },
    ],
    aliases: [],
    inputs: [
      {
        alias: "limite",
        object_id: context.object_id,
        dimension_key: "flow",
        semantic_type_key: "hydro_inflow",
        binding_role_key: "rule_inflow",
        signal_id: source.signal_ids.input,
        revision_id: source.revision_id,
        content_hash: source.content_hash,
      },
    ],
  });
  await page.reload();
  await page.getByRole("button", { name: "Publicar revisión" }).click();
  await page.getByRole("button", { name: "Probar restricciones" }).click();
  await expect(page.getByText(/8 restricciones/)).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByText("ctx.objeto.almacenamiento", { exact: false }).first(),
  ).toBeVisible();
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Aplicar límite horario al hidro");
  await page.getByRole("button", { name: "Aplicar a variante" }).click();
  await expect(page.getByText(/aplicada a esta variante/)).toBeVisible();
  await page.screenshot({
    path: "test-results/reg011-applied.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Ejecutar variante con reglas" })
    .click();
  await expect(page).toHaveURL(/\/runs\/\d+$/, { timeout: 90_000 });
  const runId = page.url().split("/").at(-1);
  await expect
    .poll(
      async () =>
        (await (await api.get(`/api/runs/${runId}`)).json()).run.status,
      { timeout: 120_000 },
    )
    .toBe("succeeded");
  const result = (await (await api.get(`/api/runs/${runId}/results`)).json())
    .results;
  expect(
    result.dispatch_table.rows.map((r: Record<string, number>) =>
      Number(r.total_hydro_turbine_flow_m3s),
    ),
  ).toEqual([4, 6]);
  const rows = result.dispatch_table.rows;
  expect(Number(rows[0].total_hydro_power_mw)).toBeCloseTo(0.4);
  expect(Number(rows[1].total_hydro_power_mw)).toBeCloseTo(0.6);
  expect(Number(rows[1].total_hydro_storage_hm3)).toBeCloseTo(2.68);
  const compliance = await (
    await api.get(`/api/runs/${runId}/rule-compliance`)
  ).json();
  expect(compliance.counts).toEqual({
    total: 8,
    evaluated: 8,
    satisfied: 8,
    violated: 0,
    unavailable: 0,
  });
  expect(compliance.rules[0].rule_id).toBe(saved.id);
  await expect(page.getByText(/8 evaluadas/)).toBeVisible();
  await page
    .getByRole("region", { name: "Cumplimiento de reglas" })
    .screenshot({
      path: "test-results/reg011-compliance.png",
    });
});
