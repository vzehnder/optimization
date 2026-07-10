# BESS-TS6-009: Run Rolling-Horizon Automation With Auditable Snapshots

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-08-11
Fecha de termino planificada: 2026-08-12

## User stories covered

12

## What to build

Extend the scheduling built in BESS-TS6-008 with rolling horizons: instead of
a fixed date range, a schedule declares a range rule that advances with each
execution (for example, every day run the next seven days). Each tick
resolves the rule to a concrete range at fire time and then behaves exactly
like any run: coverage validation against that range, immutable snapshot,
run, artifacts and indexed results.

The rolling sequence must be auditable as a sequence: from a schedule the
analyst can see every run it produced, each with its concrete resolved range
and full lineage, and from any run the analyst can see which schedule and
which tick produced it. Reproducibility holds per tick — each snapshot froze
exactly what that execution used, so the sequence can be audited even after
sources kept moving forward.

A failing tick (missing coverage for the advanced range, stale variant)
records its failure and does not break subsequent ticks, so one bad day of
data does not silently halt the automation.

## Acceptance criteria

- [ ] A schedule can declare a rolling range rule that resolves to a concrete date range at each execution.
- [ ] Each tick produces its own immutable snapshot and run with the resolved range and full lineage, reproducible independently of later ticks.
- [ ] The schedule's execution history lists every produced run with its resolved range, and each run links back to its schedule and tick.
- [ ] A failing tick records its failure visibly and subsequent ticks still execute.
- [ ] Rolling-range resolution is a pure/deep module covered by tests without the UI.

## Blocked by

BESS-TS6-008
