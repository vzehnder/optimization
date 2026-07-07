# BESS-TS3-008: Run One Case With Two Variants And Preserve Legacy Runs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-28
Fecha de termino planificada: 2026-07-29
Fecha de inicio real: 2026-07-07
Fecha de termino real: 2026-07-07

## User stories covered

15, 21

## What to build

Prove the core comparison promise and protect the old path. The same case runs
with two different variants (for example the default and a clone bound to a
different price set) over the same date range, producing two runs with
distinct technical snapshots, distinct input hashes and distinguishable
lineage in the case run list — no topology or parameters duplicated.

At the same time, the legacy scenario-version run APIs remain available: runs
launched from an existing `ScenarioVersion` keep working unchanged, and the
existing manual-run and scenario-version test suites stay green as the
regression contract.

## Acceptance criteria

- [x] The same case runs end to end with two different variants over the same range, producing distinct snapshots and distinct input series hashes.
- [x] Both runs appear in the case run list with lineage that distinguishes which variant produced each.
- [x] Legacy scenario-version runs remain executable through the existing APIs without behavior changes.
- [x] Existing manual-run and scenario-version tests pass unchanged as regression guards.
- [x] An end-to-end test covers the two-variant comparison scenario.

## Blocked by

BESS-TS3-004, BESS-TS3-007

## Resolution

Implemented TDD-first. See `docs/series_tiempo/iter3/issues/tracker_ts3.md` progress log
entry for 2026-07-07 (BESS-TS3-008) for the full implementation and verification
narrative: a new backend test in `tests/test_ts3_case_variant_api.py` proves the
two-variant comparison and legacy-run coexistence at the API level; the case run
list (`RunList` in `frontend/src/Workspace.tsx`) was extended to show which input
variant produced each run, since that was the one real gap this issue surfaced.
Verified against real PostgreSQL and real Julia via chrome-devtools MCP.
