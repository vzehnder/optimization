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

Each system run folder contains:

- `dispatch.csv`: one row per period with system totals including
  `grid_import_mw`, `grid_export_mw`, `renewable_curtailed_mw`,
  `load_demand_mw`, battery totals, market value, and period profit. Separate
  price runs also include import/export prices, import cost, export revenue,
  and net market value columns.
- `asset_dispatch.csv`: long asset-level rows keyed by `asset_id`, with the
  same grid, renewable, load, and battery dispatch fields for dynamic UI tables.
- `summary.json`: compact run status, objective value, source identifiers, and
  model version.
- `system_case_resolved.json`: normalized copy of the accepted input contract.
- `model_metadata.json`: model name, schema version, bus ID, period count,
  asset IDs, active constraint flags, and unit conventions.

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
