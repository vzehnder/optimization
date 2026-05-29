# BESS-ITER2-000: Review One-Bus Mathematical Formulation

Status: Done
Type: HITL
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

18, 19, 20, 21, 29

## What to build

Review and approve the one-bus hybrid system mathematical formulation before implementation starts.

The review should confirm that the formulation supports renewable generation, BESS, grid import/export, optional load, curtailment, battery terminal conditions, battery degradation, and anti-simultaneity constraints while remaining a single logical bus model.

## Acceptance criteria

- [x] The one-bus balance convention is accepted or corrected.
- [x] Renewable used and curtailed variables are accepted or corrected.
- [x] Grid import/export variables and anti-simultaneity behavior are accepted or corrected.
- [x] Battery physics reuse from iteration 1 is accepted or corrected.
- [x] Objective terms and sign conventions are accepted or corrected.
- [x] Validation requirements are accepted or corrected.
- [x] Out-of-scope network behavior remains excluded.

## Accepted decisions

- Accepted the one-bus balance convention:
  grid imports plus renewable used plus battery discharge equals grid exports plus battery charge plus load.
- Accepted renewable variables as separate nonnegative used and curtailed power variables linked by availability.
- Accepted separate grid import and export variables, with anti-simultaneity enabled by default and finite bounds required for any binary formulation.
- Accepted reuse of iteration 1 battery physics: bus-side charge/discharge power, end-of-period stored energy, efficiencies, terminal modes, optional anti-simultaneity, and optional linear delta-SOC degradation.
- Accepted the objective sign convention: maximize export revenue minus import cost, battery degradation cost, and optional renewable curtailment penalty.
- Accepted validation-before-model-construction requirements for schema, graph, time series, battery, renewable, load, and grid inputs.
- Confirmed that physical network behavior remains out of scope: no multiple physical buses, AC/DC flow, edge capacity, edge loss, direction, impedance, or network constraints.

No corrections were required in `docs/iter2/mathematical_model.md`.

## Verification

Documented accepted decisions in this issue. No mathematical model corrections were needed.

## Blocked by

None - can start immediately.
