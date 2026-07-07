# BESS-TS3-006: Mark Variants Stale On Series, Topology Or Parameter Changes

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-22
Fecha de termino planificada: 2026-07-23
Fecha de inicio real: 2026-07-07
Fecha de termino real: 2026-07-07

## User stories covered

13, 14

## What to build

Keep validated variants honest. When a bound time-series set gains a new
revision (manual edit or file replacement) after a variant was validated, the
variant becomes stale because the recorded hash/revision no longer matches the
current one. Likewise, when the case topology or parameters change, variants
become stale because the required-signal set may have changed.

The stale state is visible wherever the variant appears (dropdown and variant
detail) with the reason (series changed versus topology/parameters changed).
Revalidating refreshes the recorded revisions and hashes and clears the stale
marker; a stale variant cannot launch a run until revalidated (per the
BESS-TS3-000 decision record).

## Acceptance criteria

- [x] A new revision on a bound set marks every validated variant that binds it as stale.
- [x] A topology or parameter change on the case marks its variants as stale.
- [x] The stale state and its reason are visible in the variant dropdown and variant detail.
- [x] Revalidation refreshes the recorded set revisions and hashes and clears the stale marker.
- [x] Launching a run from a stale variant is blocked until revalidation, consistent with the accepted decision record.
- [x] Backend tests prove stale detection for a hash change, a topology change and a parameter change, plus the revalidation path.

## Blocked by

BESS-TS3-003

## Implementation Notes

Staleness is computed lazily by comparing recorded vs. current dependency
hashes, not via write-time triggers on every series/topology/parameter
mutation path (mirrors the read-side comparison pattern TS-1 already
established for `hierarchy_stale_state`, rather than the write-time
`optimization_cases.validation_payload_json` staleness path used by the
legacy hydraulic-diagram validator).

- New generic `validation_dependencies` table (`owner_type='case_input_variant'`,
  `owner_id`, `dependency_type` in `{'time_series_set', 'topology',
  'parameters'}`, `dependency_id`, `recorded_hash`), per the accepted TS3-000
  decision record. No new columns on `case_input_variants`.
- `app/variant_staleness.py`: pure `evaluate_variant_staleness` comparing
  recorded vs. current dependency hashes (symmetric diff: changed, added, or
  no-longer-bound each produce a reason), `VariantStaleError`.
- `AnalystStore.evaluate_case_input_variant_staleness` computes current
  dependencies from live bound sets' `content_hash` plus
  `derive_case_hierarchy_provenance` (existing TS-1 helper) over the
  variant's base `system_case`, and compares against recorded rows. Returns
  `{validated, stale, reasons}`; a variant with no recorded validation yet is
  `validated: false, stale: false` (nothing to have drifted from).
- `materialize_system_case_for_variant` (used by `run`) now stale-precheck
  first (raises `VariantStaleError`, HTTP 400, if stale) before doing
  completeness/range validation. A new `validate_case_input_variant` runs the
  same completeness/range/materialize logic without the stale precheck and
  without creating a run, so it is the only path that can clear a stale
  marker; both paths record fresh dependencies on success via a shared
  `_resolve_variant_series_for_range` helper.
- New `POST /api/scenarios/{id}/case/variants/{variant_id}/validate` route.
  `staleness` added to `GET .../default-variant` and `GET .../variants`
  variant-detail payloads.
- React: dropdown options append "(desactualizada)" when stale; the binding
  editor shows a stale banner with reasons and a "Revalidar variante" button,
  and disables "Vincular y correr variante" while stale.

Verification: Python suite 291 passed / 2 skipped (up from 276 before this
slice, including 6 new pure-module tests, 5 new persistence tests and 5 new
API tests); frontend suite 57 passed plus `tsc -b`, `eslint .`, `api:check`,
and `build`. Chrome-devtools
MCP against real PostgreSQL (project `TS3-006 Chrome QA`, scenario 40)
confirmed: a manual value edit (revision bump) on a bound set marked the
already-validated default variant stale with the exact reason text
(`time-series set 24 changed since last validation`) in both the dropdown
("(desactualizada)") and the binding-editor alert; rebinding to a different
set produced both an "added" and a "no longer bound" reason simultaneously;
the run button was disabled while stale; clicking "Revalidar variante"
cleared the marker (dropdown and banner both updated) without a page reload;
and a subsequent run reached Run 15 `succeeded` (HiGHS `OPTIMAL`, objective
197.6) end to end.
