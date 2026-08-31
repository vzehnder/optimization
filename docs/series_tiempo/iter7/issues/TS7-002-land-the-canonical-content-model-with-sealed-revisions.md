# TS7-002: Land The Canonical Content Model With Sealed Revisions

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (2.1, 2.3, 2.7, 10.1)

## What to build

Land the canonical content model in its own physical space - schema `ts_next` on
PostgreSQL, `_next` suffix on SQLite - beside the current tables, which stay
intact and remain the write source. Legacy and canonical children never share a
table, because the current writer deletes and recreates signals and periods on
some replacements and would destroy a backfill.

Deliver `time_series_sets` with `series_kind`, `visibility_scope` and
`owner_project_id`; `time_series_signals` as the stable identity;
`time_series_set_revisions`; `time_series_revision_signals` as the frozen
snapshot of unit, class, type, role, aggregation and metadata;
`time_series_periods`; `time_series_values`; `time_series_sources`; and
`time_series_revision_lineage`.

Deliver the atomic revision protocol as the only way content is written: one
transaction that creates the `building` revision under the set lock, reuses
identities by `series_key`, bulk-inserts the snapshot, validates integrity and
`value_count = signal_count * period_count`, computes the canonical hash in
streaming order, seals and moves `current_revision_id` together, and records
source, lineage, event and receipt. `content_hash` is null while `building`
(P-03). Triggers refuse any update or delete on a sealed revision and its
children; a correction is copy-on-write; only a sealed revision can be current.

A signal that disappears from a revision survives as a historical identity: it
leaves the current view, its associations read as incompatible and its bindings
go stale. It is never redirected to another signal of the same type.

## Acceptance criteria

- [x] The canonical tables live in `ts_next` / `_next` and no legacy table gains a canonical child row.
- [x] Creating or editing content always produces a complete new set revision; there is no in-place value edit path.
- [x] An interrupted publication leaves no partially visible revision: it appears whole or not at all (AC-ESP-10).
- [x] `content_hash` is null while the revision is `building` and non-null once sealed (P-03).
- [x] `UPDATE` and `DELETE` against a sealed revision or its children fail on both engines, with the same observable result.
- [x] `current_revision_id` can only point at a sealed revision.
- [x] The canonical hash is computed in streaming over `ordinal, period_index` and two identical contents produce the same hash on both engines.
- [x] `value_count = signal_count * period_count` is enforced, coverage is ordered and periods do not overlap.
- [x] Identities are reused by `series_key` and an archived identity is never recycled.
- [x] A signal absent from the current revision remains readable as history and is not redirected to another signal.

## Implementation evidence

- `app/time_series_canonical.py` emits the canonical DDL per engine
  (`ts_next.*` on PostgreSQL, `*_next` on SQLite), the portable guard triggers,
  the streaming `CanonicalContentHash` and the payload validators with their
  stable codes. `app/persistence.py` carries the atomic revision protocol
  (`publish_canonical_set_revision`), the canonical reads, the identity history
  and the archive transition.
- `tests.test_ts7_002_canonical_content_model`: 14 SQLite/domain tests plus 2
  environment-gated PostgreSQL tests, all passing.
- The atomicity test reads the uncommitted state from inside the dying
  publication, so it observes the `building` revision with a null
  `content_hash` and its four periods mid-flight and proves they are gone after
  the rollback; it cannot pass without a real rollback.
- Cross-engine equality of the canonical hash is asserted by publishing the
  same content on SQLite and on the development PostgreSQL and comparing the
  digests. `value_numeric` and `duration_hours` are `DOUBLE PRECISION` on
  PostgreSQL, because `REAL` is single precision there and would break the
  hash computed over the stored snapshot.
- Full Python regression: 869 tests pass with no failures and no skips, with
  `POSTGRES_TEST_DATABASE_URL` pointed at the development database.
- Python bytecode compilation and `git diff --check` pass.

## Carried to later slices

These are named here rather than silently dropped:

- The composite foreign key
  `(owner_linkable_object_id, owner_project_id) -> linkable_objects(id, project_id)`
  cannot be installed yet; the column exists and the `CHECK` already closes the
  `object_specific` shape. TS7-003 lands the register and the reference.
  **Landed**: TS7-003 installs it, inline for a new canonical space and through
  an idempotent `ALTER TABLE` on a PostgreSQL database that predates it.
- `current_revision_id` is guarded by a trigger on both engines instead of a
  composite foreign key, because the reference is circular with
  `time_series_set_revisions` and SQLite cannot `ALTER TABLE ... ADD CONSTRAINT`.
  The trigger enforces both membership and sealed state, so the observable
  result is the same on both engines.
- Link events and the durable idempotency receipt of chapter 9.7 land with the
  ledgers in TS7-004 and with the ingestion flow in TS7-010 and TS7-011. This
  slice records source, lineage and the per-revision validation payload.
- The `unchanged` short-circuit of chapter 9.7, which skips the revision when
  contract and hash already match the current one, belongs to that same
  publication flow with its ETag and idempotency layer, and is deliberately not
  implemented here: this slice always publishes a complete new revision.

## Blocked by

- [TS7-001: Seed The Persistent Classification Catalogs And Compatibility Matrix](TS7-001-seed-the-persistent-classification-catalogs-and-compatibility-matrix.md)
