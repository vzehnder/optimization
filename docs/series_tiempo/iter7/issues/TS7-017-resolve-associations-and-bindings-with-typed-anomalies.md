# TS7-017: Resolve Associations And Bindings With Typed Anomalies (C4)

Status: In Review
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

- [x] An ambiguous reference produces an anomaly and leaves the variant fail-closed; the closest candidate is never chosen (AC-MIG-03).
- [x] Zero blocking anomalies are open and 100% of active bindings are revalidated or retired before C6 (AC-MIG-04).
- [x] Every migrated binding resolves by real FK and passes the single evaluator; neither check is skipped.
- [x] Anomalies are typed and carry severity, evidence, resolution and actor.
- [x] Re-running C4 over an unchanged source creates no rows and alters no mappings.
- [x] A retired binding records its reason and remains consultable as history.
- [x] Migrated associations respect the active uniqueness on `signal_id + linkable_object_id + binding_role_id`.

## Blocked by

- [TS7-008: Pin A Binding To An Exact Revision And Detect Staleness](TS7-008-pin-a-binding-to-an-exact-revision-and-detect-staleness.md)
- [TS7-016: Backfill Catalogs, Objects And Canonical Content (C2-C3)](TS7-016-backfill-catalogs-objects-and-canonical-content.md)

## Delivery notes

C4 is exposed as the operator-controlled `backfill_time_series_c4` store
operation and cannot open until C3 is proven against the still-valid C0 source.
It first materializes every association that can be proved from an exact legacy
signal reference, including the permitted `global:system` price roles, then
walks every current legacy binding in stable ID order. The role comes only from
the closed alias/expansion tables. In particular, the symmetric legacy tariff
is the specified one-to-many case: its one `energy_price` signal creates both
the `grid_import_price` and `grid_export_price` links, atomically.

Each binding resolves `signal_key + time_series_set_id` to one canonical signal,
resolves the textual object reference to one registered real FK in the
variant's project, pins the sealed current revision and hash, and calls the same
association and execution compatibility evaluators as the canonical mutation
API. Only then is its legacy ID preserved where the transformation is in place;
an expanded second price binding gets a generated ID and a stable
role-qualified mapping. Required, actor and timestamps remain attributable to
the legacy row, while validation and link events carry
`system:migration:<migration_run_id>` and retain the full legacy binding as
evidence. Catalog associations are reused by their active
`signal_id + linkable_object_id + binding_role_id` identity; object-specific
bindings keep their exact owner and have no catalog association.

Every binding is independently atomic. An unresolved or incompatible one rolls
back any partial link, records a blocking typed anomaly, and makes both the
canonical executable check and the no-canonical-binding fallback refuse the
variant with `TS_BINDING_EXECUTION_BLOCKED`. Missing entity type with multiple
exact registered object keys is `TS_MIGRATION_OBJECT_AMBIGUOUS`; no approximate
candidate is considered. Cross-project scope or object failures remain
`TS_MIGRATION_PROJECT_MISMATCH` even when C0 carried an operator explanation:
an explanation is evidence, not authorization.

`retire_time_series_migration_binding` is the explicit non-waiver exit for a
binding that must not survive. It requires a blocking C4 anomaly, actor and
nonblank reason, records the immutable disposition mapping, resolves the
anomaly, removes any already-materialized canonical links, and leaves the
complete legacy row consultable through
`read_time_series_migration_binding_history`. The
`read_time_series_c4_cutover_gate` receipt counts only bindings backed by an
active canonical row plus validation, or by that explicit retirement. It is
ready only at 100% coverage and zero unresolved blocking anomalies.

Mappings and open findings use stable source identities and hashes, so a repeat
over unchanged input reuses associations, bindings, evidence and dispositions;
the second run creates no canonical link row, changes no mapping and reproduces
the same manifest.

Evidence: `tests/test_ts7_017_c4_links_backfill.py`, six always-on SQLite N1/N6
contracts plus an opt-in PostgreSQL mirror. The focused C0-C4, association,
binding and run-materialization regression passes (92 tests, 19 skipped
PostgreSQL mirrors). The full Python suite passes (1,180 tests, 108 skipped
opt-in mirrors). No HTTP, permission, OpenAPI, frontend or navigation contract
changed, and the TS-7 pre-C6 visibility rule leaves no browser surface to test.
