import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import {
  expect,
  request as requestFactory,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

async function csrfToken(api: APIRequestContext): Promise<string> {
  const response = await api.get("/api/auth/csrf");
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as { csrf_token: string }).csrf_token;
}

async function postWithCsrf(
  api: APIRequestContext,
  path: string,
  data?: unknown,
) {
  return api.post(path, {
    data,
    headers: { "X-CSRF-Token": await csrfToken(api) },
  });
}

async function apiLogin(
  api: APIRequestContext,
  email: string,
  password: string,
) {
  const response = await postWithCsrf(api, "/api/auth/login", {
    email,
    password,
    next: "/react/projects",
  });
  expect(response.ok()).toBeTruthy();
}

async function ensureAdminSession(page: Page) {
  await page.goto("/react");
  await expect(
    page.getByRole("heading", {
      name: /Crear admin|Iniciar sesion|Proyectos/,
    }),
  ).toBeVisible();
  const bootstrapHeading = page.getByRole("heading", { name: "Crear admin" });
  const loginHeading = page.getByRole("heading", { name: "Iniciar sesion" });
  if (await bootstrapHeading.isVisible()) {
    await page.getByLabel("Email").fill("admin@example.local");
    await page.getByLabel("Nombre").fill("Admin User");
    await page.getByLabel("Password").fill("admin-pass");
    await page.getByRole("button", { name: "Crear admin" }).click();
  } else if (await loginHeading.isVisible()) {
    await page.getByLabel("Email").fill("admin@example.local");
    await page.getByLabel("Password").fill("admin-pass");
    await page.getByRole("button", { name: "Entrar" }).click();
  }
  await expect(page).toHaveURL(/\/react\/projects$/);
  await expect(
    page.getByRole("heading", { name: "Proyectos", exact: true }),
  ).toBeVisible();
}

function pythonExecutable(): string {
  return (
    process.env.PYTHON ||
    [
      resolve("..", ".venv/Scripts/python.exe"),
      resolve("..", ".venv/bin/python"),
    ].find(existsSync) ||
    "python"
  );
}

function workbookBuffer(): Buffer {
  const workbookPath = join(
    mkdtempSync(join(tmpdir(), "bess-react-xlsx-")),
    "source.xlsx",
  );
  const script = `
import sys
from openpyxl import Workbook

wb = Workbook()
sheet = wb.active
sheet.title = "Ignored"
sheet.append(["ignored"])
sheet.append(["not active"])
inputs = wb.create_sheet("Inputs")
for row in [
    ["period_start", "hours", "buy_cost", "sell_revenue", "solar_1_available_mw", "load_1_demand_mw", "hydro_inflow_m3s"],
    ["2026-01-02T00:00:00", 1.0, 61.0, 49.0, 4.5, 2.1, 31.0],
    ["2026-01-02T01:00:00", 1.0, 62.0, 50.0, 4.8, 2.3, 32.0],
]:
    inputs.append(row)
wb.save(sys.argv[1])
`;
  execFileSync(pythonExecutable(), ["-c", script, workbookPath], {
    cwd: resolve(".."),
  });
  return readFileSync(workbookPath);
}

test("React auth handles bootstrap, login, refresh, roles, logout, and deactivation", async ({
  page,
  baseURL,
}) => {
  await page.goto("/react");
  await expect(
    page.getByRole("heading", { name: "Crear admin" }),
  ).toBeVisible();
  await page.getByLabel("Email").fill("admin@example.local");
  await page.getByLabel("Nombre").fill("Admin User");
  await page.getByLabel("Password").fill("admin-pass");
  await page.getByRole("button", { name: "Crear admin" }).click();

  await expect(page).toHaveURL(/\/react\/projects$/);
  await expect(
    page.getByRole("heading", { name: "Proyectos", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Admin User")).toBeVisible();

  const analystResponse = await postWithCsrf(
    page.context().request,
    "/api/admin/users",
    {
      email: "ada@example.local",
      display_name: "Ada Analyst",
      role: "analyst",
      password: "smoke-test-password",
    },
  );
  expect(analystResponse.status()).toBe(201);
  const clientResponse = await postWithCsrf(
    page.context().request,
    "/api/admin/users",
    {
      email: "client@example.local",
      display_name: "Client User",
      role: "client",
      password: "client-pass",
    },
  );
  expect(clientResponse.status()).toBe(201);
  const clientUser = ((await clientResponse.json()) as { user: { id: number } })
    .user;

  await page.getByRole("button", { name: "Salir" }).click();
  await expect(
    page.getByRole("heading", { name: "Iniciar sesion" }),
  ).toBeVisible();

  await page.getByLabel("Email").fill("ada@example.local");
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Invalid email or password.",
  );

  await page.getByLabel("Password").fill("smoke-test-password");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/react\/projects$/);
  await expect(page.getByText("Ada Analyst")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Ada Analyst")).toBeVisible();

  await page.getByRole("button", { name: "Salir" }).click();
  await page.getByLabel("Email").fill("client@example.local");
  await page.getByLabel("Password").fill("client-pass");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/react\/client$/);
  await expect(
    page.getByRole("heading", { name: "Portal cliente" }),
  ).toBeVisible();
  await page.goto("/react/projects");
  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();

  const adminApi = await requestFactory.newContext({ baseURL });
  await apiLogin(adminApi, "admin@example.local", "admin-pass");
  const deactivate = await postWithCsrf(
    adminApi,
    `/api/admin/users/${clientUser.id}/deactivate`,
  );
  expect(deactivate.ok()).toBeTruthy();
  await adminApi.dispose();

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Iniciar sesion" }),
  ).toBeVisible();
  await page.getByLabel("Email").fill("client@example.local");
  await page.getByLabel("Password").fill("client-pass");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Invalid email or password.",
  );
});

test("React analyst workspace creates a project and scenario, then preserves direct scenario refresh", async ({
  page,
}) => {
  await ensureAdminSession(page);
  const suffix = Date.now();
  const projectName = `Hybrid PMGD ${suffix}`;
  const scenarioName = `Base case ${suffix}`;

  await page.getByLabel("Nombre del proyecto").fill(projectName);
  await page
    .getByLabel("Descripcion del proyecto")
    .fill("Browser acceptance workspace");
  await page.getByRole("button", { name: "Crear proyecto" }).click();

  await expect(page.getByRole("link", { name: projectName })).toBeVisible();
  await page.getByRole("link", { name: projectName }).click();
  await expect(page.getByRole("heading", { name: projectName })).toBeVisible();
  await expect(
    page.getByText("Crea un escenario para guardar variantes del proyecto."),
  ).toBeVisible();

  await page.getByLabel("Nombre del escenario").fill(scenarioName);
  await page
    .getByLabel("Descripcion del escenario")
    .fill("Initial modeling branch");
  await page.getByRole("button", { name: "Crear escenario" }).click();

  await expect(page).toHaveURL(/\/react\/scenarios\/\d+$/);
  await expect(page.getByRole("heading", { name: scenarioName })).toBeVisible();
  await expect(
    page.getByText("Aun no hay versiones inmutables."),
  ).toBeVisible();
  await expect(
    page.getByText("Aun no hay corridas para este escenario."),
  ).toBeVisible();

  const scenarioUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(scenarioUrl);
  await expect(page.getByRole("heading", { name: scenarioName })).toBeVisible();

  await page.goBack();
  await expect(page.getByRole("heading", { name: projectName })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole("heading", { name: scenarioName })).toBeVisible();
});

test("React structured draft editor saves multi-asset edits, recovers from one failed save, and reopens persisted state", async ({
  page,
}) => {
  await ensureAdminSession(page);
  const suffix = Date.now();
  const projectName = `Draft PMGD ${suffix}`;
  const scenarioName = `Structured case ${suffix}`;
  let failNextDraftSave = true;

  await page.route("**/api/scenarios/*/draft", async (route) => {
    if (route.request().method() === "PUT" && failNextDraftSave) {
      failNextDraftSave = false;
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "synthetic save failure" }),
      });
      return;
    }
    await route.continue();
  });

  await page.getByLabel("Nombre del proyecto").fill(projectName);
  await page
    .getByLabel("Descripcion del proyecto")
    .fill("Browser draft acceptance");
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await page.getByRole("link", { name: projectName }).click();
  await page.getByLabel("Nombre del escenario").fill(scenarioName);
  await page
    .getByLabel("Descripcion del escenario")
    .fill("Structured editor branch");
  await page.getByRole("button", { name: "Crear escenario" }).click();

  await page.getByRole("link", { name: "Abrir draft" }).click();
  await expect(
    page.getByRole("heading", { name: "Draft estructurado" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Crear draft" }).click();
  await expect(page.getByText("Guardado", { exact: true })).toBeVisible();

  await page.getByLabel("Nombre del caso").fill("PMGD verano");
  await page.getByLabel("Maximum import (MW)").fill("12");
  await page.getByLabel("Maximum export (MW)").fill("8");
  await page.getByRole("button", { name: "Agregar BESS" }).click();
  await page.getByLabel("BESS asset ID").fill("battery_alpha");
  await page.getByLabel("Maximum charge (MW)").fill("3");
  await page.getByLabel("Maximum discharge (MW)").fill("4");
  await page.getByRole("button", { name: "Agregar renewable" }).click();
  await page.getByLabel("Renewable asset ID").fill("solar_north");
  await page.getByRole("button", { name: "Agregar hydro" }).click();
  await page.getByLabel("Hydro asset ID").fill("hydro_north");
  await expect(page.getByText("Cambios sin guardar")).toBeVisible();

  await page.getByRole("button", { name: "Guardar draft" }).click();
  await expect(page.getByRole("alert")).toContainText("synthetic save failure");
  await expect(page.getByLabel("Nombre del caso")).toHaveValue("PMGD verano");

  await page.getByRole("button", { name: "Guardar draft" }).click();
  await expect(page.getByText("Guardado", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Quitar solar_north" }).click();
  await expect(
    page.getByText("Confirma para quitar solar_north"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Confirmar quitar solar_north" })
    .click();
  await page.getByRole("button", { name: "Guardar draft" }).click();
  await expect(page.getByText("Guardado", { exact: true })).toBeVisible();

  const draftUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(draftUrl);
  await expect(page.getByLabel("Nombre del caso")).toHaveValue("PMGD verano");
  await expect(page.getByLabel("BESS asset ID")).toHaveValue("battery_alpha");
  await expect(page.getByLabel("Hydro asset ID")).toHaveValue("hydro_north");
  await expect(page.getByLabel("Renewable asset ID")).toHaveCount(0);
});

test("React draft editor uploads, maps, edits, and validates time-series sources", async ({
  page,
}) => {
  await ensureAdminSession(page);
  const suffix = Date.now();
  const projectName = `Time-series PMGD ${suffix}`;
  const scenarioName = `Source workflow ${suffix}`;

  await page.getByLabel("Nombre del proyecto").fill(projectName);
  await page
    .getByLabel("Descripcion del proyecto")
    .fill("Browser time-series acceptance");
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await page.getByRole("link", { name: projectName }).click();
  await page.getByLabel("Nombre del escenario").fill(scenarioName);
  await page
    .getByLabel("Descripcion del escenario")
    .fill("Upload and mapping branch");
  await page.getByRole("button", { name: "Crear escenario" }).click();

  await page.getByRole("link", { name: "Abrir draft" }).click();
  await page.getByRole("button", { name: "Crear draft" }).click();
  await expect(page.getByText("Guardado", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Agregar load" }).click();
  await page.getByRole("button", { name: "Agregar renewable" }).click();
  await page.getByRole("button", { name: "Agregar hydro" }).click();
  await page.getByRole("button", { name: "Guardar draft" }).click();
  await expect(page.getByText("Guardado", { exact: true })).toBeVisible();

  const workbook = workbookBuffer();
  await page.getByLabel("XLSX sheet").fill("Missing");
  await page.getByLabel("Source file").setInputFiles({
    name: "source.xlsx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: workbook,
  });
  await page.getByRole("button", { name: "Upload source" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "XLSX sheet 'Missing' was not found",
  );
  await expect(page.getByLabel("Nombre del caso")).toHaveValue(scenarioName);

  const csvText = [
    "period_start,hours,buy_cost,sell_revenue,solar_1_available_mw,load_1_demand_mw,hydro_inflow_m3s",
    "2026-01-01T00:00:00,1.0,55.0,42.0,3.5,2.0,25.0",
    "2026-01-01T01:00:00,1.0,60.0,48.0,4.0,2.5,30.0",
    "",
  ].join("\n");
  await page.getByLabel("XLSX sheet").fill("");
  await page.getByLabel("Source file").setInputFiles({
    name: "source.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csvText),
  });
  await page.getByRole("button", { name: "Upload source" }).click();
  await expect(page.getByText("source.csv")).toBeVisible();
  await expect(
    page.getByLabel("Source preview").getByRole("columnheader", {
      name: "buy_cost",
    }),
  ).toBeVisible();
  await expect(page.getByText("2026-01-01T00:00:00")).toBeVisible();

  await page.getByLabel("Import price column").selectOption("buy_cost");
  await page.getByLabel("Export price column").selectOption("sell_revenue");
  await page.getByRole("button", { name: "Save mapping" }).click();
  await expect(page.getByText("Valid mapped rows: 2")).toBeVisible();

  await page.getByLabel("Row 1 load_1_demand_mw").fill("-1");
  await page.getByRole("button", { name: "Save rows" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "row 2: load load_1 demand must be nonnegative",
  );
  await page.getByLabel("Row 1 load_1_demand_mw").fill("2.25");
  await page.getByRole("button", { name: "Save rows" }).click();
  await expect(page.getByText("Rows saved")).toBeVisible();
  await expect(page.getByText("Valid mapped rows: 2")).toBeVisible();

  await page.getByLabel("XLSX sheet").fill("Inputs");
  await page.getByLabel("Source file").setInputFiles({
    name: "source.xlsx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: workbook,
  });
  await page.getByRole("button", { name: "Upload source" }).click();
  await expect(page.getByText("source.xlsx")).toBeVisible();
  await expect(page.getByText("Selected sheet: Inputs")).toBeVisible();
  await expect(page.getByText("2026-01-02T00:00:00")).toBeVisible();
});

test("React case validation and versioning covers generated and expert paths", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await ensureAdminSession(page);
  const suffix = Date.now();
  const projectName = `Validation PMGD ${suffix}`;
  const scenarioName = `Version loop ${suffix}`;
  const sampleCasePath = resolve(
    "..",
    "data/cases/hybrid_system/system_case.json",
  );
  const sampleCase = readFileSync(sampleCasePath, "utf-8");

  await page.getByLabel("Nombre del proyecto").fill(projectName);
  await page
    .getByLabel("Descripcion del proyecto")
    .fill("Browser validation acceptance");
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await page.getByRole("link", { name: projectName }).click();
  await page.getByLabel("Nombre del escenario").fill(scenarioName);
  await page
    .getByLabel("Descripcion del escenario")
    .fill("Generate validate promote branch");
  await page.getByRole("button", { name: "Crear escenario" }).click();

  await page.getByRole("link", { name: "Abrir draft" }).click();
  await page.getByRole("button", { name: "Crear draft" }).click();
  await expect(page.getByText("Guardado", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Agregar BESS" }).click();
  await page.getByRole("button", { name: "Agregar load" }).click();
  await page.getByRole("button", { name: "Agregar renewable" }).click();
  await page.getByRole("button", { name: "Guardar draft" }).click();
  await expect(page.getByText("Guardado", { exact: true })).toBeVisible();

  const csvText = [
    "period_start,hours,buy_cost,sell_revenue,solar_1_available_mw,load_1_demand_mw",
    "2026-01-01T00:00:00,1.0,55.0,42.0,3.5,2.0",
    "2026-01-01T01:00:00,1.0,60.0,48.0,4.0,2.5",
    "",
  ].join("\n");
  await page.getByLabel("Source file").setInputFiles({
    name: "validation-source.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csvText),
  });
  await page.getByRole("button", { name: "Upload source" }).click();
  await expect(page.getByText("validation-source.csv")).toBeVisible();
  await page.getByLabel("Import price column").selectOption("buy_cost");
  await page.getByLabel("Export price column").selectOption("sell_revenue");
  await page.getByRole("button", { name: "Save mapping" }).click();
  await expect(page.getByText("Valid mapped rows: 2")).toBeVisible();

  await page.getByRole("button", { name: "Generar preview" }).click();
  await expect(page.getByLabel("Generated system_case")).toHaveValue(
    /import_price_usd_per_mwh/,
  );
  await page.getByRole("button", { name: "Validar con Julia" }).click();
  await expect(page.getByText("Validacion vigente")).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: "Promover version" }).click();
  await expect(page.locator("a", { hasText: "Version 1" })).toBeVisible();
  await page.locator("a", { hasText: "Version 1" }).click();
  await expect(page.getByLabel("Immutable system_case")).toHaveValue(
    /import_price_usd_per_mwh/,
  );

  await page.getByRole("link", { name: scenarioName }).click();
  await page.getByRole("link", { name: "Abrir draft" }).click();
  await page.getByLabel("Nombre del caso").fill(`${scenarioName} stale`);
  await expect(
    page.getByText("Validacion stale; valida de nuevo antes de promover."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Promover version" }),
  ).toBeDisabled();
  await page.getByRole("link", { name: scenarioName }).click();
  await page.getByRole("button", { name: "Descartar cambios" }).click();

  await page.locator("#system_case_json").fill("{bad");
  await page.getByRole("button", { name: "Crear version" }).click();
  await expect(page.getByRole("alert")).toContainText("Malformed JSON");
  await page.locator("#system_case_json").fill(sampleCase);
  await page.getByRole("button", { name: "Crear version" }).click();
  await expect(page.locator("a", { hasText: "Version 2" })).toBeVisible();

  await page.getByLabel("Subir system_case JSON").setInputFiles(sampleCasePath);
  const uploadResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/scenarios/") &&
      response.url().endsWith("/versions/upload") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Subir version" }).click();
  const uploadedVersion = (await (await uploadResponse).json()) as {
    id: number;
    version_number: number;
  };
  await expect(
    page.locator("a", {
      hasText: `Version ${uploadedVersion.version_number}`,
    }),
  ).toBeVisible();

  const runResponse = await postWithCsrf(
    page.context().request,
    `/api/scenario-versions/${uploadedVersion.id}/runs`,
  );
  expect(runResponse.status()).toBe(201);

  await page
    .getByRole("button", {
      name: `Eliminar version ${uploadedVersion.version_number}`,
    })
    .click();
  await page
    .getByRole("button", {
      name: `Confirmar eliminar version ${uploadedVersion.version_number}`,
    })
    .click();
  await expect(page.getByRole("alert")).toContainText("referenced by runs");

  await page.getByRole("button", { name: "Eliminar version 2" }).click();
  await page
    .getByRole("button", { name: "Confirmar eliminar version 2" })
    .click();
  await expect(page.locator("a", { hasText: "Version 2" })).toHaveCount(0);
});

test("React manual run lifecycle launches, polls success, and exposes failure logs", async ({
  page,
}) => {
  await ensureAdminSession(page);
  const suffix = Date.now();
  const api = page.context().request;
  const sampleCase = readFileSync(
    resolve("..", "data/cases/hybrid_system/system_case.json"),
    "utf-8",
  );

  const projectResponse = await postWithCsrf(api, "/api/projects", {
    name: `Run PMGD ${suffix}`,
    description: "Manual run browser acceptance",
  });
  expect(projectResponse.ok()).toBeTruthy();
  const project = (await projectResponse.json()) as { id: number };
  const scenarioResponse = await postWithCsrf(
    api,
    `/api/projects/${project.id}/scenarios`,
    {
      name: `Run lifecycle ${suffix}`,
      description: "Success and failure run states",
    },
  );
  expect(scenarioResponse.ok()).toBeTruthy();
  const scenario = (await scenarioResponse.json()) as { id: number };

  const successVersionResponse = await postWithCsrf(
    api,
    `/api/scenarios/${scenario.id}/versions`,
    { system_case_json: sampleCase },
  );
  expect(successVersionResponse.status()).toBe(201);
  const successVersion = (await successVersionResponse.json()) as {
    id: number;
    version_number: number;
  };

  await page.goto(`/react/scenario-versions/${successVersion.id}`);
  await expect(
    page.getByRole("heading", {
      name: `Version ${successVersion.version_number}`,
    }),
  ).toBeVisible();
  const successLaunch = page.waitForResponse(
    (response) =>
      response
        .url()
        .endsWith(`/api/scenario-versions/${successVersion.id}/runs`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Lanzar run" }).click();
  const successRun = (await (await successLaunch).json()) as {
    id: number;
    scenario_version_id: number;
    created_at: string;
  };
  let successPollCount = 0;
  await page.route(`**/api/runs/${successRun.id}`, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    successPollCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run: {
          ...successRun,
          status: successPollCount < 2 ? "running" : "succeeded",
          started_at: "2026-06-23T12:15:01Z",
          finished_at: successPollCount < 2 ? null : "2026-06-23T12:15:03Z",
          duration_seconds: successPollCount < 2 ? null : 2,
          exit_code: successPollCount < 2 ? null : 0,
          error_message: "",
          stdout: "",
          stderr: "",
          trigger_type: "manual",
          triggered_by: "internal_analyst",
        },
      }),
    });
  });
  await expect(page).toHaveURL(new RegExp(`/react/runs/${successRun.id}$`));
  await expect(
    page.getByRole("heading", { name: `Run ${successRun.id}` }),
  ).toBeVisible();
  await expect(page.getByText("succeeded", { exact: true })).toBeVisible({
    timeout: 5000,
  });
  await expect(page.getByText("2026-06-23T12:15:01Z")).toBeVisible();
  await expect(page.getByText("2026-06-23T12:15:03Z")).toBeVisible();
  await expect(page.getByText("2.00 s")).toBeVisible();
  await expect(page.getByText("0", { exact: true })).toBeVisible();
  await expect(
    page
      .getByRole("link", {
        name: `Version ${successVersion.version_number}`,
      })
      .first(),
  ).toBeVisible();

  const failureVersionResponse = await postWithCsrf(
    api,
    `/api/scenarios/${scenario.id}/versions`,
    { system_case_json: sampleCase },
  );
  expect(failureVersionResponse.status()).toBe(201);
  const failureVersion = (await failureVersionResponse.json()) as {
    id: number;
    version_number: number;
  };

  await page.goto(`/react/scenario-versions/${failureVersion.id}`);
  const failureLaunch = page.waitForResponse(
    (response) =>
      response
        .url()
        .endsWith(`/api/scenario-versions/${failureVersion.id}/runs`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Lanzar run" }).click();
  const failureRun = (await (await failureLaunch).json()) as {
    id: number;
    scenario_version_id: number;
    created_at: string;
  };
  let failurePollCount = 0;
  await page.route(`**/api/runs/${failureRun.id}`, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    failurePollCount += 1;
    if (failurePollCount === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "temporary polling outage" }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run: {
          ...failureRun,
          status: failurePollCount === 2 ? "running" : "failed",
          started_at: "2026-06-23T12:16:01Z",
          finished_at: failurePollCount === 2 ? null : "2026-06-23T12:16:03Z",
          duration_seconds: failurePollCount === 2 ? null : 2,
          exit_code: failurePollCount === 2 ? null : 23,
          error_message: "optimization failed before solve",
          error_payload: {
            status: "error",
            message: "optimization failed before solve",
          },
          stdout: "solver stdout\nsecond line\n",
          stderr:
            '{"status":"error","message":"optimization failed before solve"}\n',
          trigger_type: "manual",
          triggered_by: "internal_analyst",
        },
      }),
    });
  });
  await expect(page).toHaveURL(new RegExp(`/react/runs/${failureRun.id}$`));
  await expect(
    page.getByText("Reintentando actualizacion de run."),
  ).toBeVisible({ timeout: 5000 });
  await expect(page.getByText("failed", { exact: true })).toBeVisible({
    timeout: 6000,
  });
  await expect(
    page.getByText("optimization failed before solve").first(),
  ).toBeVisible();
  await expect(page.getByText(/solver stdout/)).toBeVisible();
  await expect(page.getByText(/second line/)).toBeVisible();
  await expect(page.getByText(/"status":"error"/)).toBeVisible();
});
