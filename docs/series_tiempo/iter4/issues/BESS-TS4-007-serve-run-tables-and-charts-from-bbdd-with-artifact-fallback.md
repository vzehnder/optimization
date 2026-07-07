# BESS-TS4-007: Serve Run Tables And Charts From BBDD With Artifact Fallback

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-23
Fecha de termino planificada: 2026-07-24

## User stories covered

13, 21

## What to build

Complete the BBDD-first read path across the run detail: every results
surface (dispatch tables, asset tables, summary and charts) serves from BBDD
whenever indexed data exists and falls back to artifacts otherwise. Historical
runs that were never indexed must keep rendering exactly as today, so no data
is lost and no migration is forced.

Partial indexing must degrade gracefully per surface: if a run has indexed
dispatch series but no indexed KPIs, the tables serve from BBDD while the
summary falls back to artifacts, without failing the whole view. Publications
and dashboards built on run results (iteration 6 client views) must keep
working unchanged, as the first step toward eventually feeding them from BBDD.

## Acceptance criteria

- [ ] Run results tables and charts serve from BBDD when indexed data exists.
- [ ] Historical runs without indexed results keep rendering from artifacts with no visible regression.
- [ ] Partially indexed runs degrade gracefully per surface instead of failing the whole run view.
- [ ] Existing publication and dashboard views keep working (regression suite green).
- [ ] Tests cover BBDD-served, artifact-fallback and mixed (partially indexed) runs.

## Blocked by

BESS-TS4-002, BESS-TS4-003, BESS-TS4-004
