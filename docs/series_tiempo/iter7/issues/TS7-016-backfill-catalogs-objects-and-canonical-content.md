# TS7-016: Backfill Catalogs, Objects And Canonical Content (C2-C3)

Status: In Review
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

- [x] A second run over an unchanged source creates no rows, alters no mappings and repeats the manifest (AC-MIG-02).
- [x] An ambiguous object reference produces `TS_MIGRATION_OBJECT_AMBIGUOUS` and no object is created from a plausible string (AC-MIG-03 object half).
- [x] Unknown keys, classes or units never become canonical types automatically and require a recorded administrative decision (AC-MIG-07).
- [x] The current pointer moves only after the revision is sealed and both hashes check.
- [x] Deleted ids are neither invented nor reassigned.
- [x] Two rows of one set producing the same `series_key` leave that set quarantined instead of silently merged.
- [x] A lightweight legacy revision event becomes `legacy_unmaterialized`, is never executable, and is not inflated into a fabricated snapshot (P-05).
- [x] Existing object-scoped series are classified `object_specific` and do not enter the global catalog (10.6).
- [x] The backfill is resumable from a checkpoint and verifiable by hash per set.

## Blocked by

- [TS7-005: Project The Catalog Transactionally With Its Performance Fixture](TS7-005-project-the-catalog-transactionally-with-its-performance-fixture.md)
- [TS7-015: Take The C0 Inventory, Manifest And Proven Restore](TS7-015-take-the-c0-inventory-manifest-and-proven-restore.md)

## Delivery notes

C2 and C3 are domain operations on the store, not HTTP endpoints: they are
operator-controlled phases, and `open_migration_phase` already refuses to open
one without a proven C0 that still describes the source.

C2 converges the classification seeds - dimensions, units, data classes,
semantic types, binding roles, object types and the compatibility matrix - with
`INSERT ... ON CONFLICT DO NOTHING` over a contract that is asserted first, so a
divergence raises `ClassificationContractDriftError` instead of quietly
rewriting a seeded row. It then materializes the closed object register with
deterministic keys: the `global:system` slot of every project, one component per
`project_id + component_type + component_key` group whose key and type agree in
every authoritative appearance (cases and drafts), and the hydraulic base
entities by their real primary key. Case copies of a hydraulic entity are never
registered, `bus` is topology rather than a link target, and a component is
never created because `entity_id` holds a plausible string: only an appearance
in a case or draft document is authoritative. A key that appears with two types
stops the phase with `TS_MIGRATION_OBJECT_AMBIGUOUS`, writes the anomaly and
leaves the register untouched - the most similar candidate is never chosen. The
C2 manifest carries only resulting state, never run-local ids or timestamps, so
a repetition over an unchanged source reproduces it byte for byte and creates no
row and no mapping.

C3 walks the legacy sets in ascending id, in independently atomic batches, and
checkpoints `last_set_id` on the run so an interrupted backfill resumes on the
same `migration_run_id`. Per set it preserves id, name, version, owner, status,
actor and timestamps; `project_id` becomes `owner_project_id`; the set starts at
`visibility_scope = 'project'`; `data_kind`, `timezone` and `content_hash` stay
as compatibility caches; `signal_key` becomes `series_key`; and unit, class,
semantic type, role, aggregation and metadata freeze into
`time_series_revision_signals`. Legacy sources are preserved with their own
identity before the set that references them. The legacy hash is recomputed from
the observed source and the canonical hash is streamed from the rows actually
written; the revision is sealed only when both check, and only then does
`current_revision_id` move. An id that was already deleted stays a hole - the
identity sequences are synchronized so no later insert reassigns it - and two
rows of one set that produce the same `series_key` leave the set quarantined,
visible and pointerless, instead of being merged.

Legacy revisions are events, not snapshots, so only the current one can be
proven. History is preserved as `legacy_unmaterialized` with its id, number,
legacy hash, source, metadata, actor and date, chained by `supersedes_revision_id`
along the known chronology, and it never gains canonical children. Earlier
revisions are deliberately not reconstructed: the current model retains neither
the source nor a complete diff chain that would make a reconstruction provable,
and fabricating values to satisfy the schema would be a worse loss of lineage
than declaring the limit (P-05). When the stored hash of the latest revision no
longer matches the observed points, the set gets a `migration_baseline` revision
and the previous one stays unmaterialized - unless the set is consumed by a
binding, where the mismatch is blocking and nothing is sealed.

An unmaterialized revision is not executable anywhere: it cannot be current, a
binding cannot pin it - the create prevalidation finds no signal contract for it
and answers `TS_COMPAT_SIGNAL_UNAVAILABLE` - and it cannot be previewed. The
preview used to answer "not found" for it, which is a different and false claim
about a revision the history shows: it now answers
`TS_PREVIEW_REVISION_UNAVAILABLE`, the same refusal it already gave a revision
that is not sealed. That is the only behavior outside the migration surface this
issue changes; no route, permission or navigation moved.

An unknown `signal_key`, class or unit never becomes a canonical type. The set
and its legacy content are preserved, the set is quarantined without a pointer,
and the anomaly stays open until
`resolve_time_series_migration_classification` records an administrative
decision - actor, reason and the exact mapping, validated dimensionally against
the seeded catalogs - after which the same run completes. The finding is
blocking when the set participates in a binding and informational when it does
not.

Existing sets are presumed `catalog`. A set only becomes `object_specific` when
every condition of 10.6 is provable: one signal, one valid key, one stable
object of the same project across signal, source and bindings, and a provenance
that explicitly declares a local birth. Anything that merely looks local raises
`TS_MIGRATION_OBJECT_SPECIFIC_REVIEW_REQUIRED` rather than being hidden from the
catalog, and a proven local definition stays structurally outside the global
catalog projection.

Evidence: `tests/test_ts7_016_c2_c3_backfill.py`, seventeen N1 contracts on
SQLite plus an opt-in PostgreSQL mirror. The mirror runs C0, C2 and C3 over the
development database inside a rolled-back transaction; it first explains what C0
reports about rows this slice does not own - five legacy bindings whose signal
no longer resolves in its set - because C0 refuses to sign a manifest that
passes over a structural difference in silence. The full Python suite passes
(1,173 tests, 107 skipped opt-in PostgreSQL mirrors). No route, permission or
navigation changed, so the generated OpenAPI and TypeScript contracts are
untouched; the only externally visible difference is the preview refusal code
for an unmaterialized revision, which no released client can reach yet.
