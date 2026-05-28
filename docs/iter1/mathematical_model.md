# Mathematical Model: Single-BESS Price-Taker Dispatch

## 1. Purpose

This document defines the initial mathematical formulation for the BESS dispatch optimization model. It must be reviewed before implementing the Julia/JuMP model.

The MVP is a deterministic, single-BESS, price-taker arbitrage model with:

- Exogenous energy prices.
- Period-indexed duration.
- Charge and discharge efficiency.
- Energy and power limits.
- Binary anti-simultaneity between charge and discharge.
- Optional terminal energy condition.
- Linear degradation cost based on absolute changes in stored energy.

## 2. Sets And Indices

Let:

```text
T = ordered set of periods
t = period index, t in T
N = number of periods
```

The first period is `t = 1`; the last period is `t = N`.

## 3. Time Convention

Each input timestamp represents the start of period `t`.

Each period has a duration:

```text
duration_hours[t] > 0
```

The decision variables `p_charge_mw[t]` and `p_discharge_mw[t]` represent average power during period `t`.

Both power variables are measured on the grid side of the BESS connection. Charging efficiency maps grid import into stored energy, and discharge efficiency maps stored energy withdrawal into grid export.

The state variable `energy_mwh[t]` represents stored energy at the end of period `t`.

For `t = 1`, the energy balance starts from `initial_energy_mwh`.

## 4. Parameters

### 4.1 Time Series Parameters

```text
price_usd_per_mwh[t]     energy price during period t
duration_hours[t]        duration of period t in hours
```

### 4.2 BESS Parameters

```text
charge_power_max_mw                         maximum charging power
discharge_power_max_mw                      maximum discharging power
energy_min_mwh                              minimum allowed stored energy
energy_max_mwh                              maximum allowed stored energy
initial_energy_mwh                          stored energy before period 1
charge_efficiency                           charging efficiency
discharge_efficiency                        discharging efficiency
degradation_cost_per_mwh_delta_soc          linear degradation cost coefficient
```

Parameter domains:

```text
charge_power_max_mw >= 0
discharge_power_max_mw >= 0
energy_min_mwh < energy_max_mwh
energy_min_mwh <= initial_energy_mwh <= energy_max_mwh
0 < charge_efficiency <= 1
0 < discharge_efficiency <= 1
degradation_cost_per_mwh_delta_soc >= 0
duration_hours[t] > 0
```

### 4.3 Terminal Parameters

The terminal condition mode is one of:

```text
none
equal_initial
min_terminal
```

If the mode is `min_terminal`, the additional constraint-configuration parameter is:

```text
terminal_energy_min_mwh
```

with:

```text
energy_min_mwh <= terminal_energy_min_mwh <= energy_max_mwh
```

## 5. Decision Variables

For the default MVP formulation, each period `t` has:

```text
p_charge_mw[t] >= 0
p_discharge_mw[t] >= 0
energy_mwh[t]
delta_soc_abs_mwh[t] >= 0
is_charging[t] in {0, 1}
```

Interpretation:

- `p_charge_mw[t]`: charging power during period `t`.
- `p_discharge_mw[t]`: discharging power during period `t`.
- `energy_mwh[t]`: stored energy at the end of period `t`.
- `delta_soc_abs_mwh[t]`: absolute change in stored energy during period `t`.
- `is_charging[t]`: binary variable used to prevent simultaneous charge and discharge.

If `prevent_simultaneous_charge_discharge = false`, `is_charging[t]` is not required as a decision variable. If `degradation_linear_delta_soc = false`, `delta_soc_abs_mwh[t]` is not required for optimization and should be reported as zero.

## 6. Derived Output Variables

The following values do not need to be JuMP decision variables unless convenient for reporting:

```text
net_discharge_mw[t] = p_discharge_mw[t] - p_charge_mw[t]
```

Positive `net_discharge_mw[t]` means net discharge/export to grid.

Negative `net_discharge_mw[t]` means net charge/import from grid.

Period degradation cost:

```text
degradation_cost_usd[t] =
    degradation_cost_per_mwh_delta_soc * delta_soc_abs_mwh[t]
```

Period market value before degradation:

```text
market_value_usd[t] =
    price_usd_per_mwh[t]
    * (p_discharge_mw[t] - p_charge_mw[t])
    * duration_hours[t]
```

Period profit after degradation:

```text
period_profit_usd[t] =
    market_value_usd[t] - degradation_cost_usd[t]
```

## 7. Objective Function

Maximize total profit:

```text
maximize
    sum over t in T (
        price_usd_per_mwh[t]
        * (p_discharge_mw[t] - p_charge_mw[t])
        * duration_hours[t]
        - degradation_cost_per_mwh_delta_soc * delta_soc_abs_mwh[t]
    )
```

No terminal value is included in the MVP objective.

## 8. Constraints

### 8.1 Energy Balance

For the first period:

```text
energy_mwh[1] =
    initial_energy_mwh
    + charge_efficiency * p_charge_mw[1] * duration_hours[1]
    - (p_discharge_mw[1] / discharge_efficiency) * duration_hours[1]
```

For periods `t = 2, ..., N`:

```text
energy_mwh[t] =
    energy_mwh[t - 1]
    + charge_efficiency * p_charge_mw[t] * duration_hours[t]
    - (p_discharge_mw[t] / discharge_efficiency) * duration_hours[t]
```

This convention means `energy_mwh[t]` is the end-of-period energy.

### 8.2 Energy Bounds

For all `t`:

```text
energy_min_mwh <= energy_mwh[t] <= energy_max_mwh
```

### 8.3 Power Bounds

For all `t`:

```text
0 <= p_charge_mw[t] <= charge_power_max_mw
0 <= p_discharge_mw[t] <= discharge_power_max_mw
```

### 8.4 Prevent Simultaneous Charge And Discharge

When `prevent_simultaneous_charge_discharge = true`, for all `t`:

```text
p_charge_mw[t] <= charge_power_max_mw * is_charging[t]
p_discharge_mw[t] <= discharge_power_max_mw * (1 - is_charging[t])
is_charging[t] in {0, 1}
```

When this constraint is disabled, `is_charging[t]` is not required and the model can be solved as an LP if no other binary variables are active.

### 8.5 Linear Delta-SOC Degradation

When `degradation_linear_delta_soc = true`, define the absolute energy movement for each period.

For the first period:

```text
delta_soc_abs_mwh[1] >= energy_mwh[1] - initial_energy_mwh
delta_soc_abs_mwh[1] >= initial_energy_mwh - energy_mwh[1]
```

For periods `t = 2, ..., N`:

```text
delta_soc_abs_mwh[t] >= energy_mwh[t] - energy_mwh[t - 1]
delta_soc_abs_mwh[t] >= energy_mwh[t - 1] - energy_mwh[t]
```

Because `delta_soc_abs_mwh[t]` has a nonnegative cost in a maximization objective, the optimizer will set it equal to the absolute value at optimum.

If this degradation constraint is disabled, the objective must omit the degradation term and `delta_soc_abs_mwh[t]` should be set to zero for reporting consistency.

### 8.6 Terminal Energy Condition

If `terminal_condition = none`:

```text
no terminal energy constraint
```

If `terminal_condition = equal_initial`:

```text
energy_mwh[N] = initial_energy_mwh
```

If `terminal_condition = min_terminal`:

```text
energy_mwh[N] >= terminal_energy_min_mwh
```

Default MVP mode:

```text
terminal_condition = equal_initial
```

## 9. Complete MVP Formulation

The default MVP uses:

- Energy balance.
- Energy bounds.
- Power bounds.
- Anti-simultaneous charge/discharge binary constraints.
- Linear delta-SOC degradation.
- Terminal energy equal to initial energy.

In compact form:

```text
maximize
    sum over t in T (
        price_usd_per_mwh[t]
        * (p_discharge_mw[t] - p_charge_mw[t])
        * duration_hours[t]
        - degradation_cost_per_mwh_delta_soc * delta_soc_abs_mwh[t]
    )

subject to
    energy_mwh[1] =
        initial_energy_mwh
        + charge_efficiency * p_charge_mw[1] * duration_hours[1]
        - (p_discharge_mw[1] / discharge_efficiency) * duration_hours[1]

    energy_mwh[t] =
        energy_mwh[t - 1]
        + charge_efficiency * p_charge_mw[t] * duration_hours[t]
        - (p_discharge_mw[t] / discharge_efficiency) * duration_hours[t]
        for t = 2, ..., N

    energy_min_mwh <= energy_mwh[t] <= energy_max_mwh
        for all t

    0 <= p_charge_mw[t] <= charge_power_max_mw
        for all t

    0 <= p_discharge_mw[t] <= discharge_power_max_mw
        for all t

    p_charge_mw[t] <= charge_power_max_mw * is_charging[t]
        for all t

    p_discharge_mw[t] <= discharge_power_max_mw * (1 - is_charging[t])
        for all t

    delta_soc_abs_mwh[1] >= energy_mwh[1] - initial_energy_mwh
    delta_soc_abs_mwh[1] >= initial_energy_mwh - energy_mwh[1]

    delta_soc_abs_mwh[t] >= energy_mwh[t] - energy_mwh[t - 1]
        for t = 2, ..., N

    delta_soc_abs_mwh[t] >= energy_mwh[t - 1] - energy_mwh[t]
        for t = 2, ..., N

    energy_mwh[N] = initial_energy_mwh

    p_charge_mw[t] >= 0
    p_discharge_mw[t] >= 0
    delta_soc_abs_mwh[t] >= 0
    is_charging[t] in {0, 1}
        for all t
```

## 10. Numerical Tolerances

Acceptance tests should use tolerances rather than exact equality for solver outputs.

Recommended tolerances:

```text
power_tolerance_mw = 1e-6
energy_tolerance_mwh = 1e-6
objective_tolerance_usd = 1e-5
```

For anti-simultaneity validation:

```text
not (
    p_charge_mw[t] > power_tolerance_mw
    and p_discharge_mw[t] > power_tolerance_mw
)
```

For terminal equality:

```text
abs(energy_mwh[N] - initial_energy_mwh) <= energy_tolerance_mwh
```

## 11. Expected Behavior Checks

### 11.1 Constant Price With Positive Degradation

If prices are constant and degradation cost is positive, the model should avoid unnecessary cycling.

Expected behavior:

```text
p_charge_mw[t] = 0
p_discharge_mw[t] = 0
energy_mwh[t] = initial_energy_mwh
```

subject to solver tolerances and terminal condition.

### 11.2 Low-High-Low Price Shape

If the price series contains a feasible low-price period followed by a high-price period, the model should charge when prices are low and discharge when prices are high, considering efficiency losses, energy limits, power limits, duration, degradation cost, and terminal condition.

### 11.3 Variable Duration

For each period, the energy change must respect:

```text
MW * hours = MWh
```

Example:

```text
p_charge_mw[t] = 10
duration_hours[t] = 0.5
charge_efficiency = 0.95
```

implies charging increases stored energy by:

```text
10 * 0.5 * 0.95 = 4.75 MWh
```

before considering any simultaneous discharge, which is prevented in the default MVP.

## 12. Future Model Extensions

Future formulations can add:

- Multiple assets with BESS index `b`.
- Local generation and demand.
- Import/export limits.
- Contract limits.
- Ancillary service capacity variables.
- Rolling-horizon terminal value.
- Throughput-based degradation.
- Cycle-depth degradation.
- Calendar degradation.
- Network constraints.

These extensions should be added in case-specific modules unless they become reusable general BESS physics.
