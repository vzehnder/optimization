# BESS-TS3-008: Run One Case With Two Variants And Preserve Legacy Runs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-28
Fecha de termino planificada: 2026-07-29

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

- [ ] The same case runs end to end with two different variants over the same range, producing distinct snapshots and distinct input series hashes.
- [ ] Both runs appear in the case run list with lineage that distinguishes which variant produced each.
- [ ] Legacy scenario-version runs remain executable through the existing APIs without behavior changes.
- [ ] Existing manual-run and scenario-version tests pass unchanged as regression guards.
- [ ] An end-to-end test covers the two-variant comparison scenario.

## Blocked by

BESS-TS3-004, BESS-TS3-007
