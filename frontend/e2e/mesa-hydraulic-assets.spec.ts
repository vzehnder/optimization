import { expect, test, type Page } from "@playwright/test";

import AxeBuilder from "@axe-core/playwright";

async function openMesa(page: Page, name: string) {
  const fixture = await (
    await page.request.get(
      `/api/auth/mesa-fixture?hydraulic_execution=true&case_name=${encodeURIComponent(name)}`,
    )
  ).json();
  const csrf = await (await page.request.get("/api/auth/csrf")).json();
  await page.request.post("/api/auth/login", {
    data: { email: "mesa@example.local", password: "mesa test pass" },
    headers: { "X-CSRF-Token": csrf.csrf_token },
  });
  await page.goto(
    `/react/scenarios/${fixture.scenario.id}/mesa?case=${fixture.case.id}&variant=${fixture.variant.id}`,
  );
  return fixture;
}

test("Crear un embalse desde la mesa conserva su identidad al recargar", async ({
  page,
}) => {
  const fixture = await openMesa(page, "Activos nuevos");
  await page
    .getByRole("button", { name: "Editar activos hidráulicos", exact: true })
    .click({ timeout: 5000 });
  const editor = page.getByRole("region", {
    name: "Activos hidráulicos del caso",
    exact: true,
  });
  await editor
    .getByRole("button", { name: "Agregar embalse", exact: true })
    .click();
  await editor
    .getByLabel("Etiqueta reservoir_1", { exact: true })
    .fill("Embalse nuevo");
  await editor
    .getByRole("button", { name: "Guardar diagrama", exact: true })
    .click();
  await expect(
    editor.getByText("Estado: saved", { exact: true }),
  ).toBeVisible();
  const diagramUrl = `/api/scenarios/${fixture.scenario.id}/hydraulic-diagram`;
  const saved = (await (await page.request.get(diagramUrl)).json()).diagram;
  const created = saved.nodes.find(
    (n: { technical_key: string }) => n.technical_key === "reservoir_1",
  );
  expect(created.display_name).toBe("Embalse nuevo");
  await page.reload();
  await page
    .getByRole("button", { name: "Editar activos hidráulicos", exact: true })
    .click();
  const recovered = (await (await page.request.get(diagramUrl)).json()).diagram;
  expect(
    recovered.nodes.find(
      (n: { technical_key: string }) => n.technical_key === "reservoir_1",
    ),
  ).toEqual(created);
  await page
    .getByRole("button", { name: "Cerrar edición hidráulica", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog", { name: "Configurar vista" })
      .getByLabel("Componente"),
  ).toContainText("Embalse nuevo");
  await expect(page).toHaveURL(/\/mesa\?/);
});

test("Usar un activo existente edita el mismo objeto sin duplicarlo", async ({
  page,
}) => {
  const fixture = await openMesa(page, "Identidad existente");
  const mesaUrl = `/api/scenarios/${fixture.scenario.id}/mesa?case_id=${fixture.case.id}&variant_id=${fixture.variant.id}`;
  const before = (await (await page.request.get(mesaUrl)).json()).components;
  const reservoir = before.find(
    (c: { entity_id: string }) => c.entity_id === "reservoir",
  );
  await page
    .getByRole("button", { name: "Editar activos hidráulicos", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Usar activo existente", exact: true })
    .selectOption("reservoir");
  await page
    .getByLabel("Etiqueta reservoir", { exact: true })
    .fill("Embalse renombrado");
  await page
    .getByRole("button", { name: "Guardar diagrama", exact: true })
    .click();
  await expect(page.getByText("Estado: saved", { exact: true })).toBeVisible();
  const after = (await (await page.request.get(mesaUrl)).json()).components;
  expect(after).toHaveLength(before.length);
  expect(
    after.find((c: { entity_id: string }) => c.entity_id === "reservoir"),
  ).toMatchObject({
    name: "Embalse renombrado",
    base_entity_id: reservoir.base_entity_id,
    linkable_object_id: reservoir.linkable_object_id,
  });
});

test("Los parámetros hidráulicos admiten valores decimales y conservan sus unidades", async ({
  page,
}) => {
  const fixture = await openMesa(page, "Parámetros decimales");
  await page
    .getByRole("button", { name: "Editar activos hidráulicos", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Usar activo existente", exact: true })
    .selectOption("reservoir");
  await page
    .getByLabel("Almacenamiento inicial reservoir", { exact: true })
    .fill("9.5");
  await page
    .getByRole("button", { name: "Guardar diagrama", exact: true })
    .click();
  await expect(page.getByText("Estado: saved", { exact: true })).toBeVisible();
  const mesa = await (
    await page.request.get(
      `/api/scenarios/${fixture.scenario.id}/mesa?case_id=${fixture.case.id}&variant_id=${fixture.variant.id}`,
    )
  ).json();
  const reservoir = mesa.components.find(
    (c: { entity_id: string }) => c.entity_id === "reservoir",
  );
  expect(
    reservoir.parameters.find(
      (p: { key: string }) => p.key === "initial_storage_hm3",
    ),
  ).toMatchObject({ value: 9.5, unit: "hm3" });
});

test("El editor hidráulico es operable con teclado y cabe a 390 px", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openMesa(page, "Edición adaptable");
  await page
    .getByRole("button", { name: "Editar activos hidráulicos", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await page
    .getByRole("combobox", { name: "Usar activo existente", exact: true })
    .selectOption("reservoir");
  await expect(
    page.getByLabel("Almacenamiento inicial reservoir", { exact: true }),
  ).toHaveValue("10");
  await page.screenshot({
    path: testInfo.outputPath("mesa-activos-editor-1440.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-activos-editor-390.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Cerrar edición hidráulica", exact: true })
    .click();
  await expect(
    page.getByRole("button", {
      name: "Editar activos hidráulicos",
      exact: true,
    }),
  ).toBeFocused();
});

test("Cerrar un borrador permite seguir editando sin perder los cambios", async ({
  page,
}) => {
  await openMesa(page, "Borrador local");
  await page
    .getByRole("button", { name: "Editar activos hidráulicos", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Agregar central", exact: true })
    .click();
  await page
    .getByLabel("Etiqueta plant_2", { exact: true })
    .fill("Central pendiente");
  await page
    .getByRole("button", { name: "Cerrar edición hidráulica", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Hay cambios hidráulicos sin guardar",
  );
  await page
    .getByRole("button", { name: "Seguir editando activos", exact: true })
    .click();
  await expect(
    page.getByLabel("Etiqueta plant_2", { exact: true }),
  ).toHaveValue("Central pendiente");
  await page
    .getByRole("button", { name: "Guardar diagrama", exact: true })
    .click();
  await expect(page.getByText("Estado: saved", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Generar preview v3", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Enfocar plant_2", exact: true }),
  ).toContainText(/unit|unidad/i);
  await expect(
    page.getByRole("button", { name: "Promover version v3", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Cerrar edición hidráulica", exact: true })
    .click();
  await expect(
    page.getByRole("region", {
      name: "Activos hidráulicos del caso",
      exact: true,
    }),
  ).toHaveCount(0);
});

test("Guardar una curva invalida la preparación visible aunque no cambien los escalares", async ({
  page,
}) => {
  await page.route("**/mesa/hydraulic-execution/preview", (route) =>
    route.fulfill({
      json: {
        preparation_hash: "a".repeat(64),
        period_count: 1,
        preview_periods: [],
        generation_metadata: {
          date_range: {
            start: "2026-10-20T00:00:00Z",
            end: "2026-10-20T02:00:00Z",
          },
        },
      },
    }),
  );
  const fixture = await openMesa(page, "Curva y preparación");
  await page
    .getByText("Preparar ejecución hidráulica", { exact: true })
    .click();
  await page
    .getByLabel("Versión fuente de la red")
    .selectOption(String(fixture.version.id));
  await page.getByLabel("Objetivo hidráulico").selectOption("energy");
  await page
    .getByRole("button", { name: "Validar red hidráulica", exact: true })
    .click();
  const execute = page.getByRole("button", {
    name: "Ejecutar red hidráulica",
    exact: true,
  });
  await expect(execute).toBeEnabled();
  await page
    .getByRole("button", { name: "Editar activos hidráulicos", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Usar activo existente", exact: true })
    .selectOption("plant_1");
  await page.getByLabel("Potencia punto 2 unit_1", { exact: true }).fill("25");
  await page
    .getByRole("button", { name: "Guardar diagrama", exact: true })
    .click();
  await expect(page.getByText("Estado: saved", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Cerrar edición hidráulica", exact: true })
    .click();
  await expect(execute).toBeDisabled();
  await expect(page.getByText(/Activos guardados.*revalidación/)).toBeVisible();
});

test("Un guardado en curso protege la edición y el cierre hasta recibir respuesta", async ({
  page,
}) => {
  await openMesa(page, "Guardado en curso");
  await page
    .getByRole("button", { name: "Editar activos hidráulicos", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Usar activo existente", exact: true })
    .selectOption("reservoir");
  const label = page.getByLabel("Etiqueta reservoir", { exact: true });
  await label.fill("Nombre guardado");
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/hydraulic-diagram", async (route) => {
    if (route.request().method() === "PUT") await gate;
    await route.continue();
  });
  await page
    .getByRole("button", { name: "Guardar diagrama", exact: true })
    .click();
  try {
    await expect(
      page.getByText("Estado: saving", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: "Cerrar edición hidráulica",
        exact: true,
      }),
    ).toBeDisabled();
    await expect(label).toBeDisabled();
  } finally {
    release();
  }
  await expect(page.getByText("Estado: saved", { exact: true })).toBeVisible();
  await expect(label).toHaveValue("Nombre guardado");
  await expect(
    page.getByRole("button", {
      name: "Cerrar edición hidráulica",
      exact: true,
    }),
  ).toBeEnabled();
});

test("Un conflicto conserva el borrador y recargar actualiza también el inventario de la mesa", async ({
  page,
}) => {
  const fixture = await openMesa(page, "Conflicto de activos");
  await page
    .getByRole("button", { name: "Editar activos hidráulicos", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Usar activo existente", exact: true })
    .selectOption("reservoir");
  const label = page.getByLabel("Etiqueta reservoir", { exact: true });
  await label.fill("Mi borrador");
  const path = `/api/scenarios/${fixture.scenario.id}/hydraulic-diagram`;
  const diagram = (await (await page.request.get(path)).json()).diagram;
  diagram.nodes.find(
    (n: { technical_key: string }) => n.technical_key === "reservoir",
  ).display_name = "Cambio concurrente";
  const csrf = (await (await page.request.get("/api/auth/csrf")).json())
    .csrf_token;
  const changed = await page.request.put(path, {
    headers: { "X-CSRF-Token": csrf },
    data: {
      revision: diagram.revision,
      nodes: diagram.nodes,
      reaches: diagram.reaches,
      viewport: diagram.layout.viewport,
    },
  });
  expect(changed.ok()).toBe(true);
  await page
    .getByRole("button", { name: "Guardar diagrama", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "stale hydraulic diagram revision",
  );
  await expect(label).toHaveValue("Mi borrador");
  await page
    .getByRole("button", { name: "Recargar diagrama", exact: true })
    .click();
  await expect(label).toHaveValue("Cambio concurrente");
  await page
    .getByRole("button", { name: "Cerrar edición hidráulica", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog", { name: "Configurar vista" })
      .getByLabel("Componente"),
  ).toContainText("Cambio concurrente");
});

test("Completar embalse y central permite promover y ejecutar sus resultados en la mesa", async ({
  page,
}, testInfo) => {
  // Includes Julia startup, validation, solving and persistence on Windows.
  // MESA-012 measured this complete journey at three minutes on this fixture.
  test.setTimeout(420000);
  page.setDefaultTimeout(10000);
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await openMesa(page, "Activos ejecutables");
  await page
    .getByRole("button", { name: "Editar activos hidráulicos", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Agregar embalse", exact: true })
    .click();
  await page
    .getByLabel("Etiqueta reservoir_1", { exact: true })
    .fill("Embalse nuevo");
  await page
    .getByLabel("Almacenamiento maximo reservoir_1", { exact: true })
    .fill("10");
  await page
    .getByLabel("Almacenamiento inicial reservoir_1", { exact: true })
    .fill("5");
  for (const index of [1, 2]) {
    await page
      .getByRole("button", {
        name: "Agregar punto de curva reservoir_1",
        exact: true,
      })
      .click();
    await page
      .getByLabel(`Almacenamiento punto ${index} reservoir_1`, { exact: true })
      .fill(index === 1 ? "0" : "10");
    await page
      .getByLabel(`Cota punto ${index} reservoir_1`, { exact: true })
      .fill(index === 1 ? "700" : "710");
  }
  await page
    .getByLabel("Importar afluentes reservoir_1", { exact: true })
    .setInputFiles({
      name: "aporte.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "timestamp,duration_hours,value_m3s\n2026-10-20T00:00:00+00:00,1,1\n2026-10-20T01:00:00+00:00,1,1\n",
      ),
    });
  await expect(
    page
      .getByRole("heading", {
        name: "Afluente natural Embalse nuevo",
        exact: true,
      })
      .locator("..")
      .locator(".."),
  ).toContainText("2026-10-20T01:00:00");
  await page
    .getByRole("button", { name: "Agregar central", exact: true })
    .click();
  await page
    .getByLabel("Etiqueta plant_2", { exact: true })
    .fill("Central nueva");
  await page
    .getByLabel("Potencia maxima central plant_2", { exact: true })
    .fill("10");
  await page
    .getByRole("button", { name: "Agregar unidad plant_2", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Nodo de toma unit_2", exact: true })
    .selectOption("reservoir_1");
  await page
    .getByRole("combobox", { name: "Nodo de descarga unit_2", exact: true })
    .selectOption("outlet");
  await page.getByLabel("Potencia maxima unit_2", { exact: true }).fill("10");
  await page.getByLabel("Caudal maximo unit_2", { exact: true }).fill("10");
  for (const index of [1, 2]) {
    await page
      .getByRole("button", {
        name: "Agregar punto de curva unit_2",
        exact: true,
      })
      .click();
    await page
      .getByLabel(`Caudal punto ${index} unit_2`, { exact: true })
      .fill(index === 1 ? "0" : "10");
    await page
      .getByLabel(`Potencia punto ${index} unit_2`, { exact: true })
      .fill(index === 1 ? "0" : "10");
  }
  await page
    .getByRole("button", { name: "Guardar diagrama", exact: true })
    .click();
  await expect(page.getByText("Estado: saved", { exact: true })).toBeVisible();
  await page.reload();
  await page
    .getByRole("button", { name: "Editar activos hidráulicos", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Usar activo existente", exact: true })
    .selectOption("plant_2");
  await expect(
    page.getByRole("combobox", { name: "Nodo de toma unit_2", exact: true }),
  ).toHaveValue("reservoir_1");
  await page
    .getByRole("button", { name: "Generar preview v3", exact: true })
    .click();
  const promote = page.getByRole("button", {
    name: "Promover version v3",
    exact: true,
  });
  await expect(promote).toBeEnabled({ timeout: 60000 });
  const promotedResponse = page.waitForResponse(
    (r) => r.url().endsWith("/hydraulic-diagram/promote"),
    { timeout: 60000 },
  );
  await promote.click();
  const promoted = await promotedResponse;
  expect(promoted.status(), await promoted.text()).toBe(201);
  const version = await promoted.json();
  await page
    .getByRole("button", { name: "Preparar versión en la mesa", exact: true })
    .click({ timeout: 5000 });
  await page
    .getByText("Preparar ejecución hidráulica", { exact: true })
    .click();
  await page
    .getByLabel("Versión fuente de la red")
    .selectOption(String(version.id));
  const execution = page.getByRole("region", {
    name: "Ejecución de red hidráulica",
    exact: true,
  });
  await expect(execution).toContainText("plant_2");
  await expect(execution).toContainText("reservoir_1");
  // A positive water value rules out arbitrary spilling among equal-energy optima.
  await page
    .getByLabel("CMg para la ejecución")
    .selectOption(`${fixture.prices.id}:price_usd_per_mwh`);
  await page.getByLabel("Valor terminal reservoir (USD/hm³)").fill("1");
  await page.getByLabel("Valor terminal reservoir_1 (USD/hm³)").fill("1");
  await page
    .getByRole("button", { name: "Validar red hidráulica", exact: true })
    .click();
  const execute = page.getByRole("button", {
    name: "Ejecutar red hidráulica",
    exact: true,
  });
  await expect(execute).toBeEnabled({ timeout: 60000 });
  await execute.click();
  await page
    .getByRole("button", {
      name: "Ver resultados hidráulicos en la mesa",
      exact: true,
    })
    .click({ timeout: 300000 });
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  const plantLabel = await dialog
    .getByRole("option")
    .filter({ hasText: / · plant_2 · #/ })
    .textContent();
  await dialog.getByLabel("Componente").selectOption({ label: plantLabel! });
  await dialog.getByLabel("Título").fill("Central nueva ejecutada");
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  await expect(
    page.getByRole("region", {
      name: "Central · Central nueva ejecutada",
      exact: true,
    }),
  ).toContainText("10 MW");
  const mesa = await (
    await page.request.get(
      `/api/scenarios/${fixture.scenario.id}/mesa?case_id=${fixture.case.id}&variant_id=${fixture.variant.id}&run_id=${new URL(page.url()).searchParams.get("run")}`,
    )
  ).json();
  const reservoir = mesa.components.find(
    (c: { entity_id: string }) => c.entity_id === "reservoir_1",
  );
  const volume = reservoir.additional_series.find(
    (s: { name: string }) => s.name === "Volumen almacenado",
  );
  expect(volume.points.at(-1).value).toBeCloseTo(4.9352, 6);
  await page.screenshot({
    path: testInfo.outputPath("mesa-activos-resultados-1440.png"),
  });
  await expect(page).toHaveURL(/\/mesa\?/);
});
