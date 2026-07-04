# BESS-TS2-004: Add XLSX Import With Sheet Selection

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-15
Fecha de termino planificada: 2026-07-16

## User stories covered

2, 3, 12, 19

## What to build

Keep Excel workflows supported as a load mechanism. An analyst uploads an XLSX
as a time-series source, chooses a sheet, and the chosen sheet flows through
the same preview, mapping and validation pipeline as CSV before values land in
BBDD. Source provenance records the sheet name alongside file name, media type
and checksum.

Failure paths must be clean: choosing an invalid sheet produces a clear error,
and unsupported workbook features fail with actionable messages instead of
crashes. Tests must prove CSV and XLSX share the same centralized validation
rules rather than duplicating them.

## Acceptance criteria

- [ ] An XLSX upload lists available sheets and lets the analyst choose one.
- [ ] The chosen sheet flows through the same preview, mapping and validation as CSV.
- [ ] Invalid sheet selection produces a clear error.
- [ ] Unsupported workbook features fail with actionable messages, not crashes.
- [ ] Source provenance records the sheet name alongside file metadata.
- [ ] Tests prove CSV and XLSX imports share the same centralized validation rules.
- [ ] React supports the sheet-selection step in the import flow.

## Blocked by

BESS-TS2-003
