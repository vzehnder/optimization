# BESS-TS3-007: Show Run Lineage With Variant, Range And Series Hashes

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-24
Fecha de termino planificada: 2026-07-27

## User stories covered

16, 17, 18

## What to build

Make run provenance complete and readable. The run detail shows which input
variant and date range produced the run, plus the full data lineage: topology
version, parameter version, and per-binding input set revisions and content
hashes frozen at launch. The automatically generated technical snapshot stays
hidden behind an on-demand detail view so the normal workflow remains simple.

Lineage is persisted with the run at creation and is immutable afterwards, so
audits can reconstruct exactly which data produced any result even after sets
gain new revisions.

## Acceptance criteria

- [ ] Run detail shows the selected variant name and the run date range.
- [ ] Run detail shows topology version, parameter version and per-binding input set revisions with content hashes.
- [ ] The generated technical snapshot is hidden by default and accessible on demand from the run detail.
- [ ] Lineage is persisted at run creation and does not change when bound sets later gain revisions.
- [ ] Backend tests prove lineage recording for variant runs; React tests cover the run-detail lineage display.

## Blocked by

BESS-TS3-001, BESS-TS3-003
