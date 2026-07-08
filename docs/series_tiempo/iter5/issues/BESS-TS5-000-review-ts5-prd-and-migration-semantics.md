# BESS-TS5-000: Review TS-5 PRD And Migration Semantics

Status: Done
Type: HITL
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-09
Fecha de termino planificada: 2026-07-09
Fecha de inicio real: 2026-07-08
Fecha de termino real: 2026-07-08

## User stories covered

1 through 17

## What to build

Review and accept the TS-5 PRD before implementation starts. TS-5 consolidates
the architecture built in TS-1 through TS-4: after it, new time-series writes
and new result writes must use the common model, legacy paths must have clear
adapters or migration routes, and the UI must stop mixing concepts.

The review must close a per-path strategy (migrate, adapt with read adapters,
freeze as read-only legacy, or rebuild on demand) for every place temporal
data lives today: series embedded in structured scenario drafts, CSV/XLSX
sources of the structured editor, the hydraulic-specific series tables used by
the hydro diagram editor, historical scenario versions with materialized
`system_case_json`, and old runs whose results only exist as artifacts.

It must also close the decisions the PRD leaves open: the future role of
`ScenarioDraft` (compatibility surface, reduced role or deprecation path,
without forcing removal), the `Scenario -> OptimizationCase` cardinality
question explicitly deferred from TS-1 to TS-5 (whose implementation lands in
BESS-TS5-006), the hydraulic series write strategy and its compatibility
window, the permission matrix for sources, input series, result series and
published outputs across analyst, admin and client roles, and the retention
boundary between immutable audit data and rebuildable derived data.

The outcome should be a short accepted-decision record in the iteration docs
at `docs/series_tiempo/iter5/decision_record_ts5_migration_semantics.md`,
including any corrections to the PRD if scope, strategies or boundaries need
adjustment before downstream issues begin.

## Acceptance criteria

- [x] A per-path strategy (migrate, adapt, freeze read-only or rebuild on demand) is decided and recorded for draft-embedded series, structured-editor sources, hydraulic-specific series tables, historical scenario versions and artifact-only results.
- [x] Historical scenario versions and executed snapshots are confirmed as never rewritten; any extraction into the new model records origin metadata.
- [x] The future role of `ScenarioDraft` is decided (compatibility, reduced role or deprecation path) without forcing its removal.
- [x] The `Scenario -> OptimizationCase` cardinality decision deferred from TS-1 is closed, including what BESS-TS5-006 must implement.
- [x] The hydraulic series write strategy (generic-model writes with adapter reads, dual write or on-demand migration) and its compatibility window are decided.
- [x] The permission matrix for sources, input series, result series and published outputs across analyst, admin and client roles is agreed.
- [x] Retention boundaries distinguishing immutable audit data from rebuildable derived data are agreed.
- [x] The architecture-closure criteria (new writes to the common model, adapters for legacy reads, UI no longer mixing concepts) are agreed as the TS-5 definition of done.
- [x] Any PRD correction is committed before downstream TS-5 implementation issues begin.

## Resolution

Accepted the TS-5 migration semantics in
`docs/series_tiempo/iter5/decision_record_ts5_migration_semantics.md`.

The review confirms:

1. Per-path strategy: extract-on-demand for draft-embedded/structured-editor
   series (BESS-TS5-001); adapt-then-migrate-on-demand for hydraulic series
   (BESS-TS5-002/003/004); historical `scenario_versions` stay frozen
   read-only legacy (already DB-trigger immutable); artifact-only old runs
   rebuild on demand via the existing TS4-008 rebuild path (BESS-TS5-009).
2. Historical scenario versions and runs are never rewritten by any TS-5
   extraction or migration; new objects always carry origin metadata.
3. `ScenarioDraft` stays a live compatibility/authoring surface (confirmed
   still routed in `frontend/src/DraftEditor.tsx`), not forced into removal;
   BESS-TS5-007 labels it as the legacy-origin path relative to the catalog.
4. `Scenario -> OptimizationCase` cardinality stays one-to-one. No TS-1
   through TS-4 issue surfaced a concrete need for multiple cases per
   scenario, and series/topology/parameter sensitivities already have working
   homes (`case_input_variants`, or a new `Scenario`). BESS-TS5-006
   implements the "confirmed, unambiguous" branch, not a schema migration.
5. Hydraulic write strategy: generic-model writes with adapter reads, no dual
   write; the compatibility window is open-ended and closes per-project,
   opportunistically, not on a TS-5-imposed deadline.
6. Permission matrix: formalizes the existing internal/client split (analyst
   and admin see all projects' sources/series/results; clients see only
   published outputs via the four existing `/api/client/...` routes).
   BESS-TS5-008's job is enforcement consistency for new TS-5 surfaces, not a
   new access model.
7. Retention boundary: rebuildable = the TS-4 result-index tables (regenerable
   via `rebuild_run_results`/`rebuild_all_run_results`); everything else
   (`scenario_versions`, `runs`, `run_artifacts`, `time_series_sources`,
   revision history, unmigrated legacy hydraulic rows) is immutable audit
   data.
8. Architecture-closure criteria for TS-5 are agreed as listed in the
   decision record's Decision 8.

No PRD text correction was required; the PRD's open per-path questions are
answered by the decision record instead.

## Verification

- Added `docs/series_tiempo/iter5/decision_record_ts5_migration_semantics.md`
  capturing the per-path strategy, `ScenarioDraft` role, cardinality outcome,
  hydraulic write strategy, permission matrix, retention boundary and
  architecture-closure criteria.
- Re-checked `app/persistence.py` for the real schema of
  `scenario_drafts`, `optimization_cases`, `hydraulic_time_series_sets`/
  `..._points`, `time_series_sets`, `case_input_variants`,
  `validation_dependencies`, `scenario_versions` and the TS-4 result-index
  tables, so every decision is grounded in what is actually implemented
  rather than the roadmap's simplified diagrams.
- Re-checked `app/draft_editor.py` and `frontend/src/DraftEditor.tsx` to
  confirm the structured draft path is live code and a live route today.
- Re-checked `app/auth.py` and the middleware gate plus route list in
  `app/main.py`, and `project_client_access` in `app/persistence.py`, to
  ground the accepted permission matrix in what is structurally enforced
  today.
- Re-checked `app/result_indexing.py` (`rebuild_run_results`,
  `rebuild_all_run_results`) and `app/result_comparison.py` (no persisted
  comparison cache) to ground the retention boundary.
- Cross-read draft issues `BESS-TS5-001` through `BESS-TS5-011` to confirm
  this record actually closes what each downstream issue expects to consume,
  with no rewrite needed to any of them.

## Blocked by

None - can start immediately.
