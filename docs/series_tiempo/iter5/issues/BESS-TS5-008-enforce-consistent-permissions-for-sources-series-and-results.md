# BESS-TS5-008: Enforce Consistent Permissions For Sources, Series And Results

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-28
Fecha de termino planificada: 2026-07-29
Fecha de inicio real: 2026-07-10
Fecha de termino real: 2026-07-10

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

- [x] Client users cannot read input series, sources or unpublished result series through any endpoint, including adapter and extraction surfaces.
- [x] Analyst and admin visibility matches the accepted permission matrix across catalog, variants, results and publications.
- [x] Permission checks live in a shared deep module or dependency enforced by the API, not only hidden by the UI.
- [x] Permission tests cover analyst, admin and client visibility for input series, result series, sources and published outputs.
- [x] Existing publication and dashboard flows keep working for allowed users.

## Blocked by

BESS-TS5-000

## Resolution

No production code changed: `require_authenticated_app_boundary`
(`app/main.py`) already gates every non-`/api/client` route behind
`INTERNAL_USER_ROLES` through the shared `AuthorizationService`
(`app/auth.py`), so every TS5-001..007 endpoint (catalog, hydraulic
adapter, extraction, migration, variants, results, comparisons,
publication preview) was already covered by construction. This issue's
work was proving it: `tests/test_ts5_permission_matrix.py` (7 tests)
sweeps client-denial across every TS-5 surface, proves analyst/admin
parity, and proves the client-vs-published-output boundary holds even
when both surfaces reference the same run. See
`docs/series_tiempo/iter5/issues/tracker_ts5.md` progress log
(2026-07-10) for the full backend-suite and Chrome verification
evidence.
