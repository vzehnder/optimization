using Test, EnergyDispatch, JSON3

@testset "Economic hydraulic validation requires finite CMg for every period" begin
    base = JSON3.read(read(joinpath(@__DIR__, "../tests/fixtures/reg002_hydraulic.json"), String), Dict{String,Any})
    base["hydraulic_objective"] = "market_value"
    for period in base["time_series"]
        period["price_usd_per_mwh"] = -10.0
    end
    @test EnergyDispatch.validate_hydraulic_v3_system_case_document(base)["status"] == "ok"
    for invalid_price in (nothing, NaN, Inf)
        invalid = deepcopy(base)
        invalid["time_series"][2]["price_usd_per_mwh"] = invalid_price
        @test_throws ArgumentError EnergyDispatch.validate_hydraulic_v3_system_case_document(invalid)
    end
    missing = deepcopy(base)
    delete!(missing["time_series"][1], "price_usd_per_mwh")
    @test_throws ArgumentError EnergyDispatch.validate_hydraulic_v3_system_case_document(missing)
    base["hydraulic_objective"] = "unknown"
    @test_throws ArgumentError EnergyDispatch.validate_hydraulic_v3_system_case_document(base)
end
