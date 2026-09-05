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
    if (url.pathname === "/api/projects/1/linkable-objects/7/time-series")
      return json(objectSummaryPage());
    if (url.pathname === "/api/time-series/catalog/descriptors")
      return json(BINDING_ROLES);
    return json({ detail: `unhandled ${url.pathname}` }, 500);
  });
}

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
        return json(objectCandidates());
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

    // The draft is intact: the same source is still chosen two steps back.
    await user.click(screen.getByRole("button", { name: "Volver" }));
    await user.click(screen.getByRole("button", { name: "Volver" }));
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

  it("replaces a binding only after showing the comparison and taking a reason", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/time-series/journey?entry=object&project_id=1&object_id=7&intent=use_revision",
    );
    const commits: { body: Record<string, unknown>; headers: Headers }[] = [];
    let candidateSearch = "";
    const fetchMock = journeyFetch((url, init) => {
      if (url.pathname === "/api/projects/1/scenarios") return json(SCENARIOS);
      if (url.pathname === "/api/scenarios/4/case/variants")
        return json(VARIANTS);
      if (
        url.pathname === "/api/scenarios/4/case-variants/9/time-series-bindings"
      )
        return json(boundBindings());
      if (url.pathname === "/api/time-series/catalog/inputs") {
        candidateSearch = url.search;
        return json(candidatePage());
      }
      if (url.pathname === "/api/time-series/catalog/inputs/41")
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

    await screen.findByRole("table", { name: "Fuentes genericas candidatas" });
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
        signal_id: 41,
        binding_role_key: "grid_import_price",
        linkable_object_id: 7,
        catalog_association_id: 12,
        revision: {
          mode: "current",
          revision_id: 90,
          content_hash: "sha256:price-2",
        },
        reason_text: "Revisada la curva nueva y aceptada",
      }),
    ]);
    expect(commits[0].headers.get("If-Match")).toBe('"etag-bind"');
  });

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

    await user.click(screen.getByRole("button", { name: "Volver" }));
    await user.click(screen.getByRole("button", { name: "Volver" }));

    // The draft survived both steps back.
    expect(
      screen.getByRole("radio", { name: "Elegir Precio de energia" }),
    ).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Volver" }));
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

    await user.click(
      within(impact).getByRole("button", { name: "Asociar fuente al objeto" }),
    );

    expect(await screen.findByText(/batch-1/)).toBeVisible();
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
      return json(candidatePage());
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

    const denied = within(table).getByRole("row", { name: /Afluente medido/ });
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

    await screen.findByRole("heading", { name: "Recorrido protegido" });
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

  it("takes the object entry point into the four steps and keeps object and scope in the rail", async () => {
    window.history.replaceState(
      {},
      "",
      "/react/projects/1/linkable-objects/7/time-series",
    );
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://localhost");
      if (url.pathname === "/api/auth/me") return json(VERIFICATION_IDENTITY);
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
      await screen.findByRole("heading", { name: "Recorrido protegido" }),
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
