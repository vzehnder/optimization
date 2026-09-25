import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { App } from "./App";

it.each(["grid", "renewable"])(
  "offers %s rules with electrical signs, known data and contextual return",
  async (kind) => {
    window.history.replaceState(
      {},
      "",
      `/react/scenarios/4/components/${kind}/rules`,
    );
    const objects = [
      {
        id: 7,
        key: "grid",
        display_name: "Red Norte",
        kind: "grid",
        variables: { importacion: "mw", exportacion: "mw" },
      },
      {
        id: 8,
        key: "solar",
        display_name: "Solar Norte",
        kind: "renewable",
        variables: { generacion: "mw", recorte: "mw" },
        known_series: { disponibilidad: { values: [10, 8], unit: "mw" } },
      },
      {
        id: 9,
        key: "load",
        display_name: "Demanda Norte",
        kind: "load",
        variables: {},
        known_series: { demanda: { values: [2, 2], unit: "mw" } },
      },
    ];
    const object = objects.find((o) => o.kind === kind)!;
    const json = (value: unknown) =>
      new Response(JSON.stringify(value), {
        headers: { "Content-Type": "application/json" },
      });
    const writes: string[] = [];
    const fetch = vi.fn(
      async (input: RequestInfo | URL, options?: RequestInit) => {
        const path = new URL(String(input), "http://localhost").pathname;
        if (options?.method && options.method !== "GET") writes.push(path);
        if (path === "/api/auth/me")
          return json({
            user: { id: 3, role: "analyst", is_active: true },
            bootstrap_required: false,
          });
        if (path.endsWith("/rule-context"))
          return json({ project_id: 1, object_id: object.id });
        if (path.endsWith("/rules"))
          return json({ object, items: [], runtime: null });
        if (path.endsWith("/object-candidates"))
          return json({ items: objects });
        return json({ items: [] });
      },
    );
    vi.stubGlobal("fetch", fetch);
    render(<App />);
    expect(
      await screen.findByText(
        `${kind === "grid" ? "Red" : "Renovable"}: ${object.display_name} · Proyecto 1`,
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Volver al componente" }),
    ).toHaveAttribute("href", "/react/scenarios/4/draft");
    expect(screen.getByLabelText("Código Python")).toHaveTextContent(
      "ctx.parametros.fraccion",
    );
    expect(screen.getByLabelText("Unidad fraccion")).toHaveValue(
      "dimensionless",
    );
    expect(
      screen.queryByText("Ejemplo de máximo de caudal"),
    ).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.selectOptions(
      await screen.findByLabelText("Objeto a relacionar"),
      kind === "grid" ? "8" : "7",
    );
    await user.type(
      screen.getByLabelText("Alias del objeto"),
      kind === "grid" ? "solar" : "red",
    );
    await user.click(screen.getByRole("button", { name: "Agregar alias" }));
    expect(
      screen.getByText(/Generación y recorte son magnitudes no negativas/),
    ).toBeVisible();
    expect(
      screen.getByText(/Importación y exportación son magnitudes no negativas/),
    ).toBeVisible();
    expect(
      screen.getByText(/positivo significa exportación neta/),
    ).toBeVisible();
    expect(screen.getByText(/disponibilidad\[t\] · MW/)).toBeVisible();
    await user.selectOptions(screen.getByLabelText("Objeto a relacionar"), "9");
    await user.type(screen.getByLabelText("Alias del objeto"), "consumo");
    await user.click(screen.getByRole("button", { name: "Agregar alias" }));
    expect(
      screen.getByText(/ctx.objetos.consumo.demanda\[t\] · MW/),
    ).toBeVisible();
    expect(screen.getByText(/demanda fija es un dato conocido/)).toBeVisible();
    expect(writes).toEqual([]);
  },
);
