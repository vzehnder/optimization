# BESS-ITER2-003: Normalize Graph Data Into Optimization Case Data

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## What to build

Create the graph normalization layer that converts validated graph data into solver-facing optimization case data.

This is the deep module for iteration 2. It should hide raw JSON shape, UI metadata, and graph traversal details from the JuMP model builder.

## Acceptance criteria

- [ ] Validated graph data can be normalized without reading files.
- [ ] Asset IDs are preserved in normalized data.
- [ ] Batteries, renewables, grids, and loads are grouped and indexed by type.
- [ ] Common timestamps, durations, and prices are aligned into arrays.
- [ ] Renewable availability is aligned by renewable asset and period.
- [ ] Load demand is aligned by load asset and period.
- [ ] Battery settings are resolved per battery asset.
- [ ] Grid settings are resolved per grid asset.
- [ ] Optional curtailment penalties default to zero.
- [ ] The normalizer rejects any missing time-series values missed by earlier validation.
- [ ] The normalizer output is independent of the JSON parser and future UI fields.

## Verification

Run unit tests that feed validated graph data directly to the normalizer and assert the normalized external behavior.

## Blocked by

BESS-ITER2-002
