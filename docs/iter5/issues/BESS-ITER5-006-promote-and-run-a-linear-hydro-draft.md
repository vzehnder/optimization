# BESS-ITER5-006: Promote And Run A Linear Hydro Draft

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter5/prd_hydro_simple_dispatch.md`

## User stories covered

43 through 48, 66

## What to build

Connect the structured linear hydro draft path to generated-case validation,
promotion, manual run execution, and artifact registration.

The analyst should be able to create a linear hydro draft, upload and map
hydro inflows, preview a generated `v2` case, validate it through Julia, promote
the current validation snapshot to an immutable scenario version, launch a
manual run, and see the run succeed with registered hydro artifacts.

## Acceptance criteria

- [ ] A linear hydro draft can generate a complete `bess_system_dispatch.v2`
      preview from structured fields and mapped source rows.
- [ ] Python generation errors appear before Julia validation when editor or
      mapping data is incomplete.
- [ ] Julia validation success and failure for generated hydro cases are
      surfaced through API and SSR UI.
- [ ] Promotion requires a current successful validation snapshot.
- [ ] Promoted scenario versions store the exact generated hydro `system_case`.
- [ ] Promoted versions retain safe source-file and mapping provenance.
- [ ] A promoted linear hydro version can launch a manual run.
- [ ] The manual run completes successfully through the existing Julia process
      boundary.
- [ ] Run artifacts are registered for input snapshot, logs, summary,
      dispatch, asset dispatch, resolved case, and metadata.
- [ ] The existing paste/upload JSON version path remains intact.

## Blocked by

BESS-ITER5-005
