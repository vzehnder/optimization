# BESS-TS5-002: Read Legacy Hydraulic Series Through The Common Catalog

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-14
Fecha de termino planificada: 2026-07-15

## User stories covered

4, 12, 16

## What to build

Stop hydrology from being a special UX island: legacy hydraulic series sets
created by the hydro diagram editor become visible through the common catalog
semantics via a read adapter, without physically migrating rows.

An analyst browsing the project series catalog sees the legacy hydraulic sets
alongside generic sets, labeled with their hydraulic origin, and can inspect
their signals, periods and values with the same vocabulary used for generic
sets. The hydro diagram editor's existing series screens and case bindings
keep working unchanged — the adapter adds a second read surface, it does not
replace the legacy path yet.

Adapter reads live in a deep module testable without the UI, and coexistence
tests prove the adapter and the legacy read path expose the same values for
the same set, so later write-path and migration slices can build on a proven
equivalence.

## Acceptance criteria

- [ ] Legacy hydraulic series sets are listed in the project series catalog alongside generic sets, labeled with their hydraulic origin.
- [ ] A legacy hydraulic set's signals, periods and values can be browsed through the common catalog semantics without migrating rows.
- [ ] The hydraulic diagram editor's existing series screens and case bindings keep working unchanged.
- [ ] Adapter reads live in a deep module testable without the UI.
- [ ] Coexistence tests prove the adapter and the legacy read path expose the same values for the same set.

## Blocked by

BESS-TS5-000
