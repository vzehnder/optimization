# BESS TS-1 Issue Tracker

This document is the local tracker for TS-1: topology and parameter hierarchy,
derived from `docs/series_tiempo/iter1/prd.md`.

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
| BESS-TS1-000 | Review TS-1 PRD And Hierarchy Semantics | HITL | ready-for-agent | Todo | 2026-07-03 | 2026-07-03 | None | [BESS-TS1-000-review-ts1-prd-and-hierarchy-semantics.md](BESS-TS1-000-review-ts1-prd-and-hierarchy-semantics.md) |
| BESS-TS1-001 | Introduce Case Hierarchy Provenance For Existing Runs | AFK | ready-for-agent | Todo | 2026-07-06 | 2026-07-07 | BESS-TS1-000 | [BESS-TS1-001-introduce-case-hierarchy-provenance-for-existing-runs.md](BESS-TS1-001-introduce-case-hierarchy-provenance-for-existing-runs.md) |
| BESS-TS1-002 | Add Topology And Parameter Snapshot Metadata For Structured Drafts | AFK | ready-for-agent | Todo | 2026-07-08 | 2026-07-09 | BESS-TS1-001 | [BESS-TS1-002-add-topology-and-parameter-snapshot-metadata-for-structured-drafts.md](BESS-TS1-002-add-topology-and-parameter-snapshot-metadata-for-structured-drafts.md) |
| BESS-TS1-003 | Add Topology And Parameter Snapshot Metadata For Hydraulic Diagrams | AFK | ready-for-agent | Todo | 2026-07-10 | 2026-07-13 | BESS-TS1-001 | [BESS-TS1-003-add-topology-and-parameter-snapshot-metadata-for-hydraulic-diagrams.md](BESS-TS1-003-add-topology-and-parameter-snapshot-metadata-for-hydraulic-diagrams.md) |
| BESS-TS1-004 | Generate Existing System Case From Hierarchy Inputs | AFK | ready-for-agent | Todo | 2026-07-14 | 2026-07-15 | BESS-TS1-002, BESS-TS1-003 | [BESS-TS1-004-generate-existing-system-case-from-hierarchy-inputs.md](BESS-TS1-004-generate-existing-system-case-from-hierarchy-inputs.md) |
| BESS-TS1-005 | Harden Stale Validation For Topology And Parameter Changes | AFK | ready-for-agent | Todo | 2026-07-16 | 2026-07-17 | BESS-TS1-004 | [BESS-TS1-005-harden-stale-validation-for-topology-and-parameter-changes.md](BESS-TS1-005-harden-stale-validation-for-topology-and-parameter-changes.md) |
| BESS-TS1-006 | Surface Topology And Parameter Provenance In React | AFK | ready-for-agent | Todo | 2026-07-20 | 2026-07-21 | BESS-TS1-004 | [BESS-TS1-006-surface-topology-and-parameter-provenance-in-react.md](BESS-TS1-006-surface-topology-and-parameter-provenance-in-react.md) |
| BESS-TS1-007 | Preserve Legacy Scenario Draft Version And Run Compatibility | AFK | ready-for-agent | Todo | 2026-07-22 | 2026-07-23 | BESS-TS1-005, BESS-TS1-006 | [BESS-TS1-007-preserve-legacy-scenario-draft-version-and-run-compatibility.md](BESS-TS1-007-preserve-legacy-scenario-draft-version-and-run-compatibility.md) |
| BESS-TS1-008 | Finalize TS-1 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | 2026-07-24 | 2026-07-24 | BESS-TS1-001 through BESS-TS1-007 | [BESS-TS1-008-finalize-ts1-acceptance-suite-and-docs.md](BESS-TS1-008-finalize-ts1-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-TS1-000
2. BESS-TS1-001
3. BESS-TS1-002 and BESS-TS1-003 can proceed after the common provenance boundary exists.
4. BESS-TS1-004 joins structured and hydraulic hierarchy inputs into stable generated snapshots.
5. BESS-TS1-005 hardens stale validation after generation equivalence is proven.
6. BESS-TS1-006 exposes provenance in React once backend metadata is stable.
7. BESS-TS1-007 runs compatibility and regression hardening across old flows.
8. BESS-TS1-008 closes the iteration with acceptance coverage and docs.

## Regression Guard

Every slice that changes backend persistence or generation should run focused
Python tests for scenario versions, structured drafts, hydraulic diagrams and
manual runs.

Slices changing React should run the relevant frontend unit tests and API type
checks.

Slices changing Julia-facing payloads must keep the Julia optimizer regression
suite green.
