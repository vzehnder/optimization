# BESSDispatch

Julia package for the single-BESS price-taker dispatch MVP. The sample case
lives in `data/cases/arbitrage_mvp` and reads scalar configuration from YAML
plus hourly prices and durations from CSV.

## Run Tests

From the repository root:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Run The Sample Case

This command loads `data/cases/arbitrage_mvp`, solves the dispatch model with
HiGHS, and writes a run folder under `outputs/arbitrage_mvp/<run_timestamp>/`.

```powershell
julia --project=. -e "using BESSDispatch; run_output = BESSDispatch.run_case(ARGS[1]); println(run_output.output_dir)" data/cases/arbitrage_mvp
```

Each run folder contains:

- `dispatch.csv`
- `summary.json`
- `config_resolved.yaml`
- `model_metadata.json`

## Run A System Case JSON

Iteration 2 adds a parallel hybrid system-dispatch API for a versioned
`system_case.json` containing graph nodes, edges, common time series, solver
settings, and asset constraints. The sample hybrid case lives at
`data/cases/hybrid_system/system_case.json` and includes one bus, one solar
renewable, one BESS, one grid connection with import/export limits, and one
local load.

Use the Julia API when embedding the optimizer in another Julia caller:

```powershell
julia --project=. -e "using BESSDispatch; system_case = BESSDispatch.load_system_case(ARGS[1]); data = BESSDispatch.normalize_system_case(system_case); result = BESSDispatch.solve_system_dispatch(data); println(result.termination_status)" data/cases/hybrid_system/system_case.json
```

Use `BESSDispatch.run_system_case` to solve and persist machine-readable
outputs:

```powershell
julia --project=. -e "using BESSDispatch; run_output = BESSDispatch.run_system_case(ARGS[1]; output_root = ARGS[2]); println(run_output.output_dir)" data/cases/hybrid_system/system_case.json outputs
```

The process-friendly CLI for a future Python worker is:

```powershell
julia --project=. scripts/run_system_case.jl data/cases/hybrid_system/system_case.json --output-root outputs
```

On success the CLI prints compact JSON to stdout with `case_name`,
`run_timestamp`, `output_dir`, `summary_path`, and `termination_status`. On
validation or solve failure it exits nonzero and writes error JSON to stderr, so
stdout remains parseable by the caller.

System periods may use the legacy single price field:

```json
"price_usd_per_mwh": 45.0
```

or paired import/export prices:

```json
"import_price_usd_per_mwh": 55.0,
"export_price_usd_per_mwh": 38.0
```

When separate prices are present, import cost and export revenue drive the
objective and are included in result outputs. Legacy single-price cases remain
valid and keep the existing `price_usd_per_mwh` output column.

Iteration 5 adds the first `bess_system_dispatch.v2` Julia contract path for a
linear simple-reservoir hydro asset. The sample lives at
`data/cases/linear_hydro_system/system_case.json` and can be run through the
same API or CLI:

```powershell
julia --project=. scripts/run_system_case.jl data/cases/linear_hydro_system/system_case.json --output-root outputs
```

The linear hydro node uses `hydro_inflow_m3s` time-series values, reservoir
storage in `hm3`, turbine and spill flows in `m3/s`, a mandatory reservoir
storage/elevation curve, terminal storage settings, spill penalty, and terminal
water value. Legacy `bess_system_dispatch.v1` cases remain accepted.

Each system run folder contains:

- `dispatch.csv`: one row per period with system totals including
  `grid_import_mw`, `grid_export_mw`, `renewable_curtailed_mw`,
  `load_demand_mw`, battery totals, market value, and period profit. Separate
  price runs also include import/export prices, import cost, export revenue,
  and net market value columns. Hydro v2 runs also include total hydro power,
  inflow, turbine flow, spill flow, storage, spill penalty, and terminal water
  value columns.
- `asset_dispatch.csv`: long asset-level rows keyed by `asset_id`, with the
  same grid, renewable, load, and battery dispatch fields for dynamic UI tables.
  Hydro v2 runs include `asset_type = hydro` rows with hydro power, inflow,
  turbine flow, spill flow, volumes, storage, reservoir elevation, spill
  penalty, and terminal water value.
- `summary.json`: compact run status, objective value, source identifiers, and
  model version. Hydro v2 runs include hydro KPIs by asset and hydro totals.
- `system_case_resolved.json`: normalized copy of the accepted input contract.
- `model_metadata.json`: model name, schema version, bus ID, period count,
  asset IDs, active constraint flags, and unit conventions, including hydro
  unit conventions when hydro assets are present.

## Generate The Plotly Report

Pass a completed run output folder to the report script:

```powershell
python python/plot_results.py outputs/arbitrage_mvp/<run_timestamp>
```

The script writes:

```text
outputs/arbitrage_mvp/<run_timestamp>/plots/dispatch_report.html
```

The report includes price and dispatch, stored energy, period profit, and
degradation cost traces.

## Run The Analyst Web App

Iteration 3 adds a private FastAPI analyst flow around the Julia system-case
CLI. From the repository root, install the Python web dependencies in the local
virtual environment and start the app:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///.tmp/analyst_app.sqlite3"
$env:ARTIFACT_ROOT = ".tmp/artifacts"
$env:JULIA = "julia"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/projects`. The first screen is the internal
project list and project creation form.

### Database Configuration

The app reads `DATABASE_URL` at startup. The Iteration 3 local implementation
supports `sqlite:///...` URLs, including `sqlite:///:memory:` for tests and
`sqlite:///.tmp/analyst_app.sqlite3` for local development.

The app domain is already organized around tables that map cleanly to a future
PostgreSQL or Supabase-backed deployment:

- `projects`
- `scenarios`
- `scenario_versions`
- `runs`
- `run_artifacts`

Supabase is not required for Iteration 3. Supabase Auth, Storage, Row Level
Security, Edge Functions, and platform-specific behavior remain out of scope for
this local analyst proof.

### Validate And Save A Scenario Version

Create a project, open it, create a scenario, then paste the full contents of
`data/cases/hybrid_system/system_case.json` into the scenario page's
`system_case_json` textarea. Click `Validate And Save`.

The backend first parses JSON, then delegates system-case contract validation to
Julia through:

```powershell
julia --project=. scripts/validate_system_case.jl <candidate-system-case.json>
```

Valid inputs are saved as immutable `ScenarioVersion` records. Invalid JSON or
Julia validation errors are returned to the API/UI and no version is created.
The JSON document remains the canonical optimization input for that version.

### Launch A Manual Run

Each saved scenario version has a `Launch Run` action. Launching a run creates a
queued `Run` quickly, then the local single-worker queue executes Julia through:

```powershell
julia --project=. scripts/run_system_case.jl <run-input-system-case.json> --output-root <run-output-root>
```

The run detail page polls `/api/runs/{run_id}` and shows `queued`, `running`,
`succeeded`, or `failed`, plus timestamps, exit code, and any stored error
message. Completed runs expose parsed summary, dispatch tables, asset dispatch
tables, and fixed basic charts from the Julia output artifacts.

### Auditable Artifacts And Downloads

Set `ARTIFACT_ROOT` to choose where run files are written. For a local run, the
backend stores files under:

```text
<ARTIFACT_ROOT>/runs/<run_id>/
```

The app preserves and registers:

- `input/system_case.json`: exact input snapshot used for execution.
- `logs/stdout.log`: captured Julia stdout.
- `logs/stderr.log`: captured Julia stderr.
- `outputs/<case>/<timestamp>/summary.json`: run summary.
- `outputs/<case>/<timestamp>/dispatch.csv`: system-level dispatch table.
- `outputs/<case>/<timestamp>/asset_dispatch.csv`: asset-level dispatch table.
- `outputs/<case>/<timestamp>/model_metadata.json`: model metadata.

The database stores artifact metadata and safe filesystem paths. Downloads are
served through `/api/run-artifacts/{artifact_id}/download` only when the
registered file is under `ARTIFACT_ROOT`.

### Iteration 3 Acceptance Verification

Run the full Python web acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run the Julia optimizer regression suite:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

The Iteration 3 acceptance test covers project creation, scenario creation,
validated scenario version creation, manual run launch, successful completion,
artifact registration, summary/table review, chart payloads, artifact
downloads, malformed JSON rejection, and failed-run logs/errors.

## Use The Structured Draft Editor

Iteration 4 adds a structured editor path beside the paste/upload
`system_case_json` path. Create a project, create a scenario, then open
`/scenarios/{scenario_id}/draft` or use the `Open Draft` link on the scenario
page.

The draft is mutable and may be incomplete. Saving the draft does not create an
executable version. Execution still starts only from an immutable
`ScenarioVersion`.

The draft page supports:

- Structured case, PCC, grid, battery, renewable, load, and solver form fields.
- A raw `structured_draft_json` textarea for advanced edits.
- CSV/XLSX source upload, preview, mapping, and mapped-row validation.
- Read-only generated `system_case` preview.
- Julia-backed generated-case validation.
- Promotion of a current valid generated case to a new immutable scenario
  version.

### Supported Assets And One-Bus Assumptions

Generated cases remain `bess_system_dispatch.v1` one-bus cases. The editor
creates exactly one PCC or bus and automatically connects every modeled asset to
that PCC with logical edges. These edges express connectivity for the one-bus
optimizer; they are not physical lines and do not carry losses, impedance,
direction, or network-flow constraints.

Supported structured assets in Iteration 4:

- `grid`: import/export limits and import/export anti-simultaneity.
- `battery`: charge/discharge power, energy bounds, initial energy,
  efficiencies, degradation cost, terminal condition, and charge/discharge
  anti-simultaneity.
- `renewable`: solar or wind display metadata, exogenous availability, and
  optional curtailment penalty.
- `load`: fixed demand by period.

Hydropower, multiple physical buses, manual edge editing, scheduling, auth,
customer portals, and configurable dashboards remain out of scope for this
iteration.

### CSV And XLSX Source Files

Upload time-series data from the draft page. The app stores the original file
under `INPUT_SOURCE_ROOT` and keeps only safe source identifiers in exposed
editor-promoted metadata.

Local startup can set the source-file root explicitly:

```powershell
$env:INPUT_SOURCE_ROOT = ".tmp/input-sources"
```

CSV files must be UTF-8 with a single header row. XLSX files use a selected
sheet when provided or the first sheet by default. Basic XLSX workbooks are
supported; formulas, merged cells, Excel tables, missing sheets, empty headers,
duplicate headers, named ranges, unit conversion, and advanced ETL are rejected
or out of scope.

### Column Mapping Rules And Units

Source columns can be auto-suggested and manually corrected before generation.
Expected units match the optimizer contract:

- `timestamp`: period start timestamp, unique and sorted ascending.
- `duration_hours`: positive duration in hours.
- `price_usd_per_mwh`: legacy single energy price in USD/MWh.
- `import_price_usd_per_mwh`: import/buy price in USD/MWh.
- `export_price_usd_per_mwh`: export/sell price in USD/MWh.
- `renewable_available_power_mw`: nonnegative MW by renewable asset ID.
- `load_demand_mw`: nonnegative MW by load asset ID.

Each source must map `timestamp`, `duration_hours`, a complete price mode, every
renewable availability series, and every load demand series. Use either
`price_usd_per_mwh` or both `import_price_usd_per_mwh` and
`export_price_usd_per_mwh`; mapping only one separate price is invalid. Numeric
columns must contain numeric values for every mapped row.

### Legacy Single Price And Separate Import/Export Prices

Legacy cases use one `price_usd_per_mwh` value per period for both grid import
cost and grid export revenue. Those cases remain valid and keep the legacy
price column in `dispatch.csv` and `asset_dispatch.csv`.

Structured editor cases can map separate buy/sell prices. Generated periods use
`import_price_usd_per_mwh` and `export_price_usd_per_mwh`; Julia uses import
price for grid import cost and export price for grid export revenue. Separate
price outputs include:

- `import_price_usd_per_mwh`
- `export_price_usd_per_mwh`
- `import_cost_usd`
- `export_revenue_usd`
- `net_market_value_usd`

Result tables show those columns and the price chart prefers import/export
price series. Legacy runs fall back to a single price series.

### Draft Validation, Preview, And Promotion

The generated preview is read-only because the structured draft remains the
editor source. The validation sequence is:

```text
structured draft + mapped source rows
-> Python editor and ingestion validation
-> generated system_case preview
-> Julia contract validation
-> promote to immutable ScenarioVersion
-> launch manual run
-> result tables, charts, and downloads
```

Error phases are separated for supportability: source-file parsing, mapping,
Python data validation, Julia validation, and run execution failures. Promoted
versions retain safe generation metadata with source filename, media type,
stored source identifier, accepted mapping, and generation timestamp.

### Iteration 4 Acceptance Verification

Run the final Iteration 4 Python acceptance test:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter4_acceptance -v
```

Run the full Python web acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run the Julia optimizer regression suite:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

The Iteration 4 acceptance test proves CSV and XLSX structured draft flows from
draft creation through source mapping, generated preview, Julia-backed
validation, promotion, manual run, artifact registration, result tables, price
charts, and downloads. It also proves the Iteration 3 paste/upload JSON path and
legacy single-price result behavior remain intact.
