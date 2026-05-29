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

function system_cli_command(script_path::AbstractString, case_path::AbstractString, output_root::AbstractString)
    project_root = normpath(joinpath(@__DIR__, ".."))
    return `$(Base.julia_cmd()) --project=$(project_root) $(script_path) $(case_path) --output-root $(output_root) --run-timestamp 2026-01-02T03:04:05`
end

function minimal_system_case_document()
    return Dict{String,Any}(
        "schema_version" => "bess_system_dispatch.v1",
        "case_name" => "minimal_hybrid_system",
        "nodes" => [
            Dict{String,Any}(
                "id" => "bus_1",
                "type" => "bus",
            ),
            Dict{String,Any}(
                "id" => "solar_1",
                "type" => "renewable",
            ),
            Dict{String,Any}(
                "id" => "battery_1",
                "type" => "battery",
                "charge_power_max_mw" => 5.0,
                "discharge_power_max_mw" => 5.0,
                "energy_min_mwh" => 0.0,
                "energy_max_mwh" => 5.0,
                "initial_energy_mwh" => 0.0,
                "charge_efficiency" => 1.0,
                "discharge_efficiency" => 1.0,
                "degradation_cost_per_mwh_delta_soc" => 0.0,
                "prevent_simultaneous_charge_discharge" => true,
                "terminal_condition" => "equal_initial",
                "terminal_energy_min_mwh" => nothing,
                "degradation_linear_delta_soc" => true,
            ),
            Dict{String,Any}(
                "id" => "grid_1",
                "type" => "grid",
            ),
        ],
        "edges" => [
            Dict{String,Any}("from" => "solar_1", "to" => "bus_1"),
            Dict{String,Any}("from" => "battery_1", "to" => "bus_1"),
            Dict{String,Any}("from" => "grid_1", "to" => "bus_1"),
        ],
        "time_series" => [
            Dict{String,Any}(
                "timestamp" => "2026-01-01T00:00:00",
                "duration_hours" => 1.0,
                "price_usd_per_mwh" => 0.0,
                "renewable_available_power_mw" => Dict{String,Any}("solar_1" => 5.0),
            ),
            Dict{String,Any}(
                "timestamp" => "2026-01-01T01:00:00",
                "duration_hours" => 1.0,
                "price_usd_per_mwh" => 100.0,
                "renewable_available_power_mw" => Dict{String,Any}("solar_1" => 0.0),
            ),
        ],
        "constraints" => Dict{String,Any}(),
        "solver" => Dict{String,Any}(
            "name" => "HiGHS",
            "options" => Dict{String,Any}(),
        ),
    )
end

function curtailment_system_case_document()
    document = minimal_system_case_document()
    document["case_name"] = "curtailment_system"

    battery = system_case_node(document, "battery_1")
    battery["charge_power_max_mw"] = 3.0
    battery["discharge_power_max_mw"] = 0.0
    battery["energy_max_mwh"] = 3.0
    battery["initial_energy_mwh"] = 0.0
    battery["terminal_condition"] = "none"
    battery["degradation_linear_delta_soc"] = false

    renewable = system_case_node(document, "solar_1")
    renewable["curtailment_penalty_usd_per_mwh"] = 2.0

    grid = system_case_node(document, "grid_1")
    grid["import_power_max_mw"] = 0.0
    grid["export_power_max_mw"] = 0.0

    document["time_series"] = [
        Dict{String,Any}(
            "timestamp" => "2026-01-01T00:00:00",
            "duration_hours" => 1.0,
            "price_usd_per_mwh" => 0.0,
            "renewable_available_power_mw" => Dict{String,Any}("solar_1" => 10.0),
        ),
    ]

    return document
end

function local_load_system_case_document()
    document = minimal_system_case_document()
    document["case_name"] = "local_load_system"
    add_load_node!(document; demands = [5.0, 2.0])

    battery = system_case_node(document, "battery_1")
    battery["charge_power_max_mw"] = 0.0
    battery["discharge_power_max_mw"] = 0.0
    battery["energy_max_mwh"] = 1.0
    battery["initial_energy_mwh"] = 0.0
    battery["degradation_linear_delta_soc"] = false

    document["time_series"][1]["price_usd_per_mwh"] = 100.0
    document["time_series"][1]["renewable_available_power_mw"] = Dict{String,Any}("solar_1" => 3.0)
    document["time_series"][2]["price_usd_per_mwh"] = 100.0
    document["time_series"][2]["renewable_available_power_mw"] = Dict{String,Any}("solar_1" => 0.0)

    return document
end

function grid_limited_system_case_document()
    document = minimal_system_case_document()
    document["case_name"] = "grid_limited_system"
    add_load_node!(document; demands = [5.0, 0.0])

    battery = system_case_node(document, "battery_1")
    battery["charge_power_max_mw"] = 0.0
    battery["discharge_power_max_mw"] = 0.0
    battery["energy_max_mwh"] = 1.0
    battery["initial_energy_mwh"] = 0.0
    battery["degradation_linear_delta_soc"] = false

    grid = system_case_node(document, "grid_1")
    grid["import_power_max_mw"] = 2.0
    grid["export_power_max_mw"] = 2.0

    document["time_series"][1]["price_usd_per_mwh"] = 100.0
    document["time_series"][1]["renewable_available_power_mw"] = Dict{String,Any}("solar_1" => 3.0)
    document["time_series"][2]["price_usd_per_mwh"] = 100.0
    document["time_series"][2]["renewable_available_power_mw"] = Dict{String,Any}("solar_1" => 5.0)

    return document
end

function grid_anti_sim_disabled_system_case_document()
    document = minimal_system_case_document()
    document["case_name"] = "grid_anti_sim_disabled_system"

    battery = system_case_node(document, "battery_1")
    battery["prevent_simultaneous_charge_discharge"] = false

    grid = system_case_node(document, "grid_1")
    grid["prevent_simultaneous_grid_import_export"] = false

    return document
end

function write_system_case_json(path::AbstractString, document)
    open(path, "w") do io
        JSON3.write(io, document)
        write(io, "\n")
    end

    return path
end

function write_minimal_system_case_json(case_dir::AbstractString; document = minimal_system_case_document())
    return write_system_case_json(joinpath(case_dir, "system_case.json"), document)
end

function system_case_node(document, node_id::AbstractString)
    return only(node for node in document["nodes"] if node["id"] == node_id)
end

function add_load_node!(document; demands = nothing)
    push!(document["nodes"], Dict{String,Any}("id" => "load_1", "type" => "load"))
    push!(document["edges"], Dict{String,Any}("from" => "load_1", "to" => "bus_1"))

    if demands !== nothing
        for (period, demand) in zip(document["time_series"], demands)
            period["load_demand_mw"] = Dict{String,Any}("load_1" => demand)
        end
    end

    return document
end

function system_case_validation_message(document)
    return mktempdir() do case_dir
        case_path = write_minimal_system_case_json(case_dir; document = document)
        try
            BESSDispatch.load_system_case(case_path)
            return nothing
        catch error
            return sprint(showerror, error)
        end
    end
end

function invalid_system_case_error_text(mutator)
    document = minimal_system_case_document()
    mutator(document)
    message = system_case_validation_message(document)
    return message === nothing ? "" : message
end

@testset "BESSDispatch package" begin
    @testset "can be imported" begin
        @test BESSDispatch isa Module
    end

    @testset "single-BESS MVP public contract remains available" begin
        exported_names = Set(names(BESSDispatch))
        required_public_names = [
            :BESSParameters,
            :TimeSeriesData,
            :ConstraintConfig,
            :SolverConfig,
            :HorizonConfig,
            :CaseData,
            :DispatchModel,
            :DispatchResult,
            :RunOutput,
            :build_dispatch_model,
            :load_case,
            :run_case,
            :solve_dispatch,
            :validate_case_data,
            :write_run_outputs,
        ]

        @test all(name -> name in exported_names, required_public_names)

        case_dir = joinpath(@__DIR__, "..", "data", "cases", "arbitrage_mvp")
        @test isfile(joinpath(case_dir, "config.yaml"))
        @test isfile(joinpath(case_dir, "bess.yaml"))
        @test isfile(joinpath(case_dir, "timeseries.csv"))
        @test !isfile(joinpath(case_dir, "system_case.json"))

        mktempdir() do output_root
            run_output = BESSDispatch.run_case(
                case_dir;
                output_root = output_root,
                run_timestamp = DateTime("2026-01-02T03:04:05"),
            )

            @test run_output.result.termination_status == "OPTIMAL"
            @test isfile(run_output.dispatch_path)
            @test isfile(run_output.summary_path)
            @test isfile(run_output.config_resolved_path)
            @test isfile(run_output.model_metadata_path)
        end
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

    @testset "runs minimal hybrid system case end to end" begin
        mktempdir() do case_dir
            case_path = write_minimal_system_case_json(case_dir)

            system_case = BESSDispatch.load_system_case(case_path)
            @test system_case.schema_version == "bess_system_dispatch.v1"
            @test Set(node.id for node in system_case.nodes) == Set(["bus_1", "solar_1", "battery_1", "grid_1"])

            optimization_case = BESSDispatch.normalize_system_case(system_case)
            @test optimization_case.case_name == "minimal_hybrid_system"
            @test optimization_case.bus_id == "bus_1"
            @test [asset.id for asset in optimization_case.renewables] == ["solar_1"]
            @test optimization_case.renewables[1].curtailment_penalty_usd_per_mwh == 0.0
            @test [asset.id for asset in optimization_case.batteries] == ["battery_1"]
            @test [asset.id for asset in optimization_case.grids] == ["grid_1"]
            @test optimization_case.renewable_available_power_mw == [5.0 0.0]

            result = BESSDispatch.solve_system_dispatch(optimization_case)
            @test result.termination_status == "OPTIMAL"
            @test isapprox(result.objective_value_usd, 500.0; atol = OBJECTIVE_TOLERANCE_USD)

            output_root = joinpath(case_dir, "outputs")
            run_output = BESSDispatch.run_system_case(
                case_path;
                output_root = output_root,
                run_timestamp = DateTime("2026-01-02T03:04:05"),
            )

            @test run_output.case_name == "minimal_hybrid_system"
            @test run_output.output_dir == joinpath(output_root, "minimal_hybrid_system", "20260102T030405000")
            @test isfile(run_output.dispatch_path)
            @test isfile(run_output.asset_dispatch_path)
            @test isfile(run_output.summary_path)
            @test isfile(run_output.system_case_resolved_path)
            @test isfile(run_output.model_metadata_path)

            dispatch_rows = collect(CSV.File(run_output.dispatch_path))
            @test length(dispatch_rows) == 2
            @test propertynames(dispatch_rows[1]) == [
                :timestamp,
                :duration_hours,
                :price_usd_per_mwh,
                :grid_import_mw,
                :grid_export_mw,
                :net_grid_export_mw,
                :renewable_used_mw,
                :renewable_curtailed_mw,
                :load_demand_mw,
                :battery_charge_mw,
                :battery_discharge_mw,
                :battery_net_discharge_mw,
                :battery_energy_mwh,
                :battery_delta_soc_abs_mwh,
                :market_value_usd,
                :battery_degradation_cost_usd,
                :curtailment_penalty_usd,
                :period_profit_usd,
            ]
            @test isapprox(dispatch_rows[1].renewable_used_mw, 5.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_rows[1].renewable_curtailed_mw, 0.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_rows[1].battery_charge_mw, 5.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_rows[2].battery_discharge_mw, 5.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_rows[2].grid_export_mw, 5.0; atol = POWER_TOLERANCE_MW)

            for row in dispatch_rows
                supply = row.grid_import_mw + row.renewable_used_mw + row.battery_discharge_mw
                consumption = row.grid_export_mw + row.battery_charge_mw + row.load_demand_mw
                @test isapprox(supply, consumption; atol = POWER_TOLERANCE_MW)
            end

            asset_rows = collect(CSV.File(run_output.asset_dispatch_path))
            @test Set(string(row.asset_id) for row in asset_rows) == Set(["solar_1", "battery_1", "grid_1"])
            @test any(row -> string(row.asset_id) == "solar_1" && isapprox(row.renewable_used_mw, 5.0; atol = POWER_TOLERANCE_MW), asset_rows)
            @test any(row -> string(row.asset_id) == "battery_1" && isapprox(row.battery_discharge_mw, 5.0; atol = POWER_TOLERANCE_MW), asset_rows)
            @test any(row -> string(row.asset_id) == "grid_1" && isapprox(row.grid_export_mw, 5.0; atol = POWER_TOLERANCE_MW), asset_rows)

            summary = JSON3.read(read(run_output.summary_path, String))
            @test string(summary.case_name) == "minimal_hybrid_system"
            @test string(summary.termination_status) == "OPTIMAL"
            @test summary.objective_value_usd == run_output.result.objective_value_usd
            @test string(summary.source_identifiers.system_case) == abspath(case_path)

            resolved_case = JSON3.read(read(run_output.system_case_resolved_path, String))
            @test string(resolved_case.schema_version) == "bess_system_dispatch.v1"
            @test string(resolved_case.case_name) == "minimal_hybrid_system"

            metadata = JSON3.read(read(run_output.model_metadata_path, String))
            @test string(metadata.model_name) == "one_bus_hybrid_system_dispatch"
            @test metadata.number_of_periods == 2
            @test collect(string.(metadata.asset_ids.batteries)) == ["battery_1"]
            @test collect(string.(metadata.asset_ids.renewables)) == ["solar_1"]
            @test collect(string.(metadata.asset_ids.grids)) == ["grid_1"]
        end
    end

    @testset "curtails excess renewable generation and applies configured penalty" begin
        mktempdir() do case_dir
            case_path = write_minimal_system_case_json(case_dir; document = curtailment_system_case_document())

            optimization_case = BESSDispatch.normalize_system_case(BESSDispatch.load_system_case(case_path))
            @test optimization_case.renewables[1].curtailment_penalty_usd_per_mwh == 2.0

            result = BESSDispatch.solve_system_dispatch(optimization_case)
            @test result.termination_status == "OPTIMAL"
            @test isapprox(result.p_renewable_used_mw[1, 1], 3.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(result.p_renewable_curtailed_mw[1, 1], 7.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(result.p_battery_charge_mw[1, 1], 3.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(result.curtailment_penalty_usd[1, 1], 14.0; atol = OBJECTIVE_TOLERANCE_USD)
            @test isapprox(result.objective_value_usd, -14.0; atol = OBJECTIVE_TOLERANCE_USD)

            run_output = BESSDispatch.run_system_case(
                case_path;
                output_root = joinpath(case_dir, "outputs"),
                run_timestamp = DateTime("2026-01-02T03:04:05"),
            )

            dispatch_row = only(collect(CSV.File(run_output.dispatch_path)))
            @test isapprox(dispatch_row.renewable_used_mw, 3.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_row.renewable_curtailed_mw, 7.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_row.curtailment_penalty_usd, 14.0; atol = OBJECTIVE_TOLERANCE_USD)
            @test isapprox(dispatch_row.period_profit_usd, -14.0; atol = OBJECTIVE_TOLERANCE_USD)

            renewable_row = only(row for row in CSV.File(run_output.asset_dispatch_path) if string(row.asset_id) == "solar_1")
            @test string(renewable_row.asset_type) == "renewable"
            @test isapprox(renewable_row.renewable_used_mw, 3.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(renewable_row.renewable_curtailed_mw, 7.0; atol = POWER_TOLERANCE_MW)
        end
    end

    @testset "serves local load and reports demand in system outputs" begin
        mktempdir() do case_dir
            case_path = write_minimal_system_case_json(case_dir; document = local_load_system_case_document())

            system_case = BESSDispatch.load_system_case(case_path)
            optimization_case = BESSDispatch.normalize_system_case(system_case)
            @test [asset.id for asset in optimization_case.loads] == ["load_1"]
            @test optimization_case.load_demand_mw == [5.0 2.0]

            result = BESSDispatch.solve_system_dispatch(optimization_case)
            @test result.termination_status == "OPTIMAL"
            @test isapprox(result.p_renewable_used_mw[1, 1], 3.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(result.p_grid_import_mw[1, 1], 2.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(result.p_grid_import_mw[1, 2], 2.0; atol = POWER_TOLERANCE_MW)

            run_output = BESSDispatch.run_system_case(
                case_path;
                output_root = joinpath(case_dir, "outputs"),
                run_timestamp = DateTime("2026-01-02T03:04:05"),
            )

            dispatch_rows = collect(CSV.File(run_output.dispatch_path))
            @test isapprox(dispatch_rows[1].load_demand_mw, 5.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_rows[2].load_demand_mw, 2.0; atol = POWER_TOLERANCE_MW)
            for row in dispatch_rows
                supply = row.grid_import_mw + row.renewable_used_mw + row.battery_discharge_mw
                consumption = row.grid_export_mw + row.battery_charge_mw + row.load_demand_mw
                @test isapprox(supply, consumption; atol = POWER_TOLERANCE_MW)
            end

            asset_rows = collect(CSV.File(run_output.asset_dispatch_path))
            @test Set(string(row.asset_id) for row in asset_rows) == Set(["solar_1", "battery_1", "grid_1", "load_1"])
            @test any(
                row -> string(row.asset_id) == "load_1" && isapprox(row.load_demand_mw, 5.0; atol = POWER_TOLERANCE_MW),
                asset_rows,
            )

            metadata = JSON3.read(read(run_output.model_metadata_path, String))
            @test collect(string.(metadata.asset_ids.loads)) == ["load_1"]
        end
    end

    @testset "enforces grid limits and default import export anti-simultaneity" begin
        mktempdir() do case_dir
            case_path = write_minimal_system_case_json(case_dir; document = grid_limited_system_case_document())

            optimization_case = BESSDispatch.normalize_system_case(BESSDispatch.load_system_case(case_path))
            @test optimization_case.grids[1].import_power_max_mw == 2.0
            @test optimization_case.grids[1].export_power_max_mw == 2.0
            @test optimization_case.grids[1].prevent_simultaneous_grid_import_export == true

            dispatch_model = BESSDispatch.build_system_dispatch_model(optimization_case)
            @test dispatch_model.is_grid_importing !== nothing
            @test all(JuMP.is_binary(dispatch_model.is_grid_importing[1, period]) for period in 1:2)

            result = BESSDispatch.solve_system_dispatch(optimization_case)
            @test result.termination_status == "OPTIMAL"
            @test isapprox(result.p_grid_import_mw[1, 1], 2.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(result.p_grid_export_mw[1, 1], 0.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(result.p_grid_import_mw[1, 2], 0.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(result.p_grid_export_mw[1, 2], 2.0; atol = POWER_TOLERANCE_MW)
            @test all(
                !(
                    result.p_grid_import_mw[1, period] > POWER_TOLERANCE_MW &&
                    result.p_grid_export_mw[1, period] > POWER_TOLERANCE_MW
                ) for period in 1:2
            )

            run_output = BESSDispatch.run_system_case(
                case_path;
                output_root = joinpath(case_dir, "outputs"),
                run_timestamp = DateTime("2026-01-02T03:04:05"),
            )

            dispatch_rows = collect(CSV.File(run_output.dispatch_path))
            @test isapprox(dispatch_rows[1].grid_import_mw, 2.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_rows[1].grid_export_mw, 0.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_rows[1].net_grid_export_mw, -2.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_rows[2].grid_import_mw, 0.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_rows[2].grid_export_mw, 2.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(dispatch_rows[2].net_grid_export_mw, 2.0; atol = POWER_TOLERANCE_MW)

            grid_rows = [row for row in CSV.File(run_output.asset_dispatch_path) if string(row.asset_id) == "grid_1"]
            @test length(grid_rows) == 2
            @test isapprox(grid_rows[1].grid_import_mw, 2.0; atol = POWER_TOLERANCE_MW)
            @test isapprox(grid_rows[2].grid_export_mw, 2.0; atol = POWER_TOLERANCE_MW)
        end
    end

    @testset "disabled grid anti-simultaneity remains bounded without grid binaries" begin
        mktempdir() do case_dir
            case_path = write_minimal_system_case_json(
                case_dir;
                document = grid_anti_sim_disabled_system_case_document(),
            )

            optimization_case = BESSDispatch.normalize_system_case(BESSDispatch.load_system_case(case_path))
            @test optimization_case.grids[1].prevent_simultaneous_grid_import_export == false

            dispatch_model = BESSDispatch.build_system_dispatch_model(optimization_case)
            @test dispatch_model.is_grid_importing === nothing
            @test isfinite(JuMP.upper_bound(dispatch_model.p_grid_import_mw[1, 1]))
            @test isfinite(JuMP.upper_bound(dispatch_model.p_grid_export_mw[1, 1]))
            @test all(!JuMP.is_binary(variable) for variable in JuMP.all_variables(dispatch_model.model))

            result = BESSDispatch.solve_system_dispatch(optimization_case)
            @test result.termination_status == "OPTIMAL"
        end
    end

    @testset "system dispatch public API and CLI contract are stable" begin
        exported_names = Set(names(BESSDispatch))
        required_public_names = [
            :SystemGraphData,
            :SystemOptimizationData,
            :SystemDispatchResult,
            :SystemRunOutput,
            :load_system_case,
            :normalize_system_case,
            :build_system_dispatch_model,
            :solve_system_dispatch,
            :run_system_case,
            :write_system_run_outputs,
        ]
        @test all(name -> name in exported_names, required_public_names)

        script_path = normpath(joinpath(@__DIR__, "..", "scripts", "run_system_case.jl"))
        @test isfile(script_path)

        mktempdir() do case_dir
            case_path = write_minimal_system_case_json(case_dir)
            output_root = joinpath(case_dir, "outputs")

            stdout = read(system_cli_command(script_path, case_path, output_root), String)
            payload = JSON3.read(stdout)

            @test string(payload.case_name) == "minimal_hybrid_system"
            @test string(payload.run_timestamp) == "20260102T030405000"
            @test string(payload.output_dir) == joinpath(output_root, "minimal_hybrid_system", "20260102T030405000")
            @test isfile(string(payload.summary_path))
            @test string(payload.termination_status) == "OPTIMAL"
        end

        mktempdir() do case_dir
            document = minimal_system_case_document()
            delete!(document, "schema_version")
            case_path = write_minimal_system_case_json(case_dir; document = document)
            output_root = joinpath(case_dir, "outputs")
            stdout_path = joinpath(case_dir, "stdout.txt")
            stderr_path = joinpath(case_dir, "stderr.txt")

            process = open(stdout_path, "w") do stdout_io
                open(stderr_path, "w") do stderr_io
                    return run(pipeline(
                        ignorestatus(system_cli_command(script_path, case_path, output_root));
                        stdout = stdout_io,
                        stderr = stderr_io,
                    ))
                end
            end

            @test !success(process)
            @test isempty(strip(read(stdout_path, String)))
            error_payload = JSON3.read(read(stderr_path, String))
            @test string(error_payload.status) == "error"
            @test occursin("schema_version is required", string(error_payload.message))
        end
    end

    @testset "rejects invalid system battery bounds before model construction" begin
        document = minimal_system_case_document()
        battery = system_case_node(document, "battery_1")
        battery["energy_min_mwh"] = 5.0
        battery["energy_max_mwh"] = 5.0

        @test occursin("battery battery_1 energy_min_mwh must be less than energy_max_mwh", system_case_validation_message(document))
    end

    @testset "rejects invalid system graph and time-series inputs" begin
        @test occursin("schema_version is required", invalid_system_case_error_text(
            document -> delete!(document, "schema_version"),
        ))
        @test occursin("schema_version must be bess_system_dispatch.v1", invalid_system_case_error_text(
            document -> document["schema_version"] = "bess_system_dispatch.v2",
        ))
        @test occursin("node id battery_1 is duplicated", invalid_system_case_error_text(
            document -> system_case_node(document, "solar_1")["id"] = "battery_1",
        ))
        @test occursin("unsupported type thermal", invalid_system_case_error_text(
            document -> system_case_node(document, "solar_1")["type"] = "thermal",
        ))
        @test occursin("exactly one bus or PCC node; found 0", invalid_system_case_error_text(
            document -> filter!(node -> node["type"] != "bus", document["nodes"]),
        ))
        @test occursin("exactly one bus or PCC node; found 2", invalid_system_case_error_text(
            document -> push!(document["nodes"], Dict{String,Any}("id" => "bus_2", "type" => "pcc")),
        ))
        @test occursin("edge references missing node id missing_node", invalid_system_case_error_text(
            document -> document["edges"][1]["from"] = "missing_node",
        ))
        @test occursin("asset node battery_1 is disconnected from bus bus_1", invalid_system_case_error_text(
            document -> filter!(edge -> edge["from"] != "battery_1" && edge["to"] != "battery_1", document["edges"]),
        ))
        @test occursin("field capacity_mw is not supported", invalid_system_case_error_text(
            document -> document["edges"][1]["capacity_mw"] = 5.0,
        ))
        @test occursin("time_series must contain at least one period", invalid_system_case_error_text(
            document -> document["time_series"] = [],
        ))
        @test occursin("duration_hours[1] must be positive", invalid_system_case_error_text(
            document -> document["time_series"][1]["duration_hours"] = 0.0,
        ))
        @test occursin("price_usd_per_mwh", invalid_system_case_error_text(
            document -> delete!(document["time_series"][1], "price_usd_per_mwh"),
        ))
        @test occursin("price_usd_per_mwh[1] must be finite", invalid_system_case_error_text(
            document -> document["time_series"][1]["price_usd_per_mwh"] = "NaN",
        ))
        @test occursin("timestamps must be strictly increasing", invalid_system_case_error_text(
            document -> document["time_series"][2]["timestamp"] = "2026-01-01T00:00:00",
        ))
        @test occursin("battery battery_1 charge_efficiency must be in (0, 1]", invalid_system_case_error_text(
            document -> system_case_node(document, "battery_1")["charge_efficiency"] = 0.0,
        ))
        @test occursin("battery battery_1 terminal_condition must be one of", invalid_system_case_error_text(
            document -> system_case_node(document, "battery_1")["terminal_condition"] = "target_energy",
        ))
        @test occursin("battery battery_1 degradation_cost_per_mwh_delta_soc must be nonnegative", invalid_system_case_error_text(
            document -> system_case_node(document, "battery_1")["degradation_cost_per_mwh_delta_soc"] = -1.0,
        ))
        @test occursin("renewable solar_1 curtailment_penalty_usd_per_mwh must be nonnegative", invalid_system_case_error_text(
            document -> system_case_node(document, "solar_1")["curtailment_penalty_usd_per_mwh"] = -1.0,
        ))
        @test occursin("grid grid_1 import_power_max_mw must be nonnegative", invalid_system_case_error_text(
            document -> system_case_node(document, "grid_1")["import_power_max_mw"] = -1.0,
        ))
        @test occursin("load_demand_mw for asset load_1 is required", invalid_system_case_error_text(
            document -> add_load_node!(document),
        ))
        @test occursin("load_demand_mw[load_1] at time_series[1] must be nonnegative", invalid_system_case_error_text(
            document -> add_load_node!(document; demands = [-1.0, 1.0]),
        ))
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

    @testset "README documents system dispatch API and CLI flow" begin
        readme_path = joinpath(@__DIR__, "..", "README.md")

        @test isfile(readme_path)

        if isfile(readme_path)
            readme = read(readme_path, String)

            @test occursin("BESSDispatch.run_system_case", readme)
            @test occursin("BESSDispatch.load_system_case", readme)
            @test occursin("scripts/run_system_case.jl", readme)
            @test occursin("--output-root", readme)
            @test occursin("summary_path", readme)
            @test occursin("termination_status", readme)
            @test occursin("asset_dispatch.csv", readme)
        end
    end
end
