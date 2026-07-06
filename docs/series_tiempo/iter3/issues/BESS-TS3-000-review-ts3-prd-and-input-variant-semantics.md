# BESS-TS3-000: Review TS-3 PRD And Input Variant Semantics

Status: Todo
Type: HITL
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-07
Fecha de termino planificada: 2026-07-07

## User stories covered

1 through 22

## What to build

Review and accept the TS-3 PRD before implementation starts. The review should
confirm the semantic model of input variants per case: an `InputSeriesVariant`
binds required case signals to `TimeSeriesSet`/`TimeSeriesSignal` without
copying values, each `OptimizationCase` has a default variant, the run date
range belongs to the execution snapshot (not the variant), and running from a
variant creates or reuses an immutable technical snapshot compatible with the
existing run infrastructure.

The outcome should be a short accepted-decision record in the iteration docs,
including any corrections to the PRD if the variant model, binding semantics,
stale rules, required-signal families or snapshot policy needs adjustment.

## Acceptance criteria

- [ ] The decision that variants store bindings (not copied series values) is accepted or corrected.
- [ ] The one-default-variant-per-case policy is accepted.
- [ ] The decision that the date range is chosen at run time and frozen in the execution snapshot (not stored on the variant) is accepted.
- [ ] The exact-period-compatibility rule (no implicit resampling in TS-3) is confirmed.
- [ ] The policy that running from a variant creates or reuses the technical snapshot automatically (manual `ScenarioVersion` no longer the main path) is accepted.
- [ ] The stale semantics (bound set revision/hash change, topology change, parameter change) are accepted, including whether a stale variant blocks runs until revalidation.
- [ ] The required-signal families (grid prices, load demand, renewable availability, hydraulic inflows, reach minimum flows) and their discovery from case topology/parameters are agreed.
- [ ] The out-of-scope list (no result series in BBDD, no resampling, no advanced comparison UI, no scheduled runs, no client-facing variant editing) is confirmed.
- [ ] Any PRD correction is committed before downstream TS-3 implementation issues begin.

## Blocked by

None - can start immediately.
