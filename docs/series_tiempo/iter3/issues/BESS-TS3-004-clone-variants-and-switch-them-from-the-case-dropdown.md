# BESS-TS3-004: Clone Variants And Switch Them From The Case Dropdown

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-16
Fecha de termino planificada: 2026-07-17

## User stories covered

2, 3

## What to build

Let a case hold multiple input variants and make switching between them
trivial. An analyst clones an existing variant (typically the default), names
it, and changes only the bindings that differ; the clone copies bindings, not
series values. The case view gains a variant dropdown that lists all variants,
marks the default, and drives which variant the run flow uses.

Cloning and variant listing are backend operations with their own endpoints;
the dropdown selection persists so the analyst can bind, validate and run
against the chosen variant without duplicating topology or parameters.

## Acceptance criteria

- [ ] Cloning a variant creates a new named variant with copied bindings and no copied series values.
- [ ] Bindings of a cloned variant can be changed without affecting the original variant.
- [ ] The case UI shows a dropdown of variants with the default clearly marked, and the selection drives binding, validation and run launch.
- [ ] Backend endpoints exist to list, create, clone and update variants scoped to the case.
- [ ] Backend tests prove clone independence and that the default variant remains the fallback selection.

## Blocked by

BESS-TS3-001
