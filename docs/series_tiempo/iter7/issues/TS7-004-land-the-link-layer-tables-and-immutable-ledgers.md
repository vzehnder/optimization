# TS7-004: Land The Link Layer Tables And Immutable Ledgers

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (2.5, 2.6, 4.1, 9.6, 9.9)

## What to build

Land the two link layers as separate structures, because they answer different
questions. `time_series_catalog_associations` says a generic source is available
to an object for a need and follows the signal's current identity.
`case_time_series_bindings` says a variant executes with one exact revision and
hash, and it does not move when a new revision is published.

The association carries `binding_role_id`, which changes its active uniqueness
(P-02): at most one active association per
`signal_id + linkable_object_id + binding_role_id`. The binding is unique per
`case_input_variant_id + linkable_object_id + binding_role_id`. Both are
append-only in effect: changing signal, object or role creates a new row and
leaves the previous one readable.

The association branch exists only for signals whose set is `series_kind =
'catalog'`. An `object_specific` set never crosses it.

Land the three ledgers - `time_series_link_events`, `time_series_link_validations`
and `time_series_scope_events` - as insert-only tables whose triggers refuse
`UPDATE` and `DELETE` identically on both engines, so no public route can erase
an audit row.

Close the structural holes with portable integrity: no orphan rows, and no
object-scoped series reachable from a catalog association.

## Acceptance criteria

- [ ] Only one active association exists per `signal_id + linkable_object_id + binding_role_id`, enforced by a partial unique index (AC-ASO-03, P-02).
- [ ] Only one active binding exists per `case_input_variant_id + linkable_object_id + binding_role_id` (AC-BIN-01).
- [ ] Changing signal, object or role creates a new row and the previous row stays queryable (AC-ASO-06).
- [ ] A binding stores an exact `set_revision_id` and hash; no column lets it follow `current_revision_id` (AC-BIN-02 structural half).
- [ ] An association whose signal belongs to an `object_specific` set cannot be inserted, on either engine.
- [ ] The three ledgers accept `INSERT` only; `UPDATE` and `DELETE` fail with the same observable result on both engines (AC-SEG-05 structural half).
- [ ] No combination of deletes leaves an orphan association, binding, validation or event (chapter 9.9).
- [ ] Every invariant in this ticket holds identically on PostgreSQL and SQLite.

## Blocked by

- [TS7-003: Register Every Linkable Object And Materialize Components](TS7-003-register-every-linkable-object-and-materialize-components.md)
