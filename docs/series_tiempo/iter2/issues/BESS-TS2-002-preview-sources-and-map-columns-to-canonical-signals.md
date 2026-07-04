# BESS-TS2-002: Preview Sources And Map Columns To Canonical Signals

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-09
Fecha de termino planificada: 2026-07-10

## User stories covered

3, 4, 12, 19, 20

## What to build

Make the import flow trustworthy before data lands in BBDD. An uploaded source
can be previewed (columns plus sample rows) so the analyst confirms the file is
correct, and source columns are explicitly mapped to canonical signals from a
signal catalog. The catalog defines the allowed `signal_key` values, expected
units and validation rules, so arbitrary spreadsheet column names never leak
into the model. Mapped signals record origin unit and canonical unit, without
complex conversions.

Mapping problems (unknown columns, missing required mapping, unit mismatch)
must surface as clear errors tied to the offending source column, and the
mapping used by an import must persist on the revision for audit. The signal
catalog and mapping validation live centrally so CSV, XLSX and manual edits can
share the same rules in later slices.

## Acceptance criteria

- [ ] An uploaded source can be previewed with columns and sample rows before import.
- [ ] A signal catalog defines allowed signal keys, expected units and validation rules.
- [ ] Column mapping resolves arbitrary source column names to canonical signal keys.
- [ ] Origin unit and canonical unit are recorded on mapped signals, without complex conversion.
- [ ] Unmapped or unknown columns produce clear, column-tied errors.
- [ ] The mapping used by an import persists on the revision for audit.
- [ ] React shows the preview-and-map step before confirming an import.
- [ ] Mapping validation is centralized for reuse by later import and edit paths.

## Blocked by

BESS-TS2-001
