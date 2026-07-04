# BESS-TS2-001: Import A Minimal CSV Time-Series Set End-To-End

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-04
Fecha de termino planificada: 2026-07-04
Fecha de inicio real: 2026-07-04
Fecha de termino real: 2026-07-04

## User stories covered

1, 4, 5, 6, 7, 9, 20

## What to build

The tracer bullet for the generic catalog: an analyst uploads a small CSV as a
time-series source, maps its value column to one canonical signal, imports it,
and the data becomes a project-scoped time-series set persisted in BBDD. The
set carries name, version label, data kind, timezone and status; the import
creates revision 1 with a content hash; periods and values live in long-format
tables keyed by set, signal and period. After import, the set and its values
are readable through the API without reopening the file.

The slice cuts through every layer with the thinnest possible path: source
upload with provenance (file name, media type, checksum), a deep import module
for parsing, mapping and persistence that is testable without UI, the new
catalog tables, API endpoints, and a minimal React flow to upload and confirm
the created set. Preview UX, XLSX, strict validation, manual edits and catalog
browsing polish belong to later slices.

## Acceptance criteria

- [x] A CSV upload creates a time-series source with provenance metadata (file name, media type, checksum).
- [x] Importing creates a project-scoped set with name, version label, data kind, timezone and status.
- [x] Imported periods and values are stored in BBDD in long format keyed by set, signal and period.
- [x] The initial import records revision 1 and a content hash for the set.
- [x] The set, its signals and its values can be read back through the API without reopening the file.
- [x] Import parsing, mapping and value persistence live in a deep module testable without UI.
- [x] A minimal React flow uploads the CSV and confirms the created set.
- [x] No binding of sets to optimization cases is introduced.

## Review outcome (2026-07-04)

Reviewed together with BESS-TS2-002. Focused TS-2 backend tests, full Python
discovery, full Vitest suite, `eslint .`, production build and API drift check
all passed. The pending manual Chrome QA was completed with
`chrome-devtools` MCP against the PostgreSQL-backed app on
`http://127.0.0.1:8000`: a dual-price CSV upload in project `TS2 Chrome QA 002`
produced the confirmation panel (set `ts2_qa_dual_price`, version `v1`,
revision 1, 3 periods, sha256 content hash) and PostgreSQL showed the set
persisted in long format (2 signals, 3 periods, 6 values, 1 revision).

## Blocked by

BESS-TS2-000
