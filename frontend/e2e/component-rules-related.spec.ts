import { expect, test } from "@playwright/test";

test("REG-004 solves a shared limit, repeats it through a plant, and blocks changed membership", async ({
  page,
}) => {
  test.skip(!process.env.RULE_ACCEPTANCE_SERVER, "requires real OCI and Julia");
  test.setTimeout(360_000);
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
  const fixture = await (await api.get("/api/auth/reg004-fixture")).json();
  await page.goto(`/react/scenarios/${fixture.scenario_id}/hydraulic-diagram`);
  await page
    .getByRole("group", { name: "Central plant_laja", exact: true })
    .click();
  await page
    .getByRole("link", { name: "Cálculos y restricciones · unit_1" })
    .click();
  await page.getByLabel("Nombre de la regla").fill("Generación compartida");
  const selectAlias = async (key: string, alias: string) => {
    const option = page
      .getByLabel("Objeto a relacionar")
      .getByRole("option", { name: new RegExp(`· ${key}$`) });
    await page
      .getByLabel("Objeto a relacionar")
      .selectOption((await option.getAttribute("value")) as string);
    await page.getByLabel("Alias del objeto").fill(alias);
    await page.getByRole("button", { name: "Agregar alias" }).click();
  };
  await selectAlias("unit_2", "segunda");
  await selectAlias("plant_laja", "central");
  await selectAlias("reservoir_alpha", "agua");
  await page.getByLabel("Parámetro 1", { exact: true }).fill("limite");
  await page.getByLabel("Unidad limite", { exact: true }).fill("mw");
  await page.getByLabel("Valor limite", { exact: true }).fill("10");
  await page.getByRole("button", { name: "Quitar parámetro 2" }).click();
  const ruleCode = (expression: string) =>
    `def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("conjunto", t, ${expression} <= ctx.parametros.limite)\n`;
  const solve = async () => {
    await page.getByRole("button", { name: "Guardar borrador" }).click();
    await page.getByRole("button", { name: "Publicar revisión" }).click();
    await page.getByRole("button", { name: "Probar restricciones" }).click();
    await expect(page.getByText(/4 restricciones · unidad MW/)).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page
        .getByRole("cell", {
          name: "1 × Unit 1.potencia + 1 × Unit 2.potencia <= 10 MW",
          exact: true,
        })
        .first(),
    ).toBeVisible();
    await page
      .getByLabel("Motivo de aplicación o desactivación")
      .fill("Límite compartido de generación");
    await page.getByRole("button", { name: "Aplicar a variante" }).click();
    await expect(page.getByText(/aplicada a esta variante/)).toBeVisible();
    const rulesUrl = page.url();
    await page.screenshot({
      path: "test-results/reg004-preview.png",
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Ejecutar variante con reglas" })
      .click();
    await expect(page).toHaveURL(/\/runs\/\d+$/, { timeout: 60_000 });
    const id = Number(page.url().split("/").at(-1));
    await expect
      .poll(
        async () =>
          (await (await api.get(`/api/runs/${id}`)).json()).run.status,
        { timeout: 90_000 },
      )
      .toBe("succeeded");
    const result = (await (await api.get(`/api/runs/${id}/results`)).json())
      .results;
    for (const row of result.dispatch_table.rows)
      expect(Number(row.total_hydro_power_mw)).toBeCloseTo(10);
    return { id, rulesUrl };
  };
  await page
    .getByRole("textbox", { name: "Código Python" })
    .fill(ruleCode("ctx.objeto.potencia[t] + ctx.objetos.segunda.potencia[t]"));
  const first = await solve();
  await page.goto(first.rulesUrl);
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Usar generación agregada de planta");
  await page.getByRole("button", { name: "Desactivar aplicación" }).click();
  await page
    .getByRole("textbox", { name: "Código Python" })
    .fill(ruleCode("ctx.objetos.central.potencia[t]"));
  const second = await solve();
  const run = (await (await api.get(`/api/runs/${second.id}`)).json()).run;
  const versionPath = `/api/scenario-versions/${run.scenario_version_id}`;
  const version = await (await api.get(versionPath)).json();
  expect(
    version.scenario_version.system_case_json.component_rules.applications[0]
      .aliases,
  ).toHaveLength(3);
  expect(
    (
      await api.post("/api/auth/reg004-membership", { headers: await csrf() })
    ).ok(),
  ).toBeTruthy();
  await page.goto(second.rulesUrl);
  await expect(
    page.getByRole("button", { name: "Ejecutar variante con reglas" }),
  ).toBeDisabled();
  await expect(page.getByRole("alert")).toContainText(/segunda:.*snapshot/);
  await expect(
    page
      .getByLabel("Objeto a relacionar")
      .getByRole("option", { name: /Unit 1/ }),
  ).toBeAttached();
  await page.screenshot({
    path: "test-results/reg004-stale.png",
    fullPage: true,
  });
  expect(await (await api.get(versionPath)).json()).toEqual(version);
});
