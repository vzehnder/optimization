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
| BESS-TS6-004 | Combine Series From Multiple Sets Into A Derived Set | AFK | ready-for-agent | Done | 2026-07-24 | 2026-07-27 | BESS-TS6-001 | [BESS-TS6-004-combine-series-from-multiple-sets-into-a-derived-set.md](BESS-TS6-004-combine-series-from-multiple-sets-into-a-derived-set.md) |
| BESS-TS6-005 | Mark Derived Sets Stale And Regenerate Them | AFK | ready-for-agent | Done | 2026-07-28 | 2026-07-29 | BESS-TS6-001 | [BESS-TS6-005-mark-derived-sets-stale-and-regenerate-them.md](BESS-TS6-005-mark-derived-sets-stale-and-regenerate-them.md) |
| BESS-TS6-006 | Ingest Forecast Data Through An Isolated External Connector | AFK | ready-for-agent | Done | 2026-07-30 | 2026-08-03 | BESS-TS6-000 | [BESS-TS6-006-ingest-forecast-data-through-an-isolated-external-connector.md](BESS-TS6-006-ingest-forecast-data-through-an-isolated-external-connector.md) |
| BESS-TS6-007 | Store Issuer And Validity For Programmed External Data | AFK | ready-for-agent | Done | 2026-08-04 | 2026-08-05 | BESS-TS6-006 | [BESS-TS6-007-store-issuer-and-validity-for-programmed-external-data.md](BESS-TS6-007-store-issuer-and-validity-for-programmed-external-data.md) |
| BESS-TS6-008 | Schedule Reruns Using Case, Variant And Date Range | AFK | ready-for-agent | Done | 2026-08-06 | 2026-08-10 | BESS-TS6-000 | [BESS-TS6-008-schedule-reruns-using-case-variant-and-date-range.md](BESS-TS6-008-schedule-reruns-using-case-variant-and-date-range.md) |
| BESS-TS6-009 | Run Rolling-Horizon Automation With Auditable Snapshots | AFK | ready-for-agent | Done | 2026-08-11 | 2026-08-12 | BESS-TS6-008 | [BESS-TS6-009-run-rolling-horizon-automation-with-auditable-snapshots.md](BESS-TS6-009-run-rolling-horizon-automation-with-auditable-snapshots.md) |
| BESS-TS6-010 | Finalize TS-6 Acceptance Suite And Docs | AFK | ready-for-agent | Done | 2026-08-13 | 2026-08-14 | BESS-TS6-001 through BESS-TS6-009 | [BESS-TS6-010-finalize-ts6-acceptance-suite-and-docs.md](BESS-TS6-010-finalize-ts6-acceptance-suite-and-docs.md) |

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
| 2026-07-10 | BESS-TS6-004 | Todo -> Done | `combine_signals` added as the fourth allowlisted transformation and the first multi-input one: `TransformationDefinition` gained an additive `multi_input: bool = False` field, and `combine_signals`'s `validate_parameters`/`execute` operate on `list[TransformationInputSet]` (parameters: `inputs: [{time_series_set_id, signal_keys}, ...]`, at least two). Validation rejects fewer than two inputs, an unknown or duplicate-claimed `signal_key`, mismatched resolutions and non-overlapping/misaligned horizons, each naming the offending input set id, via a shared `_combined_period_grid` helper reused by execution. The existing `apply_time_series_transformation` derived-set-writing logic was extracted into a private `_write_derived_time_series_set` helper (pure refactor, confirmed behavior-identical by the unchanged existing test suite) and reused by the new multi-input `AnalystStore.apply_time_series_combination`. A new project-scoped `POST /api/projects/{project_id}/time-series-transformations` endpoint exposes it (no single "owning" set in the URL, unlike the set-scoped endpoint). 7 new pure-module tests + 7 new persistence tests + 3 new API tests; full backend suite 468 passed, 2 skipped (up from 451) + full frontend suite (tsc/eslint/vitest 66 passed/api:check/build) all green. React gained a "Combinar series" panel on the project catalog page (repeatable, addable/removable input rows, each picking a set then its signals via checkboxes); the existing TS6-001 lineage panel rendered the length-2 `inputs` array with no changes needed, confirming it was already generic over transformation arity. Chrome + live `energy_dispatch` verification in project 48 (`TS6-004 Chrome QA`): imported two single-signal sets (`price_only` id 41, `demand_only` id 42), combined them via the UI into derived set id 43 (`data_kind = derived`, both signals present with correct values matching the sources, unchanged source content_hashes), and verified the failure path with a third non-overlapping-horizon set (`future_price` id 44): the alert `input sets [41, 44] do not share an overlapping horizon` rendered and nothing was written. Fixed a duplicate-id/merged-label accessibility bug found live in the new panel (both empty rows shared `id="combination-input-set-new"`) by keying the id on row index. BESS-TS6-005 remains unblocked (already gated only on BESS-TS6-001). |

| 2026-07-11 | BESS-TS6-005 | Todo -> Done | Derived-data lifecycle closed with the two-layer staleness model from Decision 6 of the decision record. Layer 1: `AnalystStore.evaluate_time_series_set_staleness` reuses `evaluate_variant_staleness` as-is with `owner_type = 'time_series_set'`, comparing the recorded `validation_dependencies` (input set hashes + `transformation_implementation` version) against current state; `list_time_series_sets` gained a batch-computed `stale` flag (`_derived_staleness_flags`, no per-set N+1). Regeneration: `AnalystStore.regenerate_derived_time_series_set` re-validates and re-executes the stored recipe (single- and multi-input, including `combine_signals`) against current input revisions, writing a new revision of the same set (never a new set, per Decision 4) with `superseded_revision_number`, refreshed lineage metadata and refreshed dependencies; it converges to a no-op when the recipe hash is unchanged, and mid-write failures restore the snapshotted rows and prior dependency records. History immutable: revision 1 keeps its content_hash after regeneration. Layer 2: `_current_case_input_variant_dependencies` propagates a `time_series_set_derived_staleness` current-dependency for validated variants, and `_resolve_variant_series_for_range` fail-closes both materialization of never-validated variants AND `validate_case_input_variant` revalidation while any bound derived set is Layer-1 stale (revalidating against stale derived data would silently clear the gate otherwise). Bumping a registry `implementation_version` marks outputs stale (proven with a patched registry). API: detail GET now returns `staleness`, list returns `stale`, new `POST .../time-series-sets/{id}/regenerate` (400 on non-derived, 404 unknown); OpenAPI schema regenerated. React: "Desactualizado" badge in the catalog list and a stale banner + "Regenerar set derivado" button on the detail page. 22 new backend tests (`tests/test_ts6_005_derived_staleness.py`); full suite 490 passed, 2 skipped (up from 468) + full frontend suite (tsc/eslint/vitest 66 passed/api:check/build) green. Julia regression not required: no artifact, `system_case_json` or optimizer change (gates run before materialization; the materialization contract is untouched). Chrome + live `energy_dispatch` verification in project 49 (`TS6-005 Chrome QA`): seeded source set 45 + scale_signal-derived set 46 (factor 2.0), edited hour-0 demand 100 -> 150 via the UI (source revision 2), confirmed the "Desactualizado" badge in the catalog and the stale banner with reason "time-series set 45 changed since last validation" on the detail page, clicked "Regenerar set derivado" and confirmed derived revision 2 (hour-0 demand 300 = 150 x 2, other periods and price signal unchanged), lineage updated to source revision 2 + new hash, revision 1 preserved byte-identical in the history, and badge/banner cleared; no console errors. BESS-TS6-006 (connector chain) is the next open issue. |

| 2026-07-11 | BESS-TS6-006 | Todo -> Done | Connector tracer bullet shipped per Decision 7: new isolated module `app/forecast_connector.py` (narrow `ForecastConnector` protocol with `fetch() -> ForecastPayload`; one concrete config-driven `HttpJsonForecastConnector` doing an httpx GET with optional Bearer token and optional dot-path `records_path` extraction, checksumming rows canonically as `sha256:` over sorted JSON). Ingestion lands through the common source/set path: new `AnalystStore.ingest_connector_time_series_set` reuses the TS-2 pipeline end-to-end — `prepare_time_series_catalog_import` validates rows exactly like a CSV (the create path was extracted verbatim into `_create_time_series_catalog_set`, now shared by `import_time_series_catalog_set`, pure refactor), first ingestion creates a `data_kind = "forecast"`, `status = validated` set with a `kind = 'connector'` source row carrying `{connector_id, target, fetched_at, record_count}` in the existing `metadata_json`; unchanged re-ingest converges (same payload checksum -> same source_key -> same content_hash -> no new source/revision rows, outcome `converged`); changed data advances one revision via the existing `replace_time_series_set_source` (change summary `Re-ingested from connector at <fetched_at>`, outcome `new_revision`); taking over a set created from a file is refused. Sources gained metadata persistence (`_get_or_create_time_series_source_record` stores `source["metadata"]`) and exposure (`_time_series_source_public_dict` returns `metadata`), both additive. API: `POST /api/projects/{project_id}/time-series-sets/connector-ingest` (forces `data_kind = "forecast"`, 400 with `connector_fetch` context on fetch errors, 400 `connector_ingestion`/`python_validation` on TS-2 rejections, 404 unknown project); `create_app` gained an injectable `forecast_connector_factory` so API tests stub the connector — core series logic never sees the external API's shape. 17 new tests in `tests/test_ts6_006_connector_ingestion.py` (6 pure connector with `httpx.MockTransport`, 6 store incl. bindability of the ingested set in a default variant, 5 API with a stub factory; zero network access); full backend suite 507 passed, 2 skipped (up from 490) + full frontend suite (tsc/eslint/vitest 66 passed/api:check/build) green. React: "Ingesta de pronostico (conector externo)" panel on the project catalog page (URL, records path, optional token, set/version/timezone/columns, repeatable signal mappings, outcome message distinguishing created/converged/new-revision) and the set detail "Origen" section now renders connector origin (connector id, target, fetch time, record count). Chrome + live `energy_dispatch` verification in project 50 (`TS6-006 Chrome QA`) against a local fake JSON API (`http://127.0.0.1:8766/forecast.json`, nested `data.records`): ingested 24 hourly periods x 2 signals as validated forecast set 47 (source kind connector, correct origin panel and values), re-ingested unchanged ("Datos sin cambios", still revision 1, no duplicate source row in BBDD), changed hour-0 demand 100 -> 150 in the fake API and re-ingested ("Datos cambiados", revision 2 with new hash, revision 1 preserved, origin panel shows the new fetch), and exercised the failure path (404 URL renders alert `connector 'http_json_forecast' received HTTP 404 ...`, nothing written). Only console entry was the expected 400 from the failure test. BESS-TS6-007 (issuer/validity for programmed data) is unblocked; BESS-TS6-008 (automation chain) remains open. |

| 2026-07-11 | BESS-TS6-007 | Todo -> Done | Issuer/validity metadata shipped for programmed external data, extending the TS6-006 connector path (English `programmed` key per the decision record's PRD correction; issuer and validity are metadata, not a new model). New pure validator `validate_program_metadata` in `app/time_series_catalog.py` (required `issuer`, ISO-8601-with-offset `issued_at`/`valid_from`/`valid_until`, `valid_from < valid_until`, unknown fields rejected). `AnalystStore.ingest_connector_time_series_set` gained an optional `program` dict: required when `data_kind = "programmed"`, rejected for any other data_kind, validated before any write, and stored per revision in the existing `time_series_set_revisions.metadata_json` under `program` (plumbed via a new additive `extra_revision_metadata` parameter on `_create_time_series_catalog_set`/`_insert_time_series_catalog_children`/`replace_time_series_set_source`; non-program callers byte-identical). Reissue semantics: convergence now requires BOTH unchanged content_hash AND unchanged program metadata — a reissue with identical values but new issuer/validity lands as a new revision (change summary `Program re-issued via connector at <fetched_at>`), never an overwrite, so revision 1 keeps its original program metadata and a run's recorded content_hash maps to the exact revision (and program version) it consumed. Catalog surfaces: `list_time_series_sets` returns a batch-parsed `program` per set (latest revision), `get_time_series_set` already exposed it via `revision_metadata`, and `list_time_series_set_revisions` now returns `program` per revision. API: `TimeSeriesConnectorIngestionRequest` gained optional `program` (issuer/issued_at/valid_from/valid_until); the connector-ingest endpoint forces `data_kind = "programmed"` when present (still `forecast` otherwise, unchanged), echoes `program` in the ingestion summary, and returns 400 `connector_ingestion` on invalid metadata with nothing written; OpenAPI schema regenerated. React: connector panel gained a "Programa oficial (data_kind programmed)" checkbox revealing emisor/emision/vigencia fields (submit gated on all four), catalog list rows and the set detail page show a "Programa oficial" line/section, and the revision history renders each revision's own issuer/validity. 21 new tests in `tests/test_ts6_007_program_metadata.py` (6 pure validator, 9 store incl. reissue-with-identical-values, run-hash-to-program traceability and variant staleness unchanged after reissue, 4 API with a stub connector, plus 2 guard tests; zero network access); full backend suite 528 passed, 2 skipped (up from 507) + full frontend suite (tsc/eslint/vitest 66 passed/api:check/build) green. Julia regression not required: no artifact, `system_case_json` or optimizer change. Chrome + live `energy_dispatch` verification in project 51 (`TS6-007 Chrome QA`) against a local fake JSON API: ingested 6 hourly periods x 2 signals as programmed set 48 with issuer `Coordinador Electrico Nacional` (catalog line, detail section and history all correct), reissued with identical values but new issued_at/valid_until ("Datos cambiados", revision 2, SAME content_hash, both program versions preserved in history), and exercised the failure path (`issued_at 'not-a-date'` renders alert `program metadata: issued_at 'not-a-date' must be ISO-8601`, set stays at revision 2). Only console entry was the expected 400. BESS-TS6-008 (automation chain) is the next open issue. |

| 2026-07-11 | BESS-TS6-008 | Todo -> Done | Fixed-range schedule automation shipped. New deep module `app/schedules.py` plans due schedules, advances cadence from due time, and executes schedules through the same variant materialization, validation, immutable scenario-version, run queue and TS-4 indexing path as manual runs. New `run_schedules` and `run_schedule_ticks` tables store declarative case/variant/range/cadence schedules plus fired tick status/error/run metadata; failed gates are visible and keep the schedule active. Admin-only API/UI now creates, lists and runs due schedules; `scripts/run_due_schedules.py` provides the one-shot external trigger. 7 new backend tests in `tests/test_ts6_008_schedules.py` cover planning, persistence, happy execution, gate failure, admin API and permissions; full backend suite 535 passed, 2 skipped; frontend suite/build/type/api checks green. Chrome DevTools + `chrome:control-chrome` live verification in `energy_dispatch`: created schedules through the admin UI, ran a due schedule with invalid data and saw visible failed tick, then seeded a valid due schedule (`scenario 59`, `variant 27`) and confirmed `run-due` returned `due_count=1`, `tick queued`, `run 29`, schedule advanced to `2026-07-12T09:00:00+00:00`, no console errors, and run 29 finished `succeeded`. BESS-TS6-009 is unblocked. |
| 2026-07-11 | BESS-TS6-009 | Todo -> Done | Rolling-horizon automation shipped on top of the BESS-TS6-008 schedule path. `app/schedules.py` now has pure `resolve_schedule_range` support for `range_mode = fixed|rolling`; rolling rules use `rolling_start_offset_hours` and `rolling_duration_hours` anchored on each tick's `due_at`. `run_schedules` persists the range rule with fixed-schedule defaults, each tick stores the concrete resolved range, scenario-version metadata records the exact range plus schedule/tick lineage, and run detail surfaces the schedule name/id and tick id. Admin API and React can create rolling schedules, show the rule, list every tick history row, and preserve failures visibly while keeping the schedule active. New/updated backend tests cover pure range resolution, persistence, per-tick recomputation, API creation and permissions; React tests cover rolling form/list history and run-lineage display. Full backend suite green (539 tests, 2 skipped); frontend vitest (66), tsc, eslint, api:generate/api:check and build all green. Chrome DevTools MCP + `chrome:control-chrome` live verification in `energy_dispatch`: created `TS6-009 Rolling Chrome schedule` (scenario 61, variant 29), first tick produced run 30 for `2026-07-11` to `2026-07-12`, run 30 succeeded with artifacts and TS-4 indexes, second rolling tick failed visibly for missing `2026-07-12` coverage, the schedule stayed active and advanced to `2026-07-13T00:00:00-04:00`, and console errors were empty. BESS-TS6-010 is the next open issue. |

| 2026-07-11 | BESS-TS6-010 | Todo -> Done | TS-6 closed with proof and docs; no production code changed because BESS-TS6-001 through BESS-TS6-009 already implement the full behavior. Added `tests.test_ts6_acceptance` (8 tests, TDD one behavior at a time) telling one continuous story: allowlist registry covers exactly `scale_signal`/`resample`/`interpolate_gaps`/`combine_signals` and rejects unknown types before writing; each transformation derives a set with full lineage (revision `metadata_json.transformation` + generic `validation_dependencies` rows incl. the `transformation_implementation` pin) while sources keep hash/revision untouched; a source edit marks derived sets Layer-1 stale (list badge flag), fail-closes bound variants for materialization AND revalidation, regeneration appends revision 2 with revision 1's hash preserved, and the manual gate reopens only after explicit revalidation; mocked connector data lands through the common source/set path (created -> converged -> new_revision) with programmed issuer/validity preserved per revision across a reissue with identical values (same content_hash, new revision); a scheduled run's snapshot metadata equals the manual run's contract (kind/input_variant/date_range/series_bindings) plus an `automation` block, `trigger_type` manual vs scheduled, both list together, and the scheduled run indexes through the same TS-4 rebuild path; rolling schedules resolve per-tick ranges recorded in tick and snapshot with visible failures and the schedule staying active; manual variant-driven runs are unchanged (no automation fields, stale gate intact) while derived sets, regenerations and schedules coexist; and a docs test pins README/issue/tracker/checklist/architecture note to their final state. Two fixture-only fixes during TDD; zero production edits. Docs: `pruebas_manuales_ts6.md` (TS-1..TS-5-shaped checklist), `architecture_ts6_final.md` (transformation layer, two-layer staleness, connector boundary, automation semantics), README section "TS-6: Transformations, Connectors And Automation", tracker finalized. No performance tests added (no measured bottleneck). Backend suite 547 passed, 2 skipped (up from 539); frontend tsc/eslint/vitest (66)/api:check/build green. Julia not required: no artifact, `system_case_json` or optimizer change. TS-6 is fully closed. |

## Final TS-6 Verification

Run before considering TS-6 closed. Focused acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts6_acceptance -v
```

Full backend suite:

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
