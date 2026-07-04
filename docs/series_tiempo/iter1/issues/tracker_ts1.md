# BESS TS-1 Issue Tracker

This document is the local tracker for TS-1: topology and parameter hierarchy,
derived from `docs/series_tiempo/iter1/prd.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the
`ready-for-agent` triage label.

## Date Policy

All issues generated from this point forward include:

- `Fecha de inicio planificada`
- `Fecha de termino planificada`

Actual start/end dates can be added or corrected by the implementer when work
really begins and ends.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Fecha de inicio planificada | Fecha de termino planificada | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BESS-TS1-000 | Review TS-1 PRD And Hierarchy Semantics | HITL | ready-for-agent | Done | 2026-07-03 | 2026-07-03 | None | [BESS-TS1-000-review-ts1-prd-and-hierarchy-semantics.md](BESS-TS1-000-review-ts1-prd-and-hierarchy-semantics.md) |
| BESS-TS1-001 | Introduce Case Hierarchy Provenance For Existing Runs | AFK | ready-for-agent | Done | 2026-07-06 | 2026-07-07 | BESS-TS1-000 | [BESS-TS1-001-introduce-case-hierarchy-provenance-for-existing-runs.md](BESS-TS1-001-introduce-case-hierarchy-provenance-for-existing-runs.md) |
| BESS-TS1-002 | Add Topology And Parameter Snapshot Metadata For Structured Drafts | AFK | ready-for-agent | Done | 2026-07-08 | 2026-07-09 | BESS-TS1-001 | [BESS-TS1-002-add-topology-and-parameter-snapshot-metadata-for-structured-drafts.md](BESS-TS1-002-add-topology-and-parameter-snapshot-metadata-for-structured-drafts.md) |
| BESS-TS1-003 | Add Topology And Parameter Snapshot Metadata For Hydraulic Diagrams | AFK | ready-for-agent | Done | 2026-07-10 | 2026-07-13 | BESS-TS1-001 | [BESS-TS1-003-add-topology-and-parameter-snapshot-metadata-for-hydraulic-diagrams.md](BESS-TS1-003-add-topology-and-parameter-snapshot-metadata-for-hydraulic-diagrams.md) |
| BESS-TS1-004 | Generate Existing System Case From Hierarchy Inputs | AFK | ready-for-agent | Done | 2026-07-14 | 2026-07-15 | BESS-TS1-002, BESS-TS1-003 | [BESS-TS1-004-generate-existing-system-case-from-hierarchy-inputs.md](BESS-TS1-004-generate-existing-system-case-from-hierarchy-inputs.md) |
| BESS-TS1-005 | Harden Stale Validation For Topology And Parameter Changes | AFK | ready-for-agent | Done | 2026-07-16 | 2026-07-17 | BESS-TS1-004 | [BESS-TS1-005-harden-stale-validation-for-topology-and-parameter-changes.md](BESS-TS1-005-harden-stale-validation-for-topology-and-parameter-changes.md) |
| BESS-TS1-006 | Surface Topology And Parameter Provenance In React | AFK | ready-for-agent | Todo | 2026-07-20 | 2026-07-21 | BESS-TS1-004 | [BESS-TS1-006-surface-topology-and-parameter-provenance-in-react.md](BESS-TS1-006-surface-topology-and-parameter-provenance-in-react.md) |
| BESS-TS1-007 | Preserve Legacy Scenario Draft Version And Run Compatibility | AFK | ready-for-agent | Todo | 2026-07-22 | 2026-07-23 | BESS-TS1-005, BESS-TS1-006 | [BESS-TS1-007-preserve-legacy-scenario-draft-version-and-run-compatibility.md](BESS-TS1-007-preserve-legacy-scenario-draft-version-and-run-compatibility.md) |
| BESS-TS1-008 | Finalize TS-1 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | 2026-07-24 | 2026-07-24 | BESS-TS1-001 through BESS-TS1-007 | [BESS-TS1-008-finalize-ts1-acceptance-suite-and-docs.md](BESS-TS1-008-finalize-ts1-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-TS1-000
2. BESS-TS1-001
3. BESS-TS1-002 and BESS-TS1-003 can proceed after the common provenance boundary exists.
4. BESS-TS1-004 joins structured and hydraulic hierarchy inputs into stable generated snapshots.
5. BESS-TS1-005 hardens stale validation after generation equivalence is proven.
6. BESS-TS1-006 exposes provenance in React once backend metadata is stable.
7. BESS-TS1-007 runs compatibility and regression hardening across old flows.
8. BESS-TS1-008 closes the iteration with acceptance coverage and docs.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-07-03 | All | Created | Initial local issue set generated from the TS-1 PRD and hierarchy roadmap. |
| 2026-07-03 | BESS-TS1-000 | Todo -> Done | Reviewed and accepted TS-1 hierarchy semantics against the full docs context. `OptimizationCase` is the main editable case concept; `ScenarioVersion` remains the immutable executable snapshot; topology/parameter boundaries and curve treatment are accepted; `Scenario -> OptimizationCase` cardinality migration is deferred; structured draft, paste/upload, hydraulic diagram and run compatibility remain required. No PRD correction was needed. |
| 2026-07-03 | BESS-TS1-001 | Todo -> Done | Added `derive_case_hierarchy_provenance` in `app/persistence.py`, a schema-agnostic split of `system_case_json` into a `topology` view (node id/type identity plus edges) and a `parameters` view (everything else), each hashed with SHA-256. Wired into `AnalystStore.create_scenario_version`, the single choke point for all four version-creation paths, merging into the existing `generation_metadata_json` column with no schema migration. New backend tests in `tests/test_case_hierarchy_provenance.py` prove provenance is recorded, that topology hashes stay stable across parameter-only edits while changing on structural edits, and that legacy rows without provenance still load safely. Full suite (161 tests) green. Verified end-to-end via chrome-devtools MCP against the real PostgreSQL-backed app: created a scenario version through the UI and confirmed `topology.content_hash`/`parameters.content_hash` in the rendered Generation metadata panel. |
| 2026-07-03 | BESS-TS1-002 | Todo -> Done | Confirmed the generic provenance split wired in BESS-TS1-001 already covers structured draft promotion, since `create_scenario_version` is the single choke point for that path too and `generate_system_case_from_draft` always emits the same `nodes`/`edges` schema. No production code change was needed. Added `tests/test_structured_draft_hierarchy_provenance.py` (4 tests, TDD vertical slices) proving: a promoted CSV-mapped draft records `topology`/`parameters` content hashes; a parameter-only draft edit keeps the topology hash stable while changing the parameters hash; removing an asset changes the topology hash; and hydro CSV mapping metadata coexists with the hierarchy provenance keys. Full suite (165 tests) green. Verified end-to-end via chrome-devtools MCP against the real PostgreSQL-backed app: built a structured draft (BESS + load) with an uploaded CSV source, validated it against real Julia, promoted it, and confirmed the resulting version's Generation metadata panel shows `kind: "structured_draft"` with CSV `source`/`mapping` details alongside `topology.content_hash`/`parameters.content_hash`. |
| 2026-07-03 | BESS-TS1-003 | Todo -> Done | The hydraulic v3 case shape (`hydraulic_network` with nested nodes/reaches/plants/units, not top-level `nodes`) fell into `derive_case_hierarchy_provenance`'s schema-version-only fallback, so topology never changed regardless of edits. Added a shape-driven `hydraulic_network` branch in `app/persistence.py`: topology covers node id/type, reach id/from/to/type, plant id/unit-membership and unit id/plant/intake/discharge (membership and connectivity only); parameters cover reservoir settings, storage-elevation/flow-power curves, reach control fields, plant/unit limits, and denormalized curve/required-time-series lists. New `tests/test_hydraulic_diagram_hierarchy_provenance.py` (5 tests, TDD vertical slices, tracer bullet first) proves: baseline promotion records distinct hashes; a layout-only node move keeps both hashes stable; combined reservoir/curve/unit-limit/reach-control edits keep topology stable while changing parameters; adding a node+reach changes topology; and a pure unit intake-node connectivity change (no add/remove) changes topology without touching parameters. Full suite (170 tests) green. Verified end-to-end via chrome-devtools MCP against the real PostgreSQL-backed app with the real Julia validator: built a reservoir+2 junctions+plant/unit diagram through the diagram editor UI, validated topology, generated the Julia-validated v3 preview, and promoted it; the resulting version's Generation metadata panel shows `kind: "hydraulic_diagram_v3"` with distinct `topology.content_hash`/`parameters.content_hash`. |
| 2026-07-03 | BESS-TS1-004 | Todo -> Done | `derive_case_hierarchy_provenance` split `system_case_json` into topology/parameter views but discarded the views after hashing. Extracted that split into `derive_case_hierarchy_views` (`app/persistence.py`) and added the inverse `generate_system_case_from_hierarchy(topology, parameters)`: the shared generation boundary, dispatching on the same shape signals as before (flat `nodes`/`edges`, `hydraulic_network`, schema-only fallback). `derive_case_hierarchy_provenance` is now a thin wrapper hashing the views, so existing hash behavior is byte-for-byte unchanged. New `tests/test_hierarchy_generation_boundary.py` (TDD, tracer bullet first) proves generation equivalence as a round trip: splitting a representative structured case and a representative hydraulic v3 case into views and regenerating through the boundary yields a document whose own re-derived views match the originals exactly; also proves the regenerated hydraulic payload still passes Julia-shaped validation and that manual run creation from a hierarchy-generated structured draft version still works. Full suite (173 tests) green. Kept conservative per the PRD: neither `generate_system_case_from_draft` nor `generate_hydraulic_v3_preview` was rewired to call the new boundary, so the persisted `system_case_json` byte layout and Julia contract are untouched; the boundary is proven and ready for TS1-005/006/007. Verified end-to-end via chrome-devtools MCP against the real PostgreSQL-backed app with the real Julia validator and solver: promoted a CSV-mapped structured draft (BESS+load) and a reservoir/junctions/plant/unit hydraulic v3 diagram, confirmed correct `kind`/`topology`/`parameters` provenance on both, and launched manual runs on both that solved to `OPTIMAL` with real HiGHS results. |
| 2026-07-03 | BESS-TS1-005 | Todo -> Done | Added `hierarchy_stale_state(previous_system_case, current_system_case)` and `hierarchy_stale_summary(label, stale_state)` in `app/persistence.py`, built directly on the TS1-004 `derive_case_hierarchy_provenance` split: comparing topology/parameter content hashes between a validated case and a freshly regenerated one identifies which part(s) drifted instead of only a whole-payload hash flip. Rewired `_stale_validation_after_hydraulic_edit` (hydraulic diagrams) to use it, storing explicit `topology`/`parameters` content-hash fields on the `hydraulic_v3_preview` validation snapshot and setting `topology_stale`/`parameters_stale` booleans plus a distinguishing `summary` when stale. Rewired `promote_hydraulic_diagram` and `validated_generated_system_case_from_draft` (structured drafts) in `app/main.py` to raise a `DraftPromotionError` naming "topology", "parameters", or "topology and parameters" instead of a generic stale message; `generated_system_case_snapshot` now also stores `topology`/`parameters` content-hash fields on the structured-draft validation snapshot. Layout-only edits stay non-stale unchanged, since node position was never part of either generated payload. New `tests/test_stale_hierarchy_validation.py` (7 tests, TDD, tracer bullet first) proves: a topology-only rewire (unit intake-node swap, no add/remove) marks `topology_stale` true / `parameters_stale` false and blocks promotion with a "topology" message; a parameter-only edit (reservoir `storage_max_hm3`) marks the reverse and blocks with a "parameters" message; a layout-only node move stays non-stale and promotable; both validation snapshot kinds record `topology.content_hash`/`parameters.content_hash`; and the same topology/parameters distinction holds for structured-draft promotion errors on a parameter-only asset edit versus a structural asset removal. Full suite (180 tests, 1 skipped) green, including the pre-existing hydraulic stale-promotion regression tests. Verified end-to-end via chrome-devtools MCP against the real PostgreSQL-backed app with the real Julia validator: on an existing promoted hydraulic v3 diagram, a parameter-only edit (reservoir max storage) surfaced "Hydraulic v3 validation is stale after parameters edits" in the UI with promotion disabled, and a topology-only edit (unit intake rewire) surfaced "...stale after topology edits"; re-validating cleared staleness and promoted a new version each time. On a structured draft, a parameter-only edit (battery max charge) was blocked from promotion pre-revalidation and re-validating promoted version 2 cleanly. No frontend changes were needed since the existing UI already renders the validation `summary` string generically; explicit topology/parameters surfacing in React remains TS1-006. |

## Regression Guard

Every slice that changes backend persistence or generation should run focused
Python tests for scenario versions, structured drafts, hydraulic diagrams and
manual runs.

Slices changing React should run the relevant frontend unit tests and API type
checks.

Slices changing Julia-facing payloads must keep the Julia optimizer regression
suite green.
