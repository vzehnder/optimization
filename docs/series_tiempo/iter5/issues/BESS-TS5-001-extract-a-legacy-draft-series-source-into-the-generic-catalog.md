# BESS-TS5-001: Extract A Legacy Draft Series Source Into The Generic Catalog

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-10
Fecha de termino planificada: 2026-07-13

## User stories covered

3, 12, 14

## What to build

The tracer bullet for the TS-5 migration workflow: an analyst opens a legacy
structured draft whose time-series data lives embedded in the draft document
(validated rows imported from a CSV/XLSX source), triggers an explicit
extraction, and that data becomes a generic time-series set in the TS-2
catalog — set, revision, periods, signals and values — with origin metadata
pointing back at the legacy draft and its original file source.

The extracted set behaves like any natively created set: it is listed in the
project series catalog, browsable, and bindable in a case input variant. The
legacy draft itself is never modified or deleted; extraction adds a new
reusable object, it does not rewrite history. Re-running the extraction for
the same draft converges without duplicate sets, revisions or values, so the
routine is safe to repair local and PostgreSQL environments.

The slice cuts through every layer with the thinnest possible path: one legacy
source shape (a structured draft with validated CSV rows), one extraction
routine in a deep module, one catalog surface showing the extracted set with
its origin, and one binding proof in a variant. Hydraulic-specific series,
bulk migration, staleness hardening and permissions belong to later slices.

## Acceptance criteria

- [ ] An analyst can extract one legacy draft's validated series data into a generic time-series set from the UI.
- [ ] The extracted set records origin metadata (legacy draft, original source file, extraction date and author) sufficient to audit where each value came from.
- [ ] The extracted set is listed in the project series catalog and bindable in a case input variant like any natively created set.
- [ ] Extraction is idempotent: re-running it for the same draft converges without duplicate sets, revisions or values, in local SQLite and PostgreSQL.
- [ ] The legacy draft and its stored source data remain unchanged and readable after extraction.
- [ ] Extraction, normalization and catalog writes live in a deep module testable without the UI.

## Blocked by

BESS-TS5-000
