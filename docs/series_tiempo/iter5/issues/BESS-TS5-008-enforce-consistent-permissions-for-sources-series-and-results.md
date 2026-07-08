# BESS-TS5-008: Enforce Consistent Permissions For Sources, Series And Results

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-28
Fecha de termino planificada: 2026-07-29

## User stories covered

8

## What to build

Implement the permission matrix accepted in BESS-TS5-000 so clients only ever
see intended data. Analysts see their projects' sources, input series, result
series and publications; admins manage users and access; clients see only
published outputs — never raw input series, uploaded sources, or unpublished
result series — and this holds consistently across every surface: the generic
catalog, adapter-read hydraulic series, extracted sets, run result indexes,
artifacts and publications.

Permission checks are enforced by the API through a shared deep module or
dependency, not merely hidden by the UI: a client hitting a catalog, source,
variant or result endpoint directly is denied. Existing publication and
dashboard flows keep working unchanged for allowed users.

## Acceptance criteria

- [ ] Client users cannot read input series, sources or unpublished result series through any endpoint, including adapter and extraction surfaces.
- [ ] Analyst and admin visibility matches the accepted permission matrix across catalog, variants, results and publications.
- [ ] Permission checks live in a shared deep module or dependency enforced by the API, not only hidden by the UI.
- [ ] Permission tests cover analyst, admin and client visibility for input series, result series, sources and published outputs.
- [ ] Existing publication and dashboard flows keep working for allowed users.

## Blocked by

BESS-TS5-000
