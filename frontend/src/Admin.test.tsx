import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AdminUsersView, ProjectExternalAccessSection } from "./Admin";

describe("external project capabilities", () => {
  it("offers external as an identity role in administration", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === "/api/admin/users") return Response.json({ users: [] });
        if (path === "/api/admin/schedules") {
          return Response.json({ schedules: [], ticks: [] });
        }
        return Response.json(
          { detail: `unhandled GET ${path}` },
          { status: 500 },
        );
      }),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <AdminUsersView />
      </QueryClientProvider>,
    );

    expect(await screen.findByLabelText("Rol")).toContainElement(
      screen.getByRole("option", { name: "external" }),
    );
  });

  it("lets an administrator list, grant, change, and revoke both capabilities", async () => {
    const users = [
      {
        id: 9,
        email: "viewer@example.local",
        display_name: "Viewer",
        role: "external",
        is_active: true,
        created_at: "2026-08-23T12:00:00Z",
        updated_at: "2026-08-23T12:00:00Z",
      },
      {
        id: 10,
        email: "operator@example.local",
        display_name: "Operator",
        role: "external",
        is_active: true,
        created_at: "2026-08-23T12:00:00Z",
        updated_at: "2026-08-23T12:00:00Z",
      },
    ];
    let assignments = [
      {
        project_id: 1,
        user_id: 9,
        email: "viewer@example.local",
        display_name: "Viewer",
        role: "external",
        is_active: true,
        portal_view: true,
        operate: false,
        assigned_at: "2026-08-23T12:01:00Z",
        assigned_by: "admin@example.local",
        updated_at: "2026-08-23T12:01:00Z",
        updated_by: "admin@example.local",
      },
    ];
    const capabilityWrites: Array<{
      userId: number;
      portal_view: boolean;
      operate: boolean;
    }> = [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        const method = init?.method || "GET";
        if (path === "/api/admin/users") {
          return Response.json({ users });
        }
        if (path === "/api/auth/csrf") {
          return Response.json({ csrf_token: "csrf-token" });
        }
        if (
          path === "/api/admin/projects/1/external-access" &&
          method === "GET"
        ) {
          return Response.json({ external_access: assignments });
        }
        const accessMatch = path.match(
          /^\/api\/admin\/projects\/1\/external-access\/(\d+)$/,
        );
        if (accessMatch && method === "PUT") {
          const userId = Number(accessMatch[1]);
          const body = JSON.parse(String(init?.body)) as {
            portal_view: boolean;
            operate: boolean;
          };
          capabilityWrites.push({ userId, ...body });
          const selectedUser = users.find(
            (candidate) => candidate.id === userId,
          )!;
          const assignment = {
            ...selectedUser,
            project_id: 1,
            user_id: userId,
            ...body,
            assigned_at: "2026-08-23T12:01:00Z",
            assigned_by: "admin@example.local",
            updated_at: "2026-08-23T12:05:00Z",
            updated_by: "admin@example.local",
          };
          assignments = [
            ...assignments.filter((candidate) => candidate.user_id !== userId),
            assignment,
          ];
          return Response.json({ external_access: assignment });
        }
        if (accessMatch && method === "DELETE") {
          const userId = Number(accessMatch[1]);
          const revoked = {
            ...assignments.find((candidate) => candidate.user_id === userId)!,
            portal_view: false,
            operate: false,
            updated_at: "2026-08-23T12:06:00Z",
            updated_by: "admin@example.local",
          };
          assignments = [
            ...assignments.filter((candidate) => candidate.user_id !== userId),
            revoked,
          ];
          return Response.json({ external_access: revoked });
        }
        return Response.json(
          { detail: `unhandled ${method} ${path}` },
          { status: 500 },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ProjectExternalAccessSection projectId={1} projectName="Hybrid PMGD" />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "Capacidades externas" }),
    ).toBeVisible();
    expect(
      await screen.findByLabelText("Portal viewer@example.local"),
    ).toBeChecked();
    expect(
      screen.getByLabelText("Operar viewer@example.local"),
    ).not.toBeChecked();

    await user.click(screen.getByLabelText("Portal viewer@example.local"));
    await user.click(screen.getByLabelText("Operar viewer@example.local"));
    await user.click(
      screen.getByRole("button", {
        name: "Guardar capacidades de viewer@example.local",
      }),
    );
    await waitFor(() =>
      expect(capabilityWrites[0]).toEqual({
        userId: 9,
        portal_view: false,
        operate: true,
      }),
    );

    await user.selectOptions(screen.getByLabelText("Usuario externo"), "10");
    await user.click(screen.getByLabelText("Portal al otorgar"));
    await user.click(screen.getByLabelText("Operar al otorgar"));
    await user.click(
      screen.getByRole("button", { name: "Otorgar capacidades" }),
    );
    await waitFor(() =>
      expect(capabilityWrites[1]).toEqual({
        userId: 10,
        portal_view: true,
        operate: true,
      }),
    );

    await user.click(
      screen.getByRole("button", { name: "Revocar viewer@example.local" }),
    );
    await user.click(
      screen.getByRole("button", {
        name: "Confirmar revocar viewer@example.local",
      }),
    );
    await waitFor(() =>
      expect(
        screen.getByLabelText("Portal viewer@example.local"),
      ).not.toBeChecked(),
    );
    expect(
      screen.getByLabelText("Operar viewer@example.local"),
    ).not.toBeChecked();
  });
});
