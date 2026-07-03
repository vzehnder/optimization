# BESS-TS1-004: Generate Existing System Case From Hierarchy Inputs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-14
Fecha de termino planificada: 2026-07-15

## User stories covered

4 through 8, 16 through 20

## What to build

Create or consolidate the generation boundary that produces the executable
`system_case_json` from topology and parameter inputs. This should be a deep,
testable module or module family that supports current structured draft and
hydraulic diagram paths without changing the Julia-facing contract.

The core proof is equivalence: generated cases from the hierarchy path should
match the accepted current payloads for representative cases.

## Acceptance criteria

- [ ] A shared generation boundary accepts topology and parameter inputs.
- [ ] Structured draft cases can generate the same executable payload through the hierarchy boundary.
- [ ] Hydraulic diagram cases can generate the same executable payload through the hierarchy boundary.
- [ ] Generated payload metadata includes topology and parameter hashes.
- [ ] Julia validation still receives a complete `system_case_json`.
- [ ] Backend tests prove generation equivalence for representative structured and hydraulic cases.
- [ ] Manual run execution from generated scenario versions still works.

## Blocked by

- BESS-TS1-002
- BESS-TS1-003
