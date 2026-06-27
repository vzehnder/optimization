# BESS-HYDRO-DIAGRAM-004: Edit Plants, Units, And Flow-Power Curves

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

6 through 8, 29 through 33, 49, 51, 57 through 62, 65, 66

## What to build

Make plant nodes generate power through unit definitions. An analyst can select
a plant, add one or more generation-only units in the panel, assign each unit
intake and discharge nodes, edit power and turbine-flow limits, and create or
select one active `flow_power` curve per unit.

The main diagram should keep the plant as the visible node while unit detail
stays inside the plant panel. Validation should require at least one active unit
for active plants that participate in the MVP solver path.

## Acceptance criteria

- [x] Selecting a plant opens a panel with plant label, optional aggregate
      limits and a unit list.
- [x] The analyst can add, edit and disable generation-only units for the
      plant.
- [x] Each unit can select active intake and discharge nodes.
- [x] Each unit can edit turbine-flow and power limits.
- [x] Each active unit can create or select one active `flow_power` curve.
- [x] Validation requires active plants to have active units unless explicitly
      marked non-modeled.
- [x] Validation rejects unit intake/discharge nodes that are inactive or equal.
- [x] Validation rejects missing or invalid `flow_power` curve bindings for
      active units.
- [x] Backend tests cover plant/unit persistence, unit validation and curve
      binding.
- [x] React tests cover the plant panel and unit subeditor.
- [x] The DB checkpoint records implemented plant, unit and flow-power curve
      state.

## Blocked by

BESS-HYDRO-DIAGRAM-003

