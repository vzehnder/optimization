# TS7-012: Bind, Read And Archive An Object Specific Series

Status: Todo
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

- [ ] The series is not selectable until it has a sealed revision (AC-ESP-02).
- [ ] Its binding is created with no intermediate catalog association (AC-ESP-07).
- [ ] It never appears in `catalog/inputs` nor as a candidate for another object, under any filter combination (AC-ESP-06).
- [ ] Archiving preserves history, revisions and past bindings (AC-ESP-08).
- [ ] Copying toward the catalog creates a new generic identity and does not mutate or reclassify the object-specific row (7.12).
- [ ] No result descriptor appears in `catalog/inputs` or is selectable as a binding source (AC-LEG-03).
- [ ] The separation holds at the query layer: a direct canonical query, not only the API, returns no object-scoped row through the catalog path.

## Blocked by

- [TS7-008: Pin A Binding To An Exact Revision And Detect Staleness](TS7-008-pin-a-binding-to-an-exact-revision-and-detect-staleness.md)
- [TS7-010: Create An Object Specific Series And Ingest It By API](TS7-010-create-an-object-specific-series-and-ingest-it-by-api.md)
