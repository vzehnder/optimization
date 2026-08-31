# TS7-011: Ingest An Object Specific Revision By CSV And XLSX

Status: Todo
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

- [ ] The first file load validates in staging and publishes exactly the previewed content, for both CSV and XLSX (AC-ESP-03).
- [ ] Updating by file produces new revisions and preserves the identity (AC-ESP-04 file half).
- [ ] The mapping can be set and corrected, and each correction revalidates before publication is allowed.
- [ ] A preview returns a bounded normalized sample and is never a download of the full content.
- [ ] Cancelling retires staging and leaves no canonical row.
- [ ] File ingestion shares the ingestion id semantics, idempotency and error codes with the points channel (7.11).
- [ ] A malformed or oversized file is refused with a stable code and leaves no partial revision.

## Blocked by

- [TS7-010: Create An Object Specific Series And Ingest It By API](TS7-010-create-an-object-specific-series-and-ingest-it-by-api.md)
