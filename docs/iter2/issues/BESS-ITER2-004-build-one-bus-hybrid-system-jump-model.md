# BESS-ITER2-004: Build One-Bus Hybrid System JuMP Model

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## What to build

Implement the one-bus hybrid system JuMP model using normalized optimization case data.

The model should support renewable used/curtailed variables, grid import/export variables, local load, BESS charge/discharge and energy variables, battery degradation, terminal conditions, and configurable anti-simultaneity behavior.

## Acceptance criteria

- [ ] The system model builder receives normalized optimization data, not raw JSON.
- [ ] The model enforces the common one-bus balance in every period.
- [ ] Renewable availability is split into used and curtailed power.
- [ ] Local load enters the bus balance as fixed demand.
- [ ] Grid import and export are separate nonnegative variables.
- [ ] Grid import/export anti-simultaneity is enabled by default and configurable.
- [ ] Battery energy balance matches the iteration 1 convention.
- [ ] Battery charge/discharge anti-simultaneity remains configurable.
- [ ] Battery terminal conditions remain supported.
- [ ] Battery linear delta-SOC degradation remains supported.
- [ ] The objective maximizes net grid market value minus degradation and optional curtailment penalties.
- [ ] The model solves the primary renewable plus BESS plus grid case with HiGHS.

## Verification

Run model-level tests for balance, dispatch behavior, curtailment, load service, anti-simultaneity, terminal conditions, and objective sign convention.

## Blocked by

BESS-ITER2-003
