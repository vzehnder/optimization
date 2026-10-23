import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";

async function openHistory(page: Page, hydraulic = false) {
  const fixture = await (
    await page.request.get(
      `/api/auth/mesa-fixture?case_name=Historial&comparison=true&hydraulic=${hydraulic}`,
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

test("Historial recupera un run y conserva su procedencia al recargar", async ({
  page,
}) => {
  const fixture = await openHistory(page);
  await page.getByText("Historial de ejecuciones", { exact: true }).click();
  const history = page.getByRole("region", {
    name: "Historial de ejecuciones",
  });
  const row = history
    .getByRole("row")
    .filter({ hasText: `Run #${fixture.reference.id} ·` });
  await expect(row).toContainText("Completada");
  await expect(row).toContainText("2026-10-20T00:00:00-03:00");
  await expect(row).toContainText(
    `Snapshot #${fixture.reference.scenario_version_id}`,
  );
  await row.getByRole("button", { name: "Consultar" }).click();
  await expect(
    page.getByRole("button", { name: "Comparar", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(page.getByLabel("Resultados de ejecución")).toHaveValue(
    String(fixture.reference.id),
  );
  await expect(page.getByRole("tabpanel")).toContainText(
    `Después · Run #${fixture.reference.id}`,
  );
  await page
    .getByRole("button", { name: "Preparación actual", exact: true })
    .click();
  await expect(page.getByRole("tabpanel")).toContainText("Entrada");
});

test("CSV descarga las vistas visibles con todos sus intervalos y la referencia elegida", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await openHistory(page);
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  const label = await dialog
    .getByRole("option")
    .filter({ hasText: "battery_1" })
    .textContent();
  await dialog.getByLabel("Componente").selectOption({ label: label! });
  await dialog.getByLabel("Título").fill("BESS Norte");
  await dialog.getByRole("checkbox", { name: /Carga BESS/ }).uncheck();
  await dialog.getByRole("checkbox", { name: /Descarga BESS/ }).check();
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await page
    .getByLabel("Ejecución de referencia")
    .selectOption(String(fixture.reference.id));
  const battery = page.getByRole("region", {
    name: "BESS · BESS Norte",
    exact: true,
  });
  await battery.getByRole("button", { name: "Tabla", exact: true }).click();
  await expect(
    battery.getByRole("cell", { name: "-3", exact: true }),
  ).toBeVisible();
  const download = async () => {
    const pending = page.waitForEvent("download");
    await page
      .getByRole("button", { name: "Exportar CSV de vistas visibles" })
      .click();
    const file = await pending;
    expect(file.suggestedFilename()).toBe(`mesa-run-${fixture.run.id}.csv`);
    return (await readFile((await file.path())!, "utf8")).trim().split(/\r?\n/);
  };
  await page.getByLabel("Distribución de las vistas").selectOption("1x1");
  const hidden = await download();
  expect(hidden).toHaveLength(3);
  expect(hidden.join("\n")).not.toContain("bess_discharge_power_mw");
  await page.getByLabel("Distribución de las vistas").selectOption("1x2");
  const rows = await download();
  expect(rows).toHaveLength(5);
  const headers = rows[0].replace(/^\uFEFF/, "").split(",");
  const data = rows
    .slice(1)
    .map((line) =>
      Object.fromEntries(
        line.split(",").map((value, i) => [headers[i], value]),
      ),
    );
  expect(
    data
      .filter((row) => row.signal_key === "bess_discharge_power_mw")
      .map((row) => [row.before, row.after, row.delta]),
  ).toEqual([
    ["1.0", "2.0", "1.0"],
    ["3.0", "0.0", "-3.0"],
  ]);
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(battery).toContainText(`Antes · Run #${fixture.reference.id}`);
  expect(await download()).toEqual(rows);
  await page.getByText("Historial de ejecuciones", { exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Historial de ejecuciones" }),
  ).toContainText("Completada");
  await page.screenshot({
    path: testInfo.outputPath("mesa-historial-1440.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-historial-390.png"),
    fullPage: true,
  });
});

test("Una referencia sin zona mantiene sus intervalos separados en la tabla", async ({
  page,
}) => {
  const fixture = await openHistory(page);
  await page.route("**/mesa/comparison?*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const demand = body.series.find(
      (s: { signal_key: string }) => s.signal_key === "load_demand_mw",
    );
    demand.before.timezone = null;
    demand.before.points = demand.before.points.map(
      (p: { start: string; end: string; value: number }) => ({
        ...p,
        start: p.start.slice(0, 19),
        end: p.end.slice(0, 19),
      }),
    );
    demand.status = "incompatible";
    demand.message = "Falta zona horaria; intervalos no alineables.";
    demand.delta = null;
    await route.fulfill({ response, json: body });
  });
  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  const demand = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await demand.getByRole("button", { name: "Tabla", exact: true }).click();
  await expect(demand.getByRole("table").getByRole("row")).toHaveCount(5);
  await expect(demand).toContainText("Falta zona horaria");
});

test("El período de consulta hidráulico recorta tabla y descarga sin cambiar la preparación", async ({
  page,
}) => {
  const fixture = await openHistory(page, true);
  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await page
    .getByLabel("Ejecución de referencia")
    .selectOption(String(fixture.reference.id));
  await page.getByText("Período de consulta", { exact: true }).click();
  await page.getByLabel("Inicio de consulta (UTC)").fill("2026-10-20T01:00");
  await page
    .getByLabel("Fin exclusivo de consulta (UTC)")
    .fill("2026-10-20T02:00");
  await page.getByRole("button", { name: "Aplicar período" }).click();
  await expect(page).toHaveURL(/range_start=2026-10-20T01/);
  const panel = page.getByRole("tabpanel");
  await panel.getByRole("button", { name: "Tabla", exact: true }).click();
  await expect(panel.getByRole("table").first().getByRole("row")).toHaveCount(
    2,
  );
  const pending = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Exportar CSV de vistas visibles" })
    .click();
  const file = await pending;
  const csv = await readFile((await file.path())!, "utf8");
  expect(csv.trim().split(/\r?\n/)).toHaveLength(2);
  expect(csv).toContain("2026-10-20T01:00:00+00:00");
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Inicio de consulta (UTC)")).toHaveValue(
    "2026-10-20T01:00",
  );
  await page.getByText("Período de consulta", { exact: true }).click();
  await page.getByRole("button", { name: "Todo el run" }).click();
  await expect(panel.getByRole("table").first().getByRole("row")).toHaveCount(
    3,
  );
});

test("Historial vacío, fallo de conexión y descarga fallida permiten reintentar", async ({
  page,
}) => {
  const fixture = await openHistory(page);
  await page.route("**/mesa/history?*", (route) =>
    route.fulfill({ status: 503, json: { detail: "Sin conexión" } }),
  );
  await page.getByText("Historial de ejecuciones", { exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "No se pudo leer el historial",
  );
  await page.unroute("**/mesa/history?*");
  await page.route("**/mesa/history?*", (route) =>
    route.fulfill({ json: { case_id: fixture.case.id, runs: [] } }),
  );
  await page.getByRole("button", { name: "Reintentar historial" }).click();
  await expect(
    page.getByText("Sin ejecuciones en este contexto."),
  ).toBeVisible();
  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await page.route("**/mesa/comparison/export", (route) =>
    route.fulfill({ status: 503, json: { detail: "Sin conexión" } }),
  );
  await page
    .getByRole("button", { name: "Exportar CSV de vistas visibles" })
    .click();
  await expect(page.getByRole("alert")).toContainText("No se pudo exportar");
  await page.unroute("**/mesa/comparison/export");
  const pending = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Exportar CSV de vistas visibles" })
    .click();
  await pending;
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("Consultar un run recupera una vista eléctrica retirada del catálogo actual", async ({
  page,
}) => {
  const fixture = await openHistory(page);
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.route("**/api/scenarios/*/mesa?*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.components = body.components.filter(
      (c: { entity_id: string }) => c.entity_id !== "load_north",
    );
    await route.fulfill({ response, json: body });
  });
  await page.reload();
  await expect(page.getByRole("tabpanel")).toContainText(
    "No disponible · load_north",
  );
  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  const demand = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await expect(demand.getByRole("img")).toContainText("Después: 10 MW");
  await page
    .getByRole("button", { name: "Preparación actual", exact: true })
    .click();
  await expect(page.getByRole("tabpanel")).toContainText(
    "No disponible · load_north",
  );
});
