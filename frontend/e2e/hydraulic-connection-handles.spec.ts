import { expect, test } from "@playwright/test";

for (const zoom of [1, 1.5]) {
  test(`moves and saves both endpoints of reaches and plant links at zoom ${zoom}`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1200, height: 1000 });
    const api = page.request;
    const headers = async () => ({
      "X-CSRF-Token": (await (await api.get("/api/auth/csrf")).json())
        .csrf_token,
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
          next: "/react/projects",
        },
      },
    );
    expect(login.ok()).toBeTruthy();
    const project = await (
      await api.post("/api/projects", {
        headers: await headers(),
        data: { name: "Connection handles" },
      })
    ).json();
    const scenario = await (
      await api.post(`/api/projects/${project.id}/scenarios`, {
        headers: await headers(),
        data: { name: `Anchors ${zoom}` },
      })
    ).json();
    const root = `/api/scenarios/${scenario.id}/hydraulic-diagram`;
    const initial = await (
      await api.post(root, { headers: await headers() })
    ).json();
    const nodes = [
      {
        component_type: "junction",
        technical_key: "upstream",
        display_name: "Upstream",
        x: 120,
        y: 80,
      },
      {
        component_type: "plant",
        technical_key: "plant",
        display_name: "Plant",
        x: 360,
        y: 260,
        units: [
          {
            technical_key: "unit_1",
            display_name: "Unit 1",
            intake_node_key: "upstream",
            discharge_node_key: "downstream",
          },
        ],
        link_anchors: {
          "in:upstream": { from: 0.2, to: 0.8 },
          "out:downstream": { from: 0.7, to: 0.3 },
        },
      },
      {
        component_type: "junction",
        technical_key: "downstream",
        display_name: "Downstream",
        x: 600,
        y: 440,
      },
    ];
    const saved = await api.put(root, {
      headers: await headers(),
      data: {
        revision: initial.diagram.revision,
        viewport: { x: 0, y: 0, zoom },
        nodes,
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
    const before = (await saved.json()).diagram;
    await page.goto(`/react/scenarios/${scenario.id}/hydraulic-diagram`);
    const canvas = page.getByRole("group", {
      name: "Editor visual de diagrama hidraulico",
    });
    await expect(canvas).toBeVisible();
    if (zoom > 1) {
      await canvas.evaluate((element) => {
        element.scrollLeft = 100;
      });
      expect(await canvas.evaluate((element) => element.scrollLeft)).toBe(100);
    }
    await expect(page.getByRole("slider")).toHaveCount(0);

    async function selectConnection(testId: string) {
      const path = page.getByTestId(testId);
      await path.scrollIntoViewIfNeeded();
      const point = await path.evaluate((element) => {
        const path = element as SVGPathElement;
        // Pick a visible segment, avoiding nodes and gaps in dashed links.
        for (let fraction = 0.2; fraction < 0.9; fraction += 0.02) {
          const point = path.getPointAtLength(path.getTotalLength() * fraction);
          const screen = new DOMPoint(point.x, point.y).matrixTransform(
            path.getScreenCTM()!,
          );
          if (document.elementFromPoint(screen.x, screen.y) === path) {
            return { x: screen.x, y: screen.y };
          }
        }
        throw new Error("Connection has no visible segment to click");
      });
      await page.mouse.click(point.x, point.y);
      await expect(path).toHaveAttribute("data-focused", "true");
      await expect(page.getByRole("slider")).toHaveCount(2);
    }

    async function moveEndpoint(
      name: string,
      nodeKey: string,
      fraction: number,
    ) {
      const handle = page.getByRole("slider", { name });
      await handle.scrollIntoViewIfNeeded();
      const start = (await handle.boundingBox())!;
      const node = (await page
        .getByTestId(`hydraulic-canvas-node-${nodeKey}`)
        .boundingBox())!;
      await page.mouse.move(
        start.x + start.width / 2,
        start.y + start.height / 2,
      );
      await page.mouse.down();
      // Move off the border too: pointer capture keeps the drag active and
      // only the horizontal coordinate changes the attachment point.
      await page.mouse.move(node.x + node.width * fraction, start.y + 50, {
        steps: 6,
      });
      await page.mouse.up();
      await expect(handle).toHaveAttribute(
        "aria-valuenow",
        String(Math.round(Math.min(1, Math.max(0, fraction)) * 100)),
      );
      await expect(
        page.getByText("Estado: dirty", { exact: true }),
      ).toBeVisible();
    }

    await selectConnection("hydraulic-link-river");
    await moveEndpoint("Mover salida de conexion en Upstream", "upstream", 0.1);
    await moveEndpoint(
      "Mover entrada de conexion en Downstream",
      "downstream",
      0.9,
    );
    await expect(page.getByTestId("hydraulic-link-river")).toHaveAttribute(
      "d",
      /^M 135 156 .*735 440$/,
    );
    // Moving a node hides the handles; selecting its edge restores them.
    await page.getByTestId("hydraulic-canvas-node-upstream").click();
    await expect(page.getByRole("slider")).toHaveCount(0);
    await selectConnection("hydraulic-plant-link-upstream-plant");
    await moveEndpoint("Mover salida de conexion en Upstream", "upstream", 0.4);
    await moveEndpoint("Mover entrada de conexion en Plant", "plant", 0.6);
    await expect(
      page.getByTestId("hydraulic-plant-link-upstream-plant"),
    ).toHaveAttribute("d", /^M 180 156 .*450 260$/);
    await selectConnection("hydraulic-plant-link-plant-downstream");
    await moveEndpoint("Mover salida de conexion en Plant", "plant", -0.2);
    await moveEndpoint(
      "Mover entrada de conexion en Downstream",
      "downstream",
      1.2,
    );
    await page
      .getByRole("slider", { name: "Mover entrada de conexion en Downstream" })
      .press("ArrowLeft");
    await expect(
      page.getByTestId("hydraulic-plant-link-plant-downstream"),
    ).toHaveAttribute("d", /^M 360 336 .*748.5 440$/);
    await canvas.screenshot({
      path: testInfo.outputPath("connection-handles.png"),
    });
    await page
      .getByRole("button", { name: "Guardar diagrama", exact: true })
      .click();
    await expect(
      page.getByText("Estado: saved", { exact: true }),
    ).toBeVisible();
    const after = (await (await api.get(root)).json()).diagram;
    expect(after.reaches).toHaveLength(1);
    expect(after.reaches[0]).toMatchObject({
      from_node_key: "upstream",
      to_node_key: "downstream",
      from_anchor: 0.1,
      to_anchor: 0.9,
    });
    for (let index = 0; index < before.nodes.length; index++) {
      expect(after.nodes[index]).toMatchObject({
        x: before.nodes[index].x,
        y: before.nodes[index].y,
        units: before.nodes[index].units,
      });
    }
    expect(
      after.nodes.find(
        (node: { technical_key: string }) => node.technical_key === "plant",
      ).link_anchors,
    ).toEqual({
      "in:upstream": { from: 0.4, to: 0.6 },
      "out:downstream": { from: 0, to: 0.99 },
    });
    await page.reload();
    await selectConnection("hydraulic-link-river");
    await expect(
      page.getByRole("slider", {
        name: "Mover salida de conexion en Upstream",
      }),
    ).toHaveAttribute("aria-valuenow", "10");
    await expect(
      page.getByRole("slider", {
        name: "Mover entrada de conexion en Downstream",
      }),
    ).toHaveAttribute("aria-valuenow", "90");
  });
}
