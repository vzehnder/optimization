# BESS-ITER4-003: Define One-Bus Assets In The Draft Editor

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

6 through 21, 56, 57

## What to build

Extend the draft editor so an analyst can define the one-bus model structure
through forms instead of JSON.

The editor should cover case metadata, a single PCC, grid settings, one or more
battery assets, one or more renewable assets, one or more load assets, and
minimal solver settings. Generated logical edges should connect every asset to
the PCC automatically.

## Acceptance criteria

- [x] Draft case metadata can be edited through API and SSR UI.
- [x] The editor represents exactly one PCC or bus for generated cases.
- [x] Grid asset settings include import limit, export limit, and
      import/export anti-simultaneity.
- [x] Battery asset settings include power limits, energy bounds, initial
      energy, efficiencies, degradation cost, terminal condition, and
      charge/discharge anti-simultaneity.
- [x] Renewable assets can be added with stable IDs and optional display
      category metadata such as solar or wind.
- [x] Load assets can be added with stable IDs.
- [x] The editor prevents duplicate asset IDs before generation.
- [x] Solver name defaults to HiGHS and solver options accept only a JSON
      object.
- [x] A system-case generation path can create a one-bus graph with logical
      edges from the structured draft asset data.
- [x] Tests cover generated graph shape, asset IDs, solver settings, duplicate
      ID errors, and basic UI/API editing behavior.

## Implementation notes

- Added a structured draft editor module that converts draft documents into a
  `bess_system_dispatch.v1` one-bus graph preview.
- Added API preview endpoint:
  `/api/scenarios/{scenario_id}/draft/generated-system-case`.
- Added SSR form editing for case metadata, PCC, grid limits and
  anti-simultaneity, one battery, one renewable, one load, and solver settings.
- Preserved the raw draft JSON textarea as an advanced compatibility path.
- Drafts initialized from existing scenario versions now prefill editable PCC,
  grid, and asset structures while retaining the immutable source version seed.
- Duplicate node or asset IDs fail before generation, and solver options must
  parse as a JSON object.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Python web/API/template tests: 48 passed.
- Julia package tests: 372 passed.

Chrome DevTools verification loaded the structured draft page, submitted the
structured form, confirmed the generated one-bus preview included the grid,
battery, renewable, and load edges to the PCC, and found no console messages or
failed network requests. Screenshots were saved under `.tmp`.

Browser note: attempted the requested in-app Browser workflow twice, but the
`node_repl` browser-control runtime failed locally with
`windows sandbox failed: spawn setup refresh`; Chrome DevTools MCP validation
was completed successfully.

## Blocked by

BESS-ITER4-002
