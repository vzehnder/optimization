using Test, BESSDispatch, JSON3

function electric_rule_case()
    document = JSON3.read(read(joinpath(@__DIR__, "../tests/fixtures/reg013_electric.json"), String), Dict{String,Any})
    document["component_rules"] = Dict{String,Any}(
        "version" => "affine_hydraulic.v1", "adapter" => "electric_system.v1",
        "objects" => [Dict("id" => id, "component_key" => key, "kind" => kind, "schema_version" => document["schema_version"])
                      for (id, key, kind) in ((7, "grid", "grid"), (8, "solar", "renewable"), (9, "load", "load"))],
        "grid" => [Dict("timestamp" => p["timestamp"], "duration_hours" => p["duration_hours"]) for p in document["time_series"]],
        "applications" => [Dict("id" => "a1", "adapter" => "electric_system.v1", "required_capabilities" => ["affine_hydraulic.v1"])],
        "rows" => [Dict{String,Any}("application_id" => "a1", "revision_id" => "r1", "name" => "fraccion",
            "line" => 3, "period" => t, "relation" => "<=", "unit" => "mw", "constant" => 0,
            "terms" => [Dict("object_id" => id, "variable" => variable, "period" => t, "coefficient" => coefficient, "unit" => "dimensionless")
                        for (id, variable, coefficient) in ((7, "exportacion", 1), (8, "generacion", -0.5))]) for t in 0:3])
    document
end

@testset "A hydraulic v3 identity cannot be relabeled as an electrical component" begin
    document = JSON3.read(read(joinpath(@__DIR__, "../tests/fixtures/reg002_hydraulic.json"), String), Dict{String,Any})
    block = electric_rule_case()["component_rules"]
    block["adapter"] = "hydraulic_v3.v1"
    block["objects"] = [Dict("id" => 7, "node_key" => "reservoir", "kind" => "grid")]
    block["grid"] = [Dict("timestamp" => p["timestamp"], "duration_hours" => p["duration_hours"]) for p in document["time_series"]]
    row = block["rows"][1]
    row["terms"][2]["object_id"], row["terms"][2]["variable"] = 7, "importacion"
    block["rows"] = [row]
    document["component_rules"] = block
    @test_throws ArgumentError BESSDispatch.validate_hydraulic_v3_system_case_document(document)
end

@testset "Electric scalar bounds and known data are validated before solving" begin
    mktempdir() do dir
        for (id, variable, t, limit, relation, valid) in ((7, "importacion", 0, -1, "<=", false),
                (7, "exportacion", 0, 7, ">=", false), (8, "generacion", 2, 2, ">=", false),
                (8, "recorte", 1, 9, ">=", false), (8, "recorte", 0, 6, "<=", true))
            document = electric_rule_case()
            row = document["component_rules"]["rows"][1]
            row["period"], row["constant"], row["relation"] = t, -limit, relation
            row["terms"] = [Dict("object_id" => id, "variable" => variable, "period" => t, "coefficient" => 1, "unit" => "dimensionless")]
            document["component_rules"]["rows"] = [row]
            path = joinpath(dir, "bounds.json")
            write(path, JSON3.write(document))
            if valid
                @test BESSDispatch.load_system_case(path).component_rules["rows"][1]["name"] == "fraccion"
            else
                @test_throws ArgumentError BESSDispatch.load_system_case(path)
            end
        end
    end
end

@testset "Electric rules reject foreign references, forged known decisions and incompatible contracts" begin
    mktempdir() do dir
        for mutate! in (
            d -> d["component_rules"]["adapter"] = "battery_system.v1",
            d -> d["component_rules"]["version"] = "unknown.v1",
            d -> d["component_rules"]["objects"][1]["kind"] = "hydraulic_unit",
            d -> d["component_rules"]["objects"][1]["schema_version"] = "bess_system_dispatch.v3",
            d -> d["component_rules"]["objects"][1]["component_key"] = "other_model",
            d -> d["component_rules"]["rows"][1]["terms"][1]["object_id"] = 999,
            d -> d["component_rules"]["rows"][1]["unit"] = "mwh",
            d -> d["component_rules"]["rows"][1]["terms"][2]["variable"] = "disponibilidad",
            d -> d["component_rules"]["rows"][1]["terms"][2]["variable"] = "importacion",
            d -> merge!(d["component_rules"]["rows"][1]["terms"][2], Dict("object_id" => 9, "variable" => "demanda")),
            d -> d["component_rules"]["applications"][1]["required_capabilities"] = ["unknown.v1"],
        )
            document = electric_rule_case()
            mutate!(document)
            path = joinpath(dir, "invalid.json")
            write(path, JSON3.write(document))
            @test_throws ArgumentError BESSDispatch.load_system_case(path)
        end
    end
end

@testset "Export fraction changes generation and curtailment while preserving electrical balance" begin
    mktempdir() do dir
        document = electric_rule_case()
        path = joinpath(dir, "electric.json")
        write(path, JSON3.write(document))
        result = BESSDispatch.solve_system_dispatch(BESSDispatch.load_system_case(path))
        @test vec(result.p_grid_export_mw) ≈ [2, 2, 0, 0]
        @test vec(result.p_grid_import_mw) ≈ [0, 0, 1, 2]
        @test vec(result.p_renewable_used_mw) ≈ [4, 4, 1, 0]
        @test vec(result.p_renewable_curtailed_mw) ≈ [6, 4, 0, 0]
        @test vec(result.p_grid_import_mw + result.p_renewable_used_mw - result.p_grid_export_mw) ≈ [2, 2, 2, 2]
        @test vec(result.p_renewable_used_mw + result.p_renewable_curtailed_mw) ≈ [10, 8, 1, 0]
        @test all(abs.(result.p_grid_import_mw .* result.p_grid_export_mw) .< 1e-8)
        run = BESSDispatch.run_system_case(path; output_root=joinpath(dir, "outputs"))
        @test JSON3.read(read(run.system_case_resolved_path, String), Dict{String,Any})["component_rules"] == document["component_rules"]
        @test JSON3.read(read(run.summary_path, String))["component_rule_adapter"] == "electric_system.v1"
        delete!(document, "component_rules")
        write(path, JSON3.write(document))
        base = BESSDispatch.solve_system_dispatch(BESSDispatch.load_system_case(path))
        @test vec(base.p_grid_export_mw) ≈ [6, 6, 0, 0]
        @test vec(base.p_renewable_curtailed_mw) ≈ [2, 0, 0, 0]
    end
end
