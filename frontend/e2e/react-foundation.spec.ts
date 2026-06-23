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
