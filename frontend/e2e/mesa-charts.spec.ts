import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("series densas se agregan por ancho, muestran valores y recuperan detalle con zoom", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const start = Date.parse("2026-08-01T00:00:00Z");
  const hour = 3600000;
  await page.route("**/api/scenarios/*/mesa?*", async (route) => {
    const body = await (await route.fetch()).json();
    const component = body.components[0];
    component.series.timezone = "UTC";
    component.series.points = Array.from({ length: 2208 }, (_, i) => ({
      start: new Date(start + i * hour).toISOString(),
      end: new Date(start + (i + 1) * hour).toISOString(),
      value: i % 24,
    }));
    component.additional_series = [
      {
        ...component.series,
        signal_key: "generation_energy_mwh",
        name: "Energía generada",
        unit: "MWh",
        points: component.series.points.map((p: object) => ({
          ...p,
          value: 2,
        })),
      },
    ];
    await route.fulfill({ json: body });
  });
  await openMesa(page);
  await page.getByRole("button", { name: "Configurar Demanda Norte" }).click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  await dialog
    .getByRole("checkbox", { name: "Energía generada · MWh" })
    .check();
  await dialog.getByLabel("Eje Y · Energía generada").selectOption("secondary");
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  const panel = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  const chart = panel.locator(".mesa-chart");
  const line = chart.locator('g[data-series="load_demand_mw"]');
  await expect(line).toHaveAttribute("data-source-count", "2208");
  const bucketSize = Number(await line.getAttribute("data-bucket-size"));
  const originalCount = Number(await line.getAttribute("data-point-count"));
  expect(originalCount).toBeLessThan(150);
  expect(bucketSize).toBeGreaterThan(hour);
  await expect(panel.locator(".mesa-chart-toolbar")).toContainText(
    "Promedio cada",
  );
  await expect(panel.locator(".mesa-chart-toolbar")).toContainText("Suma cada");
  const area = chart.locator(".mesa-chart-hit-area");
  let box = (await area.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.7);
  const tooltip = panel.getByRole("tooltip");
  await expect(tooltip).toContainText("11,5 MW");
  await expect(tooltip).toContainText(`${(bucketSize / hour) * 2} MWh`);
  await expect(tooltip).toContainText("UTC");
  await expect(tooltip).toContainText("muestras");
  await page.screenshot({ path: testInfo.outputPath("agregacion-hover.png") });
  await page.mouse.move(box.x, box.y - 10);

  // A narrower panel groups more samples. Resizing back restores the resolution.
  await page.setViewportSize({ width: 800, height: 1000 });
  await expect
    .poll(async () => Number(await line.getAttribute("data-point-count")))
    .toBeLessThan(originalCount);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(line).toHaveAttribute("data-point-count", String(originalCount));
  box = (await area.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.7);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.25, box.y + box.height * 0.7, {
    steps: 8,
  });
  await expect(chart.locator(".mesa-chart-selection")).toBeVisible();
  await page.mouse.up();
  const reset = panel.getByRole("button", { name: "Restablecer zoom" });
  await expect(reset).toBeVisible();
  await expect
    .poll(async () => Number(await line.getAttribute("data-bucket-size")))
    .toBeLessThan(bucketSize);

  // Zoom again, in reverse, to recover original hourly samples.
  box = (await area.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.7);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.7, {
    steps: 8,
  });
  await page.mouse.up();
  await expect(line).toHaveAttribute("data-bucket-size", "0");
  await expect(panel.locator(".mesa-chart-toolbar")).toContainText(
    "Resolución original",
  );
  await panel.screenshot({ path: testInfo.outputPath("zoom-detalle.png") });
  await reset.click();
  await expect(line).toHaveAttribute("data-point-count", String(originalCount));
  await expect(chart).toHaveAttribute("data-range-start", String(start));
  await expect(chart).toHaveAttribute(
    "data-range-end",
    String(start + 2208 * hour),
  );

  await chart.focus();
  await page.keyboard.press("Home");
  await expect(tooltip).toContainText("11,5 MW");
  await page.keyboard.press("Shift+ArrowRight");
  await page.keyboard.press("Shift+ArrowRight");
  await page.keyboard.press("Enter");
  await expect(reset).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(reset).toHaveCount(0);
  expect(
    (await new AxeBuilder({ page }).include(".mesa-view").analyze()).violations,
  ).toEqual([]);

  await panel.getByRole("button", { name: "Tabla", exact: true }).click();
  const table = panel.getByRole("table", {
    name: "Demanda medida · MW",
    exact: true,
  });
  await expect(table.getByRole("columnheader")).toHaveText([
    "Inicio",
    "Demanda medida (MW)",
  ]);
  await expect(table.locator("tbody tr")).toHaveCount(2208);
  await expect(table.locator("tbody tr").first().getByRole("cell")).toHaveText([
    "2026-08-01T00:00:00.000Z",
    "0",
  ]);
  await panel.screenshot({ path: testInfo.outputPath("tabla-sin-fin.png") });
});

async function openMesa(page: Page, options = "") {
  const fixture = await (
    await page.request.get(
      `/api/auth/mesa-fixture?case_name=Ejes%20y%20altura${options}`,
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

test("las fechas de ejecución ajustan todos los gráficos y restablecen el zoom en preparación y comparación", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const fixture = await openMesa(page, "&comparison=true");
  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  await dialog.getByLabel("Título").fill("Otra vista");
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  await page.getByText("Preparar ejecución eléctrica", { exact: true }).click();
  const charts = page.locator(".mesa-chart");
  await expect(charts).toHaveCount(2);
  const area = charts.first().locator(".mesa-chart-hit-area");
  await area.scrollIntoViewIfNeeded();
  const box = (await area.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.5, {
    steps: 5,
  });
  await page.mouse.up();
  await expect(
    page.getByRole("button", { name: "Restablecer zoom" }),
  ).toBeVisible();
  await page
    .getByLabel("Fin de ejecución (exclusivo)")
    .fill("2026-10-20T01:00");
  await page
    .getByLabel("Inicio de ejecución", { exact: true })
    .fill("2026-10-20T00:30");
  await expect(
    page.getByRole("button", { name: "Restablecer zoom" }),
  ).toHaveCount(0);
  for (const mode of ["Preparación actual", "Comparar", "Antes", "Después"]) {
    await page.getByRole("button", { name: mode, exact: true }).click();
    await expect(charts).toHaveCount(2);
    for (const chart of await charts.all()) {
      await expect(chart).toHaveAttribute(
        "data-range-start",
        String(Date.parse("2026-10-20T03:30Z")),
      );
      await expect(chart).toHaveAttribute(
        "data-range-end",
        String(Date.parse("2026-10-20T04:00Z")),
      );
      for (const series of await chart.locator("g[data-series]").all())
        await expect(series).toHaveAttribute("data-source-count", "1");
    }
  }
  await page
    .getByLabel("Inicio de ejecución", { exact: true })
    .fill("2026-10-21T00:00");
  await expect(page.getByText(/Indica fechas válidas/)).toBeVisible();
  await expect(charts.first()).toHaveAttribute(
    "data-range-start",
    String(Date.parse("2026-10-20T03:30Z")),
  );
  await page
    .getByLabel("Fin de ejecución (exclusivo)")
    .fill("2026-10-22T00:00");
  await expect(
    page.getByText("Sin datos en el período de ejecución seleccionado.", {
      exact: true,
    }),
  ).toHaveCount(2);
  await page
    .getByLabel("Inicio de ejecución", { exact: true })
    .fill("2026-10-20T00:00");
  await page
    .getByLabel("Fin de ejecución (exclusivo)")
    .fill("2026-10-20T02:00");
  await page.getByLabel("Zona horaria de ejecución").fill("UTC");
  await expect(charts.first().locator("polyline")).toHaveCount(0);
  await page.getByLabel("Zona horaria de ejecución").fill("America/Santiago");
  await expect(charts.first()).toHaveAttribute(
    "data-range-start",
    String(Date.parse("2026-10-20T03:00Z")),
  );
});

test("centrales y unidades permiten seleccionar costo marginal y conservarlo al guardar", async ({
  page,
}, testInfo) => {
  const fixture = await openMesa(
    page,
    "&hydraulic=true&with_run=true&market_prices=true",
  );
  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  for (const entity of ["plant_1", "unit_1"]) {
    await page
      .getByRole("button", { name: "Agregar vista", exact: true })
      .click();
    const dialog = page.getByRole("dialog", { name: "Configurar vista" });
    const label = await dialog
      .getByRole("option")
      .filter({ hasText: ` · ${entity} ·` })
      .textContent();
    await dialog.getByLabel("Componente").selectOption({ label: label! });
    await dialog.getByLabel("Título").fill(entity);
    await dialog
      .getByRole("checkbox", { name: "Costo marginal · USD/MWh", exact: true })
      .check();
    await expect(dialog.getByLabel("Eje Y · Costo marginal")).toHaveValue(
      "secondary",
    );
    await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  }
  for (const mode of ["Preparación actual", "Comparar", "Antes", "Después"]) {
    await page.getByRole("button", { name: mode, exact: true }).click();
    for (const entity of ["plant_1", "unit_1"]) {
      const panel = page.getByRole("region", {
        name: `${entity === "plant_1" ? "Central" : "Unidad"} · ${entity}`,
        exact: true,
      });
      await expect(
        panel.locator('.mesa-chart g[data-series^="price_usd_per_mwh"]'),
      ).toHaveCount(mode === "Comparar" ? 2 : 1);
      await expect(
        panel.locator('.mesa-axis-labels [data-axis="secondary"]'),
      ).toHaveText("Eje Y secundario · USD/MWh");
      await panel.getByRole("button", { name: "Tabla", exact: true }).click();
      await expect(
        panel.getByRole("table", {
          name: "Costo marginal · USD/MWh",
          exact: true,
        }),
      ).toContainText("-20");
      await expect(
        panel.getByRole("table", {
          name: "Costo marginal · USD/MWh",
          exact: true,
        }),
      ).toContainText("80");
      await panel.getByRole("button", { name: "Gráfico", exact: true }).click();
    }
  }
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    page.locator('.mesa-chart g[data-series^="price_usd_per_mwh"]'),
  ).toHaveCount(2);
  await page.screenshot({
    path: testInfo.outputPath("costo-marginal-central-unidad.png"),
    fullPage: true,
  });
});

test("generación y caudal comparten un gráfico y un estado vacío antes de seleccionar resultados", async ({
  page,
}, testInfo) => {
  const fixture = await openMesa(page, "&hydraulic=true&with_run=true");
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  const plant = await dialog
    .getByRole("option")
    .filter({ hasText: " · plant_1 ·" })
    .textContent();
  await dialog.getByLabel("Componente").selectOption({ label: plant! });
  await dialog.getByLabel("Título").fill("Generación y caudal");
  await dialog
    .getByRole("checkbox", { name: "Caudal turbinado · m3/s" })
    .check();
  await dialog.getByLabel("Eje Y · Caudal turbinado").selectOption("secondary");
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();

  const panel = page.getByRole("region", {
    name: "Central · Generación y caudal",
    exact: true,
  });
  const chart = panel.getByRole("img", {
    name: "Potencia hidráulica · MW; Caudal turbinado · m3/s",
    exact: true,
  });
  const message = "Sin resultado disponible. Selecciona una ejecución exitosa.";
  await expect(chart).toHaveCount(1);
  await expect(chart.locator("polyline")).toHaveCount(0);
  await expect(chart.locator("text")).toHaveCount(0);
  await expect(panel.getByRole("status")).toHaveCount(1);
  await expect(panel.getByRole("status")).toHaveText(message);
  await expect(
    panel.getByRole("group", { name: "Leyenda del gráfico" }),
  ).toContainText("Potencia hidráulica (MW) · Primario · Sin datos");
  await expect(
    panel.getByRole("group", { name: "Leyenda del gráfico" }),
  ).toContainText("Caudal turbinado (m3/s) · Secundario · Sin datos");
  await expect(
    panel.locator('.mesa-axis-labels [data-axis="primary"]'),
  ).toHaveText("Eje Y primario · MW");
  await expect(
    panel.locator('.mesa-axis-labels [data-axis="secondary"]'),
  ).toHaveText("Eje Y secundario · m3/s");
  await panel.screenshot({
    path: testInfo.outputPath("central-sin-resultados.png"),
  });
  const emptyMessage = (await panel.getByRole("status").boundingBox())!;
  const legend = (await panel
    .getByRole("group", { name: "Leyenda del gráfico" })
    .boundingBox())!;
  expect(emptyMessage.y + emptyMessage.height).toBeLessThanOrEqual(legend.y);
  expect(
    (await new AxeBuilder({ page }).include(".mesa-view").analyze()).violations,
  ).toEqual([]);

  await page
    .getByLabel("Resultados de ejecución")
    .selectOption(String(fixture.run.id));
  await expect(chart).toHaveCount(1);
  await expect(chart.locator("polyline")).toHaveCount(2);
  await expect(chart).toContainText("3 MW");
  await expect(chart).toContainText("4 m3/s");
  await expect(panel.locator(".mesa-chart-empty")).toHaveCount(0);
  await panel.screenshot({
    path: testInfo.outputPath("central-con-resultados.png"),
  });

  await page.getByLabel("Resultados de ejecución").selectOption("");
  await expect(chart.locator("polyline")).toHaveCount(0);
  await expect(panel.getByRole("status")).toHaveText(message);
  await panel.getByRole("button", { name: "Tabla", exact: true }).click();
  await expect(panel.getByRole("img")).toHaveCount(0);
  await expect(panel.getByRole("status")).toHaveCount(2);
  await panel.getByRole("button", { name: "Gráfico", exact: true }).click();
  await expect(chart).toHaveCount(1);
  await expect(panel.getByRole("status")).toHaveCount(1);
  await page.setViewportSize({ width: 390, height: 844 });
  await panel.screenshot({
    path: testInfo.outputPath("central-sin-resultados-movil.png"),
  });
  const mobileMessage = (await panel.getByRole("status").boundingBox())!;
  const mobileLegend = (await panel
    .getByRole("group", { name: "Leyenda del gráfico" })
    .boundingBox())!;
  expect(mobileMessage.y + mobileMessage.height).toBeLessThanOrEqual(
    mobileLegend.y,
  );
});

test("dos ejes admiten muchas series, unidades mixtas y conservan escalas al guardar", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.route("**/api/scenarios/*/mesa?*", async (route) => {
    const body = await (await route.fetch()).json();
    const component = body.components[0];
    component.additional_series = Array.from({ length: 14 }, (_, i) => ({
      ...component.series,
      signal_key: `extra_${i}`,
      name: `Serie ${i + 1}`,
      unit: i === 0 ? "USD/MWh" : "m3/s",
      points: component.series.points.map((p: { value: number }) => ({
        ...p,
        value: p.value * 100,
      })),
    }));
    await route.fulfill({ json: body });
  });
  await openMesa(page);
  await page.getByRole("button", { name: "Configurar Demanda Norte" }).click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  await dialog
    .getByRole("checkbox", { name: "Serie 1 · USD/MWh", exact: true })
    .check();
  await dialog
    .getByLabel("Eje Y · Serie 1", { exact: true })
    .selectOption("secondary");
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  const chart = page.locator(".mesa-chart");
  await expect(chart).toHaveCount(1);
  await expect(
    page.locator('.mesa-axis-labels [data-axis="primary"]'),
  ).toHaveText("Eje Y primario · MW");
  await expect(
    page.locator('.mesa-axis-labels [data-axis="secondary"]'),
  ).toHaveText("Eje Y secundario · USD/MWh");
  // A hundredfold change in magnitude must occupy the same plot range on its own axis.
  await expect
    .poll(async () => {
      const values = await chart
        .locator("polyline")
        .evaluateAll((nodes) =>
          nodes.map((node) =>
            node.getAttribute("points")!.split(/[ ,]/).map(Number),
          ),
        );
      return (
        values.length === 2 &&
        values[0].every(
          (value, index) => Math.abs(value - values[1][index]) < 0.01,
        )
      );
    })
    .toBe(true);
  await page.getByRole("button", { name: "Configurar Demanda Norte" }).click();
  for (const checkbox of await dialog.getByRole("checkbox").all())
    await checkbox.check();
  for (let i = 1; i <= 14; i++)
    await dialog
      .getByLabel(`Eje Y · Serie ${i}`, { exact: true })
      .selectOption("secondary");
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  await expect(chart.locator('g[data-axis="secondary"]')).toHaveCount(14);
  await expect(
    page.locator('.mesa-axis-labels [data-axis="secondary"]'),
  ).toContainText("Múltiples unidades: USD/MWh / m3/s");
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(chart.locator('g[data-axis="secondary"]')).toHaveCount(14);
  await expect(
    page.locator('.mesa-axis-labels [data-axis="secondary"]'),
  ).toContainText("Múltiples unidades");
  // Primary may be empty; all selected series can share the secondary axis.
  await page.getByRole("button", { name: "Configurar Demanda Norte" }).click();
  await dialog.getByLabel("Eje Y · Demanda medida").selectOption("secondary");
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  await expect(chart.locator('g[data-axis="secondary"]')).toHaveCount(15);
  await expect(
    page.locator('.mesa-axis-labels [data-axis="primary"]'),
  ).toBeEmpty();
  await page.screenshot({
    path: testInfo.outputPath("mesa-ejes.png"),
    fullPage: true,
  });
  expect(
    (await new AxeBuilder({ page }).include(".mesa-view").analyze()).violations,
  ).toEqual([]);
});

test("arrastrar agranda ambos gráficos de la fila, conserva el ancho y persiste la altura", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await openMesa(page);
  for (const title of ["Segundo gráfico", "Otra fila"]) {
    await page
      .getByRole("button", { name: "Agregar vista", exact: true })
      .click();
    const dialog = page.getByRole("dialog", { name: "Configurar vista" });
    await dialog.getByLabel("Título").fill(title);
    await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  }
  const panels = page.locator(".mesa-panel");
  const dimensions = () =>
    panels.evaluateAll((nodes) =>
      nodes.map((node) => ({
        height: node.getBoundingClientRect().height,
        width: node.getBoundingClientRect().width,
      })),
    );
  const before = await dimensions();
  const plot = panels.first().locator(".mesa-chart-plot");
  const plotBefore = (await plot.boundingBox())!.height;
  const handle = page.getByRole("button", {
    name: "Ajustar altura de la fila 1",
    exact: true,
  });
  const box = (await handle.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box.x + box.width / 2 + 90,
    box.y + box.height / 2 + 210,
    { steps: 12 },
  );
  await page.mouse.up();
  await expect
    .poll(async () => (await dimensions())[0].height)
    .toBeGreaterThan(before[0].height + 190);
  const after = await dimensions();
  expect(after[0].height).toBe(after[1].height);
  expect(after[2].height).toBe(before[2].height);
  expect(after.map((d) => d.width)).toEqual(before.map((d) => d.width));
  expect((await plot.boundingBox())!.height).toBeGreaterThan(plotBefore + 190);
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(panels).toHaveCount(3);
  expect(await dimensions()).toEqual(after);
  await handle.scrollIntoViewIfNeeded();
  const edge = (await handle.boundingBox())!;
  await page.mouse.move(edge.x + edge.width / 2, edge.y + edge.height / 2);
  await page.mouse.down();
  await page.mouse.move(edge.x + edge.width / 2, 1096, { steps: 8 });
  await expect
    .poll(async () => (await dimensions())[0].height)
    .toBeGreaterThan(1200);
  await page.mouse.up();
  const mouseTall = await dimensions();
  expect(mouseTall[0].height).toBe(mouseTall[1].height);
  // Keyboard resizing can keep growing past the viewport, without an upper cap.
  await handle.focus();
  for (let i = 0; i < 30; i++) await page.keyboard.press("ArrowDown");
  const tall = await dimensions();
  expect(tall[0].height).toBe(mouseTall[0].height + 1200);
  expect(tall[1].height).toBe(tall[0].height);
  await page.screenshot({
    path: testInfo.outputPath("mesa-altura.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    (await new AxeBuilder({ page }).include(".mesa-view").analyze()).violations,
  ).toEqual([]);
});
