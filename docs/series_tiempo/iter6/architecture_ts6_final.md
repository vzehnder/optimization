# TS-6 Final Architecture: Transformations, Connectors And Automation

Fecha: 2026-07-11
Status: Accepted, closes TS-6
Issue: `BESS-TS6-010`
Supersedes nothing; formalizes
`docs/series_tiempo/iter6/decision_record_ts6_transformation_semantics.md`
as the settled reference so future PRDs do not reopen these decisions.

## Purpose

TS-1 through TS-5 settled the common model: topology/parameter provenance,
a generic time-series catalog, case input variants with fail-closed stale
validation, BBDD-indexed run results and unified legacy paths. TS-6 added
the layer on top: declarative allowlisted transformations, external data
connectors and scheduled automation — all built as extensions of that model,
never as parallel systems. This document is the settled picture of the
result as implemented.

## The Transformation Layer

```text
TimeSeriesSet (source, any data_kind)
      |                        TRANSFORMATION_REGISTRY (app/transformations.py)
      |                          scale_signal | resample | interpolate_gaps
      v                          combine_signals (multi-input)
apply_time_series_transformation / apply_time_series_combination
      |
      v
TimeSeriesSet (data_kind = "derived", status = validated)
  - revision metadata_json.transformation: type, implementation_version,
    parameter_schema_version, validated parameters, inputs[{set, revision,
    content_hash, signals}], recipe hash, optional execution metadata
  - validation_dependencies rows (owner_type = 'time_series_set'):
    one per input set (recorded content_hash) plus one
    'transformation_implementation' pin (recorded version)
```

- **Allowlist is code, not data**: `TRANSFORMATION_REGISTRY` in
  `app/transformations.py` is the only executable surface. A
  `transformation_type` absent from the registry is rejected before anything
  is validated or written. No user-provided script is ever stored in or
  executed from the database. Adding a transformation later is additive to
  the registry.
- **Versioned behavior**: each registry entry pins an
  `implementation_version` (bumped when execution logic changes) and a
  `parameter_schema_version` (bumped when the validated-parameter shape
  changes), both recorded in every derived revision, so old derived sets
  remain interpretable and re-traceable to code behavior.
- **Output model**: first execution creates a new set (`data_kind =
  "derived"`, named by the analyst, versioned like any catalog set);
  regeneration writes a new revision of that same set, never a new set.
  Re-running an identical recipe converges (recipe-hash match) instead of
  duplicating. Sources are never mutated: their content hashes and revisions
  are untouched by any transformation.
- **Run-time stays strict**: no implicit resampling or gap filling ever
  happens at materialization or run time. Transformations run beforehand and
  produce an explicit derived version that is then bound and selected like
  any other set.

## Derived-Set Staleness: Two Layers, One Mechanism

- **Layer 1 (set vs. its recipe)**: `evaluate_time_series_set_staleness`
  reuses the generic TS-3 staleness comparator with `owner_type =
  'time_series_set'`, comparing recorded `validation_dependencies` against
  current input hashes and the registry's current implementation version.
  Stale derived sets get a catalog badge and a regenerate action; the flag
  alone blocks nothing on the set itself.
- **Layer 2 (variant vs. its bindings)**: unchanged TS-3 plumbing, plus one
  new dependency type (`time_series_set_derived_staleness`) that propagates
  "bound derived set is Layer-1 stale" into variant staleness. A variant
  bound to a known-stale derived set fails closed for both materialization
  and revalidation until the derived set is regenerated (or the binding
  changes), and then still requires an explicit revalidation because the
  regenerated revision has a new hash.
- **History is immutable**: regeneration only appends revisions. Runs,
  scenario versions and artifacts keep pointing at the exact
  revisions/hashes they consumed, before and after any regeneration.

## The Connector Boundary

External data enters the catalog exactly like a file. The isolated module
`app/forecast_connector.py` defines the narrow `ForecastConnector` protocol
(`fetch() -> ForecastPayload`) with one concrete, config-driven
implementation (`HttpJsonForecastConnector`: HTTP GET via httpx, optional
Bearer token, optional dot-path record extraction, canonical row checksum).
Endpoint, auth and payload shape are configuration, so the concrete vendor
is replaceable without touching core series logic — which never sees the
external API's shape.

Ingestion (`AnalystStore.ingest_connector_time_series_set`) reuses the TS-2
pipeline end to end: rows validate exactly like a CSV, the source row
carries `kind = 'connector'` with connector identity/target/fetch-time
metadata, and the set lands as `data_kind = "forecast"` (or `"programmed"`).
Re-ingesting unchanged data converges without writing; changed data advances
one revision via the existing replace path.

Programmed official data additionally records issuer and validity
(`validate_program_metadata`: issuer, issued_at, valid_from < valid_until,
all ISO-8601 with offset) per revision in the existing revision metadata. A
reissue with identical values but new issuer/validity still lands as a new
revision, so a run's recorded content hash maps to the exact program version
it consumed.

## Automation Semantics

Schedules are data; firing is external invocation. The `run_schedules` table
stores declarative definitions — scenario/case, input variant, range rule,
cadence, next fire time, plus the TS-1 topology/parameter hashes — never a
hand-authored `system_case_json`. `run_schedule_ticks` records every firing
with its status, resolved range, error or produced scenario-version/run ids.

- **Firing path** (`app/schedules.py`): `due_fixed_range_schedules` resolves
  which active schedules are due at time T; `execute_fixed_range_schedule`
  runs each one through the exact same pipeline as a manual variant run —
  staleness/coverage gates, validation, immutable scenario version (with the
  same `kind = "case_input_variant"` lineage plus an `automation` block
  naming schedule and tick), run creation (`trigger_type = "scheduled"`) and
  queueing, hence TS-4 result indexing on success. Gate failures mark the
  tick `failed` with the reason, create no run, and leave the schedule
  active; the next fire time always advances from the due time, not the
  wall clock.
- **Range rules**: `range_mode = "fixed"` reuses the stored range every
  tick; `range_mode = "rolling"` resolves each tick's range from its due
  time (`rolling_start_offset_hours`, `rolling_duration_hours`), and each
  tick and snapshot records the concrete resolved range, keeping
  rolling-horizon automation reproducible per tick.
- **Invocation**: a thin admin-gated API (`POST /api/admin/schedules/...`)
  plus `scripts/run_due_schedules.py` for an OS-level scheduler (cron /
  Task Scheduler). No in-process scheduler, background thread or new
  dependency exists; "what fired and what it produced" is a pure function
  of (time, schedule rows, run execution).
- **Permissions**: defining and firing schedules is admin-only, matching the
  TS-5 precedent for automation/bulk operations. Schedule-produced runs are
  ordinary runs: they list, render and compare through the existing internal
  read paths.

## What Stays Out

Confirmed out of scope, unchanged from the PRD and decision record:
arbitrary user-defined scripts as transformations; implementing every
possible transformation type upfront (`clip_negative_values`,
`shift_timezone_display` and `derive_availability_from_outage_events`
remain future, additive registry entries); replacing manual run flows;
real-time SCADA; optimizer changes; and physical storage optimizations
(partitioning, TimescaleDB) until a measured bottleneck at real volume
justifies them — none was measured during TS-6, so no performance tests
were added speculatively.

## Closing Proof

`tests/test_ts6_acceptance.py` ties the iteration together in one story:
the allowlist covers exactly the four accepted transformations and rejects
unknown types before writing; every transformation derives a set with full
lineage (metadata and dependency rows) while sources stay untouched; a
source edit marks derived outputs stale, fail-closes bound variants for
materialization and revalidation, and regeneration appends a revision while
revision 1 keeps its hash; mocked connector data lands through the common
source/set path with create/converge/new-revision semantics and per-revision
program metadata across reissues; scheduled runs produce the same snapshot
contract as manual runs plus automation lineage and index through the same
TS-4 path; rolling schedules resolve per-tick ranges and keep failures
visible without deactivating; and manual variant-driven runs remain
unchanged with the stale gate intact while all TS-6 features coexist in the
same project.

## What Comes After TS-6

Any future work builds on this as fixed ground: transformations are
registry-defined and versioned, derived data is regenerable but its history
immutable, external data flows through connectors into the common
source/set model, and automation reuses the manual pipeline end to end.
New transformation types, new connector implementations and richer schedule
rules are all additive extensions of the surfaces named here, not new
architectures.
