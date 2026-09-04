# TS7-018: Compare Canonical Reads In Shadow And Prove Convergence (C5)

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (10.2 C5, 10.3, 10.8, 10.9)

## What to build

Prove the canonical reads are right before they serve any traffic, and prove the
migrator has stopped moving.

Run canonical reads in shadow over a wide sample and compare them against the
legacy reads on semantics, counts, values, hashes, authorization and lineage. In
the same phase, compare the persisted projection against the
`TIME_SERIES_SIGNAL_CATALOG` Python registry, which is the last check before the
database becomes authoritative. Drain the dirty-roots journal with a short
mutation pause so the comparison is taken against a settled source.

Convergence is the gate: a final run over an unmutated source creates zero rows,
changes zero mappings and reproduces the same manifest. Any single shadow
difference is a zero-tolerance rollback trigger, not a finding to triage later.

## Acceptance criteria

- [x] Shadow comparison shows no difference in semantics, counts, values, hashes, authorization or lineage (AC-MIG-05).
- [x] The final run demonstrates convergence: zero new rows, zero mapping changes and the same manifest (AC-MIG-02).
- [x] The persisted projection matches the `TIME_SERIES_SIGNAL_CATALOG` registry, and a divergence stops the phase.
- [x] The dirty-roots journal drains to empty under a short mutation pause and the comparison runs against the settled source.
- [x] The sample is wide enough to cover every set state, every object family and both `series_kind` values, and its selection is recorded.
- [x] A single shadow difference halts the advance and is reported as a rollback trigger.
- [x] Legacy hydraulic series and their on-demand migration keep working throughout the phase (AC-LEG-01 read half).

## Blocked by

- [TS7-017: Resolve Associations And Bindings With Typed Anomalies (C4)](TS7-017-resolve-associations-and-bindings-with-typed-anomalies.md)

## Delivery notes

C5 is the operator-controlled `verify_time_series_c5_shadow` store operation and
cannot open until C4 is proven and the C0 recovery point still describes the
source it would roll back to. It **settles, compares and proves; it never
repairs**: chapter 9.10 gives reconciliation the job of detecting divergence,
so a projection C5 finds stale is reported, not rebuilt behind the operator.

It first takes a short legacy mutation pause and drains the dirty-roots journal
to zero, so every read that follows sees one settled source. The pause is
process state rather than a table - it must be impossible to leave behind in the
database after a crash - and it refuses `import_time_series_catalog_set`,
`replace_time_series_set_source`, `upsert_case_time_series_binding` and
`migrate_hydraulic_time_series_set` with `TS_MIGRATION_MUTATION_PAUSED` while
every legacy read keeps serving. It is released in a `finally`, whether the
phase proves or stops.

The sample is stratified by `series_kind`, set state and object family, and the
whole stratum map is recorded in the manifest beside the selected set and
binding ids. The default selection is every set; a narrower explicit `set_ids`
is allowed and is then checked against that same map, so a selection that misses
a stratum the source actually carries stops the phase with
`TS_MIGRATION_SAMPLE_INCOMPLETE` instead of quietly narrowing what "no
difference" means.

Each migrated set is compared on all six dimensions of chapter 10.2 -
semantics, counts, values, hashes, authorization and lineage - between the
legacy read and the canonical one, with the legacy unit symbol resolved against
`measurement_units` so `USD/MWh` and `usd_per_mwh` are the same claim. Bindings
re-read the C4 receipt rather than re-deriving it, and add the one check the
receipt cannot make: that each canonical binding still points at the legacy set
its reference named. The persisted projection is compared against the
`TIME_SERIES_SIGNAL_CATALOG` registry contract and against the canonical model,
and a leaked `object_specific` row is reported on its own authorization
dimension. A canonical set whose legacy row can no longer be read is a lineage
difference, not a crash.

Any single difference is fatal: the run is recorded `stopped`, every difference
is persisted as a blocking, open, typed C5 anomaly, and `MigrationPhaseStopped`
carries `rollback_trigger=True`. Because the manifest holds only resulting state
- never drained counts, run ids or timestamps - a repeat over an unmutated
source reproduces it byte for byte with zero new rows and zero mapping changes,
which is the convergence gate itself.

Landing C5 surfaced one real defect it is designed to catch: C4 wrote the link
tables directly without moving the projection's `association_count` and
`binding_count`, which chapter 9.3 requires in the same transaction as the
source change. `_refresh_catalog_link_counts` now does that for association
materialization, binding migration and binding retirement, so the migrator no
longer creates the divergence its own verification phase would stop on.

Evidence: `tests/test_ts7_018_c5_shadow_convergence.py`, thirteen always-on
SQLite N1/N6 contracts plus an opt-in PostgreSQL mirror. The focused TS-7
regression passes (360 tests, 102 skipped PostgreSQL mirrors) and the full
Python suite passes (1,194 tests, 109 skipped opt-in mirrors). No HTTP,
permission, OpenAPI, frontend or navigation contract changed, and the TS-7
pre-C6 visibility rule of chapter 11.1 leaves no browser surface to verify.
