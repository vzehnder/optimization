# TS7-012: Bind, Read And Archive An Object Specific Series

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (7.2, 7.3, 7.10, 7.12)

## What to build

Complete the object-specific path end to end: make the series executable, prove
it is invisible to everyone else, and retire it without losing history.

An object-specific series binds directly to its own object at an exact revision
and hash, with no intermediate catalog association fabricated to satisfy the
binding. It becomes apt for binding only once it has a sealed revision.

Enforce the read separation structurally, not by filtering: the series never
appears in `catalog/inputs`, never appears as a candidate for another object,
and no combination of filters surfaces it. This is the guarantee the whole
second path rests on, so it is proven against the query layer rather than the
presentation layer.

Archiving keeps the identity, its revisions and its past bindings resolvable.
Promotion toward the catalog is an explicit copy that creates a new generic
identity; it is not a flag flip on the existing row.

## Acceptance criteria

- [x] The series is not selectable until it has a sealed revision (AC-ESP-02).
- [x] Its binding is created with no intermediate catalog association (AC-ESP-07).
- [x] It never appears in `catalog/inputs` nor as a candidate for another object, under any filter combination (AC-ESP-06).
- [x] Archiving preserves history, revisions and past bindings (AC-ESP-08).
- [x] Copying toward the catalog creates a new generic identity and does not mutate or reclassify the object-specific row (7.12).
- [x] No result descriptor appears in `catalog/inputs` or is selectable as a binding source (AC-LEG-03).
- [x] The separation holds at the query layer: a direct canonical query, not only the API, returns no object-scoped row through the catalog path.

## Delivered surface

- The existing binding prevalidation and atomic batch resources now accept a
  sealed `object_specific` signal only for its exact owner. The stored binding
  carries `source_kind = object_specific`, the owner FK and a null catalog
  association; its public detail exposes the same provenance and exact hash.
- `POST OBJECT_ROOT/object-series/{signal_id}/archive` retires the set and its
  sole signal under `If-Match` and a mandatory reason. It preserves the current
  pointer, sealed revisions, values and historical binding rows. Reads and
  previews remain available while metadata edits, ingestion, new bindings and
  execution fail closed.
- The canonical content model exposes disjoint
  `catalog_time_series_signals` and
  `object_specific_time_series_signals` views on both engines. The catalog API
  continues to read only its catalog projection, and object candidates reject
  a local signal id as nonexistent regardless of filters.
- The catalog writer refuses an object-specific `set_id` with
  `TS_SET_KIND_MISMATCH`. Chapter 7.12 deliberately exposes no promotion API in
  this cut; a future catalog incorporation is already proven to create a new
  generic set/signal/revision and record
  `object_specific_catalog_copy` lineage without changing the local source.
- Result descriptors remain on the separate read-only result resource and
  have neither a canonical input signal id nor binding capabilities, preserving
  the TS7-006 `AC-LEG-03` contract.

## Evidence

- N1/N2: `tests/test_ts7_012_object_specific_binding_and_archive.py`, eight
  SQLite HTTP/query contracts mirrored by the same opt-in PostgreSQL class
  (`POSTGRES_TEST_DATABASE_URL`).
- Focused TS7-006/008/010/011/012 regression: `133` tests passed, `58` skipped
  because PostgreSQL is not configured.
- Complete Python regression: `1088` tests passed, `88` optional tests skipped.
- Generated contract: `npm run api:check` passes; TypeScript and ESLint pass,
  targeted generated-file Prettier passes, Vitest passes `133` tests and the
  production build succeeds. The repository-wide Prettier phase still reports
  25 pre-existing files outside this slice.
- No N4 is applicable: chapter 11.1 keeps the React journey behind C6, so
  browser evidence remains with TS7-020 and TS7-021.

## Blocked by

- [TS7-008: Pin A Binding To An Exact Revision And Detect Staleness](TS7-008-pin-a-binding-to-an-exact-revision-and-detect-staleness.md)
- [TS7-010: Create An Object Specific Series And Ingest It By API](TS7-010-create-an-object-specific-series-and-ingest-it-by-api.md)
