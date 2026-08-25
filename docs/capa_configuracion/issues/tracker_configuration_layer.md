# BESS Configuration Layer Issue Tracker

This document is the local implementation tracker for the configuration layer,
operator console and configured client portal defined by
`docs/capa_configuracion/architecture_configuration_layer_final.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues are AFK tracer-bullet
slices and carry the `ready-for-agent` triage label.

The accepted architecture document is normative. Implementation issues may
surface evidence that a contract is impossible, but they must not silently
reopen or weaken decisions from the completed Wayfinder map.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or newly discovered impossibility.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- |
| BESS-CONFIG-001 | Expand External Project Capabilities Beside Legacy Client Access | AFK | ready-for-agent | Done | None | [BESS-CONFIG-001-expand-external-project-capabilities-beside-legacy-client-access.md](BESS-CONFIG-001-expand-external-project-capabilities-beside-legacy-client-access.md) |
| BESS-CONFIG-002 | Cut Over The Portal To External Capabilities And Retire Legacy Client Access | AFK | ready-for-agent | Done | BESS-CONFIG-001 | [BESS-CONFIG-002-cut-over-the-portal-to-external-capabilities-and-retire-legacy-client-access.md](BESS-CONFIG-002-cut-over-the-portal-to-external-capabilities-and-retire-legacy-client-access.md) |
| BESS-CONFIG-003 | Configure One Portal Result End To End | AFK | ready-for-agent | Done | BESS-CONFIG-002 | [BESS-CONFIG-003-configure-one-portal-result-end-to-end.md](BESS-CONFIG-003-configure-one-portal-result-end-to-end.md) |
| BESS-CONFIG-004 | Cut Over All Portal Results To Safe Shared Payloads | AFK | ready-for-agent | In Review | BESS-CONFIG-003 | [BESS-CONFIG-004-cut-over-all-portal-results-to-safe-shared-payloads.md](BESS-CONFIG-004-cut-over-all-portal-results-to-safe-shared-payloads.md) |
| BESS-CONFIG-005 | Brand The Client Portal With A Project Name And Logo | AFK | ready-for-agent | In Review | BESS-CONFIG-003 | [BESS-CONFIG-005-brand-the-client-portal-with-a-project-name-and-logo.md](BESS-CONFIG-005-brand-the-client-portal-with-a-project-name-and-logo.md) |
| BESS-CONFIG-006 | Create And Activate An Operator Console End To End | AFK | ready-for-agent | Done | BESS-CONFIG-002 | [BESS-CONFIG-006-create-and-activate-an-operator-console-end-to-end.md](BESS-CONFIG-006-create-and-activate-an-operator-console-end-to-end.md) |
| BESS-CONFIG-007 | Drive Console Signal Choices From The Canonical Catalog | AFK | ready-for-agent | In Review | BESS-CONFIG-006 | [BESS-CONFIG-007-drive-console-signal-choices-from-the-canonical-catalog.md](BESS-CONFIG-007-drive-console-signal-choices-from-the-canonical-catalog.md) |
| BESS-CONFIG-008 | Land Users In Separate Analyst, Console And Portal Roots | AFK | ready-for-agent | In Review | BESS-CONFIG-002, BESS-CONFIG-006 | [BESS-CONFIG-008-land-users-in-separate-analyst-console-and-portal-roots.md](BESS-CONFIG-008-land-users-in-separate-analyst-console-and-portal-roots.md) |
| BESS-CONFIG-009 | Run A Configured Console With Parameter Overrides | AFK | ready-for-agent | In Review | BESS-CONFIG-004, BESS-CONFIG-006 | [BESS-CONFIG-009-run-a-configured-console-with-parameter-overrides.md](BESS-CONFIG-009-run-a-configured-console-with-parameter-overrides.md) |
| BESS-CONFIG-010 | Edit One Exposed Series Without Changing Canonical Data | AFK | ready-for-agent | In Review | BESS-CONFIG-007, BESS-CONFIG-009 | [BESS-CONFIG-010-edit-one-exposed-series-without-changing-canonical-data.md](BESS-CONFIG-010-edit-one-exposed-series-without-changing-canonical-data.md) |
| BESS-CONFIG-011 | Paste And Save Multi-Set Groups Atomically | AFK | ready-for-agent | In Review | BESS-CONFIG-010 | [BESS-CONFIG-011-paste-and-save-multi-set-groups-atomically.md](BESS-CONFIG-011-paste-and-save-multi-set-groups-atomically.md) |
| BESS-CONFIG-012 | Switch Named Series Sources Safely | AFK | ready-for-agent | In Review | BESS-CONFIG-010 | [BESS-CONFIG-012-switch-named-series-sources-safely.md](BESS-CONFIG-012-switch-named-series-sources-safely.md) |
| BESS-CONFIG-013 | Coordinate Editors And Preserve Auditable Series History | AFK | ready-for-agent | Todo | BESS-CONFIG-011 | [BESS-CONFIG-013-coordinate-editors-and-preserve-auditable-series-history.md](BESS-CONFIG-013-coordinate-editors-and-preserve-auditable-series-history.md) |
| BESS-CONFIG-014 | Fail Closed And Request Engineer Review After External Changes | AFK | ready-for-agent | In Review | BESS-CONFIG-009, BESS-CONFIG-010 | [BESS-CONFIG-014-fail-closed-and-request-engineer-review-after-external-changes.md](BESS-CONFIG-014-fail-closed-and-request-engineer-review-after-external-changes.md) |
| BESS-CONFIG-015 | Resolve Console Blocks With The Correct Engineer Action | AFK | ready-for-agent | Todo | BESS-CONFIG-012, BESS-CONFIG-014 | [BESS-CONFIG-015-resolve-console-blocks-with-the-correct-engineer-action.md](BESS-CONFIG-015-resolve-console-blocks-with-the-correct-engineer-action.md) |
| BESS-CONFIG-016 | Compare Two Configured Console Runs Safely | AFK | ready-for-agent | Todo | BESS-CONFIG-009, BESS-CONFIG-010 | [BESS-CONFIG-016-compare-two-configured-console-runs-safely.md](BESS-CONFIG-016-compare-two-configured-console-runs-safely.md) |
| BESS-CONFIG-017 | Prove The Configuration Layer End To End | AFK | ready-for-agent | Todo | BESS-CONFIG-001 through BESS-CONFIG-016 | [BESS-CONFIG-017-prove-the-configuration-layer-end-to-end.md](BESS-CONFIG-017-prove-the-configuration-layer-end-to-end.md) |

## Initial Frontier

Only [Expand External Project Capabilities Beside Legacy Client Access](BESS-CONFIG-001-expand-external-project-capabilities-beside-legacy-client-access.md)
can start immediately. Every other issue has at least one open blocker.

## Dependency Waves

1. BESS-CONFIG-001.
2. BESS-CONFIG-002.
3. BESS-CONFIG-003 and BESS-CONFIG-006.
4. BESS-CONFIG-004, BESS-CONFIG-005, BESS-CONFIG-007 and BESS-CONFIG-008.
5. BESS-CONFIG-009.
6. BESS-CONFIG-010.
7. BESS-CONFIG-011, BESS-CONFIG-012, BESS-CONFIG-014 and BESS-CONFIG-016.
8. BESS-CONFIG-013 and BESS-CONFIG-015.
9. BESS-CONFIG-017.

Issues in the same wave are independent according to the accepted dependency
graph and may be implemented in parallel.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-08-23 | All | Created | Seventeen AFK tracer-bullet issues published from the accepted configuration-layer architecture after explicit approval of granularity, dependency relationships and AFK classification. BESS-CONFIG-001 is the initial frontier. |
| 2026-08-23 | BESS-CONFIG-001 | Todo -> In Review | Added the transitional external identity, independent audited project capabilities, safe SQLite/PostgreSQL migration, admin API/UI management and portal compatibility under TDD. |
| 2026-08-23 | BESS-CONFIG-001 | In Review -> Done | Accepted as the prerequisite for the contract cutover. |
| 2026-08-23 | BESS-CONFIG-002 | Todo -> In Review | Retired the legacy client role and client-access contract, enforced portal_view on portal entry and every project resource, preserved revocation semantics and regenerated the React/OpenAPI contract under TDD. |
| 2026-08-23 | BESS-CONFIG-002 | In Review -> Done | Accepted as the prerequisite for the configured portal and console slices. |
| 2026-08-23 | BESS-CONFIG-003 | Todo -> In Review | Added versioned portal configurations with expected-revision control, full `portal_config.v1` structural validation, the shared `app/surface_payloads.py` boundary for one KPI, the internal configuration API and analyst UI, and identical configured output in the publication preview and the external portal under TDD. |
| 2026-08-23 | BESS-CONFIG-003 | In Review -> Done | Accepted after the focused suite and the full Python suite stayed green; it is the base the full portal cutover builds on. |
| 2026-08-23 | BESS-CONFIG-004 | Todo -> In Review | Cut the portal and the preview over to one allowlisted builder with KPIs, charts, tables and downloads, added the fixed backend catalogs plus `GET /api/portal-catalogs`, migrated dashboard templates once behind a `schema_migrations` marker, dropped run/scenario/template records from the external payload and rebuilt both surfaces on the same React report under TDD. |
| 2026-08-23 | BESS-CONFIG-005 | Todo -> In Progress | Started the project branding slice under TDD at the confirmed persistence, HTTP and React seams. |
| 2026-08-23 | BESS-CONFIG-005 | In Progress -> In Review | Added public display-name and protected PNG/JPEG logo management, revision-aware binary persistence, allowlisted branding payloads, neutral portal presentation and current-brand historical publications under TDD; 651 Python tests, 93 Vitest tests, schema checks, lint, build and a Chrome portal narrative passed. |
| 2026-08-23 | BESS-CONFIG-006 | Todo -> In Progress | Started the operator-console tracer bullet under TDD at the document, persistence, internal API, console API and React seams. |
| 2026-08-23 | BESS-CONFIG-006 | In Progress -> In Review | Added `operator_console_config.v1` structural validation, the `operator_consoles` identity with its exclusive cloned variant, revision-controlled internal management, the `/api/console` boundary with fail-closed 404s for draft, foreign and guessed ids, an allowlisted console payload, and the workspace panel, configuration editor and console shell with a non-impersonating internal test strip; 679 Python tests, 10 PostgreSQL tests against the dev database, 99 Vitest tests, tsc, eslint, API schema check, build and a Chrome narrative passed. |
| 2026-08-23 | BESS-CONFIG-006 | In Review -> Done | Accepted as the base the catalog-driven console configuration builds on. |
| 2026-08-23 | BESS-CONFIG-007 | Todo -> In Progress | Started the canonical signal-catalog slice under TDD at the required-signal, HTTP, payload-boundary and React configuration-editor seams. |
| 2026-08-23 | BESS-CONFIG-007 | In Progress -> In Review | Made `TIME_SERIES_SIGNAL_CATALOG` the single source of truth: added internal-only `GET /api/time-series/signal-catalog`, turned `ONE_BUS_ENTITY_SIGNALS` into an ordered list of declarative requirements per node type with the hydraulic path untouched, deleted the frontend signal-to-unit table so the console editor, connector ingestion, catalog import and set replacement all derive options, units and nonnegative rules from the endpoint, and guarded the external console payload against signal keys and entity pointers; 691 Python tests, 103 Vitest tests, tsc, eslint, regenerated API schema, build and a Chrome narrative on a live console passed. |
| 2026-08-24 | BESS-CONFIG-008 | Todo -> In Progress | Started the three-root slice under TDD at the auth-response, application boundary and React root seams. |
| 2026-08-24 | BESS-CONFIG-008 | In Progress -> In Review | Replaced `redirect_path` with one `landing_path` returned identically by login, bootstrap and `/api/auth/me`, implemented the safe-next -> internal -> `operate` -> portal precedence with `operate` beating `portal_view`, made a next target outside the identity's roots fall through, turned every root an external identity may not enter into a 404 ahead of the CSRF check, and split the React shell into analyst, console and portal roots with their own headers plus a denied-root fallback that links back to the server landing path; the nineteen `isClient` checks are gone. 697 Python tests, 10 PostgreSQL tests against the dev database, 108 Vitest tests, tsc, eslint, the API schema check, the production build and a Chrome narrative across the three roots passed. |
| 2026-08-24 | BESS-CONFIG-009 | Todo -> In Review | Added console-owned scalar overrides by external id, atomic boundary validation, period/run gating, immutable materialization with effective provenance, authenticated actor and console lineage on common queued runs, safe failure translation, shared configured results, reduced run history and the complete React operator workflow under TDD. 714 Python tests, 10 PostgreSQL persistence tests (5 environment skips), 532 Julia tests, 110 Vitest tests, tsc, eslint, focused Prettier, API schema check, production build and a Chrome narrative passed. |
| 2026-08-24 | BESS-CONFIG-010 | Todo -> In Review | Added console-owned series editing: the `/api/console/{id}/groups/{group_id}` values, lease and save endpoints, the opaque `ETag`/`If-Match` control, the per-copy edit lock keyed by origin set, the flat non-derived operational copy with inert origin lineage, the console-only rebinding, the auditable edit revision, the narrow copied-set dependency refresh, and the React table plus read-only chart with dirty-cell run gating under TDD. 745 Python tests, 11 PostgreSQL tests against the dev database, 113 Vitest tests, tsc, eslint, focused Prettier, the API schema check, the production build and a Chrome narrative on live console 2 (canonical set 54 unchanged, console variant rebound to operational copy 61) passed. |
| 2026-08-24 | BESS-CONFIG-011 | Todo -> In Progress | Started the atomic multi-set paste slice under TDD at the confirmed persistence, HTTP and React seams. |
| 2026-08-24 | BESS-CONFIG-011 | In Progress -> In Review | Added locale-free rectangular paste with header, locked-column and overflow reporting; atomic validation and save across every touched operational copy; capped public cell errors for coverage and stale conflicts; all configured granularities; an optional diff; sparse dirty-cell state; and bounded full-horizon rendering under TDD. 751 Python tests (6 environment skips), 119 Vitest tests, tsc, eslint, focused Prettier, the API schema check and the production build passed. A Chrome narrative pasted eight values across two sets, reviewed the complete diff and saved both copies in one request; persistence confirmed both revision-2 copies and unchanged canonical values. |
| 2026-08-25 | BESS-CONFIG-012 | Todo -> In Review | Added public named-source options, server-side project/signal/entity/coverage validation, transactional flat-copy creation and reuse, atomic console-owned rebinding, safe archival, immediate React table refresh and new-source run materialization under TDD. 764 Python tests (7 environment skips), 120 Vitest tests, tsc, eslint, focused Prettier, the API schema check and the production build passed. An isolated Chrome narrative switched Demanda from the public base option to the updated forecast, reloaded values from 10-13 to 20-23 and produced no browser-console warnings or errors. |
| 2026-08-25 | BESS-CONFIG-014 | Todo -> In Review | Collapsed the three duplicated gate computations onto one internal `describe_operator_console_block` plus the pure `build_console_run_gate`, closed the fail-open hole that let a run start with an unresolvable exposed source, added `POST /api/console/{id}/request-review` writing only `waiting_since` on a genuine engineering block, kept raw staleness detail internal while the public gate gained `review_requested_at`, and returned the active consoles a case save blocked as a synchronous non-blocking warning in the analyst draft editor under TDD. 795 Python tests (7 environment skips), 12 PostgreSQL tests against the dev database, 122 Vitest tests, tsc, eslint, focused Prettier, the regenerated API schema and the production build passed. An isolated Chrome narrative moved a case parameter, watched the console fail closed with the preparer's name, requested review, saw the run refused at 409 with only the public reason, and watched the engineer's revalidation reopen the gate. |

## Regression Guard

Every slice must preserve the existing immutable scenario-version and run
history, TS-1 through TS-6 contracts, hydraulic behavior, publication artifact
allowlists and both supported database engines where persistence changes.

Backend changes run the relevant focused tests and the full Python suite.
Frontend changes run Vitest, TypeScript, ESLint, API schema checks and the
production build. Julia tests are required when a slice changes generated case
payloads, artifact contracts or optimizer behavior. BESS-CONFIG-017 closes the
effort only after the full acceptance and browser narratives pass.
