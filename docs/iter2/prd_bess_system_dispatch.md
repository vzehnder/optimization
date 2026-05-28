# BESS System Dispatch PRD

## Problem Statement

The current MVP optimizes the dispatch of one BESS connected to the grid. That proves the core battery arbitrage formulation, but it does not yet provide a way to describe a system composed of multiple connected energy assets.

The next product need is a bridge between the mathematical optimizer and a future visual web tool. A future user should be able to draw a simple hybrid system with assets such as a battery, renewable generation, grid connection, and optional local demand, then submit that structured system to the optimizer. Iteration 2 must build the internal contract and model architecture for that future workflow without building the web interface yet.

The immediate problem is therefore not UI rendering. It is the lack of a validated graph-shaped input contract, a normalization layer between that graph and JuMP, and a one-bus dispatch model that can optimize simple hybrid systems while preserving the working single-BESS MVP.

## Solution

Build a system-dispatch layer that accepts a versioned JSON case describing nodes, edges, common time series, solver settings, and constraints. The graph is logical, not electrical-network-physical: all accepted systems in this iteration collapse to one bus or point of common coupling.

The system-dispatch flow will be:

```text
system_case JSON
-> validated SystemGraphData
-> normalized OptimizationCaseData
-> JuMP one-bus dispatch model
-> DispatchResult
-> machine-readable outputs
```

Iteration 2 must support a primary case composed of renewable generation, one battery, one grid connection, and optional local load. The design should support assets identified by stable IDs and should not bake in a single instance per type, but the primary acceptance scenario can remain small.

Julia remains the optimization engine for this iteration. To prepare for a production Python backend, the implementation must expose a stable Julia API and a stable CLI that can be invoked by a Python worker or FastAPI service later. The Python backend itself is out of scope.

## User Stories

1. As an optimization developer, I want to load a complete system case from one JSON file, so that future UI-generated cases can be submitted without YAML and CSV stitching.
2. As an optimization developer, I want every system case to declare a schema version, so that future input changes can be handled explicitly.
3. As an optimization developer, I want the JSON contract to contain graph nodes and edges, so that it matches the structure a visual editor will eventually produce.
4. As an optimization developer, I want graph validation to reject unknown node types, so that unsupported assets fail before model construction.
5. As an optimization developer, I want graph validation to require unique node IDs, so that outputs can be traced back to input assets.
6. As an optimization developer, I want graph validation to require exactly one logical bus or PCC node, so that the iteration 2 model remains a one-bus formulation.
7. As an optimization developer, I want graph validation to reject disconnected assets, so that every modeled asset participates in the system balance.
8. As an optimization developer, I want graph edges to be treated as logical connectivity only, so that the solver avoids unsupported network-flow behavior.
9. As an optimization developer, I want a graph normalization layer, so that the JuMP builder receives clean indexed data instead of raw JSON.
10. As an optimization developer, I want common period time series, so that prices, renewable availability, load, and durations share one horizon.
11. As a system modeler, I want renewable assets to provide available power by period, so that exogenous solar or wind profiles can be optimized without modeling generator physics.
12. As a system modeler, I want renewable use and curtailment to be reported separately, so that I can see how much available generation was used or spilled.
13. As a system modeler, I want an optional curtailment penalty, so that cases can discourage renewable spill when that reflects project economics.
14. As a system modeler, I want grid import and grid export to be separate nonnegative variables, so that dispatch outputs are easy to read.
15. As a system modeler, I want optional grid import and export limits, so that the PCC can represent a constrained interconnection when needed.
16. As a system modeler, I want grid import/export anti-simultaneity enabled by default, so that results do not contain artificial same-period buy and sell flows.
17. As a system modeler, I want local load to be represented as an exogenous demand series, so that simple behind-the-meter or hybrid plant cases can be tested.
18. As a system modeler, I want the battery physics from iteration 1 preserved, so that the approved energy balance, efficiencies, terminal conditions, degradation, and anti-simultaneity behavior remain valid.
19. As an optimization developer, I want the system model to keep battery charge and discharge on the bus side, so that units and signs remain consistent with the MVP.
20. As an optimization developer, I want the common bus balance to use nonnegative variables, so that the formulation is clear and testable.
21. As an optimization developer, I want the objective to maximize net energy margin minus degradation and optional curtailment cost, so that the economic meaning remains close to the MVP.
22. As a Python backend developer, I want a stable CLI that prints a short JSON result, so that Python can run Julia as an external optimization process.
23. As a Python backend developer, I want output files to be machine-readable, so that a web API can return run status, summaries, and asset dispatch without parsing logs.
24. As a future frontend developer, I want an asset-level long-format dispatch output, so that UI tables and charts can be generated dynamically from asset IDs.
25. As an analyst, I want a wide dispatch output with key system totals, so that the sample case can be inspected quickly in a spreadsheet.
26. As a maintainer, I want the existing single-BESS API to keep working, so that iteration 1 users and tests are not broken by the system-dispatch work.
27. As a maintainer, I want the new system API to be parallel to the existing MVP API, so that the old and new flows can coexist during migration.
28. As a maintainer, I want a local issue backlog for iteration 2, so that implementation slices remain small and independently grabbable.
29. As a maintainer, I want the mathematical model documented before implementation, so that the one-bus formulation is reviewed before it becomes code.
30. As a tester, I want invalid JSON, invalid graph structure, invalid time series, and infeasible or unsupported configurations to fail with explicit messages, so that defects are caught before solving.

## Implementation Decisions

- The iteration 2 case input is a single versioned JSON document. The original YAML and CSV loader remains supported for the single-BESS MVP.
- The graph is logical and UI-facing. It contains nodes and edges, but all accepted systems in this iteration are normalized to one bus or PCC.
- Standard validation requires exactly one bus or PCC node, unique node IDs, known node types, and every asset connected to the bus.
- Supported node types for this iteration are `bus`, `battery`, `renewable`, `grid`, and `load`.
- Asset IDs are first-class. The design should support multiple assets by type, although the main acceptance scenario uses one renewable, one battery, one grid connection, and optional load.
- Edges have connectivity meaning only. Edge capacities, losses, directions, impedances, and electrical-flow behavior are out of scope.
- Time series use one common ordered horizon. Each period includes timestamp, duration, grid price, and per-asset series values such as renewable availability and load demand.
- Renewable assets are exogenous availability profiles with optimization variables for used power and curtailed power.
- Grid assets use separate import and export variables. Import and export limits are optional, but validation and formulation must avoid unbounded same-period import/export cycles.
- Grid import/export anti-simultaneity is configurable and enabled by default.
- Load assets are fixed exogenous demand. They have no decision variables in this iteration.
- Battery assets reuse the iteration 1 formulation: charge/discharge power limits, energy limits, initial energy, charge and discharge efficiency, terminal condition, optional binary anti-simultaneity, and optional linear delta-SOC degradation.
- The one-bus balance convention is: grid imports plus renewable used plus battery discharge equals grid exports plus battery charge plus load.
- The base objective maximizes grid export revenue minus grid import cost, battery degradation, and optional renewable curtailment penalties.
- The new deep module is the graph normalizer. It accepts validated graph data and returns a normalized optimization case with indexed assets and aligned period arrays.
- The JuMP system model builder depends on normalized optimization data, not file paths, raw JSON, or future UI-specific fields.
- The existing single-BESS API remains stable. New system functions are added in parallel, such as loading, solving, and running a system case.
- The CLI is a stable integration boundary for a future Python backend. It runs a system case from a JSON path and prints a compact JSON result to stdout.
- Standard outputs include a run summary, model metadata, resolved system input, a wide system dispatch CSV, and a long asset dispatch CSV.
- Documentation for the one-bus mathematical formulation is required before implementation work on the system JuMP builder.
- The local issue tracker remains Markdown-based for this repository. Iteration 2 issues should be created under the iteration 2 documentation area and marked with the `ready-for-agent` triage label.

## Testing Decisions

- Tests should verify external behavior and contracts, not implementation details. The important behavior is that valid cases solve correctly, invalid cases fail clearly, outputs are stable, and iteration 1 remains compatible.
- The JSON input contract must be tested with at least one valid hybrid system case and several invalid cases.
- Graph validation tests must cover duplicate node IDs, unknown node types, missing bus, multiple bus nodes, edges pointing to missing nodes, and disconnected asset nodes.
- Normalizer tests must prove that asset IDs, time series, prices, durations, renewable availability, load demand, and battery settings are converted into aligned indexed structures.
- Model tests must prove the one-bus balance, renewable curtailment, battery charge/discharge behavior, grid import/export behavior, local load balance, terminal condition behavior, and objective sign convention.
- Result writer tests must verify both wide dispatch and long asset dispatch outputs.
- CLI tests must verify that the command can run a sample system JSON and print parseable JSON containing the output directory, summary path, and termination status.
- Regression tests from iteration 1 must continue to pass after any refactor.
- Existing MVP tests provide prior art for validation errors, solver acceptance scenarios, output writer checks, and CLI-like execution smoke tests.

## Out of Scope

- Web frontend or visual editor.
- Production Python backend or FastAPI service.
- Database persistence.
- Authentication or users.
- Multiple physical buses.
- AC or DC power flow.
- Line losses, edge capacities, edge directions, impedances, or network constraints.
- Thermal unit commitment.
- Ancillary services.
- Rolling-horizon optimization.
- Forecasting.
- Advanced battery degradation such as rainflow, cycle-depth curves, or calendar aging.
- Demand charges, peak demand tariffs, or tariff billing engines.
- Solver support beyond the current HiGHS-centered MVP path unless needed for compatibility.

## Further Notes

Iteration 2 should be treated as the technical bridge between the current optimizer and a future visual web product. The most important artifact is not a richer UI; it is a stable, validated, graph-shaped contract that can be normalized into a mathematical optimization problem.

The implementation should keep the existing MVP behavior intact. Refactors are acceptable only when they create reusable battery-model pieces or clean boundaries needed by the system-dispatch flow.

The preferred first implementation slice is to review and approve the one-bus mathematical formulation, then implement schema and graph validation, then implement graph normalization, and only then build the system JuMP model.
