using Dates
using JSON3
using JuMP

function emit_run_progress(path, stage::String, message::String)
    path === nothing && return
    mkpath(dirname(path))
    open(path, "a") do io
        JSON3.write(io, Dict(
            "timestamp" => string(now(UTC)) * "Z",
            "stage" => stage,
            "message" => message,
        ))
        println(io)
        flush(io)
    end
    return
end

function optimize_with_progress!(model; progress_path = nothing, solver_log_path = nothing)
    if solver_log_path !== nothing
        mkpath(dirname(solver_log_path))
        # Keep the CLI's stdout/stderr JSON contract intact. HiGHS flushes its
        # separate log as it solves, so the API can read it between polls.
        unset_silent(model)
        set_optimizer_attribute(model, "output_flag", true)
        set_optimizer_attribute(model, "log_to_console", false)
        set_optimizer_attribute(model, "log_file", solver_log_path)
        set_optimizer_attribute(model, "mip_min_logging_interval", 1.0)
    end
    emit_run_progress(progress_path, "optimizing", "Iniciando la optimización con HiGHS.")
    try
        optimize!(model)
    finally
        # Release the native file handle even when solving throws. In Windows
        # it would otherwise remain locked until the optimizer is collected.
        if solver_log_path !== nothing
            # Set the native option without marking the JuMP model dirty;
            # the solved values must remain available to the result writer.
            MOI.set(unsafe_backend(model), MOI.RawOptimizerAttribute("log_file"), "")
        end
    end
    emit_run_progress(progress_path, "processing", "Optimización terminada ($(termination_status(model))). Preparando resultados.")
    return
end
