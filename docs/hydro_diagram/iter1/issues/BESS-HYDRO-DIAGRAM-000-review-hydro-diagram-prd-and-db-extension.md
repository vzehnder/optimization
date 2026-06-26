# BESS-HYDRO-DIAGRAM-000: Review Hydro Diagram PRD And DB Extension

Status: Done
Type: HITL
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

All user stories as review scope.

## What to build

Review and accept the hydro diagram PRD, the database extension, the grill-me
decisions and the issue breakdown before implementation starts. Confirm that
the MVP scope is a React diagram editor over active case topology, backed by
normalised hydraulic database tables, generating `bess_system_dispatch.v3` and
running a limited hydraulic network solver.

This slice should also confirm the diagram rendering approach for React and the
rule that every DB-touching issue updates
`docs/db/hydro_diagram_db_checkpoint.md`.

## Acceptance criteria

- [x] The PRD scope is accepted or corrected.
- [x] The database extension is accepted or corrected.
- [x] The `bess_system_dispatch.v3` version decision is accepted.
- [x] The solver limitations for the MVP are accepted.
- [x] The local issue breakdown granularity is accepted.
- [x] The checkpoint update rule is accepted.
- [x] Any corrections are reflected in the PRD, DB extension, tracker and
      affected issues before downstream implementation begins.

## Review outcome

Accepted on 2026-06-26 after review against the final objective, the completed
Iteration 5 simple hydro workflow, the Iteration 6 publication boundary, the
React migration plan, the central database proposal, the hydro diagram database
extension, the grill-me decisions and the local issue breakdown.

No corrections were required before downstream implementation. The MVP remains:
a React hydraulic diagram editor over active normalized case topology,
normalized hydraulic database tables with a live checkpoint rule, a distinct
`bess_system_dispatch.v3` executable contract, and a deliberately limited
hydraulic network solver.

## Blocked by

None - can start immediately
