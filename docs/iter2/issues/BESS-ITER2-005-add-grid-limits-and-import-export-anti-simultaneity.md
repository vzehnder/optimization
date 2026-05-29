# BESS-ITER2-005: Add Grid Limits And Import Export Anti-Simultaneity

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

14, 15, 16, 20, 21, 23, 25, 30

## What to build

Add an end-to-end grid behavior slice with optional import/export limits and configurable import/export anti-simultaneity enabled by default.

The implementation must prevent unbounded or artificial same-period grid buy/sell behavior while preserving the option to solve without the binary mode when explicitly disabled.

## Acceptance criteria

- [x] Grid assets support optional import and export limits.
- [x] Negative grid limits are rejected.
- [x] Grid import and export are modeled as separate nonnegative variables.
- [x] Grid import/export anti-simultaneity is enabled by default.
- [x] When enabled, no period imports and exports above tolerance at the same grid connection.
- [x] When disabled, the model remains bounded through explicit or derived finite limits.
- [x] Import and export limits bind in a targeted scenario.
- [x] Wide dispatch output reports grid import, grid export, and net grid export.
- [x] Long asset dispatch output reports grid import and export by grid asset ID.
- [x] Existing minimal hybrid and single-BESS tests remain green after the slice.

## Implementation notes

- Added centralized grid asset parsing and validation so negative import/export limits fail during `load_system_case`, before model construction.
- Covered a targeted grid-limit scenario where import is capped while serving load and export is capped while renewable availability exceeds export capacity.
- Verified default grid import/export anti-simultaneity with grid binary variables and no same-period import/export above tolerance.
- Verified explicitly disabled grid anti-simultaneity builds without grid binaries and remains bounded through derived finite grid bounds.
- Verified wide `dispatch.csv` and long `asset_dispatch.csv` report grid import, grid export, and net grid export with the grid asset ID.

## Verification

Passed `julia --project=. -e "import Pkg; Pkg.test()"` with 299 tests, including grid limits, grid import/export anti-simultaneity, disabled anti-sim boundedness, minimal hybrid, CLI/API, and existing MVP regression tests.

## Blocked by

BESS-ITER2-001
