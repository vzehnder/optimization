using JSON3
using BESSDispatch

function usage()
    return "Usage: julia --project=. scripts/validate_system_case.jl SYSTEM_CASE_PATH"
end

function parse_cli_args(args::Vector{String})::String
    if length(args) != 1 || startswith(args[1], "--")
        throw(ArgumentError("SYSTEM_CASE_PATH is required. $(usage())"))
    end

    return args[1]
end

function system_validation_success_payload(data::BESSDispatch.SystemOptimizationData)
    return Dict{String,Any}(
        "status" => "ok",
        "case_name" => data.case_name,
        "schema_version" => data.schema_version,
        "bus_id" => data.bus_id,
        "period_count" => length(data.timestamp),
        "asset_counts" => Dict{String,Any}(
            "battery" => length(data.batteries),
            "renewable" => length(data.renewables),
            "grid" => length(data.grids),
            "load" => length(data.loads),
        ),
    )
end

function main(args::Vector{String})::Int
    try
        system_case_path = parse_cli_args(args)
        system_case = BESSDispatch.load_system_case(system_case_path)
        optimization_data = BESSDispatch.normalize_system_case(system_case)

        JSON3.write(stdout, system_validation_success_payload(optimization_data))
        println()
        return 0
    catch error
        JSON3.write(stderr, Dict{String,Any}(
            "status" => "error",
            "message" => sprint(showerror, error),
        ))
        println(stderr)
        return 1
    end
end

exit(main(ARGS))
