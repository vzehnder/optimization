# BESS-MVP-002: Load And Validate Arbitrage Case Data

Status: Todo
Type: AFK
Source: `docs/prd_bess_dispatch.md`

## What to build

Implement the first end-to-end data path from repository case files into validated internal structs. A user should be able to load the sample arbitrage case and receive a complete `CaseData` object that is ready for model construction.

The model builder must remain independent from file paths and data source details. This issue should make YAML and CSV the first concrete data source while preserving the future boundary for Excel and database loaders.

## Acceptance criteria

- [ ] A sample arbitrage case exists with scalar BESS parameters, run configuration, and a price time series.
- [ ] Loading the sample case returns validated internal structs matching the PRD contract.
- [ ] Validation rejects nonpositive durations.
- [ ] Validation rejects missing or invalid prices.
- [ ] Validation rejects invalid energy bounds and invalid initial energy.
- [ ] Validation rejects invalid charge and discharge efficiencies.
- [ ] Validation rejects invalid terminal configuration.
- [ ] Tests cover successful loading and representative validation failures.

## Blocked by

- BESS-MVP-001
