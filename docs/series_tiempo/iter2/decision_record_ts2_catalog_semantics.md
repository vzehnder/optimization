# TS-2 Catalog Semantics Decision Record

Fecha: 2026-07-04
Status: Accepted
Issue: `BESS-TS2-000`

## Context Reviewed

This decision was reviewed against:

- `docs/series_tiempo/iter2/prd.md` (TS-2 PRD and its Grill-Me answers);
- `docs/series_tiempo/propuesta_manejo_series_tiempo.md` (initial time-series
  proposal);
- `docs/series_tiempo/roadmap_iteraciones_jerarquias_series.md` (TS-1 through
  TS-6 roadmap, TS-2 section and detail);
- `docs/db/propuesta_bbdd_componentes_timeseries.md` (central DB proposal,
  `time_series_sources` / `time_series_sets` / `time_series_set_revisions` /
  `time_series_periods` / `time_series_signals` / `time_series_values` table
  definitions and their accepted decisions);
- `docs/series_tiempo/iter1/decision_record_ts1_hierarchy.md` (TS-1 accepted
  hierarchy, since TS-2 must not reopen topology/parameter semantics);
- existing signal-key usage in `app/time_series_ingestion.py`,
  `app/draft_editor.py`, `app/persistence.py` and `app/results.py` (legacy
  draft CSV/XLSX ingestion and hydraulic diagram signals).

## Accepted Decisions

1. BBDD is the operative source for time-series values. CSV/XLSX remain
   accepted load/replace mechanisms; each upload is recorded as a
   `time_series_source` with file name, media type and checksum, but the
   values consumed by the application live in the generic catalog tables, not
   in the uploaded file.
2. A `time_series_set` supports both shapes: a multi-signal package (for
   example prices + demand + renewables aligned on the same horizon) and a
   single-signal set (for example one inflow series). The schema does not
   force one signal per set.
3. `version_number`/`version_label` versus `revision_number` semantics from
   `docs/db/propuesta_bbdd_componentes_timeseries.md` are accepted as the
   precise model, refining the simplified diagram in the TS-2 PRD:
   - `time_series_sets` carries both `version_number` (monotonic integer per
     `(project_id, name)`) and `version_label` (human tag, unique within
     `(project_id, name)`, e.g. `v1`, `dry_year`, `corrected`). This is the
     version the analyst picks.
   - `time_series_set_revisions` records edits made in place to one set row
     (manual value corrections or a replacement file upload): incrementing
     `revision_number`, a recalculated `content_hash`, `change_summary` and
     the source/snapshot behind the edit. The set keeps its `version_number`
     and `version_label` across revisions.
   - Runs/snapshots freeze the exact `content_hash` (and therefore the exact
     revision) they used, per PRD Q4.
4. Initial canonical `signal_key` catalog is accepted for TS-2, grounded in
   keys already used by the legacy draft ingestion path
   (`app/time_series_ingestion.py`, `app/persistence.py`) so the generic
   catalog does not diverge from existing vocabulary:

   | `signal_key` | `entity_type` | Unit | Validation rule |
   | --- | --- | --- | --- |
   | `price_usd_per_mwh` | global (`NULL`) | `USD/MWh` | numeric, any sign (energy prices can be negative) |
   | `import_price_usd_per_mwh` | global (`NULL`) | `USD/MWh` | numeric, any sign |
   | `export_price_usd_per_mwh` | global (`NULL`) | `USD/MWh` | numeric, any sign |
   | `load_demand_mw` | `component:load` | `MW` | numeric, `>= 0` |
   | `renewable_available_power_mw` | `component:renewable` | `MW` | numeric, `>= 0` |
   | `hydro_inflow_m3s` | `component:hydro` | `m3/s` | numeric, `>= 0` |
   | `natural_inflow_m3s` | `hydraulic_node` | `m3/s` | numeric, `>= 0` |
   | `minimum_flow_m3s` | `hydraulic_reach` | `m3/s` | numeric, `>= 0` |

   This catalog is intentionally small and extensible. `unit_availability_factor`
   and other signals from the central DB proposal stay out of the TS-2 initial
   catalog because they depend on `availability_events` machinery that has not
   been built yet (later iteration); adding a `signal_key` later is additive,
   not breaking.
5. The signal catalog is implemented for TS-2 as a backend Python
   module-level registry (allowed keys, unit, entity type, nonnegative rule),
   not a new DB-enforced allowlist table. `constraint_definitions` and
   `objective_term_definitions`-style DB catalogs from the central DB proposal
   do not exist yet in this codebase and are out of scope here; a code-level
   registry is sufficient to satisfy PRD decision "a signal catalog defines
   allowed keys, expected units and validation rules" and story 19 (shared
   validation across CSV, XLSX and manual edits).
6. Timezone convention is accepted: `time_series_periods.timestamp_start` and
   `timestamp_end` are stored as `TIMESTAMPTZ` instants; `time_series_sets.timezone`
   stores the IANA zone used to interpret/import/display the set (e.g.
   `America/Santiago`); `duration_hours` is kept per period so 23/25-hour DST
   days and non-hourly resolutions remain representable.
7. Manual edit policy is accepted: bounded manual edits and file-replacement
   uploads both create a new `time_series_set_revisions` row, recompute
   `content_hash`, and do not touch `version_number`/`version_label`. Any
   `case_input_variant` (future TS-3 concept) validated against the previous
   hash becomes stale, per the `validation_dependencies` pattern already
   accepted in the central DB proposal.
8. Out-of-scope list is confirmed for TS-2: no binding of sets to
   optimization cases or variants, no result-series storage, no resampling or
   interpolation, no complex unit conversion (only trivial unit bookkeeping:
   record source unit and canonical unit), no migration of
   `hydraulic_time_series_sets`/`hydraulic_time_series_points` (those remain
   the legacy hydraulic-diagram-specific path until TS-5).

## PRD Corrections

No corrections are required to `docs/series_tiempo/iter2/prd.md` text. One
clarification is recorded for downstream issues: the PRD's
`TimeSeriesSet -> TimeSeriesSetRevision` diagram is a simplification of the
`version_number`/`version_label` + `time_series_set_revisions` model already
detailed in `docs/db/propuesta_bbdd_componentes_timeseries.md` (see Decision 3
above). Implementation issues (BESS-TS2-001 onward) should follow the fuller
model, not re-derive a simpler one.

## Acceptance Mapping

- BBDD as operative source / files as auditable load sources: accepted.
- Sets supporting both multi-signal packages and single-signal sets: accepted.
- `version_label` versus `revision_number` semantics: accepted with the
  `version_number` clarification above.
- Initial canonical signal catalog (keys, units, validation rules): agreed,
  table in Decision 4; implemented as a code-level registry per Decision 5.
- Timezone convention (instants + IANA set timezone, `America/Santiago` as key
  case): accepted.
- Manual edit policy (bounded edits creating new revisions with recalculated
  hashes): accepted.
- Out-of-scope list (no case bindings, no result series, no resampling, no
  complex unit conversion, no hydraulic table migration): confirmed.
- No PRD text correction is required before downstream TS-2 implementation
  begins; the version/revision clarification above is documented for
  implementers.
