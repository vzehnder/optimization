# TS-6 Transformation Semantics Decision Record

Fecha: 2026-07-10
Status: Accepted
Issue: `BESS-TS6-000`

## Context Reviewed

This decision was reviewed against:

- `docs/series_tiempo/iter6/prd.md` (TS-6 PRD and its Grill-Me answers,
  including the deliberate activation gate in question 1 and user story 18);
- `docs/series_tiempo/roadmap_iteraciones_jerarquias_series.md` (TS-6 section
  "Iteracion TS-6 Futura", its transformation examples list
  `resample_hourly_to_daily` / `fill_missing_linear` / `scale_signal` /
  `combine_price_scenarios` / `derive_availability_from_outage_events` /
  `clip_negative_values` / `shift_timezone_display`, and the external-forecast
  framing "deberia entrar como `time_series_source` y terminar generando
  `time_series_set`, igual que un Excel");
- `docs/series_tiempo/propuesta_manejo_series_tiempo.md` (original `data_kind`
  enumeration: `real`, `programmed`, `forecast`, `simulated`, `synthetic`,
  `mixed`);
- draft TS-6 issues `BESS-TS6-001` through `BESS-TS6-010`, to confirm this
  record actually closes what each downstream issue expects to consume;
- `docs/series_tiempo/iter2/decision_record_ts2_catalog_semantics.md`
  (`version_number`/`version_label` vs. `revision_number`, manual-edit-creates-
  new-revision policy, code-level registry precedent for
  `TIME_SERIES_SIGNAL_CATALOG` instead of a DB-enforced allowlist table);
- `docs/series_tiempo/iter3/decision_record_ts3_variant_semantics.md`
  (`case_input_variants`, `case_time_series_bindings`, the generic
  `validation_dependencies` table and `evaluate_variant_staleness`, and the
  precedent of extending an existing JSON metadata blob for lineage instead of
  adding dedicated columns);
- `docs/series_tiempo/iter4/decision_record_ts4_result_semantics.md` (dedicated
  run-result layer, BBDD-first/artifact-fallback policy, idempotent
  replace-on-write indexing — the shape TS6-008 automation must reuse, not
  duplicate);
- `docs/series_tiempo/iter5/decision_record_ts5_migration_semantics.md`
  (accepted permission matrix: analyst/admin read-write on input series across
  all projects, admin-only for retention/cleanup and bulk migration sweeps);
- current schema in `app/persistence.py`: `time_series_sources`,
  `time_series_sets` (`data_kind`, `version_number`/`version_label`,
  `content_hash`), `time_series_set_revisions` (`revision_number`,
  `content_hash`, `metadata_json TEXT NOT NULL DEFAULT '{}'`,
  `time_series_source_id` nullable), `time_series_periods`,
  `time_series_signals`, `case_input_variants`, `case_time_series_bindings`
  (binds by `time_series_set_id` only, no revision pin), and the generic
  `validation_dependencies` table (`owner_type`, `owner_id`, `dependency_type`,
  `dependency_id`, `recorded_hash`);
- `app/time_series_catalog.py` (`TIME_SERIES_DATA_KINDS = {"real",
  "programmed", "forecast", "simulated", "synthetic", "mixed"}`,
  `TIME_SERIES_SIGNAL_CATALOG` as an existing code-level registry precedent);
- `app/variant_staleness.py` (`evaluate_variant_staleness`, a generic
  dependency-hash comparator already keyed by `(dependency_type,
  dependency_id)`, not specific to any one dependency kind);
- `app/auth.py` (`VALID_USER_ROLES`, `INTERNAL_USER_ROLES`,
  `AuthorizationService.require_admin`/`require_internal`) and `app/main.py`
  (`require_admin_user` gating retention/cleanup/rebuild endpoints, all other
  internal routes gated only by the coarser `require_internal` middleware);
- `requirements.txt` (no scheduler/task-queue dependency present today —
  `fastapi`, `httpx`, `psycopg[binary]`, `plotly`, `uvicorn`, no
  `apscheduler`/`celery`);
- the real `energy_dispatch` PostgreSQL database configured in `.env`, queried
  directly to ground the activation decision in actual usage rather than
  assumption (see Verification).

## Accepted Decisions

1. **Activation decision (user story 18): TS-6 starts now.** Two independent
   grounds support this, either of which would be sufficient on its own:
   - The product owner explicitly instructed starting TS-6 implementation
     today (2026-07-10), which is itself the "record that the iteration
     starts anyway and why" branch the PRD explicitly allows.
   - Real usage of the TS-2 through TS-5 model already exists in the
     production database (`energy_dispatch`), not only in test fixtures: 41
     projects, 34 scenarios, 20 optimization cases, 20 executed scenario
     versions, 21 runs, 32 catalog time-series sets (30 `real`, 2
     `synthetic`; 29 `validated`) spanning 39 revisions across those 32 sets
     (evidence that manual edits/re-uploads have actually happened), 23
     case input variants and 22 case-time-series bindings. This is enough
     real usage of the base model to know which transformations are worth
     building — the four shipping in this iteration (below) are exactly the
     needs already implied by that usage: real signals at mismatched
     resolutions, occasional gaps, sensitivity scaling and multi-set
     scenario composition — not speculative capabilities invented ahead of
     any usage signal.
2. **Initial allowlist catalog is accepted as exactly the four
   transformations already drafted in BESS-TS6-001 through BESS-TS6-004**,
   using these canonical `transformation_type` keys (generalizing, not
   copying verbatim, the roadmap's overly narrow example names):
   - `scale_signal` (BESS-TS6-001) — single input, single signal, multiplies
     by a validated scale factor.
   - `resample` (BESS-TS6-002) — single input, target resolution plus a
     per-signal aggregation/distribution method; generalizes the roadmap's
     `resample_hourly_to_daily` to any resolution pair.
   - `interpolate_gaps` (BESS-TS6-003) — single input, a declared method
     (`linear` is the only allowlisted method for this iteration) and a
     declared maximum fillable gap; generalizes the roadmap's
     `fill_missing_linear`.
   - `combine_signals` (BESS-TS6-004) — multi-input, names each input set,
     revision and contributed signals; generalizes the roadmap's
     `combine_price_scenarios` to arbitrary signal composition, not only
     prices.

   Explicitly **future, not shipped this iteration**: `clip_negative_values`
   and `shift_timezone_display` (no drafted issue requests them — adding them
   now would be exactly the "implementing every possible transformation type
   upfront" the PRD puts out of scope) and
   `derive_availability_from_outage_events` (depends on `availability_events`
   machinery that does not exist yet in this codebase, the same reason TS-2
   deferred `unit_availability_factor`). Adding a transformation type later is
   additive to the registry described in Decision 3, not breaking.
3. **Allowlist enforcement is a code-level module registry, not a DB
   table**, mirroring the precedent `TIME_SERIES_SIGNAL_CATALOG` already set
   in TS-2 (`app/time_series_catalog.py`) rather than the "DB-enforced
   allowlist" style the central DB proposal floated but that has not been
   built anywhere in this codebase. A new module (`app/transformations.py`)
   holds one entry per allowlisted `transformation_type`: its
   `implementation_version` (integer, bumped when execution logic changes),
   its `parameter_schema_version` (integer, bumped when validated-parameter
   shape changes), a `validate_parameters(raw) -> ValidatedParameters`
   function, and an `execute(...)` function. A transformation type absent
   from this registry is rejected before anything is validated or written —
   this is what "no arbitrary user-provided script is ever stored or
   executed" means concretely: the registry is Python code reviewed and
   deployed like any other module, never data read from BBDD and executed.
4. **Output model: a transformation always produces a new `time_series_set`
   the first time it runs; regeneration (BESS-TS6-005) produces a new
   revision of that same set, never a new set.** This reuses the TS-2
   manual-edit-creates-new-revision policy verbatim (Decision 7 of the TS-2
   decision record) instead of inventing a second versioning mechanism:
   `version_number`/`version_label` identify the derived set and stay stable
   across regenerations; `time_series_set_revisions.revision_number` and
   `content_hash` advance on every (re)execution. A new `data_kind` value,
   `"derived"`, is added to `TIME_SERIES_DATA_KINDS` in
   `app/time_series_catalog.py` (additive, matching how TS-2 treated adding a
   `signal_key` later) so derived sets are distinguishable in the catalog
   list/filter UI from uploaded `real`/`synthetic`/`forecast`/`programmed`
   sets without introducing a second catalog concept. Naming follows the same
   pattern as any natively created set — the analyst names it, with the UI
   proposing a default such as `<source_name>__<transformation_type>`.
5. **Lineage contract is accepted as an extension of existing generic
   columns, not new dedicated tables** — the same choice TS-3 made for run
   lineage (Decision 9 of the TS-3 decision record) applied here to
   transformation lineage:
   - The transformation-created `time_series_set_revisions` row stores the
     full lineage in its existing `metadata_json` column: `transformation`
     object with `type`, `implementation_version`, `parameter_schema_version`,
     the validated `parameters`, and an `inputs` array of
     `{time_series_set_id, revision_number, content_hash, signals}` (one
     entry per input; a length-1 array for the three single-input
     transformations, length-N for `combine_signals`). No new column or
     table is required — `metadata_json TEXT NOT NULL DEFAULT '{}'` already
     exists on `time_series_set_revisions`.
   - The same inputs are additionally registered as rows in the existing
     `validation_dependencies` table with `owner_type = 'time_series_set'`,
     `owner_id = <derived set id>`, `dependency_type = 'time_series_set'`,
     `dependency_id = str(input_set_id)`, `recorded_hash = <input's
     content_hash at generation time>`, plus one synthetic row per derived
     set with `dependency_type = 'transformation_implementation'`,
     `dependency_id = transformation_type`, `recorded_hash =
     str(implementation_version)`. This is the same generic
     `(owner_type, owner_id, dependency_type, dependency_id, recorded_hash)`
     shape TS-3 already uses for variant staleness — reused here for a
     different `owner_type`, not duplicated with bespoke columns.
   - The catalog detail page's lineage panel (BESS-TS6-001 acceptance
     criterion) reads the latest revision's `metadata_json` directly; no
     cross-row query is needed to render one set's own lineage.
6. **Derived-set staleness composes with TS-3 variant staleness as two
   layers sharing one mechanism, not two unrelated systems:**
   - **Layer 1 (new, BESS-TS6-005):** a derived set is stale relative to its
     own recipe when `evaluate_variant_staleness`-style comparison (reused
     as-is, just called with `owner_type = 'time_series_set'` instead of
     `'case_input_variant'`) finds that any `validation_dependencies` row
     registered in Decision 5 no longer matches: an input set's current
     `content_hash` differs from `recorded_hash`, or the registry's current
     `implementation_version` for that `transformation_type` differs from
     the recorded one. This flag is visible in the catalog (list badge and
     detail page) and offers the regenerate action; it does not by itself
     change the derived set's own `content_hash` or block anything.
   - **Layer 2 (existing, TS-3, unchanged):** regenerating a stale derived
     set (Decision 4) advances its `content_hash` via a new revision, exactly
     like a manual edit or file-replace upload today. Any `case_input_variant`
     bound to that set becomes stale through the *existing*
     `evaluate_variant_staleness` mechanism with **zero changes** to
     `app/variant_staleness.py` — the fail-closed run gate TS-3 built already
     covers this case because it was written generically.
   - The one addition Layer 2 needs is propagating "derived set is currently
     stale per Layer 1" as its own current-dependency entry
     (`dependency_type = 'time_series_set_derived_staleness'`) when computing
     variant staleness for a variant bound to a derived set, so a variant
     bound to a *not-yet-regenerated-but-known-stale* derived set is blocked
     even before the derived set's own `content_hash` changes (closing
     BESS-TS6-005's acceptance criterion "a variant bound to a stale derived
     set is blocked... until resolved"). This is one new dependency type
     inside the existing generic table, not new staleness plumbing.
   - Regeneration never rewrites history: it only inserts a new
     `time_series_set_revisions` row (Decision 4); `runs`/`scenario_versions`
     keep pointing at the exact `content_hash` they consumed, unchanged,
     matching the TS-3/TS-5 immutability guarantees already in force.
7. **First external connector target: a generic, config-driven HTTP+JSON
   forecast connector — not a named commercial vendor.** No project document,
   PRD, prior decision record or codebase reference names a concrete external
   forecast/price-program API, so inventing one here would be
   unfounded speculation rather than a grounded decision. The accepted shape:
   - An isolated module `app/forecast_connector.py` defines a narrow
     `ForecastConnector` interface (`fetch() -> ForecastPayload`) and one
     concrete implementation that performs an HTTP GET (via `httpx`, already
     a dependency — no new library needed) against a base URL/auth
     configured per project or environment, then parses a JSON payload into
     rows. Endpoint, auth and payload shape are configuration, not hardcoded
     vendor logic, so the concrete vendor can be swapped without touching
     core series logic (the PRD's "isolated module, narrow interface,
     replaceable" requirement).
   - Ingestion lands through the existing `time_series_sources` +
     `time_series_sets` path exactly like a CSV/XLSX upload: the connector
     writes a `time_series_sources` row with `kind = 'connector'` (a new
     value alongside the existing `'csv'`/`'xlsx'`, additive) and
     connector-origin metadata (connector identity, fetch time, target) in
     its existing `metadata_json` column, then produces/updates a
     `time_series_sets` row with `data_kind = 'forecast'` (already in
     `TIME_SERIES_DATA_KINDS`, no new data kind needed here) through the same
     TS-2 validation and revision-convergence path uploads already use.
   - Test mocking strategy: tests exercise the concrete HTTP implementation
     against a fake/mocked `ForecastConnector` (or an `httpx` transport
     stub) — never real network access — asserting only that ingestion lands
     through the common source/set path, per BESS-TS6-006's acceptance
     criteria.
8. **Scheduling mechanism: schedule definitions stored as data; firing is
   external invocation, not an in-process scheduler.** Rejected: adding
   `apscheduler`/`celery` or a background thread inside the FastAPI process.
   No scheduler dependency exists today (`requirements.txt` confirmed empty
   of one), and introducing an always-on in-process scheduler would add
   operational surface (process lifecycle, missed-tick recovery, multi-worker
   double-firing) disproportionate to a first automation slice with no
   measured need for sub-minute precision. The accepted shape:
   - A new table stores schedules declaratively: case, parameter version
     (reusing the existing hierarchy-provenance hashes, not a new table, per
     the TS-3 decision record's clarification that no `parameter_versions`
     table exists or is needed), input variant, a range rule (fixed range for
     BESS-TS6-008, a rolling-range rule for BESS-TS6-009) and a cadence —
     never a hand-authored `system_case_json`, per the PRD.
   - Firing is "external invocation": a narrow, testable deep-module function
     resolves "which schedules are due at time T" and executes each due
     schedule through the exact same variant-run path TS-3 already built
     (staleness/coverage gates, immutable snapshot, `RunExecutor.execute`,
     TS-4 result indexing) — reusing infrastructure rather than duplicating
     it, per BESS-TS6-008's own framing. This function is invoked by a thin
     admin-gated endpoint (`POST /api/admin/schedules/run-due`) plus an
     equally thin CLI entry point, meant to be triggered by an OS-level
     scheduler (Windows Task Scheduler / cron) external to the application
     process. This keeps "which schedules fired and what they produced"
     fully unit-testable as a pure function of (current time, schedule rows,
     mocked run execution), with no live timer/thread to manage in tests.
   - Permissions: defining and executing schedules is **admin-only**,
     matching the existing TS-5 permission matrix precedent that groups
     automation/bulk operations (retention & cleanup, bulk migration sweeps)
     as admin-only rather than analyst-writable — a schedule silently
     consuming compute and hitting external connectors on a cadence carries
     more blast radius than a single analyst-triggered manual run. Viewing
     schedule-produced runs and their results uses the existing internal
     (analyst + admin) read path unchanged — they are runs like any other
     once produced, per BESS-TS6-008's "appear in run listings and
     comparisons like manual runs" criterion.
9. **Physical storage optimizations (partitioning, TimescaleDB) are
   confirmed out of scope**, unchanged from the PRD. The real database
   queried for Decision 1 shows 32 catalog sets and correspondingly small
   period/value row counts — no measured volume anywhere close to
   justifying a physical storage change. This will be revisited only if a
   future iteration measures a real bottleneck.

## PRD Corrections

No corrections are required to `docs/series_tiempo/iter6/prd.md` text. One
implementation clarification is recorded for downstream implementers:
BESS-TS6-007 refers to extending the "`programado`" data kind, but the
allowlist actually implemented in `app/time_series_catalog.py` uses the
English key `"programmed"` (part of the original `TIME_SERIES_DATA_KINDS`
set already accepted for TS-2/TS-3). BESS-TS6-007 must extend the existing
`"programmed"` key; it must not introduce a second, Spanish-named key.

## Acceptance Mapping

- Activation decision, explicitly recorded with justification (user story
  18): accepted as "start now", grounded in both the explicit product-owner
  instruction and measured real usage of the TS-2 through TS-5 model
  (Decision 1).
- Initial allowlist catalog, including what ships this iteration versus what
  stays future: decided as `scale_signal`, `resample`, `interpolate_gaps`,
  `combine_signals` shipping; `clip_negative_values`,
  `shift_timezone_display` and `derive_availability_from_outage_events`
  deferred (Decision 2), enforced via a code-level module registry
  (Decision 3).
- Output model (new set vs. derived revision, naming/versioning): decided as
  new set on first execution, new revision of the same set on regeneration,
  reusing the TS-2 version/revision scheme plus one new additive
  `data_kind = "derived"` value (Decision 4).
- Lineage contract (input sets, revisions/hashes, validated parameters,
  parameter schema version, implementation version): agreed as an extension
  of the existing `time_series_set_revisions.metadata_json` column plus
  reuse of the existing generic `validation_dependencies` table — no new
  tables (Decision 5).
- Derived-set staleness semantics, composing with TS-3 variant staleness and
  TS-5 fail-closed guarantees: agreed as two layers sharing the existing
  generic staleness-comparison mechanism, with one new dependency type to
  propagate "derived set is stale" into variant staleness before
  regeneration (Decision 6).
- First external connector target and test mocking strategy, keeping
  ingestion inside the source/set model: decided as a generic config-driven
  HTTP+JSON connector (no named vendor), landing through the existing
  `time_series_sources`/`time_series_sets` path with mocked-connector tests
  (Decision 7).
- Scheduling mechanism and its permission rules under the TS-5 permission
  matrix: decided as data-defined schedules fired by external invocation
  (admin-gated endpoint + CLI, triggered by an OS-level scheduler), with
  schedule definition/execution admin-only and result viewing on the
  existing internal read path (Decision 8).
- Physical storage optimizations confirmed out of scope until real volume is
  measured: confirmed (Decision 9), grounded in the actual measured row
  counts.
- PRD correction before downstream implementation begins: no PRD text
  correction needed; one issue-level clarification recorded above (the
  `"programmed"` vs. `"programado"` key).

## Verification

- Queried the real `energy_dispatch` PostgreSQL database (credentials from
  `.env`) directly: 41 `projects`, 34 `scenarios`, 20 `optimization_cases`,
  20 `scenario_versions`, 21 `runs`, 32 `time_series_sets` (`data_kind`
  distribution `real: 30`, `synthetic: 2`; `status` distribution
  `validated: 29`, `draft: 3`), 39 `time_series_set_revisions` rows across
  those 32 sets, 23 `case_input_variants`, 22 `case_time_series_bindings`,
  8 `hydraulic_time_series_sets` — grounding Decision 1's "real usage
  already exists" claim in measured data rather than assumption, and
  Decision 9's "no measured volume" claim in the same query.
- Confirmed in `app/time_series_catalog.py` that `TIME_SERIES_DATA_KINDS`
  already contains `"programmed"` (not `"programado"`), grounding the PRD
  Correction, and that `TIME_SERIES_SIGNAL_CATALOG` is exactly the
  code-level-registry-not-DB-table precedent Decision 3 follows.
- Confirmed in `app/persistence.py` that `time_series_set_revisions` already
  has a generic `metadata_json TEXT NOT NULL DEFAULT '{}'` column and that
  `validation_dependencies` already has the generic
  `(owner_type, owner_id, dependency_type, dependency_id, recorded_hash)`
  shape, grounding Decision 5's "no new tables" claim and Decision 6's "reuse
  the same mechanism for a new owner_type" claim.
- Confirmed in `app/persistence.py` that `case_time_series_bindings` binds by
  `time_series_set_id` only (no revision pin), grounding Decision 6's claim
  that regenerating a derived set's revision automatically flows into the
  existing variant-staleness check with no changes to how bindings resolve.
- Confirmed in `app/variant_staleness.py` (`evaluate_variant_staleness`) that
  the staleness comparator is already generic over dependency type/id, not
  hardcoded to variants, supporting its reuse for derived-set staleness in
  Decision 6 without modification.
- Confirmed in `app/auth.py` and `app/main.py` (`require_admin_user` gating
  `/api/admin/runs/rebuild-results` and the cleanup/retention endpoints) that
  admin-only gating is the existing precedent for automation/bulk operations,
  grounding Decision 8's permission choice in actual code rather than a new
  policy invented for TS-6.
- Confirmed in `requirements.txt` that no scheduler or task-queue dependency
  is present today, grounding Decision 8's rejection of an in-process
  scheduler.
- Confirmed via `docs/series_tiempo/roadmap_iteraciones_jerarquias_series.md`
  that no concrete external forecast/price-program vendor is named anywhere
  in the project's own documents, grounding Decision 7's choice of a generic,
  config-driven connector over inventing a vendor.

## Blocked by

None - can start immediately.
