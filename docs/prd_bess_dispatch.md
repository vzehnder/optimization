# BESS Dispatch Optimization PRD

## 1. Purpose

Build a Julia-based optimization model for Battery Energy Storage System (BESS) dispatch. The first product version must solve a single-BESS, price-taker energy arbitrage problem while establishing a flexible architecture that can later support real-world case-specific constraints, Excel and database data sources, rolling-horizon optimization, and richer degradation models.

The model must be designed so that general BESS physics and reusable formulations are separated from case-specific business rules and operational constraints.

## 2. MVP Scope

The MVP solves a deterministic energy arbitrage problem for one BESS connected to the grid.

The BESS can:

- Charge from the grid.
- Discharge to the grid.
- Optimize against an exogenous price time series.
- Respect energy, power, efficiency, terminal energy, and anti-simultaneous charge/discharge constraints.
- Include a linear degradation cost based on absolute changes in state of charge between consecutive periods.

The objective is to maximize net arbitrage value:

```text
energy market revenue - charging cost - linear degradation cost
```

## 3. Non-Goals For The MVP

The MVP will not include:

- Multiple BESS assets.
- Local generation.
- Local demand.
- Network or nodal constraints.
- Ancillary services.
- Demand charges or peak shaving.
- Battery degradation based on cycles, depth-of-discharge curves, rainflow counting, or calendar aging.
- Terminal salvage value.
- A database connector implementation.
- A web dashboard.

These items can be added later as case-specific modules or new data loaders without changing the base model interface.

## 4. Core Decisions

- Language: Julia.
- Optimization framework: JuMP.
- Default solver: HiGHS.
- Model type: MILP, because the MVP uses a binary variable to prevent simultaneous charge and discharge.
- Documentation language: English.
- Code identifiers: English.
- Units:
  - Power: MW.
  - Energy: MWh.
  - Price: USD/MWh.
  - Duration: hours.
  - Revenue and cost: USD.
  - Linear degradation coefficient: USD/MWh of absolute energy movement.
- Time convention:
  - Input timestamps represent the start of each period.
  - `duration_hours[t]` is the length of period `t`.
  - `energy_mwh[t]` represents the BESS energy at the end of period `t`.

## 5. Functional Requirements

### 5.1 Data Loading

The model builder must not read files, spreadsheets, or databases directly. It must receive a validated `CaseData` struct.

The MVP data source will load:

- Scalar and configuration parameters from YAML.
- Time series from CSV.

Future data sources should be implemented behind the same interface:

- Excel loader.
- Database loader.

All loaders must produce the same validated internal structs.

### 5.2 Data Validation

The loader layer must validate inputs before building the JuMP model.

Minimum validations:

- `duration_hours[t] > 0`.
- `price[t]` is present for every period.
- Timestamps are unique and sorted.
- `energy_min_mwh <= initial_energy_mwh <= energy_max_mwh`.
- `energy_min_mwh < energy_max_mwh`.
- `charge_power_max_mw >= 0`.
- `discharge_power_max_mw >= 0`.
- `0 < charge_efficiency <= 1`.
- `0 < discharge_efficiency <= 1`.
- `degradation_cost_per_mwh_delta_soc >= 0`.
- If `terminal_condition = min_terminal`, `terminal_energy_min_mwh` must be provided.
- If `terminal_condition = equal_initial`, no additional terminal energy parameter is required.

Invalid input data must fail fast with explicit error messages.

### 5.3 Configurable Constraints

The configuration must provide a simple way to activate or deactivate selected constraints before each run.

Core physical constraints are mandatory in standard runs:

- Energy balance.
- Energy bounds.
- Power bounds.

Configurable constraints:

- Prevent simultaneous charge and discharge.
- Terminal condition.
- Linear degradation based on absolute SOC movement.

Recommended config shape:

```yaml
constraints:
  energy_balance: true
  soc_bounds: true
  power_bounds: true
  prevent_simultaneous_charge_discharge: true
  terminal_condition: equal_initial
  degradation_linear_delta_soc: true
```

For the MVP, standard runs should reject attempts to disable core physical constraints. A later research mode can introduce `strict_physics: false` if needed.

### 5.4 Horizon Handling

The MVP will optimize the full time horizon provided in the input time series.

The internal model must always use indexed period duration:

```text
duration_hours[t]
```

This is required even when all periods initially have the same length.

The config should reserve fields for future rolling-horizon optimization:

```yaml
horizon:
  mode: full_horizon
  start_timestamp: null
  end_timestamp: null
  step_hours: null
  lookahead_periods: null
```

Future `rolling_horizon` support should reuse the same base formulation by solving moving windows over the period index.

### 5.5 Terminal Energy

The MVP supports these terminal condition modes:

- `none`: no terminal energy constraint.
- `equal_initial`: final energy must equal `initial_energy_mwh`.
- `min_terminal`: final energy must be at least `terminal_energy_min_mwh`.

Default mode:

```text
equal_initial
```

No terminal salvage value is included in the MVP objective.

### 5.6 Degradation

The MVP degradation model is linear and based on absolute changes in stored energy between periods.

For the first period, the movement is measured against `initial_energy_mwh`.

For later periods, the movement is measured against the previous period energy.

This requires an auxiliary variable:

```text
delta_soc_abs_mwh[t] >= energy_mwh[t] - reference_energy_mwh[t]
delta_soc_abs_mwh[t] >= reference_energy_mwh[t] - energy_mwh[t]
```

The cost is:

```text
degradation_cost_per_mwh_delta_soc * delta_soc_abs_mwh[t]
```

## 6. Proposed Julia Architecture

Recommended repository structure:

```text
Project.toml
src/
  BESSDispatch.jl
  types.jl
  io/
    loaders.jl
    csv_loader.jl
    yaml_loader.jl
    excel_loader.jl       # future
    db_loader.jl          # future
  model/
    base_model.jl
    objective.jl
    constraints_general.jl
    constraints_config.jl
  cases/
    arbitrage.jl
    real_case_template.jl
  results/
    writer.jl
scripts/
  run_case.jl
python/
  plot_results.py
docs/
  mathematical_model.md
data/
  cases/
    arbitrage_mvp/
outputs/
```

General BESS physics and reusable constraints belong in:

```text
src/model/constraints_general.jl
```

Case-specific business rules belong in:

```text
src/cases/
```

The model builder must depend on validated structs, not on file paths or database connections.

## 7. Core Structs

Initial structs should include:

```julia
struct BESSParameters
    charge_power_max_mw::Float64
    discharge_power_max_mw::Float64
    energy_min_mwh::Float64
    energy_max_mwh::Float64
    initial_energy_mwh::Float64
    charge_efficiency::Float64
    discharge_efficiency::Float64
    degradation_cost_per_mwh_delta_soc::Float64
end
```

```julia
struct TimeSeriesData
    timestamp::Vector{DateTime}
    price_usd_per_mwh::Vector{Float64}
    duration_hours::Vector{Float64}
end
```

```julia
struct ConstraintConfig
    prevent_simultaneous_charge_discharge::Bool
    terminal_condition::String
    degradation_linear_delta_soc::Bool
end
```

```julia
struct SolverConfig
    name::String
    options::Dict{String,Any}
end
```

```julia
struct HorizonConfig
    mode::String
    start_timestamp::Union{DateTime,Nothing}
    end_timestamp::Union{DateTime,Nothing}
    step_hours::Union{Float64,Nothing}
    lookahead_periods::Union{Int,Nothing}
end
```

```julia
struct CaseData
    case_name::String
    bess::BESSParameters
    time_series::TimeSeriesData
    constraints::ConstraintConfig
    solver::SolverConfig
    horizon::HorizonConfig
end
```

These types can evolve, but the model builder should keep receiving a `CaseData` object.

## 8. Input File Contract

Recommended MVP case folder:

```text
data/cases/arbitrage_mvp/
  config.yaml
  bess.yaml
  timeseries.csv
```

Example `config.yaml`:

```yaml
case_name: arbitrage_mvp

solver:
  name: HiGHS
  options: {}

constraints:
  prevent_simultaneous_charge_discharge: true
  terminal_condition: equal_initial
  degradation_linear_delta_soc: true

horizon:
  mode: full_horizon
  start_timestamp: null
  end_timestamp: null
  step_hours: null
  lookahead_periods: null
```

Example `bess.yaml`:

```yaml
charge_power_max_mw: 10.0
discharge_power_max_mw: 10.0
energy_min_mwh: 0.0
energy_max_mwh: 40.0
initial_energy_mwh: 20.0
charge_efficiency: 0.95
discharge_efficiency: 0.95
degradation_cost_per_mwh_delta_soc: 2.0
```

Example `timeseries.csv`:

```text
timestamp,price_usd_per_mwh,duration_hours
2026-01-01T00:00:00,40.0,1.0
2026-01-01T01:00:00,20.0,1.0
2026-01-01T02:00:00,90.0,1.0
```

## 9. Output Contract

Each run must create a run-specific output folder:

```text
outputs/<case_name>/<run_timestamp>/
```

Minimum files:

```text
summary.json
dispatch.csv
config_resolved.yaml
model_metadata.json
```

`dispatch.csv` must include one row per period:

- `timestamp`
- `duration_hours`
- `price_usd_per_mwh`
- `p_charge_mw`
- `p_discharge_mw`
- `net_discharge_mw`
- `energy_mwh`
- `delta_soc_abs_mwh`
- `is_charging`
- `period_profit_usd`
- `degradation_cost_usd`

`net_discharge_mw` is derived as:

```text
p_discharge_mw - p_charge_mw
```

Positive values mean net discharge/export to grid. Negative values mean net charge/import from grid.

`summary.json` must include:

- Case name.
- Run timestamp.
- Solver name.
- Solver status.
- Termination status.
- Objective value.
- Input data source paths or identifiers.
- Model version or git commit when available.

`model_metadata.json` must include:

- Model name.
- Active constraint flags.
- Terminal condition mode.
- Number of periods.
- Unit conventions.

## 10. Python Plotting Requirement

The MVP must include a Python script:

```text
python/plot_results.py
```

The script reads a run output folder and writes:

```text
outputs/<case_name>/<run_timestamp>/plots/dispatch_report.html
```

The HTML report must include:

- Price and dispatch:
  - `price_usd_per_mwh`
  - `p_charge_mw`
  - `p_discharge_mw`
- Energy state:
  - `energy_mwh`
- Period economics:
  - `period_profit_usd`
  - `degradation_cost_usd`

The MVP does not require a web dashboard.

## 11. Acceptance Criteria

The MVP is accepted when:

- A Julia package with `Project.toml`, `src/BESSDispatch.jl`, and `test/runtests.jl` exists.
- A sample `arbitrage_mvp` case can be loaded from YAML and CSV.
- The model solves with HiGHS.
- The model produces the required output files.
- The Python Plotly script creates an HTML report from a run folder.
- Input validation catches invalid durations, missing prices, invalid efficiencies, invalid SOC bounds, and invalid terminal settings before model construction.
- With constant prices and positive degradation cost, the model does not cycle unnecessarily.
- With a low-high-low price shape, the model charges during low-price periods and discharges during high-price periods when physically feasible.
- With `terminal_condition = equal_initial`, final energy equals initial energy within numerical tolerance.
- With `prevent_simultaneous_charge_discharge = true`, no period has both positive charge and positive discharge above tolerance.
- With variable `duration_hours`, energy changes respect `MW * hours = MWh`.

## 12. Initial Backlog

1. Create Julia package skeleton.
2. Define core structs in `src/types.jl`.
3. Implement YAML and CSV loaders.
4. Implement input validation.
5. Implement base JuMP model builder.
6. Implement general BESS constraints.
7. Implement arbitrage objective.
8. Implement configurable terminal condition.
9. Implement linear delta-SOC degradation formulation.
10. Implement result writer.
11. Add sample `data/cases/arbitrage_mvp` input files.
12. Add Julia tests for acceptance criteria.
13. Add Python Plotly reporting script.
14. Add README instructions for running the MVP case.

## 13. Future Extensions

Potential future work:

- Excel loader.
- Database loader.
- Rolling-horizon mode.
- Multiple BESS assets.
- Local generation and local demand.
- Peak shaving.
- Contracted injection/withdrawal limits.
- Ancillary service co-optimization.
- More advanced degradation models.
- Terminal value estimation for rolling horizon.
- Solver abstraction for Gurobi, CPLEX, Xpress, or other solvers.
