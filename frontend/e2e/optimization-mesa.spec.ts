import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";

async function openPersonalMesa(
  page: Page,
  name: string,
  withReplacement = false,
  electrical = false,
  withRun = false,
  hydraulic = false,
  executable = false,
) {
  const fixture = await (
    await page.request.get(
      `/api/auth/mesa-fixture?case_name=${encodeURIComponent(name)}&with_replacement=${withReplacement}&electrical=${electrical}&with_run=${withRun}&hydraulic=${hydraulic}&executable=${executable}`,
    )
  ).json();
  const csrf = await (await page.request.get("/api/auth/csrf")).json();
  await page.request.post("/api/auth/login", {
    data: {
      email: "mesa@example.local",
      password: "mesa test pass",
      next: "/react/projects",
    },
    headers: { "X-CSRF-Token": csrf.csrf_token },
  });
  await page.goto(
    `/react/scenarios/${fixture.scenario.id}/mesa?case=${fixture.case.id}&variant=${fixture.variant.id}`,
  );
  return fixture;
}

test("Ejecución eléctrica valida, recupera el mismo run al recargar y consulta sus resultados", async ({
  page,
}, testInfo) => {
  test.setTimeout(180000);
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await openPersonalMesa(
    page,
    "Ejecutar mesa",
    false,
    true,
    false,
    false,
    true,
  );
  const demand = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await page.goto(
    `/react/scenarios/${fixture.scenario.id}?section=data&variant=${fixture.variant.id}`,
  );
  await page.getByRole("link", { name: "Abrir mesa de optimización" }).click();
  for (const [title, key, signal] of [
    ["Descarga BESS", "battery_1", "Descarga BESS"],
    ["Energía BESS", "battery_1", "Energía almacenada"],
    ["Solar disponible", "solar_north", "Disponibilidad solar"],
  ]) {
    await page
      .getByRole("button", { name: "Agregar vista", exact: true })
      .click();
    const view = page.getByRole("dialog", { name: "Configurar vista" });
    const label = await view
      .getByRole("option")
      .filter({ hasText: key })
      .textContent();
    await view.getByLabel("Componente").selectOption({ label: label! });
    await view.getByLabel("Título").fill(title);
    for (const checkbox of await view.getByRole("checkbox").all())
      await checkbox.uncheck();
    await view.getByRole("checkbox", { name: new RegExp(signal) }).check();
    await view.getByRole("button", { name: "Aplicar", exact: true }).click();
  }
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator(".mesa-panel")).toHaveCount(4);
  await demand.getByRole("button", { name: "Tabla", exact: true }).click();
  await demand
    .getByRole("button", { name: "Editar entrada", exact: true })
    .click();
  const editor = page.getByRole("dialog", {
    name: "Editar entrada · Demanda medida",
  });
  await editor.getByLabel("Valor del intervalo 2 (MW)").fill("15");
  await editor
    .getByLabel("Motivo del cambio")
    .fill("Preparar ejecución eléctrica");
  await editor.getByLabel("Confirmo el alcance de esta edición").check();
  await editor
    .getByRole("button", { name: "Guardar entrada", exact: true })
    .click();
  await expect(editor).not.toBeVisible();
  await expect(
    demand.getByRole("cell", { name: "15", exact: true }),
  ).toBeVisible();
  await page.getByText("Preparar ejecución eléctrica", { exact: true }).click();
  await page.getByLabel("Inicio de ejecución").fill("2026-10-20T00:00");
  await page
    .getByLabel("Fin de ejecución (exclusivo)")
    .fill("2026-10-20T02:00");
  await page
    .getByRole("button", { name: "Validar preparación", exact: true })
    .click();
  await expect(page.getByText(/Preparación válida · 2 intervalos/)).toBeVisible(
    { timeout: 60000 },
  );
  await page.screenshot({
    path: testInfo.outputPath("mesa-ejecucion-1440.png"),
  });
  const accepted = page.waitForResponse(
    (response) =>
      response.url().endsWith("/mesa/execution/runs") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Ejecutar caso eléctrico", exact: true })
    .dblclick();
  const run = await (await accepted).json();
  await expect(
    page.getByText(`Ejecución #${run.id}`, { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText(`Ejecución #${run.id}`, { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Ver resultados en la mesa",
      exact: true,
    }),
  ).toBeVisible({ timeout: 120000 });
  const runs = await (
    await page.request.get(`/api/scenarios/${fixture.scenario.id}/runs`)
  ).json();
  expect(runs.runs.map((item: { id: number }) => item.id)).toEqual([run.id]);
  await page
    .getByRole("button", { name: "Ver resultados en la mesa", exact: true })
    .click();
  await expect(page.getByLabel("Resultados de ejecución")).toHaveValue(
    String(run.id),
  );
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await expect(demand).toContainText("Después: 15 MW");
  await expect(
    page.getByRole("region", { name: "BESS · Descarga BESS", exact: true }),
  ).toContainText("Sin referencia previa");
  await page.getByText("Historial de ejecuciones", { exact: true }).click();
  const historical = page
    .getByRole("region", { name: "Historial de ejecuciones" })
    .getByRole("row")
    .filter({ hasText: `Run #${run.id} ·` });
  await expect(historical).toContainText("Completada");
  await historical
    .getByRole("button", { name: "Consultar", exact: true })
    .click();
  await page.reload();
  await expect(page.locator(".mesa-panel")).toHaveCount(4);
  await expect(demand).toContainText("Después: 15 MW");
  await expect(demand).toContainText(`Snapshot #${run.scenario_version_id}`);
  await demand.getByRole("button", { name: "Tabla", exact: true }).click();
  for (const panel of await page.locator(".mesa-panel").all()) {
    const box = (await panel.boundingBox())!;
    expect(box.y + box.height).toBeLessThanOrEqual(900);
    const origin = (await panel
      .locator(".mesa-comparison-origins")
      .boundingBox())!;
    expect(origin.y + origin.height).toBeLessThanOrEqual(
      box.y + box.height - 4,
    );
  }
  await page.screenshot({
    path: testInfo.outputPath("mesa-recorrido-completo-1440.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-ejecucion-390.png"),
    fullPage: true,
  });
});

test("La mesa conserva el run durante una desconexión y explica un fallo sin perder entradas", async ({
  page,
}) => {
  let status = "queued";
  let disconnected = false;
  let launches = 0;
  await page.route("**/mesa/execution?*", (route) =>
    disconnected
      ? route.abort()
      : route.fulfill({
          json: {
            run: {
              id: 901,
              scenario_version_id: 902,
              status,
              created_at: "2026-10-20T03:00:00Z",
              error_message: status === "failed" ? "Caso infactible" : "",
              materialized_lineage: {
                mesa_execution: {
                  range_start: "2026-10-20T00:00:00",
                  range_end: "2026-10-20T02:00:00",
                  timezone: "America/Santiago",
                  resolution_hours: 1,
                },
              },
              progress: {
                stage: status,
                elapsed_seconds: 1,
                gap_percent: null,
                events: [],
                solver_log: "",
              },
            },
          },
        }),
  );
  await page.route("**/mesa/execution/runs", (route) => {
    launches++;
    return route.abort();
  });
  await openPersonalMesa(page, "Avance y desconexión", false, true);
  await expect(page.getByText("Ejecución #901", { exact: true })).toBeVisible();
  await page
    .getByText("Ver avance y log de ejecución", { exact: true })
    .click();
  await expect(
    page.getByText("Esperando turno para iniciar", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/Período del run:.*2026-10-20T00:00:00.*America\/Santiago/),
  ).toBeVisible();
  status = "running";
  await expect(
    page.getByText("Ejecución en curso", { exact: true }),
  ).toBeVisible();
  disconnected = true;
  await expect(page.getByText(/No se pudo actualizar el avance/)).toBeVisible();
  await expect(page.getByText("Ejecución #901", { exact: true })).toBeVisible();
  disconnected = false;
  await page.getByRole("button", { name: "Reintentar conexión" }).click();
  await page.reload();
  await expect(page.getByText("Ejecución #901", { exact: true })).toBeVisible();
  status = "failed";
  await expect(
    page.getByText(/La ejecución falló: Caso infactible/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Ver resultados en la mesa" }),
  ).toHaveCount(0);
  const panel = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await panel.getByRole("button", { name: "Tabla", exact: true }).click();
  await expect(
    panel.getByRole("cell", { name: "12", exact: true }),
  ).toBeVisible();
  expect(launches).toBe(0);
});

test("Cambiar fechas o guardar una entrada exige volver a validar la ejecución", async ({
  page,
}) => {
  await page.route("**/mesa/execution/preview", async (route) => {
    const body = route.request().postDataJSON();
    await route.fulfill({
      json: {
        ...body,
        preparation_hash: "a".repeat(64),
        period_count: 2,
        model_contract: "bess_system_dispatch.v2",
        series_bindings: [],
      },
    });
  });
  await openPersonalMesa(page, "Revalidar ejecución", false, true);
  await page.getByText("Preparar ejecución eléctrica", { exact: true }).click();
  const validate = page.getByRole("button", {
    name: "Validar preparación",
    exact: true,
  });
  const execute = page.getByRole("button", {
    name: "Ejecutar caso eléctrico",
    exact: true,
  });
  await validate.click();
  await expect(execute).toBeEnabled();
  await page
    .getByLabel("Fin de ejecución (exclusivo)")
    .fill("2026-10-20T01:00");
  await expect(execute).toBeDisabled();
  await page
    .getByLabel("Fin de ejecución (exclusivo)")
    .fill("2026-10-20T02:00");
  await validate.click();
  await expect(execute).toBeEnabled();
  const demand = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await demand.getByRole("button", { name: "Tabla", exact: true }).click();
  await demand
    .getByRole("button", { name: "Editar entrada", exact: true })
    .click();
  const editor = page.getByRole("dialog", {
    name: "Editar entrada · Demanda medida",
  });
  await editor.getByLabel("Valor del intervalo 2 (MW)").fill("15");
  await expect(execute).toBeDisabled();
  await editor.getByLabel("Motivo del cambio").fill("Corrección para ejecutar");
  await editor.getByLabel("Confirmo el alcance de esta edición").check();
  await editor
    .getByRole("button", { name: "Guardar entrada", exact: true })
    .click();
  await expect(editor).not.toBeVisible();
  await expect(
    demand.getByRole("cell", { name: "15", exact: true }),
  ).toBeVisible();
  await expect(execute).toBeDisabled();
  await expect(
    page.getByText(
      "La entrada cambió. Preparación pendiente de revalidación.",
      { exact: true },
    ),
  ).toBeVisible();
});

test("Edición de demanda guarda una revisión y la recupera en tabla y gráfico", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openPersonalMesa(page, "Editar demanda");
  const panel = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await panel.getByRole("button", { name: "Tabla", exact: true }).click();
  await panel
    .getByRole("button", { name: "Editar entrada", exact: true })
    .click();
  const editor = page.getByRole("dialog", {
    name: "Editar entrada · Demanda medida",
  });
  await expect(editor).toContainText("copia local");
  await editor.getByLabel("Valor del intervalo 2 (MW)").fill("15");
  await expect(editor).toContainText("Cambios pendientes");
  await editor.getByLabel("Motivo del cambio").fill("Corrección de medición");
  await editor.getByLabel("Confirmo el alcance de esta edición").check();
  await page.screenshot({ path: testInfo.outputPath("mesa-edicion-1440.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    editor.getByLabel("Valor del intervalo 2 (MW)"),
  ).toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("mesa-edicion-390.png"),
    fullPage: true,
  });
  await editor
    .getByRole("button", { name: "Guardar entrada", exact: true })
    .click();
  await expect(editor).not.toBeVisible();
  await expect(
    page.getByText(/Entrada guardada.*pendiente de revalidación/),
  ).toBeVisible();
  await expect(
    panel.getByRole("cell", { name: "15", exact: true }),
  ).toBeVisible();
  await page.reload();
  await panel.getByRole("button", { name: "Tabla", exact: true }).click();
  await expect(
    panel.getByRole("cell", { name: "15", exact: true }),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Gráfico", exact: true }).click();
  await expect(panel.getByRole("img")).toContainText("15 MW");
});

test("Edición pendiente advierte al cerrar y descartar no publica", async ({
  page,
}) => {
  const fixture = await openPersonalMesa(page, "Descartar demanda");
  const panel = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await panel.getByRole("button", { name: "Tabla", exact: true }).click();
  await panel
    .getByRole("button", { name: "Editar entrada", exact: true })
    .click();
  const editor = page.getByRole("dialog", {
    name: "Editar entrada · Demanda medida",
  });
  await editor.getByLabel("Valor del intervalo 2 (MW)").fill("99");
  await page.keyboard.press("Escape");
  await expect(editor.getByText("Hay cambios sin guardar.")).toBeVisible();
  await editor.getByRole("button", { name: "Seguir editando" }).click();
  await expect(editor.getByLabel("Valor del intervalo 2 (MW)")).toHaveValue(
    "99",
  );
  await page.keyboard.press("Escape");
  await editor
    .getByRole("button", { name: "Descartar cambios", exact: true })
    .click();
  await expect(editor).not.toBeVisible();
  await expect(
    panel.getByRole("button", { name: "Editar entrada" }),
  ).toBeFocused();
  const response = await page.request.get(
    `/api/scenarios/${fixture.scenario.id}/mesa?case_id=${fixture.case.id}&variant_id=${fixture.variant.id}`,
  );
  const demand = (await response.json()).components.find(
    (c: { entity_id: string }) => c.entity_id === "load_north",
  ).series;
  expect(demand.points.map((p: { value: number }) => p.value)).toEqual([
    10, 12,
  ]);
  expect(demand.revision_id).toBe(fixture.receipt.revision_id);
});

test("Conflicto de entrada conserva el borrador y permite comparar la revisión actual", async ({
  page,
}) => {
  const fixture = await openPersonalMesa(page, "Conflicto demanda");
  const panel = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await panel.getByRole("button", { name: "Tabla", exact: true }).click();
  await panel
    .getByRole("button", { name: "Editar entrada", exact: true })
    .click();
  const editor = page.getByRole("dialog", {
    name: "Editar entrada · Demanda medida",
  });
  await editor.getByLabel("Valor del intervalo 2 (MW)").fill("99");
  const target = `/api/scenarios/${fixture.scenario.id}/mesa/inputs/${fixture.object.id}/load_demand_mw`;
  const edit = await (
    await page.request.get(
      `${target}?case_id=${fixture.case.id}&variant_id=${fixture.variant.id}`,
    )
  ).json();
  const csrf = await (await page.request.get("/api/auth/csrf")).json();
  const saved = await page.request.post(`${target}/revisions`, {
    headers: { "X-CSRF-Token": csrf.csrf_token },
    data: {
      case_id: fixture.case.id,
      variant_id: fixture.variant.id,
      expected: edit.expected,
      unit: "MW",
      points: [edit.series.points[0], { ...edit.series.points[1], value: 15 }],
      confirm: true,
      reason: "Otra sesión corrigió la entrada",
    },
  });
  expect(saved.status()).toBe(201);
  await editor.getByLabel("Motivo del cambio").fill("Mi borrador");
  await editor.getByLabel("Confirmo el alcance de esta edición").check();
  await editor
    .getByRole("button", { name: "Guardar entrada", exact: true })
    .click();
  await expect(editor.getByRole("alert")).toContainText("La entrada cambió");
  await expect(editor.getByLabel("Valor del intervalo 2 (MW)")).toHaveValue(
    "99",
  );
  await editor
    .getByRole("button", { name: "Recargar y comparar", exact: true })
    .click();
  const comparison = editor.getByRole("table", {
    name: "Comparación de revisiones",
  });
  await expect(comparison.getByRole("row").last()).toContainText("129915");
  await editor
    .getByRole("button", { name: "Usar revisión actual", exact: true })
    .click();
  await expect(editor.getByLabel("Valor del intervalo 2 (MW)")).toHaveValue(
    "15",
  );
  await expect(
    editor.getByRole("button", { name: "Guardar entrada", exact: true }),
  ).toBeDisabled();
});

test("Edición valida números y protege la navegación a otro contexto", async ({
  page,
}) => {
  const fixture = await openPersonalMesa(page, "Navegación de edición");
  await page
    .getByRole("link", { name: fixture.scenario.name, exact: true })
    .click();
  await page.getByRole("link", { name: "Abrir mesa de optimización" }).click();
  const mesaUrl = page.url();
  const panel = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await panel.getByRole("button", { name: "Tabla", exact: true }).click();
  await panel
    .getByRole("button", { name: "Editar entrada", exact: true })
    .click();
  const editor = page.getByRole("dialog", {
    name: "Editar entrada · Demanda medida",
  });
  const value = editor.getByLabel("Valor del intervalo 2 (MW)");
  await value.fill("texto");
  await expect(editor.getByRole("alert")).toContainText("número finito");
  await expect(
    editor.getByRole("button", { name: "Guardar entrada" }),
  ).toBeDisabled();
  await value.fill("-1");
  await editor.getByLabel("Motivo del cambio").fill("Revisar valor");
  await editor.getByLabel("Confirmo el alcance de esta edición").check();
  await editor.getByRole("button", { name: "Guardar entrada" }).click();
  await expect(editor.getByRole("alert")).toContainText(
    "Valor inválido en intervalo 2",
  );
  await value.fill("15");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.goBack();
  await expect(editor.getByText("Hay cambios sin guardar.")).toBeVisible();
  await expect(page).toHaveURL(mesaUrl);
  await editor.getByRole("button", { name: "Seguir editando" }).click();
  await expect(value).toHaveValue("15");
  await page.goBack();
  await editor.getByRole("button", { name: "Descartar cambios" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/scenarios/${fixture.scenario.id}\\?section=data`),
  );
});

test("Una pérdida de conexión conserva la edición y permite reintentar", async ({
  page,
}) => {
  await openPersonalMesa(page, "Edición sin conexión");
  const panel = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await panel.getByRole("button", { name: "Tabla", exact: true }).click();
  await panel
    .getByRole("button", { name: "Editar entrada", exact: true })
    .click();
  const editor = page.getByRole("dialog", {
    name: "Editar entrada · Demanda medida",
  });
  await editor.getByLabel("Valor del intervalo 2 (MW)").fill("15");
  await editor.getByLabel("Motivo del cambio").fill("Corrección sin conexión");
  await editor.getByLabel("Confirmo el alcance de esta edición").check();
  await page.context().setOffline(true);
  await editor
    .getByRole("button", { name: "Guardar entrada", exact: true })
    .click();
  await expect(editor.getByRole("alert")).toBeVisible();
  await page.context().setOffline(false);
  await editor
    .getByRole("button", { name: "Guardar entrada", exact: true })
    .click();
  await expect(editor).not.toBeVisible();
  await expect(
    panel.getByRole("cell", { name: "15", exact: true }),
  ).toBeVisible();
});

test("Hidráulica conserva centrales homónimas y consulta embalse con escalas separadas", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await openPersonalMesa(
    page,
    "Red hidráulica",
    false,
    false,
    true,
    true,
  );
  const reservoir = page.getByRole("region", {
    name: "Embalse · Embalse Alto",
    exact: true,
  });
  await expect(
    reservoir.getByRole("img", { name: "Aporte natural · m3/s" }),
  ).toContainText("2 m3/s");
  await reservoir.getByText("Parámetros actuales", { exact: true }).click();
  await expect(
    reservoir.getByRole("row").filter({ hasText: "Volumen inicial" }),
  ).toHaveText("Volumen inicial10hm3");
  await reservoir.getByText("Parámetros actuales", { exact: true }).click();
  for (const [key, title] of [
    ["plant_1", "Central uno"],
    ["plant_2", "Central dos"],
  ]) {
    await page
      .getByRole("button", { name: "Agregar vista", exact: true })
      .click();
    const dialog = page.getByRole("dialog", { name: "Configurar vista" });
    const label = await dialog
      .getByRole("option")
      .filter({ hasText: new RegExp(` · ${key} · #`) })
      .textContent();
    await dialog.getByLabel("Componente").selectOption({ label: label! });
    await dialog.getByLabel("Título").fill(title);
    await expect(
      dialog.getByRole("checkbox", { name: /Aporte natural/ }),
    ).toHaveCount(0);
    await dialog.getByRole("button", { name: "Aplicar" }).click();
  }
  const first = page.getByRole("region", {
    name: "Central · Central uno",
    exact: true,
  });
  const second = page.getByRole("region", {
    name: "Central · Central dos",
    exact: true,
  });
  await expect(first).toContainText("Sin resultado disponible");
  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  await expect(
    first.getByRole("img", { name: "Potencia hidráulica · MW" }),
  ).toContainText("3 MW");
  await expect(
    second.getByRole("img", { name: "Potencia hidráulica · MW" }),
  ).toContainText("9 MW");
  await first.getByRole("button", { name: "Tabla", exact: true }).click();
  await expect(
    first.getByRole("cell", { name: "6", exact: true }),
  ).toBeVisible();
  await reservoir.getByRole("button", { name: /Configurar/ }).click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  await dialog.getByRole("checkbox", { name: /Volumen almacenado/ }).check();
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  await expect(
    reservoir.getByRole("img", { name: "Volumen almacenado · hm3" }),
  ).toContainText("9.8 hm3");
  await expect(reservoir.getByRole("img")).toHaveCount(2);
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    first.getByRole("cell", { name: "6", exact: true }),
  ).toBeVisible();
  await expect(reservoir).toContainText(`Run #${fixture.run.id}`);
  await expect(second.locator(".mesa-panel-footer")).toBeInViewport();
  for (const bottom of await page
    .locator(".mesa-panel")
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getBoundingClientRect().bottom),
    ))
    expect(bottom).toBeLessThanOrEqual(900);
  await page.screenshot({
    path: testInfo.outputPath("mesa-hidraulica-1440.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("mesa-hidraulica-390.png"),
    fullPage: true,
  });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("Hidráulica muestra pertenencia de unidades y conexiones de tramos en sus vistas", async ({
  page,
}) => {
  await openPersonalMesa(
    page,
    "Pertenencia hidráulica",
    false,
    false,
    false,
    true,
  );
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  let dialog = page.getByRole("dialog", { name: "Configurar vista" });
  let option = await dialog
    .getByRole("option")
    .filter({ hasText: "unit_1" })
    .textContent();
  await dialog.getByLabel("Componente").selectOption({ label: option! });
  await dialog.getByLabel("Título").fill("Unidad seleccionada");
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  const unit = page.getByRole("region", {
    name: "Unidad · Unidad seleccionada",
    exact: true,
  });
  await expect(unit).toContainText("Central: plant_1");
  await expect(unit).toContainText("Conexión: intake → outlet");
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Configurar vista" });
  option = await dialog
    .getByRole("option")
    .filter({ hasText: "reach" })
    .textContent();
  await dialog.getByLabel("Componente").selectOption({ label: option! });
  await dialog.getByLabel("Título").fill("Canal seleccionado");
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  await expect(
    page.getByRole("region", {
      name: "Tramo · Canal seleccionado",
      exact: true,
    }),
  ).toContainText("Conexión: reservoir → intake");
});

test("BESS y renovables separan parámetros, entradas y salidas ausentes", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openPersonalMesa(page, "Familias eléctricas", false, true);
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  let dialog = page.getByRole("dialog", { name: "Configurar vista" });
  const batteryOption = await dialog
    .getByRole("option")
    .filter({ hasText: "battery_1" })
    .textContent();
  await dialog.getByLabel("Componente").selectOption({ label: batteryOption! });
  await dialog.getByLabel("Título").fill("BESS Norte");
  await expect(
    dialog.getByRole("checkbox", { name: /Disponibilidad solar/ }),
  ).toHaveCount(0);
  await dialog.getByRole("checkbox", { name: /Carga BESS/ }).uncheck();
  await dialog.getByRole("checkbox", { name: /Descarga BESS/ }).check();
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  const battery = page.getByRole("region", {
    name: "BESS · BESS Norte",
    exact: true,
  });
  await expect(battery).toContainText("Salida · Solo lectura");
  await expect(battery).toContainText("Sin resultado disponible");
  await expect(battery.getByRole("img")).toHaveCount(0);
  await battery.getByText("Parámetros actuales", { exact: true }).click();
  await expect(
    battery.getByRole("row").filter({ hasText: "Energía inicial" }),
  ).toHaveText(/Energía inicial4MWh/);
  await battery.getByText("Parámetros actuales", { exact: true }).click();
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Configurar vista" });
  const solarOption = await dialog
    .getByRole("option")
    .filter({ hasText: "solar_north" })
    .textContent();
  await dialog.getByLabel("Componente").selectOption({ label: solarOption! });
  await dialog.getByLabel("Título").fill("Solar Norte");
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  const solar = page.getByRole("region", {
    name: "Renovable · Solar Norte",
    exact: true,
  });
  await expect(
    solar.getByRole("img", { name: "Disponibilidad solar · MW" }),
  ).toContainText("3 MW");
  await solar.getByRole("button", { name: "Tabla", exact: true }).click();
  await expect(solar.getByRole("table").getByRole("row")).toHaveCount(3);
  await expect(
    solar.getByRole("cell", { name: "5", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(battery).toContainText("Sin resultado disponible");
  await expect(
    solar.getByRole("cell", { name: "5", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("mesa-electricas-1440.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("mesa-electricas-390.png"),
    fullPage: true,
  });
});

test("seleccionar un run muestra descarga y energía por activo y conserva la consulta al recargar", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await openPersonalMesa(
    page,
    "Resultados eléctricos",
    false,
    true,
    true,
  );
  await page
    .getByRole("button", { name: "Configurar Demanda Norte", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  const option = await dialog
    .getByRole("option")
    .filter({ hasText: "battery_1" })
    .textContent();
  await dialog.getByLabel("Componente").selectOption({ label: option! });
  await dialog.getByLabel("Título").fill("BESS con resultados");
  await dialog.getByRole("checkbox", { name: /Carga BESS/ }).uncheck();
  await dialog.getByRole("checkbox", { name: /Descarga BESS/ }).check();
  await dialog.getByRole("checkbox", { name: /Energía almacenada/ }).check();
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  const battery = page.getByRole("region", {
    name: "BESS · BESS con resultados",
    exact: true,
  });
  await expect(
    battery.getByRole("img", { name: "Descarga BESS · MW" }),
  ).toContainText("2 MW");
  await expect(
    battery.getByRole("img", { name: "Energía almacenada · MWh" }),
  ).toContainText("2.95 MWh");
  await expect(battery).toContainText(
    `Run #${fixture.run.id} · Snapshot #${fixture.run.scenario_version_id}`,
  );
  await battery.getByRole("button", { name: "Tabla", exact: true }).click();
  await expect(
    battery
      .getByRole("table", { name: "Descarga BESS · MW" })
      .getByRole("cell", { name: "2", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Resultados de ejecución")).toHaveValue(
    String(fixture.run.id),
  );
  await expect(
    battery.getByRole("table", { name: "Energía almacenada · MWh" }),
  ).toContainText("2.95");
  await page.screenshot({
    path: testInfo.outputPath("mesa-resultados-1440.png"),
  });
  await page.getByLabel("Resultados de ejecución").selectOption("");
  await expect(
    battery.getByRole("table", { name: "Descarga BESS · MW" }),
  ).toHaveCount(0);
  await expect(battery).toContainText("Sin resultado disponible");
});

test("cambiar de run conserva una vista que todavía no se ha guardado", async ({
  page,
}) => {
  const fixture = await openPersonalMesa(
    page,
    "Vista local y resultados",
    false,
    true,
    true,
  );
  await page
    .getByRole("button", { name: "Configurar Demanda Norte", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  await dialog.getByLabel("Título").fill("Mi vista local");
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  await expect(
    page.getByRole("heading", { name: "Mi vista local", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Cambios sin guardar", { exact: true }),
  ).toBeVisible();
});

test("cuatro vistas conservan títulos, series y modos al reducir y recargar", async ({
  page,
}) => {
  await openPersonalMesa(page, "Persistencia de paneles");
  for (const title of ["Detalle", "Operación", "Auditoría"]) {
    await page
      .getByRole("button", { name: "Agregar vista", exact: true })
      .click();
    const dialog = page.getByRole("dialog", { name: "Configurar vista" });
    await dialog.getByLabel("Título").fill(title);
    if (title === "Auditoría")
      await dialog.getByLabel("Presentación").selectOption("table");
    await dialog.getByRole("button", { name: "Aplicar" }).click();
  }
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.getByLabel("Distribución de las vistas").selectOption("1x1");
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator(".mesa-panel")).toHaveCount(1);
  await expect(
    page.getByText("3 vistas ocultas; se conservan al ampliar.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByLabel("Distribución de las vistas").selectOption("2x2");
  await expect(page.locator(".mesa-panel")).toHaveCount(4);
  await expect(
    page.getByRole("heading", { name: "Detalle", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Operación", exact: true }),
  ).toBeVisible();
  const audit = page.getByRole("region", {
    name: "Demanda · Auditoría",
    exact: true,
  });
  await expect(
    audit.getByRole("table", { name: "Demanda medida · MW" }),
  ).toContainText("12");
});

test("dos pestañas personalizadas conservan su orden y distribución usando teclado", async ({
  page,
}) => {
  await openPersonalMesa(page, "Pestañas personales");
  await page
    .getByRole("button", { name: "Agregar pestaña", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  let dialog = page.getByRole("dialog", { name: "Configurar pestaña" });
  await dialog.getByLabel("Nombre de pestaña").fill("Demanda diaria");
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  await expect(
    page.getByRole("tab", { name: "Demanda diaria" }),
  ).toHaveAttribute("aria-selected", "true");
  await page.getByLabel("Distribución de las vistas").selectOption("1x2");
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Configurar vista" });
  await dialog.getByLabel("Título").fill("Detalle diario");
  await dialog.getByLabel("Posición de vista").selectOption("0");
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  await expect(page.locator(".mesa-panel h2")).toHaveText([
    "Detalle diario",
    "Demanda Norte",
  ]);
  await page
    .getByRole("button", { name: "Configurar pestaña", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Configurar pestaña" });
  await dialog.getByLabel("Posición de pestaña").selectOption("0");
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("tab")).toHaveText([
    "Demanda diaria",
    "Vista general",
  ]);
  await expect(page.getByLabel("Distribución de las vistas")).toHaveValue(
    "1x2",
  );
  await page.getByRole("tab", { name: "Demanda diaria" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Vista general" })).toBeFocused();
  await expect(page.getByLabel("Distribución de las vistas")).toHaveValue(
    "2x2",
  );
  await expect(page.locator(".mesa-panel")).toHaveCount(1);
  await page.keyboard.press("Home");
  await page
    .getByRole("button", { name: "Configurar Demanda Norte", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Quitar vista", exact: true })
    .click();
  await expect(page.locator(".mesa-panel h2")).toHaveText(["Detalle diario"]);
  await expect(
    page.getByRole("button", { name: "Agregar vista", exact: true }),
  ).toBeFocused();
  const trigger = page.getByRole("button", {
    name: "Configurar Detalle diario",
    exact: true,
  });
  await trigger.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator(".mesa-panel h2")).toHaveText(["Detalle diario"]);
});

test("un conflicto conserva la edición local y permite cargar la mesa guardada", async ({
  page,
  context,
}) => {
  await openPersonalMesa(page, "Conflicto recuperable");
  await expect(
    page.getByRole("button", { name: "Guardar mesa", exact: true }),
  ).toBeVisible();
  const other = await context.newPage();
  await other.goto(page.url());
  await expect(other.getByLabel("Distribución de las vistas")).toHaveValue(
    "2x2",
  );
  await page.getByLabel("Distribución de las vistas").selectOption("1x2");
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await other.getByLabel("Distribución de las vistas").selectOption("1x1");
  await other
    .getByRole("button", { name: "Guardar mesa", exact: true })
    .click();
  await expect(other.getByRole("alert")).toContainText("otra sesión");
  await expect(other.getByLabel("Distribución de las vistas")).toHaveValue(
    "1x1",
  );
  await other
    .getByRole("button", { name: "Cargar mesa guardada", exact: true })
    .click();
  await expect(other.getByLabel("Distribución de las vistas")).toHaveValue(
    "1x2",
  );
  await other.getByLabel("Distribución de las vistas").selectOption("2x3");
  await other
    .getByRole("button", { name: "Guardar mesa", exact: true })
    .click();
  await expect(other.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Distribución de las vistas")).toHaveValue(
    "2x3",
  );
  await other.close();
});

test("la matriz 2x2 cabe a 1440x900 y se adapta a 390 sin desbordar", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await openPersonalMesa(page, "Matriz de vistas");
  const path = `/api/scenarios/${fixture.scenario.id}/mesa/preferences?case_id=${fixture.case.id}`;
  const prefs = await (await page.request.get(path)).json();
  prefs.configuration.tabs[0].panels = [
    "Consumo",
    "Seguimiento",
    "Operación",
    "Detalle horario",
  ].map((title, i) => ({
    id: `view-${i}`,
    title,
    mode: i === 3 ? "table" : "chart",
    component: {
      linkable_object_id: fixture.object.id,
      entity_type: "component:load",
      entity_id: "load_north",
    },
    series_keys: ["load_demand_mw"],
  }));
  const csrf = await (await page.request.get("/api/auth/csrf")).json();
  expect(
    (
      await page.request.put(path, {
        data: {
          expected_revision: prefs.revision,
          configuration: prefs.configuration,
        },
        headers: { "X-CSRF-Token": csrf.csrf_token },
      })
    ).ok(),
  ).toBeTruthy();
  await page.reload();
  await expect(page.locator(".mesa-panel")).toHaveCount(4);
  const boxes = await page.locator(".mesa-panel").evaluateAll((nodes) =>
    nodes.map((node) => {
      const r = node.getBoundingClientRect();
      return { x: r.x, y: r.y, right: r.right, bottom: r.bottom };
    }),
  );
  for (const box of boxes) {
    expect(box.bottom).toBeLessThanOrEqual(900);
    expect(box.right).toBeLessThanOrEqual(1440);
  }
  expect(boxes[0].y).toBe(boxes[1].y);
  expect(boxes[2].y).toBe(boxes[3].y);
  expect(boxes[0].right).toBeLessThan(boxes[1].x);
  expect(boxes[0].bottom).toBeLessThan(boxes[2].y);
  const accessibility = await new AxeBuilder({ page })
    .include(".mesa-view")
    .analyze();
  expect(
    accessibility.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    ),
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("mesa-paneles-1440.png") });
  await page
    .getByRole("button", { name: "Configurar Consumo", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByLabel("Título")).toBeFocused();
  const dialogAxe = await new AxeBuilder({ page })
    .include(".mesa-dialog")
    .analyze();
  expect(
    dialogAxe.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    ),
  ).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-configurar-1440.png"),
  });
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: testInfo.outputPath("mesa-paneles-390.png"),
    fullPage: true,
  });
});

test("series de unidades distintas conservan selección y escalas separadas", async ({
  page,
}) => {
  await page.route("**/api/scenarios/*/mesa?*", async (route) => {
    const body = await (await route.fetch()).json();
    const component = body.components[0];
    component.additional_series = [
      {
        ...component.series,
        signal_key: "supply_price",
        name: "Precio de suministro",
        unit: "USD/MWh",
        points: [
          {
            start: "2026-10-20T00:00:00-03:00",
            end: "2026-10-20T01:00:00-03:00",
            value: 40,
          },
          {
            start: "2026-10-20T01:00:00-03:00",
            end: "2026-10-20T02:00:00-03:00",
            value: 70,
          },
        ],
      },
    ];
    await route.fulfill({ json: body });
  });
  await openPersonalMesa(page, "Unidades separadas");
  await page
    .getByRole("button", { name: "Configurar Demanda Norte", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("checkbox", { name: "Precio de suministro · USD/MWh" })
    .check();
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  await expect(
    page.getByRole("img", { name: "Demanda medida · MW", exact: true }),
  ).toContainText("10 MW");
  await expect(
    page.getByRole("img", {
      name: "Precio de suministro · USD/MWh",
      exact: true,
    }),
  ).toContainText("70 USD/MWh");
  await page.getByRole("button", { name: "Tabla", exact: true }).click();
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("table", { name: "Demanda medida · MW" }),
  ).toContainText("12");
  await expect(
    page.getByRole("table", { name: "Precio de suministro · USD/MWh" }),
  ).toContainText("70");
  await page
    .getByRole("button", { name: "Configurar Demanda Norte", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("checkbox", { name: "Demanda medida · MW", exact: true })
    .uncheck();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Aplicar" })
    .click();
  await expect(
    page.getByRole("table", { name: "Demanda medida · MW" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("table", { name: "Precio de suministro · USD/MWh" }),
  ).toBeVisible();
});

test("un componente retirado conserva identidad y se reconfigura sin reasignarse por nombre", async ({
  page,
}) => {
  const fixture = await openPersonalMesa(page, "Componente retirado", true);
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  const draftPath = `/api/scenarios/${fixture.scenario.id}/draft`;
  const { draft } = await (await page.request.get(draftPath)).json();
  draft.document.assets.find(
    (asset: { type: string }) => asset.type === "load",
  ).id = "load_replacement";
  const csrf = await (await page.request.get("/api/auth/csrf")).json();
  expect(
    (
      await page.request.put(draftPath, {
        data: { document: draft.document },
        headers: { "X-CSRF-Token": csrf.csrf_token },
      })
    ).ok(),
  ).toBeTruthy();
  await page.reload();
  await expect(page.getByRole("status")).toContainText(
    `No disponible · load_north · Objeto ${fixture.object.id}`,
  );
  await expect(
    page.getByRole("img", { name: "Demanda medida · MW" }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Configurar Demanda Norte", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("combobox", { name: "Componente", exact: true }),
  ).toHaveValue("-1");
  await expect(
    dialog.getByRole("option", {
      name: `Demanda Norte · load_replacement · #${fixture.replacement.id}`,
    }),
  ).toHaveCount(1);
  await dialog
    .getByRole("combobox", { name: "Componente", exact: true })
    .selectOption("0");
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("status")).toHaveText(
    "Sin fuente de demanda vinculada.",
  );
  await expect(page.locator(".mesa-panel")).toContainText("load_replacement");
});

test("los errores de configuración permiten reintentar sin perder la edición", async ({
  page,
}) => {
  let failRead = true;
  let failSave = true;
  await page.route("**/api/scenarios/*/mesa/preferences?*", async (route) => {
    if (
      (route.request().method() === "GET" && failRead) ||
      (route.request().method() === "PUT" && failSave)
    ) {
      await route.fulfill({
        status: 503,
        json: { detail: "Conexión interrumpida" },
      });
    } else await route.continue();
  });
  await openPersonalMesa(page, "Errores recuperables");
  await expect(page.getByRole("alert")).toContainText(
    "No se pudo cargar la configuración",
  );
  await expect(page.locator(".mesa-panel")).toHaveCount(0);
  failRead = false;
  await page
    .getByRole("button", { name: "Reintentar configuración", exact: true })
    .click();
  await page.getByRole("button", { name: "Tabla", exact: true }).click();
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Conexión interrumpida");
  await expect(
    page.getByRole("table", { name: "Demanda medida · MW" }),
  ).toContainText("12");
  failSave = false;
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("table", { name: "Demanda medida · MW" }),
  ).toContainText("12");
});

test("mesa de optimización: demanda real en gráfico, tabla y recarga", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await (
    await page.request.get("/api/auth/mesa-fixture")
  ).json();
  const csrf = await (await page.request.get("/api/auth/csrf")).json();
  const login = await page.request.post("/api/auth/login", {
    data: {
      email: "mesa@example.local",
      password: "mesa test pass",
      next: "/react/projects",
    },
    headers: { "X-CSRF-Token": csrf.csrf_token },
  });
  expect(login.ok()).toBeTruthy();
  await page.goto(
    `/react/scenarios/${fixture.scenario.id}?section=data&variant=${fixture.default_variant.id}`,
  );
  await page
    .getByLabel("Variante activa", { exact: true })
    .selectOption(String(fixture.variant.id));
  await page.getByRole("link", { name: "Abrir mesa de optimización" }).click();
  await expect(page).toHaveURL(
    new RegExp(
      `/mesa\\?case=${fixture.case.id}&variant=${fixture.variant.id}$`,
    ),
  );
  await expect(
    page.getByRole("heading", { name: "Mesa de optimización", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Proyecto Caso de demanda", { exact: true }),
  ).toBeVisible();
  const chart = page.getByRole("img", { name: "Demanda medida · MW" });
  await expect(chart).toBeVisible();
  await expect(chart).toContainText(
    "2026-10-20T00:00:00-03:00 → 2026-10-20T01:00:00-03:00: 10 MW",
  );
  await expect(chart).toContainText(
    "2026-10-20T01:00:00-03:00 → 2026-10-20T02:00:00-03:00: 12 MW",
  );
  const panel = await page
    .getByRole("region", { name: "Demanda · Demanda Norte", exact: true })
    .boundingBox();
  expect(panel).not.toBeNull();
  expect(panel!.y + panel!.height).toBeLessThanOrEqual(900);
  await page.screenshot({ path: testInfo.outputPath("mesa-demanda-1440.png") });
  const accessibility = await new AxeBuilder({ page })
    .include(".mesa-view")
    .analyze();
  expect(
    accessibility.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    ),
  ).toEqual([]);
  await page.getByRole("button", { name: "Tabla", exact: true }).focus();
  await page.keyboard.press("Enter");
  const table = page.getByRole("table", { name: "Demanda medida · MW" });
  await expect(
    table.getByRole("cell", { name: "10", exact: true }),
  ).toBeVisible();
  await expect(
    table.getByRole("cell", { name: "12", exact: true }),
  ).toBeVisible();
  await expect(
    table.getByRole("cell", { name: "2026-10-20T00:00:00-03:00", exact: true }),
  ).toBeVisible();
  await expect(table.getByRole("textbox")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath("mesa-tabla-390.png") });
  await page.reload();
  await expect(chart).toContainText("12 MW");
  await expect(
    page.getByText(
      `Caso #${fixture.case.id} · Variante Demanda alternativa · bess_system_dispatch.v2`,
      {
        exact: true,
      },
    ),
  ).toBeVisible();
});

test("mesa de optimización: carga, error con reintento y caso vacío", async ({
  page,
}) => {
  const fixture = await (
    await page.request.get("/api/auth/mesa-fixture")
  ).json();
  const csrf = await (await page.request.get("/api/auth/csrf")).json();
  await page.request.post("/api/auth/login", {
    data: {
      email: "mesa@example.local",
      password: "mesa test pass",
      next: "/react/projects",
    },
    headers: { "X-CSRF-Token": csrf.csrf_token },
  });
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  let state = "error";
  await page.route("**/api/scenarios/*/mesa?*", async (route) => {
    if (state === "error") {
      await pending;
      await route.fulfill({
        status: 503,
        json: { detail: "Conexión interrumpida" },
      });
    } else if (state === "empty") {
      const response = await route.fetch();
      const body = await response.json();
      await route.fulfill({ json: { ...body, components: [] } });
    } else {
      await route.continue();
    }
  });
  await page.goto(
    `/react/scenarios/${fixture.scenario.id}/mesa?case=${fixture.case.id}&variant=${fixture.variant.id}`,
  );
  await expect(page.getByRole("status")).toHaveText(
    "Cargando componentes del caso…",
  );
  release();
  await expect(page.getByRole("alert")).toContainText("Conexión interrumpida");
  state = "ready";
  await page.getByRole("button", { name: "Reintentar", exact: true }).click();
  await expect(
    page.getByRole("img", { name: "Demanda medida · MW" }),
  ).toBeVisible();
  state = "empty";
  await page.reload();
  await expect(page.getByRole("status")).toHaveText(
    "Este caso no tiene componentes eléctricos disponibles.",
  );
  await expect(
    page.getByRole("img", { name: "Demanda medida · MW" }),
  ).toHaveCount(0);
});

test("mesa de optimización: un período fuera de cobertura no muestra una curva parcial", async ({
  page,
}) => {
  const fixture = await (
    await page.request.get("/api/auth/mesa-fixture")
  ).json();
  const csrf = await (await page.request.get("/api/auth/csrf")).json();
  await page.request.post("/api/auth/login", {
    data: {
      email: "mesa@example.local",
      password: "mesa test pass",
      next: "/react/projects",
    },
    headers: { "X-CSRF-Token": csrf.csrf_token },
  });
  const search = new URLSearchParams({
    case: String(fixture.case.id),
    variant: String(fixture.variant.id),
    range_start: "2026-10-20T00:00:00-03:00",
    range_end: "2026-10-20T03:00:00-03:00",
  });
  await page.goto(`/react/scenarios/${fixture.scenario.id}/mesa?${search}`);
  await expect(page.getByRole("status")).toContainText(
    "Sin cobertura completa",
  );
  await expect(
    page.getByRole("img", { name: "Demanda medida · MW" }),
  ).toHaveCount(0);
});
