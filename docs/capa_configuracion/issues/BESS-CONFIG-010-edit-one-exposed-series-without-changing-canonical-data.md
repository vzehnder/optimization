# BESS-CONFIG-010: Edit One Exposed Series Without Changing Canonical Data

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Let one operator edit one configured time-series column end to end. The console
loads a permitted range into matching table and read-only chart views, obtains
the minimal single-copy edit lock, saves with optimistic concurrency, and then
runs with the edited values. On the first accepted edit the system creates a
flat operational copy and redirects only the console-owned variant, leaving
the canonical set and every other variant untouched.

## Acceptance criteria

- [ ] The operator can load one configured group and range using only external group and column ids.
- [ ] Table and chart display the same timestamps, values, public labels, units and selected range.
- [ ] The values response includes an opaque ETag and saving requires the matching `If-Match` value.
- [ ] A first accepted edit creates one flat, non-derived operational set with inert origin-set and origin-revision lineage.
- [ ] Only the console-owned variant is rebound to the operational copy; the canonical set and unrelated variants retain their ids, revisions, hashes and values.
- [ ] The accepted save creates a new auditable revision with actor, console, configuration revision, range, before/after values and optional note.
- [ ] The save refreshes only the copied-set validation dependency needed by the console variant.
- [ ] Dirty cells and an in-progress save disable running; a successful save makes the edited values eligible for the next run.
- [ ] Editing is limited to the configured and covered range and never creates timestamps or signals.
- [ ] Internal set ids, copy ids, revisions, hashes, bindings and signal keys never cross the operator payload.
- [ ] Persistence, API, React and execution tests prove that a run uses the edited copy while canonical data stays unchanged.

## Blocked by

- [BESS-CONFIG-007: Drive Console Signal Choices From The Canonical Catalog](BESS-CONFIG-007-drive-console-signal-choices-from-the-canonical-catalog.md)
- [BESS-CONFIG-009: Run A Configured Console With Parameter Overrides](BESS-CONFIG-009-run-a-configured-console-with-parameter-overrides.md)
