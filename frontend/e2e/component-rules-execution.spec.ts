import { expect, test } from "@playwright/test";

test("REG-002 applies a real Python maximum, solves in Julia and restores base flow after deactivation", async ({
  page,
}) => {
  test.skip(
    !process.env.RULE_ACCEPTANCE_SERVER,
    "requires the isolated real OCI/Julia acceptance server",
  );
  test.setTimeout(240_000);
  page.setDefaultTimeout(15_000);
  const api = page.request;
  const csrf = async () => ({
    "X-CSRF-Token": (await (await api.get("/api/auth/csrf")).json()).csrf_token,
  });
  const bootstrap = await api.post("/api/auth/bootstrap", {
    headers: await csrf(),
    data: {
      email: "admin@example.local",
      display_name: "Analista",
      password: "admin-pass",
      next: "/react/projects",
    },
  });
  expect(bootstrap.ok()).toBeTruthy();
  const fixture = await (await api.get("/api/auth/reg002-fixture")).json();
  await page.goto(`/react/scenarios/${fixture.scenario_id}/hydraulic-diagram`);
  await page
    .getByRole("group", { name: "Central plant_laja", exact: true })
    .click();
  await page
    .getByRole("link", { name: "Cálculos y restricciones · unit_1" })
    .click();
  await page.getByLabel("Nombre de la regla").fill("Máximo operativo 5");
  await page
    .getByRole("textbox", { name: "Código Python" })
    .fill(
      'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= ctx.parametros.capacidad * ctx.parametros.disponibilidad)\n',
    );
  await page.getByLabel("Valor capacidad", { exact: true }).fill("5");
  await page.getByLabel("Valor disponibilidad", { exact: true }).fill("1");
  await page.getByRole("button", { name: "Guardar borrador" }).click();
  await page.getByRole("button", { name: "Publicar revisión" }).click();
  await page.getByRole("button", { name: "Probar restricciones" }).click();
  await expect(page.getByText(/4 restricciones · unidad/)).toBeVisible({
    timeout: 30_000,
  });
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Máximo operativo de la unidad");
  await page.getByRole("button", { name: "Aplicar a variante" }).click();
  await expect(page.getByText(/aplicada a esta variante/)).toBeVisible();
  const rulesUrl = page.url();
  await page.screenshot({
    path: "test-results/reg002-applied.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Ejecutar variante con reglas" })
    .click();
  await expect(page).toHaveURL(/\/runs\/\d+$/, { timeout: 60_000 });
  const runId = Number(page.url().split("/").at(-1));
  await expect
    .poll(
      async () =>
        (await (await api.get(`/api/runs/${runId}`)).json()).run.status,
      { timeout: 90_000 },
    )
    .toBe("succeeded");
  const limited = (await (await api.get(`/api/runs/${runId}/results`)).json())
    .results;
  expect(limited.dispatch_table.rows).toHaveLength(4);
  for (const row of limited.dispatch_table.rows)
    expect(Number(row.total_hydro_turbine_flow_m3s)).toBeCloseTo(5);
  await expect(
    page.getByText("Máximo operativo 5", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("capacidad: 5 m³/s")).toBeVisible();
  await page.screenshot({
    path: "test-results/reg002-results.png",
    fullPage: true,
  });
  await page.goto(rulesUrl);
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Recuperar comportamiento base");
  await page.getByRole("button", { name: "Desactivar aplicación" }).click();
  await expect(
    page.getByText(/aplicaciones desactivadas se conservan/),
  ).toBeVisible();
  const baseResponse = await api.post(
    `/api/scenario-versions/${fixture.base_version_id}/runs`,
    { headers: await csrf(), data: {} },
  );
  expect(baseResponse.ok()).toBeTruthy();
  const base = await baseResponse.json();
  await expect
    .poll(
      async () =>
        (await (await api.get(`/api/runs/${base.id}`)).json()).run.status,
      { timeout: 90_000 },
    )
    .toBe("succeeded");
  const restored = (
    await (await api.get(`/api/runs/${base.id}/results`)).json()
  ).results;
  for (const row of restored.dispatch_table.rows)
    expect(Number(row.total_hydro_turbine_flow_m3s)).toBeCloseTo(40);
  const historical = (
    await (await api.get(`/api/runs/${runId}/results`)).json()
  ).results;
  for (const row of historical.dispatch_table.rows)
    expect(Number(row.total_hydro_turbine_flow_m3s)).toBeCloseTo(5);
});
