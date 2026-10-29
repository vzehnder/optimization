using Test, EnergyDispatch, JSON3, CSV

reach_case() = JSON3.read(read(joinpath(@__DIR__, "../tests/fixtures/reg002_hydraulic.json"), String), Dict{String,Any})
function solve_reaches(document, dir, name)
    path = joinpath(dir, name * ".json")
    write(path, JSON3.write(document))
    EnergyDispatch.run_system_case(path; output_root=joinpath(dir, name))
end

@testset "Independent non-generation flows obey sums and conserve reservoir water" begin
    mktempdir() do dir
        document = reach_case()
        network = document["hydraulic_network"]
        network["nodes"][1]["reservoir"]["terminal_water_value_usd_per_hm3"] = 1e6
        for (key, minimum) in (("b", 3.0), ("c", 2.0))
            push!(network["reaches"], Dict("id" => key, "type" => "bypass", "from_node" => "reservoir", "to_node" => "tailrace", "flow_min_m3s" => minimum))
        end
        objects = [Dict("id" => id, "kind" => "hydraulic_reach", "reach_key" => key) for (id, key) in ((1, "reach"), (2, "b"), (3, "c"))]
        term(id, coefficient, t) = Dict("object_id" => id, "variable" => "caudal", "period" => t, "coefficient" => coefficient, "unit" => "dimensionless")
        document["component_rules"] = Dict(
            "version" => "affine_hydraulic.v1", "objects" => objects,
            "grid" => [Dict("timestamp" => p["timestamp"], "duration_hours" => p["duration_hours"]) for p in document["time_series"]],
            "rows" => [Dict("application_id" => "a1", "revision_id" => "r1", "name" => "suma", "line" => 3,
                            "period" => t, "relation" => ">=", "unit" => "m3_per_s", "constant" => 0,
                            "terms" => [term(1, 1, t), term(2, -1, t), term(3, -1, t)]) for t in 0:3])
        result = solve_reaches(document, dir, "sum_of_reaches")
        assets = collect(CSV.File(result.asset_dispatch_path))
        flow(key) = [r.hydraulic_flow_m3s for r in assets if r.asset_type == "hydraulic_reach" && r.asset_id == key]
        @test flow("reach") ≈ fill(5, 4)
        @test flow("b") ≈ fill(3, 4)
        @test flow("c") ≈ fill(2, 4)
        @test [r.total_hydro_turbine_flow_m3s for r in CSV.File(result.dispatch_path)] ≈ fill(5, 4)
        @test last(CSV.File(result.dispatch_path)).total_hydro_storage_hm3 ≈ 10 - 4 * (5 + 3 + 2) * 0.0036
        @test JSON3.read(read(result.system_case_resolved_path, String), Dict{String,Any})["component_rules"] == document["component_rules"]
        for mutate! in (d -> d["component_rules"]["objects"][1]["reach_key"] = "missing",
                        d -> d["component_rules"]["rows"][1]["terms"][1]["variable"] = "potencia",
                        d -> push!(d["hydraulic_network"]["reaches"], deepcopy(d["hydraulic_network"]["reaches"][1])))
            invalid = deepcopy(document)
            mutate!(invalid)
            @test_throws ArgumentError EnergyDispatch.validate_hydraulic_v3_system_case_document(invalid)
        end
    end
end

@testset "Serial reaches and turbine discharge participate in junction balances" begin
    mktempdir() do dir
        document = reach_case()
        network = document["hydraulic_network"]
        push!(network["nodes"], Dict("id" => "middle", "type" => "junction"))
        network["reaches"][1]["to_node"] = "middle"
        push!(network["reaches"], Dict("id" => "serial", "type" => "canal", "from_node" => "middle", "to_node" => "intake"))
        push!(network["nodes"], Dict("id" => "outlet", "type" => "junction"))
        push!(network["reaches"], Dict("id" => "discharge", "type" => "tailrace", "from_node" => "tailrace", "to_node" => "outlet"))
        result = solve_reaches(document, dir, "serial")
        rows = collect(CSV.File(result.asset_dispatch_path))
        for key in ("reach", "serial", "discharge")
            @test [r.hydraulic_flow_m3s for r in rows if r.asset_type == "hydraulic_reach" && r.asset_id == key] ≈ fill(40, 4)
        end
        # Without a supplying connection, an interior junction cannot invent water.
        deleteat!(network["reaches"], 1)
        empty = solve_reaches(document, dir, "no_supply")
        @test all(r.total_hydro_turbine_flow_m3s ≈ 0 for r in CSV.File(empty.dispatch_path))
    end
end

@testset "Multiple spillways carry separate flows and are counted once" begin
    mktempdir() do dir
        document = reach_case()
        network = document["hydraulic_network"]
        network["nodes"][1]["reservoir"]["terminal_water_value_usd_per_hm3"] = 1e6
        for (key, minimum, penalty) in (("spill_a", 2.0, 10.0), ("spill_b", 3.0, 20.0))
            push!(network["reaches"], Dict("id" => key, "type" => "spillway", "from_node" => "reservoir", "to_node" => "tailrace", "flow_min_m3s" => minimum, "spill_penalty_usd_per_hm3" => penalty))
        end
        result = solve_reaches(document, dir, "spillways")
        @test [r.total_hydro_spill_flow_m3s for r in CSV.File(result.dispatch_path)] ≈ fill(5, 4)
        @test last(CSV.File(result.dispatch_path)).total_hydro_storage_hm3 ≈ 10 - 4 * 5 * 0.0036
        summary = JSON3.read(read(result.summary_path, String), Dict{String,Any})
        @test summary["hydraulic_v3_totals"]["total_spill_penalty_usd"] ≈ 4 * (2 * 10 + 3 * 20) * 0.0036
    end
end
