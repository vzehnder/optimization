# BESS-TS3-001: Run A Case From Its Default Variant End-To-End

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-08
Fecha de termino planificada: 2026-07-09

## User stories covered

1, 4, 10, 20

## What to build

The tracer bullet for the case-variant workflow: an analyst opens a case that
already has a default input variant, binds one required price signal to a
catalog set/signal, selects a run date range, and runs. The backend validates
that the binding covers the range with a compatible period, materializes the
`system_case_json` from topology + parameters + variant + range, creates (or
reuses) an immutable technical snapshot and launches it through the existing
manual-run infrastructure.

The slice cuts through every layer with the thinnest possible path: a default
variant per case, one binding for one signal family (grid price), a date-range
picker, snapshot materialization isolated in a deep module testable without
UI, and a minimal React flow to bind, pick a range and launch. Required-signal
discovery breadth, clone/dropdown UX, full validation matrices, stale marking
and lineage polish belong to later slices.

## Acceptance criteria

- [ ] Every `OptimizationCase` exposes a default input variant (created automatically when missing).
- [ ] The default variant can bind a required price signal to a catalog `TimeSeriesSet`/`TimeSeriesSignal` without copying values.
- [ ] A run can be launched from the case by selecting the default variant and an explicit date range.
- [ ] The backend materializes the `system_case_json` from topology, parameters, variant bindings and the selected range.
- [ ] The run references an immutable technical snapshot created or reused automatically; no manual `ScenarioVersion` step is required.
- [ ] Binding resolution, horizon slicing and snapshot generation live in deep modules testable without UI.
- [ ] The existing manual-run infrastructure executes the generated snapshot and the run reaches a terminal state.
- [ ] A minimal React flow binds the signal, selects the date range and launches the run from the case.

## Blocked by

BESS-TS3-000
