# BESS-TS1-005: Harden Stale Validation For Topology And Parameter Changes

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-16
Fecha de termino planificada: 2026-07-17

## User stories covered

9, 10, 13, 14, 18

## What to build

Make stale validation behavior explicit for topology and parameter changes. A
validated snapshot should remain promotable or runnable only while the current
topology and parameter hashes match the hashes captured at validation time.

The UI and APIs should distinguish topology stale, parameter stale and missing
validation where possible, while keeping existing error behavior controlled.

## Acceptance criteria

- [x] Validation snapshots store topology hash at validation time.
- [x] Validation snapshots store parameter hash at validation time.
- [x] Topology edits after validation mark the validation stale.
- [x] Parameter edits after validation mark the validation stale.
- [x] Layout-only edits do not mark topology or parameter validation stale.
- [x] Promotion or run creation blocks stale validation snapshots.
- [x] Error payloads identify whether topology or parameters caused stale state when known.
- [x] Backend tests cover topology stale, parameter stale and layout-only non-stale behavior.
- [x] Existing stale promotion protections for hydraulic diagrams remain green.

## Blocked by

BESS-TS1-004
