using CSV
using Dates
using YAML

function load_case(case_dir::AbstractString)::CaseData
    config = YAML.load_file(joinpath(case_dir, "config.yaml"))
    bess_config = YAML.load_file(joinpath(case_dir, "bess.yaml"))
    time_series = load_time_series(joinpath(case_dir, "timeseries.csv"))

    case_data = CaseData(
        required_string(config, "case_name"),
        load_bess_parameters(bess_config),
        time_series,
        load_constraint_config(required_value(config, "constraints")),
        load_solver_config(required_value(config, "solver")),
        load_horizon_config(required_value(config, "horizon")),
    )

    return validate_case_data(case_data)
end

function load_bess_parameters(config)::BESSParameters
    return BESSParameters(
        required_float(config, "charge_power_max_mw"),
        required_float(config, "discharge_power_max_mw"),
        required_float(config, "energy_min_mwh"),
        required_float(config, "energy_max_mwh"),
        required_float(config, "initial_energy_mwh"),
        required_float(config, "charge_efficiency"),
        required_float(config, "discharge_efficiency"),
        required_float(config, "degradation_cost_per_mwh_delta_soc"),
    )
end

function load_time_series(path::AbstractString)::TimeSeriesData
    timestamps = DateTime[]
    prices = Float64[]
    durations = Float64[]

    for (row_index, row) in enumerate(CSV.File(path))
        push!(timestamps, parse_required_datetime(row_value(row, :timestamp, row_index), "timeseries.csv row $row_index timestamp"))
        push!(prices, parse_required_float(row_value(row, :price_usd_per_mwh, row_index), "timeseries.csv row $row_index price_usd_per_mwh"))
        push!(durations, parse_required_float(row_value(row, :duration_hours, row_index), "timeseries.csv row $row_index duration_hours"))
    end

    return TimeSeriesData(timestamps, prices, durations)
end

function load_constraint_config(config)::ConstraintConfig
    return ConstraintConfig(
        required_bool(config, "prevent_simultaneous_charge_discharge"),
        required_string(config, "terminal_condition"),
        optional_float(required_value(config, "terminal_energy_min_mwh"), "terminal_energy_min_mwh"),
        required_bool(config, "degradation_linear_delta_soc"),
    )
end

function load_solver_config(config)::SolverConfig
    options = get(config, "options", Dict{String,Any}())
    return SolverConfig(
        required_string(config, "name"),
        Dict{String,Any}(string(key) => value for (key, value) in pairs(options)),
    )
end

function load_horizon_config(config)::HorizonConfig
    return HorizonConfig(
        required_string(config, "mode"),
        optional_datetime(required_value(config, "start_timestamp"), "horizon.start_timestamp"),
        optional_datetime(required_value(config, "end_timestamp"), "horizon.end_timestamp"),
        optional_float(required_value(config, "step_hours"), "horizon.step_hours"),
        optional_int(required_value(config, "lookahead_periods"), "horizon.lookahead_periods"),
    )
end

function validate_case_data(case_data::CaseData)::CaseData
    bess = case_data.bess

    if !isfinite(bess.charge_power_max_mw) || bess.charge_power_max_mw < 0
        throw(ArgumentError("charge_power_max_mw must be nonnegative; got $(bess.charge_power_max_mw)"))
    end

    if !isfinite(bess.discharge_power_max_mw) || bess.discharge_power_max_mw < 0
        throw(ArgumentError("discharge_power_max_mw must be nonnegative; got $(bess.discharge_power_max_mw)"))
    end

    if !(isfinite(bess.energy_min_mwh) && isfinite(bess.energy_max_mwh)) ||
       !(bess.energy_min_mwh < bess.energy_max_mwh)
        throw(ArgumentError(
            "energy_min_mwh must be less than energy_max_mwh; got energy_min_mwh=$(bess.energy_min_mwh), energy_max_mwh=$(bess.energy_max_mwh)",
        ))
    end

    if !isfinite(bess.initial_energy_mwh) ||
       !(bess.energy_min_mwh <= bess.initial_energy_mwh <= bess.energy_max_mwh)
        throw(ArgumentError(
            "initial_energy_mwh must be within energy bounds; got initial_energy_mwh=$(bess.initial_energy_mwh), energy_min_mwh=$(bess.energy_min_mwh), energy_max_mwh=$(bess.energy_max_mwh)",
        ))
    end

    if !isfinite(bess.charge_efficiency) || !(0 < bess.charge_efficiency <= 1)
        throw(ArgumentError("charge_efficiency must be in (0, 1]; got $(bess.charge_efficiency)"))
    end

    if !isfinite(bess.discharge_efficiency) || !(0 < bess.discharge_efficiency <= 1)
        throw(ArgumentError("discharge_efficiency must be in (0, 1]; got $(bess.discharge_efficiency)"))
    end

    if !isfinite(bess.degradation_cost_per_mwh_delta_soc) ||
       bess.degradation_cost_per_mwh_delta_soc < 0
        throw(ArgumentError(
            "degradation_cost_per_mwh_delta_soc must be nonnegative; got $(bess.degradation_cost_per_mwh_delta_soc)",
        ))
    end

    constraints = case_data.constraints

    if !(constraints.terminal_condition in ("none", "equal_initial", "min_terminal"))
        throw(ArgumentError(
            "terminal_condition must be one of none, equal_initial, or min_terminal; got $(constraints.terminal_condition)",
        ))
    end

    if constraints.terminal_condition == "min_terminal" && constraints.terminal_energy_min_mwh === nothing
        throw(ArgumentError("terminal_energy_min_mwh is required when terminal_condition is min_terminal"))
    end

    if constraints.terminal_condition == "min_terminal"
        terminal_energy_min_mwh = constraints.terminal_energy_min_mwh
        if !isfinite(terminal_energy_min_mwh) ||
           !(bess.energy_min_mwh <= terminal_energy_min_mwh <= bess.energy_max_mwh)
            throw(ArgumentError(
                "terminal_energy_min_mwh must be within energy bounds; got terminal_energy_min_mwh=$terminal_energy_min_mwh, energy_min_mwh=$(bess.energy_min_mwh), energy_max_mwh=$(bess.energy_max_mwh)",
            ))
        end
    end

    timestamps_count = length(case_data.time_series.timestamp)
    prices_count = length(case_data.time_series.price_usd_per_mwh)
    durations_count = length(case_data.time_series.duration_hours)

    if !(timestamps_count == prices_count == durations_count)
        throw(ArgumentError(
            "time_series vectors must have equal length; got timestamp=$timestamps_count, price_usd_per_mwh=$prices_count, duration_hours=$durations_count",
        ))
    end

    for index in 2:timestamps_count
        if !(case_data.time_series.timestamp[index - 1] < case_data.time_series.timestamp[index])
            throw(ArgumentError(
                "timestamps must be strictly increasing; timestamp[$(index - 1)]=$(case_data.time_series.timestamp[index - 1]), timestamp[$index]=$(case_data.time_series.timestamp[index])",
            ))
        end
    end

    for (index, price) in enumerate(case_data.time_series.price_usd_per_mwh)
        if !isfinite(price)
            throw(ArgumentError("price_usd_per_mwh[$index] must be finite; got $price"))
        end
    end

    for (index, duration_hours) in enumerate(case_data.time_series.duration_hours)
        if !isfinite(duration_hours) || !(duration_hours > 0)
            throw(ArgumentError("duration_hours[$index] must be positive; got $duration_hours"))
        end
    end

    return case_data
end

function required_value(config, key::AbstractString)
    if !haskey(config, key)
        throw(ArgumentError("$key is required"))
    end

    return config[key]
end

function required_string(config, key::AbstractString)::String
    return parse_required_string(required_value(config, key), key)
end

function required_bool(config, key::AbstractString)::Bool
    value = required_value(config, key)
    if !(value isa Bool)
        throw(ArgumentError("$key must be boolean; got $(repr(value))"))
    end

    return value
end

function required_float(config, key::AbstractString)::Float64
    return parse_required_float(required_value(config, key), key)
end

function row_value(row, column::Symbol, row_index::Int)
    if !(column in propertynames(row))
        throw(ArgumentError("timeseries.csv is missing required column $(String(column))"))
    end

    return getproperty(row, column)
end

function parse_required_string(value, field::AbstractString)::String
    if value === nothing || value === missing
        throw(ArgumentError("$field is required"))
    end

    parsed = string(value)
    if isempty(strip(parsed))
        throw(ArgumentError("$field is required"))
    end

    return parsed
end

function parse_required_float(value, field::AbstractString)::Float64
    if value === nothing || value === missing
        throw(ArgumentError("$field is required"))
    end

    parsed = if value isa Real
        Float64(value)
    else
        text = strip(string(value))
        if isempty(text)
            throw(ArgumentError("$field is required"))
        end

        try
            parse(Float64, text)
        catch
            throw(ArgumentError("$field must be numeric; got $(repr(value))"))
        end
    end

    return parsed
end

function parse_required_datetime(value, field::AbstractString)::DateTime
    if value === nothing || value === missing || isempty(strip(string(value)))
        throw(ArgumentError("$field is required"))
    end

    try
        return DateTime(string(value))
    catch
        throw(ArgumentError("$field must be an ISO-8601 DateTime; got $(repr(value))"))
    end
end

function optional_float(value, field::AbstractString)::Union{Float64,Nothing}
    return value === nothing ? nothing : parse_required_float(value, field)
end

function optional_int(value, field::AbstractString)::Union{Int,Nothing}
    if value === nothing
        return nothing
    end

    parsed = parse_required_float(value, field)
    if !isinteger(parsed)
        throw(ArgumentError("$field must be an integer; got $parsed"))
    end

    return Int(parsed)
end

function optional_datetime(value, field::AbstractString)::Union{DateTime,Nothing}
    return value === nothing ? nothing : parse_required_datetime(value, field)
end
