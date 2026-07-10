# BESS-TS6-008: Schedule Reruns Using Case, Variant And Date Range

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-08-06
Fecha de termino planificada: 2026-08-10

## User stories covered

11, 13

## What to build

The tracer bullet for TS-6 automation: a scheduled rerun is defined
declaratively as a case plus a parameter version, an input variant and a date
range, with a cadence — never as a hand-authored `system_case_json`. When the
schedule fires (the concrete trigger mechanism comes from the BESS-TS6-000
decision record), execution follows exactly the manual path: the same
staleness and coverage gates, the same immutable snapshot materialization,
the same run pipeline, the same artifacts and the same TS-4 result indexing.

Automation matching manual semantics is the core of this slice: a scheduled
run's snapshot records the same lineage a manual run records (topology,
parameters, variant, series revisions/hashes, range), plus metadata saying
which schedule produced it. Its results appear in run listings and run
comparisons like any manual run, closing user story 13 by construction —
the automated path reuses the indexing pipeline rather than duplicating it.

A schedule whose variant went stale or whose series no longer cover the range
fails the same way a manual run would, recording the failure visibly instead
of running with wrong data. Defining and managing schedules is gated by the
permission rules agreed in the decision record.

## Acceptance criteria

- [ ] A scheduled rerun is defined as case + parameter version + input variant + date range + cadence; no hand-authored JSON configuration exists.
- [ ] A fired schedule produces an immutable snapshot and run with the same lineage a manual run records, plus metadata identifying the schedule.
- [ ] Scheduled runs pass through the same staleness and coverage gates as manual runs, and failures are recorded visibly without corrupting the schedule.
- [ ] Results of scheduled runs are indexed in the database through the existing TS-4 pipeline and appear in run listings and comparisons like manual runs.
- [ ] Schedule definition and management respect the permission rules agreed in the decision record.
- [ ] Manual variant-driven runs are unchanged, proven by the existing regression suite staying green.
- [ ] Schedule planning and execution live in deep modules covered by tests without the UI.

## Blocked by

BESS-TS6-000
