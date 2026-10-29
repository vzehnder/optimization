using Test, EnergyDispatch, JSON3, CSV

function seepage_case()
    document = JSON3.read(read(joinpath(@__DIR__, "../tests/fixtures/reg002_hydraulic.json"), String), Dict{String,Any})
    resize!(document["time_series"], 2)
    network = document["hydraulic_network"]
    source = network["nodes"][1]
    source["reservoir"]["terminal_water_value_usd_per_hm3"] = 1e6
    source["curves"]["storage_elevation"] = [
        Dict("storage_hm3" => v, "elevation_masl" => h) for (v, h) in ((0, 700), (5, 710), (20, 755))]
    destination = deepcopy(source)
    destination["id"] = "lower"
    destination["reservoir"]["initial_storage_hm3"] = 0
    push!(network["nodes"], destination)
    for period in document["time_series"]
        period["natural_inflow_m3s"]["lower"] = 0
    end
    push!(network["reaches"], Dict("id" => "filtration", "from_node" => "reservoir", "to_node" => "lower", "type" => "other",
        "flow_behavior" => Dict("kind" => "seepage", "level_timing" => "start", "curve" => [
            Dict("elevation_masl" => h, "flow_m3s" => q) for (h, q) in ((700, 0), (720, 2), (755, 9))])))
    return document
end

function run_seepage_case(document, dir)
    path = joinpath(dir, "case.json")
    write(path, JSON3.write(document))
    return EnergyDispatch.run_system_case(path; output_root=dir)
end

@testset "Closing elevation is solved together with water balance and recorded in run metadata" begin
    mktempdir() do dir
        document = seepage_case()
        document["hydraulic_network"]["reaches"][end]["flow_behavior"]["level_timing"] = "end"
        result = run_seepage_case(document, dir)
        rows = collect(CSV.File(result.asset_dispatch_path))
        # Q = 0.6 * (10 - 0.0036Q) - 3; the next closing level uses the new volume.
        @test [r.hydraulic_flow_m3s for r in rows if r.asset_id == "filtration"] ≈ [2.9935339666320746, 2.9870818697933212]
        @test last([r.hydro_storage_hm3 for r in rows if r.asset_id == "reservoir"]) ≈ 9.978469782988869
        metadata = JSON3.read(read(result.model_metadata_path, String), Dict{String,Any})
        @test metadata["active_constraint_flags"]["hydraulic_reach_seepage"]
        @test metadata["hydraulic_reach_behaviors"]["filtration"] == Dict("kind" => "seepage", "level_timing" => "end", "source_node" => "reservoir")
    end
end

@testset "Filtration follows adjacent curve segments and transfers the same water to the second reservoir" begin
    mktempdir() do dir
        document = seepage_case()
        result = run_seepage_case(document, dir)
        assets = collect(CSV.File(result.asset_dispatch_path))
        # Worked example: V=10 gives H=725 and Q=3. One hour transfers 0.0108 hm3.
        # Next start: V=9.9892, H=724.9676, Q=2.99352; total transfer 0.021576672 hm3.
        @test [r.hydraulic_flow_m3s for r in assets if r.asset_id == "filtration"] ≈ [3.0, 2.99352]
        @test [r.hydro_storage_hm3 for r in assets if r.asset_id == "reservoir"] ≈ [9.9892, 9.978423328]
        @test [r.hydro_storage_hm3 for r in assets if r.asset_id == "lower"] ≈ [0.0108, 0.021576672]
        @test JSON3.read(read(result.system_case_resolved_path, String), Dict{String,Any}) == document
    end
end

@testset "Generation also respects all points of a flow-power table" begin
    mktempdir() do dir
        document = seepage_case()
        network = document["hydraulic_network"]
        network["nodes"][1]["reservoir"]["terminal_water_value_usd_per_hm3"] = 0
        network["reaches"][1]["flow_behavior"] = Dict("kind" => "seepage", "level_timing" => "start", "curve" => [
            Dict("elevation_masl" => 700, "flow_m3s" => 20), Dict("elevation_masl" => 755, "flow_m3s" => 20)])
        network["units"][1]["curves"]["flow_power"] = [Dict("flow_m3s" => q, "power_mw" => p) for (q, p) in ((0, 0), (10, 8), (40, 20))]
        result = run_seepage_case(document, dir)
        @test [r.total_hydro_power_mw for r in CSV.File(result.dispatch_path)] ≈ [12.0, 12.0]
        metadata = JSON3.read(read(result.model_metadata_path, String), Dict{String,Any})
        @test metadata["active_constraint_flags"]["hydraulic_unit_piecewise_flow_power"]
        @test !metadata["active_constraint_flags"]["hydraulic_unit_linear_flow_power"]
    end
end

@testset "A standalone run rejects invalid filtration before solving" begin
    for change! in (
        r -> r["flow_behavior"]["curve"][1]["elevation_masl"] = 710,
        r -> r["flow_behavior"]["curve"][1]["flow_m3s"] = -1,
        r -> r["flow_behavior"]["level_timing"] = "unknown",
        r -> r["from_node"] = "intake",
    )
        mktempdir() do dir
            document = seepage_case()
            change!(document["hydraulic_network"]["reaches"][end])
            @test_throws ArgumentError run_seepage_case(document, dir)
        end
    end
end
