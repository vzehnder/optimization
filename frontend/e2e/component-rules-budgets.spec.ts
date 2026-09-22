import { expect, test } from "@playwright/test";

test("REG-006 compares horizon energy and partial daily water budgets against an unrestricted solve", async ({
  page,
}) => {
  test.skip(!process.env.RULE_ACCEPTANCE_SERVER, "requires real OCI and Julia");
  test.setTimeout(480_000);
  page.setDefaultTimeout(20_000);
  const api = page.request;
  const csrf = async () => ({
    "X-CSRF-Token": (await (await api.get("/api/auth/csrf")).json()).csrf_token,
  });
  expect(
    (
      await api.post("/api/auth/bootstrap", {
        headers: await csrf(),
        data: {
          email: "admin@example.local",
          display_name: "Analista",
          password: "admin-pass",
          next: "/react/projects",
        },
      })
    ).ok(),
  ).toBeTruthy();
  const fixture = await (await api.get("/api/auth/reg006-fixture")).json();
  const results = async (id: number) => {
    await expect
      .poll(
        async () =>
          (await (await api.get(`/api/runs/${id}`)).json()).run.status,
        { timeout: 120_000 },
      )
      .toBe("succeeded");
    return (await (await api.get(`/api/runs/${id}/results`)).json()).results
      .dispatch_table.rows as {
      duration_hours: number;
      total_hydro_power_mw: number;
      total_hydro_turbine_flow_m3s: number;
    }[];
  };
  await page.goto(`/react/scenarios/${fixture.scenario_id}/hydraulic-diagram`);
  await page
    .getByRole("group", { name: "Central plant_laja", exact: true })
    .click();
  await page
    .getByRole("link", { name: "Cálculos y restricciones · unit_1" })
    .click();
  await page.getByLabel("Nombre de la regla").fill("Presupuesto de energía");
  await page.getByLabel("Parámetro 1", { exact: true }).fill("energia");
  await page.getByLabel("Unidad energia", { exact: true }).fill("mwh");
  await page.getByLabel("Valor energia", { exact: true }).fill("12");
  await page.getByLabel("Ventanas de presupuesto").selectOption("horizon");
  await page
    .getByRole("textbox", { name: "Código Python" })
    .fill(
      'def construir(ctx):\n    for v in ctx.ventanas():\n        ctx.restriccion("energia", v, v.integral(ctx.objeto.potencia) <= ctx.parametros.energia)\n',
    );
  const solve = async (preview: string) => {
    await page.getByRole("button", { name: "Guardar borrador" }).click();
    await page.getByRole("button", { name: "Publicar revisión" }).click();
    await page.getByRole("button", { name: "Probar restricciones" }).click();
    await expect(page.getByText(preview)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Duración real: 3.5 h")).toBeVisible();
    await expect(page.getByText("3 períodos · 3 términos")).toBeVisible();
    await page
      .getByLabel("Motivo de aplicación o desactivación")
      .fill("Presupuesto verificado");
    await page.getByRole("button", { name: "Aplicar a variante" }).click();
    await expect(page.getByText(/aplicada a esta variante/)).toBeVisible();
    const url = page.url();
    await page
      .getByRole("button", { name: "Ejecutar variante con reglas" })
      .click();
    await expect(page).toHaveURL(/\/runs\/\d+$/, { timeout: 120_000 });
    const id = Number(page.url().split("/").at(-1));
    const rows = await results(id);
    const run = (await (await api.get(`/api/runs/${id}`)).json()).run;
    const versionPath = `/api/scenario-versions/${run.scenario_version_id}`;
    return {
      url,
      id,
      rows,
      versionPath,
      version: await (await api.get(versionPath)).json(),
    };
  };
  const energy = await solve("Presupuesto efectivo: ≤ 12 MWh");
  expect(
    energy.rows.reduce(
      (sum, r) =>
        sum + Number(r.total_hydro_power_mw) * Number(r.duration_hours),
      0,
    ),
  ).toBeCloseTo(12);
  await page.goto(energy.url);
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Comparar presupuesto diario de agua");
  await page.getByRole("button", { name: "Desactivar aplicación" }).click();
  await expect(
    page.getByText(/aplicaciones desactivadas se conservan/),
  ).toBeVisible();
  await page
    .getByLabel("Nombre de la regla")
    .fill("Presupuesto diario de agua");
  await page.getByLabel("Parámetro 1", { exact: true }).fill("agua");
  await page.getByLabel("Unidad agua", { exact: true }).fill("hm3");
  await page.getByLabel("Valor agua", { exact: true }).fill("0.036");
  await page.getByLabel("Ventanas de presupuesto").selectOption("civil_day");
  await page
    .getByLabel("Acepto días parciales con el presupuesto completo")
    .check();
  await page
    .getByRole("textbox", { name: "Código Python" })
    .fill(
      'def construir(ctx):\n    for v in ctx.ventanas():\n        ctx.restriccion("agua", v, v.integral(ctx.objeto.caudal).a("hm3") <= ctx.parametros.agua)\n',
    );
  const water = await solve("Presupuesto efectivo: ≤ 0.036 hm³");
  expect(
    water.rows.reduce(
      (sum, r) =>
        sum +
        Number(r.total_hydro_turbine_flow_m3s) *
          Number(r.duration_hours) *
          3600,
      0,
    ),
  ).toBeCloseTo(36000);
  expect(
    water.version.scenario_version.system_case_json.component_rules
      .applications[0].windows,
  ).toEqual({ kind: "civil_day", timezone: "UTC", partial: "allow" });
  await page.goto(water.url);
  await expect(page.getByText("Día parcial aceptado · UTC")).toBeVisible();
  await page
    .getByRole("table")
    .filter({ hasText: "Presupuesto efectivo" })
    .screenshot({ path: "test-results/reg006-budget-preview.png" });
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Comparar sin presupuestos");
  await page.getByRole("button", { name: "Desactivar aplicación" }).click();
  await expect(
    page.getByText(/aplicaciones desactivadas se conservan/),
  ).toBeVisible();
  const response = await api.post(
    `/api/scenario-versions/${fixture.base_version_id}/runs`,
    { headers: await csrf(), data: {} },
  );
  expect(response.ok()).toBeTruthy();
  const base = await results((await response.json()).id);
  expect(
    base.reduce(
      (sum, r) =>
        sum + Number(r.total_hydro_power_mw) * Number(r.duration_hours),
      0,
    ),
  ).toBeCloseTo(105);
  expect(
    base.reduce(
      (sum, r) =>
        sum +
        Number(r.total_hydro_turbine_flow_m3s) *
          Number(r.duration_hours) *
          3600,
      0,
    ),
  ).toBeCloseTo(504000);
  expect(await (await api.get(energy.versionPath)).json()).toEqual(
    energy.version,
  );
  expect(await (await api.get(water.versionPath)).json()).toEqual(
    water.version,
  );
});
