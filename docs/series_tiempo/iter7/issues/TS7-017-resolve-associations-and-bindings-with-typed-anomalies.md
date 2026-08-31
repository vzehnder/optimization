# TS7-017: Resolve Associations And Bindings With Typed Anomalies (C4)

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (10.7, 10.2 C4)

## What to build

Convert the textual references the current bindings carry into real, typed,
reauthorized links - or refuse and record why.

Resolve each legacy `entity_type`/`entity_id` pair to exactly one
`linkable_object` through the registry built in C2. Reauthorize every reference
against the project invariants that now exist, and re-evaluate every binding
through the single compatibility evaluator. A binding the migrator cannot
resolve by foreign key and by evaluator is not declared valid.

An ambiguous reference produces a typed anomaly and leaves its variant
fail-closed. The migrator does not pick the closest-looking candidate to keep a
count moving; a variant that cannot be resolved is one that must not execute.

Before C6 can be considered, zero blocking anomalies remain open and 100% of
active bindings are either revalidated or retired with a recorded reason.

## Acceptance criteria

- [ ] An ambiguous reference produces an anomaly and leaves the variant fail-closed; the closest candidate is never chosen (AC-MIG-03).
- [ ] Zero blocking anomalies are open and 100% of active bindings are revalidated or retired before C6 (AC-MIG-04).
- [ ] Every migrated binding resolves by real FK and passes the single evaluator; neither check is skipped.
- [ ] Anomalies are typed and carry severity, evidence, resolution and actor.
- [ ] Re-running C4 over an unchanged source creates no rows and alters no mappings.
- [ ] A retired binding records its reason and remains consultable as history.
- [ ] Migrated associations respect the active uniqueness on `signal_id + linkable_object_id + binding_role_id`.

## Blocked by

- [TS7-008: Pin A Binding To An Exact Revision And Detect Staleness](TS7-008-pin-a-binding-to-an-exact-revision-and-detect-staleness.md)
- [TS7-016: Backfill Catalogs, Objects And Canonical Content (C2-C3)](TS7-016-backfill-catalogs-objects-and-canonical-content.md)
