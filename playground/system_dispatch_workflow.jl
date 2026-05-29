# System dispatch workflow playground
#
# Run this file block by block in VS Code with the Julia project activated:
#   julia --project=.
#
# In VS Code, use the Julia extension's "Execute Code Cell" command on each
# `##` block, or select lines and run them in the REPL.

##
using BESSDispatch
using CSV
using JSON3

##
# Point this to any system_case.json file, or to a folder containing one.
system_case_path = joinpath(@__DIR__, "..", "data", "cases", "hybrid_system", "system_case.json")

##
# Load and validate the graph-shaped system case before normalization.
system_case = load_system_case(system_case_path)
validate_system_case(system_case)

system_case.case_name
system_case.schema_version
[(node.id, node.type) for node in system_case.nodes]
[(edge.from, edge.to) for edge in system_case.edges]
system_case.constraints

##
# Normalize the graph into solver-facing arrays and indexed assets.
optimization_data = normalize_system_case(system_case)

optimization_data.bus_id
[battery.id for battery in optimization_data.batteries]
[renewable.id for renewable in optimization_data.renewables]
[grid.id for grid in optimization_data.grids]
[load.id for load in optimization_data.loads]

##
# Inspect the time series that will define the optimization horizon.
optimization_data.timestamp
optimization_data.price_usd_per_mwh
optimization_data.duration_hours
optimization_data.renewable_available_power_mw
optimization_data.load_demand_mw

##
# Build the JuMP model without solving it yet. This is useful when you want to
# inspect the formulation or check variable counts before optimization.
system_dispatch_model = build_system_dispatch_model(optimization_data)
system_dispatch_model.model

##
# Solve the system dispatch model and inspect the main result arrays in memory.
# Matrix-shaped result fields are indexed as asset x period.
result = solve_system_dispatch(optimization_data)

result.termination_status
result.objective_value_usd
result.p_grid_import_mw
result.p_grid_export_mw
result.p_renewable_used_mw
result.p_renewable_curtailed_mw
result.p_battery_charge_mw
result.p_battery_discharge_mw
result.battery_energy_mwh

##
# Inspect period-level aggregates equivalent to the persisted dispatch.csv.
grid_import_mw = vec(sum(result.p_grid_import_mw; dims = 1))
grid_export_mw = vec(sum(result.p_grid_export_mw; dims = 1))
net_grid_export_mw = grid_export_mw .- grid_import_mw

battery_charge_mw = vec(sum(result.p_battery_charge_mw; dims = 1))
battery_discharge_mw = vec(sum(result.p_battery_discharge_mw; dims = 1))
battery_net_discharge_mw = battery_discharge_mw .- battery_charge_mw
battery_degradation_cost_usd = vec(sum(result.battery_degradation_cost_usd; dims = 1))

renewable_used_mw = vec(sum(result.p_renewable_used_mw; dims = 1))
renewable_curtailed_mw = vec(sum(result.p_renewable_curtailed_mw; dims = 1))
curtailment_penalty_usd = vec(sum(result.curtailment_penalty_usd; dims = 1))

period_profit_usd = result.market_value_usd .- battery_degradation_cost_usd .- curtailment_penalty_usd

net_grid_export_mw
battery_net_discharge_mw
renewable_curtailed_mw
period_profit_usd

##
# Write a full system run output folder: dispatch.csv, asset_dispatch.csv,
# summary.json, system_case_resolved.json, and model_metadata.json.
run_output = run_system_case(system_case_path)
run_output.output_dir

##
# Read the persisted wide system dispatch table back from disk.
dispatch_rows = collect(CSV.File(run_output.dispatch_path))
dispatch_rows

##
# Read the persisted long asset-level dispatch table back from disk.
asset_dispatch_rows = collect(CSV.File(run_output.asset_dispatch_path))
asset_dispatch_rows

##
# Inspect summary and model metadata from the persisted output.
summary = JSON3.read(read(run_output.summary_path, String))
summary

model_metadata = JSON3.read(read(run_output.model_metadata_path, String))
model_metadata

##
# Inspect the resolved JSON system input persisted with the run.
resolved_system_case = JSON3.read(read(run_output.system_case_resolved_path, String))
resolved_system_case

##
# Optional: print the files created for this run.
readdir(run_output.output_dir)
