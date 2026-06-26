# BESS-HYDRO-DIAGRAM-010: Reject Unsupported Topologies And Stale Promotions

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

16 through 18, 42 through 48, 54, 59, 60, 63 through 67

## What to build

Harden the diagram workflow around unsupported topology and stale validation.
The editor may draw general directed graphs, but promotion and execution must
reject graph shapes outside the MVP solver capability, such as unsupported
cycles, unresolved islands, inactive endpoint references, unsupported routing,
head-dependent generation and stale validation snapshots.

The UI should keep errors actionable by selecting or linking affected diagram
entities.

## Acceptance criteria

- [ ] Validation detects unsupported cycles for the MVP solver.
- [ ] Validation detects disconnected islands without boundary conditions.
- [ ] Validation detects unsupported routing or travel-time settings.
- [ ] Validation detects head-dependent, pump-only or reversible unit modes as
      unsupported for the MVP solver.
- [ ] Validation detects stale dependencies after topology, parameter, curve or
      time-series edits.
- [ ] Promotion is blocked when validation is missing or stale.
- [ ] Error payloads include entity references where possible.
- [ ] The UI can select or focus affected diagram components from validation
      messages.
- [ ] Tests cover each unsupported topology and stale promotion case.
- [ ] Existing v1, v2 and valid v3 cases still validate and run.

## Blocked by

BESS-HYDRO-DIAGRAM-008, BESS-HYDRO-DIAGRAM-009

