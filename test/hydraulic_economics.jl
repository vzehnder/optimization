using Test, EnergyDispatch, JSON3, CSV

@testset "Hydraulic generation follows CMg with limited water" begin
    mktempdir() do dir
        document = JSON3.read(read(joinpath(@__DIR__, "../tests/fixtures/reg002_hydraulic.json"), String), Dict{String,Any})
        document["hydraulic_objective"] = "market_value"
        # 0.144 hm3 can supply the 40 m3/s, 30 MW turbine for exactly one hour.
        document["hydraulic_network"]["nodes"][1]["reservoir"]["initial_storage_hm3"] = 0.144
        for (period, price) in zip(document["time_series"], [10.0, 100.0, 20.0, -5.0])
            period["price_usd_per_mwh"] = price
        end
        path = joinpath(dir, "case.json")
        write(path, JSON3.write(document))
        output = EnergyDispatch.run_system_case(path; output_root=dir)
        rows = collect(CSV.File(output.dispatch_path))
        @test [row.total_hydro_power_mw for row in rows] ≈ [0.0, 30.0, 0.0, 0.0] atol=1e-6
        @test output.result.objective_value_usd ≈ 3000.0
        @test [row.price_usd_per_mwh for row in rows] == [10.0, 100.0, 20.0, -5.0]
        @test sum(row.hydro_revenue_usd for row in rows) ≈ 3000.0
        summary = JSON3.read(read(output.summary_path, String), Dict{String,Any})
        @test summary["hydraulic_v3_totals"]["total_revenue_usd"] ≈ 3000.0
    end
end

@testset "Terminal water value trades off revenue and respects final storage constraints" begin
    for (water_value, condition, minimum, expected_revenue, expected_storage) in [
        (0.0, "none", 0.0, 3000.0, 0.0),
        (10000.0, "none", 0.0, 3000.0, 0.0),
        (50000.0, "none", 0.0, 0.0, 0.144),
        (50000.0, "equal_initial", 0.0, 0.0, 0.144),
        (10000.0, "min_terminal", 0.072, 1500.0, 0.072),
    ]
        mktempdir() do dir
            document = JSON3.read(read(joinpath(@__DIR__, "../tests/fixtures/reg002_hydraulic.json"), String), Dict{String,Any})
            document["hydraulic_objective"] = "market_value"
            document["solver"]["options"]["mip_rel_gap"] = 0.01
            params = document["hydraulic_network"]["nodes"][1]["reservoir"]
            params["initial_storage_hm3"] = 0.144
            params["terminal_water_value_usd_per_hm3"] = water_value
            params["terminal_condition"] = condition
            params["terminal_storage_min_hm3"] = minimum
            for (period, price) in zip(document["time_series"], [10.0, 100.0, 20.0, -5.0])
                period["price_usd_per_mwh"] = price
            end
            path = joinpath(dir, "case.json")
            write(path, JSON3.write(document))
            output = EnergyDispatch.run_system_case(path; output_root=dir)
            summary = JSON3.read(read(output.summary_path, String), Dict{String,Any})
            totals = summary["hydraulic_v3_totals"]
            @test totals["total_revenue_usd"] ≈ expected_revenue atol=1e-6
            @test totals["final_storage_hm3"] ≈ expected_storage atol=1e-8
            @test totals["terminal_water_value_usd"] ≈ water_value * expected_storage atol=1e-6
            @test output.result.objective_value_usd ≈ expected_revenue + water_value * expected_storage atol=1e-6
            rows = collect(CSV.File(output.dispatch_path))
            @test all(row.total_hydro_terminal_water_value_usd == 0 for row in rows[1:end-1])
            @test rows[end].total_hydro_terminal_water_value_usd ≈ water_value * expected_storage atol=1e-6
        end
    end
end

@testset "Hydraulic MIP uses the configured relative stopping gap" begin
    mktempdir() do dir
        document = JSON3.read(read(joinpath(@__DIR__, "../tests/fixtures/reg002_hydraulic.json"), String), Dict{String,Any})
        document["hydraulic_objective"] = "market_value"
        document["solver"]["options"]["mip_rel_gap"] = 0.01
        document["hydraulic_network"]["nodes"][1]["reservoir"]["initial_storage_hm3"] = 0.144
        # A nonconvex power curve requires the mixed-integer formulation.
        insert!(document["hydraulic_network"]["units"][1]["curves"]["flow_power"], 2,
                Dict("flow_m3s" => 20.0, "power_mw" => 10.0))
        for (period, price) in zip(document["time_series"], [10.0, 100.0, 20.0, -5.0])
            period["price_usd_per_mwh"] = price
        end
        path = joinpath(dir, "case.json")
        write(path, JSON3.write(document))
        solver_log_path = joinpath(dir, "solver.log")
        output = EnergyDispatch.run_system_case(path; output_root=dir, solver_log_path)
        @test output.result.objective_value_usd ≈ 3000.0
        @test occursin(r"Gap[^\n]*tolerance[^\n]*1%", read(solver_log_path, String))
    end
end
