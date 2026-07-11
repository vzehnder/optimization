# BESS TS-6 Issue Tracker

This document is the local tracker for TS-6: declarative transformations and
automation on top of the common series model, derived from
`docs/series_tiempo/iter6/prd.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the
`ready-for-agent` triage label.

TS-6 is deliberately gated: the PRD defers it until real usage of the TS-2
through TS-5 model justifies it (user story 18). BESS-TS6-000 must close the
activation decision before any implementation issue starts.

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
| BESS-TS6-000 | Review TS-6 PRD And Transformation Semantics | HITL | ready-for-agent | Done | 2026-07-13 | 2026-07-13 | None | [BESS-TS6-000-review-ts6-prd-and-transformation-semantics.md](BESS-TS6-000-review-ts6-prd-and-transformation-semantics.md) |
| BESS-TS6-001 | Apply One Allowlisted Transformation End-To-End | AFK | ready-for-agent | Done | 2026-07-14 | 2026-07-17 | BESS-TS6-000 | [BESS-TS6-001-apply-one-allowlisted-transformation-end-to-end.md](BESS-TS6-001-apply-one-allowlisted-transformation-end-to-end.md) |
| BESS-TS6-002 | Resample A Series Set To An Optimization Resolution | AFK | ready-for-agent | Done | 2026-07-20 | 2026-07-21 | BESS-TS6-001 | [BESS-TS6-002-resample-a-series-set-to-an-optimization-resolution.md](BESS-TS6-002-resample-a-series-set-to-an-optimization-resolution.md) |
| BESS-TS6-003 | Interpolate Small Gaps Explicitly And Auditably | AFK | ready-for-agent | Done | 2026-07-22 | 2026-07-23 | BESS-TS6-001 | [BESS-TS6-003-interpolate-small-gaps-explicitly-and-auditably.md](BESS-TS6-003-interpolate-small-gaps-explicitly-and-auditably.md) |
| BESS-TS6-004 | Combine Series From Multiple Sets Into A Derived Set | AFK | ready-for-agent | Todo | 2026-07-24 | 2026-07-27 | BESS-TS6-001 | [BESS-TS6-004-combine-series-from-multiple-sets-into-a-derived-set.md](BESS-TS6-004-combine-series-from-multiple-sets-into-a-derived-set.md) |
| BESS-TS6-005 | Mark Derived Sets Stale And Regenerate Them | AFK | ready-for-agent | Todo | 2026-07-28 | 2026-07-29 | BESS-TS6-001 | [BESS-TS6-005-mark-derived-sets-stale-and-regenerate-them.md](BESS-TS6-005-mark-derived-sets-stale-and-regenerate-them.md) |
| BESS-TS6-006 | Ingest Forecast Data Through An Isolated External Connector | AFK | ready-for-agent | Todo | 2026-07-30 | 2026-08-03 | BESS-TS6-000 | [BESS-TS6-006-ingest-forecast-data-through-an-isolated-external-connector.md](BESS-TS6-006-ingest-forecast-data-through-an-isolated-external-connector.md) |
| BESS-TS6-007 | Store Issuer And Validity For Programmed External Data | AFK | ready-for-agent | Todo | 2026-08-04 | 2026-08-05 | BESS-TS6-006 | [BESS-TS6-007-store-issuer-and-validity-for-programmed-external-data.md](BESS-TS6-007-store-issuer-and-validity-for-programmed-external-data.md) |
| BESS-TS6-008 | Schedule Reruns Using Case, Variant And Date Range | AFK | ready-for-agent | Todo | 2026-08-06 | 2026-08-10 | BESS-TS6-000 | [BESS-TS6-008-schedule-reruns-using-case-variant-and-date-range.md](BESS-TS6-008-schedule-reruns-using-case-variant-and-date-range.md) |
| BESS-TS6-009 | Run Rolling-Horizon Automation With Auditable Snapshots | AFK | ready-for-agent | Todo | 2026-08-11 | 2026-08-12 | BESS-TS6-008 | [BESS-TS6-009-run-rolling-horizon-automation-with-auditable-snapshots.md](BESS-TS6-009-run-rolling-horizon-automation-with-auditable-snapshots.md) |
| BESS-TS6-010 | Finalize TS-6 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | 2026-08-13 | 2026-08-14 | BESS-TS6-001 through BESS-TS6-009 | [BESS-TS6-010-finalize-ts6-acceptance-suite-and-docs.md](BESS-TS6-010-finalize-ts6-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-TS6-000 closes the activation decision (start now versus keep
   deferring, per user story 18) and the transformation-semantics decision
   record (allowlist catalog, output model, lineage contract, derived
   staleness, connector target, scheduling mechanism and permissions).
2. BESS-TS6-001 is the transformation tracer bullet: `scale_signal` applied
   end-to-end — declarative parameters, versioned schema, allowlist
   enforcement, derived set with full lineage, catalog visibility and
   variant binding.
3. BESS-TS6-002 adds resampling to an optimization resolution, keeping
   run-time behavior strict (no implicit resampling).
4. BESS-TS6-003 adds explicit, auditable gap interpolation with a declared
   maximum gap.
5. BESS-TS6-004 adds the first multi-input transformation, composing a
   derived set from signals of several sets.
6. BESS-TS6-005 closes the derived-data lifecycle: stale marking on source
   changes and explicit regeneration, composed with the TS-3 fail-closed
   gates.
7. BESS-TS6-006 is the connector tracer bullet: external forecast data
   ingested through the common source/set model behind an isolated module.
8. BESS-TS6-007 adds issuer and validity metadata for official programmed
   data.
9. BESS-TS6-008 is the automation tracer bullet: scheduled reruns defined as
   case + parameter version + variant + range, reusing the manual pipeline
   including TS-4 result indexing.
10. BESS-TS6-009 extends scheduling with rolling-horizon range rules and
    per-tick auditable snapshots.
11. BESS-TS6-010 closes the iteration with the acceptance suite, the manual
    test checklist, the final architecture note and docs.

The three chains after BESS-TS6-000 (transformations 001-005, connectors
006-007, automation 008-009) are independent and can be reordered or
interleaved if priorities change.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-07-10 | All | Created | Initial local issue set generated from the TS-6 PRD (`docs/series_tiempo/iter6/prd.md`) and the series hierarchy roadmap. TS-6 remains gated on the activation decision (user story 18): BESS-TS6-000 must confirm real usage justifies starting before any implementation issue begins. |
| 2026-07-10 | BESS-TS6-000 | Todo -> Done | Activation decision accepted: start TS-6 now, per explicit product-owner instruction and measured real usage of the TS-2 through TS-5 model (41 projects, 21 runs, 32 catalog sets across 39 revisions, 23 input variants in `energy_dispatch`). Allowlist (`scale_signal`, `resample`, `interpolate_gaps`, `combine_signals`), output/lineage model (new set then same-set revisions, reusing `time_series_set_revisions.metadata_json` and `validation_dependencies`), derived-set staleness composition with TS-3, connector target (generic config-driven HTTP+JSON, no named vendor) and scheduling mechanism (data-defined schedules, externally invoked, admin-gated) all decided in `docs/series_tiempo/iter6/decision_record_ts6_transformation_semantics.md`. BESS-TS6-001 is unblocked. |
| 2026-07-10 | BESS-TS6-001 | Todo -> Done | Transformation tracer bullet shipped: allowlist registry `app/transformations.py` (`scale_signal`, impl v1, param schema v1), `AnalystStore.apply_time_series_transformation` (new `data_kind = "derived"` set on first run, lineage in `time_series_set_revisions.metadata_json` + `validation_dependencies`, recipe-hash convergence on re-run), `POST /api/projects/{project_id}/time-series-sets/{time_series_set_id}/transformations`, and a React "Transformaciones"/"Lineage de transformacion" panel pair on the catalog detail page. 18 new backend tests + full suite (423 passed, 2 skipped) + full frontend suite (tsc/eslint/vitest/api:check/build) all green. Chrome + live `energy_dispatch` verification: applied `scale_signal` (factor 2.0) to a seeded set in project 45 (`TS6-001 Chrome QA`), confirmed the derived set (`data_kind = derived`), doubled target signal, unchanged other signal, correct lineage panel, unchanged source content_hash, and both sets listed in the catalog. BESS-TS6-002 through BESS-TS6-005 (all blocked by BESS-TS6-001) are unblocked. |
| 2026-07-10 | BESS-TS6-002 | Todo -> Done | `resample` added as the second allowlisted transformation, reusing `AnalystStore.apply_time_series_transformation` unchanged (only a new `TransformationDefinition` in `app/transformations.py`, impl v1, param schema v1): parameters are `target_resolution_hours` plus a per-signal `mean`/`sum` method map; validation rejects non-positive/non-finite resolutions, missing/unknown signal_keys, unsupported methods, mixed-duration or non-contiguous source periods, upsampling and non-evenly-dividing target resolutions before any write. Physically-meaningless combinations are enforced via a new additive `resampling_methods` field on `TimeSeriesSignalDefinition` (`app/time_series_catalog.py`), defaulting every existing rate/intensive signal to `("mean",)` only. 15 new backend tests + full suite (438 passed, 2 skipped, up from 423) + full frontend suite (tsc/eslint/vitest 66 passed/api:check/build) all green. React "Transformaciones" panel gained a transformation-type selector and resample-specific fields (target resolution, per-signal method); the lineage panel's parameter renderer was fixed to `JSON.stringify` nested objects instead of `[object Object]`. Chrome + live `energy_dispatch` verification in project 46 (`TS6-002 Chrome QA`): resampled a seeded 24-period hourly set (id 37) to 2 hours via the UI, confirmed the derived set (id 38, 12 periods, correctly averaged values, e.g. 100/101 -> 100.5), correct lineage panel, unchanged source content_hash, and both sets listed in the catalog. The run-pipeline "resample, bind, run" loop (mismatched-resolution run fails with "horizon incompatible" / "no implicit resampling", then succeeds after resampling and rebinding) is proven end-to-end in `tests/test_ts6_002_resample_run_acceptance.py`. BESS-TS6-003 through BESS-TS6-005 remain unblocked (all were already gated only on BESS-TS6-001). |
| 2026-07-10 | BESS-TS6-003 | Todo -> Done | `interpolate_gaps` added as the third allowlisted transformation, again reusing `AnalystStore.apply_time_series_transformation` unchanged except one small additive extension: `TransformationOutput` gained an optional `execution_metadata` field (default `{}`), merged into the stored `metadata_json.transformation.execution` key only when non-empty, so scale_signal/resample's stored metadata is byte-for-byte unchanged. Parameters are `method` (only `"linear"` allowlisted this iteration) and `max_gap_hours`; validation requires a uniform source period resolution, walks consecutive periods for timestamp discontinuities, rejects any gap exceeding `max_gap_hours` naming the offending signal(s) and timestamp range, and rejects gaps not aligned to an integer multiple of the source resolution. Execution renumbers periods contiguously (matching the resample precedent), linearly interpolates every signal's value across each filled gap, and records the filled (renumbered) period indexes in `execution_metadata["filled_period_indexes"]`, which is fully derivable from the input content and validated parameters so it does not need to enter the recipe-hash convergence check. 6 new pure-module tests (`app/transformations.py`, no persistence/UI) + 5 new `AnalystStore` integration tests + 2 new API tests; full backend suite 451 passed, 2 skipped (up from 438) + full frontend suite (tsc/eslint/vitest 66 passed/api:check/build) all green. React "Transformaciones" panel gained the `interpolate_gaps` option with a `linear`-only method selector and a max-gap-hours field; the "Valores" table now marks any period listed in `execution.filled_period_indexes` with a highlighted row and an "interpolado" badge, satisfying the "distinguishable from observed values when browsing the set" acceptance criterion. Chrome + live `energy_dispatch` verification in project 47 (`TS6-003 Chrome QA`): imported a seeded 5-period hourly set with a 1-hour gap (set id 39; hour 3 missing), applied `interpolate_gaps` (`max_gap_hours=2.0`) via the UI, confirmed the derived set (id 40, 6 periods, correct linear interpolation 102/104 -> 103 and 52/54 -> 53), the highlighted/badged "interpolado" row, correct lineage panel (`max_gap_hours=2, method=linear`, input set 39 + hash), and the unchanged source set (still 5 periods, same content_hash, no badge). Also verified the failure path in the browser: requesting `max_gap_hours=0.5` against the same 1-hour gap renders the alert `gap from 2026-07-01T03:00:00-04:00 to 2026-07-01T04:00:00-04:00 (1.0 hours) exceeds max_gap_hours=0.5 for signal(s) ['import_price_usd_per_mwh', 'load_demand_mw']` and writes nothing. BESS-TS6-004 and BESS-TS6-005 remain unblocked (both were already gated only on BESS-TS6-001). |

## Final TS-6 Verification

Run before considering TS-6 closed:

```powershell
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

Julia regression is only required if a TS-6 slice changes artifact formats,
the generated `system_case_json` contract or optimizer behavior. Scheduled
and rolling-horizon runs (BESS-TS6-008, BESS-TS6-009) reuse the manual
pipeline, and transformed inputs must materialize through the existing
contract, so run it if any slice touches that boundary:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Regression Guard

Every slice that changes backend persistence must keep the existing Python
suite green: scenario versions, structured drafts, hydraulic diagrams, manual
runs, TS-1 hierarchy provenance, TS-2 catalog, TS-3 variants, TS-4 result
indexing and TS-5 migration/permission/retention tests.

Slices changing React should run the relevant frontend unit tests, `tsc -b`
and `eslint .`.

Transformations never mutate their source sets: they only add derived sets or
revisions with full lineage (inputs, revisions/hashes, validated parameters,
parameter schema version, implementation version). No arbitrary user-provided
script is ever stored in or executed from the database; only allowlisted,
versioned transformation types run.

Historical scenario versions, executed snapshots and registered artifacts
remain immutable: regeneration of derived data and scheduled automation must
never rewrite them. Runs keep pointing at the exact revisions/hashes they
consumed, before and after any regeneration.

Automation must not bypass the manual gates: scheduled and rolling-horizon
runs pass through the same staleness, coverage and permission checks as
manual runs, and no implicit resampling or gap filling ever happens at run
time.

Physical storage optimizations (partitioning, TimescaleDB) stay out of scope
unless a measured bottleneck at realistic volume justifies them.
