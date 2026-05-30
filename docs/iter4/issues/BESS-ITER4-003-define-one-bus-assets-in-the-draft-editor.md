# BESS-ITER4-003: Define One-Bus Assets In The Draft Editor

Status: Todo
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

- [ ] Draft case metadata can be edited through API and SSR UI.
- [ ] The editor represents exactly one PCC or bus for generated cases.
- [ ] Grid asset settings include import limit, export limit, and
      import/export anti-simultaneity.
- [ ] Battery asset settings include power limits, energy bounds, initial
      energy, efficiencies, degradation cost, terminal condition, and
      charge/discharge anti-simultaneity.
- [ ] Renewable assets can be added with stable IDs and optional display
      category metadata such as solar or wind.
- [ ] Load assets can be added with stable IDs.
- [ ] The editor prevents duplicate asset IDs before generation.
- [ ] Solver name defaults to HiGHS and solver options accept only a JSON
      object.
- [ ] A system-case generation path can create a one-bus graph with logical
      edges from the structured draft asset data.
- [ ] Tests cover generated graph shape, asset IDs, solver settings, duplicate
      ID errors, and basic UI/API editing behavior.

## Blocked by

BESS-ITER4-002
