import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function openMesa(page: Page) {
  const fixture = await (
    await page.request.get(
      `/api/auth/mesa-fixture?case_name=Cuadricula-${Date.now()}`,
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
}

test("cuadrícula 6x6 mantiene los controles dentro del bloque y admite selección inversa", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openMesa(page);
  await page.getByLabel("Filas", { exact: true }).selectOption("6");
  await page.getByLabel("Columnas", { exact: true }).selectOption("6");
  await expect(page.locator(".mesa-empty-cell")).toHaveCount(35);
  const panel = (await page.locator(".mesa-panel").boundingBox())!;
  const configure = page.getByRole("button", {
    name: "Configurar Demanda Norte",
    exact: true,
  });
  const control = (await configure.boundingBox())!;
  expect(control.x + control.width).toBeLessThanOrEqual(panel.x + panel.width);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await configure.click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  await dialog
    .getByRole("button", { name: "Elegir espacio", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Fila 6, columna 6 · Libre", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Fila 5, columna 4 · Libre", exact: true })
    .click();
  await dialog.getByRole("button", { name: "Usar este espacio" }).click();
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  await expect(page.locator(".mesa-cell")).toHaveCSS("grid-row", "5 / span 2");
  await expect(page.locator(".mesa-cell")).toHaveCSS(
    "grid-column",
    "4 / span 3",
  );
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator(".mesa-cell")).toHaveCSS(
    "grid-column",
    "4 / span 3",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await configure.click();
  await dialog
    .getByRole("button", { name: "Elegir espacio", exact: true })
    .click();
  const map = dialog.locator(".mesa-space-map");
  expect(
    await map.evaluate((node) => node.scrollWidth <= node.clientWidth),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("selector-6x6-movil.png"),
  });
});

test("rectángulos persistentes impiden solapamientos interiores y reducciones fuera de límites", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openMesa(page);
  await page.getByLabel("Filas", { exact: true }).selectOption("3");
  await page.getByLabel("Columnas", { exact: true }).selectOption("3");
  await page
    .getByRole("button", {
      name: "Agregar vista en fila 2, columna 2",
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  await dialog.getByLabel("Título").fill("Vista central");
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  await page
    .getByRole("button", { name: "Configurar Demanda Norte", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Elegir espacio", exact: true })
    .click();
  const cell = (row: number, column: number) =>
    dialog.getByRole("button", {
      name: `Fila ${row}, columna ${column} · Libre`,
      exact: true,
    });
  await expect(
    dialog.getByRole("button", {
      name: "Fila 2, columna 2 · Ocupada por Vista central",
    }),
  ).toHaveAttribute("aria-disabled", "true");
  await cell(1, 1).click();
  await cell(3, 3).click();
  await expect(dialog.getByRole("status")).toContainText(
    "se solapa con «Vista central»",
  );
  await expect(
    dialog.getByRole("button", { name: "Usar este espacio" }),
  ).toBeDisabled();
  await expect(
    dialog.getByRole("button", { name: "Aplicar", exact: true }),
  ).toBeDisabled();
  await page.screenshot({
    path: testInfo.outputPath("solapamiento-bloqueado.png"),
  });
  // Both corners were free; the occupied middle cell must still block the rectangle.
  await cell(3, 1).click();
  await expect(dialog.getByRole("status")).toContainText(
    "Filas 1–3 · columna 1",
  );
  await dialog.getByRole("button", { name: "Usar este espacio" }).click();
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  const cells = page.locator(".mesa-cell");
  await expect(cells.first()).toHaveCSS("grid-row", "1 / span 3");
  const main = (await cells.first().boundingBox())!;
  const other = (await cells.nth(1).boundingBox())!;
  expect(main.x + main.width).toBeLessThanOrEqual(other.x);
  expect(main.height).toBeGreaterThan(other.height * 3);
  await page.getByRole("button", { name: "Guardar mesa", exact: true }).click();
  await expect(page.getByText("Mesa guardada", { exact: true })).toBeVisible();
  await page.reload();
  await expect(cells.first()).toHaveCSS("grid-row", "1 / span 3");
  await expect(page.getByLabel("Columnas", { exact: true })).toHaveValue("3");
  await page.getByLabel("Filas", { exact: true }).selectOption("2");
  await expect(page.getByRole("alert")).toContainText("Demanda Norte");
  await expect(page.getByLabel("Filas", { exact: true })).toHaveValue("3");
  await page.screenshot({
    path: testInfo.outputPath("cuadricula-rectangular.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const boxes = await cells.evaluateAll((nodes) =>
    nodes.map((node) => ({
      top: node.getBoundingClientRect().top,
      bottom: node.getBoundingClientRect().bottom,
    })),
  );
  expect(boxes[0].bottom).toBeLessThanOrEqual(boxes[1].top);
  expect(
    (await new AxeBuilder({ page }).include(".mesa-view").analyze()).violations,
  ).toEqual([]);
});

test("selección por teclado, cancelación y liberación de celdas en una cuadrícula llena", async ({
  page,
}, testInfo) => {
  await openMesa(page);
  await page
    .getByRole("button", { name: "Configurar Demanda Norte", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Configurar vista" });
  const choose = dialog.getByRole("button", {
    name: "Elegir espacio",
    exact: true,
  });
  await choose.click();
  const first = dialog.getByRole("button", {
    name: "Fila 1, columna 1 · Libre",
    exact: true,
  });
  await first.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await dialog.getByRole("button", { name: "Usar este espacio" }).click();
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Agregar vista", exact: true }),
  ).toBeDisabled();
  await expect(page.locator(".mesa-empty-cell")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Configurar Demanda Norte", exact: true })
    .click();
  await choose.click();
  await first.click();
  await dialog.getByRole("button", { name: "Cancelar selección" }).click();
  await expect(dialog.getByLabel("Espacio en la cuadrícula")).toContainText(
    "Filas 1–2 · columnas 1–2",
  );
  await choose.click();
  await first.click();
  await dialog.getByRole("button", { name: "Usar este espacio" }).click();
  await dialog.getByRole("button", { name: "Aplicar", exact: true }).click();
  await expect(page.locator(".mesa-empty-cell")).toHaveCount(3);
  await expect(
    page.getByRole("button", { name: "Agregar vista", exact: true }),
  ).toBeEnabled();
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("button", { name: "Configurar Demanda Norte", exact: true })
    .click();
  await choose.click();
  await page.screenshot({ path: testInfo.outputPath("selector-movil.png") });
  expect(
    (await new AxeBuilder({ page }).include(".mesa-dialog").analyze())
      .violations,
  ).toEqual([]);
});
