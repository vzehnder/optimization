# TS-5 Final Architecture: The Common Topology/Parameters/Series/Results Model

Fecha: 2026-07-10
Status: Accepted, closes TS-5
Issue: `BESS-TS5-011`
Supersedes nothing; formalizes `docs/series_tiempo/iter5/decision_record_ts5_migration_semantics.md`
as the settled reference so future PRDs (starting with TS-6) do not reopen
these decisions.

## Purpose

TS-1 through TS-4 built the common model: topology/parameter provenance
(TS-1), a generic time-series catalog (TS-2), case input variants with
stale-fail-closed validation (TS-3), and indexed, comparable run results
(TS-4). TS-5 closed the gap between that new architecture and everything
that predates it: draft-embedded series, hydraulic-specific tables, historical
scenario versions and artifact-only runs. This document is the settled
picture of the result — the one future iterations should build on without
re-litigating.

## The Common Model, End To End

```text
ScenarioDraft (authoring surface, one-bus, legacy-origin)
  -> extract on demand -------------------+
                                          v
HydraulicTimeSeriesSet (legacy, adapter-read)   TimeSeriesSet (generic catalog)
  -> read adapter (no row migration)             ^        |
  -> migrate on demand ---------------------------+        |
                                                            v
                                          CaseInputVariant + CaseTimeSeriesBinding
                                                            |
                                                            v
                                          materialize_system_case_for_variant
                                          (fail-closed staleness gate)
                                                            |
                                                            v
                                          Run -> scenario_versions (frozen,
                                                 immutable, DB-trigger enforced)
                                                            |
                                                            v
                                          Run result indexes (rebuildable from
                                          run_artifacts; artifact-fallback read)
```

One case per scenario (`optimization_cases.scenario_id UNIQUE`,
`scenario_drafts.scenario_id UNIQUE`) throughout; alternatives live as
`case_input_variants` under that one case (TS-3), or as a new `Scenario` when
the difference is topology/parameters rather than input series.

## Per-Path Strategy (Accepted, Closed)

| Legacy path | Strategy | Landed in |
| --- | --- | --- |
| Series embedded in `scenario_drafts.document_json` | Extract on demand into the generic catalog, with origin metadata (draft id, source filename/checksum, extracted-by/at). Draft never rewritten. Idempotent re-extraction. | BESS-TS5-001 |
| `hydraulic_time_series_sets` / `..._points` | Read adapter over common catalog semantics (no row migration); new writes route to the generic model; existing sets migrate on demand, never automatically. | BESS-TS5-002/003/004 |
| `scenario_versions.system_case_json` | Frozen, read-only, permanently. Already DB-trigger immutable (`scenario_versions_immutable`). Never decomposed into catalog rows. | Enforced since before TS-5 |
| Runs with artifacts but no BBDD result index | Rebuild on demand via `rebuild_run_results` / `rebuild_all_run_results`; never a forced backfill. Artifact-fallback read keeps them viewable either way. | BESS-TS5-009 (retention loop) |

No path is migrated by default; every path is either adapted, extracted on
demand, migrated on demand, or frozen — matching the PRD's explicit rejection
of "full automatic migration of every historical artifact."

## Adapters And Deprecation Paths

- **`ScenarioDraft` / structured editor**: permanent compatibility and
  authoring surface, not a forced removal. Labeled in the UI (BESS-TS5-007)
  as the legacy-origin path, with "Extract legacy series to catalog" as the
  steer toward the common model. A full UX replacement is future work only,
  gated on usage data.
- **Hydraulic-specific tables**: read through `app/hydraulic_time_series_adapter.py`
  (`build_hydraulic_catalog_summary` / `build_hydraulic_catalog_detail`),
  tagged `origin: {"kind": "hydraulic_legacy"}`. New writes carry
  `origin: {"kind": "generic"}`. Migrated sets carry
  `origin: {"kind": "hydraulic_legacy_migration", ...}` pointing back at the
  legacy set id, version and content hash. The compatibility window for
  per-project, per-set migration is open-ended — closed opportunistically by
  an analyst or admin, never on a schedule TS-5 imposes.
- **Historical scenario versions**: frozen read-only forever; no adapter
  needed because they are already self-contained, reproducible snapshots.

## `Scenario -> OptimizationCase` Cardinality: Confirmed One-To-One

TS-5 confirmed (did not migrate) the one-case-per-scenario constraint.
`case_input_variants` (TS-3) already solves "alternatives without duplicating
structure" for input-series sensitivities; a materially different
topology/parameter set gets a new `Scenario`. BESS-TS5-006 removed residual
UI ambiguity (`scenario_versions.case_name` relabeled "Nombre del caso") so
the product states this outright instead of implying hidden multiplicity.
Revisiting this is possible later, but only if real usage surfaces concrete
friction — none did across TS-1 through TS-4.

## Permission Matrix (Accepted, Enforced)

| Data | Analyst | Admin | Client |
| --- | --- | --- | --- |
| Sources, input series (catalog, adapter-read hydraulic, extracted sets, variants) | Read/write, all projects | Read/write, all projects | Never |
| Result series (indexes, artifacts) | Read, all projects | Read, all projects | Never directly; only via a published publication's `allowed_artifact_types` |
| Published outputs | Read | Read | Read, only `project_client_access` projects, only `status = 'published'` |
| User/access management, retention & cleanup, bulk migration sweeps | No | Yes | No |

Enforced by a single shared gate (`require_authenticated_app_boundary` in
`app/main.py`), so a future route cannot bypass it by construction. BESS-TS5-008
is the closing proof this holds across every TS-5 surface, not a new access
model.

## Retention Boundary (Accepted, Enforced)

Immutable audit data: `scenario_versions`, `runs`, `run_artifacts`,
`time_series_sources`, `time_series_set_revisions`, and unmigrated legacy
hydraulic rows (they are the only surviving record until migrated).
Rebuildable derived data: exactly the TS-4 result-index tables
(`run_dispatch_result_indexes`/`_rows`, `run_asset_dispatch_result_indexes`/`_rows`,
`run_summary_result_indexes`) — `app/result_retention.py`
(`cleanup_run_result_data` / `cleanup_project_result_data`) removes only
these, refuses everything else with a stable `kept` reason, and every removal
is provably restorable through `rebuild_run_results` / `rebuild_all_run_results`.

## Architecture-Closure Criteria (TS-5 Definition Of Done)

All six criteria from the accepted decision record are closed:

1. New time-series and result writes go through the common model
   (hydraulic since BESS-TS5-003; generic series since TS-2; results since TS-4).
2. Every legacy read path has a working adapter or is frozen read-only
   (hydraulic since BESS-TS5-002; scenario versions already frozen).
3. The UI no longer mixes concepts (BESS-TS5-006, BESS-TS5-007).
4. Stale validation, audit and permissions hold across every storage origin
   (BESS-TS5-005, BESS-TS5-008).
5. Rebuildable derived data can be cleaned and restored without touching
   audit data (BESS-TS5-009).
6. Real TS-2 through TS-4 query patterns are indexed, not speculative ones
   (BESS-TS5-010).

`tests/test_ts5_acceptance.py` is the executable proof tying all six
together in one coexisting story: extraction binds to a variant and
materializes; the hydraulic adapter and generic writes coexist and read
correctly; on-demand migration is idempotent and leaves the legacy row and
its bindings untouched; stale validation fails closed for both an extracted
and a migrated series binding; the permission matrix holds for analyst, admin
and client; cleanup removes only rebuildable indexes and rebuild restores
them while artifact fallback keeps old runs readable throughout; and a
historical scenario version's row-level immutability is enforced at the
database level.

## What TS-6 Inherits

Any future transformation, automation or connector work (TS-6) builds on
this model as fixed ground: series live in `time_series_sets` (or behind the
hydraulic adapter during its open compatibility window), variants bind by
reference, cases stay one-per-scenario, results are BBDD-indexed with
artifact fallback, and the permission/retention boundaries above are not
renegotiated by later PRDs.
