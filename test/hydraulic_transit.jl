using Test, BESSDispatch, JSON3, CSV

function transit_case()
    document = JSON3.read(read(joinpath(@__DIR__, "../tests/fixtures/reg002_hydraulic.json"), String), Dict{String,Any})
    document["solver"]["options"]["output_flag"] = false
    document["time_series"] = [
        Dict("timestamp" => "2026-01-01T" * stamp, "duration_hours" => duration,
             "natural_inflow_m3s" => Dict("reservoir" => 0))
        for (stamp, duration) in (("00:00:00", 0.5), ("00:30:00", 1.5), ("02:00:00", 1.0), ("03:00:00", 2.0))
    ]
    document["hydraulic_network"]["nodes"][1]["reservoir"]["terminal_water_value_usd_per_hm3"] = 1e6
    merge!(document["hydraulic_network"]["reaches"][1],
           Dict("routing_method" => "fixed_delay", "travel_time_hours" => 0.75, "flow_min_m3s" => 8))
    document
end

@testset "Delayed transport rejects time grids with gaps or overlaps" begin
    for timestamp in ("2026-01-01T00:15:00", "2026-01-01T00:45:00")
        document = transit_case()
        document["time_series"][2]["timestamp"] = timestamp
        @test_throws ArgumentError BESSDispatch.validate_hydraulic_v3_system_case_document(document)
    end
end

function solve_transit(document, dir, name="transit")
    path = joinpath(dir, name * ".json")
    write(path, JSON3.write(document))
    BESSDispatch.run_system_case(path; output_root=joinpath(dir, name))
end

@testset "Fractional travel time conserves water across changing interval sizes" begin
    mktempdir() do dir
        result = solve_transit(transit_case(), dir)
        rows = collect(CSV.File(result.asset_dispatch_path))
        reach = filter(r -> r.asset_id == "reach", rows)
        # Eight m3/s depart for five hours. Nothing arrives before 00:45;
        # ten m3/s-hours arrive during 00:30–02:00; 0.75 hours remain in transit.
        @test [r.hydraulic_flow_m3s for r in reach] ≈ fill(8, 4)
        @test [r.hydraulic_arrival_flow_m3s for r in reach] ≈ [0, 20 / 3, 8, 8]
        @test [r.total_hydro_turbine_flow_m3s for r in CSV.File(result.dispatch_path)] ≈ [0, 20 / 3, 8, 8]
        @test last(reach).hydraulic_in_transit_hm3 ≈ 0.0216
        @test last(CSV.File(result.dispatch_path)).total_hydro_storage_hm3 ≈ 9.856
        @test sum(r.hydraulic_arrival_volume_hm3 for r in reach) ≈ 0.1224
    end
end

@testset "Initial water arrives without withdrawal and the remaining water carries into another grid" begin
    mktempdir() do dir
        document = transit_case()
        document["hydraulic_network"]["reaches"][1]["initial_flow_m3s"] = 4.0
        result = solve_transit(document, dir, "initial_water")
        rows = filter(r -> r.asset_id == "reach", collect(CSV.File(result.asset_dispatch_path)))
        @test [r.hydraulic_arrival_flow_m3s for r in rows] ≈ [4, 22 / 3, 8, 8]
        @test last(rows).hydraulic_in_transit_hm3 ≈ 0.0216
        transport = JSON3.read(read(result.summary_path, String), Dict{String,Any})["hydraulic_transport"]["reach"]
        @test transport["initial_volume_hm3"] ≈ 0.0108
        @test transport["final_volume_hm3"] ≈ 0.0216
        @test transport["terminal_arrivals"] == [Dict("timestamp" => "2026-01-01T05:00:00", "duration_hours" => 0.75, "value_m3s" => 8.0)]

        continuation = transit_case()
        continuation["time_series"] = [
            Dict("timestamp" => "2026-01-01T05:00:00", "duration_hours" => 0.25, "natural_inflow_m3s" => Dict("reservoir" => 0)),
            Dict("timestamp" => "2026-01-01T05:15:00", "duration_hours" => 1.0, "natural_inflow_m3s" => Dict("reservoir" => 0)),
        ]
        merge!(continuation["hydraulic_network"]["reaches"][1],
               Dict("flow_min_m3s" => 0, "initial_arrivals" => transport["terminal_arrivals"]))
        next_result = solve_transit(continuation, dir, "continuation")
        next_rows = filter(r -> r.asset_id == "reach", collect(CSV.File(next_result.asset_dispatch_path)))
        @test [r.hydraulic_arrival_flow_m3s for r in next_rows] ≈ [8, 4]
        @test last(next_rows).hydraulic_in_transit_hm3 ≈ 0 atol=1e-10
        @test last(CSV.File(next_result.dispatch_path)).total_hydro_storage_hm3 ≈ 10
    end
end
