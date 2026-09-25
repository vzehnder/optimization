import { expect, test } from "@playwright/test";

test("REG-013 relates grid and renewables from the editor through solve and compliance", async ({
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
  const { scenario_id: scenario } = await (
    await api.get("/api/auth/reg013-fixture")
  ).json();
  await page.goto(`/react/scenarios/${scenario}/draft`);
  await page.getByRole("button", { name: "Editar Renovable · solar" }).click();
  await page
    .getByRole("link", { name: "Cálculos y restricciones · solar" })
    .click();
  await expect(
    page.getByText(/Generación y recorte son magnitudes no negativas/),
  ).toBeVisible();
  await page.getByRole("link", { name: "Volver al componente" }).click();
  await page
    .getByRole("link", { name: "Cálculos y restricciones · grid" })
    .click();
  await expect(
    page.getByText(/positivo significa exportación neta/),
  ).toBeVisible();
  const context = await (
    await api.get(`/api/scenarios/${scenario}/components/grid/rule-context`)
  ).json();
  const root = `/api/projects/${context.project_id}/linkable-objects/${context.object_id}/rules`;
  const objects = (
    await (
      await api.get(`${root}/object-candidates?scenario_id=${scenario}`)
    ).json()
  ).items;
  for (const [kind, alias] of [
    ["renewable", "solar"],
    ["load", "consumo"],
  ]) {
    await page
      .getByLabel("Objeto a relacionar")
      .selectOption(
        String(objects.find((o: { kind: string }) => o.kind === kind).id),
      );
    await page.getByLabel("Alias del objeto").fill(alias);
    await page.getByRole("button", { name: "Agregar alias" }).click();
  }
  await page
    .getByLabel("Código Python")
    .fill(
      'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("fraccion", t, ctx.objeto.exportacion[t] <= ctx.parametros.fraccion * ctx.objetos.solar.generacion[t])\n        ctx.restriccion("disponibilidad", t, ctx.objetos.solar.generacion[t] + ctx.objetos.solar.recorte[t] == ctx.objetos.solar.disponibilidad[t])\n        ctx.restriccion("balance", t, ctx.objeto.importacion[t] - ctx.objeto.exportacion[t] + ctx.objetos.solar.generacion[t] == ctx.objetos.consumo.demanda[t])\n',
    );
  await page.getByRole("button", { name: "Guardar borrador" }).click();
  await expect(page.getByText(/Borrador guardado/)).toBeVisible();
  const saved = (await (await api.get(root)).json()).items[0];
  await page.getByRole("button", { name: "Publicar revisión" }).click();
  await page.getByRole("button", { name: "Probar restricciones" }).click();
  await expect(page.getByText(/12 restricciones/)).toBeVisible({
    timeout: 30_000,
  });
  expect(
    (await (await api.get(`${root}/${saved.id}/applications`)).json()).items,
  ).toEqual([]);
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Limitar exportación al 50 % de la generación utilizada");
  await page.getByRole("button", { name: "Aplicar a variante" }).click();
  await expect(page.getByText(/aplicada a esta variante/)).toBeVisible();
  await page.screenshot({
    path: "test-results/reg013-applied.png",
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
  for (const [i, exported, used, curtailed, imported, available] of [
    [0, 2, 4, 6, 0, 10],
    [1, 2, 4, 4, 0, 8],
    [2, 0, 1, 0, 1, 1],
    [3, 0, 0, 0, 2, 0],
  ]) {
    expect(Number(rows[i].grid_export_mw)).toBeCloseTo(exported);
    expect(Number(rows[i].grid_import_mw)).toBeCloseTo(imported);
    expect(Number(rows[i].renewable_used_mw)).toBeCloseTo(used);
    expect(Number(rows[i].renewable_curtailed_mw)).toBeCloseTo(curtailed);
    expect(
      Number(rows[i].grid_import_mw) +
        Number(rows[i].renewable_used_mw) -
        Number(rows[i].grid_export_mw),
    ).toBeCloseTo(2);
    expect(
      Number(rows[i].renewable_used_mw) +
        Number(rows[i].renewable_curtailed_mw),
    ).toBeCloseTo(available);
  }
  const complianceResponse = await api.get(
    `/api/runs/${runId}/rule-compliance`,
  );
  expect(complianceResponse.ok(), await complianceResponse.text()).toBeTruthy();
  const compliance = await complianceResponse.json();
  expect(compliance.counts).toEqual({
    total: 12,
    evaluated: 12,
    satisfied: 12,
    violated: 0,
    unavailable: 0,
  });
  expect(compliance.rules[0].rule_id).toBe(saved.id);
  await expect(page.getByText(/12 evaluadas/)).toBeVisible();
  await page
    .getByRole("region", { name: "Cumplimiento de reglas" })
    .screenshot({ path: "test-results/reg013-compliance.png" });
});
