# BESS-TS3-000: Review TS-3 PRD And Input Variant Semantics

Status: Done
Type: HITL
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-07
Fecha de termino planificada: 2026-07-07
Fecha de inicio real: 2026-07-06
Fecha de termino real: 2026-07-06

## User stories covered

1 through 22

## What to build

Review and accept the TS-3 PRD before implementation starts. The review should
confirm the semantic model of input variants per case: an `InputSeriesVariant`
binds required case signals to `TimeSeriesSet`/`TimeSeriesSignal` without
copying values, each `OptimizationCase` has a default variant, the run date
range belongs to the execution snapshot (not the variant), and running from a
variant creates or reuses an immutable technical snapshot compatible with the
existing run infrastructure.

The outcome should be a short accepted-decision record in the iteration docs,
including any corrections to the PRD if the variant model, binding semantics,
stale rules, required-signal families or snapshot policy needs adjustment.

## Acceptance criteria

- [x] The decision that variants store bindings (not copied series values) is accepted or corrected.
- [x] The one-default-variant-per-case policy is accepted.
- [x] The decision that the date range is chosen at run time and frozen in the execution snapshot (not stored on the variant) is accepted.
- [x] The exact-period-compatibility rule (no implicit resampling in TS-3) is confirmed.
- [x] The policy that running from a variant creates or reuses the technical snapshot automatically (manual `ScenarioVersion` no longer the main path) is accepted.
- [x] The stale semantics (bound set revision/hash change, topology change, parameter change) are accepted, including whether a stale variant blocks runs until revalidation.
- [x] The required-signal families (grid prices, load demand, renewable availability, hydraulic inflows, reach minimum flows) and their discovery from case topology/parameters are agreed.
- [x] The out-of-scope list (no result series in BBDD, no resampling, no advanced comparison UI, no scheduled runs, no client-facing variant editing) is confirmed.
- [x] Any PRD correction is committed before downstream TS-3 implementation issues begin.

## Resolution

Accepted the TS-3 input variant semantics in
`docs/series_tiempo/iter3/decision_record_ts3_variant_semantics.md`.

The review confirms:

1. Variants store bindings (new `case_input_variants` /
   `case_time_series_bindings` tables), never copied series values, mirroring
   the existing legacy `case_hydraulic_time_series_bindings` shape but scoped
   under a variant and backed by the generic TS-2 catalog.
2. One default variant per case via `case_input_variants.is_default` plus a
   partial unique index, created lazily rather than via a case-side pointer
   column.
3. The run date range is supplied at run time and frozen into
   `scenario_versions.generation_metadata_json`; it is not a variant column.
4. Exact period compatibility is required in TS-3; mismatched or gapped
   horizons fail validation before Julia runs.
5. Running a variant reuses the existing `create_scenario_version` /
   `create_run` / `RunExecutor.execute` pipeline unchanged; no new execution
   machinery.
6. Stale detection covers bound series hash drift and case topology/parameter
   hash drift (reusing TS-1's `derive_case_hierarchy_provenance`), tracked via
   a generic `validation_dependencies` table, and blocks runs until
   revalidated.
7. Required-signal families reuse the 8-key TS-2 `TIME_SERIES_SIGNAL_CATALOG`
   as-is; discovery walks existing case-active-entity tables.
8. Out-of-scope list confirmed as written.
9. Lineage (variant, range, series hashes) lives in
   `generation_metadata_json`, extending the TS-1 pattern rather than adding
   new `scenario_versions` columns; dedicated columns are deferred to TS-5.

No PRD text correction is required. Two implementation clarifications are
recorded: "TopologyVersion"/"ParameterVersion" are the existing TS-1 derived
hashes, not new tables; and the new generic bindings must not touch the
legacy hydraulic-diagram binding path.

## Verification

- Inspected `app/persistence.py` to confirm no `case_input_variants`,
  `case_time_series_bindings` or `validation_dependencies` tables exist yet,
  consistent with a decision-record-only issue with no schema changes.
- Confirmed `derive_case_hierarchy_provenance`, `hierarchy_stale_state`,
  `generate_system_case_from_hierarchy` (TS-1) and `TIME_SERIES_SIGNAL_CATALOG`
  (TS-2) already exist and ground the decisions above in real code.
- Confirmed `app/runner.py`'s `RunExecutor.execute` runs off
  `runs.scenario_version_id` unchanged, grounding the "reuse existing
  manual-run infrastructure" decision.

## Blocked by

None - can start immediately.
