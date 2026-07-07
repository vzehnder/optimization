# TS-4 Result Semantics Decision Record

Fecha: 2026-07-07
Status: Accepted
Issue: `BESS-TS4-000`

## Context Reviewed

This decision was reviewed against:

- `docs/series_tiempo/iter4/prd.md` (TS-4 PRD and its Grill-Me answers);
- `docs/series_tiempo/roadmap_iteraciones_jerarquias_series.md` (TS-4
  roadmap position: run results in BBDD, artifact fallback, rebuild and
  comparison);
- `docs/series_tiempo/propuesta_manejo_series_tiempo.md` (the broader series
  mental model and the distinction between editable inputs and derived
  outputs);
- `docs/db/propuesta_bbdd_componentes_timeseries.md` (the generic catalog
  proposal and its `data_kind = simulated` alternative for outputs);
- `docs/series_tiempo/iter1/decision_record_ts1_hierarchy.md`
  (`ScenarioVersion` as the immutable executable snapshot and `runs` pointing
  to it);
- `docs/series_tiempo/iter2/decision_record_ts2_catalog_semantics.md`
  (`time_series_sets` as the editable input-series catalog with revisions and
  manual-edit semantics);
- `docs/series_tiempo/iter3/decision_record_ts3_variant_semantics.md`
  (run lineage already frozen into `scenario_versions.generation_metadata_json`
  for variant, range and input-series provenance);
- current code in `app/persistence.py`, `app/results.py`, `app/runner.py` and
  `app/main.py` (real artifact registration, result reading and run execution
  flow actually implemented before TS-4);
- current UI expectations in `/api/runs/{run_id}/results` and the React run
  results surface (dispatch table, asset dispatch table, summary and charts as
  separate surfaces, not one monolithic result blob).

## Accepted Decisions

1. A dedicated run-result indexing layer is **accepted** over reusing the
   generic TS-2 input catalog. TS-2's `time_series_sets` model is for
   editable, reusable input data with revisions, source files and user-driven
   curation. TS-4 result rows are derived from a successful run, owned by a
   specific `run`/`scenario_version`, and must preserve the exact artifact row
   shape used by the existing run-results UI. Mixing both concepts in one
   catalog would blur lifecycle, lineage and permissions. The accepted TS-4
   shape is a dedicated persistence path rooted at the run.
2. The first indexed scope is **narrow by design**. TS4-001 only indexes the
   core `dispatch.csv` fields needed to serve the existing run results table
   for the grid-plus-BESS tracer bullet: `timestamp`, `duration_hours`,
   prices, `market_value_usd`, grid import/export, and BESS
   charge/discharge/energy. The full original dispatch row is also preserved
   alongside those typed fields so the current table contract can be served
   without a React rewrite. `asset_dispatch.csv`, `summary.json`, broader
   signal families and charts remain follow-on issues inside TS-4.
3. Result indexing writes **after run success and after artifact
   registration**. Artifacts remain the durable audit trail and rebuild
   source. Indexing adds a second, queryable trail; it never replaces or
   precedes artifact registration.
4. The read policy is **BBDD-first per surface, with artifact fallback**.
   When an indexed surface exists for a run, endpoints should serve it from
   BBDD; when it does not, the existing artifact read path remains the source
   of truth. In the tracer bullet this applies to the run results dispatch
   table only; summary, asset dispatch and charts still read artifacts.
5. Full result lineage is **accepted as a TS-4 requirement**, but phased. The
   target lineage set is run, executable snapshot (`scenario_version`), case,
   topology hash, parameter hash, input variant, date range and input series
   hashes copied from the frozen run snapshot, never re-derived from mutable
   live state. TS4-001 only needs the minimal run/snapshot linkage to land the
   tracer bullet; TS4-005 hardens the full lineage contract.
6. Idempotent, replace-whole-run indexing is **accepted**. Re-indexing the
   same run must converge without duplicate rows. TS4-001 establishes the
   replace-on-write pattern for one run's dispatch rows; TS4-006 hardens
   retries, partial-failure recovery and operational visibility.
7. Comparison scope is **accepted** as "two runs of the same case, KPI diffs
   plus period-level diffs for selected result series". This is intentionally
   narrower than general BI or cross-case analytics.
8. The out-of-scope list is **confirmed**: no artifact removal, no output
   reuse as inputs yet, no resampling or transformations, no full BI / multi-
   run analytics, and no performance partitioning beyond reasonable indexes in
   this iteration.

## PRD Corrections

`docs/series_tiempo/iter4/prd.md` needs two corrections before downstream TS-4
implementation proceeds:

1. The implementation decision "reuse `time_series_sets` with
   `data_kind = simulated`" is **rejected** for TS-4. The accepted model is a
   dedicated run-result layer rooted at the run, not the editable TS-2
   catalog.
2. "The first indexed scope covers core dispatch, asset dispatch and summary
   KPIs used by existing UI" is **too broad for the tracer bullet**. The
   accepted first slice is core dispatch only for the run results table; asset
   dispatch rows and summary KPIs remain separate downstream issues.

## Acceptance Mapping

- Storage model decision: accepted as a dedicated run-result layer, not TS-2
  catalog reuse (Decision 1).
- Initial indexed scope: agreed as core `dispatch.csv` table fields for the
  tracer bullet, with broader scopes deferred (Decision 2).
- Exact lineage fields: agreed as the full frozen run lineage set for TS-4,
  with minimal run/snapshot linkage acceptable in TS4-001 and full hardening
  deferred to TS4-005 (Decision 5).
- Write timing: accepted as post-success and post-artifact-registration
  (Decision 3).
- Idempotency requirement: accepted (Decision 6).
- Read policy: accepted as BBDD-first per surface with artifact fallback
  (Decision 4).
- Comparison scope: accepted (Decision 7).
- Out-of-scope list: confirmed (Decision 8).
- PRD correction before implementation: completed via the corrections above.

## Verification

- Confirmed in `app/results.py` and `app/main.py` that the current UI already
  consumes separate result surfaces (`dispatch_table`, `asset_dispatch_table`,
  `summary`, `charts`), supporting the accepted "per-surface BBDD-first"
  decision rather than an all-or-nothing migration.
- Confirmed in `app/runner.py` that artifacts are registered as part of the
  successful-run path before TS-4 indexing hooks in, grounding the
  post-registration write timing in real code.
- Confirmed in `app/persistence.py` and the TS-2 decision record that
  `time_series_sets` is an editable input catalog with revisions and manual
  replacement semantics, which is materially different from run-owned derived
  results and supports rejecting catalog reuse for TS-4.
- Confirmed in the TS-1 and TS-3 decision records that the frozen execution
  snapshot and input lineage already live around `scenario_versions` /
  `generation_metadata_json`, grounding the accepted result-lineage target in
  existing run semantics rather than a new ad hoc concept.

## Blocked by

None - can start immediately.
