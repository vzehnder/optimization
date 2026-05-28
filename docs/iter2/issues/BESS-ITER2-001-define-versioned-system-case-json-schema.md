# BESS-ITER2-001: Define Versioned System Case JSON Schema

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## What to build

Define the versioned `system_case` JSON contract that will become the bridge from a future visual UI or Python backend into the Julia optimization engine.

The schema must describe case metadata, schema version, graph nodes, graph edges, common time series, solver configuration, and system constraint configuration.

## Acceptance criteria

- [ ] A machine-readable JSON schema exists for the system case contract.
- [ ] The schema requires `schema_version`.
- [ ] The schema supports node types `bus`, `battery`, `renewable`, `grid`, and `load`.
- [ ] The schema supports graph edges by source and target node ID.
- [ ] The schema supports common ordered time-series records.
- [ ] The schema supports renewable availability keyed by renewable asset ID.
- [ ] The schema supports load demand keyed by load asset ID.
- [ ] The schema supports grid price, duration, solver, and constraints.
- [ ] A valid minimal hybrid system example conforms to the schema.
- [ ] Invalid examples are documented for later validation tests.

## Verification

Run schema validation against the valid and invalid examples using the selected validation approach.

## Blocked by

BESS-ITER2-000
