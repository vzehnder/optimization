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

async function deleteWithCsrf(api: APIRequestContext, path: string) {
  return api.delete(path, {
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

test("React hydraulic diagram persists reservoir junction and plant nodes across reload", async ({
  page,
}) => {
  await ensureAdminSession(page);
  const suffix = Date.now();
  const api = page.context().request;
  const projectResponse = await postWithCsrf(api, "/api/projects", {
    name: `Hydro Diagram ${suffix}`,
    description: "Hydraulic diagram browser acceptance",
  });
  expect(projectResponse.status()).toBe(201);
  const project = (await projectResponse.json()) as { id: number };
  const scenarioResponse = await postWithCsrf(
    api,
    `/api/projects/${project.id}/scenarios`,
    {
      name: `Hydraulic topology ${suffix}`,
      description: "Minimal persisted hydraulic graph",
    },
  );
  expect(scenarioResponse.status()).toBe(201);
  const scenario = (await scenarioResponse.json()) as { id: number };

  await page.goto(`/react/scenarios/${scenario.id}`);
  await page.getByRole("link", { name: "Abrir diagrama hidraulico" }).click();
  await expect(
    page.getByRole("heading", { name: "Diagrama hidraulico" }),
  ).toBeVisible();
  await expect(page.getByText("Estado: saved")).toBeVisible();

  await page.getByRole("button", { name: "Agregar embalse" }).click();
  await page.getByRole("button", { name: "Agregar union" }).click();
  await page.getByRole("button", { name: "Agregar central" }).click();
  await page.getByLabel("Etiqueta plant_1").fill("Plant Laja");
  await expect(page.getByText("Estado: dirty")).toBeVisible();
  await page.getByRole("button", { name: "Guardar diagrama" }).click();
  await expect(page.getByText("Estado: saved")).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Diagrama hidraulico" }),
  ).toBeVisible();
  await expect(page.getByLabel("Etiqueta reservoir_1")).toHaveValue(
    "Reservoir 1",
  );
  await expect(page.getByLabel("Etiqueta junction_1")).toHaveValue(
    "Junction 1",
  );
  await expect(page.getByLabel("Etiqueta plant_1")).toHaveValue("Plant Laja");
});

test("React admin users and project access cover assignment, removal, deactivation, and denials", async ({
  page,
}) => {
  await ensureAdminSession(page);
  const suffix = Date.now();
  const clientEmail = `portal-client-${suffix}@example.local`;
  const analystEmail = `ops-analyst-${suffix}@example.local`;
  const secondAdminEmail = `second-admin-${suffix}@example.local`;
  const projectName = `Access PMGD ${suffix}`;

  async function createUser(
    email: string,
    name: string,
    role: "admin" | "analyst" | "client",
    password: string,
  ) {
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Nombre").fill(name);
    await page.getByLabel("Password").fill(password);
    await page.getByLabel("Rol").selectOption(role);
    await page.getByRole("button", { name: "Crear usuario" }).click();
    await expect(page.getByText(`${email} creado.`)).toBeVisible();
  }

  async function login(email: string, password: string) {
    await expect(
      page.getByRole("heading", { name: "Iniciar sesion" }),
    ).toBeVisible();
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Entrar" }).click();
  }

  await page.getByRole("link", { name: "Admin" }).click();
  await expect(page.getByRole("heading", { name: "Usuarios" })).toBeVisible();
  await createUser(clientEmail, "Portal Client", "client", "client-pass");
  await createUser(analystEmail, "Ops Analyst", "analyst", "analyst-pass");
  await createUser(secondAdminEmail, "Second Admin", "admin", "admin-pass");

  await page.getByLabel("Email").fill(clientEmail);
  await page.getByLabel("Nombre").fill("Duplicate Client");
  await page.getByLabel("Password").fill("client-pass");
  await page.getByLabel("Rol").selectOption("client");
  await page.getByRole("button", { name: "Crear usuario" }).click();
  await expect(page.getByRole("alert")).toContainText("email already exists");

  await page.getByRole("link", { name: "Analista" }).click();
  await page.getByLabel("Nombre del proyecto").fill(projectName);
  await page
    .getByLabel("Descripcion del proyecto")
    .fill("Client access browser acceptance");
  await page.getByRole("button", { name: "Crear proyecto" }).click();
  await page.getByRole("link", { name: projectName }).click();
  await expect(
    page.getByRole("heading", { name: "Acceso cliente" }),
  ).toBeVisible();

  await page
    .getByLabel("Cliente elegible")
    .selectOption({ label: clientEmail });
  await page.getByRole("button", { name: "Asignar cliente" }).click();
  await expect(
    page.getByText(`${clientEmail} asignado a ${projectName}.`),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: `Quitar ${clientEmail}` }),
  ).toBeVisible();

  await page.getByRole("button", { name: `Quitar ${clientEmail}` }).click();
  await expect(page.getByText(`Confirma quitar ${clientEmail}`)).toBeVisible();
  await page
    .getByRole("button", { name: `Confirmar quitar ${clientEmail}` })
    .click();
  await expect(
    page.getByText(`${clientEmail} sin acceso a ${projectName}.`),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: `Quitar ${clientEmail}` }),
  ).toHaveCount(0);

  await page.getByRole("button", { name: "Salir" }).click();
  await login(analystEmail, "analyst-pass");
  await expect(page).toHaveURL(/\/react\/projects$/);
  await page.goto("/react/admin/users");
  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();

  await page.getByRole("button", { name: "Salir" }).click();
  await login(clientEmail, "client-pass");
  await expect(page).toHaveURL(/\/react\/client$/);
  await page.goto("/react/admin/users");
  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();

  await page.getByRole("button", { name: "Salir" }).click();
  await login("admin@example.local", "admin-pass");
  await page.getByRole("link", { name: "Admin" }).click();
  await page.getByRole("button", { name: `Desactivar ${clientEmail}` }).click();
  await expect(
    page.getByText(`Confirma desactivar ${clientEmail}`),
  ).toBeVisible();
  await page
    .getByRole("button", { name: `Confirmar desactivar ${clientEmail}` })
    .click();
  await expect(page.getByText(`${clientEmail} desactivado.`)).toBeFocused();

  await page.getByRole("button", { name: "Salir" }).click();
  await login(clientEmail, "client-pass");
  await expect(page.getByRole("alert")).toContainText(
    "Invalid email or password.",
  );
});

test("React client portal reviews published results, downloads allowlisted artifacts, and honors revocation", async ({
  page,
  baseURL,
}) => {
  test.setTimeout(90_000);
  await ensureAdminSession(page);
  const suffix = Date.now();
  const api = page.context().request;
  const analystEmail = `portal-analyst-${suffix}@example.local`;
  const clientEmail = `published-client-${suffix}@example.local`;
  const projectName = `Published PMGD ${suffix}`;
  const templateName = `Client Summary ${suffix}`;
  const publicationTitle = `Client Dispatch Review ${suffix}`;
  const sampleCase = readFileSync(
    resolve("..", "data/cases/hybrid_system/system_case.json"),
    "utf-8",
  );

  async function loginThroughPage(email: string, password: string) {
    await expect(
      page.getByRole("heading", { name: "Iniciar sesion" }),
    ).toBeVisible();
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).toHaveURL(/\/react\/(projects|client)$/);
  }

  const analystResponse = await postWithCsrf(api, "/api/admin/users", {
    email: analystEmail,
    display_name: "Portal Analyst",
    role: "analyst",
    password: "analyst-pass",
  });
  expect(analystResponse.status()).toBe(201);
  const clientResponse = await postWithCsrf(api, "/api/admin/users", {
    email: clientEmail,
    display_name: "Published Client",
    role: "client",
    password: "client-pass",
  });
  expect(clientResponse.status()).toBe(201);
  const clientUser = ((await clientResponse.json()) as { user: { id: number } })
    .user;
  const projectResponse = await postWithCsrf(api, "/api/projects", {
    name: projectName,
    description: "Published client project",
  });
  expect(projectResponse.status()).toBe(201);
  const project = (await projectResponse.json()) as { id: number };
  const scenarioResponse = await postWithCsrf(
    api,
    `/api/projects/${project.id}/scenarios`,
    {
      name: `Client scenario ${suffix}`,
      description: "Published results branch",
    },
  );
  expect(scenarioResponse.status()).toBe(201);
  const scenario = (await scenarioResponse.json()) as { id: number };
  const versionResponse = await postWithCsrf(
    api,
    `/api/scenarios/${scenario.id}/versions`,
    { system_case_json: sampleCase },
  );
  expect(versionResponse.status()).toBe(201);
  const version = (await versionResponse.json()) as { id: number };
  const runResponse = await postWithCsrf(
    api,
    `/api/scenario-versions/${version.id}/runs`,
  );
  expect(runResponse.status()).toBe(201);
  const run = (await runResponse.json()) as { id: number };

  await page.goto(`/react/projects/${project.id}`);
  await expect(page.getByRole("heading", { name: projectName })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Acceso cliente" }),
  ).toBeVisible();
  await page
    .getByLabel("Cliente elegible")
    .selectOption({ label: clientEmail });
  await page.getByRole("button", { name: "Asignar cliente" }).click();
  await expect(
    page.getByText(`${clientEmail} asignado a ${projectName}.`),
  ).toBeVisible();

  await page.getByRole("button", { name: "Salir" }).click();
  await loginThroughPage(analystEmail, "analyst-pass");
  await page.goto(`/react/projects/${project.id}`);
  await expect(page.getByRole("heading", { name: projectName })).toBeVisible();
  await page.getByLabel("Nombre nuevo template").fill(templateName);
  await page.getByLabel("Asset dispatch table").uncheck();
  await page.getByRole("button", { name: "Crear template" }).click();
  await expect(page.getByText(templateName).first()).toBeVisible();

  await page.goto(`/react/runs/${run.id}`);
  await expect(
    page.getByRole("heading", { name: `Run ${run.id}` }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Publication Drafts" }),
  ).toBeVisible();
  await page.getByLabel("Public Title").fill(publicationTitle);
  await page.getByLabel("Analyst Notes").fill("Approved for client review.");
  await page.getByLabel("dispatch_csv", { exact: true }).uncheck();
  await page.getByLabel("asset_dispatch_csv", { exact: true }).uncheck();
  const createPublication = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/runs/${run.id}/publications`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Crear publicacion" }).click();
  const publication = (
    (await (await createPublication).json()) as { publication: { id: number } }
  ).publication;
  await expect(page.getByText(publicationTitle).first()).toBeVisible();
  await page
    .getByRole("button", { name: `Publicar ${publicationTitle}` })
    .click();
  await expect(
    page.getByRole("button", { name: `Unpublicar ${publicationTitle}` }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Salir" }).click();
  await loginThroughPage(clientEmail, "client-pass");
  await expect(page).toHaveURL(/\/react\/client$/);
  await expect(
    page.getByRole("heading", { name: "Portal cliente" }),
  ).toBeVisible();
  await page.getByRole("link", { name: projectName }).click();
  await expect(page.getByRole("heading", { name: projectName })).toBeVisible();
  await expect(page.getByText(publicationTitle)).toBeVisible();
  await page.getByRole("link", { name: publicationTitle }).click();
  await expect(
    page.getByRole("heading", { name: publicationTitle }),
  ).toBeVisible();
  await expect(page.getByText("Approved for client review.")).toBeVisible();
  await expect(page.getByText("1250.5")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "System Dispatch" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Energy Price" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Asset Dispatch" }),
  ).toHaveCount(0);
  await expect(page.getByText("Publication Drafts")).toHaveCount(0);
  await expect(page.getByText("Crear publicacion")).toHaveCount(0);
  await expect(page.getByText("Lanzar run")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "dispatch.csv" })).toHaveCount(0);
  const summaryDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "summary.json" }).click();
  expect((await summaryDownload).suggestedFilename()).toBe("summary.json");

  const adminApi = await requestFactory.newContext({ baseURL });
  await apiLogin(adminApi, "admin@example.local", "admin-pass");
  const removeAccess = await deleteWithCsrf(
    adminApi,
    `/api/admin/projects/${project.id}/client-access/${clientUser.id}`,
  );
  expect(removeAccess.ok()).toBeTruthy();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "No encontrado" }),
  ).toBeVisible();
  await expect(page.getByText(publicationTitle)).toHaveCount(0);

  const reassign = await postWithCsrf(
    adminApi,
    `/api/admin/projects/${project.id}/client-access`,
    { user_id: clientUser.id },
  );
  expect(reassign.status()).toBe(201);
  await page.goto(
    `/react/client/projects/${project.id}/publications/${publication.id}`,
  );
  await expect(
    page.getByRole("heading", { name: publicationTitle }),
  ).toBeVisible();
  const unpublish = await postWithCsrf(
    adminApi,
    `/api/publications/${publication.id}/unpublish`,
  );
  expect(unpublish.ok()).toBeTruthy();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "No encontrado" }),
  ).toBeVisible();
  await expect(page.getByText(publicationTitle)).toHaveCount(0);

  const republish = await postWithCsrf(
    adminApi,
    `/api/publications/${publication.id}/publish`,
  );
  expect(republish.ok()).toBeTruthy();
  await page.goto(
    `/react/client/projects/${project.id}/publications/${publication.id}`,
  );
  await expect(
    page.getByRole("heading", { name: publicationTitle }),
  ).toBeVisible();
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
  await expect(
    page.getByLabel("Run state").getByText("0", { exact: true }),
  ).toBeVisible();
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

test("React run results renders Plotly charts, tables, missing legacy columns, and artifact downloads", async ({
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
    name: `Results PMGD ${suffix}`,
    description: "Run results browser acceptance",
  });
  expect(projectResponse.ok()).toBeTruthy();
  const project = (await projectResponse.json()) as { id: number };
  const scenarioResponse = await postWithCsrf(
    api,
    `/api/projects/${project.id}/scenarios`,
    {
      name: `Results review ${suffix}`,
      description: "Charts tables artifacts",
    },
  );
  expect(scenarioResponse.ok()).toBeTruthy();
  const scenario = (await scenarioResponse.json()) as { id: number };
  const versionResponse = await postWithCsrf(
    api,
    `/api/scenarios/${scenario.id}/versions`,
    { system_case_json: sampleCase },
  );
  expect(versionResponse.status()).toBe(201);
  const version = (await versionResponse.json()) as {
    id: number;
    version_number: number;
  };
  const runResponse = await postWithCsrf(
    api,
    `/api/scenario-versions/${version.id}/runs`,
  );
  expect(runResponse.status()).toBe(201);
  const run = (await runResponse.json()) as {
    id: number;
    scenario_version_id: number;
    created_at: string;
  };

  const succeededRun = {
    ...run,
    status: "succeeded",
    started_at: "2026-06-24T10:00:01Z",
    finished_at: "2026-06-24T10:00:03Z",
    duration_seconds: 2,
    exit_code: 0,
    error_message: "",
    stdout: "",
    stderr: "",
    trigger_type: "manual",
    triggered_by: "internal_analyst",
  };
  const labels = ["2026-01-01T00:00:00", "2026-01-01T01:00:00"];
  const modernResults = {
    summary: {
      case_name: "hydro_system",
      schema_version: "bess_system_dispatch.v2",
      solver_name: "HiGHS",
      solver_status: "OPTIMAL",
      termination_status: "OPTIMAL",
      objective_value_usd: 900,
      hydro_totals: {
        total_hydro_generation_mwh: 5,
        terminal_water_value_usd: 550,
      },
    },
    dispatch_table: {
      columns: [
        "timestamp",
        "export_price_usd_per_mwh",
        "grid_import_mw",
        "grid_export_mw",
        "renewable_used_mw",
        "battery_charge_mw",
        "battery_discharge_mw",
        "battery_energy_mwh",
        "total_hydro_power_mw",
        "total_hydro_storage_hm3",
        "period_profit_usd",
      ],
      rows: [
        {
          timestamp: labels[0],
          export_price_usd_per_mwh: "80.0",
          grid_import_mw: "0.0",
          grid_export_mw: "2.0",
          renewable_used_mw: "1.0",
          battery_charge_mw: "0.0",
          battery_discharge_mw: "0.5",
          battery_energy_mwh: "10.0",
          total_hydro_power_mw: "2.0",
          total_hydro_storage_hm3: "3.0",
          period_profit_usd: "160.0",
        },
        {
          timestamp: labels[1],
          export_price_usd_per_mwh: "100.0",
          grid_import_mw: "0.0",
          grid_export_mw: "3.0",
          renewable_used_mw: "1.5",
          battery_charge_mw: "0.0",
          battery_discharge_mw: "0.25",
          battery_energy_mwh: "9.5",
          total_hydro_power_mw: "3.0",
          total_hydro_storage_hm3: "3.2",
          period_profit_usd: "849.0",
        },
      ],
    },
    asset_dispatch_table: {
      columns: [
        "timestamp",
        "asset_id",
        "asset_type",
        "hydro_power_mw",
        "hydro_reservoir_elevation_masl",
      ],
      rows: [
        {
          timestamp: labels[0],
          asset_id: "hydro_1",
          asset_type: "hydro",
          hydro_power_mw: "2.0",
          hydro_reservoir_elevation_masl: "710.0",
        },
      ],
    },
    charts: {
      price: chart("price", "Energy Price", labels, [
        [
          "export_price_usd_per_mwh",
          "Export Price USD/MWh",
          "USD/MWh",
          [80, 100],
        ],
      ]),
      grid_import_export: chart(
        "grid-import-export",
        "Grid Import / Export",
        labels,
        [
          ["grid_import_mw", "Grid Import MW", "MW", [0, 0]],
          ["grid_export_mw", "Grid Export MW", "MW", [2, 3]],
        ],
      ),
      renewable_used_curtailed: chart(
        "renewable-used-curtailed",
        "Renewable Used / Curtailed",
        labels,
        [["renewable_used_mw", "Renewable Used MW", "MW", [1, 1.5]]],
      ),
      bess_charge_discharge_soc: chart(
        "bess-charge-discharge-soc",
        "BESS Charge / Discharge / SOC",
        labels,
        [
          ["battery_discharge_mw", "BESS Discharge MW", "MW", [0.5, 0.25]],
          ["battery_energy_mwh", "BESS SOC MWh", "MWh", [10, 9.5]],
        ],
      ),
      hydro_power: chart("hydro-power", "Hydro Power", labels, [
        ["total_hydro_power_mw", "Hydro Power MW", "MW", [2, 3]],
      ]),
      hydro_storage: chart("hydro-storage", "Hydro Storage", labels, [
        ["total_hydro_storage_hm3", "Hydro Storage hm3", "hm3", [3, 3.2]],
      ]),
      period_profit: chart("period-profit", "Period Profit", labels, [
        ["period_profit_usd", "Period Profit USD", "USD", [160, 849]],
      ]),
    },
    plot_series: [],
  };
  const artifact = {
    id: 901,
    run_id: run.id,
    artifact_type: "summary_json",
    path: "safe/artifacts/runs/results/summary.json",
    display_name: "summary.json",
    media_type: "application/json",
    byte_size: 42,
    created_at: "2026-06-24T10:00:03Z",
    download_url: "/api/run-artifacts/901/download",
  };

  await page.route(`**/api/runs/${run.id}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ run: succeededRun }),
    });
  });
  await page.route(`**/api/runs/${run.id}/results`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ results: modernResults }),
    });
  });
  await page.route(`**/api/runs/${run.id}/artifacts`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ artifacts: [artifact] }),
    });
  });
  await page.route("**/api/run-artifacts/901/download", async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "content-type": "application/json",
        "content-disposition": 'attachment; filename="summary.json"',
      },
      body: JSON.stringify({ termination_status: "OPTIMAL" }),
    });
  });

  await page.goto(`/react/runs/${run.id}`);
  await expect(
    page.getByRole("heading", { name: `Run ${run.id}` }),
  ).toBeVisible();
  await expect(page.getByText("hydro_system")).toBeVisible();
  await expect(page.getByText("total_hydro_generation_mwh")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Energy Price" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Hydro Power" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Period Profit" }),
  ).toBeVisible();
  await expect(page.locator(".js-plotly-plot").first()).toBeVisible({
    timeout: 10_000,
  });
  await expect(
    page.getByRole("heading", { name: "System Dispatch" }),
  ).toBeVisible();
  await expect(page.getByText("total_hydro_power_mw")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Asset Dispatch" }),
  ).toBeVisible();
  await expect(page.getByText("hydro_1")).toBeVisible();
  await expect(page.getByText("application/json")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "summary.json" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("summary.json");

  const legacyRunResponse = await postWithCsrf(
    api,
    `/api/scenario-versions/${version.id}/runs`,
  );
  expect(legacyRunResponse.status()).toBe(201);
  const legacyRun = (await legacyRunResponse.json()) as {
    id: number;
    scenario_version_id: number;
    created_at: string;
  };
  await page.route(`**/api/runs/${legacyRun.id}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run: {
          ...succeededRun,
          id: legacyRun.id,
          scenario_version_id: legacyRun.scenario_version_id,
          created_at: legacyRun.created_at,
        },
      }),
    });
  });
  await page.route(`**/api/runs/${legacyRun.id}/results`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        results: {
          ...modernResults,
          summary: {
            case_name: "legacy_system",
            schema_version: "bess_system_dispatch.v1",
            price_mode: "single_price",
          },
          charts: {
            ...modernResults.charts,
            hydro_power: {
              id: "hydro-power",
              title: "Hydro Power",
              available: false,
              labels: [],
              series: [],
              missing_columns: ["total_hydro_power_mw"],
              message: "Missing columns: total_hydro_power_mw",
            },
          },
        },
      }),
    });
  });
  await page.route(`**/api/runs/${legacyRun.id}/artifacts`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ artifacts: [] }),
    });
  });

  await page.goto(`/react/runs/${legacyRun.id}`);
  await expect(page.getByText("legacy_system")).toBeVisible();
  await expect(page.getByText("Unavailable charts")).toBeVisible();
  await expect(
    page.getByText("Missing columns: total_hydro_power_mw"),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText("legacy_system")).toBeVisible();
  await expect(
    page.getByText("Missing columns: total_hydro_power_mw"),
  ).toBeVisible();
});

test("React dashboard templates and publications cover draft preview publish and unpublish", async ({
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
    name: `Publication PMGD ${suffix}`,
    description: "Publication curation browser acceptance",
  });
  expect(projectResponse.ok()).toBeTruthy();
  const project = (await projectResponse.json()) as { id: number };
  const scenarioResponse = await postWithCsrf(
    api,
    `/api/projects/${project.id}/scenarios`,
    {
      name: `Publication case ${suffix}`,
      description: "Dashboard template and publication branch",
    },
  );
  expect(scenarioResponse.ok()).toBeTruthy();
  const scenario = (await scenarioResponse.json()) as { id: number };
  const versionResponse = await postWithCsrf(
    api,
    `/api/scenarios/${scenario.id}/versions`,
    { system_case_json: sampleCase },
  );
  expect(versionResponse.status()).toBe(201);
  const version = (await versionResponse.json()) as {
    id: number;
    version_number: number;
  };
  const runResponse = await postWithCsrf(
    api,
    `/api/scenario-versions/${version.id}/runs`,
  );
  expect(runResponse.status()).toBe(201);
  const run = (await runResponse.json()) as { id: number };

  await page.goto(`/react/projects/${project.id}`);
  await expect(
    page.getByRole("heading", { name: "Dashboard templates" }),
  ).toBeVisible();

  const templateName = `Client Summary ${suffix}`;
  const updatedTemplateName = `Client Board ${suffix}`;
  await page.getByLabel("Nombre nuevo template").fill(templateName);
  await page.getByLabel("Renewable chart").uncheck();
  await page.getByLabel("Asset dispatch table").uncheck();
  await page.getByLabel("Table row limit").fill("1");
  await page.getByRole("button", { name: "Crear template" }).click();
  await expect(page.getByText(templateName, { exact: true })).toBeVisible();

  await page.getByRole("button", { name: `Editar ${templateName}` }).click();
  await page
    .getByLabel("Nombre del template editado")
    .fill(updatedTemplateName);
  await page.getByRole("button", { name: "Actualizar template" }).click();
  await expect(
    page.getByText(updatedTemplateName, { exact: true }),
  ).toBeVisible();

  await page.goto(`/react/runs/${run.id}`);
  await expect(page.getByText("succeeded", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Publication Drafts" }),
  ).toBeVisible();
  await page.getByLabel("Dashboard Template").selectOption({
    label: updatedTemplateName,
  });
  await page.getByLabel("Public Title").fill("Board Dispatch Review");
  await page
    .getByLabel("Analyst Notes")
    .fill("Approved assumptions for preview.");
  await page.getByLabel("model_metadata_json").check();
  const createPublication = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/runs/${run.id}/publications`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Crear publicacion" }).click();
  const publication = (await (await createPublication).json()) as {
    publication: { id: number };
  };
  await expect(
    page.getByText("Board Dispatch Review", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".role-badge", { hasText: "draft" })).toBeVisible();

  let failNextPublicationUpdate = true;
  await page.route("**/api/publications/*", async (route) => {
    if (route.request().method() === "PUT" && failNextPublicationUpdate) {
      failNextPublicationUpdate = false;
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "synthetic publication save failure" }),
      });
      return;
    }
    await route.continue();
  });

  await page
    .getByRole("button", { name: "Editar publicacion Board Dispatch Review" })
    .click();
  await page.getByLabel("Public Title editado").fill("Board Dispatch Final");
  await page.getByLabel("Analyst Notes editadas").fill("Final preview notes.");
  await page.getByRole("button", { name: "Actualizar publicacion" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "synthetic publication save failure",
  );
  await expect(page.getByLabel("Public Title editado")).toHaveValue(
    "Board Dispatch Final",
  );
  await page.getByRole("button", { name: "Actualizar publicacion" }).click();
  await expect(
    page.getByText("Board Dispatch Final", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Final preview notes.", { exact: true }),
  ).toBeVisible();

  await page
    .getByRole("link", { name: "Preview as client Board Dispatch Final" })
    .click();
  await expect(page).toHaveURL(
    new RegExp(`/react/publications/${publication.publication.id}/preview$`),
  );
  await expect(
    page.getByRole("heading", { name: "Board Dispatch Final" }),
  ).toBeVisible();
  await expect(page.getByText("Final preview notes.")).toBeVisible();
  await expect(page.getByText("Objective Value")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "System Dispatch" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Asset Dispatch" }),
  ).toHaveCount(0);
  await expect(page.getByText("Publication Drafts")).toHaveCount(0);

  await page.goto(`/react/runs/${run.id}`);
  await page
    .getByRole("button", { name: "Publicar Board Dispatch Final" })
    .click();
  await expect(
    page.locator(".role-badge", { hasText: "published" }),
  ).toBeVisible();
  await expect(page.getByText("Published by")).toBeVisible();
  await expect(page.getByText("admin@example.local").first()).toBeVisible();
  await page
    .getByRole("button", { name: "Unpublicar Board Dispatch Final" })
    .click();
  await expect(
    page.locator(".role-badge", { hasText: "unpublished" }),
  ).toBeVisible();
  await expect(page.getByText("Unpublished at")).toBeVisible();
});

function chart(
  id: string,
  title: string,
  labels: string[],
  series: Array<[string, string, string, number[]]>,
) {
  return {
    id,
    title,
    available: true,
    labels,
    series: series.map(([key, label, unit, values]) => ({
      key,
      label,
      unit,
      values,
    })),
    missing_columns: [],
    message: "",
  };
}
