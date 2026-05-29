# BESS-ITER3-009: Finalize Iteration 3 Acceptance Suite And Docs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

41 through 54

## What to build

Finalize Iteration 3 with an acceptance suite and documentation proving the
complete private analyst flow from project creation through scenario versioning,
manual execution, artifact persistence, result review, and downloads.

This is the closing proof issue, not the first implementation of core behavior.

## Acceptance criteria

- [ ] Documentation explains how to configure the app locally.
- [ ] Documentation explains the database configuration approach and the
      PostgreSQL/Supabase-compatible direction without requiring Supabase.
- [ ] Documentation explains how to run the internal web app.
- [ ] Documentation explains how to validate and save a `system_case_json`.
- [ ] Documentation explains how to launch a manual run and inspect status.
- [ ] Documentation explains where artifacts are stored and how downloads map
      to Julia output files.
- [ ] A final acceptance test covers project creation, scenario creation,
      scenario version creation, Julia validation, manual run launch, successful
      completion, artifact registration, summary/table review, chart data, and
      download behavior.
- [ ] Failure-path acceptance coverage proves invalid inputs and failed Julia
      runs are persisted with useful errors and logs.
- [ ] Backend/API tests, template smoke tests, and results reader tests pass.
- [ ] The Julia regression suite remains green.
- [ ] The tracker is updated with verification instructions for Iteration 3.

## Blocked by

BESS-ITER3-001, BESS-ITER3-002, BESS-ITER3-003, BESS-ITER3-004, BESS-ITER3-005, BESS-ITER3-006, BESS-ITER3-007, BESS-ITER3-008
