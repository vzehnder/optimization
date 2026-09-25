import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { App } from "./App";

it("offers a battery reserve with explicit signs, units and contextual return", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/scenarios/4/components/battery/rules",
  );
  const json = (data: unknown) =>
    new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json" },
    });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/auth/me")
        return json({
          user: { id: 3, role: "analyst", is_active: true },
          bootstrap_required: false,
        });
      if (path.endsWith("/rule-context"))
        return json({ project_id: 1, object_id: 7 });
      if (path.endsWith("/rules"))
        return json({
          object: { id: 7, display_name: "Batería Norte", kind: "battery" },
          items: [],
          runtime: null,
        });
      if (path.endsWith("/object-candidates"))
        return json({
          items: [
            {
              id: 7,
              key: "battery",
              display_name: "Batería Norte",
              kind: "battery",
              variables: { carga: "mw", descarga: "mw", energia: "mwh" },
              known_values: { energia_inicial: { value: 2, unit: "mwh" } },
            },
          ],
        });
      if (path.endsWith("/input-candidates"))
        return json({
          items: [
            {
              alias: "entrada",
              object_id: 7,
              signal_id: 9,
              revision_id: 2,
              content_hash: "a".repeat(64),
              dimension_key: "energy",
              semantic_type_key: "battery_energy_reserve",
              binding_role_key: "rule_energy_reserve",
              unit_key: "mwh",
              series_kind: "catalog",
              display_name: "Reserva",
              set_name: "Reserva programada",
            },
          ],
        });
      return json({ items: [] });
    }),
  );
  render(<App />);
  expect(
    await screen.findByText("Batería: Batería Norte · Proyecto 1"),
  ).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Volver al componente" }),
  ).toHaveAttribute("href", "/react/scenarios/4/draft");
  expect(await screen.findByText("ctx.objeto.energia[t] · MWh")).toBeVisible();
  expect(
    screen.getByText(/Carga y descarga son potencias positivas/),
  ).toBeVisible();
  expect(screen.getByText(/energía al final del período/)).toBeVisible();
  expect(screen.getByLabelText("Código Python")).toHaveTextContent(
    "ctx.objeto.energia[t] >= ctx.parametros.reserva",
  );
  expect(screen.getByLabelText("Unidad reserva")).toHaveValue("mwh");
  expect(
    screen.queryByText("Ejemplo de máximo de caudal"),
  ).not.toBeInTheDocument();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Seleccionar entrada" }));
  await user.click(screen.getByRole("button", { name: "Continuar selección" }));
  await user.click(
    await screen.findByLabelText("Reserva · Reserva programada · MWh"),
  );
  expect(screen.getByLabelText("Alias de entrada")).toHaveValue("reserva");
  expect(
    screen.getByText(/ctx.transiciones\(ctx.objeto.descarga\)/),
  ).toBeInTheDocument();
  await user.selectOptions(
    screen.getByLabelText("Ventanas de presupuesto"),
    "horizon",
  );
  expect(screen.getByText("Ejemplo de presupuesto de energía")).toBeVisible();
});
