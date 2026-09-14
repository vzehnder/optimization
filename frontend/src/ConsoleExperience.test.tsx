import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { OperatorConsole, OperatorConsoleDocument } from "./api/client";

const document: OperatorConsoleDocument = {
  schema_version: "operator_console_config.v1",
  public_identity: { name: "Plan Norte", description: "Plan de dos horas" },
  parameters: [
    {
      id: "carga",
      pointer: { asset_id: "battery_1", field: "charge_max_mw" },
      label: "Carga máxima",
      unit: "MW",
      min: 0,
      max: 8,
      default: 4,
    },
  ],
  groups: [],
  results: {
    kpis: [
      {
        id: "beneficio",
        path: "objective_value_usd",
        label: "Beneficio",
        unit: "USD",
        decimals: 2,
        sign: "always",
        emphasis: "strong",
      },
    ],
    charts: [],
    tables: [],
  },
};

function setupConsole() {
  let saved: OperatorConsole = {
    id: 4,
    scenario_id: 10,
    case_id: 1,
    status: "draft",
    revision: 1,
    document: structuredClone(document),
    owned_variant: { id: 9, display_name: "Consola Norte" },
    prepared_by: "Ada",
    created_at: "2026-09-14T12:00:00Z",
    created_by: "Ada",
    updated_at: "2026-09-14T12:00:00Z",
    updated_by: "Ada",
    waiting_since: null,
    blocking: { reason: null, reasons: [] },
  };
  const api = {
    read: () => saved,
    replace: (next: OperatorConsole) => {
      saved = next;
    },
    override: (() => undefined) as (
      path: string,
      method: string,
      body: unknown,
    ) => Response | Promise<Response> | undefined,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input),
        method = init?.method || "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      const response = await api.override(path, method, body);
      if (response) return response;
      if (path === "/api/auth/me")
        return Response.json({
          user: {
            id: 7,
            email: "ada@example.local",
            display_name: "Ada",
            role: "analyst",
            is_active: true,
          },
          bootstrap_required: false,
        });
      if (path === "/api/auth/csrf")
        return Response.json({ csrf_token: "test-csrf" });
      if (path === "/api/time-series/signal-catalog")
        return Response.json({ signals: [] });
      if (path === "/api/portal-catalogs")
        return Response.json({
          charts: [
            {
              key: "grid_import_export",
              label: "Intercambio con la red",
              series: [
                { key: "grid_import_mw", label: "Compra", unit: "MW" },
                { key: "grid_export_mw", label: "Venta", unit: "MW" },
              ],
            },
          ],
          tables: [
            {
              key: "system_dispatch",
              label: "Despacho",
              columns: [
                { key: "timestamp", label: "Fecha", unit: null },
                { key: "grid_import_mw", label: "Compra", unit: "MW" },
              ],
            },
          ],
        });
      if (path === "/api/scenarios/10/consoles/4") {
        if (method === "PUT") {
          if (body.expected_revision !== saved.revision)
            return Response.json(
              { detail: "stale operator console revision" },
              { status: 409 },
            );
          saved = {
            ...saved,
            document: body.document,
            status: body.status,
            revision: saved.revision + 1,
          };
        }
        return Response.json({ operator_console: saved });
      }
      return Response.json(
        { detail: `Unhandled ${method} ${path}` },
        { status: 500 },
      );
    }),
  );
  window.history.replaceState({}, "", "/react/scenarios/10/consoles/4");
  return api;
}

describe("console configuration experience", () => {
  it("opens a collapsed results section to correct an incomplete field before saving", async () => {
    setupConsole();
    const user = userEvent.setup();
    render(<App />);
    const results = await screen.findByRole("button", { name: "Resultados" });
    await user.click(results);
    const label = within(
      screen.getByRole("group", { name: "Indicador 1" }),
    ).getByLabelText("Etiqueta");
    await user.clear(label);
    await user.click(results);
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );
    expect(results).toHaveAttribute("aria-expanded", "true");
    await waitFor(() => expect(label).toHaveFocus());
    await user.type(label, "Beneficio corregido");
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );
    expect(await screen.findByText("Revision 2")).toBeVisible();
  });
  it("keeps an incomplete numeric field in the form when advanced mode is requested", async () => {
    setupConsole();
    const user = userEvent.setup();
    render(<App />);
    const maximum = await screen.findByRole("spinbutton", {
      name: "Máximo de Carga máxima",
    });
    await user.clear(maximum);
    await user.click(
      screen.getByRole("button", { name: "Editar JSON avanzado" }),
    );
    expect(
      screen.queryByLabelText("Configuración completa (JSON)"),
    ).not.toBeInTheDocument();
    await waitFor(() => expect(maximum).toHaveFocus());
    await user.type(maximum, "6");
    await user.click(
      screen.getByRole("button", { name: "Editar JSON avanzado" }),
    );
    expect(
      JSON.parse(
        (
          screen.getByLabelText(
            "Configuración completa (JSON)",
          ) as HTMLTextAreaElement
        ).value,
      ).parameters[0].max,
    ).toBe(6);
  });
  it("retains the configuration through a failed background read and a retry", async () => {
    const api = setupConsole();
    const user = userEvent.setup();
    render(<App />);
    const name = await screen.findByLabelText("Nombre publico");
    await user.clear(name);
    await user.type(name, "Trabajo conservado");
    api.override = (path, method) =>
      path === "/api/scenarios/10/consoles/4" && method === "GET"
        ? Response.json(
            { detail: "Temporalmente no disponible" },
            { status: 503 },
          )
        : undefined;
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 31_000);
    await act(async () => {
      window.dispatchEvent(new Event("visibilitychange"));
    });
    await screen.findByRole("button", { name: "Reintentar configuración" });
    expect(screen.getByLabelText("Nombre publico")).toHaveValue(
      "Trabajo conservado",
    );
    api.override = () => undefined;
    await user.click(
      screen.getByRole("button", { name: "Reintentar configuración" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );
    await screen.findByText("Revision 2");
    expect(screen.getByLabelText("Nombre publico")).toHaveValue(
      "Trabajo conservado",
    );
  });
  it("requires an accepted save before activation and protects edits during that save", async () => {
    const api = setupConsole();
    const user = userEvent.setup();
    render(<App />);
    let finish: (() => void) | undefined;
    api.override = (path, method, body) =>
      path === "/api/scenarios/10/consoles/4" && method === "PUT"
        ? new Promise<Response>((resolve) => {
            finish = () => {
              const payload = body as {
                document: OperatorConsoleDocument;
                status: "draft" | "active";
              };
              api.replace({
                ...api.read(),
                ...payload,
                revision: api.read().revision + 1,
              });
              resolve(Response.json({ operator_console: api.read() }));
            };
          })
        : undefined;
    const name = await screen.findByLabelText("Nombre publico");
    await user.clear(name);
    await user.type(name, "Pendiente");
    expect(screen.getByRole("button", { name: "Activar" })).toBeDisabled();
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );
    expect(screen.getByLabelText("Nombre publico")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Activar" })).toBeDisabled();
    await waitFor(() => expect(finish).toBeDefined());
    await act(async () => {
      finish?.();
    });
    await screen.findByText("Revision 2");
    expect(screen.getByLabelText("Nombre publico")).toHaveValue("Pendiente");
    expect(screen.getByRole("button", { name: "Activar" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Activar" }));
    await act(async () => {
      finish?.();
    });
    expect(await screen.findByText("Activa", { exact: true })).toBeVisible();
    expect(screen.getByText("Revision 3")).toBeVisible();
  });
  it("keeps malformed expert text available and refuses saving or leaving expert mode", async () => {
    setupConsole();
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Editar JSON avanzado" }),
    );
    const malformed = JSON.stringify({ ...document, parameters: [null] });
    const input = screen.getByRole("textbox", {
      name: "Configuración completa (JSON)",
    });
    fireEvent.change(input, { target: { value: malformed } });
    await user.click(
      screen.getByRole("button", { name: "Volver al formulario" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Revisa la estructura",
    );
    expect(
      screen.getByRole("textbox", { name: "Configuración completa (JSON)" }),
    ).toHaveValue(malformed);
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );
    expect(screen.getByText("Revision 1")).toBeVisible();
    fireEvent.change(input, { target: { value: "{sin terminar" } });
    await user.click(
      screen.getByRole("button", { name: "Volver al formulario" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("no es JSON válido");
    expect(input).toHaveValue("{sin terminar");
    fireEvent.change(input, { target: { value: JSON.stringify(document) } });
    await user.click(
      screen.getByRole("button", { name: "Volver al formulario" }),
    );
    expect(screen.getByLabelText("Nombre publico")).toHaveValue("Plan Norte");
  });
  it("preserves local work and its starting revision after another session saves", async () => {
    const api = setupConsole();
    const user = userEvent.setup();
    render(<App />);
    const name = await screen.findByLabelText("Nombre publico");
    await user.clear(name);
    await user.type(name, "Mi plan pendiente");
    api.replace({
      ...api.read(),
      revision: 2,
      document: {
        ...document,
        public_identity: { ...document.public_identity, name: "Plan ajeno" },
      },
    });
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 31_000);
    await act(async () => {
      window.dispatchEvent(new Event("visibilitychange"));
    });
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La configuración cambió en otra sesión. Tus cambios siguen aquí y no se han guardado.",
    );
    expect(screen.getByLabelText("Nombre publico")).toHaveValue(
      "Mi plan pendiente",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Descartar mis cambios y cargar la configuración vigente",
      }),
    );
    expect(await screen.findByLabelText("Nombre publico")).toHaveValue(
      "Plan ajeno",
    );
    expect(screen.getByText("Revision 2")).toBeVisible();
  });
  it("configures KPI chart and table content from forms and the server catalog", async () => {
    setupConsole();
    const user = userEvent.setup();
    const view = render(<App />);
    await user.click(await screen.findByRole("button", { name: "Resultados" }));
    const kpi = screen.getByRole("group", { name: "Indicador 1" });
    await user.clear(within(kpi).getByLabelText("Etiqueta"));
    await user.type(within(kpi).getByLabelText("Etiqueta"), "Beneficio diario");
    await screen.findByRole("option", { name: "Intercambio con la red" });
    await user.click(screen.getByRole("button", { name: "Agregar gráfico" }));
    const chart = screen.getByRole("group", { name: "Gráfico 1" });
    await user.click(
      within(chart).getByRole("checkbox", { name: "Venta (MW)" }),
    );
    await user.click(screen.getByRole("button", { name: "Agregar tabla" }));
    const table = screen.getByRole("group", { name: "Tabla 1" });
    await user.click(within(table).getByRole("checkbox", { name: "Fecha" }));
    await user.clear(within(table).getByLabelText("Filas visibles"));
    await user.type(within(table).getByLabelText("Filas visibles"), "12");
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );
    await screen.findByText("Revision 2");
    view.unmount();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Resultados" }));
    const reopened = screen.getByRole("group", { name: "Indicador 1" });
    expect(within(reopened).getByLabelText("Etiqueta")).toHaveValue(
      "Beneficio diario",
    );
    expect(within(reopened).getByLabelText("Decimales")).toHaveValue(2);
    expect(within(reopened).getByLabelText("Signo")).toHaveValue("always");
    expect(within(reopened).getByLabelText("Énfasis")).toHaveValue("strong");
    expect(
      within(screen.getByRole("group", { name: "Gráfico 1" })).getByRole(
        "checkbox",
        { name: "Venta (MW)" },
      ),
    ).not.toBeChecked();
    expect(
      within(screen.getByRole("group", { name: "Gráfico 1" })).getByRole(
        "checkbox",
        { name: "Compra (MW)" },
      ),
    ).toBeChecked();
    expect(
      within(screen.getByRole("group", { name: "Tabla 1" })).getByLabelText(
        "Filas visibles",
      ),
    ).toHaveValue(12);
    expect(
      within(screen.getByRole("group", { name: "Tabla 1" })).getByRole(
        "checkbox",
        { name: "Fecha" },
      ),
    ).toBeChecked();
  });
  it("adds a direct numeric model field and persists its label unit bounds and default", async () => {
    const api = setupConsole();
    api.override = (path) =>
      path === "/api/scenarios/10/draft"
        ? Response.json({
            draft: {
              document: {
                assets: [
                  {
                    id: "battery_2",
                    type: "battery",
                    reserve_power_mw: 3,
                    enabled: true,
                    curve: [1, 2],
                  },
                ],
              },
            },
          })
        : undefined;
    const user = userEvent.setup();
    const view = render(<App />);
    const component = await screen.findByRole("combobox", {
      name: "Componente del parámetro",
    });
    await within(component).findByRole("option", { name: "battery_2" });
    await user.selectOptions(component, "battery_2");
    const field = screen.getByRole("combobox", { name: "Campo del modelo" });
    expect(
      within(field).queryByRole("option", { name: /enabled|curve/ }),
    ).not.toBeInTheDocument();
    await user.selectOptions(field, "reserve_power_mw");
    await user.click(screen.getByRole("button", { name: "Agregar parámetro" }));
    const parameter = screen.getByRole("group", { name: "Parámetro 2" });
    const label = within(parameter).getByLabelText("Etiqueta");
    await user.clear(label);
    await user.type(label, "Reserva");
    await user.type(within(parameter).getByLabelText("Unidad"), "MW");
    for (const [name, value] of [
      ["Mínimo", "1"],
      ["Máximo", "7"],
      ["Valor inicial", "3"],
    ]) {
      const control = within(parameter).getByRole("spinbutton", {
        name: `${name} de Reserva`,
      });
      await user.clear(control);
      await user.type(control, value);
    }
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );
    await screen.findByText("Revision 2");
    view.unmount();
    render(<App />);
    const reopened = await screen.findByRole("group", { name: "Parámetro 2" });
    expect(within(reopened).getByLabelText("Etiqueta")).toHaveValue("Reserva");
    expect(within(reopened).getByLabelText("Unidad")).toHaveValue("MW");
    expect(
      within(reopened).getByRole("spinbutton", { name: "Máximo de Reserva" }),
    ).toHaveValue(7);
    expect(
      within(reopened).getByRole("spinbutton", { name: "Mínimo de Reserva" }),
    ).toHaveValue(1);
    expect(
      within(reopened).getByRole("spinbutton", {
        name: "Valor inicial de Reserva",
      }),
    ).toHaveValue(3);
  });
  it("round trips expert settings while changing the public name in the form", async () => {
    setupConsole();
    const user = userEvent.setup();
    const view = render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Editar JSON avanzado" }),
    );
    const expert = {
      ...structuredClone(document),
      results: {
        ...document.results,
        charts: [
          {
            id: "red",
            chart_key: "grid_import_export",
            label: "Intercambio",
            series: [{ key: "grid_import_mw", label: "Compra" }],
          },
        ],
        tables: [
          {
            id: "tabla",
            table_key: "system_dispatch",
            label: "Detalle",
            row_limit: 48,
            columns: [
              { key: "timestamp", id: "fecha", label: "Fecha", unit: null },
            ],
          },
        ],
      },
    };
    fireEvent.change(
      screen.getByRole("textbox", { name: "Configuración completa (JSON)" }),
      { target: { value: JSON.stringify(expert) } },
    );
    await user.click(
      screen.getByRole("button", { name: "Volver al formulario" }),
    );
    const name = screen.getByLabelText("Nombre publico");
    await user.clear(name);
    await user.type(name, "Plan de invierno");
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );
    await screen.findByText("Revision 2");
    view.unmount();
    render(<App />);
    expect(await screen.findByLabelText("Nombre publico")).toHaveValue(
      "Plan de invierno",
    );
    await user.click(
      screen.getByRole("button", { name: "Editar JSON avanzado" }),
    );
    expect(
      JSON.parse(
        (
          screen.getByRole("textbox", {
            name: "Configuración completa (JSON)",
          }) as HTMLTextAreaElement
        ).value,
      ),
    ).toEqual({
      ...expert,
      public_identity: { ...expert.public_identity, name: "Plan de invierno" },
    });
  });
  it("persists a battery limit edited without JSON when the engineer reopens the console", async () => {
    setupConsole();
    const user = userEvent.setup();
    const view = render(<App />);
    const maximum = await screen.findByRole("spinbutton", {
      name: "Máximo de Carga máxima",
    });
    await user.clear(maximum);
    await user.type(maximum, "6");
    await user.click(
      screen.getByRole("button", { name: "Guardar configuracion" }),
    );
    await screen.findByText("Revision 2");
    view.unmount();
    render(<App />);
    expect(
      await screen.findByRole("spinbutton", { name: "Máximo de Carga máxima" }),
    ).toHaveValue(6);
    expect(screen.getByText("Borrador", { exact: true })).toBeVisible();
  });
});
