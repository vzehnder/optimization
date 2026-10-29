using Test
using EnergyDispatch
using JSON3

@testset "Live run progress preserves the result contract" begin
    for case_path in [joinpath(@__DIR__, "..", "data", "cases", "hybrid_system", "system_case.json"),
                      joinpath(@__DIR__, "..", "tests", "fixtures", "reg002_hydraulic.json")]
        mktempdir() do directory
            progress_path = joinpath(directory, "logs", "progress.jsonl")
            solver_log_path = joinpath(directory, "logs", "solver.log")
            output = run_system_case(
                case_path;
                output_root = joinpath(directory, "outputs"), progress_path, solver_log_path,
            )
            events = [JSON3.read(line) for line in readlines(progress_path)]
            @test [String(event.stage) for event in events] == ["preparing", "building", "optimizing", "processing", "saving"]
            @test output.result.termination_status == "OPTIMAL"
            log = read(solver_log_path, String)
            @test occursin("HiGHS", log)
            @test occursin("Optimal", log)
            @test isfile(output.summary_path)
        end
    end
end
