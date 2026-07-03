# BESS-TS1-003: Add Topology And Parameter Snapshot Metadata For Hydraulic Diagrams

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-10
Fecha de termino planificada: 2026-07-13

## User stories covered

1 through 15, 17 through 20

## What to build

Extend the hydraulic diagram validation and promotion path so it records
topology and parameter provenance for the generated v3 execution snapshot.
Topology should cover the active hydraulic graph and component membership.
Parameters should cover reservoir settings, unit/reach limits, selected curves,
penalties and solver-relevant assumptions.

The slice should preserve the existing v3 preview, promotion, layout snapshot
and manual run behavior.

## Acceptance criteria

- [ ] Hydraulic diagram validation produces topology snapshot metadata for active graph state.
- [ ] Hydraulic diagram validation produces parameter snapshot metadata for executable assumptions.
- [ ] Layout-only changes are not treated as physical topology changes.
- [ ] Connectivity or component-membership changes affect topology provenance.
- [ ] Reservoir, curve, reach-control or unit-limit changes affect parameter provenance.
- [ ] Promotion stores hierarchy provenance alongside the immutable v3 scenario version.
- [ ] Existing hydraulic layout snapshot behavior remains unchanged.
- [ ] Backend tests cover hydraulic topology and parameter metadata creation.
- [ ] Existing hydraulic diagram acceptance tests remain green.

## Blocked by

BESS-TS1-001
