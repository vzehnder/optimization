# BESS-HYDRO-DIAGRAM-001: Create A Minimal Persisted Hydraulic Diagram Case

Status: Done
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

- [x] A scenario can obtain or create an editable normalized optimization case
      for the hydraulic diagram.
- [x] The React UI opens a hydraulic diagram surface from the scenario context.
- [x] The analyst can add at least reservoir, junction and plant visible nodes.
- [x] Node creation persists stable technical keys and editable display labels.
- [x] Save is explicit and the UI shows dirty, saving, saved and failed states.
- [x] Reloading the editor restores the persisted active topology.
- [x] Persisted positions are restored or autolayout is applied when positions
      are missing.
- [x] Stale save attempts are rejected using `updated_at` or an equivalent
      revision token.
- [x] Backend tests cover create, save, reload and stale update rejection.
- [x] React tests cover dirty/save state and reload from server data.
- [x] `docs/db/hydro_diagram_db_checkpoint.md` records the tables and fields
      implemented by this slice.

## Implementation notes

- Added minimal normalized hydraulic diagram persistence in `AnalystStore`:
  `optimization_cases`, base hydraulic systems/nodes/plants, active
  case-hydraulic system/node/plant rows and editable layout rows.
- Added `/api/scenarios/{scenario_id}/hydraulic-diagram` POST, GET and PUT
  contracts. PUT requires the current layout revision and returns 409 on stale
  saves.
- Added a React hydraulic diagram route under
  `/react/scenarios/:scenarioId/hydraulic-diagram` with explicit save, reload
  and dirty/saving/saved/failed UI states.

## Verification

- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram`
- `npm.cmd test -- App.test.tsx -t "opens a persisted hydraulic diagram"`

## Blocked by

BESS-HYDRO-DIAGRAM-000
