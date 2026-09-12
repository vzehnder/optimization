import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { ScenarioDraftDocument } from "./api/client";

function serveEditor(saveDelay?: Promise<void>) {
  let document: ScenarioDraftDocument = {
    schema_version: "bess_editor_draft.v1",
    case: { name: "Planta Norte" },
    pcc: { id: "bus_1", type: "bus" },
    grid: { id: "grid_1", import_power_max_mw: 0, export_power_max_mw: null },
    solver: { name: "HiGHS", options: { output_flag: false, time_limit: 30 } },
    time_series: { sources: [] },
    assets: [
      { id: "load_1", type: "load" },
      {
        id: "battery_norte",
        type: "battery",
        charge_power_max_mw: 4,
        discharge_power_max_mw: 4,
        energy_min_mwh: 0,
        energy_max_mwh: 8,
        initial_energy_mwh: 4,
        charge_efficiency: 0.95,
        discharge_efficiency: 0.95,
        degradation_cost_per_mwh_delta_soc: 0,
        terminal_condition: "equal_initial",
        terminal_energy_min_mwh: null,
        prevent_simultaneous_charge_discharge: false,
        degradation_linear_delta_soc: false,
      },
    ],
  };
  const draft = () => ({
    id: 1,
    scenario_id: 10,
    updated_at: "2026-09-12T12:00:00Z",
    document,
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
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
      if (path === "/api/auth/csrf")
        return Response.json({ csrf_token: "test-token" });
      if (path === "/api/projects/1")
        return Response.json({ project: { id: 1, name: "Planta Norte" } });
      if (path === "/api/scenarios/10")
        return Response.json({
          scenario: { id: 10, project_id: 1, name: "Invierno" },
        });
      if (path === "/api/scenarios/10/draft") {
        if (init?.method === "PUT") {
          document = JSON.parse(String(init.body)).document;
          await saveDelay;
          return Response.json(draft());
        }
        return Response.json({ draft: draft() });
      }
      return Response.json({ detail: `Unhandled ${path}` }, { status: 404 });
    }),
  );
}

describe("progressive model editing", () => {
  it("keeps newer edits in the form when a save requested before opening hydro arrives late", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    let acceptSave!: () => void;
    serveEditor(
      new Promise<void>((resolve) => {
        acceptSave = resolve;
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Agregar Hidro" }),
    );
    await user.click(
      screen.getByRole("button", {
        name: "Guardar y abrir diagrama hidráulico",
      }),
    );
    expect(await screen.findByText("Guardando", { exact: true })).toBeVisible();
    await user.clear(screen.getByRole("textbox", { name: "Nombre del caso" }));
    await user.type(
      screen.getByRole("textbox", { name: "Nombre del caso" }),
      "Cambio posterior",
    );
    await act(async () => acceptSave());
    expect(
      await screen.findByText("Cambios sin guardar", { exact: true }),
    ).toBeVisible();
    expect(
      screen.getByRole("textbox", { name: "Nombre del caso" }),
    ).toHaveValue("Cambio posterior");
    expect(window.location.pathname).toBe("/react/scenarios/10/draft");
    expect(
      screen.queryByRole("dialog", { name: "Cambios sin guardar" }),
    ).not.toBeInTheDocument();
  });

  it("opens the hydraulic diagram after accepting an explicitly edited solver document", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveEditor();
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByText("Opciones técnicas del modelo", { exact: true }),
    );
    await user.clear(
      screen.getByRole("textbox", { name: "Opciones del solver (JSON)" }),
    );
    await user.paste('{"output_flag":false,"time_limit":45}');
    await user.click(screen.getByRole("button", { name: "Agregar Hidro" }));
    await user.click(
      screen.getByRole("button", {
        name: "Guardar y abrir diagrama hidráulico",
      }),
    );
    await waitFor(() =>
      expect(window.location.pathname).toBe(
        "/react/scenarios/10/hydraulic-diagram",
      ),
    );
    expect(
      screen.queryByRole("dialog", { name: "Cambios sin guardar" }),
    ).not.toBeInTheDocument();
  });

  it("edits network limits while keeping technical solver options and empty limits after reopening", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveEditor();
    const user = userEvent.setup();
    const view = render(<App />);
    await user.click(
      await screen.findByText("Opciones técnicas del modelo", { exact: true }),
    );
    expect(
      JSON.parse(
        (
          screen.getByRole("textbox", {
            name: "Opciones del solver (JSON)",
          }) as HTMLTextAreaElement
        ).value,
      ),
    ).toEqual({ output_flag: false, time_limit: 30 });
    await user.click(
      screen.getByText("Opciones técnicas del modelo", { exact: true }),
    );
    await user.clear(
      screen.getByRole("spinbutton", { name: "Importación máxima (MW)" }),
    );
    await user.type(
      screen.getByRole("spinbutton", { name: "Importación máxima (MW)" }),
      "10",
    );
    await user.click(screen.getByRole("button", { name: "Guardar modelo" }));
    expect(await screen.findByText("Guardado", { exact: true })).toBeVisible();
    view.unmount();
    render(<App />);
    expect(
      await screen.findByRole("spinbutton", {
        name: "Importación máxima (MW)",
      }),
    ).toHaveValue(10);
    expect(
      screen.getByRole("spinbutton", { name: "Exportación máxima (MW)" }),
    ).toHaveValue(null);
    await user.click(
      screen.getByText("Opciones técnicas del modelo", { exact: true }),
    );
    expect(
      JSON.parse(
        (
          screen.getByRole("textbox", {
            name: "Opciones del solver (JSON)",
          }) as HTMLTextAreaElement
        ).value,
      ),
    ).toEqual({ output_flag: false, time_limit: 30 });
  });

  it("reveals and focuses a hidden hydro curve error without losing battery edits", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveEditor();
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", {
        name: "Editar Batería · battery_norte",
      }),
    );
    await user.clear(
      screen.getByRole("spinbutton", { name: "Capacidad máxima (MWh)" }),
    );
    await user.type(
      screen.getByRole("spinbutton", { name: "Capacidad máxima (MWh)" }),
      "15",
    );
    await user.click(screen.getByRole("button", { name: "Agregar Hidro" }));
    await user.click(screen.getByText("Curvas hidráulicas", { exact: true }));
    await user.clear(screen.getByLabelText("Curva del embalse (JSON)"));
    await user.type(
      screen.getByLabelText("Curva del embalse (JSON)"),
      "invalid",
    );
    await user.click(screen.getByText("Curvas hidráulicas", { exact: true }));
    await user.click(
      screen.getByRole("button", { name: "Editar Batería · battery_norte" }),
    );
    await user.click(screen.getByRole("button", { name: "Guardar modelo" }));
    expect(
      await screen.findByRole("textbox", { name: "Curva del embalse (JSON)" }),
    ).toHaveFocus();
    expect(
      screen.getByRole("textbox", { name: "Curva del embalse (JSON)" }),
    ).toHaveValue("invalid");
    expect(
      screen.getByRole("textbox", { name: "Curva del embalse (JSON)" }),
    ).toHaveAccessibleDescription(
      "JSON inválido. Revisa comas, comillas y corchetes.",
    );
    await user.click(
      screen.getByRole("button", { name: "Editar Batería · battery_norte" }),
    );
    expect(
      screen.getByRole("spinbutton", { name: "Capacidad máxima (MWh)" }),
    ).toHaveValue(15);
    await user.click(
      screen.getByRole("link", { name: "Corregir curva del embalse" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("textbox", { name: "Curva del embalse (JSON)" }),
      ).toHaveFocus(),
    );
  });

  it("keeps a terminal condition and basic capacity across closed panels and save", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveEditor();
    const user = userEvent.setup();
    const view = render(<App />);
    await user.click(
      await screen.findByRole("button", {
        name: "Editar Batería · battery_norte",
      }),
    );
    await user.click(
      screen.getByText("Operación avanzada de la batería", { exact: true }),
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Condición terminal" }),
      "min_terminal",
    );
    await user.type(
      screen.getByRole("spinbutton", { name: "Energía terminal mínima (MWh)" }),
      "6",
    );
    await user.click(
      screen.getByText("Operación avanzada de la batería", { exact: true }),
    );
    await user.clear(
      screen.getByRole("spinbutton", { name: "Capacidad máxima (MWh)" }),
    );
    await user.type(
      screen.getByRole("spinbutton", { name: "Capacidad máxima (MWh)" }),
      "14",
    );
    await user.click(
      screen.getByRole("button", { name: "Editar Demanda · load_1" }),
    );
    await user.click(screen.getByRole("button", { name: "Guardar modelo" }));
    expect(await screen.findByText("Guardado", { exact: true })).toBeVisible();
    view.unmount();
    render(<App />);
    await user.click(
      await screen.findByRole("button", {
        name: "Editar Batería · battery_norte",
      }),
    );
    expect(
      screen.getByRole("spinbutton", { name: "Capacidad máxima (MWh)" }),
    ).toHaveValue(14);
    await user.click(
      screen.getByText("Operación avanzada de la batería", { exact: true }),
    );
    expect(
      screen.getByRole("combobox", { name: "Condición terminal" }),
    ).toHaveValue("min_terminal");
    expect(
      screen.getByRole("spinbutton", { name: "Energía terminal mínima (MWh)" }),
    ).toHaveValue(6);
    expect(
      screen.getByRole("checkbox", {
        name: "Impedir carga y descarga simultáneas",
      }),
    ).not.toBeChecked();
  });

  it("selects a battery and preserves its accepted capacity when reopening the model", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10/draft");
    serveEditor();
    const user = userEvent.setup();
    const view = render(<App />);
    await user.click(
      await screen.findByRole("button", {
        name: "Editar Batería · battery_norte",
      }),
    );
    await user.clear(
      screen.getByRole("spinbutton", { name: "Capacidad máxima (MWh)" }),
    );
    await user.type(
      screen.getByRole("spinbutton", { name: "Capacidad máxima (MWh)" }),
      "12",
    );
    await user.click(screen.getByRole("button", { name: "Guardar modelo" }));
    expect(await screen.findByText("Guardado", { exact: true })).toBeVisible();
    view.unmount();
    render(<App />);
    await user.click(
      await screen.findByRole("button", {
        name: "Editar Batería · battery_norte",
      }),
    );
    expect(
      screen.getByRole("spinbutton", { name: "Capacidad máxima (MWh)" }),
    ).toHaveValue(12);
  });
});
