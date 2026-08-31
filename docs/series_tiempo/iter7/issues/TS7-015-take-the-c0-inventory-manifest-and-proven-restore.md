# TS7-015: Take The C0 Inventory, Manifest And Proven Restore

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (10.2 C0, 10.3)

## What to build

Establish the recovery point the whole migration is measured against, before any
DDL touches the environment.

Produce a signed manifest: counts and hashes of sets, revisions, signals,
periods, values, sources and bindings; maximum primary keys; broken references
and duplicates; executable variants and their fingerprint. Take a consistent
copy and prove the restore actually works - an untested backup is not a recovery
point. Any unexplained structural difference stops C0.

Land the migration control surface this and every later phase records into:
`time_series_migration_runs` for phase state, version, watermarks, manifests and
checkpoints; `time_series_migration_mappings` with a unique key per
`source_kind + source_table + source_id + target_kind`, where a difference is a
conflict and never a second silent insert;
`time_series_migration_anomalies` for typed findings with severity, evidence,
resolution and actor; and `time_series_legacy_dirty_roots` as the monotone queue
of roots touched after the watermark.

Every row the migrator creates uses the technical actor
`system:migration:<migration_run_id>`. Original `created_by` values and
timestamps are preserved where they represent the previous identity, but no user
is impersonated as the author of a migration decision.

## Acceptance criteria

- [ ] C0 produces a signed manifest and a proven restore before any DDL runs (AC-MIG-01).
- [ ] The manifest covers counts, hashes, maximum primary keys, broken references, duplicates and executable variant fingerprints.
- [ ] An unexplained structural difference stops C0 instead of being recorded and passed over.
- [ ] The four control tables exist on both engines and are additive: no existing response, permission or navigation changes.
- [ ] A mapping conflict on the unique key is reported as a conflict, never inserted a second time.
- [ ] Every migrator-created row carries `system:migration:<migration_run_id>` as its actor.
- [ ] Original `created_by` and timestamps are preserved where they represent the previous identity.
- [ ] Re-running C0 against an unchanged source reproduces the same manifest.

## Blocked by

- None - can start immediately.
