using Dates

struct BESSParameters
    charge_power_max_mw::Float64
    discharge_power_max_mw::Float64
    energy_min_mwh::Float64
    energy_max_mwh::Float64
    initial_energy_mwh::Float64
    charge_efficiency::Float64
    discharge_efficiency::Float64
    degradation_cost_per_mwh_delta_soc::Float64
end

struct TimeSeriesData
    timestamp::Vector{DateTime}
    price_usd_per_mwh::Vector{Float64}
    duration_hours::Vector{Float64}
end

struct ConstraintConfig
    prevent_simultaneous_charge_discharge::Bool
    terminal_condition::String
    terminal_energy_min_mwh::Union{Float64,Nothing}
    degradation_linear_delta_soc::Bool
end

struct SolverConfig
    name::String
    options::Dict{String,Any}
end

struct HorizonConfig
    mode::String
    start_timestamp::Union{DateTime,Nothing}
    end_timestamp::Union{DateTime,Nothing}
    step_hours::Union{Float64,Nothing}
    lookahead_periods::Union{Int,Nothing}
end

struct CaseData
    case_name::String
    bess::BESSParameters
    time_series::TimeSeriesData
    constraints::ConstraintConfig
    solver::SolverConfig
    horizon::HorizonConfig
end
