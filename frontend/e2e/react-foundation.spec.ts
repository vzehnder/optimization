import {
  expect,
  request as requestFactory,
  test,
  type APIRequestContext,
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
    page.getByRole("heading", { name: "Area analista" }),
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
