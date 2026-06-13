# Simple Reservoir Hydropower Dispatch PRD

## Problem Statement

Iteration 4 turned the private analyst app into a practical structured modeling
workflow. An analyst can create one-bus hybrid cases from forms, CSV/XLSX time
series, generated `system_case` previews, Julia validation, immutable scenario
versions, manual runs, auditable artifacts, result tables, and basic charts.

The remaining modeling gap against the final product objective is hydropower.
The application still cannot represent a reservoir-based hydro asset, even
though the final one-bus model must support simple regulated hydropower beside
PCC/grid, BESS, solar, wind-like renewables, and local load.

Iteration 5 must add hydropower without expanding into a general hydraulic
network simulator. The system should model an independent simple reservoir with
an associated plant, no cascades, no hydraulic networks, no travel-time delays,
and no physical multi-bus electrical network. The analyst should be able to
build the hydro case from the structured editor and run it through the same
auditable flow established in Iterations 3 and 4.

The optimizer contract also needs a clear version step. Iteration 4 generated
`bess_system_dispatch.v1` cases. Hydropower adds a new node type, reservoir
curves, generation curves, water balance, spill penalties, minimum release, and
terminal water value. Those changes should be represented as
`bess_system_dispatch.v2`, while legacy `v1` cases remain valid and executable.

## Solution

Build a complete Iteration 5 hydropower path around a new `hydro` asset in the
one-bus dispatch model.

Each `hydro` asset represents one independent reservoir and one associated
plant. It has storage in `hm3`, operational flows in `m3/s`, inflow time series
in `m3/s`, turbine flow, spill flow, optional minimum release, optional terminal
condition, configurable spill penalty, terminal water value, a mandatory
reservoir storage-elevation curve, and a generation relation that can be either
linear or piecewise linear.

The hydro plant generation relation supports two modes:

- `linear`: power is proportional to turbine flow through
  `power_per_flow_mw_per_m3s`.
- `piecewise_linear`: power is linked to turbine flow through explicit
  `(flow_m3s, power_mw)` breakpoints using `PiecewiseLinearOpt.piecewiselinear`
  with the package default method.

The generation curve is univariate: it relates turbine flow to electrical
power. It does not depend on reservoir elevation in Iteration 5. The reservoir
curve relates storage to elevation and is used for validation/reporting, not for
generation. It is still represented inside the model through
`PiecewiseLinearOpt.piecewiselinear` so outputs can report
`reservoir_elevation_masl`.

The structured editor should generate `bess_system_dispatch.v2` cases by
default. Paste/upload JSON keeps accepting `v1` and should also accept `v2`.
The editor should let the analyst define hydro parameters and curve breakpoints
through simple structured controls, map `hydro_inflow_m3s.<hydro_id>` columns
from CSV/XLSX, preview the generated `system_case`, validate through Julia,
promote to an immutable scenario version, launch a manual run, and review hydro
results in tables and charts.

## User Stories

1. As an analyst, I want to add a hydro asset to a one-bus draft, so that I can
   model a regulated hydropower plant in the same workflow as BESS, renewable,
   grid, and load assets.
2. As an analyst, I want one hydro asset to represent one reservoir and one
   associated plant, so that simple hydro cases do not require hydraulic network
   modeling.
3. As an analyst, I want multiple hydro assets in one case, so that independent
   reservoirs connected to the same PCC can be optimized together.
4. As an analyst, I want hydro assets to connect automatically to the PCC, so
   that I do not need to edit graph edges manually.
5. As an analyst, I want hydropower to remain one-bus electrically, so that the
   existing optimizer assumptions stay understandable.
6. As an analyst, I want hydraulic cascades to remain out of scope, so that
   Iteration 5 remains focused on independent reservoirs.
7. As an analyst, I want hydraulic travel-time delays to remain out of scope, so
   that delay modeling can be designed separately later.
8. As an analyst, I want storage represented in `hm3`, so that reservoir bounds
   and initial state match practical reservoir data.
9. As an analyst, I want inflow represented in `m3/s`, so that time-series files
   can use common hydro operational units.
10. As an analyst, I want turbine flow represented in `m3/s`, so that the
    generation curve can be expressed as power versus flow.
11. As an analyst, I want spill flow represented in `m3/s`, so that overflow or
    non-turbined release is auditable.
12. As an analyst, I want the optimizer to convert flow and duration into
    internal volume movement, so that the reservoir balance is physically
    consistent.
13. As an analyst, I want to set minimum and maximum reservoir storage, so that
    the dispatch respects operating storage limits.
14. As an analyst, I want to set initial reservoir storage, so that runs start
    from a known state.
15. As an analyst, I want to set optional terminal storage conditions, so that I
    can prevent artificial end-of-horizon reservoir depletion.
16. As an analyst, I want terminal modes `none`, `equal_initial`, and
    `min_terminal`, so that hydro uses the same conceptual pattern as BESS.
17. As an analyst, I want terminal water value, so that the optimizer can value
    water left in storage at the end of the horizon.
18. As an analyst, I want terminal water value to coexist with terminal storage
    constraints, so that I can choose conservative constraints and economic
    valuation independently.
19. As an analyst, I want a configurable spill penalty, so that the optimizer
    can discourage water spill when appropriate.
20. As an analyst, I want spill to remain allowed, so that high-inflow cases do
    not become infeasible only because the reservoir is full.
21. As an analyst, I want optional minimum release in `m3/s`, so that simple
    environmental or downstream release requirements can be represented.
22. As an analyst, I want minimum release to be satisfied by turbine flow plus
    spill flow, so that required release does not force electrical generation.
23. As an analyst, I want optional turbine flow minimum and maximum limits, so
    that plant operating bounds can be represented.
24. As an analyst, I want a simple linear hydro generation mode, so that cases
    with approximate conversion factors can be modeled quickly.
25. As an analyst, I want linear mode to use
    `power_per_flow_mw_per_m3s`, so that power is auditable from turbine flow.
26. As an analyst, I want a piecewise-linear generation mode, so that nonlinear
    power-flow behavior can be modeled without hand-written JSON.
27. As an analyst, I want piecewise generation breakpoints to be explicit
    `(flow_m3s, power_mw)` pairs, so that curves are auditable and versioned.
28. As an analyst, I want piecewise generation curves to allow nonconvex and
    nonmonotone power values, so that real or approximated plant curves are not
    overrestricted.
29. As an analyst, I want generation breakpoint flow values to be strictly
    increasing, so that the curve domain is unambiguous.
30. As an analyst, I want generation breakpoint power values to be nonnegative,
    so that hydro remains a generation asset and not a load or pump.
31. As an analyst, I want optional `power_max_mw`, so that electrical plant or
    interconnection limits can be represented separately from the curve.
32. As an analyst, I want the generation curve domain to govern the turbine
    flow domain in piecewise mode, so that extrapolation is avoided.
33. As an analyst, I want optional turbine flow min/max limits in piecewise
    mode, so that the curve domain can be narrowed without changing breakpoints.
34. As an analyst, I want a mandatory reservoir storage-elevation curve, so that
    reservoir level can be validated and reported.
35. As an analyst, I want reservoir curve breakpoints as
    `(storage_hm3, elevation_masl)` pairs, so that storage-to-cota reporting is
    traceable.
36. As an analyst, I want reservoir storage breakpoints to be strictly
    increasing, so that the storage domain is unambiguous.
37. As an analyst, I want reservoir elevation breakpoints to be numeric and
    nondecreasing, so that the reported level is physically plausible.
38. As an analyst, I want reservoir storage bounds to fit within the reservoir
    curve domain, so that reported elevation never requires extrapolation.
39. As an analyst, I want all hydraulic curves stored in the immutable scenario
    version, so that each run is reproducible.
40. As an analyst, I want CSV/XLSX mapping for `hydro_inflow_m3s` by hydro
    asset ID, so that hydro time series can be loaded from spreadsheets.
41. As an analyst, I want the ingestion layer to reject missing hydro inflow
    mappings, so that generated hydro cases are complete before Julia
    validation.
42. As an analyst, I want the ingestion layer to reject negative hydro inflow,
    so that invalid physical inputs fail early.
43. As an analyst, I want the generated `system_case` preview to show `v2`
    schema, hydro nodes, curves, and hydro inflow series, so that I can inspect
    the exact optimization input.
44. As an analyst, I want Julia validation errors for hydro cases to appear on
    the draft page, so that curve or parameter mistakes can be corrected before
    promotion.
45. As an analyst, I want a successful hydro validation to allow promotion to a
    scenario version, so that hydro cases use the same immutable run boundary as
    other cases.
46. As an analyst, I want to run an editor-created hydro version manually, so
    that hydro dispatch goes through the existing run/artifact workflow.
47. As an analyst, I want hydro runs to preserve input snapshots, stdout,
    stderr, summary, dispatch, asset dispatch, and metadata artifacts, so that
    the audit trail remains intact.
48. As an analyst, I want `dispatch.csv` to include hydro totals, so that system
    results can be inspected in a spreadsheet.
49. As an analyst, I want `asset_dispatch.csv` to include one hydro row per
    hydro asset and period, so that asset-specific hydro behavior is visible.
50. As an analyst, I want hydro outputs to include power, inflow, turbine flow,
    spill flow, storage, reservoir elevation, spill penalty, and terminal water
    value, so that hydro economics and physics are auditable.
51. As an analyst, I want `summary.json` to include hydro KPIs by asset, so that
    run-level results can be reviewed without scanning every row.
52. As an analyst, I want `summary.json` to include total hydro KPIs, so that
    portfolio-level hydro behavior is visible.
53. As an analyst, I want result charts for hydro power, turbine flow, spill
    flow, storage, and reservoir elevation, so that hydro behavior can be
    inspected visually.
54. As an analyst, I want charts to degrade gracefully when hydro columns are
    absent, so that legacy runs still render cleanly.
55. As an analyst, I want legacy `v1` paste/upload cases to keep validating and
    running, so that previous scenario versions remain usable.
56. As an analyst, I want the structured editor to generate `v2` from Iteration
    5 onward, so that new cases use the current contract consistently.
57. As a Julia maintainer, I want `PiecewiseLinearOpt` added explicitly as a
    dependency, so that piecewise hydro curves are implemented through a proven
    JuMP-compatible library.
58. As a Julia maintainer, I want `PiecewiseLinearOpt.piecewiselinear` to use
    the library default method for Iteration 5, so that method tuning remains a
    future optimization problem.
59. As a Julia maintainer, I want nonconvex piecewise generation behavior covered
    by tests, so that the chosen default method is proven for the accepted
    contract.
60. As a Julia maintainer, I want the method choice for piecewise modeling
    documented as a pending technical optimization, so that later work can
    benchmark alternatives.
61. As a Julia maintainer, I want a new mathematical model document for
    hydropower, so that model changes are reviewed before implementation.
62. As a Julia maintainer, I want the existing battery, renewable, grid, load,
    price, CLI, and output behavior to remain stable, so that hydropower does
    not regress earlier iterations.
63. As a backend developer, I want the editor, ingestion, generated-case, and
    results modules to use small testable interfaces, so that hydro additions
    can be tested without brittle UI-only tests.
64. As a backend developer, I want source-file provenance to continue working
    for hydro cases, so that input files and mappings remain auditable.
65. As a maintainer, I want a hydro sample case under `data/cases`, so that the
    Julia engine can be exercised without the web app.
66. As a maintainer, I want acceptance coverage for a linear hydro flow, so that
    the simplest hydro mode is proven end to end.
67. As a maintainer, I want acceptance coverage for a piecewise hydro flow, so
    that the new piecewise dependency is proven end to end.
68. As a maintainer, I want manual Iteration 5 test instructions, so that the
    structured hydro workflow can be reviewed visually and operationally.

## Implementation Decisions

- Iteration 5 adds a new one-bus asset type: `hydro`.
- A `hydro` node represents one independent reservoir plus one associated
  plant.
- Multiple hydro nodes are allowed, but they are independent and share only the
  one electrical bus balance.
- Hydraulic cascades, hydraulic networks, routing, travel-time delays, and
  multiple physical hydraulic nodes are out of scope.
- Electrical modeling remains one-bus. Hydro power is supply in the common bus
  balance.
- The system case schema moves to `bess_system_dispatch.v2` for newly generated
  structured editor cases.
- Legacy `bess_system_dispatch.v1` cases remain valid for paste/upload, CLI,
  API, results, and regression tests.
- Structured editor generation should produce `v2` from Iteration 5 onward,
  even for cases without hydro.
- Paste/upload JSON should accept both `v1` and `v2`.
- `v2` extends the graph contract with hydro nodes and hydro inflow time-series
  maps.
- Hydro storage is modeled in `hm3`.
- Hydro operational flows are modeled in `m3/s`.
- The reservoir balance converts flow and period duration into volume using
  `flow_m3s * duration_hours * 3600 / 1_000_000`.
- Hydro inflow is a required time-series value for every hydro asset and period.
- Hydro spill is a nonnegative decision variable.
- Hydro turbine flow is a nonnegative decision variable.
- Hydro power is a nonnegative decision variable linked to turbine flow.
- Hydro storage is a state variable with minimum, maximum, and initial storage.
- Optional minimum release is configured as a scalar in `m3/s`.
- Minimum release is enforced on turbine flow plus spill flow.
- Optional turbine flow min/max limits are supported.
- In linear generation mode, power equals
  `power_per_flow_mw_per_m3s * turbine_flow_m3s`.
- In piecewise generation mode, power is linked to turbine flow by explicit
  `(flow_m3s, power_mw)` breakpoints.
- Piecewise generation uses `PiecewiseLinearOpt.piecewiselinear` with the
  package default method for Iteration 5.
- Optimizing or benchmarking the PiecewiseLinearOpt method choice is deferred.
- Piecewise generation accepts nonconvex and nonmonotone power curves.
- Generation breakpoint flow values must be strictly increasing.
- Generation breakpoint power values must be finite and nonnegative.
- Optional `power_max_mw` applies in both linear and piecewise modes when
  configured.
- In piecewise mode, the breakpoint domain defines the base turbine flow domain.
- Optional turbine flow min/max limits in piecewise mode must lie within the
  breakpoint domain.
- The reservoir curve is mandatory for every hydro asset.
- The reservoir curve uses explicit `(storage_hm3, elevation_masl)` breakpoints.
- Reservoir storage breakpoints must be strictly increasing.
- Reservoir elevation breakpoints must be finite and nondecreasing.
- Reservoir storage bounds and initial/terminal storage values must lie within
  the reservoir curve domain.
- Reservoir elevation is modeled/reported from storage through
  `PiecewiseLinearOpt.piecewiselinear`, but it does not affect generation in
  Iteration 5.
- Hydro terminal condition modes are `none`, `equal_initial`, and
  `min_terminal`.
- `min_terminal` requires `terminal_storage_min_hm3`.
- `terminal_water_value_usd_per_hm3` is optional and defaults to zero.
- Terminal water value contributes
  `terminal_water_value_usd_per_hm3 * final_storage_hm3` to the objective.
- Terminal water value may coexist with any terminal condition. Documentation
  must explain that `equal_initial` fixes final storage and therefore can make
  the terminal value non-decisional.
- `spill_penalty_usd_per_hm3` is optional and defaults to zero.
- Spill penalty subtracts
  `spill_penalty_usd_per_hm3 * spill_volume_hm3[t]` from the objective.
- Hydro has no electrical curtailment variable. If water should not generate,
  the model can spill instead of turbine.
- The bus balance includes hydro power on the supply side.
- `dispatch.csv` should include hydro totals such as total hydro power, inflow,
  turbine flow, spill flow, spill penalty, storage, and terminal water value
  where appropriate.
- `asset_dispatch.csv` should include hydro rows with asset-specific hydro
  columns.
- `summary.json` should include hydro KPIs by asset and totals.
- `model_metadata.json` should include hydro asset IDs, schema version, hydro
  active constraints, and hydro unit conventions.
- Result charts should add hydro-specific charts while preserving legacy chart
  fallbacks for runs without hydro columns.
- The main deep modules for Iteration 5 are the Julia hydro formulation,
  `system_case v2` contract handling, structured draft hydro generation,
  CSV/XLSX hydro inflow ingestion, hydro result rendering, and acceptance/docs.

## Testing Decisions

- Tests should verify external behavior and contracts, not implementation
  details.
- The Julia regression suite remains required for every slice that changes the
  optimizer.
- Python web tests remain required for every slice that changes the analyst app.
- Julia tests should cover `v1` compatibility, `v2` validation, hydro node
  parsing, hydro time-series validation, reservoir curve validation, generation
  curve validation, linear generation mode, piecewise generation mode,
  nonconvex/nonmonotone generation breakpoints, reservoir balance, spill,
  spill penalty, minimum release, terminal storage conditions, terminal water
  value, bus balance, outputs, summary KPIs, and CLI success/failure behavior.
- Julia tests should include a sample `v2` hydro case under `data/cases` and
  prove it can validate, solve, and write artifacts.
- Python tests should cover structured draft hydro asset persistence, form
  parsing, generated `v2` cases, duplicate IDs, invalid curve payloads, CSV/XLSX
  mapping suggestions, manual mapping overrides, missing hydro inflow mappings,
  negative hydro inflows, generated-case validation, promotion, manual run, and
  result charts.
- Result reader tests should prove hydro columns are read from existing
  artifacts without modifying the source files.
- Acceptance tests should prove a linear hydro case from draft to run results.
- Acceptance tests should prove a piecewise hydro case from draft to run
  results.
- Regression tests should prove Iteration 4 structured cases without hydro
  still work and Iteration 3/4 paste/upload `v1` JSON still validates and runs.
- Manual tests should complement automation with visual checks for hydro forms,
  breakpoint tables, mapping UI, generated preview, validation notices, charts,
  artifacts, and responsive layout.

## Out of Scope

- Hydraulic cascades.
- Hydraulic network graphs.
- Travel-time delays or routing.
- Multiple reservoirs coupled to one plant.
- Multiple plants sharing one reservoir.
- Pumped storage or negative hydro generation.
- Hydro electrical curtailment.
- Generation curves depending on reservoir elevation or head.
- Bivariate or multivariate piecewise generation curves.
- Unit conversion beyond the explicit `m3/s`, `hm3`, `hours`, and `MW`
  conventions.
- Benchmarking or selecting the optimal PiecewiseLinearOpt formulation method.
- Forecasting, stochastic inflows, or rolling-horizon water value.
- Customer read-only portal.
- Dashboard templates and publishing.
- Scheduled runs.
- Authentication, authorization, roles, or multi-user administration.
- Multiple physical electrical buses, network flow, line limits, or losses.
- Advanced Excel ETL, formulas, merged cells, named ranges, or unit conversion.

## Further Notes

Iteration 5 should be treated as the hydropower modeling bridge between the
usable structured analyst app and the final one-bus hybrid product objective.
It should not try to finish customer publication, scheduling, auth, or dashboard
builder work.

The most important product proof is that an analyst can create and run a hydro
case without writing JSON.

The most important technical proof is that `bess_system_dispatch.v2` adds hydro
without breaking `v1`, without destabilizing BESS/renewable/grid/load behavior,
and without weakening the auditable artifact trail.

The PiecewiseLinearOpt method choice is intentionally deferred. Iteration 5 uses
the library default and proves the accepted behavior with tests. A later
performance/modeling issue can compare SOS2, convex-combination,
incremental/logarithmic, or other supported methods if needed.
