# TS7-005: Project The Catalog Transactionally With Its Performance Fixture

Status: Todo
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

- [ ] Exactly one projection row exists per `catalog` signal, and none for an `object_specific` signal.
- [ ] The projection is written in the same transaction that seals the revision; killing a background worker cannot make it stale.
- [ ] The catalog page plan touches only the projection and its indexes, never periods or values (AC-CAT-04).
- [ ] A 50-row catalog page without facets meets 300 ms p95 on the fixture (AC-PER-01).
- [ ] A contextual object list or detail meets 300 ms p95 (AC-PER-02).
- [ ] Every critical query has a saved reference plan and none full-scans periods or values.
- [ ] Staged publication is durably idempotent: a retried publish converges to one result and does not double-write.
- [ ] SQLite reproduces semantics, errors, FKs, uniqueness, immutability and idempotency on the correctness fixture.

## Blocked by

- [TS7-004: Land The Link Layer Tables And Immutable Ledgers](TS7-004-land-the-link-layer-tables-and-immutable-ledgers.md)
