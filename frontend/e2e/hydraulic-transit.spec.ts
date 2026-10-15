import { expect, test } from "@playwright/test";

test("edits and reloads travel times and units on reaches and both plant connections", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const api = page.request;
  const headers = async () => ({
    "X-CSRF-Token": (await (await api.get("/api/auth/csrf")).json()).csrf_token,
  });
  const auth = await (await api.get("/api/auth/me")).json();
  expect(
    (
      await api.post(
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
      )
    ).ok(),
  ).toBeTruthy();
  const project = await (
    await api.post("/api/projects", {
      headers: await headers(),
      data: { name: "Travel times" },
    })
  ).json();
  const scenario = await (
    await api.post(`/api/projects/${project.id}/scenarios`, {
      headers: await headers(),
      data: { name: "Variable intervals" },
    })
  ).json();
  const root = `/api/scenarios/${scenario.id}/hydraulic-diagram`;
  const initial = (
    await (await api.post(root, { headers: await headers() })).json()
  ).diagram;
  const saved = await api.put(root, {
    headers: await headers(),
    data: {
      revision: initial.revision,
      nodes: [
        {
          component_type: "junction",
          technical_key: "upstream",
          display_name: "Upstream",
          x: 100,
          y: 50,
        },
        {
          component_type: "plant",
          technical_key: "plant",
          display_name: "Plant",
          x: 350,
          y: 220,
          units: [
            {
              technical_key: "unit",
              display_name: "Unit",
              intake_node_key: "upstream",
              discharge_node_key: "downstream",
            },
          ],
        },
        {
          component_type: "junction",
          technical_key: "downstream",
          display_name: "Downstream",
          x: 600,
          y: 400,
        },
      ],
      reaches: [
        {
          technical_key: "river",
          display_name: "River",
          from_node_key: "upstream",
          to_node_key: "downstream",
          reach_type: "river",
        },
      ],
    },
  });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  await page.goto(`/react/scenarios/${scenario.id}/hydraulic-diagram`);

  async function select(id: string) {
    const path = page.getByTestId(id);
    await expect(path).toBeVisible();
    await path.scrollIntoViewIfNeeded();
    const point = await path.evaluate((element) => {
      const path = element as SVGPathElement;
      for (let fraction = 0.2; fraction < 0.9; fraction += 0.02) {
        const p = path.getPointAtLength(path.getTotalLength() * fraction);
        const screen = new DOMPoint(p.x, p.y).matrixTransform(
          path.getScreenCTM()!,
        );
        if (document.elementFromPoint(screen.x, screen.y) === path)
          return { x: screen.x, y: screen.y };
      }
      throw new Error("No visible connection segment");
    });
    await page.mouse.click(point.x, point.y);
  }
  const amount = page.getByRole("spinbutton", {
    name: "Tiempo de viaje",
    exact: true,
  });
  const unit = page.getByRole("combobox", {
    name: "Unidad del tiempo de viaje",
    exact: true,
  });
  await select("hydraulic-link-river");
  await unit.selectOption("seconds");
  await amount.fill("2700");
  await unit.selectOption("hours");
  await expect(amount).toHaveValue("0.75");
  await unit.selectOption("minutes");
  await expect(amount).toHaveValue("45");
  await select("hydraulic-plant-link-upstream-plant");
  await unit.selectOption("seconds");
  await amount.fill("900");
  await select("hydraulic-plant-link-plant-downstream");
  await unit.selectOption("days");
  await amount.fill("0.0625");
  await page
    .getByRole("button", { name: "Guardar diagrama", exact: true })
    .click();
  await expect(page.getByText("Estado: saved", { exact: true })).toBeVisible();
  const diagram = (await (await api.get(root)).json()).diagram;
  expect(diagram.reaches[0]).toMatchObject({
    travel_time_hours: 0.75,
    travel_time_unit: "minutes",
    routing_method: "fixed_delay",
  });
  expect(
    diagram.nodes.find(
      (n: { technical_key: string }) => n.technical_key === "plant",
    ).link_transit,
  ).toMatchObject({
    "in:upstream": { travel_time_hours: 0.25, travel_time_unit: "seconds" },
    "out:downstream": { travel_time_hours: 1.5, travel_time_unit: "days" },
  });
  await page.reload();
  for (const [id, selectedUnit, value] of [
    ["hydraulic-link-river", "minutes", "45"],
    ["hydraulic-plant-link-upstream-plant", "seconds", "900"],
    ["hydraulic-plant-link-plant-downstream", "days", "0.0625"],
  ]) {
    await select(id);
    await expect(unit).toHaveValue(selectedUnit);
    await expect(amount).toHaveValue(value);
  }
  await page.screenshot({
    path: testInfo.outputPath("travel-time-properties.png"),
    fullPage: true,
  });
});
