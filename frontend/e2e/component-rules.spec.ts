import { expect, test } from "@playwright/test";

test("REG-001 edits and reopens Python from a hydraulic unit without applying it", async ({
  page,
}) => {
  const api = page.request;
  const csrf = async () =>
    (await (await api.get("/api/auth/csrf")).json()).csrf_token;
  const identity = await (await api.get("/api/auth/me")).json();
  const login = await api.post(
    identity.bootstrap_required ? "/api/auth/bootstrap" : "/api/auth/login",
    {
      headers: { "X-CSRF-Token": await csrf() },
      data: {
        email: "admin@example.local",
        display_name: "Admin User",
        password: "admin-pass",
        next: "/react/projects",
      },
    },
  );
  expect(login.ok()).toBeTruthy();
  const project = await (
    await api.post("/api/projects", {
      headers: { "X-CSRF-Token": await csrf() },
      data: { name: "REG-001 Browser" },
    })
  ).json();
  const scenario = await (
    await api.post(`/api/projects/${project.id}/scenarios`, {
      headers: { "X-CSRF-Token": await csrf() },
      data: { name: "Unidad de prueba" },
    })
  ).json();
  const initial = await (
    await api.post(`/api/scenarios/${scenario.id}/hydraulic-diagram`, {
      headers: { "X-CSRF-Token": await csrf() },
      data: {},
    })
  ).json();
  const saved = await api.put(
    `/api/scenarios/${scenario.id}/hydraulic-diagram`,
    {
      headers: { "X-CSRF-Token": await csrf() },
      data: {
        revision: initial.diagram.revision,
        nodes: [
          {
            component_type: "plant",
            technical_key: "plant",
            display_name: "Central",
            x: 0,
            y: 0,
            units: [
              {
                technical_key: "unit",
                display_name: "Unidad",
                is_active: true,
              },
            ],
          },
        ],
      },
    },
  );
  expect(saved.ok()).toBeTruthy();
  await page.goto(`/react/scenarios/${scenario.id}/hydraulic-diagram`);
  await page.getByRole("group", { name: "Central plant", exact: true }).click();
  await page
    .getByRole("link", { name: "Cálculos y restricciones · unit" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Cálculos y restricciones" }),
  ).toBeVisible();
  await page
    .getByLabel("Nombre de la regla")
    .fill("Capacidad por disponibilidad");
  const editor = page.getByRole("textbox", { name: "Código Python" });
  await editor.fill(
    "def construir(ctx):\n    return ctx.parametros.capacidad * ctx.parametros.disponibilidad\n",
  );
  await page.getByRole("button", { name: "Guardar borrador" }).click();
  await expect(
    page.getByText("Borrador guardado · revisión 1", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(editor).toContainText("def construir(ctx)");
  await expect(page.getByLabel("Valor capacidad")).toHaveValue("80");
  await expect(page.getByLabel("Valor disponibilidad")).toHaveValue("0.75");
  await expect(
    page.getByRole("button", { name: "Probar borrador" }),
  ).toBeDisabled();
  await expect(
    page.getByText(/Las pruebas no modifican corridas ni series/),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/reg001-editor.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Volver a la unidad" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/scenarios/${scenario.id}/hydraulic-diagram$`),
  );
});
