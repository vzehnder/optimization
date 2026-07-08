# BESS-TS5-005: Keep Stale Validation Reliable Across Legacy And Migrated Series

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-22
Fecha de termino planificada: 2026-07-22

## User stories covered

10, 16

## What to build

Prove that the TS-3 staleness contract survives migration: no run may use
outdated assumptions regardless of where its series came from. Editing an
extracted or migrated series set marks every case input variant bound to it
stale, exactly like a natively created set; topology and parameter provenance
staleness keeps working for cases whose series were extracted or migrated;
and legacy hydraulic binding staleness keeps working during the compatibility
window.

The end-to-end proof runs the fail-closed loop across storage origins: bind an
extracted or migrated set to a variant, validate, edit the set, observe the
variant become stale and block runs until revalidated. Tests cover staleness
for extracted, migrated, adapter-read and natively created sets so hardening
does not regress behavior for any origin.

## Acceptance criteria

- [ ] Editing an extracted or migrated series set marks every case input variant bound to it stale, exactly like a natively created set.
- [ ] Topology and parameter provenance staleness keeps working for cases whose series were extracted or migrated.
- [ ] Legacy hydraulic binding staleness keeps working during the compatibility window.
- [ ] Stale variants keep blocking runs until revalidated (fail closed) across old and new storage.
- [ ] Tests cover staleness for extracted, migrated, adapter-read and natively created sets.

## Blocked by

BESS-TS5-001, BESS-TS5-004
