# BESS-CONFIG-010: Edit One Exposed Series Without Changing Canonical Data

Status: In Review
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

- [x] The operator can load one configured group and range using only external group and column ids.
- [x] Table and chart display the same timestamps, values, public labels, units and selected range.
- [x] The values response includes an opaque ETag and saving requires the matching `If-Match` value.
- [x] A first accepted edit creates one flat, non-derived operational set with inert origin-set and origin-revision lineage.
- [x] Only the console-owned variant is rebound to the operational copy; the canonical set and unrelated variants retain their ids, revisions, hashes and values.
- [x] The accepted save creates a new auditable revision with actor, console, configuration revision, range, before/after values and optional note.
- [x] The save refreshes only the copied-set validation dependency needed by the console variant.
- [x] Dirty cells and an in-progress save disable running; a successful save makes the edited values eligible for the next run.
- [x] Editing is limited to the configured and covered range and never creates timestamps or signals.
- [x] Internal set ids, copy ids, revisions, hashes, bindings and signal keys never cross the operator payload.
- [x] Persistence, API, React and execution tests prove that a run uses the edited copy while canonical data stays unchanged.

## Implementation notes

- The lease lives in `operator_console_series_leases`, keyed by
  `(console_id, origin_set_id)`. The architecture places the lease columns on
  `operator_console_series_copies`, but the copy only exists once an edit is
  accepted, and the lock has to exist before that. The origin set is the same
  identity the copy carries, so the lease is still one lock per copy, presented
  per group.
- A group's `granularity` bounds the window the operator may load and edit at
  once (`day`, `week`, `month`, `full_horizon`); rows always stay native
  periods, so no value is aggregated on the way out and split on the way back
  in.
- The copy's first revision is the verbatim fork and the second is the edit, so
  the audit trail keeps a "before" that matches the origin exactly.
- The copy carries no `validation_dependencies` of its own: it is flat, never
  regenerated, and cannot go stale from the recipe of the set it was forked
  from.
- The concurrency token leaves as an opaque `ETag` header rather than a payload
  field, so no set id, revision or content hash crosses the boundary.

## Blocked by

- [BESS-CONFIG-007: Drive Console Signal Choices From The Canonical Catalog](BESS-CONFIG-007-drive-console-signal-choices-from-the-canonical-catalog.md)
- [BESS-CONFIG-009: Run A Configured Console With Parameter Overrides](BESS-CONFIG-009-run-a-configured-console-with-parameter-overrides.md)
