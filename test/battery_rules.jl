using Test, BESSDispatch, JSON3, CSV

function battery_rule_case()
    document = JSON3.read(read(joinpath(@__DIR__, "../tests/fixtures/reg012_battery.json"), String), Dict{String,Any})
    term(variable, t) = Dict{String,Any}("object_id" => 7, "variable" => variable, "period" => t, "coefficient" => 1.0, "unit" => "dimensionless")
    row(name, t, unit, limit, relation, terms) = Dict{String,Any}("application_id" => "a1", "revision_id" => "r1",
        "name" => name, "line" => 3, "period" => t, "relation" => relation, "unit" => unit, "constant" => -limit, "terms" => terms)
    document["component_rules"] = Dict{String,Any}(
        "version" => "affine_hydraulic.v1", "adapter" => "battery_system.v1",
        "objects" => [Dict("id" => 7, "component_key" => "battery", "kind" => "battery", "schema_version" => document["schema_version"])],
        "grid" => [Dict("timestamp" => p["timestamp"], "duration_hours" => p["duration_hours"]) for p in document["time_series"]],
        "applications" => [Dict("id" => "a1", "adapter" => "battery_system.v1", "required_capabilities" => ["affine_hydraulic.v1"])],
        "rows" => vcat([row("reserva", t, "mwh", limit, ">=", [term("energia", t)]) for (t, limit) in ((0, 0), (1, 4), (2, 1), (3, 2))],
                       [row("potencia", t, "mw", 3, "<=", [term("carga", t), term("descarga", t)]) for t in 0:3]))
    document
end

@testset "Battery contracts reject foreign objects, capabilities and impossible reserves" begin
    mktempdir() do dir
        for mutate! in (
            d -> d["component_rules"]["adapter"] = "hydro_v2.v1",
            d -> d["component_rules"]["version"] = "unknown.v1",
            d -> d["component_rules"]["objects"][1]["kind"] = "hydro",
            d -> d["component_rules"]["objects"][1]["schema_version"] = "bess_system_dispatch.v3",
            d -> d["component_rules"]["objects"][1]["component_key"] = "other_model",
            d -> d["component_rules"]["rows"][1]["constant"] = -7,
            d -> d["component_rules"]["rows"][1]["unit"] = "mw",
            d -> d["component_rules"]["rows"][1]["terms"][1]["variable"] = "binaria",
            d -> d["component_rules"]["rows"][1]["terms"][1]["object_id"] = 99,
            d -> d["component_rules"]["applications"][1]["required_capabilities"] = ["unknown.v1"],
        )
            document = battery_rule_case()
            mutate!(document)
            path = joinpath(dir, "invalid.json")
            write(path, JSON3.write(document))
            @test_throws ArgumentError BESSDispatch.load_system_case(path)
        end
    end
end

@testset "Battery and simple hydro share real power variables in a v2 snapshot" begin
    mktempdir() do dir
        document = JSON3.read(read(joinpath(@__DIR__, "../data/cases/linear_hydro_system/system_case.json"), String), Dict{String,Any})
        battery = only(filter(n -> n["type"] == "battery", document["nodes"]))
        battery["discharge_power_max_mw"], battery["energy_max_mwh"], battery["initial_energy_mwh"] = 4.0, 10.0, 5.0
        block = battery_rule_case()["component_rules"]
        block["objects"] = [Dict("id" => id, "component_key" => key, "kind" => kind, "schema_version" => document["schema_version"])
                            for (id, key, kind) in ((7, "battery_1", "battery"), (8, "hydro_1", "hydro"))]
        block["grid"] = [Dict("timestamp" => p["timestamp"], "duration_hours" => p["duration_hours"]) for p in document["time_series"]]
        block["rows"] = [Dict{String,Any}("name" => "conjunto", "application_id" => "a1", "revision_id" => "r1", "line" => 3,
            "period" => t, "relation" => "<=", "unit" => "mw", "constant" => -1,
            "terms" => [Dict("object_id" => id, "variable" => variable, "period" => t, "coefficient" => 1.0, "unit" => "dimensionless")
                        for (id, variable) in ((7, "descarga"), (8, "potencia"))]) for t in 0:1]
        document["component_rules"] = block
        path = joinpath(dir, "mixed.json")
        write(path, JSON3.write(document))
        result = BESSDispatch.solve_system_dispatch(BESSDispatch.load_system_case(path))
        @test vec(result.p_battery_discharge_mw + result.hydro_power_mw) ≈ [1, 1]
        @test vec(result.p_grid_export_mw) ≈ [1, 1]
        @test result.battery_energy_mwh[1, end] + sum(result.p_battery_discharge_mw) ≈ 5
    end
end

@testset "Battery energy budgets weight unequal intervals and retain terminal energy" begin
    mktempdir() do dir
        document = battery_rule_case()
        for (p, stamp, hours) in zip(document["time_series"],
                ("2026-01-01T00:00:00", "2026-01-01T00:30:00", "2026-01-01T02:00:00", "2026-01-01T03:00:00"), (0.5, 1.5, 1.0, 1.0))
            p["timestamp"], p["duration_hours"] = stamp, hours
        end
        block = document["component_rules"]
        block["version"] = "affine_budget.v1"
        block["grid"] = [Dict("timestamp" => p["timestamp"], "duration_hours" => p["duration_hours"]) for p in document["time_series"]]
        block["applications"][1]["required_capabilities"] = ["affine_budget.v1"]
        block["applications"][1]["windows"] = Dict("kind" => "horizon", "timezone" => "UTC", "partial" => "reject")
        row = deepcopy(block["rows"][1])
        row["period"], row["relation"], row["constant"] = 3, "<=", -1.2
        row["window"] = Dict("start" => "2026-01-01T00:00:00Z", "end" => "2026-01-01T04:00:00Z", "duration_hours" => 4.0, "periods" => [0, 1, 2, 3], "partial" => false)
        row["terms"] = [Dict("object_id" => 7, "variable" => "descarga", "period" => t, "coefficient" => hours, "unit" => "h")
                        for (t, hours) in ((0, 0.5), (1, 1.5), (2, 1.0), (3, 1.0))]
        block["rows"] = [row]
        path = joinpath(dir, "budget.json")
        write(path, JSON3.write(document))
        result = BESSDispatch.solve_system_dispatch(BESSDispatch.load_system_case(path))
        @test sum(vec(result.p_battery_discharge_mw) .* [0.5, 1.5, 1, 1]) ≈ 1.2
        @test result.battery_energy_mwh[1, end] ≈ 2
    end
end

@testset "Hourly battery reserves change arbitrage while preserving physical equations" begin
    mktempdir() do dir
        document = battery_rule_case()
        path = joinpath(dir, "battery.json")
        write(path, JSON3.write(document))
        graph = BESSDispatch.load_system_case(path)
        data = BESSDispatch.normalize_system_case(graph)
        result = BESSDispatch.solve_system_dispatch(data)
        @test vec(result.p_battery_charge_mw) ≈ [3, 0, 0, 1.25]
        @test vec(result.p_battery_discharge_mw) ≈ [0, 0.36, 2.7, 0]
        @test vec(result.battery_energy_mwh) ≈ [4.4, 4, 1, 2]
        @test result.objective_value_usd ≈ 208.95
        @test all(abs.(result.p_battery_charge_mw .* result.p_battery_discharge_mw) .< 1e-8)
        @test vec(result.p_grid_import_mw - result.p_grid_export_mw) ≈ [3, -0.36, -2.7, 1.25]
        run = BESSDispatch.run_system_case(path; output_root=joinpath(dir, "outputs"))
        @test JSON3.read(read(run.system_case_resolved_path, String), Dict{String,Any})["component_rules"] == document["component_rules"]
        @test JSON3.read(read(run.summary_path, String))["component_rule_adapter"] == "battery_system.v1"
        delete!(document, "component_rules")
        write(path, JSON3.write(document))
        base = BESSDispatch.solve_system_dispatch(BESSDispatch.load_system_case(path))
        @test vec(base.p_battery_discharge_mw) ≈ [0, 4, 0.68, 0]
        @test base.battery_energy_mwh[1, end] ≈ 2
    end
end
