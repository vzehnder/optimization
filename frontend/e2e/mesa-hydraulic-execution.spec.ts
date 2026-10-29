import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("El avance hidráulico conserva el run al desconectar y muestra el fallo sin resultados", async ({
  page,
}) => {
  let status = "queued";
  let disconnected = false;
  await page.route("**/mesa/hydraulic-execution?*", (route) =>
    disconnected
      ? route.abort()
      : route.fulfill({
          json: {
            run: {
              id: 901,
              scenario_version_id: 902,
              status,
              created_at: "2026-10-20T00:00:00Z",
              error_message:
                status === "failed" ? "unit_1: red infactible" : "",
              materialized_lineage: {
                mesa_hydraulic_execution: {
                  source_scenario_version_id: 17,
                  range_start: "2026-10-20T00:00:00Z",
                  range_end: "2026-10-20T02:00:00Z",
                  resolution_hours: 2,
                  objective: "energy",
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
  await openHydraulicMesa(page, "Avance recuperable");
  await expect(
    page.getByText("Ejecución hidráulica #901", { exact: true }),
  ).toBeVisible();
  await page.getByText("Ver avance y log hidráulico", { exact: true }).click();
  await expect(
    page.getByText("Esperando turno para iniciar", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Fuente #17 · Período del run:/)).toContainText(
    "Objetivo energy",
  );
  status = "running";
  await expect(
    page.getByText("Ejecución en curso", { exact: true }),
  ).toBeVisible();
  disconnected = true;
  await expect(
    page.getByText(/No se pudo actualizar el avance hidráulico/),
  ).toBeVisible();
  await expect(
    page.getByText("Ejecución hidráulica #901", { exact: true }),
  ).toBeVisible();
  disconnected = false;
  await page
    .getByRole("button", { name: "Reintentar conexión hidráulica" })
    .click();
  await page.reload();
  await expect(
    page.getByText("Ejecución hidráulica #901", { exact: true }),
  ).toBeVisible();
  status = "failed";
  await expect(
    page.getByText(/La ejecución hidráulica falló: unit_1/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Ver resultados hidráulicos en la mesa" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("img", { name: "Aporte natural · m3/s" }),
  ).toContainText("2 m3/s");
});

test("La preparación hidráulica cambia con sus opciones y se recupera de una huella obsoleta", async ({
  page,
}, testInfo) => {
  await page.route("**/mesa/hydraulic-execution/preview", (route) => {
    const body = route.request().postDataJSON();
    const periods = [
      {
        timestamp: "2026-10-20T00:00:00+00:00",
        duration_hours: 1,
        natural_inflow_m3s: { reservoir: 2 },
      },
      {
        timestamp: "2026-10-20T01:00:00+00:00",
        duration_hours: 1,
        natural_inflow_m3s: { reservoir: 4 },
      },
    ].slice(0, body.range_end === "2026-10-20T01:00:00Z" ? 1 : 2);
    return route.fulfill({
      json: {
        preparation_hash: "a".repeat(64),
        period_count: periods.length,
        preview_periods: periods,
        generation_metadata: {
          date_range: { start: body.range_start, end: body.range_end },
        },
      },
    });
  });
  await page.route("**/mesa/hydraulic-execution/runs", (route) =>
    route.fulfill({
      status: 409,
      json: { detail: "La preparación cambió. Vuelve a validar." },
    }),
  );
  const fixture = await openHydraulicMesa(page, "Revalidar red");
  await page
    .getByText("Preparar ejecución hidráulica", { exact: true })
    .click();
  await page
    .getByLabel("Versión fuente de la red")
    .selectOption(String(fixture.version.id));
  await page.getByLabel("Objetivo hidráulico").selectOption("energy");
  const validate = page.getByRole("button", {
    name: "Validar red hidráulica",
    exact: true,
  });
  const execute = page.getByRole("button", {
    name: "Ejecutar red hidráulica",
    exact: true,
  });
  await page.getByLabel("Valor terminal reservoir (USD/hm³)").fill("1");
  await expect(validate).toBeDisabled();
  await expect(page.getByRole("alert")).toContainText("iguales a cero");
  await page.getByLabel("Valor terminal reservoir (USD/hm³)").fill("0");
  await validate.focus();
  await page.keyboard.press("Enter");
  await expect(execute).toBeEnabled();
  await page
    .getByLabel("Fin hidráulico exclusivo (UTC)")
    .fill("2026-10-20T01:00");
  await expect(execute).toBeDisabled();
  await validate.click();
  await expect(execute).toBeEnabled();
  await execute.click();
  await expect(page.getByRole("alert")).toContainText("Vuelve a validar");
  await expect(execute).toBeDisabled();
  await validate.click();
  await expect(execute).toBeEnabled();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const intervals = page.getByRole("region", {
    name: "Intervalos preparados de la red",
  });
  await intervals.focus();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(() => intervals.evaluate((node) => node.scrollLeft))
    .toBeGreaterThan(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-red-preparacion-390.png"),
    fullPage: true,
  });
  await page.getByLabel("Gap relativo hidráulico").fill("0.02");
  await expect(execute).toBeDisabled();
});

async function openHydraulicMesa(
  page: Page,
  name: string,
  electricalDraft = false,
) {
  const fixture = await (
    await page.request.get(
      `/api/auth/mesa-fixture?hydraulic_execution=true&electrical_draft=${electricalDraft}&case_name=${encodeURIComponent(name)}`,
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

test("Red v3 prepara, ejecuta y recupera potencia y volumen sin salir de la mesa", async ({
  page,
}, testInfo) => {
  test.setTimeout(210000);
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await openHydraulicMesa(page, "Red ejecutable", true);
  await expect(
    page.getByText("Preparar ejecución eléctrica", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Editar activos hidráulicos" }),
  ).toBeVisible();
  await page
    .getByText("Preparar ejecución hidráulica", { exact: true })
    .click({ timeout: 5000 });
  await page
    .getByLabel("Versión fuente de la red")
    .selectOption(String(fixture.version.id));
  const execution = page.getByRole("region", {
    name: "Ejecución de red hidráulica",
  });
  await expect(execution).toContainText("plant_1");
  await expect(execution).toContainText("reservoir");
  await expect(execution).toContainText("Entradas de la versión fuente");
  await page
    .getByLabel("CMg para la ejecución")
    .selectOption(`${fixture.prices.id}:price_usd_per_mwh`);
  await page.getByLabel("Resolución hidráulica (horas)").fill("2");
  await page.getByLabel("Valor terminal reservoir (USD/hm³)").fill("1");
  await page
    .getByRole("button", { name: "Validar red hidráulica", exact: true })
    .click();
  await expect(
    execution.getByText(/Preparación válida · 1 intervalos/),
  ).toBeVisible({ timeout: 60000 });
  await expect(execution).toContainText("Cobertura completa");
  await expect(execution).toContainText("promedio ponderado");
  await expect(
    execution.getByRole("table", { name: "Vista previa hidráulica" }),
  ).toContainText("50");
  await page.screenshot({
    path: testInfo.outputPath("mesa-red-preparacion-1440.png"),
    fullPage: true,
  });
  const accepted = page.waitForResponse(
    (r) =>
      r.url().endsWith("/mesa/hydraulic-execution/runs") &&
      r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Ejecutar red hidráulica", exact: true })
    .dblclick();
  const run = await (await accepted).json();
  await expect(
    page.getByText(`Ejecución hidráulica #${run.id}`, { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText(`Ejecución hidráulica #${run.id}`, { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Ver resultados hidráulicos en la mesa" })
    .click({ timeout: 120000 });
  await expect(page.getByLabel("Resultados de ejecución")).toHaveValue(
    String(run.id),
  );
  const reservoir = page.getByRole("region", {
    name: "Embalse · Embalse Alto",
    exact: true,
  });
  await reservoir.getByRole("button", { name: /Configurar/ }).click();
  let dialog = page.getByRole("dialog", { name: "Configurar vista" });
  await dialog.getByRole("checkbox", { name: /Aporte natural/ }).uncheck();
  await dialog.getByRole("checkbox", { name: /Volumen almacenado/ }).check();
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  await expect(
    reservoir.getByRole("img", { name: "Volumen almacenado · hm3" }),
  ).toContainText("9.7336 hm3");
  await page
    .getByRole("button", { name: "Agregar vista", exact: true })
    .click();
  dialog = page.getByRole("dialog", { name: "Configurar vista" });
  const label = await dialog
    .getByRole("option")
    .filter({ hasText: / · plant_1 · #/ })
    .textContent();
  await dialog.getByLabel("Componente").selectOption({ label: label! });
  await dialog.getByLabel("Título").fill("Central ejecutada");
  await dialog.getByRole("button", { name: "Aplicar" }).click();
  await expect(
    page.getByRole("img", { name: "Potencia hidráulica · MW" }),
  ).toContainText("30 MW");
  const runs = await (
    await page.request.get(`/api/scenarios/${fixture.scenario.id}/runs`)
  ).json();
  expect(runs.runs.map((r: { id: number }) => r.id)).toEqual([run.id]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-red-resultados-1440.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("mesa-red-resultados-390.png"),
    fullPage: true,
  });
  await expect(page).toHaveURL(/\/mesa\?/);
});
