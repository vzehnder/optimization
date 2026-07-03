# BESS-TS1-007: Preserve Legacy Scenario Draft Version And Run Compatibility

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-22
Fecha de termino planificada: 2026-07-23

## User stories covered

7, 8, 17 through 20

## What to build

Run a compatibility and hardening slice across the existing modeling paths.
The new hierarchy metadata must not break paste/upload JSON, structured drafts,
hydraulic diagrams, scenario version deletion protections, manual runs,
artifacts, results or publications.

This slice should fill gaps found after the earlier implementation slices and
add regression coverage where compatibility risk is highest.

## Acceptance criteria

- [ ] Paste/upload JSON can still create immutable scenario versions.
- [ ] Structured drafts can still validate, promote and run.
- [ ] Hydraulic diagrams can still validate, promote and run.
- [ ] Manual runs still reference scenario versions, not mutable cases.
- [ ] Run artifacts and result readers still work for old and new runs.
- [ ] Publication flows still resolve scenario version and run lineage.
- [ ] Scenario version deletion protections still block versions referenced by runs or publications.
- [ ] Compatibility tests cover old versions without hierarchy metadata.
- [ ] Full relevant Python web acceptance suite remains green.

## Blocked by

- BESS-TS1-005
- BESS-TS1-006
