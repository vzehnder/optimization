# BESS-TS1-001: Introduce Case Hierarchy Provenance For Existing Runs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-06
Fecha de termino planificada: 2026-07-07
Fecha de inicio real: 2026-07-03
Fecha de termino real: 2026-07-03

## User stories covered

1 through 7, 16 through 20

## What to build

Add the first end-to-end hierarchy provenance path without changing optimizer
behavior. A scenario version created by existing flows should record
machine-readable provenance for the logical topology and parameter assumptions
that produced its `system_case_json`, even if the first implementation uses
metadata adapters rather than fully normalized version tables.

The slice should be demoable by creating a normal scenario version and seeing
topology and parameter provenance attached to that immutable snapshot.

## Acceptance criteria

- [x] New scenario versions can record topology provenance metadata.
- [x] New scenario versions can record parameter provenance metadata.
- [x] Provenance includes stable hash or revision identifiers suitable for stale checks.
- [x] Existing scenario-version immutability remains enforced.
- [x] Existing manual run creation from scenario versions still works.
- [x] Existing scenario version detail APIs still return prior fields.
- [x] Backend tests prove provenance is recorded for a newly created scenario version.
- [x] Backend tests prove old scenario versions without provenance still load safely.

## Implementation notes

- Added `derive_case_hierarchy_provenance(document)` in `app/persistence.py`: a
  schema-agnostic split of a `system_case_json` document into a `topology` view
  (node `id`/`type` identity plus `edges` connectivity) and a `parameters` view
  (every other field, including per-node parameter values, `time_series`,
  `constraints` and `solver`). Each view is hashed with SHA-256 into a stable
  `sha256:...` content hash.
- Wired the split into `AnalystStore.create_scenario_version`, the single choke
  point already used by all four version-creation paths (raw paste, file
  upload, structured-draft promotion, hydraulic-diagram promotion). Provenance
  is merged into the existing `generation_metadata_json` column, so no schema
  migration was needed and draft/hydraulic-specific metadata (`kind`,
  `source`, `mapping`, `validation_hash`, ...) is preserved unchanged.
- No React or API contract changes: `generation_metadata` was already returned
  as an untyped `Record<string, unknown>` by both the list and detail
  endpoints, so old scenario versions without a `topology`/`parameters` key
  keep loading with an empty or partial `generation_metadata` dict instead of
  erroring.

## Verification

- `.\.venv\Scripts\python.exe -m unittest tests.test_case_hierarchy_provenance -v`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` (161 passed, 1 skipped — Postgres integration test requires `POSTGRES_TEST_DATABASE_URL`)
- Manual verification against the real PostgreSQL-backed app (`.env` credentials) via chrome-devtools MCP: created a project/scenario, pasted the sample system case, confirmed the created scenario version's `generation_metadata` in the React JSON viewer includes `topology.content_hash` and `parameters.content_hash`.

## Blocked by

BESS-TS1-000
