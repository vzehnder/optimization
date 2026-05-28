# BESS-ITER2-002: Load And Validate System Graph Cases

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## What to build

Implement loading and validation for system graph cases from JSON.

The loader should produce validated graph-level data without building a JuMP model. It should fail fast with explicit messages for malformed JSON, unsupported schema versions, invalid graph structure, invalid asset parameters, and invalid time series.

## Acceptance criteria

- [ ] A system case can be loaded from a JSON file.
- [ ] Unsupported or missing schema versions are rejected.
- [ ] Duplicate node IDs are rejected.
- [ ] Unknown node types are rejected.
- [ ] Missing bus/PCC node is rejected.
- [ ] Multiple bus/PCC nodes are rejected.
- [ ] Edges referencing missing nodes are rejected.
- [ ] Disconnected asset nodes are rejected.
- [ ] Nonpositive durations are rejected.
- [ ] Missing or nonfinite prices are rejected.
- [ ] Negative renewable availability is rejected.
- [ ] Missing renewable availability for a renewable asset is rejected.
- [ ] Negative load demand is rejected.
- [ ] Missing load demand for a load asset is rejected.
- [ ] Invalid BESS parameters are rejected with messages consistent with iteration 1 behavior.
- [ ] Negative grid limits are rejected.

## Verification

Run the Julia test suite covering valid and invalid system graph cases.

## Blocked by

BESS-ITER2-001
