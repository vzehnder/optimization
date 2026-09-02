# TS7-010: Create An Object Specific Series And Ingest It By API

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter7/spec_ts7_catalogo_global_y_series_especificas.md` (7.1-7.6, 7.8, 7.11)

## What to build

Open the second path: a series that is born from an object that already exists,
belongs only to that object, and never needs a generic catalog entry behind it.

The canonical root is the normalized object -
`/api/projects/{project_id}/linkable-objects/{linkable_object_id}/time-series`.
The backend resolves the object, checks its typed FK and demands that its
project match the route before resolving any series. It does not accept
`entity_type`, `entity_id`, owner or project repeated in the payload as
authority.

Deliver the contextual list `GET OBJECT_ROOT`, which pages generic associations
and object-specific series together as a read model only - every row carries a
mandatory `source_kind` discriminator, and every mutation goes through its own
typed subresource. Deliver definition-only creation, the detail, the `If-Match`
patch limited to display name, description and curated metadata, the revision
history and the bounded preview.

Deliver ingestion by points against `OBJECT_TARGET`: prepare and validate a JSON
batch, read its status and errors, fix the mapping and revalidate, preview a
bounded normalized sample, cancel while unpublished, and publish to seal a
revision. The ingestion id is opaque and bound to actor, target, project, base
revision, hash, channel and normalized payload; knowing it does not skip
authorization.

The object owner is immutable. The order is fixed: the object exists first, then
the definition, then the values.

## Acceptance criteria

- [x] The object must exist before the definition; no route creates both at once (AC-ESP-01).
- [x] Saving only the definition is valid, and the series stays unselectable until it has a sealed revision (AC-ESP-02 backend half).
- [x] Updating by API produces new revisions and never reassigns the identity (AC-ESP-04 API half).
- [x] The object owner is immutable: no `PATCH` changes it (AC-ESP-05).
- [x] Resending the same ingestion with the same key creates no second revision; a different key returns `TS_INGEST_IDEMPOTENCY_CONFLICT` (AC-ESP-09).
- [x] An interrupted publication leaves no partial revision visible (AC-ESP-10).
- [x] `GET OBJECT_ROOT` returns both kinds with a mandatory `source_kind`, shares cursors and limits with the global catalog, and never returns values or an unbounded consumer list.
- [x] The route project must match the object's project before any series resolves; a payload cannot override it.
- [x] Knowing an `ingestion_id` does not bypass object or project authorization (AC-SEG-03).
- [x] `PATCH` touches only display name, description and curated metadata, under `If-Match`.

## Delivered surface

| Method and path | Purpose |
| --- | --- |
| `GET OBJECT_ROOT` | Contextual page of associations and local series, filtered by `kind`, semantic type, data class, unit, `availability`, compatible role and text. |
| `POST OBJECT_ROOT/object-series` | Definition-only creation under `Idempotency-Key`. |
| `GET OBJECT_ROOT/object-series/{signal_id}` | Detail with `ETag` and `304`. |
| `PATCH OBJECT_ROOT/object-series/{signal_id}` | Display name, description and curated metadata under `If-Match`. |
| `GET OBJECT_ROOT/object-series/{signal_id}/revisions` | Paginated revision metadata. |
| `GET OBJECT_ROOT/object-series/{signal_id}/preview` | Bounded preview of one exact revision. |
| `POST OBJECT_TARGET/revision-ingestions/points` | Prepare and validate one JSON batch. |
| `GET OBJECT_TARGET/revision-ingestions/{ingestion_id}` | Status, summary, errors, impact and capabilities. |
| `PUT OBJECT_TARGET/revision-ingestions/{ingestion_id}/mapping` | Fix the mapping and revalidate. |
| `GET OBJECT_TARGET/revision-ingestions/{ingestion_id}/preview` | Bounded normalized sample of what is staged. |
| `DELETE OBJECT_TARGET/revision-ingestions/{ingestion_id}` | Cancel and withdraw staging. |
| `POST OBJECT_TARGET/revision-ingestions/{ingestion_id}/publications` | Seal the revision under `If-Match` and `Idempotency-Key`. |

Deliberately out of this slice, and named so the next issue picks them up:

- `POST OBJECT_ROOT/object-series/{signal_id}/archive` belongs to TS7-012 with
  the rest of the archival journey.
- `/revision-ingestions/files` and the CSV/XLSX budgets belong to TS7-011.
- `SHARED_TARGET`, its derivations and prevalidations belong to TS7-013.
- The `object-series-creation-ingestions` convenience of chapter 7.5 is an
  integration shortcut, not an acceptance criterion, and is not exposed here.

## Evidence

- N1/N2: `tests/test_ts7_010_object_specific_series.py`, twenty-five HTTP
  contract tests against the FastAPI app, mirrored as an opt-in PostgreSQL
  suite (`POSTGRES_TEST_DATABASE_URL`).
- No N3/N4: this slice exposes no React surface. Chapter 11.1 keeps every
  visible surface behind the C6 cutover, so the browser narrative belongs to
  TS7-020 and TS7-021.

## Blocked by

- [TS7-006: Read The Global Catalog Signal First](TS7-006-read-the-global-catalog-signal-first.md)
