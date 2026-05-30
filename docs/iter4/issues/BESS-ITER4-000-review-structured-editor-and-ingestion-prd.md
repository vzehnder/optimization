# BESS-ITER4-000: Review Structured Editor And Ingestion PRD

Status: Done
Type: HITL
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

All

## What to build

Review the Iteration 4 PRD against the final product objective and the completed
Iteration 3 analyst workflow.

The review should confirm that Iteration 4 is correctly scoped around the
structured editor, CSV/XLSX time-series ingestion, backward-compatible separate
import/export prices, draft promotion, and preservation of the existing
paste/upload JSON path.

## Acceptance criteria

- [x] The PRD scope is accepted or corrected before implementation starts.
- [x] The decision to add `ScenarioDraft` as a mutable editor object is accepted
      or replaced with a clearer alternative.
- [x] The decision to keep `ScenarioVersion` immutable and executable is
      accepted.
- [x] The decision to keep the paste/upload JSON path intact is accepted.
- [x] The decision to keep `bess_system_dispatch.v1` and add optional separate
      prices backward-compatibly is accepted.
- [x] The decision to keep hydropower, scheduling, auth/roles, customer portal,
      and dashboard builder out of scope is accepted.
- [x] The vertical slice breakdown is accepted as implementable.

## Review outcome

Reviewed on 2026-05-30 against `docs/final/objetivo_final.md`, the completed
Iteration 2 one-bus optimizer contract, and the completed Iteration 3 analyst
web workflow.

Accepted the PRD as the Iteration 4 implementation contract. No corrections
were required before starting downstream implementation.

## Accepted decisions

- Accepted the structured editor path as a parallel input flow that ends in the
  existing immutable `ScenarioVersion` and manual run workflow.
- Accepted `ScenarioDraft` as a mutable scenario-owned editor object with one
  active draft per scenario for this iteration.
- Accepted keeping `ScenarioVersion` immutable and executable, with runs
  continuing to reference versions rather than drafts.
- Accepted preserving the Iteration 3 paste/upload JSON path as an advanced and
  regression-protected input route.
- Accepted keeping `bess_system_dispatch.v1` and adding optional
  `import_price_usd_per_mwh` and `export_price_usd_per_mwh` fields
  backward-compatibly.
- Accepted CSV as the fully covered ingestion path and basic XLSX as the later
  same-contract ingestion extension.
- Accepted keeping hydropower, scheduling, auth/roles, customer portal,
  configurable dashboards, canvas editing, manual graph editing, and advanced
  ETL out of scope for Iteration 4.
- Accepted the vertical slice breakdown as implementable, with separate-price
  Julia/result behavior and draft persistence unblocked after this review.

## Verification

Documentation review only. No executable code changed, so no test command was
run for this issue.

## Blocked by

None - can start immediately
