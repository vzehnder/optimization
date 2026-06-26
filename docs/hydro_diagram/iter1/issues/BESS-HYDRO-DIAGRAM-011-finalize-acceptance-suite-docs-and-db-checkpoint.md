# BESS-HYDRO-DIAGRAM-011: Finalize Acceptance Suite Docs And DB Checkpoint

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

All user stories as final acceptance scope.

## What to build

Close the iteration with acceptance coverage, manual test instructions and an
updated DB checkpoint. The final proof should demonstrate a full analyst path:
create a hydraulic diagram, add reservoir, reaches, plant and unit, define
curves and inflow, validate, promote, run, inspect results and confirm legacy
v1/v2 behavior remains intact.

The documentation should capture the remaining gaps for future iterations:
topology import, routing, head-dependent generation, pumped storage and
collaborative editing.

## Acceptance criteria

- [ ] Focused acceptance tests prove the minimal v3 hydraulic diagram workflow
      from creation through run results.
- [ ] Browser coverage proves the React diagram is usable for the primary path.
- [ ] Julia tests prove v3 solve behavior and v1/v2 regression.
- [ ] Python backend tests prove API, validation, promotion and result behavior.
- [ ] Manual test instructions are added under `docs/hydro_diagram/iter1/`.
- [ ] `docs/db/hydro_diagram_db_checkpoint.md` reflects the actual final BBDD
      state of the iteration.
- [ ] The local issue tracker progress log is updated with final verification
      commands and outcomes.
- [ ] Known out-of-scope items are documented as future work.

## Blocked by

BESS-HYDRO-DIAGRAM-001 through BESS-HYDRO-DIAGRAM-010

