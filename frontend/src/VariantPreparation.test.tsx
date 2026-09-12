import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

const priceSet = {
  id: 5,
  project_id: 1,
  name: "Precio enero",
  version_label: "v1",
  revision_number: 1,
  content_hash: "price-v1",
  timezone: "America/Santiago",
  period_count: 2,
  horizon: {
    start: "2026-01-01T00:00:00-03:00",
    end: "2026-01-01T02:00:00-03:00",
  },
  signals: [{ signal_key: "price_usd_per_mwh", unit: "USD/MWh" }],
  periods: [
    {
      period_index: 0,
      timestamp_start: "2026-01-01T00:00:00-03:00",
      timestamp_end: "2026-01-01T01:00:00-03:00",
      duration_hours: 1,
    },
    {
      period_index: 1,
      timestamp_start: "2026-01-01T01:00:00-03:00",
      timestamp_end: "2026-01-01T02:00:00-03:00",
      duration_hours: 1,
    },
  ],
  values: [],
};

function servePreparation(
  handler: (
    path: string,
    init?: RequestInit,
  ) => Response | Promise<Response> | undefined = () => undefined,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const handled = handler(path, init);
      if (handled) return handled;
      if (path === "/api/auth/csrf")
        return Response.json({ csrf_token: "test" });
      if (path === "/api/auth/me")
        return Response.json({
          user: {
            id: 7,
            role: "analyst",
            email: "analyst@example.local",
            is_active: true,
          },
          landing_path: "/react/projects",
          ts_next_canonical_read: true,
        });
      if (path === "/api/projects/1")
        return Response.json({ project: { id: 1, name: "Planta Norte" } });
      if (path === "/api/scenarios/10")
        return Response.json({
          scenario: { id: 10, project_id: 1, name: "Invierno" },
        });
      if (path === "/api/scenarios/10/draft")
        return Response.json({ detail: "not found" }, { status: 404 });
      if (path === "/api/scenarios/10/versions")
        return Response.json({ versions: [] });
      if (path === "/api/scenarios/10/runs") return Response.json({ runs: [] });
      if (path === "/api/scenarios/10/consoles")
        return Response.json({ operator_consoles: [] });
      if (path === "/api/projects/1/time-series-sets")
        return Response.json({ time_series_sets: [priceSet] });
      if (path === "/api/projects/1/time-series-sets/5")
        return Response.json({ time_series_set: priceSet });
      if (path === "/api/scenarios/10/case/variants")
        return Response.json({
          default_variant_id: 3,
          variants: [
            {
              variant: {
                id: 3,
                case_id: 2,
                display_name: "Base",
                is_default: true,
              },
              bindings: [],
              required_signals: [
                {
                  entity_type: "grid",
                  entity_id: "grid_1",
                  signal_key: "price_usd_per_mwh",
                  bound: false,
                  time_series_set_id: null,
                },
              ],
              staleness: { validated: false, stale: false, reasons: [] },
              preparation: {
                binding_mode: "legacy",
                model_status: "available",
              },
            },
          ],
        });
      return Response.json({ detail: `Unhandled ${path}` }, { status: 500 });
    }),
  );
}

const boundVariant = {
  variant: { id: 3, display_name: "Base", is_default: true },
  bindings: [
    {
      id: 8,
      signal_key: "price_usd_per_mwh",
      entity_type: null,
      entity_id: null,
      time_series_set_id: 5,
    },
  ],
  required_signals: [
    {
      entity_type: "grid",
      entity_id: "grid_1",
      signal_key: "price_usd_per_mwh",
      bound: true,
      time_series_set_id: 5,
    },
  ],
  staleness: { stale: false, validated: true, reasons: [] },
  preparation: {
    binding_mode: "legacy",
    model_status: "available",
    bindings_revision: 0,
    sources: [],
    available_coverage: null,
  },
};

function serveBoundPreparation(
  handler: (
    path: string,
    init?: RequestInit,
  ) => Response | Promise<Response> | undefined = () => undefined,
) {
  servePreparation((path, init) => {
    const handled = handler(path, init);
    if (handled) return handled;
    if (path.endsWith("/case/variants"))
      return Response.json({ default_variant_id: 3, variants: [boundVariant] });
    if (path.endsWith("/validate"))
      return Response.json({ status: "valid", series_bindings: [] });
    return undefined;
  });
}

describe("variant preparation", () => {
  it("keeps a local source choice pending when another session changes the saved binding during review", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    let changed = false;
    serveBoundPreparation((path) => {
      if (path.endsWith("/validate")) {
        changed = true;
        return Response.json({ status: "valid", series_bindings: [] });
      }
      if (path.endsWith("/case/variants") && changed)
        return Response.json({
          default_variant_id: 3,
          variants: [
            {
              ...boundVariant,
              bindings: [
                { ...boundVariant.bindings[0], time_series_set_id: 6 },
              ],
            },
          ],
        });
      return undefined;
    });
    const user = userEvent.setup();
    render(<App />);
    const review = await screen.findByRole("button", {
      name: "Revisar preparación",
    });
    await waitFor(() => expect(review).toBeEnabled());
    await user.click(review);
    expect(
      await screen.findByText("Hay fuentes seleccionadas sin confirmar."),
    ).toBeVisible();
    expect(
      screen.getByLabelText("Serie de precio (price_usd_per_mwh)"),
    ).toHaveValue("5");
    expect(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    ).toBeDisabled();
  });
  it("explains unavailable canonical access instead of linking to a hidden journey", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    serveBoundPreparation((path) => {
      if (path === "/api/auth/me")
        return Response.json({
          user: {
            id: 7,
            role: "analyst",
            email: "analyst@example.local",
            is_active: true,
          },
          landing_path: "/react/projects",
          ts_next_canonical_read: false,
        });
      if (path.endsWith("/case/variants"))
        return Response.json({
          default_variant_id: 3,
          variants: [
            {
              ...boundVariant,
              preparation: {
                ...boundVariant.preparation,
                binding_mode: "protected",
                required_signals: [
                  {
                    ...boundVariant.required_signals[0],
                    bound: false,
                    linkable_object_id: 9,
                  },
                ],
                sources: [],
              },
            },
          ],
        });
      return undefined;
    });
    render(<App />);
    expect(
      await screen.findByText(
        "La edición de estas fuentes aún no está habilitada para tu cuenta.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", {
        name: "Corregir price_usd_per_mwh (grid_1)",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    ).toBeDisabled();
  });
  it("preserves the period when refreshing preparation fails and requires a new review after retry", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    let unavailable = false;
    serveBoundPreparation((path) => {
      if (path.endsWith("/validate")) {
        unavailable = true;
        return Response.json({ status: "valid", series_bindings: [] });
      }
      if (path.endsWith("/case/variants") && unavailable)
        return Response.json(
          { detail: "Preparación temporalmente no disponible" },
          { status: 503 },
        );
      return undefined;
    });
    const user = userEvent.setup();
    render(<App />);
    const review = await screen.findByRole("button", {
      name: "Revisar preparación",
    });
    await waitFor(() => expect(review).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Inicio del período"), {
      target: { value: "2026-01-01T01:00" },
    });
    await user.click(review);
    expect(
      await screen.findByText(
        "No pudimos actualizar la preparación. Conservamos tus cambios.",
      ),
    ).toBeVisible();
    expect(screen.getByLabelText("Inicio del período")).toHaveValue(
      "2026-01-01T01:00",
    );
    expect(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    ).toBeDisabled();
    unavailable = false;
    await user.click(
      screen.getByRole("button", {
        name: "Reintentar consulta de preparación",
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByText(
          "No pudimos actualizar la preparación. Conservamos tus cambios.",
        ),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    ).toBeDisabled();
  });
  it("takes a missing canonical need to the existing protected journey", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    serveBoundPreparation((path) =>
      path.endsWith("/case/variants")
        ? Response.json({
            default_variant_id: 3,
            variants: [
              {
                ...boundVariant,
                preparation: {
                  ...boundVariant.preparation,
                  binding_mode: "protected",
                  required_signals: [
                    {
                      ...boundVariant.required_signals[0],
                      bound: false,
                      linkable_object_id: 9,
                    },
                  ],
                  sources: [],
                },
              },
            ],
          })
        : undefined,
    );
    render(<App />);
    const correction = await screen.findByRole("link", {
      name: "Corregir price_usd_per_mwh (grid_1)",
    });
    expect(correction.getAttribute("href")).toContain(
      "object_id=9&intent=use_revision",
    );
    expect(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    ).toBeDisabled();
  });
  it("applies the server-checked coverage only on request and requires reviewing the changed period", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    serveBoundPreparation((path) =>
      path.endsWith("/case/variants")
        ? Response.json({
            default_variant_id: 3,
            variants: [
              {
                ...boundVariant,
                preparation: {
                  ...boundVariant.preparation,
                  available_coverage: {
                    start: "2026-01-01T00:00:00-03:00",
                    end: "2026-01-01T02:00:00-03:00",
                  },
                },
              },
            ],
          })
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    const review = await screen.findByRole("button", {
      name: "Revisar preparación",
    });
    await waitFor(() => expect(review).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Inicio del período"), {
      target: { value: "2026-01-01T01:00" },
    });
    await user.click(review);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Ejecutar variante" }),
      ).toBeEnabled(),
    );
    await user.click(
      screen.getByRole("button", { name: "Usar cobertura disponible" }),
    );
    expect(screen.getByLabelText("Inicio del período")).toHaveValue(
      "2026-01-01T00:00",
    );
    expect(screen.getByText("Duración: 2 horas")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    ).toBeDisabled();
  });
  it("locks the reviewed inputs and accepts one run while a double click submission is pending", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    let finish!: (response: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      finish = resolve;
    });
    const run = {
      id: 77,
      scenario_id: 10,
      project_id: 1,
      scenario_version_id: 55,
      status: "queued",
      artifacts: [],
    };
    serveBoundPreparation((path) =>
      path.endsWith("/run")
        ? pending
        : path === "/api/runs/77"
          ? Response.json({ run })
          : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    const review = await screen.findByRole("button", {
      name: "Revisar preparación",
    });
    await waitFor(() => expect(review).toBeEnabled());
    await user.click(review);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Ejecutar variante" }),
      ).toBeEnabled(),
    );
    await user.dblClick(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    );
    expect(screen.getByLabelText("Inicio del período")).toBeDisabled();
    expect(
      screen.getByLabelText("Serie de precio (price_usd_per_mwh)"),
    ).toBeDisabled();
    await act(async () => {
      finish(Response.json(run, { status: 201 }));
    });
    expect(
      await screen.findByRole("heading", { name: "Ejecución 77" }),
    ).toBeVisible();
  });
  it("explains an unavailable model and directs the analyst to correct it before reviewing", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    serveBoundPreparation((path) =>
      path.endsWith("/case/variants")
        ? Response.json({
            default_variant_id: 3,
            variants: [
              {
                ...boundVariant,
                preparation: {
                  ...boundVariant.preparation,
                  model_status: "unavailable",
                },
              },
            ],
          })
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    expect(
      await screen.findByText("Falta definir o corregir el modelo."),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Revisar preparación" }),
    ).toBeDisabled();
    await user.click(screen.getByRole("link", { name: "Corregir modelo" }));
    expect(
      await screen.findByRole("heading", { name: "Draft estructurado" }),
    ).toBeVisible();
  });
  it("reports partial source acceptance and keeps the pending choice without executing", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    let acceptedPrice = false;
    servePreparation((path, init) => {
      if (path.endsWith("/case/variants"))
        return Response.json({
          default_variant_id: 3,
          variants: [
            {
              ...boundVariant,
              bindings: acceptedPrice ? boundVariant.bindings : [],
              required_signals: [
                {
                  ...boundVariant.required_signals[0],
                  bound: acceptedPrice,
                  time_series_set_id: acceptedPrice ? 5 : null,
                },
                {
                  entity_type: "component:load",
                  entity_id: "load_1",
                  signal_key: "load_demand_mw",
                  bound: false,
                  time_series_set_id: null,
                },
              ],
            },
          ],
        });
      if (path.endsWith("/bindings")) {
        if (JSON.parse(String(init?.body)).signal_key === "price_usd_per_mwh") {
          acceptedPrice = true;
          return Response.json(
            { id: 8, time_series_set_id: 5 },
            { status: 201 },
          );
        }
        return Response.json(
          { detail: "Servicio temporalmente no disponible" },
          { status: 503 },
        );
      }
      return undefined;
    });
    const user = userEvent.setup();
    render(<App />);
    await user.selectOptions(
      await screen.findByLabelText("Serie de precio (price_usd_per_mwh)"),
      "5",
    );
    await user.selectOptions(
      screen.getByLabelText("Serie load_demand_mw (load_1)"),
      "5",
    );
    await user.click(screen.getByRole("button", { name: "Confirmar fuentes" }));
    expect(
      await screen.findByText(
        /Confirmación incompleta: 1 de 2 cambios aceptados/,
      ),
    ).toBeVisible();
    expect(
      await screen.findByText("price_usd_per_mwh (grid_1): vinculada (set #5)"),
    ).toBeVisible();
    expect(screen.getByLabelText("Serie load_demand_mw (load_1)")).toHaveValue(
      "5",
    );
    expect(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    ).toBeDisabled();
  });
  it("keeps an uncertain run submission blocked and offers the history without retrying it", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    serveBoundPreparation((path) =>
      path.endsWith("/run")
        ? Promise.reject(new TypeError("Failed to fetch"))
        : undefined,
    );
    const user = userEvent.setup();
    render(<App />);
    const review = await screen.findByRole("button", {
      name: "Revisar preparación",
    });
    await waitFor(() => expect(review).toBeEnabled());
    await user.click(review);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Ejecutar variante" }),
      ).toBeEnabled(),
    );
    await user.dblClick(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    );
    expect(
      await screen.findByText(/No pudimos confirmar el envío/),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    ).toBeDisabled();
    await user.click(
      screen.getByRole("link", { name: "Consultar historial de ejecuciones" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Corridas" }),
    ).toBeVisible();
  });
  it("keeps the explicit period and offset when choosing a source with a missing hour", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    const gapSource = {
      ...priceSet,
      id: 6,
      name: "Precio con hueco",
      horizon: {
        start: "2026-01-01T00:00:00-03:00",
        end: "2026-01-01T03:00:00-03:00",
      },
      periods: [
        priceSet.periods[0],
        {
          period_index: 2,
          timestamp_start: "2026-01-01T02:00:00-03:00",
          timestamp_end: "2026-01-01T03:00:00-03:00",
          duration_hours: 1,
        },
      ],
    };
    servePreparation((path) => {
      if (path === "/api/projects/1/time-series-sets")
        return Response.json({ time_series_sets: [priceSet, gapSource] });
      if (path === "/api/projects/1/time-series-sets/6")
        return Response.json({ time_series_set: gapSource });
      return undefined;
    });
    const user = userEvent.setup();
    render(<App />);
    await user.selectOptions(
      await screen.findByLabelText("Serie de precio (price_usd_per_mwh)"),
      "5",
    );
    const start = await screen.findByLabelText("Inicio del período");
    await waitFor(() => expect(start).toHaveValue("2026-01-01T00:00"));
    fireEvent.change(start, { target: { value: "2026-01-01T01:00" } });
    expect(screen.getByLabelText("Offset de inicio")).toHaveValue("-03:00");
    await user.selectOptions(
      screen.getByLabelText("Serie de precio (price_usd_per_mwh)"),
      "6",
    );
    expect(start).toHaveValue("2026-01-01T01:00");
    expect(screen.getByLabelText("Fin del período")).toHaveValue(
      "2026-01-01T02:00",
    );
    expect(await screen.findByText(/Cobertura incompleta/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    ).toBeDisabled();
    await user.clear(screen.getByLabelText("Offset de inicio"));
    await user.type(screen.getByLabelText("Offset de inicio"), "-04:00");
    expect(screen.getByLabelText("Offset de inicio")).toHaveValue("-04:00");
    expect(screen.getByLabelText("Inicio de rango")).toHaveValue(
      "2026-01-01T01:00:00-04:00",
    );
  });
  it("uses the protected source journey and reviews the exact canonical revision before running", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    servePreparation((path) => {
      if (path === "/api/projects/1/time-series-sets")
        return Response.json(
          { detail: "Catálogo de compatibilidad no disponible" },
          { status: 503 },
        );
      if (path.endsWith("/case/variants"))
        return Response.json({
          default_variant_id: 3,
          variants: [
            {
              variant: { id: 3, display_name: "Base", is_default: true },
              bindings: [],
              required_signals: [],
              staleness: { stale: false, validated: false, reasons: [] },
              preparation: {
                binding_mode: "protected",
                model_status: "available",
                bindings_revision: 4,
                required_signals: [
                  {
                    entity_type: "grid",
                    entity_id: "grid_1",
                    signal_key: "price_usd_per_mwh",
                    bound: true,
                    time_series_set_id: 5,
                    linkable_object_id: 9,
                  },
                ],
                sources: [
                  {
                    name: "Precio enero",
                    revision_number: 7,
                    state: "valid_pinned",
                    linkable_object_id: 9,
                    timezone: "America/Santiago",
                    content_hash: "exact-7",
                  },
                ],
                available_coverage: {
                  start: "2026-01-01T00:00:00-03:00",
                  end: "2026-01-01T02:00:00-03:00",
                },
              },
            },
          ],
        });
      if (path.endsWith("/validate"))
        return Response.json({
          status: "valid",
          series_bindings: [],
          bindings_revision: 4,
        });
      return undefined;
    });
    const user = userEvent.setup();
    render(<App />);
    const journey = await screen.findByRole("link", {
      name: "Revisar fuente Precio enero",
    });
    expect(journey.getAttribute("href")).toContain(
      "/time-series/journey?entry=object&project_id=1&object_id=9&intent=use_revision",
    );
    expect(
      screen.queryByLabelText("Serie de precio (price_usd_per_mwh)"),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Precio enero · revisión 7/)).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Revisar preparación" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Ejecutar variante" }),
      ).toBeEnabled(),
    );
  });
  it("confirms sources, reviews two hours and opens the accepted run without binding again or promoting manually", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    let saved = false;
    const run = {
      id: 77,
      scenario_id: 10,
      project_id: 1,
      scenario_version_id: 55,
      status: "queued",
      created_at: "2026-01-01T03:00:00Z",
      artifacts: [],
    };
    servePreparation((path, init) => {
      if (path.endsWith("/bindings")) {
        if (saved)
          return Response.json(
            { detail: "La fuente ya estaba confirmada" },
            { status: 409 },
          );
        saved = true;
        return Response.json({ id: 8, time_series_set_id: 5 }, { status: 201 });
      }
      if (path.endsWith("/validate"))
        return Response.json(
          saved
            ? { status: "valid", series_bindings: [] }
            : { detail: "Falta confirmar" },
          { status: saved ? 200 : 400 },
        );
      if (path.endsWith("/run")) {
        expect(JSON.parse(String(init?.body))).toEqual({
          range_start: "2026-01-01T00:00:00-03:00",
          range_end: "2026-01-01T02:00:00-03:00",
        });
        return Response.json(run, { status: 201 });
      }
      if (path === "/api/runs/77") return Response.json({ run });
      return undefined;
    });
    const user = userEvent.setup();
    render(<App />);
    await user.selectOptions(
      await screen.findByLabelText("Serie de precio (price_usd_per_mwh)"),
      "5",
    );
    await user.click(
      await screen.findByRole("button", { name: "Confirmar fuentes" }),
    );
    expect(
      await screen.findByText(
        "Fuentes confirmadas. Revisa la preparación antes de ejecutar.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    ).toBeDisabled();
    await user.click(
      screen.getByRole("button", { name: "Revisar preparación" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Ejecutar variante" }),
      ).toBeEnabled(),
    );
    expect(
      screen.getByText("Preparado para ejecutar este período"),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Ejecutar variante" }));
    expect(
      await screen.findByRole("heading", { name: "Ejecución 77" }),
    ).toBeVisible();
  });
  it("identifies a missing signal and takes the analyst to its source selector while execution stays blocked", async () => {
    window.history.replaceState({}, "", "/react/scenarios/10?section=data");
    servePreparation();
    const user = userEvent.setup();
    render(<App />);
    const correction = await screen.findByRole("link", {
      name: "Corregir price_usd_per_mwh (grid_1)",
    });
    await user.click(correction);
    expect(
      screen.getByLabelText("Serie de precio (price_usd_per_mwh)"),
    ).toHaveFocus();
    expect(
      screen.getByRole("button", { name: "Ejecutar variante" }),
    ).toBeDisabled();
  });
});
