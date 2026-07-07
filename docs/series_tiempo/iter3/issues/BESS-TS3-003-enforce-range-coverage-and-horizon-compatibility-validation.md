# BESS-TS3-003: Enforce Range Coverage And Horizon Compatibility Validation

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-14
Fecha de termino planificada: 2026-07-15
Fecha de inicio real: 2026-07-07
Fecha de termino real: 2026-07-07

## User stories covered

11, 12, 19

## What to build

Harden variant validation against the selected date range. Before a run is
launched, the backend verifies that every bound set covers the requested range
with no missing dates and that all bound sets share exactly compatible
periods; mixed resolutions fail with explicit errors because TS-3 does no
implicit resampling. A successful validation records the exact set revisions
and content hashes it validated against, so later stale detection and run
lineage have a fixed reference.

Coverage and horizon-compatibility logic lives in the same deep validation
module as binding resolution. React shows the validation outcome states
(valid, incomplete coverage, mismatched periods) with actionable messages.

## Acceptance criteria

- [x] Range coverage validation rejects a run whose bindings do not cover the requested dates, naming the failing binding and the missing span.
- [x] Horizon compatibility validation rejects mixed or incompatible period resolutions with explicit errors; no implicit resampling occurs.
- [x] A successful validation records the bound set revisions and content hashes it validated against.
- [x] Backend tests cover complete, incomplete and mismatched-period scenarios per binding.
- [x] The React run flow surfaces validation states (valid, incomplete coverage, mismatched periods) before launch.

## Resolution

Implemented TDD-first.

- Hardened `app/input_variants.py` range validation so coverage failures name
  the exact binding, time-series set, and missing span. Boundary cuts now fail
  as horizon incompatibility, and cross-signal mismatches fail explicitly with
  "no implicit resampling" messaging.
- Preserved the deep-module shape from TS3-001/002: binding resolution,
  coverage validation, horizon compatibility, and time-series materialization
  stay outside route code.
- Extended `AnalystStore.materialize_system_case_for_variant` lineage so every
  validated binding records `version_number`, `version_label`,
  `revision_number`, `content_hash`, and `validated_range`.
- Added React pre-launch state in `CaseInputVariantPanel`: valid ranges show
  `Rango valido para correr.`, incomplete coverage shows an alert with the
  missing span, and period-boundary mismatches show `Horizonte incompatible`.
  The run button is disabled until the selected range is locally valid; the
  backend remains authoritative and still rejects invalid requests.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_input_variants tests.test_ts3_input_variants -v
.\.venv\Scripts\python.exe -m unittest tests.test_ts3_case_variant_api -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Results:

- Python suite: 266 tests passed, 1 skipped (pre-existing
  PostgreSQL-only skip).

Frontend:

```powershell
cd frontend
npm.cmd test -- --run App.test.tsx
npm.cmd test -- --run
npx.cmd tsc -b
npx.cmd eslint .
npm.cmd run api:check
npm.cmd run build
```

Results:

- Frontend suite: 54 tests passed.
- Typecheck, lint, API check, and production build passed. Vite emitted the
  existing large-chunk warning only.

Chrome / MCP verification:

- Ran the production React build through FastAPI at
  `http://127.0.0.1:8767/react/scenarios/31` against the real
  `energy_dispatch` PostgreSQL database.
- Seeded QA project `TS3-003 Chrome QA`, scenario
  `TS3-003 range validation case`, and two price sets in the real database.
- Verified with chrome-devtools MCP:
  - selecting the complete set shows `Rango valido para correr.` and enables
    `Vincular y correr variante`;
  - changing the end to `2026-01-01T04:00:00-03:00` shows
    `Cobertura incompleta: falta 2026-01-01T03:00:00-03:00 a 2026-01-01T04:00:00-03:00.`
    and disables the run button;
  - changing the start to `2026-01-01T00:30:00-03:00` shows
    `Horizonte incompatible: el rango debe comenzar en limite de periodo
    (2026-01-01T00:00:00-03:00).` and disables the run button.
- Verified the live backend 400 path from the page via fetch:
  `binding 'price_usd_per_mwh' on time-series set 14 missing coverage for
  [2026-01-01T03:00:00-03:00, 2026-01-01T04:00:00-03:00)`.
- Used the Chrome extension control surface to open the local app and inspect
  the local tab; Chrome later blocked tab claiming because another extension
  UI was active, so the interaction checks were completed with chrome-devtools
  MCP.

## Blocked by

BESS-TS3-002
