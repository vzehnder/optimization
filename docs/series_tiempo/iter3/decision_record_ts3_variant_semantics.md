# TS-3 Input Variant Semantics Decision Record

Fecha: 2026-07-06
Status: Accepted
Issue: `BESS-TS3-000`

## Context Reviewed

This decision was reviewed against:

- `docs/series_tiempo/iter3/prd.md` (TS-3 PRD and its Grill-Me answers);
- `docs/series_tiempo/roadmap_iteraciones_jerarquias_series.md` (TS-3 section
  and detail, including the `OptimizationCase -> ParameterVersion ->
  InputSeriesVariant -> DateRange -> Run` mental model);
- `docs/db/propuesta_bbdd_componentes_timeseries.md` (accepted decisions on
  `case_input_variants`, `case_time_series_bindings`, `validation_dependencies`,
  `time_series_set_revisions`, and the `scenario_versions.normalized_case_id` /
  `case_input_variant_id` / `time_series_set_versions_json` lineage proposal);
- `docs/series_tiempo/iter1/decision_record_ts1_hierarchy.md` (TS-1 accepted
  hierarchy semantics: `OptimizationCase` as editable object,
  `ScenarioVersion` as the only immutable executable snapshot, topology vs.
  parameters);
- `docs/series_tiempo/iter2/decision_record_ts2_catalog_semantics.md` (TS-2
  accepted catalog: `time_series_sets` / `..._set_revisions` /
  `..._periods` / `..._signals` / `..._values`, `version_number` vs.
  `revision_number`, manual-edit-creates-new-revision policy);
- current schema in `app/persistence.py` (`optimization_cases`,
  `scenario_versions`, `runs`, `time_series_sets` and related tables actually
  implemented, as opposed to only proposed);
- `app/persistence.py` hierarchy provenance helpers
  (`derive_case_hierarchy_views`, `derive_case_hierarchy_provenance`,
  `hierarchy_stale_state`, `generate_system_case_from_hierarchy`) built during
  TS-1;
- `app/time_series_catalog.py` (`TIME_SERIES_SIGNAL_CATALOG`, the 8-key
  canonical signal registry accepted in TS-2);
- `app/runner.py` (`RunExecutor.execute`, the existing manual-run
  infrastructure that reads a `run` row's `scenario_version_id` and executes
  Julia against its frozen `system_case_json`).

## Accepted Decisions

1. Variants store bindings, not copied series values, is **accepted**. A new
   `case_input_variants` table (product-facing name: `InputSeriesVariant`)
   holds one row per named variant of an `optimization_case`. A new
   `case_time_series_bindings` table resolves required signals to
   `time_series_sets` / `time_series_signals` rows by reference
   (`time_series_set_id`, `signal_key`), never by copying `time_series_values`.
   This mirrors the legacy `case_hydraulic_time_series_bindings` table that
   already exists in the schema for the hydraulic-diagram path; TS-3
   introduces the generic, TS-2-catalog-backed analog, scoped under a variant
   instead of directly under the case, so the legacy hydraulic binding path is
   left untouched until TS-5.
2. One default variant per case is **accepted**. Implemented as
   `case_input_variants.is_default BOOLEAN NOT NULL DEFAULT FALSE` with a
   partial unique index enforcing at most one default per `case_id`, rather
   than a `default_input_variant_id` column on `optimization_cases` (which
   would create a circular FK between the case and its variants). The default
   variant is created lazily — the first time an analyst opens a case without
   one, or the first time a binding is attached — consistent with TS-1's
   conservative, adapter-style implementation approach rather than a
   backfill migration.
3. The run date range belongs to the execution snapshot, not to the variant,
   is **accepted**. `case_input_variants` gets no date-range columns; the
   range is supplied as an explicit argument when running (or validating) a
   variant, alongside the variant id, and is frozen into the resulting
   `scenario_version`'s lineage metadata (see Decision 8). This is a separate
   concept from `case_solver_settings.start_timestamp/end_timestamp`, which
   the DB proposal already reserves for a future rolling-horizon solver
   window; TS-3's date range is the analyst-chosen slice of the input series,
   not a solver setting.
4. Exact-period-compatibility (no implicit resampling in TS-3) is
   **confirmed**. Range validation walks `time_series_periods` for every
   bound signal and requires that periods cover the selected
   `[start, end)` range with no gaps and matching `duration_hours`; any
   mismatch fails validation before a snapshot is materialized or Julia is
   invoked. Mixed resolutions across bound signals are rejected, not
   reconciled.
5. Running from a variant creates or reuses the technical snapshot
   automatically (manual `ScenarioVersion` creation is no longer the primary
   path) is **accepted**, and reuses existing infrastructure rather than new
   execution machinery: a new deep-module function resolves variant bindings
   against the selected range into a `time_series` payload, feeds it into
   (a sibling of) `generate_system_case_from_hierarchy` to produce
   `system_case_json`, then calls the existing `create_scenario_version` and
   `create_run`, which `RunExecutor.execute` already knows how to run. No
   changes to `runs` or `scenario_versions` execution semantics are needed;
   `scenario_versions` stays immutable and remains the only thing `runs`
   points to, per the TS-1 decision record.
6. Stale semantics are **accepted**, and a variant is stale — blocking runs
   until revalidated (fail closed, no silent re-run on stale data) — when
   either:
   - any bound `time_series_set`'s current `content_hash` differs from the
     hash recorded at the variant's last validation (same "new revision
     without changing `version_number`/`version_label`" policy TS-2 already
     established for manual edits and file-replace uploads); or
   - the case's topology or parameter provenance hash
     (`derive_case_hierarchy_provenance`, already built in TS-1) differs from
     the hash recorded at last validation.
   Both are tracked through one generic `validation_dependencies` table
   (`owner_type = 'case_input_variant'`, `owner_id`, `dependency_type` in
   `{'time_series_set', 'topology', 'parameters'}`, `dependency_id` nullable,
   `recorded_hash`) rather than bespoke staleness columns per dependency kind,
   per the DB proposal's generic pattern.
7. Required-signal families and their discovery are **agreed**: grid price
   (`import_price_usd_per_mwh` / `export_price_usd_per_mwh`), load demand
   (`load_demand_mw`), renewable availability
   (`renewable_available_power_mw`), hydraulic inflows (`natural_inflow_m3s`
   per hydraulic node) and reach minimum flows (`minimum_flow_m3s` per
   hydraulic reach) — the same `signal_key`s already registered in
   `TIME_SERIES_SIGNAL_CATALOG` from TS-2, no new catalog entries needed for
   TS-3. Discovery walks the same case-active-entity tables topology already
   uses (`case_components` for one-bus assets; `case_hydraulic_nodes` /
   `case_hydraulic_reaches` for hydro-diagram cases) to enumerate which active
   entities require which `signal_key`, mirroring how
   `case_hydraulic_curve_bindings` and `case_hydraulic_time_series_bindings`
   already discover required bindings today.
8. The out-of-scope list (no result series in BBDD, no resampling, no
   advanced comparison UI, no scheduled runs, no client-facing variant
   editing) is **confirmed** as written in the PRD.
9. Lineage storage for TS-3 is **accepted as an extension of the existing
   TS-1 pattern**, not new typed columns: the selected variant id/name, the
   date range and the resolved series lineage (`time_series_set_id`,
   `version_number`, `version_label`, `revision_number`, `content_hash` per
   bound signal) are recorded inside `scenario_versions.generation_metadata_json`,
   the same JSON blob that already carries `topology`/`parameters` provenance
   hashes from TS-1. This avoids a `scenario_versions` schema migration for
   TS-3 and keeps one consistent place for run lineage. Dedicated queryable
   columns (`case_input_variant_id`, `time_series_set_versions_json`, as
   floated in the DB proposal) are deferred to TS-5 hardening if query
   performance or reporting ever requires indexing lineage outside the JSON
   blob — nothing in TS-3's acceptance criteria needs it, since run detail
   only needs to *display* this metadata, not query across runs by variant
   at scale.

## PRD Corrections

No corrections are required to `docs/series_tiempo/iter3/prd.md` text. Two
implementation clarifications are recorded for downstream TS-3 issues:

1. "`TopologyVersion`" and "`ParameterVersion`" in the PRD/roadmap mental
   model (`OptimizationCase -> ParameterVersion -> InputSeriesVariant ->
   DateRange -> Run`) are **not** new tables. They already exist as the
   derived content hashes TS-1 built
   (`derive_case_hierarchy_provenance`/`hierarchy_stale_state` in
   `app/persistence.py`), computed on demand from `system_case_json`'s
   topology/parameter views. TS-3 reuses these hashes for the
   topology/parameters half of variant staleness (Decision 6); it does not
   introduce `topology_versions` or `parameter_versions` tables.
2. `case_input_variants`/`case_time_series_bindings` are new tables scoped by
   `case_id`, distinct from the already-implemented, hydraulic-diagram-only
   `hydraulic_time_series_sets`/`case_hydraulic_time_series_bindings` tables.
   TS-3 issues must not repurpose or migrate the legacy hydraulic binding
   path; it stays as-is until TS-5, per the TS-1 and TS-2 decision records.

## Acceptance Mapping

- Variants store bindings, not copied values: accepted (Decision 1).
- One-default-variant-per-case policy: accepted, via `is_default` + partial
  unique index rather than a case-side pointer column (Decision 2).
- Date range chosen at run time, frozen in the execution snapshot: accepted
  (Decision 3).
- Exact-period-compatibility rule (no implicit resampling in TS-3): confirmed
  (Decision 4).
- Running from a variant creates/reuses the technical snapshot automatically:
  accepted, reusing `create_scenario_version` / `create_run` /
  `RunExecutor.execute` unchanged (Decision 5).
- Stale semantics (series hash, topology, parameters), including blocking
  runs until revalidated: accepted, via a generic `validation_dependencies`
  table (Decision 6).
- Required-signal families and their discovery from case topology/parameters:
  agreed, reusing the existing TS-2 signal catalog and existing
  active-entity tables (Decision 7).
- Out-of-scope list: confirmed (Decision 8).
- Lineage storage approach: accepted as a `generation_metadata_json`
  extension, consistent with TS-1, with dedicated columns explicitly deferred
  (Decision 9).
- No PRD text correction is required before downstream TS-3 implementation
  begins; the two clarifications above (Decisions/Corrections referencing
  existing hierarchy-provenance functions and the legacy hydraulic binding
  path) are documented for implementers.

## Verification

- Inspected `app/persistence.py` schema (`optimization_cases`,
  `scenario_versions`, `runs`, `time_series_sets`,
  `case_hydraulic_time_series_bindings`) to confirm no `case_input_variants`,
  `case_time_series_bindings` or `validation_dependencies` tables exist yet,
  consistent with this issue being a decision record with no schema changes.
- Confirmed `derive_case_hierarchy_provenance`, `hierarchy_stale_state` and
  `generate_system_case_from_hierarchy` already exist in `app/persistence.py`
  from TS-1, grounding Decisions 6 and 9 in real code rather than the
  roadmap's simplified diagram.
- Confirmed `TIME_SERIES_SIGNAL_CATALOG` in `app/time_series_catalog.py`
  already carries the 8 `signal_key`s needed for Decision 7, so TS-3 does not
  need to extend the catalog.
- Confirmed `app/runner.py`'s `RunExecutor.execute` reads
  `runs.scenario_version_id` and executes the frozen `system_case_json`
  unchanged, grounding Decision 5's "reuse existing manual-run
  infrastructure" claim.

## Blocked by

None - can start immediately.
