# BESS-TS1-004: Generate Existing System Case From Hierarchy Inputs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-14
Fecha de termino planificada: 2026-07-15
Fecha de inicio real: 2026-07-03
Fecha de termino real: 2026-07-03

## User stories covered

4 through 8, 16 through 20

## What to build

Create or consolidate the generation boundary that produces the executable
`system_case_json` from topology and parameter inputs. This should be a deep,
testable module or module family that supports current structured draft and
hydraulic diagram paths without changing the Julia-facing contract.

The core proof is equivalence: generated cases from the hierarchy path should
match the accepted current payloads for representative cases.

## Acceptance criteria

- [x] A shared generation boundary accepts topology and parameter inputs.
- [x] Structured draft cases can generate the same executable payload through the hierarchy boundary.
- [x] Hydraulic diagram cases can generate the same executable payload through the hierarchy boundary.
- [x] Generated payload metadata includes topology and parameter hashes.
- [x] Julia validation still receives a complete `system_case_json`.
- [x] Backend tests prove generation equivalence for representative structured and hydraulic cases.
- [x] Manual run execution from generated scenario versions still works.

## Blocked by

- BESS-TS1-002
- BESS-TS1-003

## Resolution

`derive_case_hierarchy_provenance` (added in BESS-TS1-001, extended in
BESS-TS1-003) already split `system_case_json` into topology/parameter views
before hashing, but it discarded the views themselves. Extracted that split
into `derive_case_hierarchy_views` (`app/persistence.py`) and added the
inverse `generate_system_case_from_hierarchy(topology, parameters)`: the
shared generation boundary, dispatching on the same shape signals (flat
`nodes`/`edges` for one-bus, `hydraulic_network` for hydraulic v3, schema-only
fallback otherwise). `derive_case_hierarchy_provenance` is now a thin wrapper
that hashes the views, so existing hash behavior is unchanged.

New `tests/test_hierarchy_generation_boundary.py` (TDD, tracer bullet first)
proves generation equivalence as a round trip: for a representative structured
case (`data/cases/hybrid_system/system_case.json`) and a representative
hydraulic v3 case (built through the real hydraulic diagram API), splitting
into views and regenerating through `generate_system_case_from_hierarchy`
yields a document whose own re-derived views are identical to the originals.
It also proves the regenerated hydraulic payload still passes Julia-shaped
validation, and that manual run creation from a hierarchy-generated structured
draft version still works. Full suite (173 tests) green.

Kept conservative per the PRD: no production call site was rewired to use the
new boundary (both `generate_system_case_from_draft` and
`generate_hydraulic_v3_preview` are unchanged), avoiding any risk to the
persisted `system_case_json` byte layout or the Julia-facing contract. The
boundary is proven and available for TS1-005/006/007 to build on.

Verified end-to-end via chrome-devtools MCP against the real
PostgreSQL-backed app with the real Julia validator and solver: promoted a
structured draft (CSV-mapped BESS + load) through the draft editor UI and
confirmed `kind: "structured_draft"` with distinct `topology`/`parameters`
content hashes, then launched a manual run that solved to `OPTIMAL` with
HiGHS. Separately built a reservoir + 2 junctions + plant/unit hydraulic v3
diagram via the API, validated topology, generated and promoted the v3
preview, confirmed `kind: "hydraulic_diagram_v3"` with distinct hashes, and
launched a manual run that solved to `OPTIMAL` with real hydraulic KPIs
(storage, turbine flow, terminal water value).
