import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

const project = {
  id: 1,
  name: "Planta Norte",
  description: "Proyecto de prueba",
};
const scenario = { id: 10, project_id: 1, name: "Invierno", description: "" };

function serveWorkspace(
  handler: (path: string) => Response | Promise<Response> | undefined = () =>
    undefined,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      const handled = handler(path);
      if (handled) return handled;
      if (path === "/api/auth/me")
        return Response.json({
          user: {
            id: 7,
            email: "analyst@example.local",
            role: "analyst",
            is_active: true,
          },
          bootstrap_required: false,
          landing_path: "/react/projects",
        });
      if (path === "/api/projects/1") return Response.json({ project });
      if (path === "/api/projects/1/scenarios")
        return Response.json({ scenarios: [scenario] });
      if (path === "/api/projects/1/dashboard-templates")
        return Response.json({ dashboard_templates: [] });
      if (path === "/api/scenarios/10") return Response.json({ scenario });
      if (path === "/api/scenarios/10/draft")
        return Response.json({ detail: "not found" }, { status: 404 });
      if (path === "/api/scenarios/10/versions")
        return Response.json({ versions: [] });
      if (path === "/api/scenarios/10/runs") return Response.json({ runs: [] });
      if (path === "/api/scenarios/10/consoles")
        return Response.json({ operator_consoles: [] });
      if (path === "/api/scenarios/10/case/variants")
        return Response.json({ variants: [], default_variant_id: null });
      if (path === "/api/projects/1/time-series-sets")
        return Response.json({ time_series_sets: [] });
      return Response.json({ detail: `Unhandled ${path}` }, { status: 500 });
    }),
  );
}

describe("workspace task navigation", () => {
  it("lets an analyst reach the model when execution history is unavailable", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=runs");
    serveWorkspace((path) =>
      path === "/api/scenarios/10/runs"
        ? Response.json(
            { detail: "Historial temporalmente no disponible" },
            { status: 503 },
          )
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "Invierno" }),
    ).toBeVisible();
    expect(
      await screen.findByText("Historial temporalmente no disponible"),
    ).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Modelo" }));
    expect(
      await screen.findByRole("button", { name: "Crear draft" }),
    ).toBeVisible();
  });

  it("keeps model preparation unknown during a failed query and its pending retry", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    let retry = false;
    let finish!: (response: Response) => void;
    const response = new Promise<Response>((resolve) => {
      finish = resolve;
    });
    serveWorkspace((path) =>
      path === "/api/scenarios/10/draft"
        ? retry
          ? response
          : Response.json({ detail: "offline" }, { status: 503 })
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    expect(
      await screen.findByText("No pudimos comprobar el modelo."),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Crear modelo" }),
    ).not.toBeInTheDocument();
    retry = true;
    await user.click(
      screen.getByRole("button", { name: "Reintentar consulta del modelo" }),
    );
    expect(await screen.findByText("Consultando modelo")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Continuar preparación" }),
    ).not.toBeInTheDocument();
    await act(async () => {
      finish(Response.json({ detail: "not found" }, { status: 404 }));
    });
    expect(
      await screen.findByRole("link", { name: "Crear modelo" }),
    ).toBeVisible();
  });

  it("focuses the destination heading when opening the editor and returning to the scenario", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    serveWorkspace();
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("link", { name: "Crear modelo" }));
    expect(
      await screen.findByRole("heading", { name: "Draft estructurado" }),
    ).toHaveFocus();
    await user.click(
      within(screen.getByRole("navigation", { name: "Ruta" })).getByRole(
        "link",
        { name: "Invierno" },
      ),
    );
    expect(
      await screen.findByRole("heading", { name: "Invierno" }),
    ).toHaveFocus();
    await user.click(screen.getByRole("link", { name: "Ejecuciones" }));
    expect(screen.getByRole("heading", { name: "Invierno" })).toHaveFocus();
  });

  it("separates project tasks without losing a pending scenario name and links to scenario consoles", async () => {
    window.history.replaceState({}, "", "/react/projects/1?origin=review");
    serveWorkspace();
    const user = userEvent.setup();
    render(<App />);
    await user.type(
      await screen.findByRole("textbox", { name: "Nombre del escenario" }),
      "Verano pendiente",
    );
    expect(
      screen.queryByRole("heading", { name: "Dashboard templates" }),
    ).not.toBeInTheDocument();

    const navigation = screen.getByRole("navigation", {
      name: "Secciones del proyecto",
    });
    await user.click(
      within(navigation).getByRole("link", { name: "Informes" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Dashboard templates" }),
    ).toBeVisible();
    expect(window.location.search).toBe("?origin=review&section=reports");
    await user.click(
      within(navigation).getByRole("link", { name: "Escenarios" }),
    );
    expect(
      screen.getByRole("textbox", { name: "Nombre del escenario" }),
    ).toHaveValue("Verano pendiente");
    expect(
      within(navigation).queryByRole("link", { name: "Accesos" }),
    ).not.toBeInTheDocument();
    await user.click(
      within(navigation).getByRole("link", { name: "Consolas" }),
    );
    await user.click(
      screen.getByRole("link", { name: "Consolas de Invierno" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Consolas de operador" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/scenarios/10");
  });

  it("keeps expert JSON edits while moving between task sections and exposes versions and hydraulics", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    serveWorkspace();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Invierno" });
    expect(
      screen.queryByRole("textbox", { name: "system_case JSON" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Avanzado" }));
    await user.type(
      screen.getByRole("textbox", { name: "system_case JSON" }),
      "mi trabajo pendiente",
    );
    expect(
      screen.getByRole("heading", { name: "Versiones inmutables" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Diagrama hidráulico" }),
    ).toHaveAttribute("href", "/react/scenarios/10/hydraulic-diagram");
    expect(
      screen.getByRole("heading", { name: "Consolas de operador" }),
    ).toBeVisible();

    await user.click(screen.getByRole("link", { name: "Datos" }));
    expect(
      screen.getByRole("heading", { name: "Datos y período" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Ver catálogo del proyecto" }),
    ).toHaveAttribute("href", "/react/projects/1/time-series-sets");
    await user.click(screen.getByRole("link", { name: "Avanzado" }));
    expect(
      screen.getByRole("textbox", { name: "system_case JSON" }),
    ).toHaveValue("mi trabajo pendiente");
  });

  it("returns from comparison to the same scenario's executions and preserves other query parameters", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?origin=review");
    serveWorkspace();
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: "Ejecuciones" }));
    expect(window.location.search).toBe("?origin=review&section=runs");
    expect(screen.getByRole("link", { name: "Ejecuciones" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await user.click(screen.getByRole("link", { name: "Comparar corridas" }));
    expect(
      await screen.findByRole("heading", { name: "Comparar corridas" }),
    ).toBeVisible();
    await user.click(
      within(screen.getByRole("navigation", { name: "Ruta" })).getByRole(
        "link",
        { name: "Invierno" },
      ),
    );

    expect(
      await screen.findByRole("heading", { name: "Corridas" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/scenarios/10");
    expect(window.location.search).toBe("?origin=review&section=runs");
    expect(
      within(screen.getByRole("navigation", { name: "Ruta" })).getByRole(
        "link",
        { name: "Planta Norte" },
      ),
    ).toBeVisible();
  });

  it("opens the same scenario's editor from Crear modelo when no model exists", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10");
    serveWorkspace();
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("link", { name: "Crear modelo" }));

    expect(
      await screen.findByRole("button", { name: "Crear draft" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/scenarios/10/draft");
    const route = screen.getByRole("navigation", { name: "Ruta" });
    expect(
      within(route).getByRole("link", { name: "Planta Norte" }),
    ).toBeVisible();
    expect(within(route).getByRole("link", { name: "Invierno" })).toBeVisible();
  });
});
