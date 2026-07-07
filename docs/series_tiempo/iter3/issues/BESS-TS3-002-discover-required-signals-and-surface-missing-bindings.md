# BESS-TS3-002: Discover Required Signals And Surface Missing Bindings

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-10
Fecha de termino planificada: 2026-07-13
Fecha de inicio real: 2026-07-06
Fecha de termino real: 2026-07-06

## User stories covered

9, 19

## What to build

Make variant completeness explicit. The backend derives the list of required
signals for a case from its topology and parameters (which assets exist, which
constraints are active), and each variant reports, per required signal,
whether it is bound and to what. Incomplete variants cannot be validated or
run; the error names each missing required signal.

Required-signal discovery and binding-completeness evaluation live in a deep
module testable without UI. The React variant view lists every required
signal with its bound/missing state so an analyst immediately sees what is
left to bind.

## Acceptance criteria

- [x] Required signals are derived from the case topology and parameters via a deep module testable without UI.
- [x] Each variant reports a bound or missing state per required signal, including the bound set/signal when present.
- [x] Validating or running an incomplete variant fails with one clear error per missing required signal.
- [x] The React variant view lists required signals with their binding status.
- [x] Backend tests prove missing-binding errors per required signal and completeness for a fully bound variant.

## Resolution

Implemented test-first (RED/GREEN per behavior):

- New deep module `app/required_signals.py`: `discover_required_signals`
  derives required signals from the one-bus `nodes`/`edges` topology shape
  `generate_system_case_from_draft` produces (the only shape
  `materialize_system_case_for_variant` currently reads; the
  `hydraulic_network` shape is out of reach through this endpoint today and
  was left unimplemented rather than built speculatively). `grid` nodes
  require a price signal, satisfied by any of `price_usd_per_mwh` /
  `import_price_usd_per_mwh` / `export_price_usd_per_mwh` (matching TS3-001's
  finding that the legacy single-price binding is a valid completion of the
  price family, not just the asymmetric pair); `load` / `renewable` / `hydro`
  nodes each require their one signal_key from `TIME_SERIES_SIGNAL_CATALOG`.
  `evaluate_variant_completeness` reports bound/missing per required signal
  against the variant's `case_time_series_bindings` (still keyed by
  `signal_key` only, not entity-scoped — that schema change is BESS-TS3-005
  scope). `MissingRequiredSignalsError` names every missing signal in one
  message.
- `AnalystStore.materialize_system_case_for_variant` now evaluates
  completeness right after generating the base system case and raises
  `MissingRequiredSignalsError` before resolving any bindings if anything is
  missing. New `AnalystStore.evaluate_case_input_variant_required_signals`
  powers the read side for the panel; it swallows `KeyError`/
  `DraftGenerationError` from a not-yet-created editor draft (a fresh
  scenario, or a hydraulic-diagram case that never has one) and returns `[]`
  rather than 404ing the whole panel — caught by a dedicated regression test
  after Chrome verification showed the panel breaking for that case.
- API: `GET /api/scenarios/{id}/case/default-variant` now also returns
  `required_signals`; `POST .../run` catches `MissingRequiredSignalsError`
  alongside the existing `DraftGenerationError`/`InputVariantRangeError` and
  returns 400 with the same clear message.
- React: `CaseInputVariantPanel` renders every required signal with its
  bound/missing state (`price_usd_per_mwh (grid_1): falta vincular` /
  `vinculada (set #12)`), reusing the existing alert paragraph to surface the
  400 message when a run is blocked.

Chrome + real Postgres + real Julia verification (per user request), using a
"TS3-002 Chrome QA" project with two scenarios:

1. A grid+battery+load case with only price bound: the panel correctly listed
   both required signals with `load_demand_mw (load_1): falta vincular`, and
   clicking run returned the exact message
   `missing required bindings: component:load load_1 requires load_demand_mw`
   without touching Julia. Binding load too flipped both to `vinculada`.
2. A grid+battery-only case (TS3-001's tracer-bullet shape, used to confirm no
   regression): bound the same catalog price set and ran end to end — Run 9
   reached `succeeded` (HiGHS `OPTIMAL`, exit code 0) with dispatch
   charts/tables as expected.

A real, pre-existing gap was found and deliberately **not** fixed here: once
the grid+battery+load variant had both `price_usd_per_mwh` and
`load_demand_mw` bound, running it reached Julia and failed with
`ArgumentError: load_demand_mw for asset load_1 is required at
time_series[1]`. `resolve_bound_signal_series`/`materialize_variant_time_series`
(TS3-001) write every bound signal as a flat scalar column, but
`generate_system_case_from_draft`'s legacy contract expects entity-scoped
signals (`load_demand_mw`, `renewable_available_power_mw`, `hydro_inflow_m3s`)
as a `{asset_id: value}` map per period — see
`draft_editor._period_from_validated_row`. Fixing this correctly requires
entity-scoped bindings (which asset a `load_demand_mw` binding applies to),
which is exactly BESS-TS3-005's stated scope ("Bindings are entity-scoped, so
the same canonical signal kind can be bound to different sets for different
assets"). TS3-002's job was discovery and gating, both of which work
correctly; materializing entity-scoped signal families end to end is left to
TS3-005, whose acceptance criteria already require it.

## Verification

- `.venv\Scripts\python.exe -m unittest discover -s tests -v` — 262 tests,
  1 skipped (pre-existing Postgres-only skip), all passing.
- `npm test -- --run`, `npx tsc -b`, `npx eslint .`, `npm run api:check`,
  `npm run build` — all clean in `frontend/`.
- Live Chrome verification against the real `energy_dispatch` Postgres
  database and real Julia, described above.

## Blocked by

BESS-TS3-001
