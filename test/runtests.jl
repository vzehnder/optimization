using Dates
using BESSDispatch
using CSV
using JSON3
using JuMP
using Test
using YAML

const POWER_TOLERANCE_MW = 1e-6
const ENERGY_TOLERANCE_MWH = 1e-6
const OBJECTIVE_TOLERANCE_USD = 1e-5

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
    degradation_cost_per_mwh_delta_soc = 0.0,
    prevent_simultaneous_charge_discharge = false,
    terminal_condition = "none",
    terminal_energy_min_mwh = nothing,
    degradation_linear_delta_soc = false,
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
            degradation_cost_per_mwh_delta_soc,
        ),
        time_series = BESSDispatch.TimeSeriesData(timestamps, prices, period_durations),
        constraints = BESSDispatch.ConstraintConfig(
            prevent_simultaneous_charge_discharge,
            terminal_condition,
            terminal_energy_min_mwh,
            degradation_linear_delta_soc,
        ),
    )
end

function plot_report_command(script_path::AbstractString, run_output_dir::AbstractString)
    python = Sys.which("python")
    if python !== nothing
        return `$(python) $(script_path) $(run_output_dir)`
    end

    python3 = Sys.which("python3")
    if python3 !== nothing
        return `$(python3) $(script_path) $(run_output_dir)`
    end

    py = Sys.which("py")
    if py !== nothing
        return `$(py) -3 $(script_path) $(run_output_dir)`
    end

    error("Python executable is required to run the Plotly report smoke check")
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
        @test case_data.bess.degradation_cost_per_mwh_delta_soc == 20.0

        @test case_data.time_series.timestamp == [
            DateTime("2026-01-01T00:00:00") + Hour(hour) for hour in 0:23
        ]
        @test case_data.time_series.price_usd_per_mwh == [
            40.0,
            38.0,
            35.0,
            32.0,
            30.0,
            34.0,
            45.0,
            55.0,
            60.0,
            50.0,
            35.0,
            25.0,
            20.0,
            22.0,
            28.0,
            45.0,
            70.0,
            95.0,
            110.0,
            100.0,
            80.0,
            60.0,
            50.0,
            42.0,
        ]
        @test case_data.time_series.duration_hours == fill(1.0, 24)

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
        @test length(dispatch_model.p_charge_mw) == 24
        @test length(dispatch_model.p_discharge_mw) == 24
        @test length(dispatch_model.energy_mwh) == 24
    end

    @testset "running the sample case writes persisted run outputs" begin
        case_dir = joinpath(@__DIR__, "..", "data", "cases", "arbitrage_mvp")

        mktempdir() do output_root
            run_output = BESSDispatch.run_case(
                case_dir;
                output_root = output_root,
                run_timestamp = DateTime("2026-01-02T03:04:05"),
            )

            @test run_output.case_name == "arbitrage_mvp"
            @test run_output.run_timestamp == "20260102T030405000"
            @test run_output.output_dir == joinpath(output_root, "arbitrage_mvp", "20260102T030405000")
            @test isfile(run_output.dispatch_path)
            @test isfile(run_output.summary_path)
            @test isfile(run_output.config_resolved_path)
            @test isfile(run_output.model_metadata_path)

            dispatch_rows = collect(CSV.File(run_output.dispatch_path))
            @test length(dispatch_rows) == 24
            @test propertynames(dispatch_rows[1]) == [
                :timestamp,
                :duration_hours,
                :price_usd_per_mwh,
                :p_charge_mw,
                :p_discharge_mw,
                :net_discharge_mw,
                :energy_mwh,
                :delta_soc_abs_mwh,
                :is_charging,
                :period_profit_usd,
                :degradation_cost_usd,
            ]

            summary = JSON3.read(read(run_output.summary_path, String))
            @test string(summary.case_name) == "arbitrage_mvp"
            @test string(summary.run_timestamp) == "20260102T030405000"
            @test string(summary.solver_name) == "HiGHS"
            @test !isempty(string(summary.solver_status))
            @test string(summary.termination_status) == "OPTIMAL"
            @test summary.objective_value_usd == run_output.result.objective_value_usd
            @test string(summary.source_identifiers.case_dir) == abspath(case_dir)

            resolved_config = YAML.load_file(run_output.config_resolved_path)
            @test resolved_config["case_name"] == "arbitrage_mvp"
            @test resolved_config["constraints"]["terminal_condition"] == "equal_initial"
            @test resolved_config["constraints"]["degradation_linear_delta_soc"] == true

            metadata = JSON3.read(read(run_output.model_metadata_path, String))
            @test string(metadata.model_name) == "single_bess_price_taker_dispatch"
            @test metadata.number_of_periods == 24
            @test string(metadata.terminal_condition) == "equal_initial"
            @test metadata.active_constraint_flags.prevent_simultaneous_charge_discharge == true
            @test metadata.active_constraint_flags.degradation_linear_delta_soc == true
            @test string(metadata.unit_conventions.energy) == "MWh"

            second_run_output = BESSDispatch.run_case(
                case_dir;
                output_root = output_root,
                run_timestamp = DateTime("2026-01-02T03:04:05"),
            )

            @test second_run_output.run_timestamp == "20260102T030405000-02"
            @test second_run_output.output_dir != run_output.output_dir
            @test isfile(second_run_output.dispatch_path)
        end
    end

    @testset "plot report script creates an HTML report for a sample run" begin
        case_dir = joinpath(@__DIR__, "..", "data", "cases", "arbitrage_mvp")
        script_path = joinpath(@__DIR__, "..", "python", "plot_results.py")

        mktempdir() do output_root
            run_output = BESSDispatch.run_case(
                case_dir;
                output_root = output_root,
                run_timestamp = DateTime("2026-01-02T03:04:05"),
            )

            report_path = joinpath(run_output.output_dir, "plots", "dispatch_report.html")
            @test !isfile(report_path)

            run(plot_report_command(script_path, run_output.output_dir))

            @test isfile(report_path)
            report_html = read(report_path, String)
            @test occursin("Plotly.newPlot", report_html)
            @test occursin("price_usd_per_mwh", report_html)
            @test occursin("p_charge_mw", report_html)
            @test occursin("p_discharge_mw", report_html)
            @test occursin("energy_mwh", report_html)
            @test occursin("period_profit_usd", report_html)
            @test occursin("degradation_cost_usd", report_html)
        end
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

    @testset "enabled degradation reports absolute SOC movement and subtracts cost" begin
        result = BESSDispatch.solve_dispatch(
            core_arbitrage_case(
                prices = [10.0, 100.0, 10.0],
                degradation_cost_per_mwh_delta_soc = 2.0,
                degradation_linear_delta_soc = true,
            ),
        )

        @test result.termination_status == "OPTIMAL"
        @test isapprox(result.delta_soc_abs_mwh[1], 10.0; atol = 1e-6)
        @test isapprox(result.delta_soc_abs_mwh[2], 10.0; atol = 1e-6)
        @test isapprox(result.delta_soc_abs_mwh[3], 0.0; atol = 1e-6)
        @test result.degradation_cost_usd == result.delta_soc_abs_mwh .* 2.0
        @test isapprox(result.objective_value_usd, 860.0; atol = 1e-6)
    end

    @testset "disabled degradation omits penalty and reports zero movement cost" begin
        case_data = core_arbitrage_case(
            prices = [10.0, 100.0],
            degradation_cost_per_mwh_delta_soc = 50.0,
            degradation_linear_delta_soc = false,
        )

        dispatch_model = BESSDispatch.build_dispatch_model(case_data)
        result = BESSDispatch.solve_dispatch(case_data)

        @test dispatch_model.delta_soc_abs_mwh === nothing
        @test result.termination_status == "OPTIMAL"
        @test result.delta_soc_abs_mwh == [0.0, 0.0]
        @test result.degradation_cost_usd == [0.0, 0.0]
        @test isapprox(result.objective_value_usd, 900.0; atol = 1e-6)
    end

    @testset "positive degradation avoids unnecessary cycling at constant prices" begin
        result = BESSDispatch.solve_dispatch(
            core_arbitrage_case(
                prices = [50.0, 50.0, 50.0],
                initial_energy_mwh = 5.0,
                degradation_cost_per_mwh_delta_soc = 2.0,
                prevent_simultaneous_charge_discharge = true,
                terminal_condition = "equal_initial",
                degradation_linear_delta_soc = true,
            ),
        )

        @test result.termination_status == "OPTIMAL"
        @test all(result.p_charge_mw .<= 1e-6)
        @test all(result.p_discharge_mw .<= 1e-6)
        @test all(abs.(result.energy_mwh .- 5.0) .<= 1e-6)
        @test all(result.delta_soc_abs_mwh .<= 1e-6)
        @test isapprox(result.objective_value_usd, 0.0; atol = 1e-6)
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

    @testset "MVP acceptance scenario suite" begin
        @testset "constant prices with positive degradation do not cycle" begin
            result = BESSDispatch.solve_dispatch(
                core_arbitrage_case(
                    prices = [50.0, 50.0, 50.0],
                    initial_energy_mwh = 5.0,
                    degradation_cost_per_mwh_delta_soc = 2.0,
                    prevent_simultaneous_charge_discharge = true,
                    terminal_condition = "equal_initial",
                    degradation_linear_delta_soc = true,
                ),
            )

            @test result.termination_status == "OPTIMAL"
            @test all(result.p_charge_mw .<= POWER_TOLERANCE_MW)
            @test all(result.p_discharge_mw .<= POWER_TOLERANCE_MW)
            @test all(abs.(result.energy_mwh .- 5.0) .<= ENERGY_TOLERANCE_MWH)
            @test all(result.delta_soc_abs_mwh .<= ENERGY_TOLERANCE_MWH)
            @test isapprox(result.objective_value_usd, 0.0; atol = OBJECTIVE_TOLERANCE_USD)
        end

        @testset "low-high-low shape charges low and discharges high" begin
            result = BESSDispatch.solve_dispatch(
                core_arbitrage_case(
                    prices = [30.0, 10.0, 100.0, 30.0],
                    initial_energy_mwh = 0.0,
                    prevent_simultaneous_charge_discharge = true,
                    terminal_condition = "equal_initial",
                ),
            )

            @test result.termination_status == "OPTIMAL"
            @test result.p_charge_mw[2] > POWER_TOLERANCE_MW
            @test result.p_discharge_mw[3] > POWER_TOLERANCE_MW
            @test isapprox(result.energy_mwh[end], 0.0; atol = ENERGY_TOLERANCE_MWH)
            @test result.objective_value_usd > 0.0
        end

        @testset "equal_initial terminal energy is enforced" begin
            initial_energy_mwh = 10.0
            result = BESSDispatch.solve_dispatch(
                core_arbitrage_case(
                    prices = [100.0, 10.0],
                    initial_energy_mwh = initial_energy_mwh,
                    terminal_condition = "equal_initial",
                ),
            )

            @test result.termination_status == "OPTIMAL"
            @test isapprox(result.energy_mwh[end], initial_energy_mwh; atol = ENERGY_TOLERANCE_MWH)
        end

        @testset "anti-simultaneity prevents same-period charge and discharge" begin
            result = BESSDispatch.solve_dispatch(
                core_arbitrage_case(
                    prices = [10.0, 100.0],
                    prevent_simultaneous_charge_discharge = true,
                    terminal_condition = "equal_initial",
                ),
            )

            @test result.termination_status == "OPTIMAL"
            @test result.is_charging !== nothing
            @test all(
                !(
                    result.p_charge_mw[period] > POWER_TOLERANCE_MW &&
                    result.p_discharge_mw[period] > POWER_TOLERANCE_MW
                ) for period in eachindex(result.p_charge_mw)
            )
        end

        @testset "variable duration energy accounting uses MW times hours" begin
            result = BESSDispatch.solve_dispatch(
                core_arbitrage_case(
                    prices = [10.0, 100.0],
                    durations = [0.5, 1.0],
                    prevent_simultaneous_charge_discharge = true,
                ),
            )

            @test result.termination_status == "OPTIMAL"
            @test isapprox(result.p_charge_mw[1], 10.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(result.energy_mwh[1], 10.0 * 0.5; atol = ENERGY_TOLERANCE_MWH)
            @test isapprox(result.p_discharge_mw[2], 5.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(result.energy_mwh[end], 0.0; atol = ENERGY_TOLERANCE_MWH)
        end
    end

    @testset "README documents MVP execution flow" begin
        readme_path = joinpath(@__DIR__, "..", "README.md")

        @test isfile(readme_path)

        if isfile(readme_path)
            readme = read(readme_path, String)

            @test occursin("julia --project=. -e \"import Pkg; Pkg.test()\"", readme)
            @test occursin("BESSDispatch.run_case", readme)
            @test occursin("data/cases/arbitrage_mvp", readme)
            @test occursin("python python/plot_results.py", readme)
            @test occursin("plots/dispatch_report.html", readme)
        end
    end
end
