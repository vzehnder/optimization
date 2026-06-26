# BESS-HYDRO-DIAGRAM-001: Create A Minimal Persisted Hydraulic Diagram Case

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

1 through 7, 13 through 16, 20 through 22, 57, 58, 61 through 64

## What to build

Create the first complete saved hydraulic diagram path. An analyst can open a
React hydraulic diagram for a scenario case, add a small set of visible
hydraulic nodes such as reservoir, junction and plant placeholders, assign
stable keys and display labels, save explicitly, reload the page and see the
same active case topology and positions.

The slice should create or connect the minimal normalized case and hydraulic
base/active tables needed for this path. It should also create the layout
tables from the DB extension if they are needed for saved positions, expose
backend APIs consumed by React, and update the DB checkpoint with the real
implemented state.

## Acceptance criteria

- [ ] A scenario can obtain or create an editable normalized optimization case
      for the hydraulic diagram.
- [ ] The React UI opens a hydraulic diagram surface from the scenario context.
- [ ] The analyst can add at least reservoir, junction and plant visible nodes.
- [ ] Node creation persists stable technical keys and editable display labels.
- [ ] Save is explicit and the UI shows dirty, saving, saved and failed states.
- [ ] Reloading the editor restores the persisted active topology.
- [ ] Persisted positions are restored or autolayout is applied when positions
      are missing.
- [ ] Stale save attempts are rejected using `updated_at` or an equivalent
      revision token.
- [ ] Backend tests cover create, save, reload and stale update rejection.
- [ ] React tests cover dirty/save state and reload from server data.
- [ ] `docs/db/hydro_diagram_db_checkpoint.md` records the tables and fields
      implemented by this slice.

## Blocked by

BESS-HYDRO-DIAGRAM-000

