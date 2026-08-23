# BESS-CONFIG-003: Configure One Portal Result End To End

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Deliver the first thin path through the new portal configuration model. An
analyst creates or edits a versioned portal configuration, chooses one
allowlisted KPI with a public label and presentation options, previews it, and
an authorized external user sees that same KPI in the live publication.
Invalid document structure is rejected before writing, while a structurally
valid active edit becomes visible immediately.

Introduce the shared safe payload boundary with only the behavior required for
this first KPI. Other legacy portal sections may continue through their
existing path until the full cutover issue, so this slice can land
independently without regressing the current portal.

## Acceptance criteria

- [x] Each project can persist one portal configuration with draft or active status, a schema version, a revision counter, timestamps and the updating user.
- [x] The internal configuration UI lets an analyst define the portal display name, KPI section label and one allowlisted KPI item without editing raw database state.
- [x] Unknown schema versions, malformed documents, duplicate ids, invalid enums and stale expected revisions are rejected without a partial write.
- [x] Saving a valid active configuration increments its revision and updates the audit metadata.
- [x] The publication preview and external publication render the configured KPI with the same id, label, value, unit, decimals, sign and emphasis.
- [x] A missing KPI value is omitted without breaking the rest of the publication.
- [x] Canonical KPI paths and internal run metadata are resolved in the backend and do not cross the external payload.
- [x] Existing portal behavior not yet handled by the new builder remains green until the full cutover.
- [x] Persistence, API, React and authorization tests prove the complete analyst-to-client path.

## Implementation notes

Two contract details the accepted architecture leaves implicit were settled
here and must stay consistent with the remaining slices:

- `results_block` carries a `labels` map so the configured KPI section title
  reaches the client. The normative `results_block` shorthand lists item
  arrays only, and neither it nor `portal_payload` has a place for
  `sections.kpis.label`, which this issue requires to be configurable. A
  disabled section exposes an empty label, never a default.
- `sign` accepts `auto`, `always` and `never`; `emphasis` accepts `normal` and
  `strong`. The architecture shows only `auto` and `strong` by example, so the
  full enumerations are declared in `app/portal_configuration.py`.

Validation covers the whole `portal_config.v1` document (KPIs, charts, tables
and downloads) because that is the persisted schema version, but only the KPI
section is rendered by the new builder. Charts and tables keep the legacy
dashboard-template path until BESS-CONFIG-004. `portal_configurations` carries
no logo columns yet; BESS-CONFIG-005 adds them with the branding endpoints.

## Blocked by

- [BESS-CONFIG-002: Cut Over The Portal To External Capabilities And Retire Legacy Client Access](BESS-CONFIG-002-cut-over-the-portal-to-external-capabilities-and-retire-legacy-client-access.md)
