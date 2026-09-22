import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

it("shows the full destination at every step and returns with the original variant and filters", async () => {
  const objectSearch = new URLSearchParams({
    scenario_id: "4",
    variant_id: "9",
    return_to: "/scenarios/4?section=data&variant=9",
    q: "load_1",
    kind: "all",
  });
  const returnTo = `/projects/1/linkable-objects/7/time-series?${objectSearch}`;
  window.history.replaceState(
    {},
    "",
    `/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate&scenario_id=4&variant_id=9&${new URLSearchParams({ return_to: returnTo })}`,
  );
  const writes: string[] = [];
  vi.stubGlobal(
    "fetch",
    journeyFetch((url) => {
      if (url.pathname === "/api/time-series/catalog/inputs")
        return json(candidatePage());
      if (url.pathname === "/api/time-series/catalog/inputs/41")
        return json(inputDetail());
      if (url.pathname === "/api/auth/csrf")
        return json({ csrf_token: "csrf" });
      if (url.pathname.endsWith("association-prevalidations"))
        return json(associationPrevalidation());
      if (url.pathname.endsWith("association-batches"))
        writes.push(url.pathname);
      return null;
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  const destination = await screen.findByRole("region", {
    name: "Destino de la vinculación",
  });
  await within(destination).findByText("Default · #9");
  function checkDestination() {
    expect(destination).toHaveTextContent("Cuenca Norte · #1");
    expect(destination).toHaveTextContent("Plan base · #4");
    expect(destination).toHaveTextContent("Caso base · #2");
    expect(destination).toHaveTextContent("Default · #9");
    expect(destination).toHaveTextContent("Sistema · #7");
    expect(
      within(destination).getByRole("link", {
        name: "Revisar objetos del escenario",
      }),
    ).toHaveAttribute("href", "/react/scenarios/4?section=data&variant=9");
  }
  checkDestination();
  expect(
    screen.queryByRole("button", { name: "Paso anterior" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Volver a la pantalla de origen" }),
  ).toHaveAttribute("href", `/react${returnTo}`);
  await user.selectOptions(
    screen.getByLabelText("Necesidad funcional"),
    "grid_import_price",
  );
  await user.click(
    screen.getByRole("radio", { name: "Reutilizar una fuente generica" }),
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await user.click(
    await screen.findByRole("radio", { name: "Elegir Precio de energia" }),
  );
  checkDestination();
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await screen.findByRole("heading", { name: "Datos o revision ejecutable" });
  checkDestination();
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await screen.findByRole("table", { name: "Prevalidacion por fila" });
  checkDestination();
  expect(
    screen.queryByRole("button", { name: "Siguiente" }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Paso anterior" }));
  expect(
    screen.getByRole("heading", { name: "Datos o revision ejecutable" }),
  ).toHaveFocus();
  await user.click(screen.getByRole("button", { name: "Paso anterior" }));
  expect(
    screen.getByRole("radio", { name: "Elegir Precio de energia" }),
  ).toBeChecked();
  await user.click(screen.getByRole("button", { name: "Paso anterior" }));
  expect(screen.getByLabelText("Necesidad funcional")).toHaveValue(
    "grid_import_price",
  );
  await user.click(
    screen.getByRole("link", { name: "Volver a la pantalla de origen" }),
  );
  await waitFor(() =>
    expect(window.location.pathname).toBe(
      "/react/projects/1/linkable-objects/7/time-series",
    ),
  );
  expect(window.location.search).toBe(`?${objectSearch}`);
  expect(writes).toEqual([]);
});

it("provides a local exit when the journey has no return URL", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate",
  );
  vi.stubGlobal("fetch", journeyFetch());
  render(<App />);
  expect(
    await screen.findByRole("link", { name: "Volver a la pantalla de origen" }),
  ).toHaveAttribute("href", "/react/projects/1/linkable-objects/7/time-series");
  const destination = screen.getByRole("region", {
    name: "Destino de la vinculación",
  });
  expect(
    within(destination).queryByRole("link", {
      name: "Revisar objetos del escenario",
    }),
  ).not.toBeInTheDocument();
  expect(within(destination).getAllByText("Sin seleccionar")).toHaveLength(3);
});

it("updates the destination when the execution variant changes", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=use_revision&scenario_id=4&variant_id=9",
  );
  vi.stubGlobal(
    "fetch",
    journeyFetch((url) => {
      if (url.pathname === "/api/scenarios/4/case/variants")
        return json({
          ...VARIANTS,
          variants: [
            ...VARIANTS.variants,
            {
              ...VARIANTS.variants[0],
              variant: {
                ...VARIANTS.variants[0].variant,
                id: 10,
                display_name: "Alternativa solar",
                is_default: false,
              },
            },
          ],
        });
      if (url.pathname.endsWith("/time-series-bindings"))
        return json(boundBindings());
      return null;
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  const destination = await screen.findByRole("region", {
    name: "Destino de la vinculación",
  });
  await within(destination).findByText("Default · #9");
  await user.selectOptions(screen.getByLabelText("Variante"), "10");
  expect(
    within(destination).getByText("Alternativa solar · #10"),
  ).toBeVisible();
  expect(
    within(destination).queryByText("Default · #9"),
  ).not.toBeInTheDocument();
  expect(
    within(destination).getByRole("link", {
      name: "Revisar objetos del escenario",
    }),
  ).toHaveAttribute("href", "/react/scenarios/4?section=data&variant=10");
  await user.selectOptions(screen.getByLabelText("Escenario"), "");
  expect(within(destination).getAllByText("Sin seleccionar")).toHaveLength(3);
});

it.each([
  "entry=object&project_id=0&object_id=7",
  "entry=object&project_id=1&object_id=9007199254740993",
  "entry=object&project_id=1&object_id=7&intent=update_shared&association_id=bad",
])(
  "UX-004 refuses an incomplete or invalid journey destination (%s)",
  async (query) => {
    window.history.replaceState({}, "", `/react/time-series/journey?${query}`);
    vi.stubGlobal("fetch", journeyFetch());
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "Recorrido no disponible" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Siguiente" }),
    ).not.toBeInTheDocument();
  },
);

it.each([
  "https://example.com",
  "//example.com",
  "/admin/users",
  "/scenarios/4?return_to=https://example.com",
])(
  "UX-004 never offers an arbitrary return destination (%s)",
  async (returnTo) => {
    window.history.replaceState(
      {},
      "",
      `/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate&${new URLSearchParams({ return_to: returnTo })}`,
    );
    vi.stubGlobal("fetch", journeyFetch());
    render(<App />);
    await screen.findByRole("heading", {
      level: 1,
      name: "Asociar fuente al objeto",
    });
    const link = screen.queryByRole("link", { name: "Volver al origen" });
    if (returnTo.startsWith("/scenarios"))
      expect(link).toHaveAttribute("href", "/react/scenarios/4");
    else expect(link).not.toBeInTheDocument();
  },
);

it("UX-004 retries a failed prevalidation with the same selected source", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate",
  );
  let available = false;
  vi.stubGlobal(
    "fetch",
    journeyFetch((url) => {
      if (url.pathname === "/api/time-series/catalog/inputs")
        return json(candidatePage());
      if (url.pathname === "/api/time-series/catalog/inputs/41")
        return json(inputDetail());
      if (url.pathname === "/api/auth/csrf")
        return json({ csrf_token: "csrf" });
      if (url.pathname.endsWith("association-prevalidations"))
        return available
          ? json(associationPrevalidation())
          : json(
              {
                error: {
                  code: "TS_REVIEW_UNAVAILABLE",
                  message: "Revisión temporalmente no disponible",
                },
              },
              503,
            );
      return null;
    }),
  );
  render(<App />);
  const user = userEvent.setup();
  await reachTheAssociationImpact(user);
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Revisión temporalmente no disponible",
  );
  available = true;
  await user.click(screen.getByRole("button", { name: "Revisar de nuevo" }));
  expect(
    await screen.findByRole("button", { name: "Asociar fuente al objeto" }),
  ).toBeEnabled();
  expect(
    screen.getByRole("region", { name: "Impacto y confirmacion" }),
  ).toHaveTextContent("Precio de energia");
});

it("filters needs by object and blocks a stale incompatible need from the URL", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate&binding_role_key=renewable_available_power",
  );
  const roleQueries: URL[] = [];
  const candidateQueries: URL[] = [];
  vi.stubGlobal(
    "fetch",
    journeyFetch((url) => {
      if (url.pathname === "/api/time-series/catalog/descriptors") {
        roleQueries.push(url);
        return json(BINDING_ROLES);
      }
      if (url.pathname === "/api/time-series/catalog/inputs") {
        candidateQueries.push(url);
        return json(candidatePage());
      }
      return null;
    }),
  );
  render(<App />);
  const user = userEvent.setup();
  await screen.findByRole("option", { name: "Precio de compra a la red" });
  expect(
    screen.queryByRole("option", { name: "Renewable Available Power" }),
  ).not.toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "La necesidad seleccionada no corresponde a Sistema",
  );
  await user.click(
    screen.getByRole("radio", { name: "Reutilizar una fuente generica" }),
  );
  expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  expect(candidateQueries).toHaveLength(0);
  expect(
    roleQueries.at(-1)!.searchParams.get("context_linkable_object_id"),
  ).toBe("7");
  expect(roleQueries.at(-1)!.searchParams.get("context_usage")).toBe(
    "association",
  );
  await user.selectOptions(
    screen.getByLabelText("Necesidad funcional"),
    "grid_import_price",
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await user.click(
    await screen.findByRole("radio", { name: "Elegir Precio de energia" }),
  );
  expect(screen.getByRole("button", { name: "Siguiente" })).toBeEnabled();
});

it("showing all sources preserves the search but resets the page and selected source", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate&binding_role_key=grid_import_price&q=Precio",
  );
  const queries: URL[] = [];
  vi.stubGlobal(
    "fetch",
    journeyFetch((url) => {
      if (url.pathname !== "/api/time-series/catalog/inputs") return null;
      queries.push(url);
      const page = candidatePage();
      const allowed = page.items.filter(
        (row) => row.compatibility_decision.allowed,
      );
      return json({
        ...page,
        items:
          url.searchParams.get("cursor") === "second"
            ? [allowed[1]]
            : url.searchParams.get("compatibility") === "all"
              ? page.items
              : allowed,
        page: {
          limit: 2,
          has_more: !url.searchParams.has("cursor"),
          next_cursor: "second",
        },
      });
    }),
  );
  render(<App />);
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("radio", {
      name: "Reutilizar una fuente generica",
    }),
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await screen.findByRole("radio", { name: "Elegir Precio de energia" });
  expect(
    screen.getByRole("checkbox", { name: "Mostrar todas las series" }),
  ).not.toBeChecked();
  await user.click(screen.getByRole("button", { name: "Más fuentes" }));
  await screen.findByText("Página 2");
  await user.click(
    await screen.findByRole("radio", { name: "Elegir Precio spot" }),
  );
  expect(screen.getByRole("button", { name: "Siguiente" })).toBeEnabled();
  await user.click(
    screen.getByRole("checkbox", { name: "Mostrar todas las series" }),
  );
  expect(
    await screen.findByRole("radio", { name: "Elegir Afluente medido" }),
  ).toBeDisabled();
  expect(screen.getByText("Página 1")).toBeVisible();
  expect(
    screen.getByRole("radio", { name: "Elegir Precio spot" }),
  ).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  expect(screen.getByLabelText("Buscar fuentes candidatas")).toHaveValue(
    "Precio",
  );
  expect(queries.at(-1)!.searchParams.get("q")).toBe("Precio");
  expect(queries.at(-1)!.searchParams.get("compatibility")).toBe("all");
  expect(queries.at(-1)!.searchParams.has("cursor")).toBe(false);
  expect(new URLSearchParams(window.location.search).get("show_all")).toBe("1");
  await user.click(
    screen.getByRole("checkbox", { name: "Mostrar todas las series" }),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("radio", { name: "Elegir Afluente medido" }),
    ).not.toBeInTheDocument(),
  );
  expect(
    screen.getByRole("checkbox", { name: "Mostrar todas las series" }),
  ).not.toBeChecked();
  expect(
    queries.some(
      (query) =>
        query.searchParams.get("compatibility") === "allowed" &&
        !query.searchParams.has("cursor"),
    ),
  ).toBe(true);
  expect(new URLSearchParams(window.location.search).has("show_all")).toBe(
    false,
  );
});

it("UX-004 changing the need discards its candidate and cursor", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate&binding_role_key=grid_import_price&cursor=old-page",
  );
  vi.stubGlobal(
    "fetch",
    journeyFetch((url) => {
      if (url.pathname === "/api/time-series/catalog/descriptors")
        return json(
          descriptorPage([
            { key: "grid_import_price", display_name: "Precio de compra" },
            { key: "grid_export_price", display_name: "Precio de venta" },
          ]),
        );
      if (url.pathname === "/api/time-series/catalog/inputs")
        return json(candidatePage());
      return null;
    }),
  );
  render(<App />);
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("radio", {
      name: "Reutilizar una fuente generica",
    }),
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await user.click(
    await screen.findByRole("radio", { name: "Elegir Precio de energia" }),
  );
  await user.click(screen.getByRole("button", { name: "Paso anterior" }));
  await user.selectOptions(
    screen.getByLabelText("Necesidad funcional"),
    "grid_export_price",
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(
    await screen.findByRole("radio", { name: "Elegir Precio de energia" }),
  ).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  expect(screen.getByText("Página 1")).toBeVisible();
  expect(new URLSearchParams(window.location.search).has("cursor")).toBe(false);
});

it("UX-004 explains a refused candidate query and retries without losing the need", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate&binding_role_key=grid_import_price",
  );
  let available = false;
  vi.stubGlobal(
    "fetch",
    journeyFetch((url) => {
      if (url.pathname === "/api/time-series/catalog/inputs")
        return available
          ? json(candidatePage())
          : json(
              {
                error: {
                  code: "TS_QUERY_FAILED",
                  message: "Fuentes temporalmente no disponibles",
                },
              },
              503,
            );
      return null;
    }),
  );
  render(<App />);
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("radio", {
      name: "Reutilizar una fuente generica",
    }),
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Fuentes temporalmente no disponibles",
  );
  expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  available = true;
  await user.click(screen.getByRole("button", { name: "Reintentar fuentes" }));
  expect(
    await screen.findByRole("radio", { name: "Elegir Precio de energia" }),
  ).toBeEnabled();
  expect(screen.getByRole("complementary")).toHaveTextContent(
    "Precio de compra a la red",
  );
});

it("UX-004 searches and pages candidates on the server before choosing a source", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate&binding_role_key=grid_import_price",
  );
  vi.stubGlobal(
    "fetch",
    journeyFetch((url) => {
      if (url.pathname === "/api/time-series/catalog/inputs") {
        if (url.searchParams.get("cursor") === "second")
          return json({
            ...candidatePage(),
            items: [
              candidateRow({
                identity: {
                  ...candidateRow().identity,
                  display_name: "Precio nocturno",
                },
              }),
            ],
          });
        return json({
          ...candidatePage(),
          items:
            url.searchParams.get("q") === "nocturno"
              ? []
              : candidatePage().items,
          page: { limit: 1, has_more: true, next_cursor: "second" },
        });
      }
      return null;
    }),
  );
  render(<App />);
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("radio", {
      name: "Reutilizar una fuente generica",
    }),
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await user.type(
    screen.getByLabelText("Buscar fuentes candidatas"),
    "nocturno",
  );
  await user.click(screen.getByRole("button", { name: "Buscar fuentes" }));
  expect(
    await screen.findByText(/No hay fuentes en esta página/),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Más fuentes" }));
  expect(
    await screen.findByRole("radio", { name: "Elegir Precio nocturno" }),
  ).toBeEnabled();
  await user.click(
    screen.getByRole("radio", { name: "Elegir Precio nocturno" }),
  );
  expect(screen.getByRole("button", { name: "Siguiente" })).toBeEnabled();
});

it("UX-004 opens compatible sources with the need and variant from the model", async () => {
  window.history.replaceState(
    {},
    "",
    "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=use_revision&binding_role_key=grid_import_price&scenario_id=4&variant_id=9",
  );
  vi.stubGlobal(
    "fetch",
    journeyFetch((url) => {
      if (url.pathname === "/api/projects/1/scenarios") return json(SCENARIOS);
      if (url.pathname === "/api/scenarios/4/case/variants")
        return json(VARIANTS);
      if (url.pathname.endsWith("/time-series-bindings"))
        return json(boundBindings());
      if (url.pathname === "/api/time-series/catalog/inputs") {
        return url.searchParams.get("context_binding_role_key") ===
          "grid_import_price" &&
          url.searchParams.get("context_linkable_object_id") === "7" &&
          url.searchParams.get("context_variant_id") === "9"
          ? json(candidatePage())
          : json({ detail: "Falta contexto" }, 422);
      }
      return null;
    }),
  );
  render(<App />);
  const user = userEvent.setup();
  await screen.findByRole("option", { name: "Precio de compra a la red" });
  expect(screen.getByLabelText("Necesidad funcional")).toHaveValue(
    "grid_import_price",
  );
  await waitFor(() =>
    expect(screen.getByLabelText("Variante")).toHaveValue("9"),
  );
  await user.click(
    screen.getByRole("radio", { name: "Reutilizar una fuente generica" }),
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(
    await screen.findByRole("radio", { name: "Elegir Precio de energia" }),
  ).toBeEnabled();
  expect(
    screen.getByRole("radio", { name: "Elegir Afluente medido" }),
  ).toBeDisabled();
  expect(
    screen.getByText("La dimension de la senal no corresponde al rol."),
  ).toBeVisible();
  expect(
    screen.getByRole("complementary", { name: "Contexto del recorrido" }),
  ).toHaveTextContent("Sistema");
});

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

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function objectSummaryPage() {
  return {
    items: [],
    page: { limit: 50, has_more: false, next_cursor: null },
    summary: { total_count: 0 },
    meta: {
      section: "object_context",
      project_id: 1,
      linkable_object_id: 7,
      object: {
        id: 7,
        display_name: "Sistema",
        object_kind: "global",
        object_type_key: "global_signal_slot",
      },
      catalog_generation: 4,
      request_id: "req_summary",
    },
  };
}

const BINDING_ROLES = {
  items: [
    {
      id: 1,
      key: "grid_import_price",
      display_name: "Precio de compra a la red",
      canonical_unit_key: "usd_per_mwh",
      status: "active",
    },
  ],
  page: { limit: 200, has_more: false, next_cursor: null },
  summary: { total_count: 1 },
  facets: null,
  meta: { section: "descriptors", catalog_generation: 4 },
};

function journeyFetch(
  extra?: (url: URL, init?: RequestInit) => Response | null,
) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const answered = extra?.(url, init);
    if (answered) return answered;
    if (url.pathname === "/api/auth/me") return json(VERIFICATION_IDENTITY);
    if (url.pathname === "/api/projects/1")
      return json({
        project: {
          id: 1,
          name: "Cuenca Norte",
          description: "",
          created_at: "2026-01-01",
        },
      });
    if (url.pathname === "/api/projects/1/scenarios") return json(SCENARIOS);
    if (url.pathname === "/api/scenarios/4/case/variants")
      return json(VARIANTS);
    if (url.pathname === "/api/projects/1/linkable-objects/7/time-series")
      return json(objectSummaryPage());
    if (url.pathname === "/api/time-series/catalog/descriptors")
      return json(BINDING_ROLES);
    return json({ detail: `unhandled ${url.pathname}` }, 500);
  });
}

function descriptorPage(
  items: { key: string; display_name: string; canonical_unit_key?: string }[],
) {
  return {
    items: items.map((item, index) => ({
      id: index + 1,
      status: "active",
      ...item,
    })),
    page: { limit: 200, has_more: false, next_cursor: null },
    summary: { total_count: items.length },
    facets: null,
    meta: { section: "descriptors", catalog_generation: 4 },
  };
}

const SEMANTIC_TYPES = descriptorPage([
  {
    key: "energy_price",
    display_name: "Energy price",
    canonical_unit_key: "usd_per_mwh",
  },
]);
const UNITS = descriptorPage([{ key: "usd_per_mwh", display_name: "USD/MWh" }]);
const DATA_CLASSES = descriptorPage([
  { key: "forecast", display_name: "Forecast" },
]);

const DEFAULT_ROLES = [
  ["grid_import_price", "usd_per_mwh"],
  ["grid_export_price", "usd_per_mwh"],
  ["load_demand", "mw"],
  ["renewable_available_power", "mw"],
  ["hydro_inflow", "m3_per_s"],
  ["natural_inflow", "m3_per_s"],
  ["minimum_flow", "m3_per_s"],
] as const;

function defaultsFetch(
  extra?: (url: URL, init?: RequestInit) => Response | null,
) {
  return journeyFetch((url, init) => {
    const answered = extra?.(url, init);
    if (answered) return answered;
    if (url.pathname === "/api/time-series/catalog/descriptors") {
      const kind = url.searchParams.get("kind");
      if (kind === "binding_role" || kind === "semantic_type")
        return json(
          descriptorPage(
            DEFAULT_ROLES.map(([key, unit]) => ({
              key,
              display_name: key,
              canonical_unit_key: unit,
            })),
          ),
        );
      if (kind === "unit")
        return json(
          descriptorPage(
            ["usd_per_mwh", "mw", "m3_per_s"].map((key) => ({
              key,
              display_name: key,
            })),
          ),
        );
      if (kind === "data_class")
        return json(
          descriptorPage([
            { key: "forecast", display_name: "Forecast" },
            { key: "real", display_name: "Real" },
          ]),
        );
    }
    return null;
  });
}

function openLocalJourney(role = "grid_export_price") {
  window.history.replaceState(
    {},
    "",
    `/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate&scenario_id=4&variant_id=9&binding_role_key=${role}`,
  );
}

async function enterLocalDefinition(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    await screen.findByRole("radio", {
      name: "Crear especifica para este objeto",
    }),
  );
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeEnabled(),
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await screen.findByLabelText("Clave local");
}

it.each(DEFAULT_ROLES)(
  "suggests an editable definition for %s and submits the displayed defaults",
  async (role, unit) => {
    openLocalJourney(role);
    let definition: Record<string, unknown> | undefined;
    vi.stubGlobal(
      "fetch",
      defaultsFetch((url, init) => {
        if (url.pathname === "/api/auth/csrf")
          return json({ csrf_token: "csrf" });
        if (url.pathname.endsWith("/object-series")) {
          definition = JSON.parse(String(init?.body));
          return new Response(
            JSON.stringify({ object_series: OBJECT_SERIES }),
            {
              status: 201,
              headers: {
                "Content-Type": "application/json",
                ETag: '"object-series-41-1"',
              },
            },
          );
        }
        return null;
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    await enterLocalDefinition(user);
    await waitFor(() =>
      expect(screen.getByLabelText("Unidad")).toHaveValue(unit),
    );
    expect(screen.getByLabelText("Clave local")).toHaveValue(`sistema_${role}`);
    expect(screen.getByLabelText("Nombre visible")).not.toHaveValue("");
    expect(screen.getByLabelText("Descripcion")).not.toHaveValue("");
    expect(screen.getByLabelText("Tipo semantico")).toHaveValue(role);
    expect(screen.getByLabelText("Clase de dato")).toHaveValue("forecast");
    expect(screen.getByLabelText("Zona horaria")).toHaveValue(
      Intl.DateTimeFormat().resolvedOptions().timeZone,
    );
    expect(screen.getByLabelText("Resolucion (segundos)")).toHaveValue(3600);
    const name = (screen.getByLabelText("Nombre visible") as HTMLInputElement)
      .value;
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(
      screen.getByRole("button", { name: "Guardar definicion" }),
    );
    await screen.findByText("awaiting_data");
    expect(definition).toMatchObject({
      object_series_key: `sistema_${role}`,
      display_name: name,
      intended_binding_role_key: role,
      semantic_type_key: role,
      unit_key: unit,
      data_class_key: "forecast",
      temporal_contract: { nominal_resolution_seconds: 3600 },
    });
  },
);

it("preserves edits when context arrives late and inherits untouched fields from the current variant", async () => {
  openLocalJourney();
  let resolveContext!: (response: Response) => void;
  const contextResponse = new Promise<Response>((resolve) => {
    resolveContext = resolve;
  });
  const fetchOther = defaultsFetch();
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://localhost");
      return url.pathname === "/api/projects/1/linkable-objects/7/time-series"
        ? contextResponse
        : fetchOther(input, init);
    }),
  );
  const user = userEvent.setup();
  render(<App />);
  await enterLocalDefinition(user);
  await user.clear(screen.getByLabelText("Nombre visible"));
  await user.type(screen.getByLabelText("Nombre visible"), "Mi precio");
  await user.clear(screen.getByLabelText("Descripcion"));
  await user.clear(screen.getByLabelText("Zona horaria"));
  await user.type(screen.getByLabelText("Zona horaria"), "Europe/Madrid");
  const reference = {
    source_kind: "object_specific",
    series_key: "sistema_grid_export_price",
    semantic_type_key: "grid_export_price",
    data_class_key: "real",
    availability: "ready",
    need: { binding_role_key: "grid_export_price" },
    temporal_contract: {
      nominal_resolution_seconds: 900,
      timezone: "America/Santiago",
    },
    binding_summary: {
      items: [
        {
          scenario_id: 4,
          variant_id: 9,
          binding_role_key: "grid_export_price",
          execution_blocked: false,
        },
      ],
    },
  };
  resolveContext(
    json({
      ...objectSummaryPage(),
      items: [
        {
          ...reference,
          series_key: "otra_serie",
          data_class_key: "forecast",
          temporal_contract: {
            nominal_resolution_seconds: 1800,
            timezone: "UTC",
          },
          binding_summary: { items: [] },
        },
        reference,
      ],
    }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("Resolucion (segundos)")).toHaveValue(900),
  );
  expect(screen.getByLabelText("Clave local")).toHaveValue(
    "sistema_grid_export_price_2",
  );
  expect(screen.getByLabelText("Clase de dato")).toHaveValue("real");
  expect(screen.getByLabelText("Nombre visible")).toHaveValue("Mi precio");
  expect(screen.getByLabelText("Descripcion")).toHaveValue("");
  expect(screen.getByLabelText("Zona horaria")).toHaveValue("Europe/Madrid");

  await user.clear(screen.getByLabelText("Clave local"));
  await user.type(screen.getByLabelText("Clave local"), "precio_manual");
  await user.selectOptions(screen.getByLabelText("Clase de dato"), "forecast");
  await user.clear(screen.getByLabelText("Resolucion (segundos)"));
  await user.type(screen.getByLabelText("Resolucion (segundos)"), "1800");
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await user.click(screen.getByRole("button", { name: "Paso anterior" }));
  expect(screen.getByLabelText("Clave local")).toHaveValue("precio_manual");
  expect(screen.getByLabelText("Clase de dato")).toHaveValue("forecast");
  expect(screen.getByLabelText("Resolucion (segundos)")).toHaveValue(1800);
  expect(screen.getByLabelText("Nombre visible")).toHaveValue("Mi precio");
});

it("updates untouched defaults when the need changes and keeps manual type and unit choices", async () => {
  openLocalJourney();
  vi.stubGlobal("fetch", defaultsFetch());
  const user = userEvent.setup();
  render(<App />);
  await enterLocalDefinition(user);
  await user.click(screen.getByRole("button", { name: "Paso anterior" }));
  await user.selectOptions(
    screen.getByLabelText("Necesidad funcional"),
    "natural_inflow",
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(screen.getByLabelText("Clave local")).toHaveValue(
    "sistema_natural_inflow",
  );
  expect(screen.getByLabelText("Tipo semantico")).toHaveValue("natural_inflow");
  expect(screen.getByLabelText("Unidad")).toHaveValue("m3_per_s");
  await user.selectOptions(
    screen.getByLabelText("Tipo semantico"),
    "load_demand",
  );
  expect(screen.getByLabelText("Unidad")).toHaveValue("mw");
  await user.selectOptions(screen.getByLabelText("Unidad"), "usd_per_mwh");
  await user.click(screen.getByRole("button", { name: "Paso anterior" }));
  await user.selectOptions(
    screen.getByLabelText("Necesidad funcional"),
    "grid_import_price",
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(screen.getByLabelText("Tipo semantico")).toHaveValue("load_demand");
  expect(screen.getByLabelText("Unidad")).toHaveValue("usd_per_mwh");
  await user.clear(screen.getByLabelText("Clave local"));
  await user.type(screen.getByLabelText("Clave local"), "Test--precio");
  expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
});

// The definition exists before any data does, which is the whole point of
// chapter 7.2: it is saved, and it is not selectable yet.
const OBJECT_SERIES = {
  signal_id: 41,
  object_series_key: "precio_local",
  display_name: "Precio local",
  source_kind: "object_specific",
  set_status: "draft",
  availability: "awaiting_data",
  binding_ready: false,
  resource_version: 1,
  current_revision: null,
  compatible_role_keys: ["grid_import_price"],
  owner: {
    project_id: 1,
    linkable_object_id: 7,
    object_kind: "global_signal_slot",
    object_type_key: "global:system",
  },
};

const OBJECT_INGESTION = {
  ingestion_id: "ing_local_01",
  channel: "api_points",
  state: "ready_to_publish",
  mode: "replace_full",
  normalized: {
    period_count: 1,
    value_count: 1,
    coverage_start: "2026-01-01T00:00:00Z",
    coverage_end: "2026-01-01T01:00:00Z",
    content_hash: "sha256:local-first-revision",
  },
  validation: {
    valid: true,
    error_count: 0,
    errors: [],
    errors_truncated: false,
  },
  impact: {},
  requires_confirmation: false,
  validation_token: "validation-local-01",
  capabilities: { remap: false },
  expires_at: "2026-01-01T02:00:00Z",
};

function candidateRow(overrides: Record<string, unknown> = {}) {
  return {
    entry_kind: "input",
    signal_id: 41,
    identity: {
      series_key: "energy_price",
      display_name: "Precio de energia",
      description: null,
      status: "active",
    },
    owner: { project_id: 1, project_name: "Cuenca Norte" },
    set: {
      id: 7,
      name: "Inputs 2026",
      version_number: 1,
      version_label: null,
      description: null,
      status: "active",
      visibility_scope: "global",
    },
    classification: {
      semantic_type_key: "energy_price",
      data_class_key: "real",
      unit_key: "usd_per_mwh",
    },
    current_revision: {
      id: 90,
      number: 2,
      sealed: true,
      created_at: "2026-02-01T10:00:00",
    },
    coverage_summary: {
      start: "2026-01-01T00:00:00",
      end: "2026-01-02T00:00:00",
      period_count: 24,
      nominal_resolution_seconds: 3600,
      minimum_resolution_seconds: 3600,
      maximum_resolution_seconds: 3600,
      regularity: "regular",
      source_timezone: "UTC",
    },
    origin_summary: { source_kind: "api" },
    link_summary: { association_count: 2, binding_count: 1 },
    resource_version: 3,
    compatibility_decision: {
      allowed: true,
      compatibility_rule_id: 5,
      rule_version: 1,
      contract_version: 1,
      errors: [],
      primary_error: null,
    },
    ...overrides,
  };
}

function candidatePage() {
  return {
    items: [
      candidateRow(),
      candidateRow({
        signal_id: 43,
        identity: {
          series_key: "spot_price",
          display_name: "Precio spot",
          description: null,
          status: "active",
        },
      }),
      candidateRow({
        signal_id: 42,
        identity: {
          series_key: "measured_inflow",
          display_name: "Afluente medido",
          description: null,
          status: "active",
        },
        classification: {
          semantic_type_key: "natural_inflow",
          data_class_key: "real",
          unit_key: "m3_per_s",
        },
        compatibility_decision: {
          allowed: false,
          compatibility_rule_id: null,
          rule_version: null,
          contract_version: 1,
          errors: [
            {
              code: "TS_COMPAT_DIMENSION_MISMATCH",
              message_key: "timeseries.compat.dimension_mismatch",
              message: "La dimension de la senal no corresponde al rol.",
              field: null,
              context: {},
            },
          ],
          primary_error: {
            code: "TS_COMPAT_DIMENSION_MISMATCH",
            message_key: "timeseries.compat.dimension_mismatch",
            message: "La dimension de la senal no corresponde al rol.",
            field: null,
            context: {},
          },
        },
      }),
    ],
    page: { limit: 50, has_more: false, next_cursor: null },
    summary: { total_count: 3 },
    facets: null,
    meta: { section: "inputs", catalog_generation: 4 },
  };
}

function inputDetail() {
  return {
    signal_id: 41,
    identity: {
      series_key: "energy_price",
      display_name: "Precio de energia",
      description: null,
      status: "active",
    },
    owner: { project_id: 1, project_name: "Cuenca Norte" },
    set: {
      id: 7,
      name: "Inputs 2026",
      version_number: 1,
      version_label: null,
      description: null,
      status: "active",
      visibility_scope: "global",
      scope_revision: 2,
    },
    contract: {
      semantic_type: {
        key: "energy_price",
        display_name: "Precio de energia",
        description: null,
        status: "active",
        dimension_key: "price",
        value_kind: "continuous",
        default_aggregation: "mean",
      },
      data_class: { key: "real", display_name: "Real", status: "active" },
      unit: {
        key: "usd_per_mwh",
        symbol: "USD/MWh",
        dimension_key: "price",
        status: "active",
      },
      signal_role: "input",
      aggregation: "mean",
    },
    current_revision: {
      id: 90,
      number: 2,
      state: "sealed",
      content_hash: "sha256:price-2",
      timezone: "UTC",
      timestamp_convention: "period_start",
      created_at: "2026-02-01T10:00:00",
      created_by: "analyst@example.local",
    },
    coverage_summary: {
      start: "2026-01-01T00:00:00",
      end: "2026-01-02T00:00:00",
      period_count: 24,
      nominal_resolution_seconds: 3600,
      minimum_resolution_seconds: 3600,
      maximum_resolution_seconds: 3600,
      regularity: "regular",
      source_timezone: "UTC",
    },
    origin_summary: { source_kind: "api" },
    link_summary: { association_count: 2, binding_count: 1 },
    provenance: {
      kind: "api",
      source_key: "mesa-precios",
      filename: null,
      media_type: null,
      checksum: null,
    },
    validation_summary: { status: "valid", error_count: 0 },
  };
}

function associationPrevalidation(overrides: Record<string, unknown> = {}) {
  return {
    normalized_request: {},
    request_hash: "hash-1",
    operations: [
      {
        client_operation_id: "op-1",
        action: "add",
        verdict: "accepted",
        compatibility_decision: {
          allowed: true,
          compatibility_rule_id: 5,
          rule_version: 1,
          contract_version: 1,
          errors: [],
          primary_error: null,
        },
        errors: [],
        observed_state: {},
        comparison: { before: null, after: {} },
      },
    ],
    can_commit: true,
    requires_confirmation: false,
    expires_at: "2026-02-01T10:05:00+00:00",
    prevalidation_token: "tok-1",
    commit_etag: '"etag-1"',
    request_id: "req_pre",
    ...overrides,
  };
}

async function reachTheAssociationImpact(
  user: ReturnType<typeof userEvent.setup>,
) {
  await screen.findByRole("option", { name: "Precio de compra a la red" });
  await user.selectOptions(
    screen.getByLabelText("Necesidad funcional"),
    "grid_import_price",
  );
  await user.click(
    screen.getByRole("radio", { name: "Reutilizar una fuente generica" }),
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await screen.findByRole("table", { name: "Fuentes genericas candidatas" });
  await user.click(
    screen.getByRole("radio", { name: "Elegir Precio de energia" }),
  );
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
}

const SCENARIOS = {
  scenarios: [
    {
      id: 4,
      project_id: 1,
      name: "Plan base",
      description: "",
      created_at: "2026-01-01T00:00:00",
    },
  ],
};

const VARIANTS = {
  case: {
    id: 2,
    scenario_id: 4,
    case_key: "base",
    display_name: "Caso base",
    updated_at: "2026-01-01T00:00:00",
  },
  default_variant_id: 9,
  variants: [
    {
      variant: {
        id: 9,
        case_id: 2,
        variant_key: "default",
        display_name: "Default",
        is_default: true,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
      bindings: [],
      required_signals: [],
      staleness: { validated: true, stale: false, reasons: [] },
    },
  ],
};

function boundBindings() {
  return {
    items: [
      {
        binding_id: 73,
        scenario_id: 4,
        case_input_variant_id: 9,
        signal_id: 41,
        signal: {
          id: 41,
          series_key: "energy_price",
          display_name: "Precio de energia",
        },
        time_series_set_id: 7,
        set_revision_id: 71,
        bound_content_hash: "sha256:price-1",
        revision: {
          mode: "current",
          id: 71,
          content_hash: "sha256:price-1",
          observed_current_revision_id: 71,
          current_revision_id: 90,
        },
        object: {
          id: 7,
          project_id: 1,
          object_kind: "global",
          object_type_key: "global_signal_slot",
          object_key: "global",
          display_name: "Sistema",
          status: "active",
        },
        binding_role: {
          id: 1,
          key: "grid_import_price",
          display_name: "Precio de compra a la red",
        },
        catalog_association_id: 12,
        source_kind: "catalog",
        status: "active",
        state: "stale",
        lifecycle_revision: 1,
      },
    ],
    page: { limit: 1, has_more: false, next_cursor: null },
    summary: { total_count: 1 },
    meta: { scenario_id: 4, variant_id: 9, bindings_revision: 3 },
  };
}

function bindingPrevalidation() {
  return {
    normalized_request: {},
    request_hash: "hash-b",
    observed_bindings_revision: 3,
    operations: [
      {
        client_operation_id: "bind-41-grid_import_price",
        action: "replace",
        verdict: "confirmation_required",
        compatibility_decision: {
          allowed: true,
          compatibility_rule_id: 5,
          rule_version: 1,
          contract_version: 1,
          errors: [],
          primary_error: null,
        },
        errors: [],
        observed_state: {},
        comparison: {
          before: { binding_id: 73, state: "stale", set_revision_id: 71 },
          after: { set_revision_id: 90 },
        },
      },
    ],
    can_commit: true,
    requires_confirmation: true,
    expires_at: "2026-02-01T10:05:00+00:00",
    prevalidation_token: "tok-bind",
    commit_etag: '"etag-bind"',
    request_id: "req_pre_bind",
  };
}

const LOCAL_ALTERNATIVE = {
  kind: "derive_object_specific",
  label_key: "create_specific_for_this_object",
  available: true,
  requires_admin: false,
  unavailable_code: null,
  href: "/api/projects/1/linkable-objects/7/time-series/catalog-associations/12/object-series-derivation-prevalidations",
};

const SHARED_ALTERNATIVE = {
  kind: "publish_shared",
  label_key: "publish_for_everyone",
  available: true,
  requires_admin: true,
  unavailable_code: null,
  href: "/api/projects/1/linkable-objects/7/time-series/catalog-associations/12/shared-series/revision-ingestions/points",
};

function associationView(intent: string) {
  return {
    association: {
      association_id: 12,
      signal_id: 41,
      set_id: 7,
      series_key: "energy_price",
      display_name: "Precio de energia",
      binding_role_key: "grid_import_price",
      status: "active",
      linkable_object_id: 7,
      project_id: 1,
    },
    impact: {
      source: {
        set_id: 7,
        set_name: "Inputs 2026",
        visibility_scope: "global",
        owner_project_id: 1,
        owner_project_name: "Cuenca Norte",
        current_revision_id: 90,
        current_revision_number: 2,
        current_content_hash: "sha256:price-2",
        signal_count: 1,
      },
      associations: { total: 2, other_objects: 1 },
      bindings: {
        total_active: 1,
        current: 1,
        pinned: 0,
        projects_affected: 1,
        variants_affected: 1,
      },
      effect: {
        bindings_will_become_stale: 1,
        associations_will_require_revalidation: 0,
      },
      listed_consumers: [
        { linkable_object_id: 7, project_id: 1, relation: "current" },
        { linkable_object_id: 8, project_id: 2, relation: "pinned" },
      ],
      consumers_truncated: false,
    },
    impact_fingerprint: "tsi_abc",
    recommendation:
      intent === "local" ? "derive_object_specific" : "publish_shared",
    requires_confirmation: true,
    derivation_required: false,
    derivation_required_codes: [],
    alternatives:
      intent === "local"
        ? [LOCAL_ALTERNATIVE, SHARED_ALTERNATIVE]
        : [SHARED_ALTERNATIVE, LOCAL_ALTERNATIVE],
    set_signals: [
      {
        signal_id: 41,
        series_key: "energy_price",
        display_name: "Precio de energia",
        semantic_type_key: "energy_price",
        unit_key: "usd_per_mwh",
      },
    ],
    links: {
      detail:
        "/api/projects/1/linkable-objects/7/time-series/catalog-associations/12",
      catalog_detail: "/api/time-series/catalog/associations/12",
      shared_point_ingestions: SHARED_ALTERNATIVE.href,
      derivation_prevalidations: LOCAL_ALTERNATIVE.href,
      derivations:
        "/api/projects/1/linkable-objects/7/time-series/catalog-associations/12/object-series-derivations",
    },
    capabilities: {
      publish_shared: true,
      derive_object_specific: true,
      preview_source: true,
    },
    request_id: "req_assoc",
  };
}

function sharedIngestion() {
  return {
    ingestion_id: "ing-1",
    channel: "api_points",
    state: "ready_to_publish",
    mode: "replace_full",
    normalized: {
      point_count: 2,
      coverage_start: "2026-01-01T00:00:00+00:00",
      coverage_end: "2026-01-01T02:00:00+00:00",
      content_hash: "sha256:price-3",
    },
    validation: {
      valid: true,
      error_count: 0,
      errors: [],
      errors_truncated: false,
    },
    impact: {},
    requires_confirmation: true,
    validation_token: "tok-shared",
    capabilities: { publish: true, remap: false, cancel: true, preview: true },
    expires_at: "2026-02-01T11:00:00+00:00",
    impact_fingerprint: "tsi_abc",
    derivation_required: false,
    derivation_required_codes: [],
    alternatives: [SHARED_ALTERNATIVE, LOCAL_ALTERNATIVE],
    etag: '"shared-etag"',
  };
}

function objectCandidates() {
  return {
    items: [
      {
        object: {
          id: 7,
          project_id: 1,
          object_kind: "global",
          object_type_key: "global_signal_slot",
          object_key: "global",
          display_name: "Sistema",
          status: "active",
        },
        compatibility_decision: {
          allowed: true,
          compatibility_rule_id: 5,
          rule_version: 1,
          contract_version: 1,
          errors: [],
          primary_error: null,
        },
        selectable: true,
      },
      {
        object: {
          id: 8,
          project_id: 1,
          object_kind: "component",
          object_type_key: "battery",
          object_key: "bess-1",
          display_name: "Bateria 1",
          status: "active",
        },
        compatibility_decision: {
          allowed: true,
          compatibility_rule_id: 5,
          rule_version: 1,
          contract_version: 1,
          errors: [],
          primary_error: null,
        },
        selectable: true,
      },
      {
        object: {
          id: 9,
          project_id: 1,
          object_kind: "component",
          object_type_key: "load",
          object_key: "load-1",
          display_name: "Consumo 1",
          status: "active",
        },
        compatibility_decision: {
          allowed: false,
          compatibility_rule_id: null,
          rule_version: null,
          contract_version: 1,
          errors: [
            {
              code: "TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED",
              message_key: "timeseries.compat.object_type_not_allowed",
              message: "Ese tipo de objeto no admite esta necesidad.",
              field: null,
              context: {},
            },
          ],
          primary_error: {
            code: "TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED",
            message_key: "timeseries.compat.object_type_not_allowed",
            message: "Ese tipo de objeto no admite esta necesidad.",
            field: null,
            context: {},
          },
        },
        selectable: false,
      },
    ],
    page: { limit: 50, has_more: false, next_cursor: null },
    summary: { total_count: 3 },
    facets: null,
    meta: { section: "object_candidates", catalog_generation: 4 },
  };
}

describe("single protected mutation journey", () => {
  it("takes the catalog entry point through the same review and commits many rows as one atomic batch", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/time-series/journey?entry=catalog&signal_id=41&project_id=1",
    );
    const prevalidated: Record<string, unknown>[] = [];
    const commits: { body: Record<string, unknown>; headers: Headers }[] = [];
    let candidateSearch = "";
    const fetchMock = journeyFetch((url, init) => {
      if (
        url.pathname === "/api/time-series/catalog/inputs/41/object-candidates"
      ) {
        candidateSearch = url.search;
        const page = objectCandidates();
        return json({
          ...page,
          items: url.searchParams.has("cursor")
            ? [page.items[1]]
            : [page.items[0], page.items[2]],
          page: {
            has_more: !url.searchParams.has("cursor"),
            next_cursor: "second-objects",
            limit: 2,
          },
        });
      }
      if (url.pathname === "/api/time-series/catalog/inputs/41")
        return json(inputDetail());
      if (url.pathname === "/api/auth/csrf")
        return json({ csrf_token: "csrf" });
      if (
        url.pathname === "/api/time-series/catalog/association-prevalidations"
      ) {
        const body = JSON.parse(String(init?.body)) as {
          operations: { client_operation_id: string }[];
        };
        prevalidated.push(body);
        return json(
          associationPrevalidation({
            operations: body.operations.map((operation) => ({
              client_operation_id: operation.client_operation_id,
              action: "add",
              verdict: "accepted",
              compatibility_decision: {
                allowed: true,
                compatibility_rule_id: 5,
                rule_version: 1,
                contract_version: 1,
                errors: [],
                primary_error: null,
              },
              errors: [],
              observed_state: {},
              comparison: { before: null, after: {} },
            })),
          }),
        );
      }
      if (url.pathname === "/api/time-series/catalog/association-batches") {
        commits.push({
          body: JSON.parse(String(init?.body)),
          headers: new Headers(init?.headers),
        });
        return json(
          {
            outcome: "created",
            batch_id: "batch-bulk",
            operations: [],
            request_id: "req_bulk",
          },
          201,
        );
      }
      return null;
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("option", { name: "Precio de compra a la red" });
    await user.selectOptions(
      screen.getByLabelText("Necesidad funcional"),
      "grid_import_price",
    );
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    const table = await screen.findByRole("table", {
      name: "Objetos candidatos",
    });
    expect(new URLSearchParams(candidateSearch).get("target_project_id")).toBe(
      "1",
    );
    expect(new URLSearchParams(candidateSearch).get("include_denied")).toBe(
      "true",
    );
    const denied = within(table).getByRole("row", { name: /Consumo 1/ });
    expect(within(denied).getByRole("checkbox")).toBeDisabled();
    expect(
      within(denied).getByText("TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED"),
    ).toBeVisible();

    await user.click(screen.getByRole("checkbox", { name: "Elegir Sistema" }));
    await user.click(screen.getByRole("button", { name: "Más objetos" }));
    await screen.findByRole("checkbox", { name: "Elegir Bateria 1" });
    await user.click(
      screen.getByRole("checkbox", { name: "Elegir Bateria 1" }),
    );
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("sha256:price-2")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    // The same final review as the object entry point: one table of verdicts
    // and the same all-or-nothing statement.
    const impact = await screen.findByRole("region", {
      name: "Impacto y confirmacion",
    });
    const verdicts = await within(impact).findByRole("table", {
      name: "Prevalidacion por fila",
    });
    expect(within(verdicts).getAllByText("Aceptada")).toHaveLength(2);
    expect(within(impact).getByText(/todo o nada/i)).toBeVisible();
    expect(impact).toHaveTextContent("Sistema, Bateria 1");

    await user.click(
      within(impact).getByRole("button", { name: "Asociar fuente al objeto" }),
    );

    await waitFor(() => expect(commits).toHaveLength(1));
    expect(prevalidated[0].target_project_id).toBe(1);
    expect(commits[0].body.operations).toEqual([
      expect.objectContaining({ signal_id: 41, linkable_object_id: 7 }),
      expect.objectContaining({ signal_id: 41, linkable_object_id: 8 }),
    ]);
    expect(commits[0].headers.get("If-Match")).toBe('"etag-1"');
    expect(await screen.findByText(/batch-bulk/)).toBeVisible();
  });

  it("keeps the draft and states that nothing was written when the commit is refused", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate",
    );
    const fetchMock = journeyFetch((url) => {
      if (url.pathname === "/api/time-series/catalog/inputs")
        return json(candidatePage());
      if (url.pathname === "/api/time-series/catalog/inputs/41")
        return json(inputDetail());
      if (url.pathname === "/api/auth/csrf")
        return json({ csrf_token: "csrf" });
      if (
        url.pathname === "/api/time-series/catalog/association-prevalidations"
      )
        return json(associationPrevalidation());
      if (url.pathname === "/api/time-series/catalog/association-batches")
        return json(
          {
            error: {
              code: "TS_LINK_PRECONDITION_CHANGED",
              message_key: "timeseries.link.precondition_changed",
              message: "El catalogo cambio desde la prevalidacion.",
              field: null,
              context: {},
              details: [],
            },
            request_id: "req_refused",
          },
          412,
        );
      return null;
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);
    await reachTheAssociationImpact(user);
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    const impact = await screen.findByRole("region", {
      name: "Impacto y confirmacion",
    });
    await user.click(
      within(impact).getByRole("button", { name: "Asociar fuente al objeto" }),
    );

    // AC-SEG-07: the stable code, the request id and the explicit statement.
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("TS_LINK_PRECONDITION_CHANGED");
    expect(alert).toHaveTextContent("req_refused");
    expect(alert).toHaveTextContent("No se escribio nada");

    expect(
      within(impact).getByRole("button", { name: "Asociar fuente al objeto" }),
    ).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Revisar de nuevo" }));
    await waitFor(() =>
      expect(
        within(impact).getByRole("button", {
          name: "Asociar fuente al objeto",
        }),
      ).toBeEnabled(),
    );

    // The draft is intact: the same source is still chosen two steps back.
    await user.click(screen.getByRole("button", { name: "Paso anterior" }));
    await user.click(screen.getByRole("button", { name: "Paso anterior" }));
    expect(
      screen.getByRole("radio", { name: "Elegir Precio de energia" }),
    ).toBeChecked();
  });

  it("publishes for everyone only with the reason, the acknowledgement and the observed fingerprint", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=update_shared&association_id=12",
    );
    const root =
      "/api/projects/1/linkable-objects/7/time-series/catalog-associations/12";
    const publications: { body: Record<string, unknown>; headers: Headers }[] =
      [];
    const fetchMock = journeyFetch((url, init) => {
      if (url.pathname === root)
        return json(
          associationView(url.searchParams.get("intent") ?? "shared"),
        );
      if (url.pathname === "/api/auth/csrf")
        return json({ csrf_token: "csrf" });
      if (url.pathname === `${root}/shared-series/revision-ingestions/points`)
        return json(
          { ingestion: sharedIngestion(), request_id: "req_ing" },
          201,
        );
      if (
        url.pathname ===
        `${root}/shared-series/revision-ingestions/ing-1/publications`
      ) {
        publications.push({
          body: JSON.parse(String(init?.body)),
          headers: new Headers(init?.headers),
        });
        return json(
          {
            publication: { outcome: "published", revision_id: 91 },
            request_id: "req_pub",
          },
          201,
        );
      }
      return null;
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("radio", {
        name: "Todos los consumidores deben ver la curva nueva",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(
      await screen.findByRole("radio", { name: "Publicar para todos" }),
    );
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    await user.type(
      screen.getByLabelText("Puntos (instante, duracion en segundos, valor)"),
      "2026-01-01T00:00:00+00:00,3600,81\n2026-01-01T01:00:00+00:00,3600,82",
    );
    await user.click(
      screen.getByRole("button", { name: "Preparar y previsualizar" }),
    );
    expect(await screen.findByText("sha256:price-3")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    const impact = await screen.findByRole("region", {
      name: "Impacto y confirmacion",
    });
    // AC-SHR-03: the destructive branch keeps its own name.
    const publish = within(impact).getByRole("button", {
      name: "Publicar para todos",
    });
    expect(screen.queryByRole("button", { name: "Guardar" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Actualizar" })).toBeNull();
    expect(publish).toBeDisabled();

    await user.type(
      within(impact).getByLabelText("Motivo"),
      "Mesa de precios de enero",
    );
    expect(publish).toBeDisabled();
    await user.click(within(impact).getByRole("checkbox"));
    expect(publish).toBeEnabled();
    await user.click(publish);

    await waitFor(() => expect(publications).toHaveLength(1));
    expect(publications[0].body).toEqual({
      validation_token: "tok-shared",
      impact_fingerprint: "tsi_abc",
      confirm: true,
      comprehension_acknowledged: true,
      reason_code: "shared_revision_published",
      reason_text: "Mesa de precios de enero",
    });
    expect(publications[0].headers.get("If-Match")).toBe('"shared-etag"');
    expect(publications[0].headers.get("Idempotency-Key")).toBeTruthy();
  });

  it("offers the local alternative first when the declared intent is local and never says Guardar", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=update_shared&association_id=12",
    );
    const observedIntents: (string | null)[] = [];
    const fetchMock = journeyFetch((url) => {
      if (
        url.pathname ===
        "/api/projects/1/linkable-objects/7/time-series/catalog-associations/12"
      ) {
        const intent = url.searchParams.get("intent");
        observedIntents.push(intent);
        return json(associationView(intent ?? "shared"));
      }
      return null;
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("radio", {
        name: "Solo este objeto necesita otra curva",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    const choices = await screen.findByRole("group", {
      name: "Como seguir con la fuente compartida",
    });
    const labels = within(choices)
      .getAllByRole("radio")
      .map((radio) => radio.getAttribute("value"));
    // AC-SHR-02: the local outcome leads for a declared local intent.
    expect(labels).toEqual(["derive_object_specific", "publish_shared"]);
    expect(
      within(choices).getByRole("radio", {
        name: "Crear especifica para este objeto",
      }),
    ).toBeVisible();
    // AC-SHR-03: the shared branch is never softened into a neutral verb.
    expect(
      within(choices).getByRole("radio", { name: "Publicar para todos" }),
    ).toBeVisible();
    expect(screen.queryByRole("radio", { name: "Guardar" })).toBeNull();
    expect(screen.queryByRole("radio", { name: "Actualizar" })).toBeNull();
    expect(observedIntents).toContain("local");

    // The rail never says "undeclared" about a source the impact just proved
    // is shared, and it narrows the moment the local branch is taken.
    const rail = screen.getByRole("complementary", {
      name: "Contexto del recorrido",
    });
    expect(within(rail).getByText("Fuente generica compartida")).toBeVisible();
    await user.click(
      within(choices).getByRole("radio", {
        name: "Crear especifica para este objeto",
      }),
    );
    expect(within(rail).getByText("Solo este objeto")).toBeVisible();

    // The impact is answered before any branch is taken.
    expect(screen.getByText(/1 binding quedara obsoleto/)).toBeVisible();
    expect(screen.getByText(/2 asociaciones/)).toBeVisible();
    expect(screen.getByText(/1 objeto distinto/)).toBeVisible();
  });

  it.each([
    { signalId: 41, associationId: 12 },
    { signalId: 42, associationId: null },
  ])(
    "replaces a binding only after showing the comparison and taking a reason ($signalId)",
    async ({ signalId, associationId }) => {
      window.history.replaceState(
        {},
        "",
        "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=use_revision",
      );
      const commits: { body: Record<string, unknown>; headers: Headers }[] = [];
      let candidateSearch = "";
      const fetchMock = journeyFetch((url, init) => {
        if (url.pathname === "/api/projects/1/scenarios")
          return json(SCENARIOS);
        if (url.pathname === "/api/scenarios/4/case/variants")
          return json(VARIANTS);
        if (
          url.pathname ===
          "/api/scenarios/4/case-variants/9/time-series-bindings"
        )
          return json({
            ...boundBindings(),
            items: [
              {
                ...boundBindings().items[0],
                binding_id: 999,
                object: { ...boundBindings().items[0].object, id: 99 },
                bound_content_hash: "other-object-hash",
              },
              ...boundBindings().items,
            ],
          });
        if (url.pathname === "/api/time-series/catalog/inputs") {
          candidateSearch = url.search;
          return json({
            ...candidatePage(),
            items: [candidateRow({ signal_id: signalId })],
          });
        }
        if (url.pathname === `/api/time-series/catalog/inputs/${signalId}`)
          return json(inputDetail());
        if (url.pathname === "/api/auth/csrf")
          return json({ csrf_token: "csrf" });
        if (
          url.pathname ===
          "/api/scenarios/4/case-variants/9/time-series-binding-prevalidations"
        )
          return json(bindingPrevalidation());
        if (
          url.pathname ===
          "/api/scenarios/4/case-variants/9/time-series-binding-batches"
        ) {
          commits.push({
            body: JSON.parse(String(init?.body)),
            headers: new Headers(init?.headers),
          });
          return json(
            {
              outcome: "created",
              batch_id: "batch-bind",
              bindings_revision: 4,
              operations: [],
              request_id: "req_commit_bind",
            },
            201,
          );
        }
        return null;
      });
      vi.stubGlobal("fetch", fetchMock);
      const user = userEvent.setup();

      render(<App />);

      await screen.findByRole("option", { name: "Precio de compra a la red" });
      await user.selectOptions(
        screen.getByLabelText("Necesidad funcional"),
        "grid_import_price",
      );
      await user.click(
        screen.getByRole("radio", { name: "Reutilizar una fuente generica" }),
      );
      await screen.findByRole("option", { name: "Plan base" });
      await user.selectOptions(screen.getByLabelText("Escenario"), "4");
      await screen.findByRole("option", { name: "Default" });
      await user.selectOptions(screen.getByLabelText("Variante"), "9");
      await user.click(screen.getByRole("button", { name: "Siguiente" }));

      await screen.findByRole("table", {
        name: "Fuentes genericas candidatas",
      });
      expect(new URLSearchParams(candidateSearch).get("context_usage")).toBe(
        "execution",
      );
      await user.click(
        screen.getByRole("radio", { name: "Elegir Precio de energia" }),
      );
      await user.click(screen.getByRole("button", { name: "Siguiente" }));

      // AC-BIN-05: the replacement is visible before it can be confirmed.
      const comparison = await screen.findByRole("table", {
        name: "Comparacion del reemplazo",
      });
      expect(within(comparison).getByText("sha256:price-1")).toBeVisible();
      expect(within(comparison).getByText("sha256:price-2")).toBeVisible();
      expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();

      await user.type(
        screen.getByLabelText("Motivo del reemplazo"),
        "Revisada la curva nueva y aceptada",
      );
      expect(screen.getByRole("button", { name: "Siguiente" })).toBeEnabled();
      await user.click(screen.getByRole("button", { name: "Siguiente" }));

      const impact = await screen.findByRole("region", {
        name: "Impacto y confirmacion",
      });
      await user.click(
        within(impact).getByRole("button", {
          name: "Usar revision en una variante",
        }),
      );

      await waitFor(() => expect(commits).toHaveLength(1));
      expect(commits[0].body.expected_bindings_revision).toBe(3);
      expect(commits[0].body.operations).toEqual([
        expect.objectContaining({
          action: "replace",
          binding_id: 73,
          expected_lifecycle_revision: 1,
          signal_id: signalId,
          binding_role_key: "grid_import_price",
          linkable_object_id: 7,
          catalog_association_id: associationId,
          revision: {
            mode: "current",
            revision_id: 90,
            content_hash: "sha256:price-2",
          },
          reason_text: "Revisada la curva nueva y aceptada",
        }),
      ]);
      expect(commits[0].headers.get("If-Match")).toBe('"etag-bind"');
    },
  );

  it("keeps the draft when stepping back and forces a new prevalidation when the source changes", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate",
    );
    const prevalidated: Record<string, unknown>[] = [];
    const commits: { body: unknown; headers: Headers }[] = [];
    const fetchMock = journeyFetch((url, init) => {
      if (url.pathname === "/api/time-series/catalog/inputs")
        return json(candidatePage());
      if (url.pathname === "/api/time-series/catalog/inputs/41")
        return json(inputDetail());
      if (url.pathname === "/api/time-series/catalog/inputs/43")
        return json({
          ...inputDetail(),
          signal_id: 43,
          identity: {
            series_key: "spot_price",
            display_name: "Precio spot",
            description: null,
            status: "active",
          },
          current_revision: {
            ...inputDetail().current_revision,
            id: 95,
            number: 4,
            content_hash: "sha256:spot-4",
          },
        });
      if (url.pathname === "/api/auth/csrf")
        return json({ csrf_token: "csrf" });
      if (
        url.pathname === "/api/time-series/catalog/association-prevalidations"
      ) {
        const body = JSON.parse(String(init?.body)) as {
          operations: { signal_id: number }[];
        };
        prevalidated.push(body);
        const signalId = body.operations[0].signal_id;
        return json(
          associationPrevalidation({
            prevalidation_token: `tok-${signalId}`,
            commit_etag: `"etag-${signalId}"`,
          }),
        );
      }
      if (url.pathname === "/api/time-series/catalog/association-batches") {
        commits.push({
          body: JSON.parse(String(init?.body)),
          headers: new Headers(init?.headers),
        });
        return json(
          {
            outcome: "created",
            batch_id: "batch-2",
            operations: [],
            request_id: "req_commit",
          },
          201,
        );
      }
      return null;
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);
    await reachTheAssociationImpact(user);
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await screen.findByRole("region", { name: "Impacto y confirmacion" });
    expect(prevalidated).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Paso anterior" }));
    await user.click(screen.getByRole("button", { name: "Paso anterior" }));

    // The draft survived both steps back.
    expect(
      screen.getByRole("radio", { name: "Elegir Precio de energia" }),
    ).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Paso anterior" }));
    expect(screen.getByLabelText("Necesidad funcional")).toHaveValue(
      "grid_import_price",
    );

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("radio", { name: "Elegir Precio spot" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("sha256:spot-4")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    const impact = await screen.findByRole("region", {
      name: "Impacto y confirmacion",
    });
    await waitFor(() => expect(prevalidated).toHaveLength(2));
    expect(prevalidated[1].operations).toEqual([
      expect.objectContaining({ signal_id: 43 }),
    ]);

    await user.click(
      within(impact).getByRole("button", { name: "Asociar fuente al objeto" }),
    );
    await waitFor(() => expect(commits).toHaveLength(1));
    expect(commits[0].headers.get("If-Match")).toBe('"etag-43"');
    expect(
      (commits[0].body as Record<string, unknown>).prevalidation_token,
    ).toBe("tok-43");
  });

  it("pins the observed revision, prevalidates once and commits with token, ETag and idempotency key", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate",
    );
    const commits: { body: unknown; headers: Headers }[] = [];
    const fetchMock = journeyFetch((url, init) => {
      if (url.pathname === "/api/time-series/catalog/inputs")
        return json(candidatePage());
      if (url.pathname === "/api/time-series/catalog/inputs/41")
        return json(inputDetail());
      if (url.pathname === "/api/auth/csrf")
        return json({ csrf_token: "csrf" });
      if (
        url.pathname === "/api/time-series/catalog/association-prevalidations"
      )
        return json(associationPrevalidation());
      if (url.pathname === "/api/time-series/catalog/association-batches") {
        commits.push({
          body: JSON.parse(String(init?.body)),
          headers: new Headers(init?.headers),
        });
        return json(
          {
            outcome: "created",
            batch_id: "batch-1",
            operations: [
              {
                client_operation_id: "op-1",
                action: "add",
                outcome: "created",
                association_id: 12,
              },
            ],
            request_id: "req_commit",
          },
          201,
        );
      }
      return null;
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);
    await reachTheAssociationImpact(user);

    // Step 3 states the exact revision and hash the association observed.
    expect(await screen.findByText("sha256:price-2")).toBeVisible();
    expect(screen.getByText("Revision 2")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    const impact = await screen.findByRole("region", {
      name: "Impacto y confirmacion",
    });
    expect(within(impact).getByText("Aceptada")).toBeVisible();
    expect(within(impact).getByText(/2 asociaciones/)).toBeVisible();
    expect(within(impact).getByText(/todo o nada/i)).toBeVisible();
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Asociar fuente al objeto",
      }),
    ).toBeVisible();
    expect(within(impact).getByText("Sistema")).toBeVisible();
    expect(
      within(impact).getByText(/Precio de energia · revisión 2/),
    ).toBeVisible();

    await user.click(
      within(impact).getByRole("button", { name: "Asociar fuente al objeto" }),
    );

    expect(await screen.findByText(/batch-1/)).toBeVisible();
    expect(
      screen.getByText(
        /La fuente quedó asociada al objeto. Su uso en una variante se confirma por separado/,
      ),
    ).toBeVisible();
    expect(commits).toHaveLength(1);
    const body = commits[0].body as Record<string, unknown>;
    expect(body.prevalidation_token).toBe("tok-1");
    expect(body.confirmed).toBe(true);
    expect(commits[0].headers.get("If-Match")).toBe('"etag-1"');
    expect(commits[0].headers.get("Idempotency-Key")).toBeTruthy();
  });

  it("explains an incompatible candidate with its stable code and never lets it be chosen", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate",
    );
    const searches: string[] = [];
    const fetchMock = journeyFetch((url) => {
      if (url.pathname !== "/api/time-series/catalog/inputs") return null;
      searches.push(url.search);
      const page = candidatePage();
      return json({
        ...page,
        items:
          url.searchParams.get("compatibility") === "all"
            ? page.items
            : page.items.filter((row) => row.compatibility_decision.allowed),
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("option", { name: "Precio de compra a la red" });
    await user.selectOptions(
      screen.getByLabelText("Necesidad funcional"),
      "grid_import_price",
    );
    await user.click(
      screen.getByRole("radio", { name: "Reutilizar una fuente generica" }),
    );
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    const table = await screen.findByRole("table", {
      name: "Fuentes genericas candidatas",
    });
    const compatible = within(table).getByRole("row", {
      name: /Precio de energia/,
    });
    expect(within(compatible).getByRole("radio")).toBeEnabled();

    expect(
      within(table).queryByRole("row", { name: /Afluente medido/ }),
    ).not.toBeInTheDocument();
    expect(new URLSearchParams(searches.at(-1)).get("compatibility")).toBe(
      "allowed",
    );
    await user.click(
      screen.getByRole("checkbox", { name: "Mostrar todas las series" }),
    );
    await screen.findByRole("radio", { name: "Elegir Afluente medido" });

    const denied = within(
      screen.getByRole("table", { name: "Fuentes genericas candidatas" }),
    ).getByRole("row", { name: /Afluente medido/ });
    expect(within(denied).getByRole("radio")).toBeDisabled();
    expect(
      within(denied).getByText(
        "La dimension de la senal no corresponde al rol.",
      ),
    ).toBeVisible();
    expect(
      within(denied).getByText("TS_COMPAT_DIMENSION_MISMATCH"),
    ).toBeVisible();

    const applied = new URLSearchParams(searches.at(-1));
    expect(applied.get("context_linkable_object_id")).toBe("7");
    expect(applied.get("context_binding_role_key")).toBe("grid_import_price");
    expect(applied.get("context_usage")).toBe("association");
    expect(applied.get("compatibility")).toBe("all");
  });

  it("makes origin and scope explicit before anything can be selected", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate",
    );
    vi.stubGlobal("fetch", journeyFetch());
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("heading", {
      name: "Asociar fuente al objeto",
      level: 1,
    });
    const rail = screen.getByRole("complementary", {
      name: "Contexto del recorrido",
    });
    // Nothing may be selected until the origin is declared.
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();

    await screen.findByRole("option", { name: "Precio de compra a la red" });
    await user.selectOptions(
      screen.getByLabelText("Necesidad funcional"),
      "grid_import_price",
    );
    await user.click(
      screen.getByRole("radio", { name: "Crear especifica para este objeto" }),
    );

    expect(within(rail).getByText("Solo este objeto")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    const steps = within(rail).getByRole("list", {
      name: "Pasos del recorrido",
    });
    expect(
      within(steps).getByText("Definicion o seleccion").closest("li"),
    ).toHaveAttribute("aria-current", "step");
    // The rail never drops the object or the scope.
    expect(within(rail).getByText("Sistema")).toBeVisible();
    expect(within(rail).getByText("Solo este objeto")).toBeVisible();
  });

  it.each(["puntos", "CSV", "XLSX", "CSV corregido"])(
    "defines an object-specific series, stages %s and seals it in the same four steps",
    async (channel) => {
      window.history.replaceState(
        {},
        "",
        "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=associate",
      );
      const seen: string[] = [];
      const fetchMock = journeyFetch((url, init) => {
        if (url.pathname === "/api/auth/csrf")
          return json({ csrf_token: "csrf" });
        if (url.pathname === "/api/time-series/catalog/descriptors") {
          const kind = url.searchParams.get("kind");
          if (kind === "semantic_type") return json(SEMANTIC_TYPES);
          if (kind === "unit") return json(UNITS);
          if (kind === "data_class") return json(DATA_CLASSES);
          return json(BINDING_ROLES);
        }
        if (
          url.pathname ===
          "/api/projects/1/linkable-objects/7/time-series/object-series"
        ) {
          seen.push("definition");
          return new Response(
            JSON.stringify({ object_series: OBJECT_SERIES }),
            {
              status: 201,
              headers: {
                "Content-Type": "application/json",
                ETag: '"object-series-41-1"',
              },
            },
          );
        }
        if (url.pathname.endsWith("/revision-ingestions/points")) {
          seen.push("staging");
          return json({ ingestion: OBJECT_INGESTION }, 201);
        }
        if (url.pathname.endsWith("/revision-ingestions/files")) {
          if (channel === "CSV corregido")
            return json(
              {
                ingestion: {
                  ...OBJECT_INGESTION,
                  state: "awaiting_mapping",
                  validation_token: null,
                  file: {
                    original_filename: "precios.csv",
                    columns: [
                      "timestamp",
                      "duration_hours",
                      "price",
                      "corrected_price",
                    ],
                    available_sheets: [],
                    selected_sheet: null,
                    preview_rows: [],
                  },
                },
              },
              202,
            );
          if (channel === "XLSX")
            return json(
              {
                ingestion: {
                  ...OBJECT_INGESTION,
                  state: "awaiting_mapping",
                  validation_token: null,
                  file: {
                    original_filename: "precios.xlsx",
                    columns: [],
                    available_sheets: ["Notas", "Precios"],
                    selected_sheet: null,
                    preview_rows: [],
                  },
                },
              },
              202,
            );
          return json(
            {
              ingestion: {
                ...OBJECT_INGESTION,
                state: "awaiting_mapping",
                validation_token: null,
                file: {
                  original_filename: "precios.csv",
                  columns: ["timestamp", "duration_hours", "price"],
                  available_sheets: [],
                  selected_sheet: null,
                  preview_rows: [
                    {
                      timestamp: "2026-01-01T00:00:00Z",
                      duration_hours: "1",
                      price: "18.4",
                    },
                  ],
                },
              },
            },
            202,
          );
        }
        if (url.pathname.endsWith("/mapping")) {
          if (
            channel === "CSV corregido" &&
            JSON.parse(String(init?.body)).columns.signals[0].value === "price"
          )
            return json(
              {
                detail: "Valor inválido",
                context: {
                  ingestion: {
                    ...OBJECT_INGESTION,
                    state: "invalid",
                    validation_token: null,
                    capabilities: { publish: false },
                    validation: {
                      valid: false,
                      error_count: 1,
                      errors: [
                        {
                          code: "TS_INGEST_VALUE_INVALID",
                          message: "Número ambiguo",
                          location: { source_row_number: 2, column: "price" },
                        },
                      ],
                    },
                    file: {
                      original_filename: "precios.csv",
                      columns: [
                        "timestamp",
                        "duration_hours",
                        "price",
                        "corrected_price",
                      ],
                      available_sheets: [],
                      selected_sheet: null,
                      preview_rows: [],
                    },
                  },
                },
              },
              422,
            );
          if (channel === "XLSX" && !JSON.parse(String(init?.body)).columns)
            return json(
              {
                detail: "Choose the file columns",
                code: "TS_INGEST_MAPPING_INVALID",
                context: {
                  ingestion: {
                    ...OBJECT_INGESTION,
                    state: "awaiting_mapping",
                    validation_token: null,
                    validation: {
                      valid: false,
                      errors: [
                        {
                          code: "TS_INGEST_MAPPING_INVALID",
                          message: "Elegir columnas",
                        },
                      ],
                      error_count: 1,
                    },
                    file: {
                      original_filename: "precios.xlsx",
                      columns: ["timestamp", "duration_hours", "price"],
                      available_sheets: ["Notas", "Precios"],
                      selected_sheet: "Precios",
                      preview_rows: [],
                    },
                  },
                },
              },
              422,
            );
          seen.push("staging");
          return json({
            ingestion: {
              ...OBJECT_INGESTION,
              channel: "file_csv",
              capabilities: { publish: true },
              file: {
                original_filename: "precios.csv",
                columns: ["timestamp", "duration_hours", "price"],
                available_sheets: [],
                selected_sheet: null,
                preview_rows: [],
              },
            },
          });
        }
        if (url.pathname.endsWith("/preview"))
          return json({
            source_row_count: 1,
            returned_row_count: 1,
            rows: [{ timestamp_start: "2026-01-01T00:00:00Z", value: 18.4 }],
          });
        if (url.pathname.endsWith("/publications")) {
          seen.push("publication");
          // The seal has to travel with the definition ETag and its own key.
          const headers = new Headers(init?.headers);
          expect(headers.get("If-Match")).toBe('"object-series-41-1"');
          expect(headers.get("Idempotency-Key")).toBeTruthy();
          return json(
            {
              publication: {
                outcome: "new_revision",
                revision_id: 501,
                content_hash: "sha256:local-first-revision",
              },
            },
            201,
          );
        }
        return null;
      });
      vi.stubGlobal("fetch", fetchMock);
      const user = userEvent.setup();

      render(<App />);

      await screen.findByRole("heading", {
        name: "Asociar fuente al objeto",
        level: 1,
      });
      await screen.findByRole("option", { name: "Precio de compra a la red" });
      await user.selectOptions(
        screen.getByLabelText("Necesidad funcional"),
        "grid_import_price",
      );
      await user.click(
        screen.getByRole("radio", {
          name: "Crear especifica para este objeto",
        }),
      );
      await user.click(screen.getByRole("button", { name: "Siguiente" }));

      // Step 2 is the definition, and it says out loud that the series belongs
      // to this object only.
      expect(
        await screen.findByText(/Solo este objeto\. La serie pertenece a/),
      ).toBeVisible();
      await user.clear(screen.getByLabelText("Clave local"));
      await user.type(screen.getByLabelText("Clave local"), "precio_local");
      await user.clear(screen.getByLabelText("Nombre visible"));
      await user.type(screen.getByLabelText("Nombre visible"), "Precio local");
      await user.selectOptions(
        screen.getByLabelText("Tipo semantico"),
        "energy_price",
      );
      await user.selectOptions(screen.getByLabelText("Unidad"), "usd_per_mwh");
      await user.selectOptions(
        screen.getByLabelText("Clase de dato"),
        "forecast",
      );
      await user.click(screen.getByRole("button", { name: "Siguiente" }));

      // Step 3: saving only the definition is already valid, and it leaves the
      // series explicitly not selectable.
      await user.click(
        await screen.findByRole("button", { name: "Guardar definicion" }),
      );
      expect(await screen.findByText("awaiting_data")).toBeVisible();
      expect(screen.getByText("No, aun sin revision sellada")).toBeVisible();

      if (channel !== "puntos") {
        await user.upload(
          screen.getByLabelText("Archivo para esta serie"),
          new File(
            ["timestamp,duration_hours,price\n2026-01-01T00:00:00Z,1,18.4\n"],
            channel === "XLSX" ? "precios.xlsx" : "precios.csv",
            {
              type:
                channel === "XLSX"
                  ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  : "text/csv",
            },
          ),
        );
        await user.click(
          screen.getByRole("button", { name: "Subir archivo temporal" }),
        );
        if (channel === "XLSX")
          await user.selectOptions(
            await screen.findByLabelText("Hoja del archivo"),
            "Precios",
          );
        await user.selectOptions(
          await screen.findByLabelText("Columna de valor"),
          "price",
        );
        await user.selectOptions(
          screen.getByLabelText("Columna de inicio"),
          "timestamp",
        );
        await user.selectOptions(
          screen.getByLabelText("Columna de duración en horas"),
          "duration_hours",
        );
        await user.click(
          screen.getByRole("button", {
            name: "Confirmar columnas y validar archivo",
          }),
        );
        if (channel === "CSV corregido") {
          expect(
            await screen.findByText(/fila 2, columna price: Número ambiguo/),
          ).toBeVisible();
          expect(
            screen.queryByRole("table", { name: "Revisión del archivo" }),
          ).not.toBeInTheDocument();
          await user.selectOptions(
            screen.getByLabelText("Columna de valor"),
            "corrected_price",
          );
          await user.click(
            screen.getByRole("button", {
              name: "Confirmar columnas y validar archivo",
            }),
          );
        }
        expect(
          await screen.findByRole("table", { name: "Revisión del archivo" }),
        ).toHaveTextContent("18.4");
      } else {
        await user.type(
          screen.getByLabelText(
            "Puntos (instante ISO, duracion en segundos, valor)",
          ),
          "2026-01-01T00:00:00+00:00,3600,18.4",
        );
        await user.click(screen.getByRole("button", { name: "Validar datos" }));
      }
      expect(await screen.findByText("ready_to_publish")).toBeVisible();

      await user.click(screen.getByRole("button", { name: "Siguiente" }));

      // Step 4 states the scope, the absence of any catalog association and the
      // all-or-nothing publication before it can be confirmed.
      expect(
        await screen.findByText("Solo este objeto: Sistema."),
      ).toBeVisible();
      expect(screen.getByText(/Ninguna asociacion de catalogo/)).toBeVisible();
      const seal = screen.getByRole("button", {
        name: "Publicar revision de esta serie",
      });
      expect(seal).toBeDisabled();

      await user.type(
        screen.getByLabelText("Motivo"),
        "Primera carga de la curva local",
      );
      await user.click(seal);

      expect(
        await screen.findByText(/Revision sellada \(new_revision\)/),
      ).toBeVisible();
      expect(
        screen.getByRole("link", { name: "Abrir series del objeto" }),
      ).toHaveAttribute(
        "href",
        "/react/projects/1/linkable-objects/7/time-series",
      );
      expect(
        screen.getByText(/La revisión importada todavía debe elegirse/),
      ).toBeVisible();
      // Define, stage, seal: three server moves, in that order, once each.
      expect(seen).toEqual(["definition", "staging", "publication"]);
    },
  );

  it("takes the object entry point into the four steps and keeps object and scope in the rail", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/projects/1/linkable-objects/7/time-series",
    );
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://localhost");
      if (url.pathname === "/api/auth/me") return json(VERIFICATION_IDENTITY);
      if (url.pathname === "/api/projects/1")
        return json({
          project: {
            id: 1,
            name: "Cuenca Norte",
            description: "",
            created_at: "2026-01-01",
          },
        });
      if (url.pathname === "/api/projects/1/scenarios") return json(SCENARIOS);
      if (url.pathname === "/api/scenarios/4/case/variants")
        return json(VARIANTS);
      if (url.pathname === "/api/projects/1/linkable-objects/7/time-series")
        return json(objectSummaryPage());
      if (url.pathname === "/api/time-series/catalog/descriptors")
        return json(BINDING_ROLES);
      return json({ detail: `unhandled ${url.pathname}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    await user.click(
      await screen.findByRole("link", { name: "Asociar fuente al objeto" }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Asociar fuente al objeto",
        level: 1,
      }),
    ).toBeVisible();
    const rail = screen.getByRole("complementary", {
      name: "Contexto del recorrido",
    });
    expect(within(rail).getByText("Sistema")).toBeVisible();
    expect(within(rail).getByText("Objeto")).toBeVisible();
    const steps = within(rail).getByRole("list", {
      name: "Pasos del recorrido",
    });
    expect(within(steps).getAllByRole("listitem")).toHaveLength(4);
    expect(
      within(steps).getByText("Origen y alcance").closest("li"),
    ).toHaveAttribute("aria-current", "step");
  });
});
