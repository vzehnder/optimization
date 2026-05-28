# BESS-ITER2-002: Harden Graph And Time-Series Validation

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

2, 4, 5, 6, 7, 8, 10, 30

## What to build

Harden the system case loader so invalid graph and time-series inputs fail before JuMP model construction with explicit errors.

This slice should keep the minimal valid case working while adding focused invalid-input coverage.

## Acceptance criteria

- [ ] Missing or unsupported schema versions are rejected.
- [ ] Duplicate node IDs are rejected.
- [ ] Unknown node types are rejected.
- [ ] Missing bus/PCC node is rejected.
- [ ] Multiple bus/PCC nodes are rejected.
- [ ] Edges referencing missing nodes are rejected.
- [ ] Asset nodes disconnected from the single bus are rejected.
- [ ] Edge capacities, edge losses, and network-flow fields are ignored or rejected according to the accepted contract.
- [ ] Empty time series are rejected.
- [ ] Nonpositive durations are rejected.
- [ ] Missing or nonfinite prices are rejected.
- [ ] Duplicate or unsorted timestamps are rejected.
- [ ] Invalid battery bounds, efficiencies, terminal settings, and degradation costs are rejected with clear messages.
- [ ] The minimal valid system case from BESS-ITER2-001 still solves.
- [ ] Existing single-BESS tests remain green after the slice.

## Verification

Run validation tests for invalid graph and time-series cases, then run the minimal system solve and existing MVP tests.

## Blocked by

BESS-ITER2-001
