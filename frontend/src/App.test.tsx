import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("application shell", () => {
  it("lets internal users create projects and scenarios, then refresh a direct scenario link", async () => {
    window.history.replaceState({}, "", "/react/projects");
    const projects: Array<{
      id: number;
      name: string;
      description: string;
      created_at: string;
    }> = [];
    const scenarios: Array<{
      id: number;
      project_id: number;
      name: string;
      description: string;
      created_at: string;
    }> = [];
    let transientProjectFailure = true;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/auth/me") {
          return new Response(
            JSON.stringify({
              user: {
                id: 7,
                email: "ada@example.local",
                display_name: "Ada Analyst",
                role: "analyst",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (path === "/api/auth/csrf") {
          return new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects" && method === "GET") {
          return new Response(JSON.stringify({ projects }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects" && method === "POST") {
          if (transientProjectFailure) {
            transientProjectFailure = false;
            return new Response(
              JSON.stringify({ detail: "temporary outage" }),
              {
                status: 503,
                headers: { "Content-Type": "application/json" },
              },
            );
          }
          const body = JSON.parse(String(init?.body));
          const project = {
            id: 1,
            name: body.name,
            description: body.description,
            created_at: "2026-06-23T12:00:00Z",
          };
          projects.push(project);
          return new Response(JSON.stringify(project), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1") {
          return new Response(JSON.stringify({ project: projects[0] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/scenarios" && method === "GET") {
          return new Response(JSON.stringify({ scenarios }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/projects/1/scenarios" && method === "POST") {
          const body = JSON.parse(String(init?.body));
          const scenario = {
            id: 10,
            project_id: 1,
            name: body.name,
            description: body.description,
            created_at: "2026-06-23T12:05:00Z",
          };
          scenarios.push(scenario);
          return new Response(JSON.stringify(scenario), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10") {
          return new Response(JSON.stringify({ scenario: scenarios[0] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/versions") {
          return new Response(JSON.stringify({ versions: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (path === "/api/scenarios/10/runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({ detail: `unhandled ${method} ${path}` }),
          {
            status: 500,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Proyectos" }),
    ).toBeVisible();
    expect(
      screen.getByText("Crea un proyecto para comenzar a modelar escenarios."),
    ).toBeVisible();

    await user.type(
      screen.getByLabelText("Nombre del proyecto"),
      "Hybrid PMGD",
    );
    await user.type(
      screen.getByLabelText("Descripcion del proyecto"),
      "Analyst workspace",
    );
    await user.click(screen.getByRole("button", { name: "Crear proyecto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "temporary outage",
    );
    expect(screen.getByLabelText("Nombre del proyecto")).toHaveValue(
      "Hybrid PMGD",
    );

    await user.click(screen.getByRole("button", { name: "Crear proyecto" }));
    expect(
      await screen.findByRole("link", { name: "Hybrid PMGD" }),
    ).toBeVisible();

    await user.click(screen.getByRole("link", { name: "Hybrid PMGD" }));
    expect(
      await screen.findByRole("heading", { name: "Hybrid PMGD" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Crea un escenario para guardar variantes del proyecto.",
      ),
    ).toBeVisible();

    await user.type(screen.getByLabelText("Nombre del escenario"), "Base case");
    await user.type(
      screen.getByLabelText("Descripcion del escenario"),
      "Initial modeling branch",
    );
    await user.click(screen.getByRole("button", { name: "Crear escenario" }));

    expect(
      await screen.findByRole("heading", { name: "Base case" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/scenarios/10");
    expect(screen.getByText("Aun no hay versiones inmutables.")).toBeVisible();
    expect(
      screen.getByText("Aun no hay corridas para este escenario."),
    ).toBeVisible();

    window.history.pushState({}, "", "/react/scenarios/10");
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Base case" })).toBeVisible();
    });
  });

  it("bootstraps the first admin through the JSON contract", async () => {
    window.history.replaceState({}, "", "/react");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ user: null, bootstrap_required: true }), {
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrf_token: "csrf-bootstrap" }), {
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user: {
              id: 1,
              email: "admin@example.local",
              display_name: "Admin User",
              role: "admin",
              is_active: true,
            },
            redirect_path: "/react/projects",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ projects: [] }), {
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Crear admin" }),
    ).toBeVisible();
    await user.type(screen.getByLabelText("Email"), "admin@example.local");
    await user.type(screen.getByLabelText("Nombre"), "Admin User");
    await user.type(screen.getByLabelText("Password"), "admin pass");
    await user.click(screen.getByRole("button", { name: "Crear admin" }));

    expect(
      await screen.findByRole("heading", { name: "Proyectos" }),
    ).toBeVisible();
    expect(screen.getByText("Admin User")).toBeVisible();
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/auth/bootstrap",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "admin@example.local",
          display_name: "Admin User",
          password: "admin pass",
        }),
      }),
    );
    const bootstrapHeaders = new Headers(fetchMock.mock.calls[2][1].headers);
    expect(bootstrapHeaders.get("X-CSRF-Token")).toBe("csrf-bootstrap");
  });

  it("logs in to the safe pre-login destination and logs out immediately", async () => {
    window.history.replaceState({}, "", "/react/system");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user: null, bootstrap_required: false }),
          { headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrf_token: "csrf-login" }), {
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user: {
              id: 7,
              email: "ada@example.local",
              display_name: "Ada Analyst",
              role: "analyst",
              is_active: true,
            },
            redirect_path: "/react/system",
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrf_token: "csrf-logout" }), {
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Iniciar sesion" }),
    ).toBeVisible();
    await user.type(screen.getByLabelText("Email"), "ada@example.local");
    await user.type(screen.getByLabelText("Password"), "smoke-test-password");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(
      await screen.findByRole("heading", { name: "Estado del sistema" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/system");

    await user.click(screen.getByRole("button", { name: "Salir" }));

    expect(
      await screen.findByRole("heading", { name: "Iniciar sesion" }),
    ).toBeVisible();
    expect(screen.queryByText("Ada Analyst")).not.toBeInTheDocument();
    const loginHeaders = new Headers(fetchMock.mock.calls[2][1].headers);
    expect(loginHeaders.get("X-CSRF-Token")).toBe("csrf-login");
    expect(JSON.parse(String(fetchMock.mock.calls[2][1].body))).toMatchObject({
      next: "/react/system",
    });
    const logoutHeaders = new Headers(fetchMock.mock.calls[4][1].headers);
    expect(logoutHeaders.get("X-CSRF-Token")).toBe("csrf-logout");
  });

  it("lands clients in the client area and blocks internal routes", async () => {
    window.history.replaceState({}, "", "/react/projects");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              user: {
                id: 8,
                email: "client@example.local",
                display_name: "Client User",
                role: "client",
                is_active: true,
              },
              bootstrap_required: false,
            }),
            { headers: { "Content-Type": "application/json" } },
          ),
      ),
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Forbidden" }),
    ).toBeVisible();
    expect(screen.getByText("Client User")).toBeVisible();
  });

  it("loads current identity and renders the authenticated user", async () => {
    window.history.replaceState({}, "", "/react");
    let resolveRequest: (response: Response) => void = () => undefined;
    const response = new Promise<Response>((resolve) => {
      resolveRequest = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => response),
    );

    render(<App />);

    expect(screen.getByRole("status")).toHaveTextContent("Cargando sesion");

    resolveRequest(
      new Response(
        JSON.stringify({
          user: {
            id: 7,
            email: "ada@example.local",
            display_name: "Ada Analyst",
            role: "analyst",
            is_active: true,
          },
          bootstrap_required: false,
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );

    expect(await screen.findByText("Ada Analyst")).toBeVisible();
    expect(screen.getByText("analyst")).toBeVisible();
  });

  it("renders login when no server session exists", async () => {
    window.history.replaceState({}, "", "/react");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ user: null, bootstrap_required: false }),
            { headers: { "Content-Type": "application/json" } },
          ),
      ),
    );

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Iniciar sesion" }),
    ).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a recoverable error state when identity loading fails", async () => {
    window.history.replaceState({}, "", "/react");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "service unavailable" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user: null, bootstrap_required: false }),
          { headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudo cargar la sesion",
    );
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(
      await screen.findByRole("heading", { name: "Iniciar sesion" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("navigates within the shell without a document reload", async () => {
    window.history.replaceState({}, "", "/react");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/projects") {
        return new Response(JSON.stringify({ projects: [] }), {
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(
        JSON.stringify({
          user: {
            id: 7,
            email: "ada@example.local",
            display_name: "Ada Analyst",
            role: "analyst",
            is_active: true,
          },
          bootstrap_required: false,
        }),
        { headers: { "Content-Type": "application/json" } },
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Ada Analyst");

    await user.click(screen.getByRole("link", { name: "Sistema" }));

    expect(
      screen.getByRole("heading", { name: "Estado del sistema" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/system");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
