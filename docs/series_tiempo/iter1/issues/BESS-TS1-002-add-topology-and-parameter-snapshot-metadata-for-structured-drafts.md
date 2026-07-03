# BESS-TS1-002: Add Topology And Parameter Snapshot Metadata For Structured Drafts

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-08
Fecha de termino planificada: 2026-07-09
Fecha de inicio real: 2026-07-03
Fecha de termino real: 2026-07-03

## User stories covered

1 through 12, 15 through 18

## What to build

Extend the structured draft promotion path so it can split the generated model
into topology-like and parameter-like snapshot metadata while still producing
the same executable `system_case_json` as today.

The analyst should be able to promote a structured draft and later inspect that
the resulting version came from a specific topology snapshot and parameter
snapshot, without needing to understand the raw JSON.

## Acceptance criteria

- [x] Structured draft generation identifies topology-relevant content.
- [x] Structured draft generation identifies parameter-relevant content.
- [x] Promotion from structured draft stores topology and parameter snapshot metadata.
- [x] The generated `system_case_json` remains equivalent to the current structured draft output.
- [x] Existing CSV/XLSX source-mapping promotion still works.
- [x] Existing paste/upload JSON flow remains unchanged.
- [x] Backend tests cover structured draft promotion with hierarchy metadata.
- [x] Regression tests prove existing Iteration 4/5 structured draft flows still pass.

## Implementation notes

- No production code change was needed. `BESS-TS1-001` already wired
  `derive_case_hierarchy_provenance` into `AnalystStore.create_scenario_version`,
  the single choke point used by every version-creation path, including
  structured draft promotion (`promote_generated_system_case` ->
  `save_validated_scenario_version` -> `create_scenario_version`). Since
  `generate_system_case_from_draft` always emits `bess_system_dispatch.v2`
  documents with `nodes`/`edges`, the schema-agnostic topology/parameter split
  already applies to structured-draft-originated versions.
- Added `tests/test_structured_draft_hierarchy_provenance.py` as
  characterization tests proving this behavior specifically for the
  structured draft path (as opposed to `test_case_hierarchy_provenance.py`,
  which only exercises the raw paste/upload path): a promoted CSV-mapped
  draft records `topology`/`parameters` content hashes; editing only a
  battery parameter keeps the topology hash stable while changing the
  parameters hash; removing an asset changes the topology hash; and hydro CSV
  mapping metadata (`kind`, `source`, `mapping`) coexists with the new
  `topology`/`parameters` keys without clobbering either.
- No changes were needed to `generation_metadata_from_draft` (CSV/XLSX mapping
  metadata) or to the paste/upload JSON path — both continue to work
  unchanged, confirmed by the existing regression suite.

## Verification

- `.\.venv\Scripts\python.exe -m unittest tests.test_structured_draft_hierarchy_provenance -v` (4 passed)
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` (165 passed, 1 skipped — Postgres integration test requires `POSTGRES_TEST_DATABASE_URL`)
- Manual verification against the real PostgreSQL-backed app (`.env` credentials) via chrome-devtools MCP: created a project/scenario, built a structured draft (BESS + load assets) with an uploaded CSV time-series source, validated it against real Julia, and promoted it. The resulting `Version 1` generation metadata panel shows both `kind: "structured_draft"` with its CSV `source`/`mapping` details and the new `topology.content_hash` / `parameters.content_hash` keys side by side.

## Blocked by

BESS-TS1-001
