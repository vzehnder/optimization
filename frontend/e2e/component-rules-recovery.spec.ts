import { expect, test } from "@playwright/test";

test("REG-009 retains, replaces and restores pins without changing historical solves", async ({
  page,
}) => {
  test.skip(!process.env.RULE_ACCEPTANCE_SERVER, "requires real OCI and Julia");
  test.setTimeout(420_000);
  page.setDefaultTimeout(25_000);
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
  const second = await (
    await api.get(
      `/api/scenarios/${scenario}/hydraulic-plants/plant_laja/units/unit_2/rule-context`,
    )
  ).json();
  const root = (id: number) =>
    `/api/projects/${context.project_id}/linkable-objects/${id}/rules`;
  const selected = await (
    await api.get(`${root(context.object_id)}/scope?scenario_id=${scenario}`)
  ).json();
  const scope = {
    scenario_id: scenario,
    variant_id: selected.variants[0].id,
    range_start: selected.range_start,
    range_end: selected.range_end,
  };
  const code =
    'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= ctx.parametros.limite)\n';
  const parameters = [
    {
      name: "limite",
      type: "number",
      unit: "m3_per_s",
      value: 5,
      min: 0,
      max: null,
    },
  ];
  const definition = {
    name: "Política de caudal",
    code,
    parameters,
    scenario_id: scenario,
    inputs: [],
    aliases: [],
    temporal: null,
    windows: null,
  };
  const saved = await post(root(context.object_id), {
    ...definition,
    expected_revision: 0,
  });
  const source = `${root(context.object_id)}/${saved.id}`;
  const publication = await post(`${source}/publications`, {
    expected_revision: 1,
  });
  await post(`${source}/library`, { publication_id: publication.id });
  const instantiate = async (id: number, name: string, value: number) => {
    const instance = await post(`${root(id)}/instances`, {
      publication_id: publication.id,
      scenario_id: scenario,
      variant_id: scope.variant_id,
      name,
      parameters: [{ ...parameters[0], value }],
      aliases: [],
      inputs: [],
      request_id: name,
      reason: "Límite local",
    });
    const path = `${root(id)}/${instance.id}`;
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
    const application = await post(`${path}/applications`, {
      job_id: job.id,
      reason: "Configuración inicial",
    });
    return { path, id: instance.id, object: id, application };
  };
  const north = await instantiate(context.object_id, "Norte", 5);
  const south = await instantiate(second.object_id, "Sur", 12);
  const url = (item: typeof north) =>
    `/react/projects/${context.project_id}/linkable-objects/${item.object}/rules?scenario_id=${scenario}&rule=${item.id}`;
  const solve = async (flow: number) => {
    const run = await post(
      `/api/scenarios/${scenario}/case/variants/${scope.variant_id}/run`,
      { range_start: scope.range_start, range_end: scope.range_end },
    );
    await expect
      .poll(
        async () =>
          (await (await api.get(`/api/runs/${run.id}`)).json()).run.status,
        { timeout: 90_000 },
      )
      .toBe("succeeded");
    const results = (
      await (await api.get(`/api/runs/${run.id}/results`)).json()
    ).results;
    for (const row of results.dispatch_table.rows)
      expect(Number(row.total_hydro_turbine_flow_m3s)).toBeCloseTo(flow);
    const versionPath = `/api/scenario-versions/${run.scenario_version_id}`;
    return {
      run,
      versionPath,
      version: await (await api.get(versionPath)).json(),
    };
  };
  const original = await solve(17);
  const update = await api.put(source, {
    headers: await csrf(),
    data: {
      ...definition,
      code: code.replace(
        "ctx.parametros.limite)",
        "ctx.parametros.limite / 2)",
      ),
      expected_revision: 1,
    },
  });
  expect(update.ok()).toBeTruthy();
  const newer = await post(`${source}/publications`, { expected_revision: 2 });

  const recover = async (
    item: typeof north,
    target: string,
    reason: string,
    historical?: string,
  ) => {
    await page.goto(url(item));
    await page
      .getByRole("button", { name: "Comparar y recuperar revisiones" })
      .click();
    if (historical)
      await page.getByLabel("Aplicación de origen").selectOption(historical);
    await page.getByLabel("Revisión a utilizar").selectOption(target);
    await page
      .getByRole("button", { name: "Comparar con la aplicación histórica" })
      .click();
    await expect(
      page.getByRole("table", { name: "Comparación de revisiones" }),
    ).toBeVisible();
    if (item === south && !historical)
      await page.screenshot({
        path: "test-results/reg009-comparison.png",
        fullPage: true,
      });
    await page.getByRole("button", { name: "Probar recuperación" }).click();
    await expect(
      page.getByText(
        "Prueba completa: 4 restricciones. No garantiza factibilidad.",
      ),
    ).toBeVisible({ timeout: 40_000 });
    const confirm = page.getByRole("button", {
      name: "Confirmar recuperación",
    });
    await expect(confirm).toBeDisabled();
    await page.getByLabel("Motivo de recuperación").fill(reason);
    await confirm.click();
    await expect(
      page.getByText(
        "Recuperación aplicada. La aplicación anterior permanece en el historial.",
      ),
    ).toBeVisible();
    const active = (
      await (await api.get(`${item.path}/applications`)).json()
    ).items.find((a: { status: string }) => a.status === "active");
    expect(active.publication_id).toBe(target);
    expect(active.validation_status).toBe("valid");
  };
  await recover(north, publication.id, "Mantener límite Norte");
  await recover(south, newer.id, "Adoptar nueva política Sur");
  await solve(11);
  await recover(
    south,
    publication.id,
    "Recuperar política anterior",
    south.application.id,
  );
  await solve(17);
  expect(await (await api.get(original.versionPath)).json()).toEqual(
    original.version,
  );
  await page.goto(`/react/runs/${original.run.id}`);
  await page.getByText("Ver revisión exacta consumida").first().click();
  const snapshot =
    original.version.scenario_version.system_case_json.component_rules
      .applications[0];
  await expect(
    page.getByText(snapshot.code_hash, { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/reg009-historical-run.png",
    fullPage: true,
  });

  await page.goto(
    `/react/projects/${context.project_id}/linkable-objects/${context.object_id}/rules?scenario_id=${scenario}&rule=${saved.id}`,
  );
  await page
    .getByRole("button", { name: "Comparar y recuperar revisiones" })
    .click();
  await page
    .getByLabel("Motivo de archivo")
    .fill("Retirar política compartida");
  await page
    .getByRole("button", { name: "Archivar definición", exact: true })
    .click();
  await expect(page.getByText("Definición: Archivada")).toBeVisible();
  await page.goto(url(north));
  await expect(page.getByRole("alert")).toContainText("archivada");
  await expect(
    page.getByRole("button", { name: "Ejecutar variante con reglas" }),
  ).toBeDisabled();
  expect(await (await api.get(original.versionPath)).json()).toEqual(
    original.version,
  );
});
