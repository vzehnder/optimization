# BESS dispatch workflow playground
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
# Point this to any case folder with config.yaml, bess.yaml, and timeseries.csv.
case_dir = joinpath(@__DIR__, "..", "data", "cases", "arbitrage_mvp")

##
# Load and validate the case data before constructing the optimization model.
case_data = load_case(case_dir)
validate_case_data(case_data)

case_data.case_name
case_data.bess
case_data.constraints

##
# Inspect the time series that will define the optimization horizon.
case_data.time_series.timestamp
case_data.time_series.price_usd_per_mwh
case_data.time_series.duration_hours

##
# Build the JuMP model without solving it yet. This is useful when you want to
# inspect the formulation or check variable counts before optimization.
dispatch_model = build_dispatch_model(case_data)
dispatch_model.model

##
# Solve the dispatch model and inspect the main result vectors in memory.
result = solve_dispatch(case_data)

result.termination_status
result.objective_value_usd
result.p_charge_mw
result.p_discharge_mw
result.net_discharge_mw
result.energy_mwh
period_profit_usd = result.market_value_usd .- result.degradation_cost_usd
period_profit_usd
result.degradation_cost_usd

##
# Write a full run output folder: dispatch.csv, summary.json,
# config_resolved.yaml, and model_metadata.json.
run_output = run_case(case_dir)
run_output.output_dir

##
# Read the persisted dispatch table back from disk.
dispatch_rows = collect(CSV.File(run_output.dispatch_path))
dispatch_rows

##
# Inspect summary metadata from the persisted output.
summary = JSON3.read(read(run_output.summary_path, String))
summary

##
# Generate the Plotly HTML report from the run output folder.
plot_script = joinpath(@__DIR__, "..", "python", "plot_results.py")

python_exe = something(Sys.which("python"), Sys.which("python3"), Sys.which("py"))

if basename(python_exe) == "py.exe" || basename(python_exe) == "py"
    run(`$(python_exe) -3 $(plot_script) $(run_output.output_dir)`)
else
    run(`$(python_exe) $(plot_script) $(run_output.output_dir)`)
end

report_path = joinpath(run_output.output_dir, "plots", "dispatch_report.html")
isfile(report_path)
report_path

##
# Optional: print the files created for this run.
readdir(run_output.output_dir)
readdir(joinpath(run_output.output_dir, "plots"))
