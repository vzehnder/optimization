import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";

async function openMesa(page: Page, name: string, comparison = false) {
  const fixture = await (
    await page.request.get(
      `/api/auth/mesa-fixture?case_name=${encodeURIComponent(name)}&executable=true&comparison=${comparison}`,
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

test("Una serie manual se publica como apoyo y persiste en una pestaña sin duplicar sus datos", async ({
  page,
}) => {
  await openMesa(page, "Apoyo manual");
  await page
    .getByRole("button", { name: "Crear serie manual", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Crear serie manual",
    exact: true,
  });
  await dialog.getByLabel("Nombre de la serie").fill("Demanda de apoyo");
  await dialog
    .getByLabel("Objeto propietario")
    .selectOption({ label: "Demanda Norte · load_north" });
  await dialog
    .getByLabel("Inicio con offset")
    .fill("2026-10-20T00:00:00-03:00");
  await dialog.getByLabel("Zona horaria").fill("America/Santiago");
  await dialog.getByLabel("Duración de cada intervalo (minutos)").fill("60");
  await dialog.getByLabel("Valores por intervalo").fill("20\n30");
  await dialog.getByLabel("Motivo").fill("Proyección manual de demanda");
  await dialog.getByLabel("Confirmo la publicación como apoyo").check();
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/mesa/manual-series") &&
      r.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: "Publicar serie de apoyo" }).click();
  expect((await response).status()).toBe(201);
  await expect(dialog).not.toBeVisible();
  await page
    .getByRole("button", { name: "Agregar pestaña", exact: true })
    .click();
  const tab = page.getByRole("dialog", { name: "Configurar pestaña" });
  await tab.getByLabel("Nombre de pestaña").fill("Proyecciones");
  await tab.getByRole("button", { name: "Aplicar" }).click();
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  const view = page.getByRole("dialog", { name: "Configurar vista" });
  const option = view
    .getByLabel("Componente")
    .getByRole("option", { name: /Demanda de apoyo/ });
  await view
    .getByLabel("Componente")
    .selectOption((await option.getAttribute("value")) as string);
  await view.getByLabel("Título", { exact: true }).fill("Proyección manual");
  await view.getByLabel("Presentación").selectOption("table");
  await view.getByRole("button", { name: "Aplicar" }).click();
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  const panel = page.getByRole("region", {
    name: "Serie manual · Proyección manual",
    exact: true,
  });
  await expect(
    panel.getByText(/No participa en esta simulación/),
  ).toBeVisible();
  await expect(
    panel.getByRole("cell", { name: "20", exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByRole("cell", { name: "30", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Proyecciones" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(panel.getByText(/Revisión 1/)).toBeVisible();
});

async function manualFixture(page: Page, name: string, comparison = false) {
  const fixture = await openMesa(page, name, comparison);
  const path = `/api/scenarios/${fixture.scenario.id}/mesa`;
  const csrf = (await (await page.request.get("/api/auth/csrf")).json())
    .csrf_token;
  const created = await page.request.post(`${path}/manual-series`, {
    headers: { "X-CSRF-Token": csrf },
    data: {
      case_id: fixture.case.id,
      variant_id: fixture.variant.id,
      object_id: fixture.object.id,
      name: "Demanda de apoyo",
      binding_role_key: "load_demand",
      semantic_type_key: "load_demand",
      unit_key: "mw",
      timezone: "America/Santiago",
      resolution_seconds: 3600,
      points: [
        {
          start: "2026-10-20T00:00:00-03:00",
          end: "2026-10-20T01:00:00-03:00",
          value: 20,
        },
        {
          start: "2026-10-20T01:00:00-03:00",
          end: "2026-10-20T02:00:00-03:00",
          value: 30,
        },
      ],
      confirm: true,
      reason: "Preparar apoyo",
    },
  });
  expect(created.status()).toBe(201);
  const manual = await created.json();
  const data = await (
    await page.request.get(
      `${path}?case_id=${fixture.case.id}&variant_id=${fixture.variant.id}`,
    )
  ).json();
  const source = data.components.find(
    (c: { entity_type: string }) => c.entity_type === "manual_series",
  );
  const prefs = await page.request.put(
    `${path}/preferences?case_id=${fixture.case.id}`,
    {
      headers: { "X-CSRF-Token": csrf },
      data: {
        expected_revision: 0,
        configuration: {
          schema_version: 1,
          active_tab_id: "manual",
          tabs: [
            {
              id: "manual",
              title: "Apoyo",
              layout: "2x2",
              panels: [
                {
                  id: "support",
                  title: "Demanda de apoyo",
                  mode: "table",
                  component: {
                    entity_id: source.entity_id,
                    entity_type: source.entity_type,
                    linkable_object_id: source.linkable_object_id,
                  },
                  series_keys: [source.series.signal_key],
                },
                {
                  id: "demand",
                  title: "Demanda Norte",
                  mode: "table",
                  component: {
                    entity_id: "load_north",
                    entity_type: "component:load",
                    linkable_object_id: fixture.object.id,
                  },
                  series_keys: ["load_demand_mw"],
                },
              ],
            },
          ],
        },
      },
    },
  );
  expect(prefs.ok()).toBe(true);
  await page.reload();
  return { fixture, manual, path, csrf };
}

test("Editar la serie manual conserva su identidad y vincularla cambia la preparación", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const { fixture, manual, path } = await manualFixture(
    page,
    "Vinculación manual",
  );
  const panel = page.getByRole("region", {
    name: "Serie manual · Demanda de apoyo",
    exact: true,
  });
  const demand = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await expect(
    demand.getByRole("cell", { name: "10", exact: true }),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Gestionar serie manual" }).click();
  const editor = page.getByRole("dialog", {
    name: "Serie manual · Demanda de apoyo",
  });
  await editor.getByLabel("Valor del intervalo 2 (MW)").fill("35");
  await editor.getByLabel("Motivo").fill("Actualizar proyección");
  await editor
    .getByLabel("Confirmo la publicación de una nueva revisión")
    .check();
  await editor.getByRole("button", { name: "Publicar revisión" }).click();
  await expect(editor.getByText(/Revisión 2/)).toBeVisible();
  await expect(
    demand.getByRole("cell", { name: "12", exact: true }),
  ).toBeVisible();
  await editor.getByLabel("Motivo").fill("Usar proyección en la preparación");
  await editor
    .getByLabel("Confirmo el reemplazo de esta entrada en la variante")
    .check();
  await editor
    .getByRole("button", { name: "Vincular revisión publicada" })
    .click();
  await expect(
    editor.getByText("Vínculo vigente en esta variante", { exact: true }),
  ).toBeVisible();
  await editor.getByRole("button", { name: "Cerrar", exact: true }).click();
  await expect(
    demand.getByRole("cell", { name: "35", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(panel.getByText(/Revisión 2/)).toBeVisible();
  await expect(
    demand.getByRole("cell", { name: "35", exact: true }),
  ).toBeVisible();
  const detail = await (
    await page.request.get(
      `${path}/manual-series/${manual.signal_id}?case_id=${fixture.case.id}&variant_id=${fixture.variant.id}`,
    )
  ).json();
  expect(detail.series.signal_id).toBe(manual.signal_id);
  expect(detail.series.binding_state).toBe("valid_current");
  const manualTable = await panel
    .getByRole("region", { name: "Intervalos de Demanda de apoyo" })
    .boundingBox();
  expect(manualTable!.height).toBeGreaterThanOrEqual(65);
  await expect(
    panel.getByRole("cell", { name: "35", exact: true }),
  ).toBeInViewport();
  await page.screenshot({ path: testInfo.outputPath("mesa-manual-1440.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("mesa-manual-390.png"),
    fullPage: true,
  });
});

test("Editar un apoyo sin vínculo conserva la preparación eléctrica validada", async ({
  page,
}) => {
  await manualFixture(page, "Apoyo sin efecto");
  await page.route("**/mesa/execution/preview", (route) =>
    route.fulfill({
      json: {
        preparation_hash: "a".repeat(64),
        period_count: 2,
        range_start: "2026-10-20T00:00:00-03:00",
        range_end: "2026-10-20T02:00:00-03:00",
        timezone: "America/Santiago",
        resolution_hours: 1,
        model_contract: "bess_system_dispatch.v2",
        series_bindings: [],
      },
    }),
  );
  await page.getByText("Preparar ejecución eléctrica", { exact: true }).click();
  await page
    .getByRole("button", { name: "Validar preparación", exact: true })
    .click();
  const execute = page.getByRole("button", {
    name: "Ejecutar caso eléctrico",
    exact: true,
  });
  await expect(execute).toBeEnabled();
  await page.getByRole("button", { name: "Gestionar serie manual" }).click();
  const editor = page.getByRole("dialog", {
    name: "Serie manual · Demanda de apoyo",
  });
  await editor.getByLabel("Valor del intervalo 2 (MW)").fill("31");
  await editor.getByLabel("Motivo").fill("Apoyo sin vínculo");
  await editor
    .getByLabel("Confirmo la publicación de una nueva revisión")
    .check();
  await editor.getByRole("button", { name: "Publicar revisión" }).click();
  await expect(editor.getByText(/Revisión 2/)).toBeVisible();
  await editor.getByRole("button", { name: "Cerrar", exact: true }).click();
  await expect(execute).toBeEnabled();
});

test("El apoyo no inventa resultados ni diferencias en la comparación o su CSV", async ({
  page,
}) => {
  const { fixture } = await manualFixture(page, "Apoyo histórico", true);
  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  const panel = page.getByRole("region", {
    name: "Serie manual · Demanda de apoyo",
    exact: true,
  });
  await expect(
    panel.getByText(/Esta vista de apoyo no tiene resultados ni diferencias/),
  ).toBeVisible();
  await expect(panel.getByRole("table")).toHaveCount(0);
  const downloaded = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Exportar CSV de vistas visibles" })
    .click();
  const file = await (await downloaded).path();
  const csv = await readFile(file!, "utf8");
  const rows = csv
    .trim()
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map((row) => row.split(","));
  const header = rows[0];
  const support = rows
    .slice(1)
    .find((row) => row[header.indexOf("entity_type")] === "manual_series");
  expect(support).toBeDefined();
  expect(support![header.indexOf("role")]).toBe("support");
  for (const column of [
    "before",
    "after",
    "delta",
    "before_revision_id",
    "after_revision_id",
  ])
    expect(support![header.indexOf(column)]).toBe("");
});

test("Un conflicto conserva el borrador y aceptar la revisión actual actualiza la mesa", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { fixture, manual, path, csrf } = await manualFixture(
    page,
    "Conflicto manual",
  );
  const trigger = page.getByRole("button", { name: "Gestionar serie manual" });
  await trigger.click();
  const editor = page.getByRole("dialog", {
    name: "Serie manual · Demanda de apoyo",
  });
  await editor.getByLabel("Valor del intervalo 2 (MW)").fill("35");
  await page.keyboard.press("Escape");
  await expect(editor.getByText("Hay cambios sin publicar.")).toBeVisible();
  await editor.getByRole("button", { name: "Seguir editando" }).click();
  const target = `${path}/manual-series/${manual.signal_id}`;
  const latest = await (
    await page.request.get(
      `${target}?case_id=${fixture.case.id}&variant_id=${fixture.variant.id}`,
    )
  ).json();
  const changed = await page.request.post(`${target}/revisions`, {
    headers: { "X-CSRF-Token": csrf },
    data: {
      case_id: fixture.case.id,
      variant_id: fixture.variant.id,
      expected: latest.expected,
      unit: "MW",
      points: latest.series.points.map(
        (p: { start: string; end: string; value: number }, i: number) => ({
          ...p,
          value: i === 1 ? 50 : 20,
        }),
      ),
      reason: "Otra sesión",
      confirm: true,
    },
  });
  expect(changed.status()).toBe(201);
  await editor.getByLabel("Motivo").fill("Mi corrección");
  await editor
    .getByLabel("Confirmo la publicación de una nueva revisión")
    .check();
  await editor.getByRole("button", { name: "Publicar revisión" }).click();
  await expect(editor.getByRole("alert")).toContainText("cambiaron");
  await expect(editor.getByLabel("Valor del intervalo 2 (MW)")).toHaveValue(
    "35",
  );
  await editor
    .getByRole("button", { name: "Consultar revisión actual" })
    .click();
  await expect(
    editor.getByRole("table", { name: "Comparar cambios manuales" }),
  ).toContainText("50");
  await editor.getByRole("button", { name: "Usar revisión actual" }).click();
  await expect(editor.getByLabel("Valor del intervalo 2 (MW)")).toHaveValue(
    "50",
  );
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-manual-editor-390.png"),
    fullPage: true,
  });
  await editor.getByRole("button", { name: "Cerrar", exact: true }).click();
  const panel = page.getByRole("region", {
    name: "Serie manual · Demanda de apoyo",
    exact: true,
  });
  await expect(
    panel.getByRole("cell", { name: "50", exact: true }),
  ).toBeVisible();
  await expect(trigger).toBeFocused();
});
