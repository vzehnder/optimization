import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function openComparison(page: Page) {
  const fixture = await (
    await page.request.get(
      "/api/auth/mesa-fixture?case_name=Comparación%20hidráulica&hydraulic=true&comparison=true",
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

async function addView(
  page: Page,
  entity: string,
  title: string,
  signals: string[],
  edit = false,
) {
  await page
    .getByRole("button", {
      name: edit ? "Configurar Embalse Alto" : "Agregar vista",
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  const label = await dialog
    .getByRole("option")
    .filter({ hasText: new RegExp(` · ${entity} ·`) })
    .textContent();
  await dialog.getByLabel("Componente").selectOption({ label: label! });
  await dialog.getByLabel("Título").fill(title);
  for (const box of await dialog.getByRole("checkbox").all())
    await box.uncheck();
  for (const signal of signals)
    await dialog.getByRole("checkbox", { name: new RegExp(signal) }).check();
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  return page
    .locator(".mesa-panel")
    .filter({ has: page.getByRole("heading", { name: title, exact: true }) });
}

test("La comparación hidráulica conserva muestras y parámetros ejecutados con escalas independientes", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await openComparison(page);
  const reservoir = await addView(page, "reservoir", "Agua histórica", [
    "Aporte natural",
    "Volumen almacenado",
    "Cota del embalse",
  ]);
  const plant = await addView(page, "plant_1", "Central histórica", [
    "Potencia hidráulica",
    "Caudal turbinado",
  ]);
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await expect(
    reservoir.getByRole("img", { name: "Volumen almacenado · hm3" }),
  ).toContainText("Después: 9.8 hm3");
  await expect(reservoir).toContainText("Sin referencia previa");
  await reservoir.getByText("Parámetros ejecutados", { exact: true }).click();
  await expect(
    reservoir.getByRole("row", { name: "Volumen inicial 10 hm3" }),
  ).toBeVisible();
  await expect(reservoir).toContainText(
    `Snapshot #${fixture.run.scenario_version_id}`,
  );
  await reservoir.getByText("Parámetros ejecutados", { exact: true }).click();
  await expect(
    plant.getByRole("img", { name: "Potencia hidráulica · MW" }),
  ).toContainText("Después: 3 MW");
  await expect(
    plant.getByRole("img", { name: "Caudal turbinado · m3/s" }),
  ).toContainText("Después: 4 m3/s");
  await page
    .getByLabel("Ejecución de referencia")
    .selectOption(String(fixture.reference.id));
  await expect(
    reservoir.getByRole("img", { name: "Volumen almacenado · hm3" }),
  ).toContainText("Antes: 10 hm3");
  await reservoir.getByRole("button", { name: "Tabla", exact: true }).click();
  const volume = reservoir.getByRole("table", {
    name: "Volumen almacenado · hm3",
    exact: true,
  });
  await expect(volume.getByRole("row").nth(1)).toContainText("10");
  await expect(volume.getByRole("row").nth(1)).toContainText("9.8");
  const values = await volume
    .getByRole("row")
    .nth(1)
    .getByRole("cell")
    .allTextContents();
  expect(Number(values[4])).toBeCloseTo(-0.2);
  await expect(
    reservoir
      .getByRole("table", { name: "Aporte natural · m3/s", exact: true })
      .getByRole("row")
      .nth(1),
  ).toContainText("0");
  await page.getByRole("button", { name: "Después", exact: true }).click();
  await expect(
    volume.getByRole("columnheader", {
      name: "Volumen almacenado · Después (hm3)",
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  const diagramPath = `/api/scenarios/${fixture.scenario.id}/hydraulic-diagram`;
  const { diagram } = await (await page.request.get(diagramPath)).json();
  const current = diagram.nodes.find(
    (n: { technical_key: string }) => n.technical_key === "reservoir",
  );
  current.display_name = "Embalse editado";
  current.reservoir.initial_storage_hm3 = 15;
  current.natural_inflow_series.points[0].value_m3s = 99;
  const csrf = await (await page.request.get("/api/auth/csrf")).json();
  expect(
    (
      await page.request.put(diagramPath, {
        data: {
          revision: diagram.revision,
          nodes: diagram.nodes,
          reaches: diagram.reaches,
        },
        headers: { "X-CSRF-Token": csrf.csrf_token },
      })
    ).ok(),
  ).toBe(true);
  await page.reload();
  await expect(volume.getByRole("row").nth(1)).toContainText("9.8");
  await expect(reservoir).toContainText("Entidad ejecutada: Embalse Alto");
  await expect(reservoir).not.toContainText("Embalse editado");
  await reservoir.getByText("Parámetros ejecutados", { exact: true }).click();
  await expect(
    reservoir.getByRole("row", { name: "Volumen inicial 10 hm3" }),
  ).toBeVisible();
  await reservoir.getByText("Parámetros ejecutados", { exact: true }).click();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-hidraulica-comparacion-1440.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-hidraulica-comparacion-390.png"),
    fullPage: true,
  });
});

test("La matriz hidráulica muestra potencia caudal volumen y cota con procedencia a 1440 y 390 px", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await openComparison(page);
  await addView(
    page,
    "plant_1",
    "Potencia de central",
    ["Potencia hidráulica"],
    true,
  );
  await addView(page, "unit_1", "Caudal de unidad", ["Caudal turbinado"]);
  const volume = await addView(page, "reservoir", "Volumen de embalse", [
    "Volumen almacenado",
  ]);
  await addView(page, "reservoir", "Cota de embalse", ["Cota del embalse"]);
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await page
    .getByLabel("Ejecución de referencia")
    .selectOption(String(fixture.reference.id));
  await expect(page.locator(".mesa-comparison-origins")).toHaveCount(4);
  await volume.getByRole("button", { name: "Tabla", exact: true }).click();
  await page.screenshot({
    path: testInfo.outputPath("mesa-hidraulica-matriz-layout.png"),
  });
  for (const panel of await page.locator(".mesa-panel").all()) {
    const box = (await panel.boundingBox())!;
    expect(box.y + box.height).toBeLessThanOrEqual(900);
    const footer = (await panel
      .locator(".mesa-comparison-origins")
      .boundingBox())!;
    expect(footer.y + footer.height).toBeLessThanOrEqual(
      box.y + box.height - 4,
    );
    for (const chart of await panel.getByRole("img").all())
      expect((await chart.boundingBox())!.height).toBeGreaterThanOrEqual(80);
  }
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-hidraulica-matriz-1440.png"),
  });
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.route("**/mesa/hydraulic-execution?*", (route) =>
    route.fulfill({ json: { run: fixture.run } }),
  );
  await page.reload();
  await expect(
    page.getByText(`Ejecución hidráulica #${fixture.run.id}`, { exact: true }),
  ).toBeVisible();
  for (const panel of await page.locator(".mesa-panel").all()) {
    const box = (await panel.boundingBox())!;
    expect(box.y + box.height).toBeLessThanOrEqual(900);
    const origin = (await panel
      .locator(".mesa-comparison-origins")
      .boundingBox())!;
    expect(origin.y + origin.height).toBeLessThanOrEqual(
      box.y + box.height - 4,
    );
    await expect(panel.locator(".mesa-comparison-origins")).toBeInViewport({
      ratio: 1,
    });
    for (const chart of await panel.getByRole("img").all())
      expect((await chart.boundingBox())!.height).toBeGreaterThanOrEqual(80);
  }
  await page.screenshot({
    path: testInfo.outputPath("mesa-hidraulica-run-1440.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("mesa-hidraulica-matriz-390.png"),
    fullPage: true,
  });
  for (const panel of await page.locator(".mesa-panel").all()) {
    const box = (await panel.boundingBox())!;
    const footer = (await panel
      .locator(".mesa-comparison-origins")
      .boundingBox())!;
    expect(footer.y + footer.height).toBeLessThanOrEqual(
      box.y + box.height - 4,
    );
    for (const chart of await panel.getByRole("img").all()) {
      const chartBox = (await chart.boundingBox())!;
      for (const label of await chart.locator("text").all())
        expect((await label.boundingBox())!.x).toBeGreaterThanOrEqual(
          chartBox.x,
        );
    }
  }
});
