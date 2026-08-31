# TS7-003: Register Every Linkable Object And Materialize Components

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (2.4, 5.3, 10.4)

## What to build

Give the heterogeneous link targets one normalized identity. Land
`linkable_object_types` and `linkable_objects` as a closed registry whose rows
carry a real typed foreign key into exactly one subtype table - never a text
pair - so authorization and integrity resolve structurally.

Register the accepted object families: `global_signal_slots` per project and
system scope, `components` for `grid`, `load`, `renewable`, `battery` and
`hydro`, and the hydraulic base entities `system`, `node`, `reach`, `plant` and
`unit`. Projects, users, runs, publications and consoles are not link targets.

Materialize `components` from the components embedded in cases and drafts, with
deterministic keys and no fuzzy matching: group by
`project_id + component_type + technical_key`, create only when key and type are
valid and agree across every authoritative appearance, and refuse when the same
key carries two types or two projects. A plausible-looking `entity_id` string is
never enough to create a component.

Every linkable object belongs to exactly one project, and that project is the
one the route must match before any series is resolved.

## Acceptance criteria

- [x] `linkable_objects` resolves to exactly one subtype row through a real typed FK; no route accepts `entity_type`/`entity_id` text as authority.
- [x] Each accepted family registers its objects; projects, users, runs, publications and consoles cannot be registered.
- [x] `components` materialization is deterministic and repeatable: a second run creates no rows and changes no keys.
- [x] The same technical key with two component types, or across two projects, is refused rather than guessed.
- [x] A case-scoped hydraulic reference resolves through its FK to the base entity, never to the case copy primary key.
- [x] Deleting or archiving a subtype row cannot leave an orphan `linkable_objects` row on either engine.
- [x] Every linkable object exposes one owning project, and a mismatch between route project and object project is refused before any series lookup.

## Implementation evidence

- `app/linkable_objects.py` emits the register DDL per engine
  (`ts_next.global_signal_slots`, `ts_next.components`, `ts_next.linkable_objects`
  on PostgreSQL; the `*_next` suffix on SQLite), the branch `CHECK`, the portable
  guard trigger, the subtype lookup and projection SQL, and the pure appearance
  collectors that read components out of cases and drafts.
  `app/persistence.py` carries the register service: transactional
  parent-plus-subtype registration, `materialize_project_linkable_objects`,
  reference resolution and the archive transition.
- `tests.test_ts7_003_linkable_object_register`: 15 SQLite/domain tests plus 4
  environment-gated PostgreSQL tests, all passing.
- The object type is **derived**, never declared. The service reads the real
  object, builds its `object_type_key` from it (`'global:' || slot_key`,
  `'component:' || component_type`, or the hydraulic family), and the database
  recomputes the same expression in the guard, so a row whose declared type
  disagrees with its typed FK cannot commit on either engine.
- `component:bus` and any slot whose key is not `system` are closed out by that
  same comparison: they produce a key the sealed TS7-001 catalog does not carry,
  so they are refused without a second rule. Projects, users, runs, publications,
  consoles and scenarios have no branch column at all, and the service refuses
  them with `TS_OBJECT_FAMILY_NOT_LINKABLE` before touching the database.
- Materialization groups appearances by `project_id + component_type +
  technical_key` with no fuzzy matching. A second pass creates no row and moves
  no key; a key carrying two component types raises
  `TS_MIGRATION_OBJECT_AMBIGUOUS` and leaves the whole pass unwritten; an
  appearance without a key is skipped as `missing_component_key` rather than
  invented. A group can never span two projects because the project is part of
  the grouping key, and a text reference is resolved only inside the project of
  the route.
- The case-copy test is built so it cannot pass by accident: the copy points at
  the downstream node while the copy's own primary key is the primary key of a
  *different* base node, so a resolver that read the copy's key would land on
  that decoy and the assertion would name it.
- Orphans are closed from both sides. Every branch foreign key is
  `ON DELETE CASCADE`, so deleting a subtype row (or a whole project) takes its
  register row with it; and a portable trigger refuses retiring a component
  behind the register's back with `TS_OBJECT_REGISTER_ORPHAN`, so archiving goes
  through `archive_linkable_object`, which archives both in one transaction.
- Both engines report the same failure for the same row. The two SQLite triggers
  were collapsed into one with an explicit `CASE`, because SQLite promises no
  order between triggers on the same event and a row that breaks the type rule
  and the project rule at once must be named the same way PostgreSQL names it.
- Full Python regression: 888 tests pass with no failures and no skips, with
  `POSTGRES_TEST_DATABASE_URL` pointed at the development database.
- Python bytecode compilation and `git diff --check` pass.

## Decisions recorded

- **`object_kind` follows the sealed catalog, not the abbreviation in 2.4.**
  TS7-001 sealed `linkable_object_types` with `object_kind = 'global_signal_slot'`
  for `global:system`, and that contract is immutable. `linkable_objects.object_kind`
  therefore reads `global_signal_slot` where chapter 2.4 writes `global`. One
  vocabulary is used for both tables, so the guard compares them directly instead
  of translating between two spellings of the same family.
- **The register lives in the canonical space.** Chapter 2.4 writes the three
  tables unqualified, but they are part of the C2 expansion and the owner
  reference below is a real composite foreign key into them, so they land in
  `ts_next` / `*_next` beside the content model of TS7-002 rather than in the
  legacy space.
- **A subtype delete cascades to the register.** Chapter 2.4 restricts *physical
  deletion of a linked object*; that restriction is carried by the `RESTRICT`
  foreign keys the associations and bindings of TS7-004 will add on top. Here the
  branch keys cascade, so the register can never be left holding a row whose real
  object is gone, and deleting a project still works.

## Carried to later slices

- The composite foreign key TS7-002 carried here is installed:
  `(owner_linkable_object_id, owner_project_id) -> linkable_objects(id, project_id)`.
  A database created between TS7-002 and this slice gets it in place on
  PostgreSQL through an idempotent `ALTER TABLE`; SQLite cannot
  `ALTER TABLE ... ADD CONSTRAINT`, so there the constraint is part of the create
  statement and only a local SQLite file built from this same unreleased branch
  would lack it. No released deployment has these tables.
- `TS_COMPAT_PROJECT_CONTEXT_MISMATCH` is raised here by
  `authorize_linkable_object_project`, which is the object half of the single
  domain policy of chapter 5.3. The variant half, the actor half and the source
  scope join it with the association and binding layer in TS7-004 and TS7-007.
- Registering the objects of a project is exposed as a service call, not as a
  route or a migration step: C2 wires it into the migrator in TS7-016, and no
  user-visible surface exists before the cutover (chapter 11.1).

## Blocked by

- [TS7-002: Land The Canonical Content Model With Sealed Revisions](TS7-002-land-the-canonical-content-model-with-sealed-revisions.md)
