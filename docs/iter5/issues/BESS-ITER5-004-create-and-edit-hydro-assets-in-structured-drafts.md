# BESS-ITER5-004: Create And Edit Hydro Assets In Structured Drafts

Status: Done
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

- [x] The structured draft document can store hydro assets.
- [x] The server-rendered draft form exposes hydro fields and simple breakpoint
      editing controls.
- [x] The draft editor supports linear hydro generation parameters.
- [x] The draft editor supports piecewise generation breakpoints.
- [x] The draft editor supports reservoir storage-elevation breakpoints.
- [x] Generated cases from the structured editor use
      `bess_system_dispatch.v2`.
- [x] Generated nodes include PCC, grid, existing assets, and hydro assets.
- [x] Generated edges connect hydro assets to the PCC automatically.
- [x] Duplicate IDs across PCC, grid, hydro, battery, renewable, and load
      assets are rejected.
- [x] Generated preview includes hydro curves and hydro parameters.
- [x] Drafts initialized from existing versions preserve supported `v2` hydro
      data where possible.
- [x] Existing structured editor tests for grid, battery, renewable, and load
      remain green.

## Blocked by

BESS-ITER5-003

## Implementation notes

Completed on 2026-06-04.

- Structured editor generated previews now use `bess_system_dispatch.v2`.
- Hydro assets can be stored in draft JSON, generated into system-case nodes,
  connected to the PCC, and preserved when initializing a draft from a `v2`
  scenario version.
- The server-rendered draft form exposes hydro storage, terminal, linear
  generation, optional bounds, piecewise generation curve, and reservoir curve
  controls.
- Verified with focused structured editor tests, the full Python web suite, and
  Chrome DevTools inspection of the local draft page.
