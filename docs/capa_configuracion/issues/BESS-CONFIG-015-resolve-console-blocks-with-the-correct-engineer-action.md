# BESS-CONFIG-015: Resolve Console Blocks With The Correct Engineer Action

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Give engineers a focused recovery workflow in the existing scenario console
list. Each blocked console shows its real reason, review age and the one correct
action: revalidate the owned variant for a moved dependency or edit the
configuration for an unavailable field. A canonical source advancing beyond
an operational copy appears as a non-blocking badge and never regenerates
operator data.

## Acceptance criteria

- [x] The scenario console list shows name, draft or active status, blocking reason, `waiting_since` and old-origin-copy state.
- [x] `dependencia_movida` links to the existing validation action for the console-owned variant.
- [x] Successful variant validation can clear `dependencia_movida` but cannot pretend to repair `campo_no_disponible`.
- [x] `campo_no_disponible` links to the exact parameter or column configuration that must be corrected.
- [x] Saving a corrected valid configuration can clear `campo_no_disponible` but cannot silently attest unrelated moved dependencies.
- [x] Advancing a canonical source revision produces an internal old-copy badge without blocking the operator.
- [x] Old operational copies are never regenerated automatically and their values and audit history remain intact.
- [x] A failure reference from an operator links internal users to the existing technical run detail while remaining inaccessible to external users.
- [x] The recovery surface adds no global inbox, notification scheduler, semantic save-time linter, automatic expiry or record of who moved the dependency.
- [x] Integration and React tests cover both distinct recovery paths, mixed states, old-copy detection and 404 protection of technical run details.

## Implementation notes

- The internal console description now exposes one typed recovery action. A
  moved dependency reuses validation for the console-owned variant and clears
  only that attestation; an unavailable field carries the exact parameter or
  group-column target and clears only after a valid corrected save.
- Operational copy lineage compares the immutable copied revision with the
  current canonical revision. It renders as an internal, non-blocking badge
  without rebinding, regenerating or mutating the copy or its audit history.
- The most recent failed operator run is exposed only as an internal technical
  reference to the existing run detail. Existing root authorization keeps the
  same URL unavailable to external users.

## Blocked by

- [BESS-CONFIG-012: Switch Named Series Sources Safely](BESS-CONFIG-012-switch-named-series-sources-safely.md)
- [BESS-CONFIG-014: Fail Closed And Request Engineer Review After External Changes](BESS-CONFIG-014-fail-closed-and-request-engineer-review-after-external-changes.md)
