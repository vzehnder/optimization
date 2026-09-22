import { expect, test } from "@playwright/test";

test("REG-003 selects canonical inputs, solves hourly limits and locates stale, missing and crossed inputs", async ({
  page,
}) => {
  test.skip(!process.env.RULE_ACCEPTANCE_SERVER, "requires real OCI and Julia");
  test.setTimeout(300_000);
  page.setDefaultTimeout(20_000);
  const api = page.request;
  const csrf = async () => ({
    "X-CSRF-Token": (await (await api.get("/api/auth/csrf")).json()).csrf_token,
  });
  const login = await api.post("/api/auth/bootstrap", {
    headers: await csrf(),
    data: {
      email: "admin@example.local",
      display_name: "Analista",
      password: "admin-pass",
      next: "/react/projects",
    },
  });
  expect(login.ok()).toBeTruthy();
  const fixture = await (await api.get("/api/auth/reg002-fixture")).json();
  await page.goto(
    `/react/scenarios/${fixture.scenario_id}/hydraulic-plants/plant_laja/units/unit_1/rules`,
  );
  await page.getByLabel("Nombre de la regla").fill("Límites horarios");
  await page
    .getByRole("textbox", { name: "Código Python" })
    .fill(
      'def construir(ctx):\n    for t in ctx.periodos:\n        minimo = ctx.entradas.afluente[t] * ctx.parametros.fraccion\n        maximo = ctx.parametros.capacidad * ctx.entradas.disponibilidad[t]\n        ctx.restriccion("minimo", t, ctx.objeto.caudal[t] >= minimo)\n        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= maximo)\n        ctx.salida("minimo", t, minimo)\n        ctx.salida("maximo", t, maximo)\n',
    );
  await page.getByLabel("Valor capacidad", { exact: true }).fill("20");
  await page.getByLabel("Parámetro 2", { exact: true }).fill("fraccion");
  await page.getByLabel("Valor fraccion", { exact: true }).fill("0.25");
  const select = async (name: string) => {
    await page
      .getByRole("button", { name: "Seleccionar entrada", exact: true })
      .click();
    await page.getByRole("button", { name: "Continuar selección" }).click();
    await page.getByRole("radio", { name: new RegExp(name) }).check();
    await page.getByRole("button", { name: "Continuar selección" }).click();
    await page.getByRole("button", { name: "Continuar selección" }).click();
    await page
      .getByRole("button", { name: "Usar entrada en borrador" })
      .click();
  };
  await select("Afluente operativo");
  await select("Disponibilidad programada");
  const compile = async () => {
    await page.getByRole("button", { name: "Guardar borrador" }).click();
    await expect(page.getByText(/Borrador guardado/)).not.toContainText(
      "cambios sin guardar",
    );
    await page.getByRole("button", { name: "Publicar revisión" }).click();
    await page.getByRole("button", { name: "Probar restricciones" }).click();
  };
  await compile();
  await expect(
    page.getByRole("table", { name: "Límites y salidas horarias" }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByRole("img", { name: /Curvas horarias/ }),
  ).toBeVisible();
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Programa horario revisado");
  await page.getByRole("button", { name: "Aplicar a variante" }).click();
  await expect(page.getByText(/aplicada a esta variante/)).toBeVisible();
  const rulesUrl = page.url();
  await page.screenshot({
    path: "test-results/reg003-hourly-preview.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Ejecutar variante con reglas" })
    .click();
  await expect(page).toHaveURL(/\/runs\/\d+$/, { timeout: 90_000 });
  const runId = Number(page.url().split("/").at(-1));
  await expect
    .poll(
      async () =>
        (await (await api.get(`/api/runs/${runId}`)).json()).run.status,
      { timeout: 120_000 },
    )
    .toBe("succeeded");
  const results = (await (await api.get(`/api/runs/${runId}/results`)).json())
    .results;
  expect(
    results.dispatch_table.rows.map((r: Record<string, unknown>) =>
      Number(r.total_hydro_turbine_flow_m3s),
    ),
  ).toEqual([20, 10, 15, 20]);
  const run = (await (await api.get(`/api/runs/${runId}`)).json()).run;
  const historical = await (
    await api.get(`/api/scenario-versions/${run.scenario_version_id}`)
  ).json();
  expect(
    (
      await api.post("/api/auth/reg003-republish", { headers: await csrf() })
    ).ok(),
  ).toBeTruthy();
  await page.goto(rulesUrl);
  await expect(page.getByText(/Entrada obsoleta/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Ejecutar variante con reglas" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Probar revisión fijada" }).click();
  await expect(page.getByText("Compilando restricciones…")).toBeVisible();
  await expect(page.getByText("Compilando restricciones…")).not.toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByRole("table", { name: "Límites y salidas horarias" }),
  ).toBeVisible();
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Mantener programa anterior revalidado");
  await page.getByRole("button", { name: "Desactivar aplicación" }).click();
  await page.getByRole("button", { name: "Aplicar a variante" }).click();
  await expect(page.getByText(/Entrada obsoleta/)).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "Ejecutar variante con reglas" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Quitar entrada afluente" }).click();
  await select("Afluente incompleto");
  await compile();
  await expect(
    page.getByRole("alert").filter({ hasText: /afluente · período 4/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Quitar entrada afluente" }).click();
  await select("Afluente con cruce");
  await compile();
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: /período 3.*RULE_BOUNDS_CONFLICT/ }),
  ).toBeVisible({ timeout: 30_000 });
  await page.screenshot({
    path: "test-results/reg003-crossed-bounds.png",
    fullPage: true,
  });
  expect(
    await (
      await api.get(`/api/scenario-versions/${run.scenario_version_id}`)
    ).json(),
  ).toEqual(historical);
});
