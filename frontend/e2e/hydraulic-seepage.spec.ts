import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

test("filtration is opt-in, editable, persistent and removable for each reach", async ({
  page,
}, testInfo) => {
  test.setTimeout(90_000);
  page.setDefaultTimeout(10_000);
  const api = page.request;
  const headers = async () => ({
    "X-CSRF-Token": (await (await api.get("/api/auth/csrf")).json()).csrf_token,
  });
  const auth = await (await api.get("/api/auth/me")).json();
  const login = await api.post(
    auth.bootstrap_required ? "/api/auth/bootstrap" : "/api/auth/login",
    {
      headers: await headers(),
      data: {
        email: "admin@example.local",
        display_name: "Analista",
        password: "admin-pass",
      },
    },
  );
  expect(login.ok()).toBeTruthy();
  const project = await (
    await api.post("/api/projects", {
      headers: await headers(),
      data: { name: "Filtración" },
    })
  ).json();
  const scenario = await (
    await api.post(`/api/projects/${project.id}/scenarios`, {
      headers: await headers(),
      data: { name: "Curva cota–filtración" },
    })
  ).json();
  const root = `/api/scenarios/${scenario.id}/hydraulic-diagram`;
  const initial = await (
    await api.post(root, { headers: await headers() })
  ).json();
  const python =
    process.env.PYTHON ||
    [
      resolve("../.venv/Scripts/python.exe"),
      resolve("../.venv/bin/python"),
    ].find(existsSync) ||
    "python";
  const nodes = JSON.parse(
    execFileSync(
      python,
      [
        "-c",
        "import json; from tests.test_hydro_diagram_acceptance import complete_v3_nodes; print(json.dumps(complete_v3_nodes()))",
      ],
      {
        cwd: resolve(".."),
        encoding: "utf8",
        windowsHide: true,
      },
    ),
  );
  nodes[1].x = nodes[0].x + 200;
  nodes[1].y = nodes[0].y + 250;
  const seeded = await api.put(root, {
    headers: await headers(),
    data: {
      revision: initial.diagram.revision,
      nodes,
      reaches: ["canal_a", "canal_b"].map((key, i) => ({
        technical_key: key,
        display_name: key,
        from_node_key: "reservoir_alpha",
        to_node_key: "junction_in",
        reach_type: "canal",
        from_anchor: 0.2 + i * 0.6,
        to_anchor: 0.2 + i * 0.6,
      })),
    },
  });
  expect(seeded.ok(), await seeded.text()).toBeTruthy();
  await page.goto(`/react/scenarios/${scenario.id}/hydraulic-diagram`);
  await page.getByTestId("hydraulic-link-canal_a").click();
  await expect(
    page.getByText("Filtración según cota", { exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "+ Agregar comportamiento", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Filtración según cota", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Filtración según cota" }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Editar tabla y gráfico" }).click();
  const editor = page.getByRole("dialog", {
    name: "Curva de filtración · canal_a",
  });
  await expect(editor).toBeVisible();
  await expect(
    editor.getByRole("button", { name: "Listo", exact: true }),
  ).toBeDisabled();
  for (const [i, [h, q]] of [
    [700, 0],
    [720, 2],
    [760, 10],
  ].entries()) {
    await editor
      .getByRole("button", { name: "Agregar punto", exact: true })
      .click();
    await editor
      .getByLabel(`Cota punto ${i + 1}`, { exact: true })
      .fill(String(h));
    await editor
      .getByLabel(`Caudal punto ${i + 1}`, { exact: true })
      .fill(String(q));
  }
  await editor.getByText("Configuración avanzada", { exact: true }).click();
  await editor
    .getByLabel("Cota de referencia", { exact: true })
    .selectOption("end");
  await editor.getByRole("button", { name: "Listo", exact: true }).click();
  await page.getByTestId("hydraulic-link-canal_b").click();
  await expect(
    page.getByRole("heading", { name: "Filtración según cota" }),
  ).toHaveCount(0);
  await page.getByTestId("hydraulic-link-canal_a").click();
  await expect(
    page.getByText("reservoir_alpha · 3 puntos · Cota al cierre", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Guardar diagrama", exact: true })
    .click();
  await expect(page.getByText("Estado: saved", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByTestId("hydraulic-link-canal_a").click();
  await expect(
    page.getByText("reservoir_alpha · 3 puntos · Cota al cierre", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Editar tabla y gráfico" }).click();
  await expect(
    editor.getByLabel("Caudal punto 3", { exact: true }),
  ).toHaveValue("10");
  await page.screenshot({
    path: testInfo.outputPath("filtration-curve.png"),
    fullPage: true,
  });
  await editor.getByRole("button", { name: "Cancelar", exact: true }).click();
  await page
    .getByRole("button", { name: "Quitar filtración", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Guardar diagrama", exact: true })
    .click();
  await expect(page.getByText("Estado: saved", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByTestId("hydraulic-link-canal_a").click();
  await expect(
    page.getByRole("heading", { name: "Filtración según cota" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "+ Agregar comportamiento", exact: true }),
  ).toBeVisible();
});
