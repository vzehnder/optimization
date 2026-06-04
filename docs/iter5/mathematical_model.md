# Mathematical Model: One-Bus Hybrid System Dispatch With Simple Reservoir Hydropower

## 1. Purpose

This document defines the Iteration 5 mathematical formulation for simple
reservoir hydropower inside the one-bus hybrid dispatch model.

It extends the Iteration 2 one-bus formulation and Iteration 4 separate import
and export price behavior with independent hydro assets. It preserves the
existing BESS, renewable, grid, load, price, validation, CLI, and output
contracts while adding `bess_system_dispatch.v2` hydropower support.

The hydro model is intentionally limited:

- One electrical bus or PCC.
- One hydro node represents one reservoir and one associated plant.
- Multiple hydro nodes are allowed, but they are independent.
- No hydraulic cascades.
- No hydraulic networks.
- No travel-time delays.
- No generation dependence on reservoir elevation in Iteration 5.
- No pumped storage.
- No hydro electrical curtailment.

## 2. Sets And Indices

Let:

```text
T = ordered set of periods
B = set of battery assets
R = set of renewable assets
G = set of grid connection assets
L = set of local load assets
H = set of hydro assets

t in T
b in B
r in R
g in G
l in L
h in H
N = number of periods
```

The first period is `t = 1`; the last period is `t = N`.

## 3. Time And Unit Convention

Each input timestamp represents the start of period `t`.

Each period has:

```text
duration_hours[t] > 0
```

Electrical power is measured in `MW`.

Battery energy is measured in `MWh`.

Reservoir storage is measured in `hm3`.

Hydro operational flows are measured in `m3/s`.

Reservoir elevation is measured in `masl`.

Energy price is measured in `USD/MWh`.

Spill penalty and terminal water value are measured in `USD/hm3`.

The conversion from flow to volume over a period is:

```text
flow_volume_hm3(flow_m3s, t) =
    flow_m3s * duration_hours[t] * 3600 / 1_000_000
```

Define:

```text
k_hm3_per_m3s_hour = 3600 / 1_000_000
```

Then:

```text
flow_volume_hm3(flow_m3s, t) =
    flow_m3s * duration_hours[t] * k_hm3_per_m3s_hour
```

## 4. Existing One-Bus Components

The Iteration 5 model preserves the Iteration 2/4 components:

- Battery charge/discharge, SOC, degradation, terminal condition, and optional
  anti-simultaneity.
- Renewable used and curtailed generation with optional curtailment penalty.
- Grid import/export variables, limits, and optional anti-simultaneity.
- Local load demand.
- Legacy single price or separate import/export prices.

The details of those components remain governed by the earlier one-bus model
documents unless explicitly extended here.

## 5. Hydro Parameters

For each hydro asset `h`:

```text
storage_min_hm3[h]
storage_max_hm3[h]
initial_storage_hm3[h]
terminal_condition[h] in {none, equal_initial, min_terminal}
terminal_storage_min_hm3[h]
terminal_water_value_usd_per_hm3[h] >= 0
spill_penalty_usd_per_hm3[h] >= 0
minimum_release_m3s[h] >= 0
generation_mode[h] in {linear, piecewise_linear}
power_max_mw[h] >= 0 or omitted
turbine_flow_min_m3s[h] >= 0 or omitted
turbine_flow_max_m3s[h] >= 0 or omitted
```

For each period:

```text
hydro_inflow_m3s[h,t] >= 0
```

### 5.1 Linear Generation Parameters

When:

```text
generation_mode[h] = linear
```

The required parameter is:

```text
power_per_flow_mw_per_m3s[h] >= 0
```

The required operating upper bound is:

```text
turbine_flow_max_m3s[h] >= 0
```

`turbine_flow_min_m3s[h]` remains optional.

### 5.2 Piecewise Generation Parameters

When:

```text
generation_mode[h] = piecewise_linear
```

The required generation curve is a list of breakpoints:

```text
(flow_breakpoint_m3s[h,k], power_breakpoint_mw[h,k])
```

Validation requirements:

- At least two breakpoints.
- `flow_breakpoint_m3s` strictly increasing.
- `flow_breakpoint_m3s >= 0`.
- `power_breakpoint_mw` finite and nonnegative.
- Power breakpoints may be nonconvex and nonmonotone.
- If `turbine_flow_min_m3s` is configured, it must lie within the curve domain.
- If `turbine_flow_max_m3s` is configured, it must lie within the curve domain.
- If no explicit turbine flow bounds are configured, the curve domain defines
  the turbine flow bounds.

The curve is implemented using:

```text
PiecewiseLinearOpt.piecewiselinear
```

with the package default method.

### 5.3 Reservoir Curve Parameters

Every hydro asset requires a storage-elevation curve:

```text
(storage_breakpoint_hm3[h,k], elevation_breakpoint_masl[h,k])
```

Validation requirements:

- At least two breakpoints.
- `storage_breakpoint_hm3` strictly increasing.
- `elevation_breakpoint_masl` finite.
- `elevation_breakpoint_masl` nondecreasing.
- `storage_min_hm3`, `storage_max_hm3`, `initial_storage_hm3`, and any terminal
  storage parameters must lie within the storage breakpoint domain.

The curve is implemented using:

```text
PiecewiseLinearOpt.piecewiselinear
```

The resulting elevation is reportable. It does not affect hydro generation in
Iteration 5.

## 6. Hydro Decision Variables

For each hydro asset `h` and period `t`:

```text
hydro_turbine_flow_m3s[h,t] >= 0
hydro_spill_flow_m3s[h,t] >= 0
hydro_power_mw[h,t] >= 0
hydro_storage_hm3[h,t]
hydro_reservoir_elevation_masl[h,t]
```

Derived output values:

```text
hydro_inflow_volume_hm3[h,t] =
    hydro_inflow_m3s[h,t] * duration_hours[t] * k_hm3_per_m3s_hour

hydro_turbine_volume_hm3[h,t] =
    hydro_turbine_flow_m3s[h,t] * duration_hours[t] * k_hm3_per_m3s_hour

hydro_spill_volume_hm3[h,t] =
    hydro_spill_flow_m3s[h,t] * duration_hours[t] * k_hm3_per_m3s_hour

hydro_spill_penalty_usd[h,t] =
    spill_penalty_usd_per_hm3[h] * hydro_spill_volume_hm3[h,t]
```

Terminal water value:

```text
hydro_terminal_water_value_usd[h] =
    terminal_water_value_usd_per_hm3[h] * hydro_storage_hm3[h,N]
```

## 7. Hydro Constraints

### 7.1 Reservoir Storage Balance

For the first period:

```text
hydro_storage_hm3[h,1] =
    initial_storage_hm3[h]
    + hydro_inflow_m3s[h,1] * duration_hours[1] * k_hm3_per_m3s_hour
    - hydro_turbine_flow_m3s[h,1] * duration_hours[1] * k_hm3_per_m3s_hour
    - hydro_spill_flow_m3s[h,1] * duration_hours[1] * k_hm3_per_m3s_hour
```

For periods `t = 2, ..., N`:

```text
hydro_storage_hm3[h,t] =
    hydro_storage_hm3[h,t - 1]
    + hydro_inflow_m3s[h,t] * duration_hours[t] * k_hm3_per_m3s_hour
    - hydro_turbine_flow_m3s[h,t] * duration_hours[t] * k_hm3_per_m3s_hour
    - hydro_spill_flow_m3s[h,t] * duration_hours[t] * k_hm3_per_m3s_hour
```

### 7.2 Reservoir Storage Bounds

For all hydro assets and periods:

```text
storage_min_hm3[h] <= hydro_storage_hm3[h,t] <= storage_max_hm3[h]
```

### 7.3 Minimum Release

For all hydro assets and periods:

```text
hydro_turbine_flow_m3s[h,t] + hydro_spill_flow_m3s[h,t]
    >= minimum_release_m3s[h]
```

If `minimum_release_m3s` is omitted, it defaults to zero.

### 7.4 Turbine Flow Bounds

If `turbine_flow_min_m3s[h]` is configured:

```text
hydro_turbine_flow_m3s[h,t] >= turbine_flow_min_m3s[h]
```

This is a simple lower bound. Iteration 5 does not include an on/off binary for
technical minimum turbine operation.

If `turbine_flow_max_m3s[h]` is configured:

```text
hydro_turbine_flow_m3s[h,t] <= turbine_flow_max_m3s[h]
```

In piecewise mode, the generation curve domain also bounds turbine flow. Any
explicit min/max bounds must lie inside that domain.

### 7.5 Linear Generation Mode

When `generation_mode[h] = linear`:

```text
hydro_power_mw[h,t] =
    power_per_flow_mw_per_m3s[h] * hydro_turbine_flow_m3s[h,t]
```

If `power_max_mw[h]` is configured:

```text
hydro_power_mw[h,t] <= power_max_mw[h]
```

### 7.6 Piecewise-Linear Generation Mode

When `generation_mode[h] = piecewise_linear`, enforce:

```text
hydro_power_mw[h,t] =
    generation_curve_h(hydro_turbine_flow_m3s[h,t])
```

where `generation_curve_h` is defined by the accepted flow-power breakpoints
and implemented with `PiecewiseLinearOpt.piecewiselinear`.

If `power_max_mw[h]` is configured:

```text
hydro_power_mw[h,t] <= power_max_mw[h]
```

### 7.7 Reservoir Elevation Curve

For every hydro asset and period:

```text
hydro_reservoir_elevation_masl[h,t] =
    reservoir_curve_h(hydro_storage_hm3[h,t])
```

where `reservoir_curve_h` is defined by storage-elevation breakpoints and
implemented with `PiecewiseLinearOpt.piecewiselinear`.

This variable is used for reporting and validation. It does not enter hydro
power generation in Iteration 5.

### 7.8 Terminal Storage Condition

If:

```text
terminal_condition[h] = none
```

there is no terminal storage constraint.

If:

```text
terminal_condition[h] = equal_initial
```

then:

```text
hydro_storage_hm3[h,N] = initial_storage_hm3[h]
```

If:

```text
terminal_condition[h] = min_terminal
```

then:

```text
hydro_storage_hm3[h,N] >= terminal_storage_min_hm3[h]
```

## 8. One-Bus Balance With Hydro

For every period:

```text
sum over g in G p_grid_import_mw[g,t]
+ sum over r in R p_renewable_used_mw[r,t]
+ sum over b in B p_battery_discharge_mw[b,t]
+ sum over h in H hydro_power_mw[h,t]
=
sum over g in G p_grid_export_mw[g,t]
+ sum over b in B p_battery_charge_mw[b,t]
+ sum over l in L load_demand_mw[l,t]
```

Hydro power is supply. There is no hydro electrical curtailment variable.

## 9. Objective Function

The Iteration 5 objective maximizes:

```text
grid export revenue
- grid import cost
- battery degradation cost
- renewable curtailment penalty
- hydro spill penalty
+ terminal water value
```

In expanded form:

```text
maximize
    sum over t in T (
        sum over g in G export_price[t] * p_grid_export_mw[g,t] * duration_hours[t]
        - sum over g in G import_price[t] * p_grid_import_mw[g,t] * duration_hours[t]
    )
    - sum over b in B, t in T battery_degradation_cost_usd[b,t]
    - sum over r in R, t in T renewable_curtailment_penalty_usd[r,t]
    - sum over h in H, t in T (
        spill_penalty_usd_per_hm3[h]
        * hydro_spill_flow_m3s[h,t]
        * duration_hours[t]
        * k_hm3_per_m3s_hour
      )
    + sum over h in H (
        terminal_water_value_usd_per_hm3[h] * hydro_storage_hm3[h,N]
      )
```

For legacy single-price cases:

```text
import_price[t] = export_price[t] = price_usd_per_mwh[t]
```

For separate-price cases:

```text
import_price[t] = import_price_usd_per_mwh[t]
export_price[t] = export_price_usd_per_mwh[t]
```

## 10. Output Requirements

### 10.1 System Dispatch Output

`dispatch.csv` should include existing columns and hydro totals such as:

```text
total_hydro_power_mw
total_hydro_inflow_m3s
total_hydro_turbine_flow_m3s
total_hydro_spill_flow_m3s
total_hydro_storage_hm3
total_hydro_spill_penalty_usd
total_hydro_terminal_water_value_usd
```

`total_hydro_storage_hm3` is a sum across independent reservoirs. It is useful
as an operational aggregate, not as one physical reservoir.

### 10.2 Asset Dispatch Output

`asset_dispatch.csv` should include one row per hydro asset and period with:

```text
asset_id
asset_type = hydro
hydro_power_mw
hydro_inflow_m3s
hydro_turbine_flow_m3s
hydro_spill_flow_m3s
hydro_inflow_volume_hm3
hydro_turbine_volume_hm3
hydro_spill_volume_hm3
hydro_storage_hm3
hydro_reservoir_elevation_masl
hydro_spill_penalty_usd
hydro_terminal_water_value_usd
```

`hydro_terminal_water_value_usd` may be zero except in the final period, or
may be repeated in a clearly documented way. The summary must include the
authoritative terminal water value.

### 10.3 Summary Output

`summary.json` should include hydro KPIs per asset:

```text
total_hydro_generation_mwh
total_turbine_volume_hm3
total_spill_volume_hm3
initial_storage_hm3
final_storage_hm3
initial_reservoir_elevation_masl
final_reservoir_elevation_masl
total_spill_penalty_usd
terminal_water_value_usd
```

It should also include total hydro KPIs aggregated across hydro assets.

### 10.4 Metadata Output

`model_metadata.json` should include:

```text
schema_version = bess_system_dispatch.v2
hydro asset IDs
hydro generation modes
hydro unit conventions
active hydro constraints
PiecewiseLinearOpt usage
```

## 11. Validation Requirements

Validation must reject:

- Unsupported schema version.
- Unknown node type.
- Duplicate node IDs.
- Missing bus/PCC.
- Multiple bus/PCC nodes.
- Disconnected hydro assets.
- Missing hydro inflow for any hydro asset and period.
- Negative hydro inflow.
- Invalid storage bounds.
- Initial storage outside bounds.
- Terminal storage outside bounds.
- Invalid terminal condition.
- Negative spill penalty.
- Negative terminal water value.
- Negative minimum release.
- Invalid generation mode.
- Linear mode without required coefficient or max turbine flow.
- Negative linear generation coefficient.
- Invalid turbine flow min/max.
- Piecewise generation mode without at least two breakpoints.
- Piecewise generation flow breakpoints that are not strictly increasing.
- Piecewise generation flow breakpoints that are negative.
- Piecewise generation power breakpoints that are negative or nonfinite.
- Piecewise turbine flow bounds outside the curve domain.
- Missing reservoir curve.
- Reservoir curve with fewer than two breakpoints.
- Reservoir storage breakpoints that are not strictly increasing.
- Reservoir elevation breakpoints that are nonfinite or decreasing.
- Storage bounds outside reservoir curve domain.
- Configurations that make the model unbounded.

Invalid inputs must fail before JuMP solve with explicit error messages.

## 12. Expected Behavior Checks

### 12.1 Linear Hydro Dispatch

With inflow, storage capacity, positive export price, and linear generation, the
model should turbine water when it is economical and feasible, respecting
storage bounds, release constraints, spill penalty, power max, and terminal
water value.

### 12.2 Piecewise Hydro Dispatch

With a nonconvex or nonmonotone piecewise power-flow curve, the model should use
the accepted piecewise relation and never produce power outside the curve
domain.

### 12.3 Spill Feasibility

When inflow exceeds what can be stored or turbinated, the model should spill
water rather than become infeasible, unless other constraints make the case
infeasible.

### 12.4 Minimum Release

When `minimum_release_m3s` is configured, turbine flow plus spill flow must meet
or exceed it in every period.

### 12.5 Terminal Water Value

When terminal water value is positive and terminal condition does not fully fix
final storage, the optimizer should account for the economic value of stored
water at the end of the horizon.

### 12.6 Legacy Regression

`bess_system_dispatch.v1` cases without hydro should validate, solve, and
produce compatible outputs as before.

## 13. Future Model Extensions

Future iterations can add:

- Hydraulic travel-time delays.
- Cascaded reservoirs.
- Separate reservoir and plant nodes.
- Multiple plants per reservoir.
- Pumped storage.
- Bivariate generation curves depending on flow and reservoir elevation/head.
- Rolling-horizon water value.
- Stochastic inflows.
- More detailed ecological release constraints.
- Benchmarking and selection of PiecewiseLinearOpt formulation methods.
