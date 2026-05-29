# BESS-ITER2-002: Harden Graph And Time-Series Validation

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

2, 4, 5, 6, 7, 8, 10, 30

## What to build

Harden the system case loader so invalid graph and time-series inputs fail before JuMP model construction with explicit errors.

This slice should keep the minimal valid case working while adding focused invalid-input coverage.

## Acceptance criteria

- [x] Missing or unsupported schema versions are rejected.
- [x] Duplicate node IDs are rejected.
- [x] Unknown node types are rejected.
- [x] Missing bus/PCC node is rejected.
- [x] Multiple bus/PCC nodes are rejected.
- [x] Edges referencing missing nodes are rejected.
- [x] Asset nodes disconnected from the single bus are rejected.
- [x] Edge capacities, edge losses, and network-flow fields are ignored or rejected according to the accepted contract.
- [x] Empty time series are rejected.
- [x] Nonpositive durations are rejected.
- [x] Missing or nonfinite prices are rejected.
- [x] Duplicate or unsorted timestamps are rejected.
- [x] Invalid battery bounds, efficiencies, terminal settings, and degradation costs are rejected with clear messages.
- [x] The minimal valid system case from BESS-ITER2-001 still solves.
- [x] Existing single-BESS tests remain green after the slice.

## Implementation notes

- Hardened the `system_case` loader so schema, graph shape, edge contract, time-series ordering, duration, price, and battery parameter errors fail before JuMP model construction.
- Rejected unsupported edge fields such as capacities, losses, and network-flow metadata because iteration 2 treats edges as logical connectivity only.
- Added validation coverage for missing/unsupported schema version, duplicate IDs, unknown node types, missing/multiple bus or PCC nodes, missing edge endpoints, disconnected assets, empty/invalid time series, and invalid battery settings.

## Verification

Passed `julia --project=. -e "import Pkg; Pkg.test()"` with 222 tests, including invalid graph and time-series validation, the minimal system solve, and existing MVP tests.

## Blocked by

BESS-ITER2-001
