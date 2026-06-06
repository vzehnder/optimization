# BESS Iteration 5 Issue Tracker

This document is the local tracker for the simple reservoir hydropower
iteration derived from `docs/iter5/prd_hydro_simple_dispatch.md` and
`docs/iter5/mathematical_model.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the `ready-for-agent`
triage label.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- |
| BESS-ITER5-000 | Review Hydro PRD And Mathematical Formulation | HITL | ready-for-agent | Done | None | [BESS-ITER5-000-review-hydro-prd-and-mathematical-formulation.md](BESS-ITER5-000-review-hydro-prd-and-mathematical-formulation.md) |
| BESS-ITER5-001 | Run A Linear Hydro v2 System Case End To End | AFK | ready-for-agent | Done | BESS-ITER5-000 | [BESS-ITER5-001-run-a-linear-hydro-v2-system-case-end-to-end.md](BESS-ITER5-001-run-a-linear-hydro-v2-system-case-end-to-end.md) |
| BESS-ITER5-002 | Run A Piecewise Hydro v2 System Case End To End | AFK | ready-for-agent | Done | BESS-ITER5-001 | [BESS-ITER5-002-run-a-piecewise-hydro-v2-system-case-end-to-end.md](BESS-ITER5-002-run-a-piecewise-hydro-v2-system-case-end-to-end.md) |
| BESS-ITER5-003 | Harden Hydro Contract Validation And v1 Regression | AFK | ready-for-agent | Done | BESS-ITER5-001, BESS-ITER5-002 | [BESS-ITER5-003-harden-hydro-contract-validation-and-v1-regression.md](BESS-ITER5-003-harden-hydro-contract-validation-and-v1-regression.md) |
| BESS-ITER5-004 | Create And Edit Hydro Assets In Structured Drafts | AFK | ready-for-agent | Done | BESS-ITER5-003 | [BESS-ITER5-004-create-and-edit-hydro-assets-in-structured-drafts.md](BESS-ITER5-004-create-and-edit-hydro-assets-in-structured-drafts.md) |
| BESS-ITER5-005 | Map Hydro Inflows From CSV And XLSX | AFK | ready-for-agent | Done | BESS-ITER5-004 | [BESS-ITER5-005-map-hydro-inflows-from-csv-and-xlsx.md](BESS-ITER5-005-map-hydro-inflows-from-csv-and-xlsx.md) |
| BESS-ITER5-006 | Promote And Run A Linear Hydro Draft | AFK | ready-for-agent | Done | BESS-ITER5-005 | [BESS-ITER5-006-promote-and-run-a-linear-hydro-draft.md](BESS-ITER5-006-promote-and-run-a-linear-hydro-draft.md) |
| BESS-ITER5-007 | Render Hydro Results Tables And Charts | AFK | ready-for-agent | Done | BESS-ITER5-006 | [BESS-ITER5-007-render-hydro-results-tables-and-charts.md](BESS-ITER5-007-render-hydro-results-tables-and-charts.md) |
| BESS-ITER5-008 | Prove Piecewise Hydro From Editor End To End | AFK | ready-for-agent | Done | BESS-ITER5-002, BESS-ITER5-005, BESS-ITER5-007 | [BESS-ITER5-008-prove-piecewise-hydro-from-editor-end-to-end.md](BESS-ITER5-008-prove-piecewise-hydro-from-editor-end-to-end.md) |
| BESS-ITER5-009 | Finalize Iteration 5 Acceptance Suite And Docs | AFK | ready-for-agent | Done | BESS-ITER5-001 through BESS-ITER5-008 | [BESS-ITER5-009-finalize-iteration-5-acceptance-suite-and-docs.md](BESS-ITER5-009-finalize-iteration-5-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-ITER5-000
2. BESS-ITER5-001
3. BESS-ITER5-002
4. BESS-ITER5-003
5. BESS-ITER5-004
6. BESS-ITER5-005
7. BESS-ITER5-006
8. BESS-ITER5-007
9. BESS-ITER5-008
10. BESS-ITER5-009

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-06-03 | BESS-ITER5-000 | Todo -> Done | Reviewed and accepted the hydro PRD and mathematical formulation against the final objective, completed Iteration 2 optimizer contract, completed Iteration 3 analyst workflow, and completed Iteration 4 structured editor workflow. No corrections were required. |
| 2026-06-03 | BESS-ITER5-001 | Todo -> Done | Added the first `bess_system_dispatch.v2` linear hydro path in Julia: loader validation, normalization, reservoir balance, linear generation, spill/release/terminal economics, hydro outputs, sample case, API/CLI coverage, full Julia verification with 415 tests, and Python web regression verification with 67 tests. |
| 2026-06-04 | BESS-ITER5-002 | Todo -> Done | Added explicit `PiecewiseLinearOpt` dependency, piecewise hydro generation curves with default `piecewiselinear` method, reservoir elevation modeled through `piecewiselinear`, nonmonotone sample case, API/CLI/output coverage, and full Julia verification with 444 tests. |
| 2026-06-04 | BESS-ITER5-003 | Todo -> Done | Hardened hydro contract-boundary validation coverage for invalid graph, inflow, storage, terminal, penalty, turbine-flow, linear-generation, piecewise-generation, and reservoir-curve cases; kept nonmonotone/nonconvex piecewise curves accepted; improved reservoir-domain error messages; verified 468 Julia tests and 67 Python web tests. |
| 2026-06-04 | BESS-ITER5-004 | Todo -> Done | Added hydro assets to structured drafts, generated `bess_system_dispatch.v2` previews, automatic PCC edges, linear and piecewise hydro form controls, reservoir curve controls, duplicate-ID regression coverage, and preservation from existing `v2` versions; verified 71 Python web tests and Chrome DevTools local UI inspection. |
| 2026-06-05 | BESS-ITER5-005 | Todo -> Done | Added CSV/XLSX hydro inflow mapping suggestions, manual `hydro_inflow_m3s.<hydro_id>` mapping, missing/negative/nonnumeric validation, generated `v2` period inflow maps, and provenance metadata coverage; verified 77 Python web tests and Chrome DevTools local UI inspection. |
| 2026-06-05 | BESS-ITER5-006 | Todo -> Done | Connected promoted linear hydro generated drafts to the manual run artifact contract by registering `system_case_resolved.json`, added end-to-end promoted hydro draft/run coverage with safe source and mapping provenance, aligned the hydro test fixture with the current Julia one-bus normalizer, verified 78 Python web tests, and completed a Chrome DevTools real-Julia local smoke. |
| 2026-06-05 | BESS-ITER5-007 | Todo -> Done | Added hydro result API/chart payloads for dispatch totals and asset reservoir elevation, rendered `summary.json` hydro KPIs in the run page, preserved legacy missing-column fallbacks, verified 81 Python tests, and completed Chrome DevTools local UI inspection. |
| 2026-06-05 | BESS-ITER5-008 | Todo -> Done | Added focused Iteration 5 acceptance coverage for a piecewise hydro structured editor flow through UI/API draft save, CSV and XLSX inflow mapping, generated `v2` preview preserving nonmonotone breakpoints, Julia validation, promotion, manual run, resolved-case and metadata artifacts, result tables/charts, and invalid breakpoint rejection before promotion. |
| 2026-06-05 | BESS-ITER5-009 | Todo -> Done | Added final Iteration 5 acceptance coverage for linear hydro, piecewise hydro, paste/upload `v1`, no-hydro structured `v2`, and malformed hydro inflow failures; expanded hydro docs and manual checklist; verified focused Iteration 5, full Python, and full Julia suites. |

## Regression Guard

Every Iteration 5 slice that changes Julia code must run:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

Every slice that changes the Python web application should run the relevant
backend/API/template tests introduced for Iterations 3 and 4.

Slices touching structured editor generation, time-series ingestion, or results
must prove the Iteration 3/4 paste/upload `bess_system_dispatch.v1` path still
works unless the slice is limited to Julia-only behavior.

## Final Iteration 5 Verification

The closing acceptance slice must run the focused Iteration 5 acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter5_acceptance -v
```

It must also run the full Python web acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

It must keep the Julia optimizer regression suite green:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

The final acceptance coverage must prove linear hydro and piecewise hydro flows
from structured draft through source mapping, generated `v2` preview,
Julia-backed validation, promotion to immutable scenario version, manual run,
artifact registration, hydro result tables/charts, downloads, and legacy `v1`
regression compatibility.

## Dependency Notes

- BESS-ITER5-000 is HITL because the hydropower formulation should be accepted
  before optimizer implementation.
- BESS-ITER5-001 creates the first thin vertical hydro path with linear
  generation directly through the Julia contract and persisted outputs.
- BESS-ITER5-002 adds the PiecewiseLinearOpt path after the linear hydro path
  proves the base reservoir balance and output contract.
- BESS-ITER5-003 hardens invalid-input behavior and legacy compatibility after
  both happy paths exist.
- BESS-ITER5-004 adds hydro to structured draft editing after the Julia contract
  is stable.
- BESS-ITER5-005 extends source mapping after hydro draft assets exist.
- BESS-ITER5-006 connects the linear hydro draft to the existing immutable
  version and manual run workflow.
- BESS-ITER5-007 exposes hydro results after the linear end-to-end web flow
  writes real artifacts.
- BESS-ITER5-008 proves the piecewise hydro editor path after both the
  PiecewiseLinearOpt contract and web result path exist.
- BESS-ITER5-009 is the final proof that the iteration satisfies the PRD and
  preserves previous iteration behavior.
