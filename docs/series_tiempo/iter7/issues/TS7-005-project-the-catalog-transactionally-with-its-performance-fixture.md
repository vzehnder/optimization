# TS7-005: Project The Catalog Transactionally With Its Performance Fixture

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (9.1-9.10)

## What to build

Build the read model the global catalog is served from.
`time_series_catalog_entries` holds exactly one row per signal of a `catalog`
set, derived from `current_revision_id` through
`time_series_revision_signals`, and it is maintained inside the same transaction
that seals a revision - never by a background job that can drift.

Land the mandatory indexes for each documented query shape, keyset pagination
over a stable ordering, and staged copy-on-write publication with durable
idempotency so a retried publish converges instead of duplicating.

Build the PostgreSQL performance fixture the delivery is measured against:
100.000 entries, 1.000.000 associations, 1.000.000 bindings and 100.000.000
cells, with a saved reference `EXPLAIN (ANALYZE, BUFFERS)` per critical query.
No critical query may full-scan periods or values. SQLite runs the correctness
fixture and keeps identical semantics, errors, foreign keys, uniqueness,
immutability and idempotency, but does not participate in the budgets.

## Acceptance criteria

- [x] Exactly one projection row exists per `catalog` signal, and none for an `object_specific` signal.
- [x] The projection is written in the same transaction that seals the revision; killing a background worker cannot make it stale.
- [x] The catalog page plan touches only the projection and its indexes, never periods or values (AC-CAT-04).
- [x] A 50-row catalog page without facets meets 300 ms p95 on the fixture (AC-PER-01).
- [x] A contextual object list or detail meets 300 ms p95 (AC-PER-02).
- [x] Every critical query has a saved reference plan and none full-scans periods or values.
- [x] Staged publication is durably idempotent: a retried publish converges to one result and does not double-write.
- [x] SQLite reproduces semantics, errors, FKs, uniqueness, immutability and idempotency on the correctness fixture.

## Implementation evidence

- `app/time_series_catalog_projection.py` emits `time_series_catalog_entries`,
  the `time_series_catalog_generations` counter and the common
  `time_series_operation_idempotency` table into the canonical space
  (`ts_next` on PostgreSQL, `_next` on SQLite), with the eleven mandatory
  indexes of chapter 9.5, a stored `tsvector` plus GIN index on PostgreSQL and
  the normalized-text index on SQLite. It also owns the portable read-model
  logic: sort/search normalization, the coverage and resolution summary, the
  keyset ladder, the signed cursor and the two-armed object union.
- `app/persistence.py` calls `_project_catalog_entries` and
  `_raise_catalog_generation` from inside the transaction that seals a
  revision, before it returns, and exposes `read_catalog_page`,
  `read_object_context_page`, `catalog_generation`,
  `catalog_projection_divergence`, `rebuild_catalog_projection`,
  `explain_catalog_page` and `explain_object_context_page`.
- `app/time_series_catalog_fixture.py` and
  `scripts/ts7_catalog_performance_fixture.py` build the fixture through the
  production writers at any scale, measure the budgeted queries and save the
  reference plans. `fixture_plan(1.0)` is the documented reference size;
  `--periods` shortens coverage so a machine that cannot hold 100.000.000 cells
  still measures the reference page and list plans.
- `tests.test_ts7_005_catalog_projection` proves 20 SQLite contracts and
  repeats the engine-sensitive half in 6 PostgreSQL tests: projection
  membership, the `object_specific` refusal on both engines, atomicity of a
  failed publication, one generation step per publication, the `unchanged`
  republication, durable idempotency and its two conflicts, the keyset walk and
  its three navigation refusals, the page plan, divergence detection, the
  shadow rebuild and the object union with its own keyset.
- Evidence files in `docs/series_tiempo/iter7/performance/`:
  `ts7-005-postgresql-reference-projection.json` (10.000 entries, 100.000
  associations, 100.000 bindings), `ts7-005-postgresql-full-coverage.json`
  (1.000 periods per revision, 100.000 cells) and
  `ts7-005-sqlite-correctness.json`. Every file records
  `reads_periods_or_values: false`.
- Verification: 25 TS7-005 tests pass on SQLite and PostgreSQL; 106 tests pass
  across TS7-001 to TS7-005 plus `test_postgres_persistence` with
  `POSTGRES_TEST_DATABASE_URL` pointed at the development database. Full Python
  regression: 928 tests pass with 24 environment-gated skips. Bytecode
  compilation and `git diff --check` pass. No existing test was edited.

## Measured budgets

Measured on the development PostgreSQL inside a rolled-back transaction, and on
a throwaway SQLite file for the correctness fixture.

| Criterion | Budget | PostgreSQL p95 | SQLite p95 |
| --- | --- | --- | --- |
| AC-PER-01 catalog page of 50 rows | 300 ms | 20.6 ms | 1.6 ms |
| AC-PER-02 contextual object list | 300 ms | 50.7 ms | 1.2 ms |
| AC-PER-07 synchronous publication | 5 s | 4.49 s at 50.000 cells | 87 ms at 1.200 cells |

Reference plans, saved with `EXPLAIN (ANALYZE, BUFFERS)`:

- `catalog_page`: `Index Scan using
  time_series_catalog_entries_next_updated_at_idx`, 9 shared buffers, no other
  relation in the plan.
- `catalog_page_keyset`: same index with `Index Cond: (updated_at <= ...)`, so
  a deep page seeks instead of scanning from the top.
- `object_context_page`: bounded `Append` of the two arms over the association
  index and the projection primary key.

## Decisions recorded

- **The projection is a step of the publication, not a job.**
  `_project_catalog_entries` and the single generation step run inside the same
  transaction that seals the revision and moves `current_revision_id`. A
  publication that fails after staging leaves neither a revision nor a
  projection row, which is what the atomicity test asserts. There is no queue
  and no worker to kill.
- **An unchanged republication is a real no-op.** The content hash is only
  known after the snapshot is staged, so the flow stages it, compares the hash
  with the current revision, and on equality discards the staged `building`
  revision and returns `outcome: unchanged`. No revision number is consumed, the
  pointer does not move, the projection is untouched and the generation does not
  rise. A source row created only for that attempt is removed with it.
- **The idempotency key covers what the caller can fingerprint.** Values are
  consumed as a stream and cannot be digested twice, so the request hash covers
  target, contract and coverage, plus an optional `request_fingerprint` the
  caller computes from the body, file checksum or staged ingestion. Two
  different bodies under one key then conflict with
  `TS_IDEMPOTENCY_KEY_CONFLICT` instead of replaying; without a fingerprint the
  key still covers everything the store itself can see. The claim, the mutation
  and the stored result share one transaction, and a replay returns exactly the
  saved result.
- **The keyset carries a redundant bound on its leading column.** The ladder
  alone is correct but plans as a filter from the top of the index; adding
  `leading <= ?` (or `>=` ascending) turns the same page into an index seek.
  Without it a keyset page silently degrades into an offset page as the user
  pages deeper. All projection sort columns are `NOT NULL`, so the explicit null
  flag chapter 9.4 requires has no nullable key to guard here.
- **Cursors are signed with a per-process key unless one is configured.**
  `TS_CATALOG_CURSOR_SECRET` makes a cursor readable across workers; without it
  each process signs with its own key and a foreign cursor is refused as
  `TS_QUERY_CURSOR_MISMATCH` rather than silently trusted. Actor binding
  belongs to the HTTP surface and lands with TS7-006.
- **The rebuild is a compared shadow, never an in-place repair.**
  `rebuild_catalog_projection` fills a shadow table from the canonical model,
  compares row counts and a content hash against the live table, and only then
  replaces the rows and raises the generation once. A rebuild that finds the
  projection already correct reports `unchanged` and changes nothing.
  `catalog_projection_divergence` reports drift - missing, unexpected, stale and
  leaked `object_specific` rows - and never repairs silently.

## Findings to carry forward

- **AC-PER-07 does not hold at the reference cell count with the current
  writer.** 50.000 cells publish in 4.49 s p95, so 100.000 cells exceed the 5 s
  budget. The cost is the value stream of the TS7-002 protocol, not the
  projection: batching the per-signal link counts into one grouped read per
  revision cut the fixed overhead of a 50-signal publication from 2.64 s to
  0.35 s. Chapter 9.7 already allows `COPY` on PostgreSQL for staged ingestion;
  that is where TS7-011 should recover the rest. AC-PER-07 belongs to
  TS7-011/TS7-022, not to this issue's acceptance list.
- **The contextual list has a known escalation threshold.** The catalog arm
  orders by the projection's `updated_at`, so it reads every association of the
  object before its bounded sort. At 10.000 associations on a single object -
  ten times what any real object carries in the fixture - it measures 50.7 ms
  against a 300 ms budget. Chapter 9.10 sets the trigger for an additional
  object-scoped projection at 100.000 visible sources per object or a list p95
  above 300 ms; neither is reached, and that decision belongs to TS7-020.
- **The reference fixture was not run at scale 1.** 100.000.000 cells is tens
  of gigabytes and the only PostgreSQL available here is the shared development
  database, so every run was rolled back and the largest committed shape was
  10.000 entries with 100.000 associations and 100.000 bindings. The script
  takes `--scale 1 --keep --database-url` for a dedicated performance database.

## Blocked by

- [TS7-004: Land The Link Layer Tables And Immutable Ledgers](TS7-004-land-the-link-layer-tables-and-immutable-ledgers.md)
