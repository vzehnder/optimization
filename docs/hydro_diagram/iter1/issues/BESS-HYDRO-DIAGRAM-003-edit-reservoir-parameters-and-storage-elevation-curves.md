# BESS-HYDRO-DIAGRAM-003: Edit Reservoir Parameters And Storage-Elevation Curves

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

23 through 28, 31, 33, 57 through 62

## What to build

Make reservoir nodes operationally meaningful. An analyst can select a
reservoir in the diagram, edit storage bounds, initial storage, terminal
condition and terminal water value, then create or select a versioned
`storage_elevation` curve. The case validation should require the reservoir
parameters and curve binding before the reservoir can participate in a v3
payload.

This slice must keep curve data versioned in the hydraulic curve tables rather
than embedding mutable points only in the diagram document.

## Acceptance criteria

- [ ] Selecting a reservoir opens a panel with storage bounds, initial storage,
      terminal condition and terminal water value.
- [ ] The panel can create or edit a `storage_elevation` curve as point rows.
- [ ] The panel can select an existing compatible versioned curve.
- [ ] Saving persists curve sets, curve points and the case curve binding.
- [ ] Validation requires reservoir parameters for active reservoir nodes.
- [ ] Validation requires a `storage_elevation` binding for active reservoir
      nodes.
- [ ] Validation rejects non-increasing storage points, decreasing elevation,
      storage bounds outside curve domain and invalid terminal settings.
- [ ] Backend tests cover parameter persistence, curve versioning, binding and
      invalid curve cases.
- [ ] React tests cover reservoir panel editing, curve table editing and
      validation error display.
- [ ] The DB checkpoint records implemented curve and reservoir parameter
      tables.

## Blocked by

BESS-HYDRO-DIAGRAM-002

