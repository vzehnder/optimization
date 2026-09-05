import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

const VERIFICATION_IDENTITY = {
  user: {
    id: 3,
    email: "verifier@example.local",
    display_name: "Cuenta de verificacion",
    role: "admin",
    is_active: true,
  },
  bootstrap_required: false,
  landing_path: "/react/projects",
  ts_next_canonical_read: true,
};

const REGULAR_IDENTITY = {
  ...VERIFICATION_IDENTITY,
  user: {
    ...VERIFICATION_IDENTITY.user,
    id: 4,
    email: "analyst@example.local",
    display_name: "Analyst",
    role: "analyst",
  },
  ts_next_canonical_read: false,
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function contextualPage() {
  return {
    items: [
      {
        source_kind: "catalog",
        signal_id: 41,
        set_id: 7,
        series_key: "energy_price",
        display_name: "Precio de energia",
        semantic_type_key: "energy_price",
        unit_key: "usd_per_mwh",
        data_class_key: "real",
        availability: "ready",
        current_revision: {
          revision_id: 90,
          revision_number: 2,
          content_hash: "current-hash",
          coverage_start: "2026-01-01T00:00:00",
          coverage_end: "2026-01-02T00:00:00",
          period_count: 24,
          value_count: 24,
        },
        temporal_contract: {
          regularity: "regular",
          nominal_resolution_seconds: 3600,
          timestamp_convention: "period_start",
          timezone: "UTC",
        },
        compatible_role_keys: ["grid_import_price"],
        need: {
          binding_role_key: "grid_import_price",
          source: "catalog_association",
        },
        association: {
          association_id: 12,
          binding_role_key: "grid_import_price",
          status: "active",
          state: "active_valid",
        },
        binding_state: "bound",
        binding_summary: {
          total_count: 1,
          truncated: false,
          items: [
            {
              binding_id: 73,
              scenario_id: 4,
              scenario_name: "Plan base",
              variant_id: 9,
              variant_name: "Default",
              binding_role_key: "grid_import_price",
              revision_id: 71,
              revision_number: 1,
              content_hash: "bound-hash-71",
              state: "stale",
              execution_blocked: true,
            },
          ],
        },
        capabilities: { preview: true, bind: true },
        links: { detail: "/api/time-series/catalog/inputs/41" },
        updated_at: "2026-02-01T10:00:00Z",
      },
      {
        source_kind: "object_specific",
        signal_id: 55,
        set_id: 11,
        series_key: "natural_inflow_forecast",
        display_name: "Afluente previsto",
        semantic_type_key: "natural_inflow",
        unit_key: "m3_per_s",
        data_class_key: "forecast",
        availability: "ready",
        current_revision: {
          revision_id: 101,
          revision_number: 1,
          content_hash: "local-hash-101",
          coverage_start: "2026-01-01T00:00:00",
          coverage_end: "2026-01-02T00:00:00",
          period_count: 24,
          value_count: 24,
        },
        temporal_contract: {
          regularity: "regular",
          nominal_resolution_seconds: 3600,
          timestamp_convention: "period_start",
          timezone: "America/Santiago",
        },
        compatible_role_keys: ["natural_inflow"],
        need: {
          binding_role_key: "natural_inflow",
          source: "object_specific_intention",
        },
        association: null,
        binding_state: "unbound",
        binding_summary: { total_count: 0, truncated: false, items: [] },
        capabilities: { preview: true, bind: true },
        links: {
          detail:
            "/api/projects/1/linkable-objects/7/time-series/object-series/55",
        },
        updated_at: "2026-02-01T09:00:00Z",
      },
    ],
    page: {
      limit: 50,
      has_more: false,
      next_cursor: null as string | null,
    },
    summary: { total_count: 2 },
    meta: {
      section: "object_context",
      project_id: 1,
      linkable_object_id: 7,
      object: {
        id: 7,
        display_name: "Sistema",
        object_kind: "global_signal_slot",
        object_type_key: "global:system",
      },
      catalog_generation: 12,
      request_id: "req_summary",
    },
  };
}

describe("contextual object time-series summary", () => {
  it("shows both source kinds, separate association and usage states, and blocked staleness", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/projects/1/linkable-objects/7/time-series",
    );
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        void init;
        const path = new URL(String(input), "http://localhost").pathname;
        if (path === "/api/auth/me") return json(VERIFICATION_IDENTITY);
        if (path === "/api/projects/1/linkable-objects/7/time-series")
          return json(contextualPage());
        return json({ detail: `unhandled ${path}` }, 500);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const table = await screen.findByRole("table", {
      name: "Series del objeto Sistema",
    });
    const generic = within(table).getByRole("row", {
      name: /Precio de energia/,
    });
    expect(within(generic).getByText("Fuente generica")).toBeVisible();
    expect(within(generic).getByText("grid_import_price")).toBeVisible();
    expect(within(generic).getByText("Asociada al objeto")).toBeVisible();
    expect(within(generic).getByText(/Usada en Default/)).toBeVisible();
    expect(within(generic).getByText(/revision 1/)).toBeVisible();
    expect(within(generic).getByText(/bound-hash-71/)).toBeVisible();
    expect(within(generic).getByText("Obsoleta")).toBeVisible();
    expect(within(generic).getByText("Ejecucion bloqueada")).toBeVisible();

    const local = within(table).getByRole("row", {
      name: /Afluente previsto/,
    });
    expect(within(local).getByText("Serie especifica")).toBeVisible();
    expect(within(local).getByText("Solo este objeto")).toBeVisible();
    expect(within(local).getByText("Sin asociacion de catalogo")).toBeVisible();
    expect(
      within(local).getByText("Aun no usada en una variante"),
    ).toBeVisible();

    // TS7-021: the summary never mutates; both named actions hand off to the
    // one protected journey.
    expect(
      screen.getByRole("link", { name: "Asociar fuente al objeto" }),
    ).toHaveAttribute(
      "href",
      "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate",
    );
    expect(
      screen.getByRole("link", { name: "Usar revision en una variante" }),
    ).toHaveAttribute(
      "href",
      "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=use_revision",
    );
    for (const [, init] of fetchMock.mock.calls) {
      expect((init?.method ?? "GET").toUpperCase()).toBe("GET");
    }
  });

  it("sends contextual filters to the server and renders only its answer", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/projects/1/linkable-objects/7/time-series",
    );
    const requested: string[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://localhost");
      if (url.pathname === "/api/auth/me") return json(VERIFICATION_IDENTITY);
      if (url.pathname === "/api/projects/1/linkable-objects/7/time-series") {
        requested.push(url.search);
        const page = contextualPage();
        if (url.searchParams.get("kind") === "object_specific") {
          page.items = [page.items[1]];
          page.summary.total_count = 1;
        }
        return json(page);
      }
      return json({ detail: `unhandled ${url.pathname}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("row", { name: /Precio de energia/ });
    await user.type(screen.getByLabelText("Buscar"), "afluente");
    await user.selectOptions(
      screen.getByLabelText("Origen"),
      "object_specific",
    );
    await user.click(screen.getByRole("button", { name: "Filtrar" }));

    await waitFor(() =>
      expect(
        screen.queryByRole("row", { name: /Precio de energia/ }),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("row", { name: /Afluente previsto/ }),
    ).toBeVisible();
    const applied = new URLSearchParams(requested.at(-1));
    expect(applied.get("q")).toBe("afluente");
    expect(applied.get("kind")).toBe("object_specific");
  });

  it("pages with the server cursor and returns through the cursor trail", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/projects/1/linkable-objects/7/time-series",
    );
    const requested: string[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://localhost");
      if (url.pathname === "/api/auth/me") return json(VERIFICATION_IDENTITY);
      if (url.pathname === "/api/projects/1/linkable-objects/7/time-series") {
        const cursor = url.searchParams.get("cursor") ?? "";
        requested.push(cursor);
        const page = contextualPage();
        const second = cursor === "cursor-page-2";
        page.items = [page.items[second ? 1 : 0]];
        page.page = {
          limit: 1,
          has_more: !second,
          next_cursor: second ? null : "cursor-page-2",
        };
        return json(page);
      }
      return json({ detail: `unhandled ${url.pathname}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("row", { name: /Precio de energia/ });
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    await screen.findByRole("row", { name: /Afluente previsto/ });
    expect(
      screen.queryByRole("row", { name: /Precio de energia/ }),
    ).not.toBeInTheDocument();
    expect(requested).toEqual(["", "cursor-page-2"]);
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Anterior" }));
    expect(
      await screen.findByRole("row", { name: /Precio de energia/ }),
    ).toBeVisible();
  });

  it("keeps the contextual route absent outside the verification accounts", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/projects/1/linkable-objects/7/time-series",
    );
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/auth/me") return json(REGULAR_IDENTITY);
      return json({ detail: `unexpected ${path}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "No encontrado" }),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/linkable-objects/7/time-series"),
      ),
    ).toBe(false);
  });
});
