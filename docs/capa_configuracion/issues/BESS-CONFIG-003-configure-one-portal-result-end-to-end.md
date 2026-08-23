# BESS-CONFIG-003: Configure One Portal Result End To End

Status: Todo
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

- [ ] Each project can persist one portal configuration with draft or active status, a schema version, a revision counter, timestamps and the updating user.
- [ ] The internal configuration UI lets an analyst define the portal display name, KPI section label and one allowlisted KPI item without editing raw database state.
- [ ] Unknown schema versions, malformed documents, duplicate ids, invalid enums and stale expected revisions are rejected without a partial write.
- [ ] Saving a valid active configuration increments its revision and updates the audit metadata.
- [ ] The publication preview and external publication render the configured KPI with the same id, label, value, unit, decimals, sign and emphasis.
- [ ] A missing KPI value is omitted without breaking the rest of the publication.
- [ ] Canonical KPI paths and internal run metadata are resolved in the backend and do not cross the external payload.
- [ ] Existing portal behavior not yet handled by the new builder remains green until the full cutover.
- [ ] Persistence, API, React and authorization tests prove the complete analyst-to-client path.

## Blocked by

- [BESS-CONFIG-002: Cut Over The Portal To External Capabilities And Retire Legacy Client Access](BESS-CONFIG-002-cut-over-the-portal-to-external-capabilities-and-retire-legacy-client-access.md)
