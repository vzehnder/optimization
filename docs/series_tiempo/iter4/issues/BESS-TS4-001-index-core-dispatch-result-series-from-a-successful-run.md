# BESS-TS4-001: Index Core Dispatch Result Series From A Successful Run

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-09
Fecha de termino planificada: 2026-07-10

## User stories covered

1, 2, 3, 6, 7, 8, 18

## What to build

The tracer bullet for the result-series workflow: an analyst runs a simple
grid-plus-BESS case to success and, after the run's artifacts are registered,
the system automatically indexes the core `dispatch.csv` series in BBDD tied
to the run and its execution snapshot. When the analyst opens the run's
results table, the backend serves the indexed data from BBDD instead of
re-reading the CSV, falling back to artifacts for runs that have no indexed
results.

The slice cuts through every layer with the thinnest possible path: one
storage model (per the BESS-TS4-000 decision), one artifact parsed
(`dispatch.csv`), one core signal scope (grid import/export power, prices and
market value, BESS charge/discharge and stored energy), one read surface (the
run results table) and an unchanged React rendering. Artifact parsing, result
normalization and BBDD writes live in a deep module testable without UI.
Signal-family breadth, asset-level rows, summary KPIs, full lineage,
idempotency hardening, charts, rebuild and comparison belong to later slices.

## Acceptance criteria

- [ ] A successful run automatically indexes its core dispatch series (grid import/export, price and market value, BESS charge/discharge and energy) in BBDD after artifact registration.
- [ ] Indexed result records are linked to the run and its execution snapshot.
- [ ] Artifacts continue to be produced and registered unchanged; indexing adds a second trail, it does not replace the first.
- [ ] The run results table endpoint serves indexed data from BBDD when present and falls back to artifacts otherwise.
- [ ] The React results table renders from BBDD-served data without visible regression.
- [ ] Artifact parsing, result normalization and BBDD writes live in deep modules testable without UI.
- [ ] Runs that predate result indexing keep serving their results from artifacts.

## Blocked by

BESS-TS4-000
