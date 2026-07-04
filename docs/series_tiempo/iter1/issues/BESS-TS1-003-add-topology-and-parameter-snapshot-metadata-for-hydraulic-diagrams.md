# BESS-TS1-003: Add Topology And Parameter Snapshot Metadata For Hydraulic Diagrams

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-10
Fecha de termino planificada: 2026-07-13
Fecha de inicio real: 2026-07-03
Fecha de termino real: 2026-07-03

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

- [x] Hydraulic diagram validation produces topology snapshot metadata for active graph state.
- [x] Hydraulic diagram validation produces parameter snapshot metadata for executable assumptions.
- [x] Layout-only changes are not treated as physical topology changes.
- [x] Connectivity or component-membership changes affect topology provenance.
- [x] Reservoir, curve, reach-control or unit-limit changes affect parameter provenance.
- [x] Promotion stores hierarchy provenance alongside the immutable v3 scenario version.
- [x] Existing hydraulic layout snapshot behavior remains unchanged.
- [x] Backend tests cover hydraulic topology and parameter metadata creation.
- [x] Existing hydraulic diagram acceptance tests remain green.

## Resolution

`derive_case_hierarchy_provenance` in `app/persistence.py` gained a
shape-driven branch for documents carrying a `hydraulic_network` key (the v3
hydraulic-diagram case shape). Topology now covers node id/type, reach
id/from/to/type, plant id/unit-membership and unit id/plant/intake/discharge —
pure component membership and connectivity. Parameters now cover reservoir
settings, storage-elevation and flow-power curves, reach control fields
(routing method, travel time, minimum flow, spill penalty), plant/unit limits,
and the denormalized curve/required-time-series lists. The one-bus branch and
the schema-version-only fallback are unchanged, so structured-draft and
paste/upload provenance (BESS-TS1-001/002) are unaffected.

New tests in `tests/test_hydraulic_diagram_hierarchy_provenance.py` (5 tests,
TDD vertical slices) prove: baseline promotion records distinct topology and
parameter hashes; a layout-only node move keeps both hashes stable; combined
reservoir/curve/unit-limit/reach-control edits keep the topology hash stable
while changing the parameters hash; adding a node and reach changes the
topology hash; and changing a unit's intake-node connectivity (no
add/remove) changes the topology hash while leaving the parameters hash
untouched. Full suite (170 tests) green.

Verified end-to-end via chrome-devtools MCP against the real
PostgreSQL-backed app with the real Julia validator: built a reservoir +
2 junctions + plant/unit hydraulic diagram through the diagram editor UI,
validated topology, generated the v3 preview (Julia-validated), and promoted
it. The resulting scenario version's Generation metadata panel showed
`kind: "hydraulic_diagram_v3"` alongside distinct
`topology.content_hash`/`parameters.content_hash` values.

## Blocked by

BESS-TS1-001
