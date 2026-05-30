# BESS-ITER4-006: Promote A Validated Draft And Run It Manually

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

47 through 50, 64

## What to build

Complete the structured editor path by promoting a validated draft into an
immutable scenario version and running it through the existing manual execution
flow.

The promoted version must store the exact generated `system_case_json`, then the
existing run queue, Julia executor, artifact registration, result reader, and
download behavior should work without a second execution path.

## Acceptance criteria

- [ ] A successfully validated generated case can be promoted to a new
      immutable scenario version.
- [ ] The promoted version stores the exact generated `system_case_json`.
- [ ] The source draft remains editable after promotion.
- [ ] The promoted scenario version can launch a manual run through the existing
      run endpoint and UI.
- [ ] The run executes through the existing Julia process boundary.
- [ ] Success and failure artifacts are registered through the existing artifact
      mechanism.
- [ ] Results for an editor-created version render summary, tables, charts, and
      downloads.
- [ ] The paste/upload JSON path can still promote and run a scenario version.
- [ ] Acceptance tests cover draft-to-version-to-run behavior end to end.

## Blocked by

BESS-ITER4-005
