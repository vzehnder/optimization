import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AdminUsersView, ProjectExternalAccessSection } from "./Admin";
import type { AdminUser, ExternalProjectAccess } from "./api/client";

const externalUser: AdminUser = {
  id: 9,
  email: "persona@example.local",
  display_name: "Persona externa",
  role: "external",
  is_active: true,
  created_at: "2026-09-14T12:00:00Z",
  updated_at: "2026-09-14T12:00:00Z",
};
const reportAccess: ExternalProjectAccess = {
  ...externalUser,
  user_id: 9,
  project_id: 1,
  portal_view: true,
  operate: false,
  assigned_at: "2026-09-14T12:00:00Z",
  updated_at: "2026-09-14T12:00:00Z",
  assigned_by: "admin@example.local",
  updated_by: "admin@example.local",
};

function renderAdministration(access = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        {access ? (
          <ProjectExternalAccessSection
            projectId={1}
            projectName="Planta Norte"
          />
        ) : (
          <AdminUsersView />
        )}
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function accessApi(
  initial: ExternalProjectAccess[] = [],
  failNextSave = false,
) {
  let assignments = initial;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === "/api/auth/csrf")
        return Response.json({ csrf_token: "test-csrf" });
      if (path === "/api/admin/users")
        return Response.json({ users: [externalUser] });
      if (path === "/api/admin/projects/1/external-access")
        return Response.json({ external_access: assignments });
      if (
        path === "/api/admin/projects/1/external-access/9" &&
        init?.method === "PUT"
      ) {
        if (failNextSave) {
          failNextSave = false;
          return Response.json(
            { detail: "No se pudo guardar el acceso." },
            { status: 503 },
          );
        }
        const capabilities = JSON.parse(String(init.body));
        const assignment = {
          ...externalUser,
          project_id: 1,
          user_id: 9,
          ...capabilities,
          assigned_at: "2026-09-14T12:00:00Z",
          updated_at: "2026-09-14T13:00:00Z",
          assigned_by: "admin@example.local",
          updated_by: "admin@example.local",
        };
        assignments = [assignment];
        return Response.json({ external_access: assignment });
      }
      return Response.json({ detail: "Unexpected request" }, { status: 500 });
    }),
  );
}

describe("understandable administration", () => {
  it("keeps reviewed permissions after a failed save and accepts an explicit retry", async () => {
    accessApi([reportAccess], true);
    const user = userEvent.setup();
    renderAdministration(true);
    await user.click(
      await screen.findByLabelText(
        "Operar consolas para persona@example.local",
      ),
    );
    await user.click(
      screen.getByRole("button", {
        name: "Guardar capacidades de persona@example.local",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Confirmar cambios" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudo guardar el acceso.",
    );
    expect(
      screen.getByRole("region", {
        name: "Revisar cambios de persona@example.local",
      }),
    ).toHaveTextContent("Operar consolas: Sin acceso → Permitido");
    expect(
      screen.getByLabelText("Ver informes para persona@example.local"),
    ).toBeChecked();
    expect(
      screen.queryByText("Capacidades de persona@example.local actualizadas."),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirmar cambios" }));
    expect(
      await screen.findByText(
        "Capacidades de persona@example.local actualizadas.",
      ),
    ).toBeVisible();
    expect(
      screen.getByLabelText("Operar consolas para persona@example.local"),
    ).toBeChecked();
  });

  it("moves keyboard focus to the access review before confirmation", async () => {
    accessApi();
    const user = userEvent.setup();
    renderAdministration(true);
    await user.click(await screen.findByLabelText("Ver informes"));
    const reviewButton = screen.getByRole("button", { name: "Revisar acceso" });
    reviewButton.focus();
    await user.keyboard("{Enter}");
    expect(
      screen.getByRole("heading", { name: "Revisar acceso" }),
    ).toHaveFocus();
    await user.tab();
    expect(
      screen.getByRole("button", { name: "Otorgar capacidades" }),
    ).toHaveFocus();
    await user.click(
      screen.getByRole("button", { name: "Volver a editar acceso" }),
    );
    expect(screen.getByLabelText("Usuario externo")).toHaveFocus();
    expect(screen.getByLabelText("Ver informes")).toBeChecked();
  });

  it("focuses a rejected schedule date without losing the selected range or cadence", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path === "/api/admin/users") return Response.json({ users: [] });
        if (path === "/api/auth/csrf")
          return Response.json({ csrf_token: "test-csrf" });
        if (path === "/api/admin/schedules" && init?.method === "POST") {
          const payload = JSON.parse(String(init.body));
          if (payload.next_run_at === "2026-09-15T09:00:00")
            return Response.json(
              { detail: "next_run_at must include a timezone offset" },
              { status: 400 },
            );
          return Response.json(
            { schedule: { id: 1, ...payload, is_active: true } },
            { status: 201 },
          );
        }
        if (path === "/api/admin/schedules")
          return Response.json({ schedules: [], ticks: [] });
        return Response.json({ detail: "Unexpected request" }, { status: 500 });
      }),
    );
    const user = userEvent.setup();
    renderAdministration();
    await user.click(screen.getByRole("link", { name: "Programación" }));
    for (const [label, value] of [
      ["Nombre de la programación", "Plan diario"],
      ["Escenario (ID)", "10"],
      ["Variante (ID)", "30"],
      ["Inicio del período", "2026-09-15T00:00:00-03:00"],
      ["Fin del período", "2026-09-16T00:00:00-03:00"],
      ["Próxima ejecución", "2026-09-15T09:00:00"],
    ])
      await user.type(screen.getByLabelText(label), value);
    await user.selectOptions(screen.getByLabelText("Frecuencia"), "weekly");
    await user.click(
      screen.getByRole("button", { name: "Crear programación" }),
    );
    const date = screen.getByLabelText("Próxima ejecución");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Próxima ejecución debe incluir un offset horario, por ejemplo -03:00.",
    );
    expect(date).toHaveFocus();
    expect(date).toHaveAttribute("aria-invalid", "true");
    expect(date).toHaveAccessibleDescription(/debe incluir un offset horario/);
    expect(screen.getByLabelText("Inicio del período")).toHaveValue(
      "2026-09-15T00:00:00-03:00",
    );
    expect(screen.getByLabelText("Frecuencia")).toHaveValue("weekly");
    await user.type(date, "-03:00");
    await user.click(
      screen.getByRole("button", { name: "Crear programación" }),
    );
    expect(await screen.findByText("Plan diario creado.")).toBeVisible();
  });

  it("recovers a failed access query before offering project permissions", async () => {
    let unavailable = true;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === "/api/admin/users")
          return Response.json({ users: [externalUser] });
        if (path === "/api/admin/projects/1/external-access") {
          if (unavailable) {
            unavailable = false;
            return Response.json(
              { detail: "Accesos temporalmente no disponibles" },
              { status: 503 },
            );
          }
          return Response.json({ external_access: [reportAccess] });
        }
        return Response.json({ detail: "Unexpected request" }, { status: 500 });
      }),
    );
    const user = userEvent.setup();
    renderAdministration(true);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Accesos temporalmente no disponibles",
    );
    await user.click(
      screen.getByRole("button", { name: "Reintentar accesos" }),
    );
    expect(
      await screen.findByLabelText("Ver informes para persona@example.local"),
    ).toBeChecked();
    expect(
      screen.getByLabelText("Operar consolas para persona@example.local"),
    ).not.toBeChecked();
  });

  it("separates scheduling from users while retaining both unfinished forms", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input);
        if (path === "/api/admin/users") return Response.json({ users: [] });
        if (path === "/api/admin/schedules")
          return Response.json({ schedules: [], ticks: [] });
        return Response.json({ detail: "Unexpected request" }, { status: 500 });
      }),
    );
    const user = userEvent.setup();
    renderAdministration();
    await user.type(
      await screen.findByLabelText("Email"),
      "pendiente@example.local",
    );
    expect(
      screen.queryByRole("button", { name: "Ejecutar vencidos" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Programación" }));
    await user.type(
      screen.getByLabelText("Nombre de la programación"),
      "Plan diario pendiente",
    );
    expect(
      screen.getByRole("button", { name: "Ejecutar vencidos" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Crear usuario" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Usuarios y accesos" }));
    expect(screen.getByLabelText("Email")).toHaveValue(
      "pendiente@example.local",
    );
    await user.click(screen.getByRole("link", { name: "Programación" }));
    expect(screen.getByLabelText("Nombre de la programación")).toHaveValue(
      "Plan diario pendiente",
    );
  });

  it("identifies a duplicate email and preserves the form for a corrected retry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path === "/api/auth/csrf")
          return Response.json({ csrf_token: "test-csrf" });
        if (path === "/api/admin/users" && init?.method === "POST") {
          const payload = JSON.parse(String(init.body));
          return payload.email === "duplicado@example.local"
            ? Response.json({ detail: "email already exists" }, { status: 400 })
            : Response.json({ user: externalUser }, { status: 201 });
        }
        if (path === "/api/admin/users") return Response.json({ users: [] });
        if (path === "/api/admin/schedules")
          return Response.json({ schedules: [], ticks: [] });
        return Response.json({ detail: "Unexpected request" }, { status: 500 });
      }),
    );
    const user = userEvent.setup();
    renderAdministration();
    const email = await screen.findByLabelText("Email");
    await user.type(email, "duplicado@example.local");
    await user.type(
      screen.getByLabelText("Nombre", { exact: true }),
      "Persona externa",
    );
    await user.type(screen.getByLabelText("Contraseña"), "test-only-password");
    await user.selectOptions(screen.getByLabelText("Rol"), "external");
    await user.click(screen.getByRole("button", { name: "Crear usuario" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ya existe un usuario con este email.",
    );
    expect(email).toHaveAttribute("aria-invalid", "true");
    expect(email).toHaveAccessibleDescription(
      "Ya existe un usuario con este email.",
    );
    expect(email).toHaveFocus();
    expect(screen.getByLabelText("Nombre", { exact: true })).toHaveValue(
      "Persona externa",
    );
    expect(screen.getByLabelText("Contraseña")).toHaveValue(
      "test-only-password",
    );
    expect(screen.getByLabelText("Rol")).toHaveValue("external");
    await user.clear(email);
    await user.type(email, externalUser.email);
    await user.click(screen.getByRole("button", { name: "Crear usuario" }));
    expect(
      await screen.findByText("persona@example.local creado."),
    ).toBeVisible();
  });

  it("adds console access without removing the existing report permission", async () => {
    accessApi([reportAccess]);
    const user = userEvent.setup();
    const view = renderAdministration(true);
    await user.click(
      await screen.findByLabelText(
        "Operar consolas para persona@example.local",
      ),
    );
    await user.click(
      screen.getByRole("button", {
        name: "Guardar capacidades de persona@example.local",
      }),
    );
    const review = screen.getByRole("region", {
      name: "Revisar cambios de persona@example.local",
    });
    expect(within(review).getByRole("heading")).toHaveFocus();
    expect(review).toHaveTextContent("Planta Norte");
    expect(review).toHaveTextContent("Ver informes: Permitido → Permitido");
    expect(review).toHaveTextContent("Operar consolas: Sin acceso → Permitido");
    await user.click(
      within(review).getByRole("button", { name: "Confirmar cambios" }),
    );
    expect(
      await screen.findByText(
        "Capacidades de persona@example.local actualizadas.",
      ),
    ).toBeVisible();
    view.unmount();
    renderAdministration(true);
    expect(
      await screen.findByLabelText(
        "Operar consolas para persona@example.local",
      ),
    ).toBeChecked();
    expect(
      screen.getByLabelText("Ver informes para persona@example.local"),
    ).toBeChecked();
  });

  it("reviews the person and project before granting reports without console access", async () => {
    accessApi();
    const user = userEvent.setup();
    const view = renderAdministration(true);
    const reports = await screen.findByLabelText("Ver informes");
    const consoles = screen.getByLabelText("Operar consolas");
    expect(reports).not.toBeChecked();
    expect(consoles).not.toBeChecked();
    await user.click(reports);
    await user.click(screen.getByRole("button", { name: "Revisar acceso" }));
    const review = screen.getByRole("region", { name: "Revisar acceso" });
    expect(review).toHaveTextContent("persona@example.local");
    expect(review).toHaveTextContent("Planta Norte");
    expect(review).toHaveTextContent("Ver informes: Permitido");
    expect(review).toHaveTextContent("Operar consolas: Sin acceso");
    expect(
      screen.queryByText("persona@example.local", { selector: "strong" }),
    ).not.toBeInTheDocument();
    await user.click(
      within(review).getByRole("button", { name: "Otorgar capacidades" }),
    );
    expect(
      await screen.findByText(
        "Capacidades de persona@example.local otorgadas en Planta Norte.",
      ),
    ).toBeVisible();
    view.unmount();
    renderAdministration(true);
    expect(
      await screen.findByLabelText("Ver informes para persona@example.local"),
    ).toBeChecked();
    expect(
      screen.getByLabelText("Operar consolas para persona@example.local"),
    ).not.toBeChecked();
  });

  it("creates one external identity and shows its readable role after reopening", async () => {
    let users: AdminUser[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path === "/api/auth/csrf")
          return Response.json({ csrf_token: "test-csrf" });
        if (path === "/api/admin/users" && init?.method === "POST") {
          const payload = JSON.parse(String(init.body));
          if (payload.role !== "external")
            return Response.json(
              { detail: "Unsupported role" },
              { status: 422 },
            );
          users = [externalUser];
          return Response.json({ user: externalUser }, { status: 201 });
        }
        if (path === "/api/admin/users") return Response.json({ users });
        if (path === "/api/admin/schedules")
          return Response.json({ schedules: [], ticks: [] });
        return Response.json({ detail: "Unexpected request" }, { status: 500 });
      }),
    );
    const user = userEvent.setup();
    const view = renderAdministration();
    const role = await screen.findByLabelText("Rol");
    expect(
      within(role)
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["Analista", "Usuario externo", "Administrador"]);
    await user.type(screen.getByLabelText("Email"), externalUser.email);
    await user.type(
      screen.getByLabelText("Nombre", { exact: true }),
      externalUser.display_name,
    );
    await user.type(screen.getByLabelText("Contraseña"), "test-only-password");
    await user.selectOptions(role, "external");
    await user.click(screen.getByRole("button", { name: "Crear usuario" }));
    expect(
      await screen.findByText("persona@example.local creado."),
    ).toBeVisible();
    view.unmount();
    renderAdministration();
    expect(
      await screen.findByText("Persona externa | Usuario externo | Activo"),
    ).toBeVisible();
  });
});
