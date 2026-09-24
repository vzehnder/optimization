import { expect, test } from "@playwright/test";

test("REG-008 reuses one revision with independent limits and preserves historical solves", async ({
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
  const { scenario_id: scenario } = await (
    await api.get("/api/auth/reg004-fixture")
  ).json();
  const context = await (
    await api.get(
      `/api/scenarios/${scenario}/hydraulic-plants/plant_laja/units/unit_1/rule-context`,
    )
  ).json();
  const second = await (
    await api.get(
      `/api/scenarios/${scenario}/hydraulic-plants/plant_laja/units/unit_2/rule-context`,
    )
  ).json();
  const url = (id: number) =>
    `/react/projects/${context.project_id}/linkable-objects/${id}/rules?scenario_id=${scenario}&return_to=/scenarios/${scenario}/hydraulic-diagram`;
  await page.goto(url(context.object_id));
  await page.getByRole("button", { name: "Biblioteca del proyecto" }).click();
  await page.getByText("Ejemplos editables", { exact: true }).click();
  await page
    .getByRole("button", {
      name: "Crear ejemplo: Máximo de caudal",
      exact: true,
    })
    .click();
  await page.getByLabel("Nombre de la regla").fill("Caudal reutilizable");
  await page.getByRole("button", { name: "Guardar borrador" }).click();
  const sourceUrl = page.url();
  await page
    .getByRole("button", { name: "Publicar revisión", exact: true })
    .click();
  await page.getByRole("button", { name: "Ofrecer en biblioteca" }).click();
  await expect(
    page.getByText("Revisión disponible en la biblioteca del proyecto."),
  ).toBeVisible();
  const apply = async () => {
    await page
      .getByRole("button", { name: "Preparar revisión fijada" })
      .click();
    await page
      .getByRole("button", { name: "Probar restricciones", exact: true })
      .click();
    await expect(page.getByText(/4 restricciones · unidad m³\/s/)).toBeVisible({
      timeout: 30_000,
    });
    await page
      .getByLabel("Motivo de aplicación o desactivación")
      .fill("Límite local comprobado");
    await page
      .getByRole("button", { name: "Aplicar a variante", exact: true })
      .click();
    await expect(page.getByText(/aplicada a esta variante/)).toBeVisible();
  };
  const instantiate = async (id: number, name: string, value: number) => {
    await page.goto(url(id));
    await page.getByRole("button", { name: "Biblioteca del proyecto" }).click();
    await page
      .getByRole("button", {
        name: "Usar Caudal reutilizable · revisión 2",
        exact: true,
      })
      .click();
    await page.getByLabel("Nombre de la instancia").fill(name);
    await page
      .getByLabel("Valor local limite", { exact: true })
      .fill(String(value));
    await page
      .getByLabel("Motivo de reutilización")
      .fill("Capacidad propia de la unidad");
    await page
      .getByRole("button", { name: "Crear instancia", exact: true })
      .click();
    await expect(page.getByText(/Revisión compartida fijada:/)).toBeVisible();
    await apply();
    return page.url();
  };
  const firstUrl = await instantiate(context.object_id, "Límite Norte", 5);
  const secondUrl = await instantiate(second.object_id, "Límite Sur", 12);
  const solve = async (flow: number) => {
    await page
      .getByRole("button", { name: "Ejecutar variante con reglas" })
      .click();
    await expect(page).toHaveURL(/\/runs\/\d+$/, { timeout: 60_000 });
    const runId = page.url().split("/").at(-1);
    await expect
      .poll(
        async () =>
          (await (await api.get(`/api/runs/${runId}`)).json()).run.status,
        { timeout: 90_000 },
      )
      .toBe("succeeded");
    const run = (await (await api.get(`/api/runs/${runId}`)).json()).run;
    const results = (await (await api.get(`/api/runs/${runId}/results`)).json())
      .results;
    for (const row of results.dispatch_table.rows)
      expect(Number(row.total_hydro_turbine_flow_m3s)).toBeCloseTo(flow);
    const path = `/api/scenario-versions/${run.scenario_version_id}`;
    const version = await (await api.get(path)).json();
    const block = version.scenario_version.system_case_json.component_rules;
    expect(
      new Set(
        block.rows.map(
          (r: { application_id: string; name: string; period: number }) =>
            `${r.application_id}:${r.name}:${r.period}`,
        ),
      ).size,
    ).toBe(8);
    expect(
      new Set(
        block.applications.map(
          (a: { publication_id: string }) => a.publication_id,
        ),
      ).size,
    ).toBe(1);
    return { path, version };
  };
  const original = await solve(17);
  await page.goto(secondUrl);
  await page.getByLabel("Valor limite", { exact: true }).fill("8");
  await page.getByRole("button", { name: "Guardar borrador" }).click();
  await expect(page.getByRole("alert")).toContainText("configuración local");
  await page
    .getByLabel("Motivo de aplicación o desactivación")
    .fill("Actualizar solo Sur");
  await page.getByRole("button", { name: "Desactivar aplicación" }).click();
  await apply();
  await solve(13);
  await page.goto(firstUrl);
  await page.getByRole("button", { name: "Biblioteca del proyecto" }).click();
  await page
    .getByRole("button", {
      name: "Comparar instancias · Caudal reutilizable · revisión 2",
    })
    .click();
  await expect(page.getByText("limite: 5 m³/s", { exact: true })).toBeVisible();
  await expect(page.getByText("limite: 8 m³/s", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "test-results/reg008-comparison.png",
    fullPage: true,
  });
  await page.goto(sourceUrl);
  await page.getByLabel("Valor limite", { exact: true }).fill("7");
  await page.getByRole("button", { name: "Guardar borrador" }).click();
  await page
    .getByRole("button", { name: "Publicar revisión", exact: true })
    .click();
  await page.goto(firstUrl);
  await expect(page.getByRole("alert")).toContainText(
    "nueva revisión publicada",
  );
  await expect(
    page.getByRole("button", { name: "Ejecutar variante con reglas" }),
  ).toBeDisabled();
  expect(await (await api.get(original.path)).json()).toEqual(original.version);
});
