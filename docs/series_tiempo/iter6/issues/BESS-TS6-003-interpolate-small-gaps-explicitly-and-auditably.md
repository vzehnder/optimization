# BESS-TS6-003: Interpolate Small Gaps Explicitly And Auditably

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-07-22
Fecha de termino planificada: 2026-07-23

## User stories covered

2, 5, 6

## What to build

Add an explicit gap-filling transformation to the allowlist: an analyst takes
a set with small gaps (missing periods inside its horizon) and produces a
derived set where those gaps are filled with a declared method (linear
interpolation first), under a declared maximum gap size.

Missing-data handling must be auditable, never silent: the transformation
parameters declare the method and the maximum gap it may fill, and the
derived set records which periods were filled so a reviewer can distinguish
observed values from interpolated ones. Gaps larger than the declared
maximum cause the transformation to fail with a clear message naming the
signal and the offending range, instead of quietly fabricating data.

As with resampling, this stays a pre-run step: TS-2 import validation and
TS-3 coverage validation keep rejecting incomplete data at their own gates,
and the analyst closes real gaps by producing an explicit derived version and
binding it, so every filled value is traceable to a versioned decision.

## Acceptance criteria

- [ ] An analyst can fill small gaps in a catalog set from the UI and obtain a derived set with the method and maximum gap recorded as validated parameters.
- [ ] The derived set records which periods were filled, distinguishable from observed values when browsing the set.
- [ ] Gaps larger than the declared maximum fail the transformation with a clear message naming the signal and range; no data is written.
- [ ] Existing TS-2 import validation and TS-3 range-coverage validation behavior is unchanged.
- [ ] The derived set records full lineage and is bindable in a case input variant.
- [ ] The interpolation implementation is a pure/deep module covered by tests without the UI.

## Blocked by

BESS-TS6-001
