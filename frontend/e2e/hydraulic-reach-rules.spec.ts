import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

test("exports the real diagram guide and opens editable Python directly from a reach", async ({
  page,
}, testInfo) => {
  test.setTimeout(90_000);
  page.setDefaultTimeout(15_000);
  const api = page.request;
  const headers = async () => ({
    "X-CSRF-Token": (await (await api.get("/api/auth/csrf")).json()).csrf_token,
  });
  const auth = await (await api.get("/api/auth/me")).json();
  const signedIn = await api.post(
    auth.bootstrap_required ? "/api/auth/bootstrap" : "/api/auth/login",
    {
      headers: await headers(),
      data: {
        email: "admin@example.local",
        display_name: "Analista",
        password: "admin-pass",
        next: "/react/projects",
      },
    },
  );
  expect(signedIn.ok()).toBeTruthy();
  const project = await (
    await api.post("/api/projects", {
      headers: await headers(),
      data: { name: "Reach guide acceptance" },
    })
  ).json();
  const scenario = await (
    await api.post(`/api/projects/${project.id}/scenarios`, {
      headers: await headers(),
      data: { name: "Canales independientes" },
    })
  ).json();
  const root = `/api/scenarios/${scenario.id}/hydraulic-diagram`;
  const initial = await (
    await api.post(root, { headers: await headers() })
  ).json();
  // Reuse the authoritative HTTP acceptance fixture on an isolated smoke DB.
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
      { cwd: resolve(".."), encoding: "utf8", windowsHide: true },
    ),
  );
  // Distinct anchors keep all three parallel reaches clickable.
  nodes[1].x = nodes[0].x + 200;
  nodes[1].y = nodes[0].y + 250;
  const saved = await api.put(root, {
    headers: await headers(),
    data: {
      revision: initial.diagram.revision,
      viewport: { x: 0, y: 0, zoom: 1 },
      nodes,
      reaches: ["canal_a", "canal_b", "canal_c"].map((key, index) => ({
        technical_key: key,
        display_name: key,
        from_node_key: "reservoir_alpha",
        to_node_key: "junction_in",
        reach_type: "canal",
        from_anchor: 0.2 + index * 0.3,
        to_anchor: 0.2 + index * 0.3,
      })),
    },
  });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.goto(`/react/scenarios/${scenario.id}/hydraulic-diagram`);
  const downloadEvent = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "exportar diagram_info_constr.md" })
    .click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe("diagram_info_constr.md");
  const file = testInfo.outputPath("diagram_info_constr.md");
  await download.saveAs(file);
  const markdown = readFileSync(file, "utf8");
  expect(markdown).toContain("canal_a");
  expect(markdown).toContain("reservoir_alpha");
  expect(markdown).toContain("junction_in");
  expect(markdown).toContain(
    "ctx.objetos.b.caudal[t] + ctx.objetos.c.caudal[t]",
  );
  expect(markdown).toContain("| Estado | Guardado |");
  expect(markdown.match(/```python/g)?.length).toBeGreaterThanOrEqual(11);
  await page.getByTestId("hydraulic-link-canal_a").click();
  await page
    .getByRole("link", { name: "Cálculos y restricciones · canal_a" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Cálculos y restricciones" }),
  ).toBeVisible();
  const editor = page.getByRole("textbox", { name: "Código Python" });
  await expect(editor).toBeVisible();
  await expect(editor).toContainText("ctx.restriccion");
  await page
    .getByLabel("Objeto a relacionar")
    .selectOption({ label: "canal_b · canal_b" });
  await page.getByLabel("Alias del objeto").fill("b");
  await page.getByRole("button", { name: "Agregar alias" }).click();
  await expect(page.getByText("ctx.objetos.b.caudal[t] · m³/s")).toBeVisible();
  await editor.fill(
    'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("relacion", t, ctx.objeto.caudal[t] >= ctx.objetos.b.caudal[t])',
  );
  await page.getByRole("button", { name: "Guardar borrador" }).click();
  await expect(
    page.getByRole("button", { name: "Publicar revisión" }),
  ).toBeEnabled();
  await page.screenshot({
    path: testInfo.outputPath("reach-python-editor.png"),
    fullPage: true,
  });
});
