# BESS-HYDRO-DIAGRAM-009: Persist Layout And Snapshot Promoted Diagrams

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

19 through 22, 48, 50, 57, 61 through 64

## What to build

Complete layout persistence and historical snapshots. The editable diagram
stores node positions, viewport, zoom and visual state by case. Promotion copies
a lightweight non-executable layout snapshot to the promoted scenario version
so that historical versions can be inspected with the visual arrangement used
at promotion time.

This slice should prove that layout edits do not change solver inputs and that
topology edits still invalidate validation.

## Acceptance criteria

- [ ] Diagram positions, viewport and zoom persist by case.
- [ ] New entities without saved positions receive deterministic autolayout.
- [ ] Layout-only changes do not change generated `system_case_json`.
- [ ] Promotion creates a scenario-version layout snapshot.
- [ ] Historical version view or API can return the layout snapshot read-only.
- [ ] Editing the active case after promotion does not modify the historical
      snapshot.
- [ ] Backend tests cover layout persistence, autolayout fallback and snapshot
      immutability.
- [ ] React tests cover moving nodes, saving layout and reload.
- [ ] The DB checkpoint records layout and snapshot table implementation.

## Blocked by

BESS-HYDRO-DIAGRAM-006

