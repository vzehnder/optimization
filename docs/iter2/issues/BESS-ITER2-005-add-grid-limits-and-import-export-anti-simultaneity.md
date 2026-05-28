# BESS-ITER2-005: Add Grid Limits And Import Export Anti-Simultaneity

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

14, 15, 16, 20, 21, 23, 25, 30

## What to build

Add an end-to-end grid behavior slice with optional import/export limits and configurable import/export anti-simultaneity enabled by default.

The implementation must prevent unbounded or artificial same-period grid buy/sell behavior while preserving the option to solve without the binary mode when explicitly disabled.

## Acceptance criteria

- [ ] Grid assets support optional import and export limits.
- [ ] Negative grid limits are rejected.
- [ ] Grid import and export are modeled as separate nonnegative variables.
- [ ] Grid import/export anti-simultaneity is enabled by default.
- [ ] When enabled, no period imports and exports above tolerance at the same grid connection.
- [ ] When disabled, the model remains bounded through explicit or derived finite limits.
- [ ] Import and export limits bind in a targeted scenario.
- [ ] Wide dispatch output reports grid import, grid export, and net grid export.
- [ ] Long asset dispatch output reports grid import and export by grid asset ID.
- [ ] Existing minimal hybrid and single-BESS tests remain green after the slice.

## Verification

Run grid limit and anti-simultaneity tests, the minimal system test, and existing MVP tests.

## Blocked by

BESS-ITER2-001
