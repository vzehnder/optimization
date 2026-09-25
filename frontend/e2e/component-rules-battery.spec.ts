import { expect, test } from "@playwright/test";

test("REG-012 reserves battery energy from its editor and reports frozen compliance", async ({
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
    await api.get("/api/auth/reg012-fixture")
  ).json();
  await page.goto(`/react/scenarios/${scenario}/draft`);
  await page.getByRole("button", { name: "Editar Batería · battery" }).click();
  await page
    .getByRole("link", { name: "Cálculos y restricciones · battery" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Cálculos y restricciones" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Carga y descarga son potencias positivas/),
  ).toBeVisible();
  const context = await (
    await api.get(`/api/scenarios/${scenario}/components/battery/rule-context`)
  ).json();
  const root = `/api/projects/${context.project_id}/linkable-objects/${context.object_id}/rules`;
  const saved = await post(root, {
    name: "Reserva horaria de batería",
    expected_revision: 0,
    scenario_id: scenario,
    code: 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("reserva", t, ctx.objeto.energia[t] >= ctx.entradas.reserva[t])\n        ctx.restriccion("potencia", t, ctx.objeto.carga[t] + ctx.objeto.descarga[t] <= ctx.parametros.limite)\n',
    parameters: [{ name: "limite", type: "number", unit: "mw", value: 3 }],
    aliases: [],
    inputs: [
      {
        alias: "reserva",
        object_id: context.object_id,
        dimension_key: "energy",
        semantic_type_key: "battery_energy_reserve",
        binding_role_key: "rule_energy_reserve",
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
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Conservar reserva horaria");
  await page.getByRole("button", { name: "Aplicar a variante" }).click();
  await expect(page.getByText(/aplicada a esta variante/)).toBeVisible();
  await page.screenshot({
    path: "test-results/reg012-applied.png",
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
  const rows = result.dispatch_table.rows;
  for (const [i, energy] of [4.4, 4, 1, 2].entries())
    expect(Number(rows[i].battery_energy_mwh)).toBeCloseTo(energy);
  expect(Number(rows[1].battery_discharge_mw)).toBeCloseTo(0.36);
  expect(Number(rows[2].battery_discharge_mw)).toBeCloseTo(2.7);
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
    .screenshot({ path: "test-results/reg012-compliance.png" });
});
