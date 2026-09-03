# TS7-015: Take The C0 Inventory, Manifest And Proven Restore

Status: In Review
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

- [x] C0 produces a signed manifest and a proven restore before any DDL runs (AC-MIG-01).
- [x] The manifest covers counts, hashes, maximum primary keys, broken references, duplicates and executable variant fingerprints.
- [x] An unexplained structural difference stops C0 instead of being recorded and passed over.
- [x] The four control tables exist on both engines and are additive: no existing response, permission or navigation changes.
- [x] A mapping conflict on the unique key is reported as a conflict, never inserted a second time.
- [x] Every migrator-created row carries `system:migration:<migration_run_id>` as its actor.
- [x] Original `created_by` and timestamps are preserved where they represent the previous identity.
- [x] Re-running C0 against an unchanged source reproduces the same manifest.

## Blocked by

- None - can start immediately.

## Delivery notes

The four control tables keep the exact names chapter 10.3 gives them, on both
engines. They deliberately stay out of the `ts_next` / `_next` space: those
names do not collide with anything legacy, C0 reads a source the expansion is
not yet authoritative over, and the control rows have to survive a rollback that
abandons the expansion.

`AC-MIG-01` says the manifest and the proven restore come before any DDL runs.
The expansion DDL of C1 already landed in TS7-001 to TS7-005, so that ordering
can no longer be re-proven by running C0 first. What is enforced instead is the
rule the ordering exists for: `open_migration_phase` refuses
`TS_MIGRATION_RECOVERY_POINT_REQUIRED` unless a proven C0 exists **and** its
inventory still describes the current source, so no later phase runs without a
recovery point it could actually be rolled back to.

The restore proof reloads the copy into a scratch SQLite database and recomputes
the inventory over the restored rows. What C0 has to prove is that the copy is
complete and reloadable; landing it on a scratch engine keeps the proof from
depending on a second production database being available.

Four anomaly codes name conditions chapter 10.7 has no entry for -
`TS_MIGRATION_DUPLICATE_BINDING`, `TS_MIGRATION_BINDING_SIGNAL_UNRESOLVED`,
`TS_MIGRATION_VALUE_SET_MISMATCH` and `TS_MIGRATION_REVISION_CHAIN_BROKEN`.
None of them weakens a treatment that table already decides.

Evidence: `tests/test_ts7_015_c0_inventory_and_manifest.py`, twenty N1 contracts
on SQLite plus a two-test opt-in PostgreSQL mirror that exercises the DDL, the
engine-specific probe SQL and the mapping conflict. The full Python suite passes
(1155 tests). No HTTP route, permission or navigation changed, so the generated
OpenAPI and TypeScript contracts are untouched.
