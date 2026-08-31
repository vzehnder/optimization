# TS7-016: Backfill Catalogs, Objects And Canonical Content (C2-C3)

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (10.4, 10.5, 10.6)

## What to build

Fill the canonical model from the current one, idempotently, resumably and
verifiably by hash - never in a big bang, and never inventing what cannot be
proven.

Converge the seeds of units, classes, types, roles and rules, then materialize
`global_signal_slots`, `components` and `linkable_objects` with deterministic
keys and no fuzzy matching. An ambiguous object reference produces
`TS_MIGRATION_OBJECT_AMBIGUOUS`; the most similar candidate is never chosen. A
component is never created just because `entity_id` holds a plausible string.

Then backfill content per set. Preserve id, name, version, owner, state, actor
and timestamps; `project_id` becomes `owner_project_id`; the set starts at
`visibility_scope = 'project'`; `data_kind`, `timezone` and `content_hash` remain
compatibility caches; `signal_key` becomes `series_key`; and unit, class, type,
role, aggregation and metadata freeze into `time_series_revision_signals`. The
current pointer moves only after sealing and checking both hashes. Deleted ids
are neither invented nor reassigned, and two rows of one set producing the same
`series_key` leave that set quarantined.

An unknown `signal_key`, class or unit does not become a canonical type: the set
and its content are preserved, a blocking anomaly is raised if it participates
in an active binding, and an administrator must map it or create a complete
custom type. Legacy revisions that were lightweight events are not inflated into
invented snapshots - `legacy_unmaterialized` marks inherited history without
data, never executable (P-05). Existing object-scoped series are classified as
`object_specific` rather than pushed into the global catalog.

## Acceptance criteria

- [ ] A second run over an unchanged source creates no rows, alters no mappings and repeats the manifest (AC-MIG-02).
- [ ] An ambiguous object reference produces `TS_MIGRATION_OBJECT_AMBIGUOUS` and no object is created from a plausible string (AC-MIG-03 object half).
- [ ] Unknown keys, classes or units never become canonical types automatically and require a recorded administrative decision (AC-MIG-07).
- [ ] The current pointer moves only after the revision is sealed and both hashes check.
- [ ] Deleted ids are neither invented nor reassigned.
- [ ] Two rows of one set producing the same `series_key` leave that set quarantined instead of silently merged.
- [ ] A lightweight legacy revision event becomes `legacy_unmaterialized`, is never executable, and is not inflated into a fabricated snapshot (P-05).
- [ ] Existing object-scoped series are classified `object_specific` and do not enter the global catalog (10.6).
- [ ] The backfill is resumable from a checkpoint and verifiable by hash per set.

## Blocked by

- [TS7-005: Project The Catalog Transactionally With Its Performance Fixture](TS7-005-project-the-catalog-transactionally-with-its-performance-fixture.md)
- [TS7-015: Take The C0 Inventory, Manifest And Proven Restore](TS7-015-take-the-c0-inventory-manifest-and-proven-restore.md)
