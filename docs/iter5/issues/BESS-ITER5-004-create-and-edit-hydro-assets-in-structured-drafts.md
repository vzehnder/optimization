# BESS-ITER5-004: Create And Edit Hydro Assets In Structured Drafts

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter5/prd_hydro_simple_dispatch.md`

## User stories covered

1 through 4, 23 through 39, 43, 56, 63

## What to build

Add hydro assets to the structured draft editor and generated-case preview.

The analyst should be able to define a hydro asset from the draft page,
including reservoir storage settings, terminal settings, spill penalty, minimum
release, terminal water value, generation mode, linear parameters, optional
power and turbine-flow bounds, generation breakpoints, and reservoir
storage-elevation breakpoints. Generated structured editor cases should use
`bess_system_dispatch.v2` and automatically connect hydro assets to the PCC.

## Acceptance criteria

- [ ] The structured draft document can store hydro assets.
- [ ] The server-rendered draft form exposes hydro fields and simple breakpoint
      editing controls.
- [ ] The draft editor supports linear hydro generation parameters.
- [ ] The draft editor supports piecewise generation breakpoints.
- [ ] The draft editor supports reservoir storage-elevation breakpoints.
- [ ] Generated cases from the structured editor use
      `bess_system_dispatch.v2`.
- [ ] Generated nodes include PCC, grid, existing assets, and hydro assets.
- [ ] Generated edges connect hydro assets to the PCC automatically.
- [ ] Duplicate IDs across PCC, grid, hydro, battery, renewable, and load
      assets are rejected.
- [ ] Generated preview includes hydro curves and hydro parameters.
- [ ] Drafts initialized from existing versions preserve supported `v2` hydro
      data where possible.
- [ ] Existing structured editor tests for grid, battery, renewable, and load
      remain green.

## Blocked by

BESS-ITER5-003
