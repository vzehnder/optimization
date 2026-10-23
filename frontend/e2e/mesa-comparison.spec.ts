import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function openComparison(page: Page) {
  const fixture = await (
    await page.request.get(
      "/api/auth/mesa-fixture?case_name=Comparación&comparison=true",
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
    `/react/scenarios/${fixture.scenario.id}/mesa?case=${fixture.case.id}&variant=${fixture.variant.id}&run=${fixture.run.id}`,
  );
  return fixture;
}

async function addBattery(page: Page) {
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
  return page.getByRole("region", { name: "BESS · BESS Norte", exact: true });
}

test("Comparar conserva entradas congeladas y sincroniza antes, después y delta en tabla y gráfico", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await openComparison(page);
  const battery = await addBattery(page);
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await expect(battery).toContainText("Sin referencia previa");
  await page
    .getByLabel("Ejecución de referencia")
    .selectOption(String(fixture.reference.id));
  await expect(
    battery.getByRole("img", { name: "Descarga BESS · MW" }),
  ).toContainText("Antes: 1 MW");
  await expect(battery.getByRole("img")).toContainText("Después: 2 MW");
  await battery.getByRole("button", { name: "Tabla", exact: true }).click();
  const table = battery.getByRole("table", { name: "Descarga BESS · MW" });
  await expect(
    table.getByRole("columnheader", {
      name: "Descarga BESS · Antes (MW)",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    table.getByRole("cell", { name: "-3", exact: true }),
  ).toBeVisible();
  await expect(battery).toContainText(`Antes · Run #${fixture.reference.id}`);
  await expect(battery).toContainText(`Después · Run #${fixture.run.id}`);
  await page.getByRole("button", { name: "Después", exact: true }).click();
  await expect(
    table.getByRole("columnheader", {
      name: "Descarga BESS · Después (MW)",
      exact: true,
    }),
  ).toBeVisible();
  await expect(table.getByRole("columnheader", { name: /Antes/ })).toHaveCount(
    0,
  );
  await page.getByRole("button", { name: "Antes", exact: true }).click();
  await expect(
    table.getByRole("cell", { name: "3", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Preparación actual", exact: true })
    .click();
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
  await editor.getByLabel("Valor del intervalo 1 (MW)").fill("12");
  await editor.getByLabel("Motivo del cambio").fill("Edición posterior al run");
  await editor.getByLabel("Confirmo el alcance de esta edición").check();
  await editor
    .getByRole("button", { name: "Guardar entrada", exact: true })
    .click();
  await expect(editor).not.toBeVisible();
  await expect(
    page.getByText(/Preparación pendiente de revalidación/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await expect(
    demand.getByRole("cell", { name: "10", exact: true }),
  ).toHaveCount(2);
  await expect(demand).toContainText("Entrada exógena sin cambio");
  await expect(
    demand.getByRole("button", { name: "Editar entrada", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Comparar", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    demand.getByRole("cell", { name: "10", exact: true }),
  ).toHaveCount(2);
  await page.screenshot({
    path: testInfo.outputPath("mesa-comparacion-1440.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-comparacion-390.png"),
    fullPage: true,
  });
});

test("Cuatro paneles de comparación mantienen sus orígenes visibles a 1440 px", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await openComparison(page);
  await addBattery(page);
  for (const [title, key, signal] of [
    ["Energía BESS", "battery_1", "Energía almacenada"],
    ["Solar disponible", "solar_north", "Disponibilidad solar"],
  ]) {
    await page
      .getByRole("button", { name: "Agregar vista", exact: true })
      .click();
    const dialog = page.getByRole("dialog", { name: "Configurar vista" });
    const label = await dialog
      .getByRole("option")
      .filter({ hasText: key })
      .textContent();
    await dialog.getByLabel("Componente").selectOption({ label: label! });
    await dialog.getByLabel("Título").fill(title);
    for (const checkbox of await dialog.getByRole("checkbox").all())
      await checkbox.uncheck();
    await dialog.getByRole("checkbox", { name: new RegExp(signal) }).check();
    await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  }
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await page
    .getByLabel("Ejecución de referencia")
    .selectOption(String(fixture.reference.id));
  await expect(page.locator(".mesa-comparison-origins")).toHaveCount(4);
  const demand = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await demand.getByRole("button", { name: "Tabla", exact: true }).click();
  for (const panel of await page.locator(".mesa-panel").all()) {
    const box = (await panel.boundingBox())!;
    const footer = (await panel
      .locator(".mesa-comparison-origins")
      .boundingBox())!;
    expect(box.y + box.height).toBeLessThanOrEqual(900);
    expect(footer.y + footer.height).toBeLessThanOrEqual(
      box.y + box.height - 4,
    );
    for (const chart of await panel.getByRole("img").all()) {
      expect((await chart.boundingBox())!.height).toBeGreaterThanOrEqual(80);
    }
  }
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-comparacion-cuatro-1440.png"),
  });
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.route("**/mesa/execution?*", (route) =>
    route.fulfill({ json: { run: fixture.run } }),
  );
  await page.reload();
  await expect(
    page.getByText(`Ejecución #${fixture.run.id}`, { exact: true }),
  ).toBeVisible();
  for (const panel of await page.locator(".mesa-panel").all()) {
    const box = (await panel.boundingBox())!;
    expect(box.y + box.height).toBeLessThanOrEqual(900);
    for (const chart of await panel.getByRole("img").all())
      expect((await chart.boundingBox())!.height).toBeGreaterThanOrEqual(80);
  }
  await page.screenshot({
    path: testInfo.outputPath("mesa-comparacion-run-1440.png"),
  });
});

test("Una referencia tardía no reemplaza la selección nueva y el error permite reintentar", async ({
  page,
}) => {
  const fixture = await openComparison(page);
  const battery = await addBattery(page);
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await expect(battery).toContainText("Sin referencia previa");
  let release!: () => void;
  let finished!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const completed = new Promise<void>((resolve) => {
    finished = resolve;
  });
  let delayed = true;
  let failed = false;
  await page.route("**/mesa/comparison?*", async (route) => {
    if (!new URL(route.request().url()).searchParams.has("reference_run_id"))
      return route.continue();
    if (delayed) {
      const response = await route.fetch();
      await gate;
      await route.fulfill({ response }).catch(() => {});
      finished();
    } else if (failed) {
      await route.fulfill({
        status: 503,
        json: { detail: "Comparación temporalmente no disponible" },
      });
    } else await route.continue();
  });
  const requested = page.waitForRequest((r) =>
    r.url().includes("reference_run_id="),
  );
  await page
    .getByLabel("Ejecución de referencia")
    .selectOption(String(fixture.reference.id));
  await requested;
  try {
    await expect(
      page.getByText("Cargando series del contexto seleccionado…"),
    ).toHaveCount(2);
    await page.getByLabel("Ejecución de referencia").selectOption("");
    await expect(battery).toContainText("Sin referencia previa");
  } finally {
    release();
  }
  await completed;
  await expect(page.getByLabel("Ejecución de referencia")).toHaveValue("");
  await expect(battery).toContainText("Sin referencia previa");
  delayed = false;
  failed = true;
  await page
    .getByLabel("Ejecución de referencia")
    .selectOption(String(fixture.reference.id));
  await expect(page.getByText(/No se pudo comparar/)).toHaveCount(2);
  await expect(page.locator(".mesa-comparison-signal")).toHaveCount(0);
  failed = false;
  await page
    .getByRole("button", { name: "Reintentar comparación" })
    .first()
    .click();
  await expect(battery).toContainText(`Antes · Run #${fixture.reference.id}`);
});

test("Cambiar fechas y caso descarta comparaciones del contexto anterior", async ({
  page,
}) => {
  const fixture = await openComparison(page);
  const demand = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await demand.getByRole("button", { name: "Tabla", exact: true }).click();
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await expect(
    demand.getByRole("cell", { name: "10", exact: true }),
  ).toHaveCount(2);
  let release!: () => void;
  let finished!: () => void;
  let entered!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const completed = new Promise<void>((resolve) => {
    finished = resolve;
  });
  const requested = new Promise<void>((resolve) => {
    entered = resolve;
  });
  await page.route("**/mesa/comparison?*", async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("range_start") !== "2026-10-20T00:00:00-03:00")
      return route.continue();
    const response = await route.fetch();
    entered();
    await gate;
    await route.fulfill({ response }).catch(() => {});
    finished();
  });
  const navigate = async (url: URL) =>
    page.evaluate((href) => {
      history.pushState(null, "", href);
      dispatchEvent(new PopStateEvent("popstate"));
    }, url.href);
  const first = new URL(page.url());
  first.searchParams.set("range_start", "2026-10-20T00:00:00-03:00");
  first.searchParams.set("range_end", "2026-10-20T01:00:00-03:00");
  await navigate(first);
  await requested;
  const second = new URL(first);
  second.searchParams.set("range_start", "2026-10-20T01:00:00-03:00");
  second.searchParams.set("range_end", "2026-10-20T02:00:00-03:00");
  try {
    await navigate(second);
    await expect(
      demand.getByRole("cell", { name: "12", exact: true }),
    ).toHaveCount(2);
    await expect(
      demand.getByRole("cell", { name: "10", exact: true }),
    ).toHaveCount(0);
    const other = await (
      await page.request.get(
        "/api/auth/mesa-fixture?case_name=Otro%20contexto&comparison=true",
      )
    ).json();
    const next = new URL(
      `/react/scenarios/${other.scenario.id}/mesa?case=${other.case.id}&variant=${other.variant.id}&run=${other.run.id}&comparison=compare`,
      page.url(),
    );
    await navigate(next);
    await expect(demand).toContainText(`Después · Run #${other.run.id}`);
    await expect(demand).not.toContainText(`Run #${fixture.run.id} ·`);
  } finally {
    release();
  }
  await completed;
  await expect(
    page.getByRole("link", { name: "Otro contexto", exact: true }),
  ).toBeVisible();
  await expect(demand).not.toContainText(`Run #${fixture.run.id} ·`);
});
