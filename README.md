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

Iteration 5 adds `bess_system_dispatch.v2` Julia contract paths for
simple-reservoir hydro assets. The linear sample lives at
`data/cases/linear_hydro_system/system_case.json` and the piecewise sample lives
at `data/cases/piecewise_hydro_system/system_case.json`. Both can be run through
the same API or CLI:

```powershell
julia --project=. scripts/run_system_case.jl data/cases/linear_hydro_system/system_case.json --output-root outputs
julia --project=. scripts/run_system_case.jl data/cases/piecewise_hydro_system/system_case.json --output-root outputs
```

Hydro nodes use `hydro_inflow_m3s` time-series values, reservoir storage in
`hm3`, turbine and spill flows in `m3/s`, a mandatory reservoir
storage/elevation curve, terminal storage settings, spill penalty, and terminal
water value. Linear hydro uses `power_per_flow_mw_per_m3s`; piecewise hydro
uses explicit nonconvex or nonmonotone `(flow_m3s, power_mw)` breakpoints through
`PiecewiseLinearOpt`. Legacy `bess_system_dispatch.v1` cases remain accepted.

### Simple Reservoir Hydro Scope

`bess_system_dispatch.v2` adds one `hydro` node type. One hydro node represents
one independent reservoir and one associated plant connected to the common
one-bus PCC. Multiple hydro nodes are allowed, but they are independent and
share only the electrical bus balance.

The hydro scope excludes hydraulic cascades, hydraulic network routing,
travel-time delays, pumped storage, multiple reservoirs coupled to one plant,
multiple plants sharing one reservoir, and generation curves that depend on
reservoir elevation or head. Electrical modeling remains one-bus; graph edges
are logical connectivity only.

### Hydro Units And Flow Conversion

Hydro storage uses `hm3`. Inflow, turbine flow, spill flow, and minimum release
use `m3/s`. Power uses `MW`, period duration uses hours, and hydro water
economics use `USD/hm3`.

The reservoir balance converts any flow over a period into volume as:

```text
volume_hm3 = flow_m3s * duration_hours * 3600 / 1_000_000
```

That conversion is used for inflow volume, turbine volume, spill volume, spill
penalty, and storage updates.

### Hydro Generation Modes

Linear hydro uses:

```text
hydro_power_mw = power_per_flow_mw_per_m3s * turbine_flow_m3s
```

Linear mode requires `power_per_flow_mw_per_m3s` and
`turbine_flow_max_m3s`. Optional `power_max_mw` can cap generated power.

Piecewise hydro uses explicit `generation_curve` breakpoints:

```json
{"flow_m3s": 30.0, "power_mw": 2.4}
```

Flow breakpoints must be nonnegative and strictly increasing. Power values must
be finite and nonnegative, but may be nonconvex or nonmonotone. The model uses
`PiecewiseLinearOpt.piecewiselinear` with the package default method. Optional
turbine-flow bounds in piecewise mode must lie inside the curve domain.

### Reservoir Curves And Water Economics

Every hydro asset requires a `reservoir_curve` of
`(storage_hm3, elevation_masl)` breakpoints. Storage breakpoints must be
strictly increasing and elevation values must be finite and nondecreasing.
Storage bounds, initial storage, and terminal storage values must lie inside
the reservoir curve domain. The reservoir curve reports elevation; it does not
affect generation in Iteration 5.

`minimum_release_m3s` is met by turbine flow plus spill flow. Spill is always
allowed and may be penalized with `spill_penalty_usd_per_hm3`. Terminal storage
modes are `none`, `equal_initial`, and `min_terminal`.
`terminal_water_value_usd_per_hm3` adds value for final stored water and can be
used with any terminal mode; when `equal_initial` fixes final storage, that
terminal value is reported but normally not dispatch-decisional.

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

Open `http://127.0.0.1:8000/`. Iteration 6 enables local authentication for
the `app.main:app` entrypoint. On a fresh database the app redirects to
`/bootstrap`, where the first internal `admin` account is created. After that,
users sign in through `/login`; `admin` and `analyst` users enter the internal
analyst app, while `client` users enter `/client`.

Passwords are stored as PBKDF2-SHA256 hashes. Sessions use opaque server-side
tokens in an HTTP-only cookie. Programmatic tests can still instantiate
`create_app()` without auth by default, or pass `auth_enabled=True` to exercise
the Iteration 6 boundary.

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

Structured editor cases generate one-bus `system_case` documents. Iteration 4
generated `bess_system_dispatch.v1`; Iteration 5 generates
`bess_system_dispatch.v2` by default, including cases without hydro. The editor
creates exactly one PCC or bus and automatically connects every modeled asset to
that PCC with logical edges. These edges express connectivity for the one-bus
optimizer; they are not physical lines and do not carry losses, impedance,
direction, or network-flow constraints. Paste/upload JSON still accepts legacy
`bess_system_dispatch.v1` cases.

Supported structured assets:

- `grid`: import/export limits and import/export anti-simultaneity.
- `battery`: charge/discharge power, energy bounds, initial energy,
  efficiencies, degradation cost, terminal condition, and charge/discharge
  anti-simultaneity.
- `renewable`: solar or wind display metadata, exogenous availability, and
  optional curtailment penalty.
- `load`: fixed demand by period.
- `hydro`: simple independent reservoir assets with linear or piecewise
  generation curves, reservoir storage/elevation curves, inflow mapping,
  spill/terminal economics, and hydro result tables/charts.

Iteration 5 structured editor cases generate `bess_system_dispatch.v2` by
default. Multiple physical buses, manual edge editing, scheduling, auth,
customer portals, and configurable dashboards remain out of scope for this
iteration.

### Hydro Structured Editor And Inflow Mapping

The draft editor can define hydro storage settings, terminal mode, spill
penalty, minimum release, terminal water value, linear parameters, piecewise
generation breakpoints, and reservoir storage/elevation breakpoints. Generated
previews include hydro nodes, hydro curves, and automatic hydro-to-PCC edges.

CSV and XLSX mapping supports `hydro_inflow_m3s.<hydro_id>` for every hydro
asset in the draft. Missing, nonnumeric, negative, or unmapped hydro inflow
values fail in Python validation before Julia validation or promotion. Promoted
versions retain safe source-file and mapping metadata without exposing absolute
local source paths.

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
- `hydro_inflow_m3s`: nonnegative `m3/s` by hydro asset ID.

Each source must map `timestamp` and `duration_hours`. Blank numeric mappings
are treated as zero values, including price fields, renewable availability,
load demand, and hydro inflow series present in the draft. Use
`price_usd_per_mwh` for legacy single-price cases, or map either/both
`import_price_usd_per_mwh` and `export_price_usd_per_mwh` for separate pricing;
an unmapped side defaults to `0.0`. Numeric columns must contain numeric values
for every mapped row.

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

### Hydro Results And Artifacts

Hydro runs preserve the same audit boundary as earlier iterations: input
snapshot, stdout/stderr logs, `summary.json`, `dispatch.csv`,
`asset_dispatch.csv`, `system_case_resolved.json`, and `model_metadata.json`.

Hydro result tables expose total hydro columns from `dispatch.csv` and hydro
asset rows from `asset_dispatch.csv`. Hydro charts cover power, inflow, turbine
flow, spill flow, storage, and reservoir elevation. Runs without hydro continue
to render price, grid, renewable, BESS, load, and profit charts; hydro chart
panels degrade through missing-column messages instead of breaking legacy pages.

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

### Iteration 5 Acceptance Verification

Run the focused Iteration 5 acceptance test:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter5_acceptance -v
```

The current Iteration 5 acceptance coverage proves linear hydro and piecewise
hydro structured editor flows, CSV and XLSX hydro inflow mapping, generated
`bess_system_dispatch.v2` previews, Julia-backed validation, promotion, manual
run execution, resolved-case and metadata artifacts, hydro result tables and
charts, paste/upload `bess_system_dispatch.v1` compatibility, structured
editor cases without hydro still generated as `v2`, and malformed hydro inputs
reported before promotion.

## Client Publication And Read-Only Portal

Iteration 6 adds the product boundary above completed analyst runs: local auth,
role-gated internal pages, admin user management, client project assignment,
minimal dashboard templates, publication drafts, client preview, publish and
unpublish controls, a read-only client portal, and allowlisted downloads.

The app still uses the Julia optimizer and artifact formats from earlier
iterations. Publications do not mutate runs or scenario versions; they curate
which completed results are visible to assigned clients.

### Local Auth Roles And Sessions

When auth is enabled, a fresh database redirects to `/bootstrap`. The bootstrap
form creates the first internal `admin` user and then closes. All later users
sign in through `/login` and end sessions through `/logout`.

Supported roles:

- `admin`: internal role that can manage users, assign clients to projects, and
  use analyst workflow pages.
- `analyst`: internal role that can create projects, scenarios, versions, runs,
  dashboard templates, and publications.
- `client`: read-only role that can only access `/client` routes for assigned
  projects and active publications.

Passwords are stored as PBKDF2-SHA256 hashes. Sessions are opaque server-side
tokens referenced by an HTTP-only cookie. Deactivated users cannot create new
sessions, and existing sessions stop resolving once the user is deactivated.

### Admin Users And Project Access

Admins manage local users from `/admin/users` or the `/api/admin/users`
endpoints. User records preserve email, display name, role, active state, and
audit timestamps without exposing password hashes through API responses.

Client project access is explicit many-to-many assignment. Admins add or remove
client users under a project through the admin project-access endpoints. A
client sees only assigned projects on `/client`, and assignment removal
immediately blocks project pages, publication pages, and downloads for that
project.

### Dashboard Templates

Dashboard templates belong to a project and control selected result sections
for client views. They can enable or disable summary KPIs, price charts, grid
charts, renewable charts, BESS charts, hydro charts, profit charts, system
dispatch table previews, and asset dispatch table previews. `table_preview_limit`
keeps client tables bounded.

Templates reuse existing result readers. Missing columns hide or mark only the
unavailable section, so legacy runs without hydro columns and older single-price
runs still render cleanly.

### Publication Drafts Preview Publish And Unpublish

Analysts create publication drafts from succeeded runs only. A publication
stores project, scenario, scenario version, run, selected dashboard template,
public title, analyst notes, status, allowed artifact types, and audit fields.

Drafts start hidden from clients. Internal users can open
`/publications/{publication_id}/preview` to see the same client renderer before
publishing. Publishing changes status to `published`; unpublishing changes
status to `unpublished` and removes client access immediately without deleting
the internal run or publication record.

### Client Portal And Read-Only Routes

Clients enter at `/client`, see assigned projects, open
`/client/projects/{project_id}`, and then open active publications under
`/client/projects/{project_id}/publications/{publication_id}`. These pages show
publication title, notes, run provenance, selected summary, selected charts,
limited table previews, and enabled downloads.

Client pages do not render analyst controls such as draft editing, validation,
source upload, promotion, run launch, publication editing, or internal artifact
downloads. Client attempts to access internal pages or APIs return a controlled
redirect, `403`, or `404` depending on authentication and object visibility.

### Artifact Allowlist And Revocation

Publication drafts default to business artifacts when those files are
registered:

- `summary_json`
- `dispatch_csv`
- `asset_dispatch_csv`

Technical artifacts such as input snapshots, stdout logs, stderr logs, resolved
system cases, and model metadata are disabled by default. Analysts can enable
registered artifact types explicitly. Client download routes validate client
role, active session, project assignment, publication status, artifact allowlist
membership, and safe registered paths under `ARTIFACT_ROOT` before returning a
file.

Revocation is immediate for three cases: user deactivation, project-assignment
removal, and publication unpublish. Those changes stop client page and download
access without changing the underlying analyst run history.

### Iteration 6 Acceptance Verification

Run the focused Iteration 6 acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_acceptance -v
```

Run the full Python web acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Iteration 6 does not change Julia-facing contracts or artifact formats. Run the
Julia suite only when a later change touches optimizer behavior or output
formats:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```
