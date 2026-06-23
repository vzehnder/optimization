import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("application shell", () => {
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
      await screen.findByRole("heading", { name: "Area analista" }),
    ).toBeVisible();
    expect(screen.getByText("Admin User")).toBeVisible();
    expect(fetchMock).toHaveBeenLastCalledWith(
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
    const fetchMock = vi.fn(
      async () =>
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
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Ada Analyst");

    await user.click(screen.getByRole("link", { name: "Sistema" }));

    expect(
      screen.getByRole("heading", { name: "Estado del sistema" }),
    ).toBeVisible();
    expect(window.location.pathname).toBe("/react/system");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
