# BESS React UI Migration Issue Tracker

This document is the local tracker for the React UI migration derived from
[`prd_react_ui_migration.md`](../prd_react_ui_migration.md).

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the
`ready-for-agent` triage label and are intended for future execution.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- |
| BESS-REACT-000 | Establish React Application Foundation | AFK | ready-for-agent | Done | None | [BESS-REACT-000-establish-react-application-foundation.md](BESS-REACT-000-establish-react-application-foundation.md) |
| BESS-REACT-001 | Migrate Authentication And Role-Gated Entry | AFK | ready-for-agent | Done | BESS-REACT-000 | [BESS-REACT-001-migrate-authentication-and-role-gated-entry.md](BESS-REACT-001-migrate-authentication-and-role-gated-entry.md) |
| BESS-REACT-002 | Migrate Project And Scenario Workspace | AFK | ready-for-agent | Done | BESS-REACT-001 | [BESS-REACT-002-migrate-project-and-scenario-workspace.md](BESS-REACT-002-migrate-project-and-scenario-workspace.md) |
| BESS-REACT-003 | Migrate Structured Scenario Draft Editor | AFK | ready-for-agent | Done | BESS-REACT-002 | [BESS-REACT-003-migrate-structured-scenario-draft-editor.md](BESS-REACT-003-migrate-structured-scenario-draft-editor.md) |
| BESS-REACT-004 | Migrate Time-Series Ingestion And Editing | AFK | ready-for-agent | Todo | BESS-REACT-003 | [BESS-REACT-004-migrate-time-series-ingestion-and-editing.md](BESS-REACT-004-migrate-time-series-ingestion-and-editing.md) |
| BESS-REACT-005 | Migrate Case Validation And Versioning | AFK | ready-for-agent | Todo | BESS-REACT-004 | [BESS-REACT-005-migrate-case-validation-and-versioning.md](BESS-REACT-005-migrate-case-validation-and-versioning.md) |
| BESS-REACT-006 | Migrate Manual Run Lifecycle | AFK | ready-for-agent | Todo | BESS-REACT-005 | [BESS-REACT-006-migrate-manual-run-lifecycle.md](BESS-REACT-006-migrate-manual-run-lifecycle.md) |
| BESS-REACT-007 | Migrate Results Charts And Artifacts | AFK | ready-for-agent | Todo | BESS-REACT-006 | [BESS-REACT-007-migrate-results-charts-and-artifacts.md](BESS-REACT-007-migrate-results-charts-and-artifacts.md) |
| BESS-REACT-008 | Migrate Dashboard Templates And Publications | AFK | ready-for-agent | Todo | BESS-REACT-002, BESS-REACT-007 | [BESS-REACT-008-migrate-dashboard-templates-and-publications.md](BESS-REACT-008-migrate-dashboard-templates-and-publications.md) |
| BESS-REACT-009 | Migrate Admin Users And Project Access | AFK | ready-for-agent | Todo | BESS-REACT-001, BESS-REACT-002 | [BESS-REACT-009-migrate-admin-users-and-project-access.md](BESS-REACT-009-migrate-admin-users-and-project-access.md) |
| BESS-REACT-010 | Migrate Read-Only Client Portal | AFK | ready-for-agent | Todo | BESS-REACT-008, BESS-REACT-009 | [BESS-REACT-010-migrate-read-only-client-portal.md](BESS-REACT-010-migrate-read-only-client-portal.md) |
| BESS-REACT-011 | Cut Over To React And Remove Legacy UI | AFK | ready-for-agent | Todo | BESS-REACT-000 through BESS-REACT-010 | [BESS-REACT-011-cut-over-to-react-and-remove-legacy-ui.md](BESS-REACT-011-cut-over-to-react-and-remove-legacy-ui.md) |

## Recommended Execution Order

1. BESS-REACT-000 establishes the coexisting React application, typed API
   client, production serving, and browser acceptance seam.
2. BESS-REACT-001 establishes JSON authentication, role-aware entry, and the
   mutation security inherited by every later slice.
3. BESS-REACT-002 creates the project/scenario navigation spine.
4. After the workspace exists, BESS-REACT-003 through BESS-REACT-007 form the
   primary analyst modeling and run-review chain.
5. BESS-REACT-009 can proceed in parallel with BESS-REACT-003 through
   BESS-REACT-007 after project navigation exists.
6. BESS-REACT-008 follows result review because publication preview reuses the
   client-safe result presentation.
7. BESS-REACT-010 joins project assignment and published results into the first
   complete React client path.
8. BESS-REACT-011 runs only after every earlier replacement path is accepted.

The critical path is:

```text
BESS-REACT-000
-> BESS-REACT-001
-> BESS-REACT-002
-> BESS-REACT-003
-> BESS-REACT-004
-> BESS-REACT-005
-> BESS-REACT-006
-> BESS-REACT-007
-> BESS-REACT-008
-> BESS-REACT-010
-> BESS-REACT-011
```

BESS-REACT-009 branches after BESS-REACT-002 and rejoins at
BESS-REACT-010.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-06-22 | All | Created | Initial local issue set generated from the React UI Migration PRD using tracer-bullet vertical slices. |
| 2026-06-22 | BESS-REACT-000 | Todo -> In Progress | Implementation and non-browser verification complete; Chrome smoke verification pending plugin recovery. |
| 2026-06-22 | BESS-REACT-000 | In Progress -> Done | Chrome and automated Chromium smoke tests pass; foundation accepted. |
| 2026-06-23 | BESS-REACT-001 | Todo -> Done | JSON auth contracts, React bootstrap/login/logout/role entry, CSRF defense, regression updates, Playwright acceptance, and Chrome smoke pass. |
| 2026-06-23 | BESS-REACT-002 | Todo -> Done | React analyst project/scenario workspace, direct detail routes, empty/error states, browser acceptance, and Chrome smoke pass. |
| 2026-06-23 | BESS-REACT-003 | Todo -> Done | React structured draft editor, multi-asset save/reopen/removal, dirty/saving/saved/failed states, stale-save guard, navigation guard, browser acceptance, backend regressions, and Chrome smoke pass. |

## Acceptance Seam

The primary seam is a browser-driven acceptance suite against a real isolated
FastAPI application and database. Every issue must prove its user-visible React
flow through this seam, including the relevant API, cookie, upload, polling,
download, and permission behavior.

Focused API or component tests are additions to this seam, not replacements for
it. Tests should assert visible behavior and stable contracts rather than
component trees, hook calls, CSS classes, or other implementation details.

## Regression Guard

Every migration slice must preserve the existing Python acceptance suites for
the domain behavior it touches. Slices that affect authorization must include
both positive internal/client access and material negative access cases.

The Julia regression suite is required only if a slice changes Julia-facing
validation, execution contracts, or artifact formats. The migration is expected
to avoid those changes.

BESS-REACT-000 must establish stable frontend commands for:

- type generation and drift checking;
- static analysis and formatting checks;
- focused component tests;
- browser acceptance tests;
- production build and production-serving smoke tests.

Later issues should use those commands rather than introducing per-issue test
runners.

## Final Migration Verification

The cutover issue must prove all of the following from a clean environment:

- the production React build is reproducible;
- FastAPI serves the compiled application and direct SPA routes correctly;
- the full browser acceptance suite passes across admin, analyst, and client
  roles;
- the full Python test suite passes after obsolete HTML assertions are removed
  or converted to API/domain assertions;
- security coverage passes for sessions, cross-site request forgery defense,
  role boundaries, project assignment, publication state, revocation, artifact
  allowlists, and safe paths;
- no user workflow still depends on legacy HTML renderers or form endpoints;
- operator and developer documentation matches the final commands and route
  behavior.

## Dependency Notes

- BESS-REACT-000 is intentional prefactoring: it makes each later end-to-end
  migration slice small enough to execute and verify independently.
- BESS-REACT-001 precedes all protected product work because client-side route
  guards cannot substitute for complete JSON authentication and mutation
  security contracts.
- BESS-REACT-003 and BESS-REACT-004 are separate because asset-form state and
  tabular source state have different interaction and performance risks, while
  each remains independently demoable.
- BESS-REACT-005 closes the authoring loop before run execution is migrated.
- BESS-REACT-007 precedes publication work so internal review and client-safe
  presentation share proven result semantics.
- BESS-REACT-009 can run in parallel with the analyst modeling chain but must be
  complete before the portal can prove project assignment and revocation.
- BESS-REACT-010 deliberately includes revocation in the same vertical slice as
  client visibility; delayed authorization hardening would create an unsafe
  intermediate portal.
- BESS-REACT-011 is intentionally the only issue authorized to remove the legacy
  UI after complete parity is proven.
