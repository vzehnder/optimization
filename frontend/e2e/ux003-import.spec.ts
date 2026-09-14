import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

async function post(page: Page, path: string, data: unknown) {
  const token = (await (await page.request.get("/api/auth/csrf")).json())
    .csrf_token;
  return page.request.post(path, { data, headers: { "X-CSRF-Token": token } });
}

async function openImport(page: Page) {
  const me = await (await page.request.get("/api/auth/me")).json();
  if (me.bootstrap_required)
    await post(page, "/api/auth/bootstrap", {
      email: "admin@example.local",
      password: "admin-pass",
      display_name: "Admin User",
    });
  else
    await post(page, "/api/auth/login", {
      email: "admin@example.local",
      password: "admin-pass",
    });
  const project = await (
    await post(page, "/api/projects", {
      name: `Importación UX-003 ${Date.now()}`,
    })
  ).json();
  const scenario = await (
    await post(page, `/api/projects/${project.id}/scenarios`, {
      name: "Precios y demanda",
    })
  ).json();
  const document = {
    schema_version: "bess_editor_draft.v1",
    case: { name: "UX003" },
    pcc: { id: "bus_1", type: "bus" },
    grid: { id: "grid_1" },
    assets: [{ id: "load_1", type: "load" }],
    solver: { name: "HiGHS" },
    time_series: { sources: [] },
  };
  const draft = await post(page, `/api/scenarios/${scenario.id}/draft`, {
    document,
  });
  expect(draft.ok()).toBeTruthy();
  await page.goto(`/react/scenarios/${scenario.id}/draft`);
  return { project, scenario };
}

test("UX-003 imports a CSV with two signals, opens its values and prepares one execution", async ({
  page,
}, testInfo) => {
  const { project, scenario } = await openImport(page);
  const wizard = page.getByRole("region", {
    name: "Importar series de tiempo",
  });
  await wizard.getByLabel("Archivo CSV o XLSX").setInputFiles({
    name: "precios-demanda.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "timestamp,hours,price,demand\n2026-01-01T00:00:00+00:00,1,55,2\n2026-01-01T01:00:00+00:00,1,60,2.5\n",
    ),
  });
  await wizard.getByRole("button", { name: "Continuar a columnas" }).click();
  await wizard.getByLabel("Columna de valores 1").selectOption("price");
  await wizard
    .getByRole("combobox", { name: /^Señal 1/ })
    .selectOption("price_usd_per_mwh");
  await wizard.getByRole("button", { name: "Agregar señal" }).click();
  await wizard.getByLabel("Columna de valores 2").selectOption("demand");
  await wizard
    .getByRole("combobox", { name: /^Señal 2/ })
    .selectOption("load_demand_mw");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: testInfo.outputPath("columnas-1440.png"),
    fullPage: true,
  });
  expect(
    (
      await new AxeBuilder({ page }).include(".guided-import").analyze()
    ).violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
  await wizard
    .getByRole("button", { name: "Confirmar columnas y revisar" })
    .click();
  await wizard.getByRole("button", { name: "Comprobar datos" }).click();
  await expect(
    wizard.getByRole("table", { name: "Datos que se importarán" }),
  ).toContainText("2.5");
  await wizard.getByRole("button", { name: "Continuar a importación" }).click();
  for (const width of [1440, 1280, 320]) {
    await page.setViewportSize({ width, height: width === 1280 ? 720 : 900 });
    await wizard.scrollIntoViewIfNeeded();
    await expect(page.locator("body")).toHaveJSProperty("scrollWidth", width);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: testInfo.outputPath(`importacion-${width}.png`),
      fullPage: true,
    });
  }
  const accessibility = await new AxeBuilder({ page })
    .include(".guided-import")
    .analyze();
  expect(
    accessibility.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.evaluate(() => {
    document.documentElement.style.zoom = "2";
  });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: testInfo.outputPath("importacion-zoom200.png"),
    fullPage: true,
  });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 640);
  await page.evaluate(() => {
    document.documentElement.style.zoom = "1";
  });
  await wizard.getByRole("button", { name: "Volver a revisión" }).focus();
  await page.keyboard.press("Tab");
  await expect(
    wizard.getByRole("button", { name: "Confirmar importación" }),
  ).toBeFocused();
  await wizard.getByRole("button", { name: "Confirmar importación" }).click();
  const link = wizard.getByRole("link", { name: "Abrir precios-demanda" });
  await expect(link).toBeVisible();
  await link.click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "precios-demanda (v1)", exact: true }),
  ).toBeVisible();
  const sets = await (
    await page.request.get(`/api/projects/${project.id}/time-series-sets`)
  ).json();
  expect(sets.time_series_sets).toHaveLength(1);
  const imported = await (
    await page.request.get(
      `/api/projects/${project.id}/time-series-sets/${sets.time_series_sets[0].id}`,
    )
  ).json();
  const seriesValues = imported.time_series_set.values as {
    signal_key: string;
    value_numeric: number;
  }[];
  expect(
    seriesValues
      .filter((value) => value.signal_key === "price_usd_per_mwh")
      .map((value) => value.value_numeric),
  ).toEqual([55, 60]);
  expect(
    seriesValues
      .filter((value) => value.signal_key === "load_demand_mw")
      .map((value) => value.value_numeric),
  ).toEqual([2, 2.5]);
  await page.goto(`/react/scenarios/${scenario.id}?section=data`);
  await page
    .getByLabel("Serie de precio (price_usd_per_mwh)", { exact: true })
    .selectOption(String(sets.time_series_sets[0].id));
  await page
    .getByLabel("Serie load_demand_mw (load_1)", { exact: true })
    .selectOption(String(sets.time_series_sets[0].id));
  await page
    .getByRole("button", { name: "Confirmar fuentes", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Usar cobertura disponible", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Revisar preparación", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Ejecutar variante", exact: true })
    .click();
  await expect(page).toHaveURL(/\/runs\/\d+/);
});

test("UX-003 corrects an XLSX cell and keeps the selected sheet and edits when returning", async ({
  page,
}) => {
  const { project } = await openImport(page);
  const python =
    process.env.PYTHON ||
    [
      path.resolve("../.venv/Scripts/python.exe"),
      path.resolve("../.venv/bin/python"),
    ].find(existsSync) ||
    "python";
  const buffer = execFileSync(python, [
    "-c",
    "from openpyxl import Workbook; from io import BytesIO; import sys; b=Workbook(); b.active.title='Notas'; b.active.append(['nota']); b.active.append(['Revisar precios']); s=b.create_sheet('Precios'); s.append(['timestamp','hours','price']); s.append(['2026-01-01T00:00:00+00:00',1,'1,234']); s.append(['2026-01-01T01:00:00+00:00',1,60]); o=BytesIO(); b.save(o); sys.stdout.buffer.write(o.getvalue())",
  ]);
  const wizard = page.getByRole("region", {
    name: "Importar series de tiempo",
  });
  await wizard.getByLabel("Archivo CSV o XLSX").setInputFiles({
    name: "precios.xlsx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer,
  });
  await wizard.getByRole("button", { name: "Continuar a columnas" }).click();
  await wizard
    .getByRole("combobox", { name: "Hoja", exact: true })
    .selectOption("Precios");
  await wizard.getByLabel("Columna de valores 1").selectOption("price");
  await wizard
    .getByRole("combobox", { name: /^Señal 1/ })
    .selectOption("price_usd_per_mwh");
  await wizard
    .getByRole("button", { name: "Confirmar columnas y revisar" })
    .click();
  await wizard.getByRole("button", { name: "Comprobar datos" }).click();
  await wizard
    .getByRole("button", {
      name: "Corregir hoja Precios, fila 2, columna price",
    })
    .click();
  await expect(
    wizard.getByLabel("Fila 2, price", { exact: true }),
  ).toBeFocused();
  await wizard.getByLabel("Fila 2, price", { exact: true }).fill("70");
  await wizard.getByRole("button", { name: "Volver a columnas" }).click();
  await wizard
    .getByRole("combobox", { name: "Hoja", exact: true })
    .selectOption("Notas");
  await wizard
    .getByRole("combobox", { name: "Hoja", exact: true })
    .selectOption("Precios");
  await expect(wizard.getByLabel("Columna de valores 1")).toHaveValue("price");
  await wizard
    .getByRole("button", { name: "Confirmar columnas y revisar" })
    .click();
  await expect(wizard.getByLabel("Fila 2, price", { exact: true })).toHaveValue(
    "70",
  );
  await wizard
    .getByRole("button", { name: "Guardar correcciones en la fuente temporal" })
    .click();
  await wizard.getByRole("button", { name: "Comprobar datos" }).click();
  await wizard.getByRole("button", { name: "Continuar a importación" }).click();
  await wizard.getByRole("button", { name: "Confirmar importación" }).click();
  await wizard.getByRole("link", { name: "Abrir precios" }).click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "precios (v1)", exact: true }),
  ).toBeVisible();
  const sets = await (
    await page.request.get(`/api/projects/${project.id}/time-series-sets`)
  ).json();
  expect(sets.time_series_sets).toHaveLength(1);
  const imported = await (
    await page.request.get(
      `/api/projects/${project.id}/time-series-sets/${sets.time_series_sets[0].id}`,
    )
  ).json();
  expect(
    imported.time_series_set.values.map(
      (value: { value_numeric: number }) => value.value_numeric,
    ),
  ).toEqual([70, 60]);
});
