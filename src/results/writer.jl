using CSV
using DataFrames
using Dates
using JSON3
using YAML

struct RunOutput
    case_name::String
    run_timestamp::String
    output_dir::String
    dispatch_path::String
    summary_path::String
    config_resolved_path::String
    model_metadata_path::String
    result::DispatchResult
end

function run_case(
    case_dir::AbstractString;
    output_root::AbstractString = "outputs",
    run_timestamp = nothing,
)::RunOutput
    case_data = load_case(case_dir)
    result = solve_dispatch(case_data)

    return write_run_outputs(
        case_data,
        result;
        output_root,
        run_timestamp,
        source_identifiers = case_source_identifiers(case_dir),
    )
end

function write_run_outputs(
    case_data::CaseData,
    result::DispatchResult;
    output_root::AbstractString = "outputs",
    run_timestamp = nothing,
    source_identifiers = Dict{String,Any}(),
)::RunOutput
    run_timestamp_id = format_run_timestamp(run_timestamp)
    case_output_root = joinpath(output_root, case_data.case_name)
    output_dir, resolved_run_timestamp = unique_run_output_dir(case_output_root, run_timestamp_id)
    mkpath(output_dir)

    dispatch_path = joinpath(output_dir, "dispatch.csv")
    summary_path = joinpath(output_dir, "summary.json")
    config_resolved_path = joinpath(output_dir, "config_resolved.yaml")
    model_metadata_path = joinpath(output_dir, "model_metadata.json")

    CSV.write(dispatch_path, dispatch_dataframe(case_data, result))
    YAML.write_file(config_resolved_path, case_data_dict(case_data))
    write_json_file(summary_path, summary_dict(case_data, result, resolved_run_timestamp, source_identifiers))
    write_json_file(model_metadata_path, model_metadata_dict(case_data))

    return RunOutput(
        case_data.case_name,
        resolved_run_timestamp,
        output_dir,
        dispatch_path,
        summary_path,
        config_resolved_path,
        model_metadata_path,
        result,
    )
end

function dispatch_dataframe(case_data::CaseData, result::DispatchResult)::DataFrame
    n_periods = length(case_data.time_series.timestamp)
    is_charging = result.is_charging === nothing ? fill(missing, n_periods) : result.is_charging
    period_profit = result.market_value_usd .- result.degradation_cost_usd

    return DataFrame(
        timestamp = string.(case_data.time_series.timestamp),
        duration_hours = case_data.time_series.duration_hours,
        price_usd_per_mwh = case_data.time_series.price_usd_per_mwh,
        p_charge_mw = result.p_charge_mw,
        p_discharge_mw = result.p_discharge_mw,
        net_discharge_mw = result.net_discharge_mw,
        energy_mwh = result.energy_mwh,
        delta_soc_abs_mwh = result.delta_soc_abs_mwh,
        is_charging = is_charging,
        period_profit_usd = period_profit,
        degradation_cost_usd = result.degradation_cost_usd,
    )
end

function summary_dict(
    case_data::CaseData,
    result::DispatchResult,
    run_timestamp::String,
    source_identifiers,
)::Dict{String,Any}
    return Dict{String,Any}(
        "case_name" => case_data.case_name,
        "run_timestamp" => run_timestamp,
        "solver_name" => result.solver_name,
        "solver_status" => result.solver_status,
        "termination_status" => result.termination_status,
        "objective_value_usd" => result.objective_value_usd,
        "source_identifiers" => Dict{String,Any}(string(key) => value for (key, value) in pairs(source_identifiers)),
        "model_version" => package_version_string(),
    )
end

function model_metadata_dict(case_data::CaseData)::Dict{String,Any}
    constraints = case_data.constraints

    return Dict{String,Any}(
        "model_name" => "single_bess_price_taker_dispatch",
        "active_constraint_flags" => Dict{String,Any}(
            "energy_balance" => true,
            "soc_bounds" => true,
            "power_bounds" => true,
            "prevent_simultaneous_charge_discharge" => constraints.prevent_simultaneous_charge_discharge,
            "terminal_condition" => constraints.terminal_condition != "none",
            "degradation_linear_delta_soc" => constraints.degradation_linear_delta_soc,
        ),
        "terminal_condition" => constraints.terminal_condition,
        "number_of_periods" => length(case_data.time_series.timestamp),
        "unit_conventions" => Dict{String,Any}(
            "power" => "MW",
            "energy" => "MWh",
            "price" => "USD/MWh",
            "duration" => "hours",
            "revenue_and_cost" => "USD",
            "linear_degradation_coefficient" => "USD/MWh of absolute energy movement",
        ),
    )
end

function case_data_dict(case_data::CaseData)::Dict{String,Any}
    bess = case_data.bess
    constraints = case_data.constraints
    solver = case_data.solver
    horizon = case_data.horizon

    return Dict{String,Any}(
        "case_name" => case_data.case_name,
        "bess" => Dict{String,Any}(
            "charge_power_max_mw" => bess.charge_power_max_mw,
            "discharge_power_max_mw" => bess.discharge_power_max_mw,
            "energy_min_mwh" => bess.energy_min_mwh,
            "energy_max_mwh" => bess.energy_max_mwh,
            "initial_energy_mwh" => bess.initial_energy_mwh,
            "charge_efficiency" => bess.charge_efficiency,
            "discharge_efficiency" => bess.discharge_efficiency,
            "degradation_cost_per_mwh_delta_soc" => bess.degradation_cost_per_mwh_delta_soc,
        ),
        "constraints" => Dict{String,Any}(
            "prevent_simultaneous_charge_discharge" => constraints.prevent_simultaneous_charge_discharge,
            "terminal_condition" => constraints.terminal_condition,
            "terminal_energy_min_mwh" => constraints.terminal_energy_min_mwh,
            "degradation_linear_delta_soc" => constraints.degradation_linear_delta_soc,
        ),
        "solver" => Dict{String,Any}(
            "name" => solver.name,
            "options" => Dict{String,Any}(string(key) => value for (key, value) in pairs(solver.options)),
        ),
        "horizon" => Dict{String,Any}(
            "mode" => horizon.mode,
            "start_timestamp" => optional_datetime_string(horizon.start_timestamp),
            "end_timestamp" => optional_datetime_string(horizon.end_timestamp),
            "step_hours" => horizon.step_hours,
            "lookahead_periods" => horizon.lookahead_periods,
        ),
    )
end

function case_source_identifiers(case_dir::AbstractString)::Dict{String,Any}
    return Dict{String,Any}(
        "case_dir" => abspath(case_dir),
        "config" => abspath(joinpath(case_dir, "config.yaml")),
        "bess" => abspath(joinpath(case_dir, "bess.yaml")),
        "timeseries" => abspath(joinpath(case_dir, "timeseries.csv")),
    )
end

function format_run_timestamp(run_timestamp)::String
    if run_timestamp === nothing
        return Dates.format(Dates.now(), dateformat"yyyymmddTHHMMSSsss")
    elseif run_timestamp isa DateTime
        return Dates.format(run_timestamp, dateformat"yyyymmddTHHMMSSsss")
    else
        return sanitize_run_timestamp(string(run_timestamp))
    end
end

function sanitize_run_timestamp(run_timestamp::String)::String
    sanitized = replace(run_timestamp, r"[:\\/*?\"<>|]" => "-")
    if isempty(strip(sanitized))
        throw(ArgumentError("run_timestamp must not be empty"))
    end

    return sanitized
end

function unique_run_output_dir(case_output_root::AbstractString, run_timestamp::String)::Tuple{String,String}
    candidate = joinpath(case_output_root, run_timestamp)
    if !isdir(candidate)
        return candidate, run_timestamp
    end

    suffix = 2
    while true
        resolved_run_timestamp = "$(run_timestamp)-$(lpad(suffix, 2, '0'))"
        candidate = joinpath(case_output_root, resolved_run_timestamp)
        if !isdir(candidate)
            return candidate, resolved_run_timestamp
        end
        suffix += 1
    end
end

optional_datetime_string(value::Nothing) = nothing
optional_datetime_string(value::DateTime) = string(value)

function write_json_file(path::AbstractString, data)
    open(path, "w") do io
        JSON3.write(io, data)
        write(io, "\n")
    end
end

function package_version_string()
    try
        version = pkgversion(@__MODULE__)
        return version === nothing ? nothing : string(version)
    catch
        return nothing
    end
end
