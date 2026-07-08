# BESS-TS5-001: Extract A Legacy Draft Series Source Into The Generic Catalog

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-10
Fecha de termino planificada: 2026-07-13
Fecha de inicio real: 2026-07-08
Fecha de termino real: 2026-07-08

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

- [x] An analyst can extract one legacy draft's validated series data into a generic time-series set from the UI.
- [x] The extracted set records origin metadata (legacy draft, original source file, extraction date and author) sufficient to audit where each value came from.
- [x] The extracted set is listed in the project series catalog and bindable in a case input variant like any natively created set.
- [x] Extraction is idempotent: re-running it for the same draft converges without duplicate sets, revisions or values, in local SQLite and PostgreSQL.
- [x] The legacy draft and its stored source data remain unchanged and readable after extraction.
- [x] Extraction, normalization and catalog writes live in a deep module testable without the UI.

## Blocked by

BESS-TS5-000

## Implementation Notes

- Deep module `app/legacy_series_extraction.py` (`prepare_draft_series_extraction`)
  reads a draft's already-validated `time_series` source (`source.mapping` +
  `source.validated_rows`, the same shape `generate_system_case_from_draft`
  consumes) and turns it directly into generic catalog periods/signals/values,
  with no re-mapping step. Reuses `time_series_ingestion.mapped_column` /
  `mapped_asset_columns` to discover exactly which signals were mapped
  (including entity-scoped `load_demand_mw` / `renewable_available_power_mw` /
  `hydro_inflow_m3s` per asset id), so unmapped assets are not extracted as
  spurious zero series.
- `AnalystStore.extract_draft_time_series_set` (`app/persistence.py`) is the
  persistence-level entry point. A new `time_series_set_extractions` table
  (keyed on `scenario_id` + `source_id`) records origin and is the idempotency
  key: re-extracting unchanged data returns the existing set untouched; a
  content-hash mismatch (source data changed) raises rather than silently
  duplicating. Origin metadata (scenario id, source id, filename, checksum,
  extracted-by/at) is stored in the revision's `metadata_json` under an
  `origin` key, reusing the existing `revision_metadata` read path — no new
  read API needed.
- `CatalogValue` gained an optional `entity_key` field, and the shared
  `_insert_time_series_signals_periods_values` helper now keys its
  signal-id lookup on `(signal_key, entity_key)` instead of `signal_key`
  alone. This was a latent gap: the generic CSV importer never produces two
  signals sharing a `signal_key` with different `entity_key`, but legacy
  draft extraction does (e.g. two load assets both mapping to
  `load_demand_mw`). Backward compatible (existing callers pass
  `entity_key=None` on both sides).
- New endpoint: `POST /api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/extract`.
  New UI panel "Extract legacy series to catalog" in `DraftEditor.tsx`,
  shown once a source's mapping is validated; only needs set name/version
  label/data kind/timezone (no column mapping wizard). Catalog set detail
  page (`Workspace.tsx`) shows an "Origen" section when `revision_metadata.origin.kind
  === "legacy_draft_extraction"`.
- Verified in Chrome against the real PostgreSQL dev database (project 38,
  scenario 47): upload CSV -> save mapping -> Extract to catalog -> listed in
  project catalog -> origin section shows scenario/source/extracted-by/at ->
  re-extracting with identical inputs returns the same set (no duplicate) ->
  set is selectable and range-valid in the case's required-signal binding
  dropdowns for `load_demand_mw` and `renewable_available_power_mw`.
- Tests: `tests/test_ts5_draft_series_extraction.py` (persistence-level and
  endpoint-level, 8 cases: tracer bullet, idempotency, origin metadata, draft
  immutability, variant binding, validation-required error path).
