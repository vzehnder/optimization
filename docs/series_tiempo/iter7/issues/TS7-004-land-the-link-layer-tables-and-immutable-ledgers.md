# TS7-004: Land The Link Layer Tables And Immutable Ledgers

Status: In Review
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

- [x] Only one active association exists per `signal_id + linkable_object_id + binding_role_id`, enforced by a partial unique index (AC-ASO-03, P-02).
- [x] Only one active binding exists per `case_input_variant_id + linkable_object_id + binding_role_id` (AC-BIN-01).
- [x] Changing signal, object or role creates a new row and the previous row stays queryable (AC-ASO-06).
- [x] A binding stores an exact `set_revision_id` and hash; no column lets it follow `current_revision_id` (AC-BIN-02 structural half).
- [x] An association whose signal belongs to an `object_specific` set cannot be inserted, on either engine.
- [x] The three ledgers accept `INSERT` only; `UPDATE` and `DELETE` fail with the same observable result on both engines (AC-SEG-05 structural half).
- [x] No combination of deletes leaves an orphan association, binding, validation or event (chapter 9.9).
- [x] Every invariant in this ticket holds identically on PostgreSQL and SQLite.

## Implementation evidence

- `app/time_series_links.py` emits the two link tables, the three insert-only
  ledgers, their composite foreign keys, both partial active-row indexes and
  the portable history/ledger guards. They live in `ts_next` on PostgreSQL and
  use the `_next` suffix on SQLite, beside the canonical model and without
  replacing the legacy `case_time_series_bindings` writer.
- `app/persistence.py` installs the layer after canonical content and object
  registration, adds `case_input_variants.bindings_revision` additively and
  exposes the physical table map. Named PostgreSQL checks converge databases
  that already carry an earlier additive table definition.
- `tests.test_ts7_004_link_layer` proves 12 SQLite contracts and repeats the
  engine-sensitive contract in 3 PostgreSQL tests: both active cardinalities,
  exact revision/hash pinning, the `object_specific` exclusion, lifecycle
  evidence, append-only identity, immutable ledgers and restricted parent
  deletes. PostgreSQL fixtures run inside force-rollback transactions.
- Focused TS7-001 through TS7-004 verification: 69 tests pass with
  `POSTGRES_TEST_DATABASE_URL` pointed at the development database. Full Python
  regression: 903 tests pass with 18 environment-gated skips. Python bytecode
  compilation and `git diff --check` pass.

## Decisions recorded

- **Link history and audit history have distinct stable failures.** Identity
  edits or physical deletion of associations/bindings raise
  `TS_LINK_HISTORY_IMMUTABLE`; updates or deletes of any of the three ledgers
  raise `TS_LINK_LEDGER_IMMUTABLE`. Both engines expose those exact names.
- **Lifecycle changes are the only in-place link mutation.** An association may
  move from active to archived and a binding may move from active to
  superseded/removed only with coherent actor/date evidence. Signal, object,
  role, revision, hash, source path and supersession pointers remain immutable;
  replacing them requires a new row.
- **Historical roots use restrictive references.** No public-domain cascade is
  introduced below objects, variants, canonical signals/revisions/sets, users
  or compatibility rules. Direct deletion attempts are rejected and the
  orphan probes remain empty on both supported engines.

## Blocked by

- [TS7-003: Register Every Linkable Object And Materialize Components](TS7-003-register-every-linkable-object-and-materialize-components.md)
