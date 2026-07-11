# BESS-TS6-009: Run Rolling-Horizon Automation With Auditable Snapshots

Status: Done
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

- [x] A schedule can declare a rolling range rule that resolves to a concrete date range at each execution.
- [x] Each tick produces its own immutable snapshot and run with the resolved range and full lineage, reproducible independently of later ticks.
- [x] The schedule's execution history lists every produced run with its resolved range, and each run links back to its schedule and tick.
- [x] A failing tick records its failure visibly and subsequent ticks still execute.
- [x] Rolling-range resolution is a pure/deep module covered by tests without the UI.

## Blocked by

BESS-TS6-008

## Implementation Notes

- `app/schedules.py` now resolves both fixed and rolling schedule ranges through
  `resolve_schedule_range`; rolling rules are anchored on each tick's `due_at`
  with `rolling_start_offset_hours` and `rolling_duration_hours`.
- `run_schedules` persists `range_mode`, `rolling_start_offset_hours` and
  `rolling_duration_hours`; existing fixed schedules default to `range_mode =
  fixed`.
- The schedule executor now writes each tick with the concrete resolved range,
  materializes/validates that exact range, and stores the same range plus
  schedule/tick lineage in scenario-version metadata.
- Admin API and React admin UI can create rolling schedules, show the rule, and
  list every tick history row with resolved range, run id or failure message.
- Run detail lineage now surfaces the schedule name, schedule id and tick id
  from the immutable snapshot metadata.

## Verification

- `.\.venv\Scripts\python.exe -m unittest tests.test_ts6_008_schedules -v`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` -> 539 tests,
  2 skipped
- `cd frontend; npm.cmd test -- --run` -> 66 passed
- `cd frontend; npx.cmd tsc -b`
- `cd frontend; npx.cmd eslint .`
- `cd frontend; npm.cmd run api:generate`
- `cd frontend; npm.cmd run api:check`
- `cd frontend; npm.cmd run build`
- Chrome DevTools MCP + `chrome:control-chrome` live verification against
  `energy_dispatch`: created `TS6-009 Rolling Chrome schedule` for scenario 61
  / variant 29, confirmed the UI displays `rolling | offset 0h | duracion 24h`,
  ran the first due tick (`tick 3`, range `2026-07-11T00:00:00-04:00` to
  `2026-07-12T00:00:00-04:00`, `run 30`), confirmed run detail lineage shows
  `TS6-009 Rolling Chrome schedule | schedule 4 | tick 3`, triggered the next
  rolling tick with `now = 2026-07-12T01:00:00-04:00`, confirmed visible
  failure for missing coverage on `2026-07-12` to `2026-07-13`, schedule stayed
  active and advanced to `2026-07-13T00:00:00-04:00`, and Chrome console had no
  errors. Direct BBDD check: run 30 `succeeded`, 8 artifacts, 24 dispatch rows,
  48 asset rows and 1 summary index.
