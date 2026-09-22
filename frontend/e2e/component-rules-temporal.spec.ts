import { expect, test } from "@playwright/test";

test("REG-005 compares initial policies in a real solve with unequal intervals", async ({
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
  const fixture = await (await api.get("/api/auth/reg005-fixture")).json();
  await page.goto(`/react/scenarios/${fixture.scenario_id}/hydraulic-diagram`);
  await page
    .getByRole("group", { name: "Central plant_laja", exact: true })
    .click();
  await page
    .getByRole("link", { name: "Cálculos y restricciones · unit_1" })
    .click();
  await page.getByLabel("Nombre de la regla").fill("Rampas de caudal");
  await page.getByLabel("Parámetro 1", { exact: true }).fill("subida");
  await page
    .getByLabel("Unidad subida", { exact: true })
    .fill("m3_per_s_per_h");
  await page.getByLabel("Valor subida", { exact: true }).fill("4");
  await page.getByLabel("Parámetro 2", { exact: true }).fill("bajada");
  await page
    .getByLabel("Unidad bajada", { exact: true })
    .fill("m3_per_s_per_h");
  await page.getByLabel("Máximo bajada", { exact: true }).fill("10");
  await page.getByLabel("Valor bajada", { exact: true }).fill("2");
  await page
    .getByRole("button", { name: "Agregar parámetro", exact: true })
    .click();
  await page.getByLabel("Parámetro 3", { exact: true }).fill("final");
  await page.getByLabel("Unidad final", { exact: true }).fill("m3_per_s");
  await page.getByLabel("Valor final", { exact: true }).fill("1");
  const code =
    'def construir(ctx):\n    for paso in ctx.transiciones(ctx.objeto.caudal):\n        diferencia = paso.actual - paso.anterior\n        ctx.restriccion("subida", paso.periodo, diferencia <= ctx.parametros.subida * paso.horas)\n        ctx.restriccion("bajada", paso.periodo, -diferencia <= ctx.parametros.bajada * paso.horas)\n    t = len(ctx.periodos) - 1\n    ctx.restriccion("final", t, ctx.objeto.caudal[t] <= ctx.parametros.final)\n';
  await page.getByRole("textbox", { name: "Código Python" }).fill(code);
  await page.getByLabel("Política del primer período").selectOption("initial");
  await page.getByRole("button", { name: "Agregar valor inicial" }).click();
  await page.getByLabel("Valor inicial 1").fill("2");
  await page.getByLabel("Instante inicial 1").fill("2025-12-31T23:30:00Z");
  const solve = async (flows: number[], count: number) => {
    await page.getByRole("button", { name: "Guardar borrador" }).click();
    await page.getByRole("button", { name: "Publicar revisión" }).click();
    await page.getByRole("button", { name: "Probar restricciones" }).click();
    await expect(
      page.getByText(new RegExp(`${count} restricciones · unidad m³/s`)),
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByText(/Distancia entre inicios: 0.5 h/).first(),
    ).toBeVisible();
    await page
      .getByLabel("Motivo de aplicación o desactivación")
      .fill("Rampas en grilla variable");
    await page.getByRole("button", { name: "Aplicar a variante" }).click();
    await expect(page.getByText(/aplicada a esta variante/)).toBeVisible();
    const url = page.url();
    await page.screenshot({
      path: `test-results/reg005-${count}-preview.png`,
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Ejecutar variante con reglas" })
      .click();
    await expect(page).toHaveURL(/\/runs\/\d+$/, { timeout: 90_000 });
    const id = Number(page.url().split("/").at(-1));
    await expect
      .poll(
        async () =>
          (await (await api.get(`/api/runs/${id}`)).json()).run.status,
        { timeout: 90_000 },
      )
      .toBe("succeeded");
    const results = (await (await api.get(`/api/runs/${id}/results`)).json())
      .results;
    expect(results.dispatch_table.rows).toHaveLength(3);
    results.dispatch_table.rows.forEach(
      (r: { total_hydro_turbine_flow_m3s: number }, i: number) =>
        expect(Number(r.total_hydro_turbine_flow_m3s)).toBeCloseTo(flows[i]),
    );
    const run = (await (await api.get(`/api/runs/${id}`)).json()).run;
    const versionPath = `/api/scenario-versions/${run.scenario_version_id}`;
    return {
      url,
      versionPath,
      version: await (await api.get(versionPath)).json(),
    };
  };
  const initial = await solve([4, 5, 1], 7);
  expect(
    initial.version.scenario_version.system_case_json.component_rules
      .applications[0].temporal.initial_values[0].timestamp,
  ).toBe("2025-12-31T23:30:00Z");
  await page.goto(initial.url);
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Comparar omisión inicial");
  await page.getByRole("button", { name: "Desactivar aplicación" }).click();
  await page.getByLabel("Política del primer período").selectOption("omit");
  const omitted = await solve([6, 5, 1], 5);
  await page.goto(omitted.url);
  await expect(
    page.getByText(/Primera comparación omitida: período 1/),
  ).toBeVisible();
  await page.getByLabel("Inicio UTC").fill("2026-01-01T00:30:00");
  await expect(
    page.getByText(/El horizonte o la variante cambió/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Aplicar a variante" }),
  ).toBeDisabled();
  expect(await (await api.get(initial.versionPath)).json()).toEqual(
    initial.version,
  );
});
