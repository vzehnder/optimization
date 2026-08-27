/// <reference lib="dom" />
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

const SERIOUS_IMPACTS = new Set(["serious", "critical"]);
const INTERACTIVE_TAGS = new Set([
  "A",
  "BUTTON",
  "INPUT",
  "SELECT",
  "TEXTAREA",
]);

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

async function putWithCsrf(
  api: APIRequestContext,
  path: string,
  data?: unknown,
) {
  return api.put(path, {
    data,
    headers: { "X-CSRF-Token": await csrfToken(api) },
  });
}

/**
 * Runs an automated WCAG 2.0/2.1 A and AA accessibility audit and fails on any
 * violation of serious or critical impact. The descriptive label and rendered
 * violation list keep regressions debuggable from the test report alone.
 */
async function expectNoSeriousAccessibilityViolations(
  page: Page,
  label: string,
) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = results.violations.filter((violation) =>
    SERIOUS_IMPACTS.has(violation.impact ?? ""),
  );
  const summary = blocking
    .map(
      (violation) =>
        `${violation.id} (${violation.impact}): ${violation.help} [${violation.nodes
          .map((node) => node.target.join(" "))
          .join(", ")}]`,
    )
    .join("\n");
  expect(summary, `${label} accessibility violations:\n${summary}`).toBe("");
}

/**
 * Proves the page is operable with the keyboard alone: starting from no focus,
 * the Tab key must move focus into the document's interactive controls rather
 * than getting trapped on the body.
 */
async function expectKeyboardReachesInteractiveControls(
  page: Page,
  label: string,
) {
  await page.evaluate(() => {
    const active = document.activeElement as HTMLElement | null;
    active?.blur();
  });
  const reached: string[] = [];
  for (let step = 0; step < 15; step += 1) {
    await page.keyboard.press("Tab");
    const tag = await page.evaluate(
      () => document.activeElement?.tagName ?? "",
    );
    if (tag) reached.push(tag);
  }
  expect(
    reached.some((tag) => INTERACTIVE_TAGS.has(tag)),
    `${label} keyboard focus reached: ${reached.join(", ")}`,
  ).toBeTruthy();
}

test("representative React pages pass automated accessibility and keyboard smoke checks", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const suffix = Date.now();
  const sampleCase = readFileSync(
    resolve("..", "data/cases/hybrid_system/system_case.json"),
    "utf-8",
  );

  // Auth page: representative unauthenticated entry.
  await page.goto("/react");
  await expect(
    page.getByRole("heading", { name: /Crear admin|Iniciar sesion/ }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page, "auth");
  await expectKeyboardReachesInteractiveControls(page, "auth");

  // The auth form must be fully operable from the keyboard, including submit.
  await page.getByLabel("Email").focus();
  await page.keyboard.type("admin@example.local");
  const onBootstrap = await page
    .getByRole("heading", { name: "Crear admin" })
    .isVisible();
  if (onBootstrap) {
    await page.keyboard.press("Tab");
    await page.keyboard.type("Admin User");
  }
  await page.keyboard.press("Tab");
  await page.keyboard.type("admin-pass");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/react\/projects$/);

  // Seed a full analyst-to-client chain through the API for the editor,
  // results, and client portal pages.
  const api = page.context().request;
  const clientEmail = `a11y-client-${suffix}@example.local`;
  const projectName = `A11y Project ${suffix}`;

  const clientResponse = await postWithCsrf(api, "/api/admin/users", {
    email: clientEmail,
    display_name: "A11y Client",
    role: "external",
    password: "client-pass",
  });
  expect(clientResponse.status()).toBe(201);
  const clientUser = ((await clientResponse.json()) as { user: { id: number } })
    .user;

  const projectResponse = await postWithCsrf(api, "/api/projects", {
    name: projectName,
    description: "Accessibility coverage project",
  });
  expect(projectResponse.status()).toBe(201);
  const project = (await projectResponse.json()) as { id: number };

  const scenarioResponse = await postWithCsrf(
    api,
    `/api/projects/${project.id}/scenarios`,
    { name: `A11y scenario ${suffix}`, description: "Accessibility branch" },
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

  const templateResponse = await postWithCsrf(
    api,
    `/api/projects/${project.id}/dashboard-templates`,
    { name: `A11y template ${suffix}` },
  );
  expect(templateResponse.status()).toBe(201);
  const template = (
    (await templateResponse.json()) as { dashboard_template: { id: number } }
  ).dashboard_template;

  const publicationTitle = `A11y Publication ${suffix}`;
  const publicationResponse = await postWithCsrf(
    api,
    `/api/runs/${run.id}/publications`,
    {
      dashboard_template_id: template.id,
      public_title: publicationTitle,
      analyst_notes: "Accessibility review notes.",
    },
  );
  expect(publicationResponse.status()).toBe(201);
  const publication = (
    (await publicationResponse.json()) as { publication: { id: number } }
  ).publication;
  const publishResponse = await postWithCsrf(
    api,
    `/api/publications/${publication.id}/publish`,
  );
  expect(publishResponse.ok()).toBeTruthy();

  const assignResponse = await putWithCsrf(
    api,
    `/api/admin/projects/${project.id}/external-access/${clientUser.id}`,
    { portal_view: true, operate: false },
  );
  expect(assignResponse.status()).toBe(200);

  // Admin page.
  await page.goto("/react/admin/users");
  await expect(
    page.getByRole("heading", { name: "Administracion" }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page, "admin");
  await expectKeyboardReachesInteractiveControls(page, "admin");

  // Editor page.
  await page.goto(`/react/scenarios/${scenario.id}/draft`);
  await expect(
    page.getByRole("heading", { name: "Draft estructurado" }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page, "editor");
  await expectKeyboardReachesInteractiveControls(page, "editor");

  // Results page.
  await page.goto(`/react/runs/${run.id}`);
  await expect(
    page.getByRole("heading", { name: `Run ${run.id}` }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page, "results");
  await expectKeyboardReachesInteractiveControls(page, "results");

  // Client page: switch to the external identity with portal_view.
  await page.getByRole("button", { name: "Salir" }).click();
  await expect(
    page.getByRole("heading", { name: "Iniciar sesion" }),
  ).toBeVisible();
  await page.getByLabel("Email").fill(clientEmail);
  await page.getByLabel("Password").fill("client-pass");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/react\/client$/);
  await page.goto(
    `/react/client/projects/${project.id}/publications/${publication.id}`,
  );
  await expect(
    page.getByRole("heading", { name: publicationTitle }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page, "client");
  await expectKeyboardReachesInteractiveControls(page, "client");
});
