import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

const operatorIdentity = {
  id: 12,
  email: "olga@example.local",
  display_name: "Olga Operadora",
  role: "external",
  is_active: true,
};

const analystIdentity = {
  id: 7,
  email: "ada@example.local",
  display_name: "Ada Analyst",
  role: "analyst",
  is_active: true,
};

const consoleShell = {
  console: {
    id: 4,
    name: "Plan diario Planta Norte",
    description: "Ajuste diario",
    prepared_by: "Ada Analyst",
    updated_at: "2026-08-23T12:00:00Z",
  },
};

function stubApi(
  identity: typeof analystIdentity,
  landingPath: string | null,
  handler: (path: string) => Response | undefined = () => undefined,
) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path === "/api/auth/me") {
      return Response.json({
        user: identity,
        bootstrap_required: false,
        landing_path: landingPath,
      });
    }
    const handled = handler(path);
    if (handled) return handled;
    return Response.json({ detail: `unhandled GET ${path}` }, { status: 500 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("the three sibling application roots", () => {
  it("lands where the backend says, with no second calculation", async () => {
    window.history.replaceState({}, "", "/react");
    stubApi(operatorIdentity, "/react/console/4", (path) =>
      path === "/api/console/4" ? Response.json(consoleShell) : undefined,
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Plan diario Planta Norte" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/console/4");
  });

  it("gives the console root its own header instead of the analyst one", async () => {
    window.history.replaceState({}, "", "/react/console/4");
    stubApi(operatorIdentity, "/react/console/4", (path) =>
      path === "/api/console/4" ? Response.json(consoleShell) : undefined,
    );

    render(<App />);

    const header = await screen.findByRole("banner");
    expect(
      await within(header).findByText("Plan diario Planta Norte"),
    ).toBeVisible();
    expect(within(header).getByText("Olga Operadora")).toBeVisible();
    expect(within(header).getByRole("button", { name: "Salir" })).toBeVisible();
    expect(screen.queryByText("BESS Workspace")).toBeNull();
    expect(screen.queryByRole("link", { name: "Analista" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Portal cliente" })).toBeNull();
  });

  it("keeps an external identity out of the analyst root, id or not", async () => {
    window.history.replaceState({}, "", "/react/runs/99");
    const fetchMock = stubApi(operatorIdentity, "/react/console/4");

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "No encontrado" }),
    ).toBeVisible();
    expect(screen.queryByRole("link", { name: "Analista" })).toBeNull();
    expect(screen.getByRole("link", { name: "Volver" })).toHaveAttribute(
      "href",
      "/react/console/4",
    );
    expect(fetchMock.mock.calls.map((call) => String(call[0]))).not.toContain(
      "/api/runs/99",
    );
  });

  it("keeps an internal identity out of the portal root", async () => {
    window.history.replaceState({}, "", "/react/client");
    const fetchMock = stubApi(analystIdentity, "/react/projects");

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "No encontrado" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Volver" })).toHaveAttribute(
      "href",
      "/react/projects",
    );
    expect(fetchMock.mock.calls.map((call) => String(call[0]))).not.toContain(
      "/api/client/projects",
    );
  });

  it("keeps the console list on its own route with a single row", async () => {
    window.history.replaceState({}, "", "/react/console");
    stubApi(operatorIdentity, "/react/console/4", (path) =>
      path === "/api/console"
        ? Response.json({
            consoles: [
              {
                console: {
                  id: 4,
                  name: "Plan diario Planta Norte",
                  description: "Ajuste diario",
                },
                project: { name: "Planta Norte" },
                state: "active",
              },
            ],
          })
        : undefined,
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Mis consolas" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Plan diario Planta Norte" }),
    ).toHaveAttribute("href", "/react/console/4");
    expect(window.location.pathname).toBe("/react/console");
  });
});
