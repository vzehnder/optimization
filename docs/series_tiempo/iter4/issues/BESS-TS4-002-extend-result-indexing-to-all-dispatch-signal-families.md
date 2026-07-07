# BESS-TS4-002: Extend Result Indexing To All Dispatch Signal Families

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-13
Fecha de termino planificada: 2026-07-14
Fecha de inicio real: 2026-07-07
Fecha de termino real: 2026-07-07

## User stories covered

7, 9, 10

## What to build

Extend the tracer-bullet indexer so every `dispatch.csv` signal family that
feeds existing tables and charts is stored in BBDD: load demand, renewable
used and curtailed power, hydro generation, turbined flow, spill and storage
(covering both one-bus hydro and hydraulic-diagram cases), and the main
economics columns (profit, costs, revenues) where the UI consumes them.

Indexing must adapt to the case type: a column that does not exist for a given
case is simply absent from the indexed results, never an error and never a
fabricated zero series. Indexed series must map to canonical signal keys
rather than raw CSV column names, so downstream read, comparison and
publication surfaces do not depend on artifact column spelling.

## Acceptance criteria

- [x] Load demand and renewable used/curtailed series index for hybrid cases.
- [x] Hydro generation, turbined flow, spill and storage series index for hydro cases (one-bus and diagram).
- [x] The economics columns used by existing UI (profit, costs, revenues) index when present.
- [x] Case types missing a signal family index cleanly without spurious records or errors.
- [x] Indexed series are identified by canonical signal keys, not raw CSV column names.
- [x] Tests index representative artifacts from at least one hybrid run and one hydro run.

## Resolution

Implemented test-first (RED/GREEN per behavior):

- Read the real Julia writers (`src/system_dispatch.jl`) rather than assuming
  column shape. Found that hydraulic-diagram ("v3" network) cases write
  `dispatch.csv` through a different function (`hydraulic_v3_dispatch_dataframe`)
  that never includes grid, battery or price columns at all — only
  `timestamp`, `duration_hours` and the `total_hydro_*` family. The TS4-001
  gate (`supports_core_dispatch_index`) required grid/battery/price columns
  unconditionally, so every hydraulic-diagram run was silently skipped and
  never indexed. This was the real, code-verified gap behind user story 10 and
  the "one-bus and diagram" acceptance criterion.
- `app/result_indexing.py` now has `supports_dispatch_index`, which accepts a
  dispatch.csv if it matches the existing core (grid+battery+price) shape
  **or** a new hydro-only shape (`total_hydro_power_mw`,
  `total_hydro_turbine_flow_m3s`, `total_hydro_spill_flow_m3s`,
  `total_hydro_storage_hm3`). One-bus hydro cases still match the core shape
  (Julia writes grid/battery columns unconditionally, filled with zeros when
  absent from the topology); hydraulic-diagram cases now match the new
  hydro-only shape.
- Added `DISPATCH_SIGNAL_KEY_CATALOG`, a raw-CSV-column -> canonical
  `signal_key` map covering core, demand/renewable, hydro and economics
  families (e.g. `total_hydro_power_mw` -> `hydro_generation_power_mw`,
  `battery_degradation_cost_usd` -> `bess_degradation_cost_usd`). The indexer
  computes `dispatch_signal_keys(columns)`, restricted to whatever columns are
  actually present, so an absent family produces no entries and no errors,
  never a fabricated key.
- `run_dispatch_result_indexes` gained a `signal_keys_json` column (added via
  `_ensure_column` for existing databases, and in the `CREATE TABLE` for fresh
  ones). `replace_run_dispatch_result_index` / `get_run_dispatch_result_index`
  read and write it; `get_run_dispatch_result_index(...)["signal_keys"]`
  exposes the mapping. The existing `dispatch_table` (`columns`/`rows`) read
  contract used by React is untouched, so no UI change was required.

## Verification

- New backend tests in `tests/test_ts4_result_indexing.py`:
  `test_indexes_hydro_only_diagram_dispatch_csv_without_grid_or_battery_columns`
  (RED against the pre-existing gate, GREEN after the `supports_dispatch_index`
  change), `test_indexes_demand_renewable_and_economics_signal_keys_for_a_hybrid_run`,
  and `test_missing_signal_families_are_absent_from_signal_keys_without_errors`.
- Targeted run: `python -m unittest tests.test_ts4_result_indexing -v` (7
  tests, all passing).
- Full suite: `python -m unittest discover -s tests -v` — 303 tests, OK
  (2 skipped, pre-existing Julia-dependent skips, no failures).
- Frontend: `npm test -- --run` (61 tests passing), `npx tsc -b`, `npx eslint .`,
  `npm run api:check` and `npm run build` all passed in `frontend/` — expected,
  since this slice does not change any HTTP-visible contract.
- Real Postgres / live verification: connected to the local `energy_dispatch`
  database from `.env` and confirmed the `signal_keys_json` migration
  (`_ensure_column`) applies cleanly to the existing schema with no errors.
  Indexed real run `19` (`hybrid_system`, a genuine production run with
  `load_demand_mw`, `renewable_used_mw`, `renewable_curtailed_mw`,
  `battery_degradation_cost_usd`, `curtailment_penalty_usd` in its real
  `dispatch.csv`) and confirmed the canonical `signal_keys` mapping populated
  correctly from real artifact data. Started a second local server instance
  (`BESS_AUTH_ENABLED=false`, port 8010, same real database, no changes to the
  running production-pointed server or any user account) and confirmed
  `GET /api/runs/19/results` still serves the correct `dispatch_table` and
  chart availability after indexing — no regression on the existing read path.
  The chrome-devtools MCP browser could not be attached for an in-browser
  screenshot: its automation profile was already held by a live browser
  process (`--remote-debugging-pipe`), most likely a concurrent Claude Code
  session on this machine; forcing it closed would have risked disrupting
  that other session, so it was left alone in favor of the API-level live
  check above.

## Blocked by

BESS-TS4-001
