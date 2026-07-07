# BESS-TS4-003: Index Asset-Level Dispatch Rows

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-15
Fecha de termino planificada: 2026-07-15

## User stories covered

11

## What to build

Index the per-asset rows of `asset_dispatch.csv` so that each asset's dispatch
series is queryable in BBDD by asset identity. An analyst inspecting a run
should be able to see per-asset dispatch served from BBDD, with the asset id,
name and type preserved on each indexed series, and with the same run linkage
as the case-level series from earlier slices.

The per-asset results surface (the asset dispatch table on the run detail)
must read from BBDD when indexed data exists and fall back to artifacts for
runs without indexed results, rendering identically in both paths.

## Acceptance criteria

- [ ] Asset-level dispatch series index in BBDD with asset identity (id, name, type) preserved.
- [ ] Per-asset series carry the same run and snapshot linkage as case-level series.
- [ ] The asset dispatch endpoint serves indexed data from BBDD with artifact fallback.
- [ ] The React asset dispatch table renders identically from indexed data.
- [ ] Tests index a multi-asset run's `asset_dispatch.csv` from representative artifacts.

## Blocked by

BESS-TS4-001
