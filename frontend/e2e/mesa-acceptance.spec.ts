import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { writeFile } from "node:fs/promises";

test("La ayuda acompaña el acceso desde el escenario y devuelve el foco sin perder la mesa", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await (
    await page.request.get(
      "/api/auth/mesa-fixture?case_name=Aceptación%20mesa&electrical=true",
    )
  ).json();
  const csrf = await (await page.request.get("/api/auth/csrf")).json();
  expect(
    (
      await page.request.post("/api/auth/login", {
        data: {
          email: "mesa@example.local",
          password: "mesa test pass",
          next: "/react/projects",
        },
        headers: { "X-CSRF-Token": csrf.csrf_token },
      })
    ).ok(),
  ).toBe(true);
  await page.goto(
    `/react/scenarios/${fixture.scenario.id}?section=data&variant=${fixture.variant.id}`,
  );
  await page.getByRole("link", { name: "Abrir mesa de optimización" }).click();
  await expect(page).toHaveURL(
    new RegExp(
      `/mesa\\?case=${fixture.case.id}&variant=${fixture.variant.id}$`,
    ),
  );
  const demand = page.getByRole("region", {
    name: "Demanda · Demanda Norte",
    exact: true,
  });
  await demand.getByRole("button", { name: "Tabla", exact: true }).click();
  const help = page.getByRole("button", {
    name: "Cómo usar la mesa",
    exact: true,
  });
  await expect(help).toBeVisible();
  await help.focus();
  await page.keyboard.press("Enter");
  const guide = page.getByRole("dialog", {
    name: "Cómo usar la mesa",
    exact: true,
  });
  await expect(guide).toBeVisible();
  await expect(guide).toContainText("Guardar mesa");
  await expect(guide).toContainText("fin exclusivo");
  await expect(guide).toContainText("Sin referencia previa");
  await expect(guide).toContainText("Historial de ejecuciones");
  await expect(guide).toContainText("Exportar CSV de vistas visibles");
  await expect(guide).toContainText("Vincular revisión publicada");
  await expect(
    guide.getByRole("button", { name: "Cerrar ayuda" }),
  ).toBeFocused();
  await page.screenshot({ path: testInfo.outputPath("mesa-ayuda-1440.png") });
  await writeFile(
    testInfo.outputPath("mesa-entorno.json"),
    JSON.stringify(
      {
        browser: page.context().browser()?.version(),
        viewport: page.viewportSize(),
        ...(await page.evaluate(() => ({
          dpr: devicePixelRatio,
          locale: navigator.language,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          font: getComputedStyle(document.body).fontFamily,
          colorScheme: matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light",
          reducedMotion: matchMedia("(prefers-reduced-motion: reduce)").matches,
        }))),
      },
      null,
      2,
    ),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const closeBox = await guide
    .getByRole("button", { name: "Cerrar ayuda" })
    .boundingBox();
  expect(closeBox!.y).toBeGreaterThanOrEqual(0);
  expect(closeBox!.y + closeBox!.height).toBeLessThanOrEqual(844);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("mesa-ayuda-390.png") });
  await page.keyboard.press("Escape");
  await expect(guide).not.toBeVisible();
  await expect(help).toBeFocused();
  await expect(
    demand.getByRole("cell", { name: "12", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Cambios sin guardar", { exact: true }),
  ).toBeVisible();
});
