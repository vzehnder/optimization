// Exploratory recorder, not a product test or a timing benchmark.
// Start serve_baseline.py first with a unique UX_BASELINE_TOKEN.
import { createRequire } from "node:module";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const root = fileURLToPath(new URL("../../../../", import.meta.url));
const require = createRequire(resolve(root, "frontend/package.json"));
const { chromium } = require("@playwright/test");
const token = process.argv[2];
if (!token || !/^[a-zA-Z0-9-]+$/.test(token)) throw new Error("Supply the fixture server token.");
const baseURL = "http://127.0.0.1:8124";
const identity = await (await fetch(`${baseURL}/api/auth/smoke-token`)).json();
if (identity.token !== token) throw new Error("Not this recorder's disposable server; refusing to mutate.");
const output = resolve(root, ".tmp/ux-000", token, "capture");
mkdirSync(output, { recursive: true });
const fixture = JSON.parse(readFileSync(resolve(output, "../fixture.json"), "utf8"));
const browser = await chromium.launch({ headless: true });
const report = {
  recorded_at: new Date().toISOString(), browser: browser.version(),
  viewport: { width: 1280, height: 720 }, timezone: "America/Santiago",
  method: "Scripted exploration informed by source and existing fixtures. No human participants; elapsed times include browser/API latency, not solver computation or screenshot capture.",
  fixture, identities: {}, tasks: [], observations: {},
};
let context;
let page;
let currentTask;
let readyRunId;
let publicationId;

async function login(name) {
  if (context) await context.close();
  context = await browser.newContext({ baseURL, viewport: report.viewport, timezoneId: report.timezone });
  page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.on("pageerror", error => report.observations.page_errors = [...(report.observations.page_errors || []), error.message]);
  await page.goto("/react");
  await page.getByLabel("Email").fill(`${name}@ux.example.local`);
  await page.getByLabel("Password").fill("ux-baseline-only");
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL(url => !url.pathname.endsWith("/login") && url.pathname !== "/react");
  const response = await context.request.get("/api/auth/me");
  const me = await response.json();
  report.identities[name] = { role: me.user?.role, landing_path: me.landing_path, ts_next_canonical_read: me.ts_next_canonical_read, observed_path: new URL(page.url()).pathname };
}

async function request(method, path, data) {
  const csrf = await (await context.request.get("/api/auth/csrf")).json();
  const response = await context.request.fetch(path, { method, data, headers: { "X-CSRF-Token": csrf.csrf_token } });
  if (!response.ok()) throw new Error(`${method} ${path}: ${response.status()} ${await response.text()}`);
  return response.json();
}

async function shot(name, fullPage = false) {
  await page.screenshot({ path: resolve(output, `${name}.png`), fullPage });
  if (currentTask) currentTask.captures.push(`${name}.png`);
}

async function task(name, action) {
  const entry = { name, elapsed_ms: null, help: "Recorder author consulted source and existing tests; no human usability measurement.", captures: [] };
  report.tasks.push(entry);
  currentTask = entry;
  const start = performance.now();
  try {
    entry.observed = await action();
    entry.outcome = "completed";
  } catch (error) {
    entry.outcome = "interrupted";
    entry.error = error.message;
    entry.alerts = await page.getByRole("alert").allTextContents().catch(() => []);
  }
  entry.elapsed_ms ??= Math.round(performance.now() - start);
  entry.url = page.url();
  await shot(name);
  currentTask = undefined;
  writeFileSync(resolve(output, "observations.json"), JSON.stringify(report, null, 2));
  console.log(`${name}: ${entry.outcome} (${entry.elapsed_ms} ms)`);
}

function stopTimer(start) { currentTask.elapsed_ms = Math.round(performance.now() - start); }

try {
  await login("admin");
  const kpi = { id: "objective", path: "objective_value_usd", label: "Beneficio total", unit: "USD", decimals: 1, sign: "auto", emphasis: "strong" };
  await request("PUT", `/api/projects/${fixture.project.id}/portal-configuration`, {
    expected_revision: 0, status: "active", document: {
      schema_version: "portal_config.v1", display_name: "UX Planta de prueba",
      sections: {
        kpis: { enabled: true, label: "Resumen", items: [kpi] },
        charts: { enabled: false, label: "Graficos", items: [] },
        tables: { enabled: false, label: "Tablas", items: [] },
        downloads: { enabled: true, label: "Descargas" },
      },
    },
  });
  await request("POST", `/api/projects/${fixture.project.id}/dashboard-templates`, { name: "Informe UX-000" });

  await login("analyst");
  await task("01-retomar", async () => {
    const start = performance.now();
    await page.goto(`/react/projects/${fixture.project.id}`);
    await page.getByRole("link", { name: fixture.scenarios.partial.name, exact: true }).click();
    await page.getByRole("link", { name: "Abrir draft", exact: true }).click();
    await page.getByLabel("Nombre del caso").waitFor();
    stopTimer(start);
    return { case_name: await page.getByLabel("Nombre del caso").inputValue(), actions: "Proyecto → Preparacion parcial → Abrir draft", pending: "Modelo guardado sin fuentes" };
  });

  await task("02-importar", async () => {
    // Setup outside the measured interval; the file and component are ready.
    await page.getByRole("button", { name: "Agregar load", exact: true }).click();
    await page.getByRole("button", { name: "Guardar draft", exact: true }).click();
    await page.getByText("Guardado", { exact: true }).waitFor();
    const start = performance.now();
    const csv = "period_start,hours,buy_cost,load_1_demand_mw\n2026-01-01T00:00:00,1,55,2\n2026-01-01T01:00:00,1,60,2.5\n";
    await page.getByLabel("Source file", { exact: true }).setInputFiles({ name: "ux-inputs.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
    await page.getByRole("button", { name: "Upload source", exact: true }).click();
    await page.getByLabel("Catalog set name").fill("Precio y demanda UX");
    await page.getByLabel("Catalog version label").fill("v1");
    await page.getByLabel("Catalog timezone").fill("America/Santiago");
    await page.getByLabel("Catalog timestamp column").selectOption("period_start");
    await page.getByLabel("Catalog duration column").selectOption("hours");
    if (await page.getByLabel("Mapped source column 1").count() === 0)
      await page.getByRole("button", { name: "Add signal mapping", exact: true }).click();
    await page.getByLabel("Mapped source column 1").selectOption("buy_cost");
    await page.getByLabel("Canonical signal 1").selectOption("import_price_usd_per_mwh");
    await page.getByLabel("Source unit 1", { exact: true }).fill("USD/MWh");
    if (await page.getByLabel("Mapped source column 2").count() === 0)
      await page.getByRole("button", { name: "Add signal mapping", exact: true }).click();
    await page.getByLabel("Mapped source column 2").selectOption("load_1_demand_mw");
    await page.getByLabel("Canonical signal 2").selectOption("load_demand_mw");
    await page.getByLabel("Source unit 2", { exact: true }).fill("MW");
    const importedResponse = page.waitForResponse(response => response.url().endsWith("/catalog-import") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Import to catalog", exact: true }).click();
    await page.getByText("Catalog import created", { exact: true }).waitFor();
    const imported = (await (await importedResponse).json()).time_series_set;
    await page.goto(`/react/scenarios/${fixture.scenarios.partial.id}`);
    await page.getByLabel("Serie de precio (price_usd_per_mwh)", { exact: true }).selectOption(String(imported.id));
    await page.getByLabel("Serie load_demand_mw (load_1)", { exact: true }).selectOption(String(imported.id));
    await page.getByRole("button", { name: "Vincular y correr variante", exact: true }).click();
    await page.waitForURL(/\/react\/runs\/\d+$/);
    await page.goto(`/react/scenarios/${fixture.scenarios.partial.id}`);
    await page.getByRole("list", { name: "Senales requeridas", exact: true }).waitFor();
    const binding = await page.getByRole("list", { name: "Senales requeridas", exact: true }).innerText();
    stopTimer(start);
    return { imported: imported.name, revision: imported.revision_number, values: imported.values, binding, limitation: "El guardado visible de los dos usos exige Vincular y correr variante y crea una corrida." };
  });

  await task("03-ejecutar", async () => {
    const start = performance.now();
    await page.goto(`/react/scenarios/${fixture.scenarios.ready.id}`);
    await page.getByRole("button", { name: "Vincular y correr variante", exact: true }).click();
    await page.waitForURL(/\/react\/runs\/\d+$/);
    readyRunId = Number(new URL(page.url()).pathname.split("/").at(-1));
    await page.getByRole("heading", { name: `Run ${readyRunId}`, exact: true }).waitFor();
    stopTimer(start);
    return { run_id: readyRunId, range: [fixture.scenarios.ready.range_start, fixture.scenarios.ready.range_end], manual_promotion: false };
  });

  await task("04-recuperar-desactualizada", async () => {
    await page.goto(`/react/scenarios/${fixture.scenarios.stale.id}`);
    await page.getByRole("button", { name: "Revalidar variante", exact: true }).waitFor();
    const start = performance.now();
    const reasons = await page.getByRole("list", { name: "Motivos de desactualizacion" }).innerText();
    const runDisabled = await page.getByRole("button", { name: "Vincular y correr variante", exact: true }).isDisabled();
    await page.getByRole("button", { name: "Revalidar variante", exact: true }).click();
    await page.getByRole("button", { name: "Revalidar variante", exact: true }).waitFor({ state: "hidden" });
    await page.getByText("Rango valido para correr.", { exact: true }).waitFor();
    await page.getByRole("list", { name: "Senales requeridas", exact: true }).waitFor();
    stopTimer(start);
    return { reasons, run_disabled_before: runDisabled, run_disabled_after: await page.getByRole("button", { name: "Vincular y correr variante", exact: true }).isDisabled() };
  });

  await task("05-interpretar-comparar", async () => {
    // Reuse the already indexed comparison fixture. SmokeRunQueue's legacy
    // dispatch lacks market_value_usd and cannot supply this baseline.
    const comparison = fixture.scenarios.comparison;
    const start = performance.now();
    await page.goto(`/react/runs/${comparison.run_ids[0]}`);
    await page.getByText("1000", { exact: true }).first().waitFor();
    await page.getByRole("navigation", { name: "Ruta", exact: true }).getByRole("link", { name: comparison.name, exact: true }).click();
    await page.getByRole("link", { name: "Comparar corridas", exact: true }).click();
    await page.getByLabel("Corrida base").selectOption(String(comparison.run_ids[0]));
    await page.getByLabel("Corrida candidata").selectOption(String(comparison.run_ids[1]));
    await page.getByRole("heading", { name: "Diferencias en KPIs", exact: true }).waitFor();
    stopTimer(start);
    return { base: await page.getByLabel("Corrida base").inputValue(), candidate: await page.getByLabel("Corrida candidata").inputValue(), kpi_row: await page.getByRole("row").filter({ hasText: "objective_value_usd" }).innerText(), result_model: "Existing create_indexed_run fixture: base 1000 USD; candidate 1500 USD; known difference 500 USD" };
  });

  await task("06-entregar-informe", async () => {
    if (!readyRunId) throw new Error("No accepted run from task 03.");
    const start = performance.now();
    await page.goto(`/react/runs/${readyRunId}`);
    await page.getByLabel("Public Title", { exact: true }).fill("Informe de prueba UX-000");
    await page.getByRole("button", { name: "Crear publicacion", exact: true }).click();
    await page.getByRole("link", { name: "Preview as client Informe de prueba UX-000", exact: true }).click();
    await page.getByRole("heading", { name: "Informe de prueba UX-000", exact: true }).waitFor();
    publicationId = Number(new URL(page.url()).pathname.split("/").at(-2));
    await page.goBack();
    await page.getByRole("button", { name: "Publicar Informe de prueba UX-000", exact: true }).click();
    await page.getByRole("button", { name: "Unpublicar Informe de prueba UX-000", exact: true }).waitFor();
    stopTimer(start);
    return { publication_id: publicationId, action: "Crear publicacion → Preview as client → regresar → Publicar" };
  });

  await login("operator");
  await task("07-operar", async () => {
    const start = performance.now();
    await page.goto(`/react/console/${fixture.scenarios.ready.console_id}`);
    await page.getByLabel("Potencia maxima BESS (MW)", { exact: true }).fill("3");
    const pending = await page.getByText("Guarda los cambios antes de ejecutar.", { exact: true }).innerText();
    const disabled = await page.getByRole("button", { name: "Ejecutar", exact: true }).isDisabled();
    await page.getByRole("button", { name: "Guardar parametros", exact: true }).click();
    await page.getByText("Guarda los cambios antes de ejecutar.", { exact: true }).waitFor({ state: "hidden" });
    const accepted = page.waitForResponse(response => response.url().endsWith(`/api/console/${fixture.scenarios.ready.console_id}/runs`) && response.request().method() === "POST");
    await page.getByRole("button", { name: "Ejecutar", exact: true }).click();
    const response = await accepted;
    stopTimer(start);
    return { pending, disabled_before_save: disabled, run_status: response.status(), body: await response.json() };
  });
  await page.goto("/react/projects");
  await page.getByRole("heading", { name: "No encontrado", exact: true }).waitFor();
  report.observations.operator_internal_access = "No encontrado";
  await shot("08-operador-acceso-interno");

  await login("reader");
  if (publicationId) {
    await page.goto(`/react/client/projects/${fixture.project.id}/publications/${publicationId}`);
    await page.getByRole("heading", { name: "Informe de prueba UX-000", exact: true }).waitFor();
  }
  await shot("09-portal");

  await login("verification");
  await page.getByRole("link", { name: "Catalogo", exact: true }).click();
  await page.getByRole("heading", { level: 1 }).waitFor();
  await shot("10-catalogo-verificacion");

  await login("analyst");
  for (const viewport of [{ width: 1280, height: 720 }, { width: 1440, height: 900 }, { width: 320, height: 900 }]) {
    await page.setViewportSize(viewport);
    for (const [name, path, heading] of [
      ["proyecto", `/react/projects/${fixture.project.id}`, fixture.project.name],
      ["escenario", `/react/scenarios/${fixture.scenarios.empty.id}`, fixture.scenarios.empty.name],
    ]) {
      await page.goto(path);
      await page.getByRole("heading", { name: heading, exact: true }).waitFor();
      await page.getByRole("heading", { name: name === "proyecto" ? "Escenarios" : "Versiones inmutables", exact: true }).waitFor();
      await shot(`${name}-${viewport.width}`);
    }
  }
  await page.setViewportSize(report.viewport);
  await page.goto(`/react/scenarios/${fixture.scenarios.empty.id}`);
  await page.getByRole("link", { name: "Abrir draft", exact: true }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Crear draft", exact: true }).waitFor();
  report.observations.keyboard = { action: "Focus Abrir draft; Enter", reached: page.url(), focused_tag: await page.evaluate(() => document.activeElement?.tagName) };
  await shot("11-primer-comportamiento");
} finally {
  writeFileSync(resolve(output, "observations.json"), JSON.stringify(report, null, 2));
  await browser.close();
  console.log(`Evidence: ${output}`);
}
