using Dates
using JSON3
using BESSDispatch

function usage()
    return "Usage: julia --project=. scripts/run_system_case.jl SYSTEM_CASE_PATH --output-root OUTPUT_ROOT [--run-timestamp ISO_DATETIME]"
end

function required_option_value(args::Vector{String}, index::Int, option::String)::String
    if index >= length(args)
        throw(ArgumentError("$option requires a value. $(usage())"))
    end

    return args[index + 1]
end

function parse_cli_args(args::Vector{String})
    system_case_path = nothing
    output_root = "outputs"
    run_timestamp = nothing

    index = 1
    while index <= length(args)
        arg = args[index]
        if arg == "--output-root"
            output_root = required_option_value(args, index, arg)
            index += 2
        elseif startswith(arg, "--output-root=")
            output_root = split(arg, "="; limit = 2)[2]
            index += 1
        elseif arg == "--run-timestamp"
            run_timestamp = DateTime(required_option_value(args, index, arg))
            index += 2
        elseif startswith(arg, "--run-timestamp=")
            run_timestamp = DateTime(split(arg, "="; limit = 2)[2])
            index += 1
        elseif startswith(arg, "--")
            throw(ArgumentError("unsupported option $arg. $(usage())"))
        elseif system_case_path === nothing
            system_case_path = arg
            index += 1
        else
            throw(ArgumentError("unexpected positional argument $arg. $(usage())"))
        end
    end

    if system_case_path === nothing
        throw(ArgumentError("SYSTEM_CASE_PATH is required. $(usage())"))
    end

    return system_case_path, output_root, run_timestamp
end

function system_cli_success_payload(run_output::BESSDispatch.SystemRunOutput)
    return Dict{String,Any}(
        "case_name" => run_output.case_name,
        "run_timestamp" => run_output.run_timestamp,
        "output_dir" => run_output.output_dir,
        "summary_path" => run_output.summary_path,
        "termination_status" => run_output.result.termination_status,
    )
end

function main(args::Vector{String})::Int
    try
        system_case_path, output_root, run_timestamp = parse_cli_args(args)
        run_output = BESSDispatch.run_system_case(
            system_case_path;
            output_root = output_root,
            run_timestamp = run_timestamp,
        )

        JSON3.write(stdout, system_cli_success_payload(run_output))
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
