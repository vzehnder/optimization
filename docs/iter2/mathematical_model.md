# Mathematical Model: One-Bus Hybrid System Dispatch

## 1. Purpose

This document defines the iteration 2 mathematical formulation for hybrid BESS system dispatch. It extends the single-BESS MVP into a one-bus system model with connected assets while preserving the approved battery physics from iteration 1.

The model is deterministic and price-taking. It supports:

- A single logical bus or point of common coupling.
- One or more battery assets by ID.
- One or more renewable assets with exogenous available power.
- One or more grid connection assets with import and export variables.
- Optional local load assets with exogenous demand.
- Period-indexed duration.
- Optional binary anti-simultaneity for battery charge/discharge.
- Optional binary anti-simultaneity for grid import/export.
- Optional terminal energy conditions per battery.
- Optional linear battery degradation cost based on absolute SOC movement.
- Optional renewable curtailment penalty.

The formulation does not model physical network flows. Graph edges are only a validation mechanism for connecting assets to the single bus.

## 2. Sets And Indices

Let:

```text
T = ordered set of periods
B = set of battery assets
R = set of renewable assets
G = set of grid connection assets
L = set of local load assets

t in T
b in B
r in R
g in G
l in L
N = number of periods
```

The first period is `t = 1`; the last period is `t = N`.

## 3. Time Convention

Each input timestamp represents the start of period `t`.

Each period has duration:

```text
duration_hours[t] > 0
```

Power variables are average MW during the period. Energy changes use:

```text
MW * hours = MWh
```

Battery charge and discharge variables are measured on the bus side of the battery connection, matching the iteration 1 convention.

Battery stored energy:

```text
energy_mwh[b,t]
```

represents stored energy in battery `b` at the end of period `t`.

## 4. Parameters

### 4.1 Common Time Series Parameters

```text
price_usd_per_mwh[t]     grid energy price during period t
duration_hours[t]        duration of period t in hours
```

The base iteration 2 model uses one price per period for both import and export.

### 4.2 Battery Parameters

For each battery `b`:

```text
charge_power_max_mw[b]
discharge_power_max_mw[b]
energy_min_mwh[b]
energy_max_mwh[b]
initial_energy_mwh[b]
charge_efficiency[b]
discharge_efficiency[b]
degradation_cost_per_mwh_delta_soc[b]
terminal_condition[b]
terminal_energy_min_mwh[b]
prevent_simultaneous_charge_discharge[b]
degradation_linear_delta_soc[b]
```

Domains:

```text
charge_power_max_mw[b] >= 0
discharge_power_max_mw[b] >= 0
energy_min_mwh[b] < energy_max_mwh[b]
energy_min_mwh[b] <= initial_energy_mwh[b] <= energy_max_mwh[b]
0 < charge_efficiency[b] <= 1
0 < discharge_efficiency[b] <= 1
degradation_cost_per_mwh_delta_soc[b] >= 0
terminal_condition[b] in {none, equal_initial, min_terminal}
```

If `terminal_condition[b] = min_terminal`:

```text
energy_min_mwh[b] <= terminal_energy_min_mwh[b] <= energy_max_mwh[b]
```

### 4.3 Renewable Parameters

For each renewable `r`:

```text
renewable_available_power_mw[r,t] >= 0
curtailment_penalty_usd_per_mwh[r] >= 0
```

The curtailment penalty defaults to zero when omitted.

### 4.4 Grid Parameters

For each grid connection `g`:

```text
import_power_max_mw[g] >= 0 or omitted
export_power_max_mw[g] >= 0 or omitted
prevent_simultaneous_grid_import_export[g]
```

If import or export limits are omitted, the implementation must still provide finite operational bounds for any binary anti-simultaneity formulation. These bounds may be derived from connected asset limits and time-series maxima.

### 4.5 Load Parameters

For each load `l`:

```text
load_demand_mw[l,t] >= 0
```

Load is fixed and must be served by the bus balance unless the full model is infeasible.

## 5. Decision Variables

### 5.1 Battery Variables

For each battery `b` and period `t`:

```text
p_battery_charge_mw[b,t] >= 0
p_battery_discharge_mw[b,t] >= 0
energy_mwh[b,t]
delta_soc_abs_mwh[b,t] >= 0
is_battery_charging[b,t] in {0, 1}
```

`delta_soc_abs_mwh` is required only when linear delta-SOC degradation is enabled for the battery. `is_battery_charging` is required only when battery anti-simultaneity is enabled.

### 5.2 Renewable Variables

For each renewable `r` and period `t`:

```text
p_renewable_used_mw[r,t] >= 0
p_renewable_curtailed_mw[r,t] >= 0
```

### 5.3 Grid Variables

For each grid connection `g` and period `t`:

```text
p_grid_import_mw[g,t] >= 0
p_grid_export_mw[g,t] >= 0
is_grid_importing[g,t] in {0, 1}
```

`is_grid_importing` is required only when grid import/export anti-simultaneity is enabled.

## 6. Derived Output Variables

System net export:

```text
net_grid_export_mw[t] =
    sum over g in G p_grid_export_mw[g,t]
    - sum over g in G p_grid_import_mw[g,t]
```

Total renewable used and curtailed:

```text
total_renewable_used_mw[t] =
    sum over r in R p_renewable_used_mw[r,t]

total_renewable_curtailed_mw[t] =
    sum over r in R p_renewable_curtailed_mw[r,t]
```

Total load:

```text
total_load_mw[t] =
    sum over l in L load_demand_mw[l,t]
```

Battery degradation cost:

```text
battery_degradation_cost_usd[b,t] =
    degradation_cost_per_mwh_delta_soc[b] * delta_soc_abs_mwh[b,t]
```

Renewable curtailment penalty:

```text
curtailment_penalty_usd[r,t] =
    curtailment_penalty_usd_per_mwh[r]
    * p_renewable_curtailed_mw[r,t]
    * duration_hours[t]
```

Market value:

```text
market_value_usd[t] =
    price_usd_per_mwh[t]
    * (
        sum over g in G p_grid_export_mw[g,t]
        - sum over g in G p_grid_import_mw[g,t]
      )
    * duration_hours[t]
```

Period profit:

```text
period_profit_usd[t] =
    market_value_usd[t]
    - sum over b in B battery_degradation_cost_usd[b,t]
    - sum over r in R curtailment_penalty_usd[r,t]
```

## 7. Objective Function

Maximize total system profit:

```text
maximize
    sum over t in T (
        price_usd_per_mwh[t]
        * (
            sum over g in G p_grid_export_mw[g,t]
            - sum over g in G p_grid_import_mw[g,t]
          )
        * duration_hours[t]
    )
    - sum over b in B, t in T (
        degradation_cost_per_mwh_delta_soc[b]
        * delta_soc_abs_mwh[b,t]
    )
    - sum over r in R, t in T (
        curtailment_penalty_usd_per_mwh[r]
        * p_renewable_curtailed_mw[r,t]
        * duration_hours[t]
    )
```

If degradation is disabled for a battery, omit its degradation term and report zero degradation movement for that battery.

If curtailment penalty is omitted for a renewable asset, use zero.

No terminal salvage value is included.

## 8. Constraints

### 8.1 Common Bus Balance

For every period `t`:

```text
sum over g in G p_grid_import_mw[g,t]
+ sum over r in R p_renewable_used_mw[r,t]
+ sum over b in B p_battery_discharge_mw[b,t]
=
sum over g in G p_grid_export_mw[g,t]
+ sum over b in B p_battery_charge_mw[b,t]
+ sum over l in L load_demand_mw[l,t]
```

This convention keeps all flow variables nonnegative.

### 8.2 Renewable Availability

For every renewable `r` and period `t`:

```text
p_renewable_used_mw[r,t]
+ p_renewable_curtailed_mw[r,t]
= renewable_available_power_mw[r,t]
```

### 8.3 Battery Energy Balance

For each battery `b`, first period:

```text
energy_mwh[b,1] =
    initial_energy_mwh[b]
    + charge_efficiency[b]
      * p_battery_charge_mw[b,1]
      * duration_hours[1]
    - (
        p_battery_discharge_mw[b,1]
        / discharge_efficiency[b]
      )
      * duration_hours[1]
```

For each battery `b` and periods `t = 2, ..., N`:

```text
energy_mwh[b,t] =
    energy_mwh[b,t - 1]
    + charge_efficiency[b]
      * p_battery_charge_mw[b,t]
      * duration_hours[t]
    - (
        p_battery_discharge_mw[b,t]
        / discharge_efficiency[b]
      )
      * duration_hours[t]
```

### 8.4 Battery Energy Bounds

For every battery `b` and period `t`:

```text
energy_min_mwh[b] <= energy_mwh[b,t] <= energy_max_mwh[b]
```

### 8.5 Battery Power Bounds

For every battery `b` and period `t`:

```text
0 <= p_battery_charge_mw[b,t] <= charge_power_max_mw[b]
0 <= p_battery_discharge_mw[b,t] <= discharge_power_max_mw[b]
```

### 8.6 Battery Charge/Discharge Anti-Simultaneity

When enabled for battery `b`, for every period `t`:

```text
p_battery_charge_mw[b,t]
    <= charge_power_max_mw[b] * is_battery_charging[b,t]

p_battery_discharge_mw[b,t]
    <= discharge_power_max_mw[b] * (1 - is_battery_charging[b,t])

is_battery_charging[b,t] in {0, 1}
```

When disabled, `is_battery_charging[b,t]` is not required.

### 8.7 Battery Linear Delta-SOC Degradation

When enabled for battery `b`, first period:

```text
delta_soc_abs_mwh[b,1] >= energy_mwh[b,1] - initial_energy_mwh[b]
delta_soc_abs_mwh[b,1] >= initial_energy_mwh[b] - energy_mwh[b,1]
```

For periods `t = 2, ..., N`:

```text
delta_soc_abs_mwh[b,t] >= energy_mwh[b,t] - energy_mwh[b,t - 1]
delta_soc_abs_mwh[b,t] >= energy_mwh[b,t - 1] - energy_mwh[b,t]
```

Because the objective penalizes `delta_soc_abs_mwh`, the optimizer sets it equal to the absolute SOC movement at optimum.

When disabled, omit these variables and report zero degradation movement for that battery.

### 8.8 Battery Terminal Energy Condition

For each battery `b`:

If `terminal_condition[b] = none`:

```text
no terminal energy constraint
```

If `terminal_condition[b] = equal_initial`:

```text
energy_mwh[b,N] = initial_energy_mwh[b]
```

If `terminal_condition[b] = min_terminal`:

```text
energy_mwh[b,N] >= terminal_energy_min_mwh[b]
```

### 8.9 Grid Import And Export Bounds

If a grid import limit is configured:

```text
p_grid_import_mw[g,t] <= import_power_max_mw[g]
```

If a grid export limit is configured:

```text
p_grid_export_mw[g,t] <= export_power_max_mw[g]
```

If no explicit limit is configured, the implementation may still impose finite derived bounds needed for numerical stability and binary anti-simultaneity.

### 8.10 Grid Import/Export Anti-Simultaneity

When enabled for grid connection `g`, for every period `t`:

```text
p_grid_import_mw[g,t]
    <= grid_import_big_m_mw[g,t] * is_grid_importing[g,t]

p_grid_export_mw[g,t]
    <= grid_export_big_m_mw[g,t] * (1 - is_grid_importing[g,t])

is_grid_importing[g,t] in {0, 1}
```

The `grid_import_big_m_mw` and `grid_export_big_m_mw` values must be finite. They may come from explicit grid limits or conservative derived bounds.

When disabled, the implementation must still avoid unbounded import/export cycles through finite limits or validation.

## 9. Complete Default Formulation

The default iteration 2 model uses:

- One-bus balance.
- Renewable availability balance.
- Battery energy balance.
- Battery energy bounds.
- Battery power bounds.
- Battery charge/discharge anti-simultaneity.
- Battery linear delta-SOC degradation.
- Battery terminal condition equal to initial energy unless configured otherwise.
- Grid import/export variables.
- Grid import/export anti-simultaneity.
- Net energy margin objective.

## 10. Validation Requirements

Before model construction, validation must reject:

- Missing or unsupported schema version.
- Empty time series.
- Nonpositive period duration.
- Nonfinite price values.
- Duplicate or unsorted timestamps.
- Unknown node types.
- Duplicate node IDs.
- Missing bus node.
- Multiple bus nodes.
- Edges that reference missing node IDs.
- Asset nodes not connected to the single bus.
- Negative renewable availability.
- Missing renewable availability for a renewable asset.
- Negative load demand.
- Missing load demand for a load asset.
- Invalid battery bounds, efficiencies, terminal settings, or degradation cost.
- Negative grid import or export limits.
- Grid configurations that can make the model unbounded.

Invalid inputs must fail before JuMP model construction with explicit error messages.

## 11. Numerical Tolerances

Acceptance tests should use tolerances rather than exact equality for solver outputs.

Recommended tolerances:

```text
power_tolerance_mw = 1e-6
energy_tolerance_mwh = 1e-6
objective_tolerance_usd = 1e-5
balance_tolerance_mw = 1e-6
```

For battery anti-simultaneity:

```text
not (
    p_battery_charge_mw[b,t] > power_tolerance_mw
    and p_battery_discharge_mw[b,t] > power_tolerance_mw
)
```

For grid anti-simultaneity:

```text
not (
    p_grid_import_mw[g,t] > power_tolerance_mw
    and p_grid_export_mw[g,t] > power_tolerance_mw
)
```

For bus balance:

```text
abs(total_supply_mw[t] - total_consumption_mw[t])
    <= balance_tolerance_mw
```

## 12. Expected Behavior Checks

### 12.1 Renewable Plus Battery Plus Grid

With low-price renewable availability before a high-price period, the model should charge the battery when economical and export later, respecting battery limits, efficiency, terminal condition, and grid limits.

### 12.2 Renewable Curtailment

If renewable availability exceeds what can be consumed, stored, or exported, the model should curtail the excess and report it explicitly.

### 12.3 Load Service

With local load, the bus balance must serve load from some combination of grid import, renewable used, or battery discharge.

### 12.4 Grid Anti-Simultaneity

When grid anti-simultaneity is enabled, no period should import and export above tolerance at the same grid connection.

### 12.5 Battery Regression

For a system case equivalent to the iteration 1 single-BESS arbitrage problem, battery dispatch behavior should match the approved sign conventions and energy accounting.

## 13. Future Model Extensions

Future iterations can add:

- Multiple physical buses.
- Network flows and line limits.
- Separate import and export prices.
- Power purchase agreements or contract limits.
- Ancillary services.
- Rolling-horizon terminal value.
- Forecast uncertainty.
- Advanced degradation models.
- Demand charges and tariff engines.
- Production Python API service.
