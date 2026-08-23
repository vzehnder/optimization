# BESS-CONFIG-004: Cut Over All Portal Results To Safe Shared Payloads

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Complete the configured portal by supporting the full fixed report order:
publication context, KPIs, charts, tables and approved downloads. Migrate each
project from its most recent usable dashboard template, switch both preview and
live portal to one allowlisted payload builder, and stop reading dashboard
templates for presentation. An analyst can configure the content and
vocabulary inside the fixed shell, and a client sees only those declared
results.

The shared results block established here is also the contract later consumed
by operator-console results.

## Acceptance criteria

- [x] Portal configurations support ordered KPI, chart, table and download sections using only fixed backend catalogs.
- [x] Existing dashboard-template flags and table limits migrate to explicit portal configuration entries without enabling content that was previously hidden.
- [x] A project with publications but no usable template receives a safe explicit configuration with no result panels enabled by fallback.
- [x] Dashboard templates remain as legacy data but are no longer read to construct preview or live presentation.
- [x] Preview and live portal use the same result builder and differ only where context-specific URLs require it.
- [x] Only configured KPIs, chart series, tables and columns appear; unknown keys, `all_series` and `plot_series` never pass through.
- [x] Downloads remain the intersection of portal configuration and the publication artifact allowlist.
- [x] The portal renders the fixed macro order with configured labels, empty states and unavailable-result language that exposes no artifact details.
- [x] Negative boundary tests inject sensitive database fields, unknown summary keys and server artifact paths and prove none appear in portal, preview or serialized results.
- [x] Existing publication identity, comments, dates, status, run selection and downloadable artifacts remain intact.

## Implementation notes

Three contract details the accepted architecture leaves implicit were settled
here and must stay consistent with the console slices:

- `results_block.labels` carries `kpis`, `charts`, `tables` and `downloads`.
  A disabled section exposes an empty label and the surfaces render nothing for
  it, so no default vocabulary can leak. The downloads label lives in
  `results_block` beside the other section titles even though the download list
  itself is a top-level `portal_payload` field.
- The external publication payload now exposes only `project {id, name}`,
  `publication {id, project_id, public_title, analyst_notes, published_at,
  status}`, `period`, `results_state`, `results_block` and `downloads`.
  `scenario`, `scenario_version`, `run`, `template` and `results_error` are
  gone: an artifact failure only produces `results_state = "unavailable"`.
  `project` becomes `branding` in BESS-CONFIG-005.
- `GET /api/publications/{id}/preview` returns that same payload plus an
  internal `preview_context` block (`run_id`, `scenario_version_number`,
  `results_error`) so the analyst keeps navigation and the technical reason for
  an unavailable result. Everything the client sees comes from the shared
  builder and renders through the same React components.

Supporting decisions:

- `app/portal_configuration.py` declares the fixed catalogs: nine charts with
  their allowed series and two tables with their allowed columns. Validation
  rejects any `chart_key`, series key, `table_key` or column key outside them,
  and `GET /api/portal-catalogs` publishes that vocabulary so the analyst UI can
  only offer what the backend accepts.
- The dashboard-template migration runs once, guarded by a new
  `schema_migrations` marker table. Without the marker a project published
  after the cutover would be configured from its template on the next start,
  silently enabling panels the analyst never declared. Projects that already
  carry a configuration are never touched, and a published project without a
  usable template gets a document with every section disabled.
- `show_summary` used to print the whole summary document; only
  `objective_value_usd` migrates as a KPI, because the KPI contract carries
  scalars with a public label and unit. Migrated tables keep every catalog
  column so nothing that used to be visible disappears; the analyst trims them.

## Blocked by

- [BESS-CONFIG-003: Configure One Portal Result End To End](BESS-CONFIG-003-configure-one-portal-result-end-to-end.md)
