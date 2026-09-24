using Test, BESSDispatch, JSON3, CSV

function simple_hydro_rule_case()
    document = JSON3.read(read(joinpath(@__DIR__, "../data/cases/linear_hydro_system/system_case.json"), String), Dict{String,Any})
    document["component_rules"] = Dict{String,Any}(
        "version" => "affine_hydraulic.v1", "adapter" => "hydro_v2.v1",
        "objects" => [Dict("id" => 7, "component_key" => "hydro_1", "kind" => "hydro", "schema_version" => "bess_system_dispatch.v2")],
        "grid" => [Dict("timestamp" => p["timestamp"], "duration_hours" => p["duration_hours"]) for p in document["time_series"]],
        "applications" => [Dict("id" => "a1", "adapter" => "hydro_v2.v1", "required_capabilities" => ["affine_hydraulic.v1"])],
        "rows" => [Dict{String,Any}(
            "application_id" => "a1", "revision_id" => "r1", "name" => "maximo", "line" => 3,
            "period" => t, "relation" => "<=", "unit" => "m3_per_s", "constant" => -limit,
            "terms" => [Dict{String,Any}("object_id" => 7, "variable" => "caudal", "period" => t, "coefficient" => 1.0, "unit" => "dimensionless")],
        ) for (t, limit) in ((0, 4.0), (1, 6.0))],
    )
    return document
end

@testset "V2 readers reject unknown capabilities and foreign object contracts" begin
    mktempdir() do dir
        for mutate! in (
            d -> delete!(d["component_rules"], "adapter"),
            d -> d["component_rules"]["adapter"] = "hydraulic_v3.v1",
            d -> d["component_rules"]["version"] = "future.v9",
            d -> d["schema_version"] = "bess_system_dispatch.v1",
            d -> d["component_rules"]["objects"][1]["kind"] = "hydraulic_unit",
            d -> d["component_rules"]["objects"][1]["schema_version"] = "bess_system_dispatch.v3",
            d -> d["component_rules"]["objects"][1]["component_key"] = "other_model",
            d -> d["component_rules"]["objects"][1]["unit_key"] = "hydro_1",
            d -> d["component_rules"]["rows"][1]["terms"][1]["variable"] = "cota",
            d -> d["component_rules"]["rows"][1]["terms"][1]["object_id"] = 99,
            d -> d["component_rules"]["applications"][1]["required_capabilities"] = ["future.v9"],
            d -> d["component_rules"]["applications"][1]["adapter"] = "hydraulic_v3.v1",
        )
            document = simple_hydro_rule_case()
            mutate!(document)
            path = joinpath(dir, "invalid.json")
            write(path, JSON3.write(document))
            @test_throws ArgumentError BESSDispatch.load_system_case(path)
        end
    end
end

@testset "V2 rules survive loading, normalization and solving with physical balances" begin
    mktempdir() do dir
        document = simple_hydro_rule_case()
        path = joinpath(dir, "hydro.json")
        write(path, JSON3.write(document))
        graph = BESSDispatch.load_system_case(path)
        data = BESSDispatch.normalize_system_case(graph)
        result = BESSDispatch.solve_system_dispatch(data)
        @test vec(result.hydro_turbine_flow_m3s) ≈ [4, 6]
        @test vec(result.hydro_power_mw) ≈ [0.4, 0.6]
        @test vec(result.hydro_storage_hm3) ≈ [2.5936, 2.68]
        @test vec(result.p_grid_export_mw) ≈ [0.4, 0.6]
        run = BESSDispatch.run_system_case(path; output_root=joinpath(dir, "outputs"))
        @test JSON3.read(read(run.system_case_resolved_path, String), Dict{String,Any})["component_rules"] == document["component_rules"]
        @test JSON3.read(read(run.summary_path, String))["component_rule_adapter"] == "hydro_v2.v1"
    end
end

@testset "V2 rules retain the nonconvex generation curve and all four physical variables" begin
    mktempdir() do dir
        document = simple_hydro_rule_case()
        piecewise = JSON3.read(read(joinpath(@__DIR__, "../data/cases/piecewise_hydro_system/system_case.json"), String), Dict{String,Any})
        document["nodes"][end] = piecewise["nodes"][end]
        block = document["component_rules"]
        for row in block["rows"]
            row["relation"] = "=="
        end
        for (variable, unit, value, relation, period) in (("potencia", "mw", 0.65, ">=", 1),
                ("vertimiento", "m3_per_s", 2.0, "==", 0), ("vertimiento", "m3_per_s", 2.0, "==", 1),
                ("almacenamiento", "hm3", 2.6656, "==", 1))
            row = deepcopy(block["rows"][period + 1])
            row["name"], row["unit"], row["constant"], row["relation"] = variable, unit, -value, relation
            row["terms"][1]["variable"] = variable
            push!(block["rows"], row)
        end
        path = joinpath(dir, "piecewise.json")
        write(path, JSON3.write(document))
        result = BESSDispatch.solve_system_dispatch(BESSDispatch.load_system_case(path))
        @test vec(result.hydro_turbine_flow_m3s) ≈ [4, 6]
        @test vec(result.hydro_power_mw) ≈ [0.75, 0.65]
        @test vec(result.hydro_spill_flow_m3s) ≈ [2, 2]
        @test vec(result.hydro_storage_hm3) ≈ [2.5864, 2.6656]
        @test vec(result.p_grid_export_mw) ≈ [0.75, 0.65]
        delete!(document, "component_rules")
        write(path, JSON3.write(document))
        baseline = BESSDispatch.solve_system_dispatch(BESSDispatch.load_system_case(path))
        @test vec(baseline.hydro_power_mw) ≈ [0.8, 0.8]
    end
end
