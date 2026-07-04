# BESS-TS2-000: Review TS-2 PRD And Series Catalog Semantics

Status: Done
Type: HITL
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-06
Fecha de termino planificada: 2026-07-06
Fecha de inicio real: 2026-07-04
Fecha de termino real: 2026-07-04

## User stories covered

1 through 23

## What to build

Review and accept the TS-2 PRD before implementation starts. The review should
confirm the semantic model of the generic time-series catalog:
`TimeSeriesSource -> TimeSeriesSet -> TimeSeriesSetRevision ->
TimeSeriesPeriod -> TimeSeriesSignal -> TimeSeriesValue`, and the boundary
against TS-3 (no case bindings in this iteration).

The outcome should be a short accepted-decision record in the iteration docs,
including any corrections to the PRD if the catalog model, revision semantics,
signal catalog or timezone convention needs adjustment.

## Acceptance criteria

- [x] The decision that BBDD is the operative source and files are auditable load sources is accepted or corrected.
- [x] The decision that sets support both multi-signal packages and single-signal sets is accepted.
- [x] The `version_label` versus `revision_number` semantics are accepted or corrected.
- [x] The initial canonical signal catalog (allowed `signal_key` values, expected units, validation rules) is agreed.
- [x] The timezone convention (timestamps as instants plus IANA set timezone, with `America/Santiago` as the key case) is accepted.
- [x] The manual edit policy (bounded edits creating new revisions with recalculated hashes) is accepted.
- [x] The out-of-scope list (no case bindings, no result series, no resampling, no complex unit conversion, no hydraulic table migration) is confirmed.
- [x] Any PRD correction is committed before downstream TS-2 implementation issues begin.

## Resolution

Accepted the TS-2 catalog semantics in
`docs/series_tiempo/iter2/decision_record_ts2_catalog_semantics.md`.

The review confirms:

1. BBDD is the operative source; CSV/XLSX remain auditable load/replace
   mechanisms recorded as `time_series_sources`.
2. `time_series_sets` support both multi-signal packages and single-signal
   sets.
3. `version_number`/`version_label` (the version the analyst picks) is
   distinct from `time_series_set_revisions.revision_number` (in-place edit
   history on one set row) — a clarification of the PRD's simplified diagram,
   grounded in `docs/db/propuesta_bbdd_componentes_timeseries.md`.
4. An initial 8-key canonical `signal_key` catalog is accepted, reusing keys
   already live in the legacy draft ingestion path
   (`price_usd_per_mwh`, `import_price_usd_per_mwh`,
   `export_price_usd_per_mwh`, `load_demand_mw`,
   `renewable_available_power_mw`, `hydro_inflow_m3s`, `natural_inflow_m3s`,
   `minimum_flow_m3s`), implemented as a backend code-level registry rather
   than a new DB allowlist table.
5. Timezone convention: instants (`TIMESTAMPTZ`) plus IANA `timezone` on the
   set, `America/Santiago` as the key case.
6. Manual edit policy: bounded edits and file replacements create a new
   revision and recomputed hash without changing `version_number`/`version_label`.
7. Out-of-scope list confirmed as written in the PRD.

No PRD text correction is required before downstream TS-2 implementation.

## Verification

- `grep -nE "TS-2 Catalog Semantics Decision Record|Status: Accepted|version_number.*monotonic integer per|Initial canonical .signal_key. catalog is accepted|Timezone convention is accepted|Manual edit policy is accepted" docs/series_tiempo/iter2/decision_record_ts2_catalog_semantics.md`
  passed after adding the decision record.
- Cross-checked the proposed canonical `signal_key` list against existing
  usage in `app/time_series_ingestion.py`, `app/persistence.py` and
  `app/draft_editor.py` to avoid inventing a second vocabulary.
- Inspected the running Postgres database (`energy_dispatch`) via `psycopg`
  to confirm no `time_series_*` catalog tables exist yet, consistent with
  this issue being purely a decision-record review with no schema changes.

## Blocked by

None - can start immediately.
