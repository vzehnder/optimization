# BESS-CONFIG-017: Prove The Configuration Layer End To End

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Close the configuration-layer effort with one acceptance narrative that proves
the migrated portal and the operator console work through their real
boundaries. The automated suite, React coverage and browser verification must
exercise the fixed shells, authorization, configuration, editing, execution,
results, recovery and migration contracts without relying on internal ids or
privileged shortcuts.

This issue is closing proof and documentation. Any missing behavior uncovered
by the proof is fixed in the owning slice rather than weakening the accepted
specification.

## Acceptance criteria

- [x] Migration proof shows a legacy client becomes `external` plus `portal_view`, sees the same publications and gains no console access.
- [x] Capability proof covers `portal_view`, `operate`, both, neither, revocation on the next request, landing precedence and external 404 behavior.
- [x] Configuration proof covers structural rejection without writes, active revision increments, semantic fail-closed loading and faithful preview.
- [x] Portal proof covers configured results, allowlisted downloads, current branding, conscious removal of project description and product marks, and inaccessible foreign content.
- [x] Parameter proof shows isolation from the analyst draft and base hash while the immutable run contains effective values and real actor lineage.
- [x] Series proof covers first operational copy, canonical isolation, source switching, atomic multi-set save, parser ambiguity, truncation, cell errors and unchanged state after failure.
- [x] Concurrency proof covers atomic group leases, heartbeat, expiry, stale ETag, read-only contention, undo, internal restore and complete audit attribution.
- [x] Staleness proof distinguishes own and external changes, proves both recovery gestures, records review requests and keeps old-origin copies non-blocking.
- [x] Execution proof covers common Julia/indexing reuse, safe pre-engine and Julia failures, configured run detail and two-run comparison.
- [x] Payload-boundary proof injects sensitive database columns, unknown result keys and server paths into both surfaces and proves none escape.
- [x] Signal-catalog proof shows a declarative new entry reaches the internal console editor without changing table, parser, external payload or frontend unit mapping.
- [x] React tests cover all three roots, fixed-shell states, editing gestures, branding, results, recovery and authorization guards.
- [x] Browser verification completes operator login, landing, lease, paste, save, run, result, comparison and engineer recovery; it also completes client login, publication, branding, results and authorized download.
- [x] Full backend, frontend, schema-drift, production-build and relevant engine regression suites pass.
- [x] Final documentation records verification commands and results and confirms that every explicitly out-of-scope item remains out of the implementation.

## Implementation

- Added `tests/test_configuration_layer_acceptance.py` as the closing backend
  narrative across migration, authorization, operator editing, immutable runs,
  recovery, safe results, comparison, portal configuration and payload bounds.
- Added `scripts/run_configuration_acceptance_app.py` as a repeatable local
  fixture for the visible Chrome narrative, using the real FastAPI/React
  boundaries, SQLite in memory and the existing synchronous smoke run queue.
- Migrated the historical Playwright scenarios from the retired `client` and
  `client-access` contracts to `external` capabilities, active portal
  configuration and current visible UI controls.
- Fixed same-timestamp capability revocation in React so a returned capability
  change resets the editor even when `updated_at` has not advanced.

## Verification

Commands, results, coverage mapping and the browser narrative are recorded in
[the final configuration-layer verification](../verification_configuration_layer_final.md).

## Scope closure

No accepted contract was weakened to make the proof pass. The complete
architecture `Fuera de alcance` list is repeated and confirmed unchanged in
the verification report.

## Blocked by

- [BESS-CONFIG-001: Expand External Project Capabilities Beside Legacy Client Access](BESS-CONFIG-001-expand-external-project-capabilities-beside-legacy-client-access.md)
- [BESS-CONFIG-002: Cut Over The Portal To External Capabilities And Retire Legacy Client Access](BESS-CONFIG-002-cut-over-the-portal-to-external-capabilities-and-retire-legacy-client-access.md)
- [BESS-CONFIG-003: Configure One Portal Result End To End](BESS-CONFIG-003-configure-one-portal-result-end-to-end.md)
- [BESS-CONFIG-004: Cut Over All Portal Results To Safe Shared Payloads](BESS-CONFIG-004-cut-over-all-portal-results-to-safe-shared-payloads.md)
- [BESS-CONFIG-005: Brand The Client Portal With A Project Name And Logo](BESS-CONFIG-005-brand-the-client-portal-with-a-project-name-and-logo.md)
- [BESS-CONFIG-006: Create And Activate An Operator Console End To End](BESS-CONFIG-006-create-and-activate-an-operator-console-end-to-end.md)
- [BESS-CONFIG-007: Drive Console Signal Choices From The Canonical Catalog](BESS-CONFIG-007-drive-console-signal-choices-from-the-canonical-catalog.md)
- [BESS-CONFIG-008: Land Users In Separate Analyst, Console And Portal Roots](BESS-CONFIG-008-land-users-in-separate-analyst-console-and-portal-roots.md)
- [BESS-CONFIG-009: Run A Configured Console With Parameter Overrides](BESS-CONFIG-009-run-a-configured-console-with-parameter-overrides.md)
- [BESS-CONFIG-010: Edit One Exposed Series Without Changing Canonical Data](BESS-CONFIG-010-edit-one-exposed-series-without-changing-canonical-data.md)
- [BESS-CONFIG-011: Paste And Save Multi-Set Groups Atomically](BESS-CONFIG-011-paste-and-save-multi-set-groups-atomically.md)
- [BESS-CONFIG-012: Switch Named Series Sources Safely](BESS-CONFIG-012-switch-named-series-sources-safely.md)
- [BESS-CONFIG-013: Coordinate Editors And Preserve Auditable Series History](BESS-CONFIG-013-coordinate-editors-and-preserve-auditable-series-history.md)
- [BESS-CONFIG-014: Fail Closed And Request Engineer Review After External Changes](BESS-CONFIG-014-fail-closed-and-request-engineer-review-after-external-changes.md)
- [BESS-CONFIG-015: Resolve Console Blocks With The Correct Engineer Action](BESS-CONFIG-015-resolve-console-blocks-with-the-correct-engineer-action.md)
- [BESS-CONFIG-016: Compare Two Configured Console Runs Safely](BESS-CONFIG-016-compare-two-configured-console-runs-safely.md)
