using Test, BESSDispatch, JSON3, CSV

function rule_case()
    document = JSON3.read(read(joinpath(@__DIR__, "../tests/fixtures/reg002_hydraulic.json"), String), Dict{String,Any})
    document["component_rules"] = Dict{String,Any}(
        "version" => "affine_flow.v1",
        "objects" => [Dict("id" => 7, "unit_key" => "unit")],
        "grid" => [Dict("timestamp" => p["timestamp"], "duration_hours" => p["duration_hours"]) for p in document["time_series"]],
        "rows" => [Dict{String,Any}(
            "application_id" => "a1", "revision_id" => "r1", "name" => "maximo", "line" => 3,
            "period" => t, "relation" => "<=", "unit" => "m3_per_s", "constant" => -5.0,
            "terms" => [Dict{String,Any}("object_id" => 7, "variable" => "caudal", "period" => t, "coefficient" => 1.0, "unit" => "dimensionless")],
        ) for t in 0:3],
    )
    return document
end

@testset "Unsupported or malformed rules fail before optimization" begin
    for mutate! in (
        d -> d["component_rules"]["version"] = "future.v9",
        d -> d["component_rules"]["rows"][1]["relation"] = "<",
        d -> d["component_rules"]["rows"][1]["constant"] = Inf,
        d -> d["component_rules"]["rows"][1]["terms"][1]["coefficient"] = NaN,
        d -> d["component_rules"]["rows"][1]["terms"][1]["object_id"] = 99,
        d -> d["component_rules"]["rows"][1]["terms"][1]["variable"] = "cota",
        d -> d["component_rules"]["rows"][1]["terms"][1]["period"] = -1,
        d -> d["component_rules"]["rows"][1]["unit"] = "mw",
        d -> d["component_rules"]["grid"][1]["duration_hours"] = 2,
        d -> d["component_rules"]["objects"][1]["unit_key"] = "foreign_unit",
        d -> d["component_rules"]["rows"][1]["terms"][1]["power"] = 2,
    )
        document = rule_case()
        mutate!(document)
        @test_throws ArgumentError BESSDispatch.validate_hydraulic_v3_system_case_document(document)
    end
end

function solve_rule_case(document, dir, name)
    path = joinpath(dir, "$name.json")
    write(path, JSON3.write(document))
    BESSDispatch.run_system_case(path; output_root=joinpath(dir, name))
end

@testset "A frozen maximum changes all four periods and survives the resolved snapshot" begin
    mktempdir() do dir
        document = rule_case()
        base = deepcopy(document)
        delete!(base, "component_rules")
        baseline = solve_rule_case(base, dir, "base")
        limited = solve_rule_case(document, dir, "limited")
        @test all(row.total_hydro_turbine_flow_m3s ≈ 40.0 for row in CSV.File(baseline.dispatch_path))
        @test all(row.total_hydro_turbine_flow_m3s ≈ 5.0 for row in CSV.File(limited.dispatch_path))
        frozen = JSON3.read(read(limited.system_case_resolved_path, String), Dict{String,Any})
        @test frozen["component_rules"] == document["component_rules"]
    end
end

@testset "Rules compose with physical bounds and cannot be silently dropped" begin
    mktempdir() do dir
        equal = rule_case()
        for row in equal["component_rules"]["rows"]
            row["relation"] = "=="
        end
        result = solve_rule_case(equal, dir, "equal")
        @test all(row.total_hydro_turbine_flow_m3s ≈ 5 for row in CSV.File(result.dispatch_path))
        impossible = rule_case()
        impossible["hydraulic_network"]["units"][1]["min_flow_m3s"] = 6.0
        @test_throws ArgumentError BESSDispatch.validate_hydraulic_v3_system_case_document(impossible)
        @test_throws Exception solve_rule_case(impossible, dir, "infeasible")
        unsupported = rule_case()
        unsupported["schema_version"] = "bess_system_dispatch.v2"
        path = joinpath(dir, "unsupported.json")
        write(path, JSON3.write(unsupported))
        @test_throws ArgumentError BESSDispatch.load_system_case(path)
    end
end
