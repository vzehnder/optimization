# BESS TS-5 Issue Tracker

This document is the local tracker for TS-5: migration, unification and
hardening of the common topology/parameters/series/results model, derived
from `docs/series_tiempo/iter5/prd.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the
`ready-for-agent` triage label.

## Date Policy

All issues generated from this point forward include:

- `Fecha de inicio planificada`
- `Fecha de termino planificada`

Actual start/end dates can be added or corrected by the implementer when work
really begins and ends.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Fecha de inicio planificada | Fecha de termino planificada | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BESS-TS5-000 | Review TS-5 PRD And Migration Semantics | HITL | ready-for-agent | Done | 2026-07-09 | 2026-07-09 | None | [BESS-TS5-000-review-ts5-prd-and-migration-semantics.md](BESS-TS5-000-review-ts5-prd-and-migration-semantics.md) |
| BESS-TS5-001 | Extract A Legacy Draft Series Source Into The Generic Catalog | AFK | ready-for-agent | Done | 2026-07-10 | 2026-07-13 | BESS-TS5-000 | [BESS-TS5-001-extract-a-legacy-draft-series-source-into-the-generic-catalog.md](BESS-TS5-001-extract-a-legacy-draft-series-source-into-the-generic-catalog.md) |
| BESS-TS5-002 | Read Legacy Hydraulic Series Through The Common Catalog | AFK | ready-for-agent | Todo | 2026-07-14 | 2026-07-15 | BESS-TS5-000 | [BESS-TS5-002-read-legacy-hydraulic-series-through-the-common-catalog.md](BESS-TS5-002-read-legacy-hydraulic-series-through-the-common-catalog.md) |
| BESS-TS5-003 | Route New Hydraulic Series Writes To The Generic Model | AFK | ready-for-agent | Todo | 2026-07-16 | 2026-07-17 | BESS-TS5-002 | [BESS-TS5-003-route-new-hydraulic-series-writes-to-the-generic-model.md](BESS-TS5-003-route-new-hydraulic-series-writes-to-the-generic-model.md) |
| BESS-TS5-004 | Migrate Legacy Hydraulic Sets On Demand With Audit Preserved | AFK | ready-for-agent | Todo | 2026-07-20 | 2026-07-21 | BESS-TS5-003 | [BESS-TS5-004-migrate-legacy-hydraulic-sets-on-demand-with-audit-preserved.md](BESS-TS5-004-migrate-legacy-hydraulic-sets-on-demand-with-audit-preserved.md) |
| BESS-TS5-005 | Keep Stale Validation Reliable Across Legacy And Migrated Series | AFK | ready-for-agent | Todo | 2026-07-22 | 2026-07-22 | BESS-TS5-001, BESS-TS5-004 | [BESS-TS5-005-keep-stale-validation-reliable-across-legacy-and-migrated-series.md](BESS-TS5-005-keep-stale-validation-reliable-across-legacy-and-migrated-series.md) |
| BESS-TS5-006 | Resolve Scenario And Case Cardinality In Schema And UI | AFK | ready-for-agent | Todo | 2026-07-23 | 2026-07-24 | BESS-TS5-000 | [BESS-TS5-006-resolve-scenario-and-case-cardinality-in-schema-and-ui.md](BESS-TS5-006-resolve-scenario-and-case-cardinality-in-schema-and-ui.md) |
| BESS-TS5-007 | Unify Concept Labels And Deprecation Paths In The UI | AFK | ready-for-agent | Todo | 2026-07-27 | 2026-07-27 | BESS-TS5-006 | [BESS-TS5-007-unify-concept-labels-and-deprecation-paths-in-the-ui.md](BESS-TS5-007-unify-concept-labels-and-deprecation-paths-in-the-ui.md) |
| BESS-TS5-008 | Enforce Consistent Permissions For Sources, Series And Results | AFK | ready-for-agent | Todo | 2026-07-28 | 2026-07-29 | BESS-TS5-000 | [BESS-TS5-008-enforce-consistent-permissions-for-sources-series-and-results.md](BESS-TS5-008-enforce-consistent-permissions-for-sources-series-and-results.md) |
| BESS-TS5-009 | Add Retention And Cleanup For Rebuildable Derived Data | AFK | ready-for-agent | Todo | 2026-07-30 | 2026-07-30 | BESS-TS5-000 | [BESS-TS5-009-add-retention-and-cleanup-for-rebuildable-derived-data.md](BESS-TS5-009-add-retention-and-cleanup-for-rebuildable-derived-data.md) |
| BESS-TS5-010 | Review Constraints And Indexes For Real Query Patterns | AFK | ready-for-agent | Todo | 2026-07-31 | 2026-07-31 | BESS-TS5-001 through BESS-TS5-005 | [BESS-TS5-010-review-constraints-and-indexes-for-real-query-patterns.md](BESS-TS5-010-review-constraints-and-indexes-for-real-query-patterns.md) |
| BESS-TS5-011 | Finalize TS-5 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | 2026-08-03 | 2026-08-03 | BESS-TS5-001 through BESS-TS5-010 | [BESS-TS5-011-finalize-ts5-acceptance-suite-and-docs.md](BESS-TS5-011-finalize-ts5-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-TS5-000 closes the PRD review and the migration-semantics decision
   record (per-path strategies, `ScenarioDraft` role, hydraulic write
   strategy, cardinality, permission matrix, retention boundaries).
2. BESS-TS5-001 is the tracer bullet: one legacy draft's embedded series
   extract into the generic catalog with origin metadata and bind to a
   variant, idempotently.
3. BESS-TS5-002 exposes legacy hydraulic series through the common catalog
   semantics via a read adapter, without migrating rows.
4. BESS-TS5-003 routes new hydraulic series writes to the generic model so
   the parallel legacy tables stop growing.
5. BESS-TS5-004 adds the on-demand, audit-preserving migration for existing
   legacy hydraulic sets, plus a stable bulk sweep.
6. BESS-TS5-005 proves stale validation stays fail-closed across extracted,
   migrated, adapter-read and native series.
7. BESS-TS5-006 implements the accepted `Scenario -> OptimizationCase`
   cardinality outcome in schema, routes and UI.
8. BESS-TS5-007 unifies concept labels and marks deprecation paths in the UI.
9. BESS-TS5-008 enforces the accepted permission matrix for sources, input
   series, result series and publications across every surface.
10. BESS-TS5-009 adds retention and cleanup for rebuildable derived data,
    closed against the TS-4 rebuild path.
11. BESS-TS5-010 reviews constraints and indexes against the real TS-2
    through TS-4 query patterns with query-shape guard tests.
12. BESS-TS5-011 closes the iteration with the acceptance suite, the final
    architecture document and docs.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-07-08 | All | Created | Initial local issue set generated from the TS-5 PRD (`docs/series_tiempo/iter5/prd.md`) and the series hierarchy roadmap. |
| 2026-07-08 | BESS-TS5-000 | Todo -> Done | Accepted TS-5 migration semantics in `docs/series_tiempo/iter5/decision_record_ts5_migration_semantics.md`: per-path strategy (extract-on-demand for draft/structured series, adapt-then-migrate-on-demand for hydraulic series, freeze-read-only for historical scenario versions, rebuild-on-demand for artifact-only runs); `ScenarioDraft` stays a compatibility surface; `Scenario -> OptimizationCase` cardinality confirmed one-to-one (no migration); hydraulic write strategy is generic-model writes with adapter reads, no dual write, open-ended per-project compatibility window; permission matrix formalizes the existing internal/client split; retention boundary is the TS-4 result-index tables (rebuildable) versus everything else (immutable audit). No PRD correction required. |
| 2026-07-08 | BESS-TS5-001 | Todo -> Done | Added deep module `app/legacy_series_extraction.py` extracting a draft's already-validated `time_series` source (mapping + `validated_rows`) directly into a generic catalog set (periods/signals/values, entity-scoped signals included), no column-remapping step required. New `AnalystStore.extract_draft_time_series_set` persistence method with a `time_series_set_extractions` origin/idempotency table; re-extraction of unchanged data is a no-op returning the same set, a content-hash mismatch raises instead of duplicating. Fixed a latent gap in the shared TS-2 catalog insert helper (`CatalogValue`/`_insert_time_series_signals_periods_values`) that assumed one signal per `signal_key` per set; now keys on `(signal_key, entity_key)`, needed because legacy drafts can have multiple assets of the same type. New endpoint `POST /api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/extract` and a new "Extract legacy series to catalog" panel in `DraftEditor.tsx`; catalog set detail page shows an "Origen" section for extracted sets. Backend: `tests/test_ts5_draft_series_extraction.py` (8 tests, full suite green). Frontend: `tsc -b`, `eslint .`, `vitest run`, `npm run build` all green (note: `npm run api:check` false-positives as stale due to a pre-existing Windows `core.autocrlf` CRLF/LF mismatch unrelated to this change, confirmed present on the base branch too). Verified live in Chrome against the real PostgreSQL dev DB end-to-end: upload -> validate mapping -> extract -> catalog listing -> origin metadata -> idempotent re-extraction (no duplicate) -> selectable and range-valid in the case's required-signal binding dropdowns. |

## Final TS-5 Verification

Run before considering TS-5 closed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts5_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```powershell
cd frontend
npm test -- --run
npx tsc -b
npx eslint .
npm run api:check
npm run build
```

Julia regression is only required if a TS-5 slice changes artifact formats,
the generated `system_case_json` contract or optimizer behavior; the
hydraulic write-path slices (BESS-TS5-003, BESS-TS5-004) must prove payload
equivalence, so run it when they land:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Regression Guard

Every slice that changes backend persistence must keep the existing Python
suite green: scenario versions, structured drafts, hydraulic diagrams, manual
runs, TS-1 hierarchy provenance, TS-2 catalog, TS-3 variant and TS-4 result
indexing tests.

Slices changing React should run the relevant frontend unit tests, `tsc -b`
and `eslint .`.

Historical scenario versions, executed snapshots and registered artifacts are
immutable: no TS-5 migration, extraction, cleanup or constraint change may
rewrite or delete them. Extraction and migration always add new objects with
origin metadata; legacy reads must keep working through adapters or frozen
snapshots for as long as the compatibility window is open.

Cleanup may only remove derived data that is provably rebuildable from
artifacts through the existing rebuild path; it must never remove audit data.
