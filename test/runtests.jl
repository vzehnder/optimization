using Dates
using BESSDispatch
using JuMP
using Test

function valid_case_data(;
    bess = BESSDispatch.BESSParameters(10.0, 10.0, 0.0, 40.0, 20.0, 0.95, 0.95, 2.0),
    time_series = BESSDispatch.TimeSeriesData(
        [DateTime("2026-01-01T00:00:00"), DateTime("2026-01-01T01:00:00")],
        [40.0, 90.0],
        [1.0, 1.0],
    ),
    constraints = BESSDispatch.ConstraintConfig(true, "equal_initial", nothing, true),
    solver = BESSDispatch.SolverConfig("HiGHS", Dict{String,Any}()),
    horizon = BESSDispatch.HorizonConfig("full_horizon", nothing, nothing, nothing, nothing),
)
    return BESSDispatch.CaseData("test_case", bess, time_series, constraints, solver, horizon)
end

function validation_message(case_data)
    try
        BESSDispatch.validate_case_data(case_data)
        return nothing
    catch error
        return sprint(showerror, error)
    end
end

function core_arbitrage_case(;
    prices = [10.0, 100.0, 10.0],
    durations = nothing,
    initial_energy_mwh = 0.0,
    charge_efficiency = 1.0,
    discharge_efficiency = 1.0,
    prevent_simultaneous_charge_discharge = false,
    terminal_condition = "none",
    terminal_energy_min_mwh = nothing,
)
    timestamps = [DateTime("2026-01-01T00:00:00") + Hour(index - 1) for index in eachindex(prices)]
    period_durations = durations === nothing ? fill(1.0, length(prices)) : durations

    return valid_case_data(
        bess = BESSDispatch.BESSParameters(
            10.0,
            10.0,
            0.0,
            10.0,
            initial_energy_mwh,
            charge_efficiency,
            discharge_efficiency,
            0.0,
        ),
        time_series = BESSDispatch.TimeSeriesData(timestamps, prices, period_durations),
        constraints = BESSDispatch.ConstraintConfig(
            prevent_simultaneous_charge_discharge,
            terminal_condition,
            terminal_energy_min_mwh,
            false,
        ),
    )
end

@testset "BESSDispatch package" begin
    @testset "can be imported" begin
        @test BESSDispatch isa Module
    end

    @testset "loads the sample arbitrage case" begin
        case_dir = joinpath(@__DIR__, "..", "data", "cases", "arbitrage_mvp")

        case_data = BESSDispatch.load_case(case_dir)

        @test case_data.case_name == "arbitrage_mvp"
        @test case_data.bess.charge_power_max_mw == 10.0
        @test case_data.bess.discharge_power_max_mw == 10.0
        @test case_data.bess.energy_min_mwh == 0.0
        @test case_data.bess.energy_max_mwh == 40.0
        @test case_data.bess.initial_energy_mwh == 20.0
        @test case_data.bess.charge_efficiency == 0.95
        @test case_data.bess.discharge_efficiency == 0.95
        @test case_data.bess.degradation_cost_per_mwh_delta_soc == 2.0

        @test case_data.time_series.timestamp == [
            DateTime("2026-01-01T00:00:00"),
            DateTime("2026-01-01T01:00:00"),
            DateTime("2026-01-01T02:00:00"),
        ]
        @test case_data.time_series.price_usd_per_mwh == [40.0, 20.0, 90.0]
        @test case_data.time_series.duration_hours == [1.0, 1.0, 1.0]

        @test case_data.constraints.prevent_simultaneous_charge_discharge
        @test case_data.constraints.terminal_condition == "equal_initial"
        @test isnothing(case_data.constraints.terminal_energy_min_mwh)
        @test case_data.constraints.degradation_linear_delta_soc

        @test case_data.solver.name == "HiGHS"
        @test isempty(case_data.solver.options)

        @test case_data.horizon.mode == "full_horizon"
        @test isnothing(case_data.horizon.start_timestamp)
        @test isnothing(case_data.horizon.end_timestamp)
        @test isnothing(case_data.horizon.step_hours)
        @test isnothing(case_data.horizon.lookahead_periods)
    end

    @testset "rejects nonpositive durations" begin
        case_data = valid_case_data(
            time_series = BESSDispatch.TimeSeriesData(
                [DateTime("2026-01-01T00:00:00")],
                [40.0],
                [0.0],
            ),
        )

        @test occursin("duration_hours[1] must be positive", validation_message(case_data))
    end

    @testset "rejects missing prices" begin
        case_data = valid_case_data(
            time_series = BESSDispatch.TimeSeriesData(
                [DateTime("2026-01-01T00:00:00"), DateTime("2026-01-01T01:00:00")],
                [40.0],
                [1.0, 1.0],
            ),
        )

        @test occursin("time_series vectors must have equal length", validation_message(case_data))
    end

    @testset "rejects invalid prices" begin
        case_data = valid_case_data(
            time_series = BESSDispatch.TimeSeriesData(
                [DateTime("2026-01-01T00:00:00")],
                [NaN],
                [1.0],
            ),
        )

        @test occursin("price_usd_per_mwh[1] must be finite", validation_message(case_data))
    end

    @testset "rejects invalid energy bounds" begin
        case_data = valid_case_data(
            bess = BESSDispatch.BESSParameters(10.0, 10.0, 40.0, 40.0, 20.0, 0.95, 0.95, 2.0),
        )

        @test occursin("energy_min_mwh must be less than energy_max_mwh", validation_message(case_data))
    end

    @testset "rejects invalid initial energy" begin
        case_data = valid_case_data(
            bess = BESSDispatch.BESSParameters(10.0, 10.0, 0.0, 40.0, 50.0, 0.95, 0.95, 2.0),
        )

        @test occursin("initial_energy_mwh must be within energy bounds", validation_message(case_data))
    end

    @testset "rejects invalid charge efficiency" begin
        case_data = valid_case_data(
            bess = BESSDispatch.BESSParameters(10.0, 10.0, 0.0, 40.0, 20.0, 0.0, 0.95, 2.0),
        )

        @test occursin("charge_efficiency must be in (0, 1]", validation_message(case_data))
    end

    @testset "rejects invalid discharge efficiency" begin
        case_data = valid_case_data(
            bess = BESSDispatch.BESSParameters(10.0, 10.0, 0.0, 40.0, 20.0, 0.95, 1.1, 2.0),
        )

        @test occursin("discharge_efficiency must be in (0, 1]", validation_message(case_data))
    end

    @testset "rejects unknown terminal condition" begin
        case_data = valid_case_data(
            constraints = BESSDispatch.ConstraintConfig(true, "target_energy", nothing, true),
        )

        @test occursin("terminal_condition must be one of", validation_message(case_data))
    end

    @testset "rejects missing min_terminal energy" begin
        case_data = valid_case_data(
            constraints = BESSDispatch.ConstraintConfig(true, "min_terminal", nothing, true),
        )

        @test occursin("terminal_energy_min_mwh is required when terminal_condition is min_terminal", validation_message(case_data))
    end

    @testset "rejects out-of-bounds min_terminal energy" begin
        case_data = valid_case_data(
            constraints = BESSDispatch.ConstraintConfig(true, "min_terminal", 45.0, true),
        )

        @test occursin("terminal_energy_min_mwh must be within energy bounds", validation_message(case_data))
    end

    @testset "rejects unsorted timestamps" begin
        case_data = valid_case_data(
            time_series = BESSDispatch.TimeSeriesData(
                [DateTime("2026-01-01T01:00:00"), DateTime("2026-01-01T00:00:00")],
                [40.0, 90.0],
                [1.0, 1.0],
            ),
        )

        @test occursin("timestamps must be strictly increasing", validation_message(case_data))
    end

    @testset "rejects negative charge power limit" begin
        case_data = valid_case_data(
            bess = BESSDispatch.BESSParameters(-1.0, 10.0, 0.0, 40.0, 20.0, 0.95, 0.95, 2.0),
        )

        @test occursin("charge_power_max_mw must be nonnegative", validation_message(case_data))
    end

    @testset "solves low-high-low core arbitrage dispatch" begin
        result = BESSDispatch.solve_dispatch(core_arbitrage_case())

        @test result.termination_status == "OPTIMAL"
        @test result.objective_value_usd ≈ 900.0 atol = 1e-6
        @test result.p_charge_mw[1] ≈ 10.0 atol = 1e-6
        @test result.p_discharge_mw[2] ≈ 10.0 atol = 1e-6
        @test result.energy_mwh[1] ≈ 10.0 atol = 1e-6
        @test result.energy_mwh[2] ≈ 0.0 atol = 1e-6
    end

    @testset "builds a JuMP model from the validated sample case" begin
        case_dir = joinpath(@__DIR__, "..", "data", "cases", "arbitrage_mvp")

        dispatch_model = BESSDispatch.build_dispatch_model(BESSDispatch.load_case(case_dir))

        @test dispatch_model.model isa JuMP.Model
        @test length(dispatch_model.p_charge_mw) == 3
        @test length(dispatch_model.p_discharge_mw) == 3
        @test length(dispatch_model.energy_mwh) == 3
    end

    @testset "uses period duration in energy balance" begin
        result = BESSDispatch.solve_dispatch(
            core_arbitrage_case(
                prices = [10.0, 100.0],
                durations = [0.5, 1.0],
            ),
        )

        @test result.termination_status == "OPTIMAL"
        @test result.p_charge_mw[1] ≈ 10.0 atol = 1e-6
        @test result.energy_mwh[1] ≈ 5.0 atol = 1e-6
        @test result.net_discharge_mw[2] ≈ 5.0 atol = 1e-6
        @test result.energy_mwh[2] ≈ 0.0 atol = 1e-6
    end

    @testset "terminal_condition none leaves final energy unconstrained" begin
        result = BESSDispatch.solve_dispatch(
            core_arbitrage_case(
                prices = [100.0, 10.0],
                initial_energy_mwh = 10.0,
                terminal_condition = "none",
            ),
        )

        @test result.termination_status == "OPTIMAL"
        @test result.energy_mwh[end] < 10.0 - 1e-6
    end

    @testset "terminal_condition equal_initial returns final energy to initial energy" begin
        result = BESSDispatch.solve_dispatch(
            core_arbitrage_case(
                prices = [100.0, 10.0],
                initial_energy_mwh = 10.0,
                terminal_condition = "equal_initial",
            ),
        )

        @test result.termination_status == "OPTIMAL"
        @test result.energy_mwh[end] ≈ 10.0 atol = 1e-6
    end

    @testset "terminal_condition min_terminal returns final energy to configured minimum" begin
        result = BESSDispatch.solve_dispatch(
            core_arbitrage_case(
                prices = [100.0, 10.0],
                initial_energy_mwh = 10.0,
                terminal_condition = "min_terminal",
                terminal_energy_min_mwh = 4.0,
            ),
        )

        @test result.termination_status == "OPTIMAL"
        @test result.energy_mwh[end] ≈ 4.0 atol = 1e-6
    end

    @testset "enabled anti-simultaneity mode reports physically consistent dispatch modes" begin
        result = BESSDispatch.solve_dispatch(
            core_arbitrage_case(
                prices = [10.0, 100.0],
                prevent_simultaneous_charge_discharge = true,
                terminal_condition = "equal_initial",
            ),
        )

        @test result.termination_status == "OPTIMAL"
        @test result.is_charging !== nothing
        @test result.p_charge_mw[1] > 1e-6
        @test result.p_discharge_mw[2] > 1e-6
        @test isapprox(result.is_charging[1], 1.0; atol = 1e-6)
        @test isapprox(result.is_charging[2], 0.0; atol = 1e-6)
        @test all(
            !(
                result.p_charge_mw[period] > 1e-6 &&
                result.p_discharge_mw[period] > 1e-6
            ) for period in eachindex(result.p_charge_mw)
        )
    end

    @testset "enabled anti-simultaneity mode prevents same-period lossy cycling" begin
        result = BESSDispatch.solve_dispatch(
            core_arbitrage_case(
                prices = [-10.0],
                initial_energy_mwh = 5.0,
                charge_efficiency = 0.95,
                discharge_efficiency = 0.95,
                prevent_simultaneous_charge_discharge = true,
                terminal_condition = "equal_initial",
            ),
        )

        @test result.termination_status == "OPTIMAL"
        @test result.p_charge_mw[1] <= 1e-6
        @test result.p_discharge_mw[1] <= 1e-6
        @test isapprox(result.energy_mwh[1], 5.0; atol = 1e-6)
    end

    @testset "disabled anti-simultaneity mode builds without charging mode binary" begin
        case_data = core_arbitrage_case(
            prices = [10.0, 100.0],
            prevent_simultaneous_charge_discharge = false,
            terminal_condition = "equal_initial",
        )

        dispatch_model = BESSDispatch.build_dispatch_model(case_data)
        result = BESSDispatch.solve_dispatch(case_data)

        @test dispatch_model.is_charging === nothing
        @test all(!JuMP.is_binary(variable) for variable in JuMP.all_variables(dispatch_model.model))
        @test result.termination_status == "OPTIMAL"
        @test result.is_charging === nothing
    end
end
