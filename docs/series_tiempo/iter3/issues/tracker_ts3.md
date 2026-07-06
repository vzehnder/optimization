# BESS TS-3 Issue Tracker

This document is the local tracker for TS-3: input series variants per case,
default variant and run date range, derived from
`docs/series_tiempo/iter3/prd.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the
`ready-for-agent` triage label.

## Date Policy

All issues generated from this point forward include:

- `Fecha de inicio planificada`
- `Fecha de termino planificada`

Actual start/end dates can be added or corrected by the implementer when work
really begins and ends.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Fecha de inicio planificada | Fecha de termino planificada | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BESS-TS3-000 | Review TS-3 PRD And Input Variant Semantics | HITL | ready-for-agent | Todo | 2026-07-07 | 2026-07-07 | None | [BESS-TS3-000-review-ts3-prd-and-input-variant-semantics.md](BESS-TS3-000-review-ts3-prd-and-input-variant-semantics.md) |
| BESS-TS3-001 | Run A Case From Its Default Variant End-To-End | AFK | ready-for-agent | Todo | 2026-07-08 | 2026-07-09 | BESS-TS3-000 | [BESS-TS3-001-run-a-case-from-its-default-variant-end-to-end.md](BESS-TS3-001-run-a-case-from-its-default-variant-end-to-end.md) |
| BESS-TS3-002 | Discover Required Signals And Surface Missing Bindings | AFK | ready-for-agent | Todo | 2026-07-10 | 2026-07-13 | BESS-TS3-001 | [BESS-TS3-002-discover-required-signals-and-surface-missing-bindings.md](BESS-TS3-002-discover-required-signals-and-surface-missing-bindings.md) |
| BESS-TS3-003 | Enforce Range Coverage And Horizon Compatibility Validation | AFK | ready-for-agent | Todo | 2026-07-14 | 2026-07-15 | BESS-TS3-002 | [BESS-TS3-003-enforce-range-coverage-and-horizon-compatibility-validation.md](BESS-TS3-003-enforce-range-coverage-and-horizon-compatibility-validation.md) |
| BESS-TS3-004 | Clone Variants And Switch Them From The Case Dropdown | AFK | ready-for-agent | Todo | 2026-07-16 | 2026-07-17 | BESS-TS3-001 | [BESS-TS3-004-clone-variants-and-switch-them-from-the-case-dropdown.md](BESS-TS3-004-clone-variants-and-switch-them-from-the-case-dropdown.md) |
| BESS-TS3-005 | Bind All Required Signal Families | AFK | ready-for-agent | Todo | 2026-07-20 | 2026-07-21 | BESS-TS3-002 | [BESS-TS3-005-bind-all-required-signal-families.md](BESS-TS3-005-bind-all-required-signal-families.md) |
| BESS-TS3-006 | Mark Variants Stale On Series, Topology Or Parameter Changes | AFK | ready-for-agent | Todo | 2026-07-22 | 2026-07-23 | BESS-TS3-003 | [BESS-TS3-006-mark-variants-stale-on-series-topology-or-parameter-changes.md](BESS-TS3-006-mark-variants-stale-on-series-topology-or-parameter-changes.md) |
| BESS-TS3-007 | Show Run Lineage With Variant, Range And Series Hashes | AFK | ready-for-agent | Todo | 2026-07-24 | 2026-07-27 | BESS-TS3-001, BESS-TS3-003 | [BESS-TS3-007-show-run-lineage-with-variant-range-and-series-hashes.md](BESS-TS3-007-show-run-lineage-with-variant-range-and-series-hashes.md) |
| BESS-TS3-008 | Run One Case With Two Variants And Preserve Legacy Runs | AFK | ready-for-agent | Todo | 2026-07-28 | 2026-07-29 | BESS-TS3-004, BESS-TS3-007 | [BESS-TS3-008-run-one-case-with-two-variants-and-preserve-legacy-runs.md](BESS-TS3-008-run-one-case-with-two-variants-and-preserve-legacy-runs.md) |
| BESS-TS3-009 | Finalize TS-3 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | 2026-07-30 | 2026-07-30 | BESS-TS3-001 through BESS-TS3-008 | [BESS-TS3-009-finalize-ts3-acceptance-suite-and-docs.md](BESS-TS3-009-finalize-ts3-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-TS3-000 closes the PRD review and the input-variant semantics decision record.
2. BESS-TS3-001 is the tracer bullet: default variant, one price binding, date range, materialized snapshot and a real run end to end.
3. BESS-TS3-002 adds required-signal discovery and missing-binding surfacing on top of the tracer path.
4. BESS-TS3-003 hardens range coverage and horizon compatibility validation, recording revisions and hashes.
5. BESS-TS3-004 can proceed any time after BESS-TS3-001; it adds clone and the case variant dropdown.
6. BESS-TS3-005 extends bindings to every signal family (load, renewable, hydraulic inflows, minimum flows).
7. BESS-TS3-006 adds stale detection for series revisions and topology/parameter changes, with revalidation.
8. BESS-TS3-007 completes run lineage (variant, range, revisions, hashes) with the technical snapshot hidden by default.
9. BESS-TS3-008 proves two-variant comparison on one case and locks the legacy scenario-version regression contract.
10. BESS-TS3-009 closes the iteration with acceptance coverage and docs.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-07-06 | All | Created | Initial local issue set generated from the TS-3 PRD (`docs/series_tiempo/iter3/prd.md`) and the series hierarchy roadmap. |

## Final TS-3 Verification

Run before considering TS-3 closed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```powershell
cd frontend
npm test -- --run
npx tsc -b
npx eslint .
npm run api:check
npm run build
```

Julia regression is only required if a TS-3 slice changes the generated
`system_case_json` contract, optimizer behavior, or artifact formats:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Regression Guard

Every slice that changes backend persistence must keep the existing Python
suite green: scenario versions, structured drafts, hydraulic diagrams, manual
runs, TS-1 hierarchy provenance and TS-2 catalog tests.

Slices changing React should run the relevant frontend unit tests, `tsc -b`
and `eslint .`.

TS-3 materializes `system_case_json` payloads that the Julia optimizer already
accepts; if any slice changes that contract, the Julia regression suite must
be run.

TS-3 must not remove or break the legacy scenario-version run path; it remains
the regression contract until a later iteration retires it explicitly.
