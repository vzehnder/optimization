# BESS-TS6-002: Resample A Series Set To An Optimization Resolution

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-07-20
Fecha de termino planificada: 2026-07-21

## User stories covered

1, 5, 6

## What to build

Add a resampling transformation to the allowlist built in BESS-TS6-001: an
analyst takes a set whose resolution does not match the optimization case
(for example hourly data for a daily model, or sub-hourly measurements for an
hourly model) and produces a derived set aligned to the target resolution.

The transformation is declarative: parameters select the target resolution
and the aggregation or distribution method per signal (for example mean for
prices, sum for energy), validated against a versioned parameter schema.
Methods that make no physical sense for a signal are rejected at validation
time rather than producing silently wrong data.

Resampling stays an explicit pre-run step, never an implicit run-time
behavior: the run pipeline keeps failing with a clear message when bound
series do not match the selected range and resolution, exactly as TS-3
established. The analyst resolves that failure by resampling first and
binding the derived set in the variant, so every resolution change is a
visible, versioned decision with lineage.

The derived set records the same lineage contract as the tracer bullet and is
bindable in a case input variant, closing the loop: resample, bind, run.

## Acceptance criteria

- [ ] An analyst can resample a catalog set to a target resolution from the UI and obtain a derived set with the chosen aggregation methods recorded.
- [ ] Aggregation/distribution methods are validated per signal against a versioned parameter schema, rejecting physically meaningless combinations.
- [ ] The run pipeline still fails clearly when bound series do not match the selected range and resolution; no implicit resampling happens at run time.
- [ ] The derived set records full lineage (input set, revision/hash, parameters, schema version, implementation version) and is bindable in a case input variant.
- [ ] A case run using the resampled derived set completes end-to-end.
- [ ] The resampling implementation is a pure/deep module covered by tests without the UI.

## Blocked by

BESS-TS6-001
