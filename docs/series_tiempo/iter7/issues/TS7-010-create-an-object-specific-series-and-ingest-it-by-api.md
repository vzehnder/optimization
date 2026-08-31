# TS7-010: Create An Object Specific Series And Ingest It By API

Status: Todo
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

- [ ] The object must exist before the definition; no route creates both at once (AC-ESP-01).
- [ ] Saving only the definition is valid, and the series stays unselectable until it has a sealed revision (AC-ESP-02 backend half).
- [ ] Updating by API produces new revisions and never reassigns the identity (AC-ESP-04 API half).
- [ ] The object owner is immutable: no `PATCH` changes it (AC-ESP-05).
- [ ] Resending the same ingestion with the same key creates no second revision; a different key returns `TS_INGEST_IDEMPOTENCY_CONFLICT` (AC-ESP-09).
- [ ] An interrupted publication leaves no partial revision visible (AC-ESP-10).
- [ ] `GET OBJECT_ROOT` returns both kinds with a mandatory `source_kind`, shares cursors and limits with the global catalog, and never returns values or an unbounded consumer list.
- [ ] The route project must match the object's project before any series resolves; a payload cannot override it.
- [ ] Knowing an `ingestion_id` does not bypass object or project authorization (AC-SEG-03).
- [ ] `PATCH` touches only display name, description and curated metadata, under `If-Match`.

## Blocked by

- [TS7-006: Read The Global Catalog Signal First](TS7-006-read-the-global-catalog-signal-first.md)
