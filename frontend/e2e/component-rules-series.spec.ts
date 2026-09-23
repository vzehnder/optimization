import { expect, test } from "@playwright/test";

test("REG-007 publishes power, solves a compatible case and regenerates while preserving its old pin and run", async ({
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
  await page.getByLabel("Nombre de la regla").fill("Potencia calculada");
  await page
    .getByRole("textbox", { name: "Código Python" })
    .fill(
      'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.salida("potencia", t, ctx.parametros.capacidad * ctx.entradas.disponibilidad[t])\n',
    );
  await page.getByLabel("Unidad capacidad", { exact: true }).fill("mw");
  await page.getByLabel("Valor capacidad", { exact: true }).fill("20");
  const selectAvailability = async () => {
    await page
      .getByRole("button", { name: "Seleccionar entrada", exact: true })
      .click();
    await page.getByRole("button", { name: "Continuar selección" }).click();
    await page
      .getByRole("radio", { name: /Disponibilidad programada/ })
      .check();
    await page.getByRole("button", { name: "Continuar selección" }).click();
    await page.getByRole("button", { name: "Continuar selección" }).click();
    await page
      .getByRole("button", { name: "Usar entrada en borrador" })
      .click();
  };
  const compile = async () => {
    await page.getByRole("button", { name: "Guardar borrador" }).click();
    await expect(page.getByText(/Borrador guardado/)).not.toContainText(
      "cambios sin guardar",
    );
    await page
      .getByRole("button", { name: "Publicar revisión", exact: true })
      .click();
    await page.getByRole("button", { name: "Probar restricciones" }).click();
    await expect(
      page.getByRole("button", { name: "Publicar serie calculada" }),
    ).toBeEnabled({ timeout: 30_000 });
  };
  await selectAvailability();
  await compile();
  await page.getByRole("button", { name: "Publicar serie calculada" }).click();
  await page.getByRole("button", { name: "Continuar publicación" }).click();
  await page
    .getByLabel("Nombre de la serie")
    .fill("Potencia disponible REG007");
  await page.getByLabel("Clave de la serie").fill("potencia_disponible");
  await page
    .getByLabel("Clasificación de la salida")
    .selectOption("renewable_available_power");
  await page.getByRole("button", { name: "Continuar publicación" }).click();
  await expect(page.getByText(/4 intervalos completos/)).toBeVisible();
  await page.getByRole("button", { name: "Continuar publicación" }).click();
  await page
    .getByLabel("Motivo de publicación")
    .fill("Disponibilidad revisada");
  const published = page.waitForResponse(
    (r) =>
      r.request().method() === "POST" &&
      r.url().endsWith("/series-publications"),
  );
  await page.getByRole("button", { name: "Confirmar publicación" }).click();
  const receipt = await (await published).json();
  await expect(page.getByText(/Serie publicada.*revisión 1/)).toBeVisible();
  const rulesUrl = page.url();
  await page.getByRole("link", { name: "Ver serie publicada" }).click();
  await expect(page).toHaveURL(/time-series\/catalog/);
  await expect(
    page.getByRole("heading", { name: "Potencia disponible REG007" }),
  ).toBeVisible();

  const consumer = await (await api.get("/api/auth/reg007-fixture")).json();
  const variant = (
    await (
      await api.get(
        `/api/scenarios/${consumer.scenario_id}/case/default-variant`,
      )
    ).json()
  ).variant.id;
  const root = `/api/scenarios/${consumer.scenario_id}/case-variants/${variant}`;
  const selections = [
    {
      role: "renewable_available_power",
      owner: consumer.solar_object_id,
      signal: receipt.signal_id,
      revision: receipt.revision_id,
      hash: receipt.content_hash,
    },
    ...["grid_import_price", "grid_export_price"].map((role) => ({
      role,
      owner: consumer.system_object_id,
      signal: consumer.price.signal_ids.price,
      revision: consumer.price.revision_id,
      hash: consumer.price.content_hash,
    })),
  ];
  const request = {
    expected_bindings_revision: 0,
    operations: selections.map((s) => ({
      client_operation_id: s.role,
      action: "create",
      linkable_object_id: s.owner,
      binding_role_key: s.role,
      signal_id: s.signal,
      revision: {
        mode: "current",
        revision_id: s.revision,
        content_hash: s.hash,
      },
      catalog_association_id: null,
      reason_code: "variant_input_selected",
    })),
  };
  const review = await (
    await api.post(`${root}/time-series-binding-prevalidations`, {
      headers: await csrf(),
      data: request,
    })
  ).json();
  expect(review.can_commit).toBeTruthy();
  const bound = await api.post(`${root}/time-series-binding-batches`, {
    headers: {
      ...(await csrf()),
      "If-Match": review.commit_etag,
      "Idempotency-Key": "reg007-bind",
    },
    data: {
      ...request,
      prevalidation_token: review.prevalidation_token,
      confirmed: true,
    },
  });
  expect(bound.status()).toBe(201);
  const runPath = `/api/scenarios/${consumer.scenario_id}/case/variants/${variant}/run`;
  const runBody = {
    range_start: "2026-01-01T00:00:00",
    range_end: "2026-01-01T04:00:00",
  };
  const runResponse = await api.post(runPath, {
    headers: await csrf(),
    data: runBody,
  });
  expect(runResponse.status(), await runResponse.text()).toBe(201);
  const run = await runResponse.json();
  await expect
    .poll(
      async () =>
        (await (await api.get(`/api/runs/${run.id}`)).json()).run.status,
      { timeout: 120_000 },
    )
    .toBe("succeeded");
  const versionPath = `/api/scenario-versions/${run.scenario_version_id}`;
  const historical = await (await api.get(versionPath)).json();
  expect(
    historical.scenario_version.system_case_json.time_series.map(
      (p: { renewable_available_power_mw: { reg007_solar: number } }) =>
        p.renewable_available_power_mw.reg007_solar,
    ),
  ).toEqual([20, 10, 15, 20]);
  await api.post("/api/auth/reg003-republish", { headers: await csrf() });
  await page.goto(rulesUrl);
  await expect(page.getByText(/Receta obsoleta/)).toBeVisible();
  await page
    .getByRole("button", { name: "Quitar entrada disponibilidad" })
    .click();
  await selectAvailability();
  await compile();
  await page
    .getByRole("button", { name: "Regenerar Potencia disponible REG007" })
    .click();
  for (let step = 0; step < 3; step++)
    await page.getByRole("button", { name: "Continuar publicación" }).click();
  await page
    .getByLabel("Motivo de publicación")
    .fill("Nueva disponibilidad verificada");
  const regeneration = page.waitForResponse(
    (r) =>
      r.request().method() === "POST" && r.url().endsWith("/regenerations"),
  );
  await page.getByRole("button", { name: "Confirmar regeneración" }).click();
  const revised = await (await regeneration).json();
  await expect(page.getByText(/Serie publicada.*revisión 2/)).toBeVisible();
  expect(revised.signal_id).toBe(receipt.signal_id);
  expect(revised.revision_id).not.toBe(receipt.revision_id);
  const bindings = await (await api.get(`${root}/time-series-bindings`)).json();
  const power = bindings.items.find(
    (b: { signal_id: number }) => b.signal_id === receipt.signal_id,
  );
  expect([power.set_revision_id, power.state]).toEqual([
    receipt.revision_id,
    "stale",
  ]);
  expect(
    (
      await api.post(runPath, { headers: await csrf(), data: runBody })
    ).status(),
  ).toBe(409);
  expect(await (await api.get(versionPath)).json()).toEqual(historical);
  const preview = await (
    await api.get(
      `/api/time-series/catalog/inputs/${receipt.signal_id}/preview?revision_id=${revised.revision_id}&from=2026-01-01T00:00:00Z&to=2026-01-01T04:00:00Z&sampling=none&max_points=4`,
    )
  ).json();
  expect(preview.points.map((p: { value: number }) => p.value)).toEqual([
    10, 10, 10, 10,
  ]);
  await page.screenshot({
    path: "test-results/reg007-published-series.png",
    fullPage: true,
  });
});
