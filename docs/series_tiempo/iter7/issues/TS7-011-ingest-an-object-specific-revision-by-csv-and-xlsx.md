# TS7-011: Ingest An Object Specific Revision By CSV And XLSX

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (7.7, 7.8, 7.11)

## What to build

Add the file channel to the ingestion flow the points channel already
established, sharing its stages, its ids and its error matrix rather than
growing a parallel path.

Upload a CSV or XLSX to staging and get back a validation job. Read its status,
summary and typed errors. Fix or set the column mapping and revalidate. Preview
a bounded normalized sample - a preview is a sample, not a download. Cancel and
retire staging while unpublished. Publish, and seal a revision whose content is
exactly what the preview showed, nothing re-read from a file that may have
changed underneath.

Validation happens in staging, before anything canonical is touched, so a
malformed file never leaves a half-written revision behind.

## Acceptance criteria

- [x] The first file load validates in staging and publishes exactly the previewed content, for both CSV and XLSX (AC-ESP-03).
- [x] Updating by file produces new revisions and preserves the identity (AC-ESP-04 file half).
- [x] The mapping can be set and corrected, and each correction revalidates before publication is allowed.
- [x] A preview returns a bounded normalized sample and is never a download of the full content.
- [x] Cancelling retires staging and leaves no canonical row.
- [x] File ingestion shares the ingestion id semantics, idempotency and error codes with the points channel (7.11).
- [x] A malformed or oversized file is refused with a stable code and leaves no partial revision.

## Delivered surface

`POST OBJECT_TARGET/revision-ingestions/files` accepts a multipart `file` and
optional JSON `mapping`, requires `Idempotency-Key`, and returns the same `202`
ingestion receipt used by the points channel. The existing status, mapping,
preview, cancellation and publication resources then drive the file job without
a parallel lifecycle.

The staging parser supports UTF-8 CSV and XLSX with explicit worksheet
selection when a workbook has multiple sheets. It retains the immutable parsed
upload for mapping corrections, normalizes local timestamps through the chosen
IANA timezone, reports file coordinates instead of JSON pointers, and stages
the complete replacement or append snapshot that publication seals. Canonical
tables are touched only by the publication transaction.

The boundary enforces the specified CSV and XLSX byte budgets, XLSX expanded
size and compression ratio, one-million-period/five-million-cell/two-hundred-
column quotas, two-hundred-error cap, two-hundred-row preview cap and three
active jobs per actor/project. Formula workbooks, duplicate signal mappings,
unsafe provenance fields and idempotency-key reuse are refused with stable
problem documents.

## Evidence

- N1/N2: `tests/test_ts7_011_object_specific_file_ingestion.py`, sixteen HTTP
  contract tests against the FastAPI app, mirrored as an opt-in PostgreSQL
  suite (`POSTGRES_TEST_DATABASE_URL`). They cover CSV and XLSX publication,
  exact preview/content equality, revision identity, remapping without another
  upload, cancellation, append snapshots, multisheet selection, quotas,
  compression bombs, formulas, file-local errors and authorization-safe
  provenance.
- Regression: the complete Python suite passes (`1072` tests, `80` skipped
  because PostgreSQL is not configured), and the generated OpenAPI contract is
  current (`npm run api:check`).
- No N3/N4: this slice exposes no React surface. Chapter 11.1 keeps visible
  mutation journeys behind C6, so browser evidence belongs to TS7-020 and
  TS7-021.

## Blocked by

- [TS7-010: Create An Object Specific Series And Ingest It By API](TS7-010-create-an-object-specific-series-and-ingest-it-by-api.md)
