# BESS-TS5-010: Review Constraints And Indexes For Real Query Patterns

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-31
Fecha de termino planificada: 2026-07-31

## User stories covered

14, 15

## What to build

Ground performance hardening in the query patterns TS-2 through TS-4 actually
created, not speculation: browsing the project catalog, reading one set's
values by date range, resolving a variant's bound signals, loading a run's
indexed results, comparing two runs, and scanning candidates for rebuild or
cleanup. Inventory those hot paths, review which constraints and indexes
support them, and add the missing ones.

Schema changes ship as idempotent routines that work on both local SQLite and
PostgreSQL, so environments can be repaired safely by re-running them. Guard
tests assert query shapes — the intended access paths and the absence of full
scans on hot paths — rather than exact timings, per the PRD's testing
decision. All existing suites stay green after constraint changes.

## Acceptance criteria

- [ ] The main TS-2 through TS-4 query patterns (catalog browse, range reads, variant resolution, run result reads, comparison, rebuild/cleanup scans) are inventoried with their supporting constraints and indexes.
- [ ] Missing indexes and constraints are added via idempotent schema routines that work on both SQLite and PostgreSQL.
- [ ] Guard tests assert query shapes rather than exact timings.
- [ ] The full existing Python suite stays green after constraint and index changes.

## Blocked by

BESS-TS5-001 through BESS-TS5-005
