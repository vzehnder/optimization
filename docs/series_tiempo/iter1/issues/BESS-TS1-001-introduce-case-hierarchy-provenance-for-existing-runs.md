# BESS-TS1-001: Introduce Case Hierarchy Provenance For Existing Runs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-06
Fecha de termino planificada: 2026-07-07

## User stories covered

1 through 7, 16 through 20

## What to build

Add the first end-to-end hierarchy provenance path without changing optimizer
behavior. A scenario version created by existing flows should record
machine-readable provenance for the logical topology and parameter assumptions
that produced its `system_case_json`, even if the first implementation uses
metadata adapters rather than fully normalized version tables.

The slice should be demoable by creating a normal scenario version and seeing
topology and parameter provenance attached to that immutable snapshot.

## Acceptance criteria

- [ ] New scenario versions can record topology provenance metadata.
- [ ] New scenario versions can record parameter provenance metadata.
- [ ] Provenance includes stable hash or revision identifiers suitable for stale checks.
- [ ] Existing scenario-version immutability remains enforced.
- [ ] Existing manual run creation from scenario versions still works.
- [ ] Existing scenario version detail APIs still return prior fields.
- [ ] Backend tests prove provenance is recorded for a newly created scenario version.
- [ ] Backend tests prove old scenario versions without provenance still load safely.

## Blocked by

BESS-TS1-000
