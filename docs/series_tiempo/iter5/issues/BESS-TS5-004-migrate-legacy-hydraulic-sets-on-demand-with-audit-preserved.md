# BESS-TS5-004: Migrate Legacy Hydraulic Sets On Demand With Audit Preserved

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-20
Fecha de termino planificada: 2026-07-21

## User stories covered

4, 6, 14

## What to build

An explicit, on-demand migration path that converts a legacy hydraulic series
set into a generic catalog set, preserving audit metadata: origin, source
linkage where present, version identity and content-hash lineage, so the
migrated set can always be traced back to what it came from and edit history
remains auditable after migration.

Migration is never applied silently or in bulk by default: an admin or
analyst chooses a set and migrates it. Historical scenario versions and runs
that referenced the legacy set are not rewritten — they keep reading their
frozen snapshots — while future bindings use the migrated generic set. A bulk
routine can sweep the remaining legacy hydraulic sets of a project and report
migrated, skipped and failed sets stably, so local and PostgreSQL
environments can be repaired safely.

## Acceptance criteria

- [ ] An admin or analyst can migrate one legacy hydraulic series set into the generic catalog on demand.
- [ ] Migration preserves audit metadata: origin, source linkage where present, version identity and content-hash lineage.
- [ ] Historical scenario versions and runs that referenced the legacy set remain untouched and readable.
- [ ] Migration is idempotent: re-running converges (skip or stable replace) without duplicates, in local SQLite and PostgreSQL.
- [ ] A bulk routine can migrate all remaining legacy hydraulic sets of a project and report migrated/skipped/failed stably across repeated runs.

## Blocked by

BESS-TS5-003
