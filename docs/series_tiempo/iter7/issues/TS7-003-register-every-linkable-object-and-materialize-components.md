# TS7-003: Register Every Linkable Object And Materialize Components

Status: Todo
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

- [ ] `linkable_objects` resolves to exactly one subtype row through a real typed FK; no route accepts `entity_type`/`entity_id` text as authority.
- [ ] Each accepted family registers its objects; projects, users, runs, publications and consoles cannot be registered.
- [ ] `components` materialization is deterministic and repeatable: a second run creates no rows and changes no keys.
- [ ] The same technical key with two component types, or across two projects, is refused rather than guessed.
- [ ] A case-scoped hydraulic reference resolves through its FK to the base entity, never to the case copy primary key.
- [ ] Deleting or archiving a subtype row cannot leave an orphan `linkable_objects` row on either engine.
- [ ] Every linkable object exposes one owning project, and a mismatch between route project and object project is refused before any series lookup.

## Blocked by

- [TS7-002: Land The Canonical Content Model With Sealed Revisions](TS7-002-land-the-canonical-content-model-with-sealed-revisions.md)
