using Test, JSON3, BESSDispatch

@testset "Result artifacts record the solver's primal status" begin
    mktempdir() do dir
        output = BESSDispatch.run_system_case(joinpath(@__DIR__, "..", "tests", "fixtures", "reg002_hydraulic.json"); output_root=dir)
        summary = JSON3.read(read(output.summary_path, String), Dict{String,Any})
        @test get(summary, "primal_status", nothing) == "FEASIBLE_POINT"
    end
end

@testset "A solve without primal values preserves its termination evidence" begin
    mktempdir() do dir
        document = JSON3.read(read(joinpath(@__DIR__, "..", "tests", "fixtures", "reg002_hydraulic.json"), String), Dict{String,Any})
        document["hydraulic_network"]["nodes"][1]["reservoir"]["initial_storage_hm3"] = 0
        document["hydraulic_network"]["units"][1]["min_flow_m3s"] = 1
        path = joinpath(dir, "infeasible.json")
        write(path, JSON3.write(document))
        caught = try
            BESSDispatch.run_system_case(path; output_root=dir)
            nothing
        catch error
            error
        end
        @test caught !== nothing && hasproperty(caught, :termination_status)
        if caught !== nothing && hasproperty(caught, :termination_status)
            @test caught.termination_status == "INFEASIBLE"
            @test caught.primal_status == "NO_SOLUTION"
        end
    end
end
