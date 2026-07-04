# BESS-TS2-005: Browse The Project Time-Series Catalog

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-17
Fecha de termino planificada: 2026-07-20

## User stories covered

16, 17, 18

## What to build

Make the series library visible as business objects. A project catalog lists
its time-series sets with name, version label, data kind, status, timezone,
current revision and content hash, so the analyst can recognize packages like
`hidrologia_seca_v2` or `precios_enero_2026_v1`. A set detail view shows the
signals it contains (canonical keys, units, entity metadata when known), a
horizon summary (period count, start, end) and the provenance of the current
revision, so it is clear whether a set holds prices, demand, renewables or
inflows and where the data came from.

Catalog and detail reads come from BBDD, never from reopening source files.
This slice is read-oriented: manual editing and file replacement arrive in the
following slices.

## Acceptance criteria

- [ ] A project catalog lists its time-series sets with name, version label, data kind, status and timezone.
- [ ] The catalog shows current revision number and content hash per set.
- [ ] A set detail view shows signals with canonical keys, units and entity metadata when known.
- [ ] The detail view shows a horizon summary with period count, start and end.
- [ ] Source provenance of the current revision (file name, sheet when applicable) is visible.
- [ ] Catalog and detail reads come from BBDD, not from reopening source files.
- [ ] Backend tests cover list and detail behavior at the API boundary.

## Blocked by

BESS-TS2-001
