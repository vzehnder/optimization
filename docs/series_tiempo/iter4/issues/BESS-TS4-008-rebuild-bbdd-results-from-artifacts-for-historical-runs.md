# BESS-TS4-008: Rebuild BBDD Results From Artifacts For Historical Runs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-27
Fecha de termino planificada: 2026-07-27

## User stories covered

14

## What to build

A rebuild action or tool that, given a historical successful run with
registered artifacts and no (or incomplete) indexed results, parses the
artifacts and populates the BBDD result series. The rebuild must reuse the
same parsing, normalization, lineage and write modules as live post-run
indexing, so a rebuilt run is indistinguishable from a freshly indexed one.

Rebuild must be idempotent: already-indexed runs are skipped unless explicitly
forced, and re-running the tool converges. It must report what was indexed,
skipped and failed. Legacy runs without TS-3 variant lineage rebuild with
absent lineage fields and still serve their tables and charts from BBDD
afterwards.

## Acceptance criteria

- [ ] A rebuild action or tool indexes a historical successful run's results from its registered artifacts.
- [ ] Rebuild reuses the same parsing, normalization, lineage and write modules as post-run indexing.
- [ ] Rebuild is idempotent and skips already-indexed runs unless forced.
- [ ] Rebuild reports what was indexed, skipped and failed.
- [ ] Legacy runs without TS-3 lineage rebuild with absent lineage fields and serve tables and charts from BBDD afterwards.

## Blocked by

BESS-TS4-005, BESS-TS4-006
