# TS7-002: Land The Canonical Content Model With Sealed Revisions

Status: Todo
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

- [ ] The canonical tables live in `ts_next` / `_next` and no legacy table gains a canonical child row.
- [ ] Creating or editing content always produces a complete new set revision; there is no in-place value edit path.
- [ ] An interrupted publication leaves no partially visible revision: it appears whole or not at all (AC-ESP-10).
- [ ] `content_hash` is null while the revision is `building` and non-null once sealed (P-03).
- [ ] `UPDATE` and `DELETE` against a sealed revision or its children fail on both engines, with the same observable result.
- [ ] `current_revision_id` can only point at a sealed revision.
- [ ] The canonical hash is computed in streaming over `ordinal, period_index` and two identical contents produce the same hash on both engines.
- [ ] `value_count = signal_count * period_count` is enforced, coverage is ordered and periods do not overlap.
- [ ] Identities are reused by `series_key` and an archived identity is never recycled.
- [ ] A signal absent from the current revision remains readable as history and is not redirected to another signal.

## Blocked by

- [TS7-001: Seed The Persistent Classification Catalogs And Compatibility Matrix](TS7-001-seed-the-persistent-classification-catalogs-and-compatibility-matrix.md)
