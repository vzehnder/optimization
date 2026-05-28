# BESS-MVP-002: Load And Validate Arbitrage Case Data

Status: Done
Type: AFK
Source: `docs/prd_bess_dispatch.md`

## What to build

Implement the first end-to-end data path from repository case files into validated internal structs. A user should be able to load the sample arbitrage case and receive a complete `CaseData` object that is ready for model construction.

The model builder must remain independent from file paths and data source details. This issue should make YAML and CSV the first concrete data source while preserving the future boundary for Excel and database loaders.

## Acceptance criteria

- [x] A sample arbitrage case exists with scalar BESS parameters, run configuration, and a price time series.
- [x] Loading the sample case returns validated internal structs matching the PRD contract.
- [x] Validation rejects nonpositive durations.
- [x] Validation rejects missing or invalid prices.
- [x] Validation rejects invalid energy bounds and invalid initial energy.
- [x] Validation rejects invalid charge and discharge efficiencies.
- [x] Validation rejects invalid terminal configuration.
- [x] Tests cover successful loading and representative validation failures.

## Blocked by

- BESS-MVP-001
