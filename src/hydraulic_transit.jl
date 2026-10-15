# Initial water is specified either as a steady pre-horizon departure flow or
# as an arrival schedule carried from the previous run. Times are absolute;
# a continuation can therefore use a completely different interval grid.
function hydraulic_initial_arrivals(reach, horizon_start)
    delay = Float64(get(reach, "travel_time_hours", 0.0))
    initial = parse_required_float(get(reach, "initial_flow_m3s", 0.0), "initial_flow_m3s")
    (!isfinite(initial) || initial < 0) && throw(ArgumentError("initial_flow_m3s must be finite and nonnegative"))
    schedule = get(reach, "initial_arrivals", nothing)
    if schedule === nothing
        return initial == 0 || delay == 0 ? Tuple{Float64,Float64,Float64}[] : [(0.0, delay, initial)]
    end
    initial != 0 && throw(ArgumentError("choose initial_flow_m3s or initial_arrivals, not both"))
    schedule isa AbstractVector || throw(ArgumentError("initial_arrivals must be an array"))
    segments = Tuple{Float64,Float64,Float64}[]
    previous_end = 0.0
    for raw in schedule
        point = to_string_key_dict(raw)
        start = parse_required_datetime(required_value(point, "timestamp"), "initial_arrivals.timestamp")
        left = Dates.value(start - horizon_start) / 3_600_000
        duration = parse_required_float(required_value(point, "duration_hours"), "initial_arrivals.duration_hours")
        flow = parse_required_float(required_value(point, "value_m3s"), "initial_arrivals.value_m3s")
        if !isfinite(duration) || duration <= 0 || !isfinite(flow) || flow < 0 || left < previous_end - 1e-9 || left + duration > delay + 1e-9
            throw(ArgumentError("initial arrivals must be nonnegative, ordered, nonoverlapping and within the initial travel-time window"))
        end
        push!(segments, (left, left + duration, flow))
        previous_end = left + duration
    end
    segments
end

function hydraulic_transit_summary(reaches, timestamps, durations, departure)
    starts = [Dates.value(timestamp - first(timestamps)) / 3_600_000 for timestamp in timestamps]
    horizon_end = last(starts) + last(durations)
    transport = Dict{String,Any}()
    for (r, reach) in enumerate(reaches)
        delay = Float64(get(reach, "travel_time_hours", 0.0))
        initial = hydraulic_initial_arrivals(reach, first(timestamps))
        segments = vcat(initial, [(starts[t] + delay, starts[t] + durations[t] + delay, departure[r, t]) for t in eachindex(starts)])
        tail = [
            Dict("timestamp" => string(first(timestamps) + Millisecond(round(Int, max(left, horizon_end) * 3_600_000))),
                 "duration_hours" => right - max(left, horizon_end), "value_m3s" => max(0.0, flow))
            for (left, right, flow) in segments if right > horizon_end + 1e-9 && flow > 1e-10
        ]
        transport[reach["id"]] = Dict(
            "travel_time_hours" => delay,
            "initial_volume_hm3" => sum((right - left) * flow * HM3_PER_M3S_HOUR for (left, right, flow) in initial; init=0.0),
            "final_volume_hm3" => sum(p["duration_hours"] * p["value_m3s"] * HM3_PER_M3S_HOUR for p in tail; init=0.0),
            "terminal_arrivals" => tail,
            "terminal_policy" => "carry_forward_unvalued",
            "diagram_link" => get(reach, "diagram_link", nothing),
        )
    end
    transport
end
