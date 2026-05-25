using HiGHS
using JuMP

struct DispatchModel
    model::JuMP.Model
    p_charge_mw::Vector{JuMP.VariableRef}
    p_discharge_mw::Vector{JuMP.VariableRef}
    energy_mwh::Vector{JuMP.VariableRef}
    is_charging::Union{Nothing,Vector{JuMP.VariableRef}}
end

struct DispatchResult
    case_name::String
    solver_name::String
    termination_status::String
    objective_value_usd::Float64
    p_charge_mw::Vector{Float64}
    p_discharge_mw::Vector{Float64}
    net_discharge_mw::Vector{Float64}
    energy_mwh::Vector{Float64}
    market_value_usd::Vector{Float64}
    is_charging::Union{Nothing,Vector{Float64}}
end

function build_dispatch_model(case_data::CaseData)::DispatchModel
    validate_case_data(case_data)

    if case_data.solver.name != "HiGHS"
        throw(ArgumentError("only HiGHS solver is supported; got $(case_data.solver.name)"))
    end

    n_periods = length(case_data.time_series.timestamp)
    if n_periods == 0
        throw(ArgumentError("time_series must contain at least one period"))
    end

    bess = case_data.bess
    time_series = case_data.time_series
    model = Model(HiGHS.Optimizer)
    set_silent(model)

    for (name, value) in case_data.solver.options
        set_optimizer_attribute(model, name, value)
    end

    @variable(model, 0 <= p_charge_mw[1:n_periods] <= bess.charge_power_max_mw)
    @variable(model, 0 <= p_discharge_mw[1:n_periods] <= bess.discharge_power_max_mw)
    @variable(model, bess.energy_min_mwh <= energy_mwh[1:n_periods] <= bess.energy_max_mwh)

    is_charging = nothing
    if case_data.constraints.prevent_simultaneous_charge_discharge
        @variable(model, is_charging[1:n_periods], Bin)

        @constraint(
            model,
            [period in 1:n_periods],
            p_charge_mw[period] <= bess.charge_power_max_mw * is_charging[period]
        )
        @constraint(
            model,
            [period in 1:n_periods],
            p_discharge_mw[period] <= bess.discharge_power_max_mw * (1 - is_charging[period])
        )
    end

    @constraint(
        model,
        energy_mwh[1] ==
        bess.initial_energy_mwh +
        bess.charge_efficiency * p_charge_mw[1] * time_series.duration_hours[1] -
        (p_discharge_mw[1] / bess.discharge_efficiency) * time_series.duration_hours[1]
    )

    for period in 2:n_periods
        @constraint(
            model,
            energy_mwh[period] ==
            energy_mwh[period - 1] +
            bess.charge_efficiency * p_charge_mw[period] * time_series.duration_hours[period] -
            (p_discharge_mw[period] / bess.discharge_efficiency) * time_series.duration_hours[period]
        )
    end

    if case_data.constraints.terminal_condition == "equal_initial"
        @constraint(model, energy_mwh[n_periods] == bess.initial_energy_mwh)
    elseif case_data.constraints.terminal_condition == "min_terminal"
        @constraint(model, energy_mwh[n_periods] >= case_data.constraints.terminal_energy_min_mwh)
    end

    @objective(
        model,
        Max,
        sum(
            time_series.price_usd_per_mwh[period] *
            (p_discharge_mw[period] - p_charge_mw[period]) *
            time_series.duration_hours[period] for period in 1:n_periods
        )
    )

    return DispatchModel(model, p_charge_mw, p_discharge_mw, energy_mwh, is_charging)
end

function solve_dispatch(case_data::CaseData)::DispatchResult
    dispatch_model = build_dispatch_model(case_data)
    optimize!(dispatch_model.model)

    termination = string(termination_status(dispatch_model.model))
    if !has_values(dispatch_model.model)
        throw(ErrorException("optimization finished without primal values; termination_status=$termination"))
    end

    p_charge = value.(dispatch_model.p_charge_mw)
    p_discharge = value.(dispatch_model.p_discharge_mw)
    energy = value.(dispatch_model.energy_mwh)
    is_charging = dispatch_model.is_charging === nothing ? nothing : value.(dispatch_model.is_charging)
    net_discharge = p_discharge .- p_charge
    market_value = case_data.time_series.price_usd_per_mwh .* net_discharge .* case_data.time_series.duration_hours

    return DispatchResult(
        case_data.case_name,
        case_data.solver.name,
        termination,
        objective_value(dispatch_model.model),
        p_charge,
        p_discharge,
        net_discharge,
        energy,
        market_value,
        is_charging,
    )
end

