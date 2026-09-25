const COMPONENT_RULE_VERSION = "affine_flow.v1"
const HYDRAULIC_RULE_VERSION = "affine_hydraulic.v1"
const TEMPORAL_RULE_VERSION = "affine_temporal.v1"
const BUDGET_RULE_VERSION = "affine_budget.v1"
const SIMPLE_HYDRO_RULE_ADAPTER = "hydro_v2.v1"
const BATTERY_RULE_ADAPTER = "battery_system.v1"

function validate_budget_window(row, policy, grid)
    policy isa AbstractDict || throw(ArgumentError("budget window requires an explicit policy"))
    get(policy, "kind", nothing) in ("horizon", "civil_day") || throw(ArgumentError("invalid budget window kind"))
    !isempty(required_string(policy, "timezone")) || throw(ArgumentError("missing budget timezone"))
    get(policy, "partial", nothing) in ("reject", "allow") || throw(ArgumentError("invalid partial window policy"))
    window = required_dict(row, "window")
    Set(keys(window)) == Set(("start", "end", "duration_hours", "periods", "partial")) || throw(ArgumentError("invalid window fields"))
    indices = required_vector(window, "periods")
    !isempty(indices) && all(t -> t isa Integer && !(t isa Bool) && 0 <= t < length(grid), indices) || throw(ArgumentError("empty or invalid budget periods"))
    indices == collect(first(indices):last(indices)) && row["period"] == last(indices) || throw(ArgumentError("noncontiguous budget window"))
    start = parse_required_datetime(window["start"], "window.start")
    finish = parse_required_datetime(window["end"], "window.end")
    cursor = start
    for t in indices
        point = grid[t + 1]
        cursor == parse_required_datetime(point["timestamp"], "grid.timestamp") || throw(ArgumentError("misaligned budget window"))
        cursor += Millisecond(round(Int, point["duration_hours"] * 3600000))
    end
    cursor == finish || throw(ArgumentError("misaligned budget end"))
    hours = get(window, "duration_hours", nothing)
    hours isa Real && !(hours isa Bool) && isfinite(hours) && hours > 0 &&
        isapprox(hours, Dates.value(finish - start) / 3600000; atol=1e-9, rtol=0) || throw(ArgumentError("incorrect window duration"))
    get(window, "partial", nothing) isa Bool || throw(ArgumentError("missing partial window flag"))
    window["partial"] && policy["partial"] != "allow" && throw(ArgumentError("partial day not accepted"))
    if policy["kind"] == "horizon"
        indices == collect(0:length(grid)-1) && !window["partial"] || throw(ArgumentError("incomplete horizon window"))
    end
    return Set(indices)
end

function validate_component_rules(document)
    haskey(document, "component_rules") || return
    rules = required_dict(document, "component_rules")
    schema = required_string(document, "schema_version")
    simple_hydro = schema in (SYSTEM_SCHEMA_VERSION, SYSTEM_SCHEMA_VERSION_V2)
    schema in (SYSTEM_SCHEMA_VERSION, SYSTEM_SCHEMA_VERSION_V2, SYSTEM_SCHEMA_VERSION_V3) ||
        throw(ArgumentError("component rules require v1/v2 or hydraulic v3"))
    if simple_hydro
        adapter = get(rules, "adapter", nothing)
        adapter in (SIMPLE_HYDRO_RULE_ADAPTER, BATTERY_RULE_ADAPTER) || throw(ArgumentError("unsupported system component rule adapter"))
        schema == SYSTEM_SCHEMA_VERSION && adapter != BATTERY_RULE_ADAPTER && throw(ArgumentError("v1 requires battery adapter"))
        for application in required_vector(rules, "applications")
            get(application, "adapter", nothing) in (adapter == BATTERY_RULE_ADAPTER ? (BATTERY_RULE_ADAPTER, SIMPLE_HYDRO_RULE_ADAPTER) : (SIMPLE_HYDRO_RULE_ADAPTER,)) || throw(ArgumentError("application adapter differs from snapshot"))
            capabilities = required_vector(application, "required_capabilities")
            !isempty(capabilities) && all(v -> v in (COMPONENT_RULE_VERSION, HYDRAULIC_RULE_VERSION, TEMPORAL_RULE_VERSION, BUDGET_RULE_VERSION), capabilities) ||
                throw(ArgumentError("unsupported application capabilities"))
        end
    elseif haskey(rules, "adapter") && rules["adapter"] != "hydraulic_v3.v1"
        throw(ArgumentError("component rule adapter does not match v3"))
    end
    get(rules, "version", nothing) in (COMPONENT_RULE_VERSION, HYDRAULIC_RULE_VERSION, TEMPORAL_RULE_VERSION, BUDGET_RULE_VERSION) ||
        throw(ArgumentError("unsupported component rules version"))
    budget = rules["version"] == BUDGET_RULE_VERSION
    temporal = rules["version"] == TEMPORAL_RULE_VERSION || budget
    extended = rules["version"] != COMPONENT_RULE_VERSION
    periods = required_vector(document, "time_series")
    1 <= length(periods) <= 8784 || throw(ArgumentError("component rules period quota exceeded"))
    grid = required_vector(rules, "grid")
    expected_grid = [Dict("timestamp" => p["timestamp"], "duration_hours" => p["duration_hours"]) for p in periods]
    length(grid) == length(expected_grid) && all(
        parse_required_datetime(a["timestamp"], "rules.timestamp") == parse_required_datetime(b["timestamp"], "period.timestamp") &&
        a["duration_hours"] == b["duration_hours"] for (a, b) in zip(grid, expected_grid)) ||
        throw(ArgumentError("component rules grid differs from snapshot"))
    temporal_policies = Dict{String,Any}()
    if temporal
        for application in required_vector(rules, "applications")
            policy = get(application, "temporal", nothing)
            policy === nothing && continue
            get(policy, "first_period", nothing) in ("omit", "initial") || throw(ArgumentError("invalid initial period policy"))
            initial_values = required_vector(policy, "initial_values")
            (policy["first_period"] == "initial") == !isempty(initial_values) || throw(ArgumentError("initial values do not match temporal policy"))
            temporal_policies[required_string(application, "id")] = policy
        end
        !budget && isempty(temporal_policies) && throw(ArgumentError("temporal rules require an explicit initial period policy"))
    end
    window_policies = budget ? Dict(a["id"] => get(a, "windows", nothing) for a in rules["applications"]) : Dict()
    network = simple_hydro ? Dict("units" => [], "nodes" => [], "plants" => []) : document["hydraulic_network"]
    units = Set(u["id"] for u in network["units"])
    hydros = simple_hydro ? Dict(n["id"] => parse_system_hydro_asset(SystemNode(n["id"], "hydro", Dict{String,Any}(n)))
                               for n in document["nodes"] if n["type"] == "hydro") : Dict()
    batteries = simple_hydro ? Dict(n["id"] => n for n in document["nodes"] if n["type"] == "battery") : Dict()
    reservoirs = Set(n["id"] for n in network["nodes"] if n["type"] == "reservoir")
    plants = Set(p["id"] for p in network["plants"])
    objects = required_vector(rules, "objects")
    object_ids = Set{Int}()
    for object in objects
        id = get(object, "id", nothing)
        id isa Integer && !(id isa Bool) && id > 0 && !(id in object_ids) ||
            throw(ArgumentError("invalid component rules object identity"))
        keys_present = [key for key in ("unit_key", "node_key", "plant_key", "component_key") if haskey(object, key)]
        length(keys_present) == 1 || throw(ArgumentError("ambiguous component rules object"))
        key = only(keys_present)
        valid = if simple_hydro
            key == "component_key" && get(object, "schema_version", nothing) == schema &&
                ((get(object, "kind", nothing) == "hydro" && schema == SYSTEM_SCHEMA_VERSION_V2 && haskey(hydros, object[key])) ||
                 (get(object, "kind", nothing) == "battery" && rules["adapter"] == BATTERY_RULE_ADAPTER && haskey(batteries, object[key])))
        else
            key == "unit_key" ? object[key] in units : extended && (key == "node_key" ? object[key] in reservoirs : key == "plant_key" && object[key] in plants)
        end
        valid || throw(ArgumentError("component rules object outside snapshot"))
        push!(object_ids, id)
    end
    by_id = Dict(o["id"] => o for o in objects)
    for object in objects
        haskey(object, "plant_key") || continue
        members = required_vector(object, "member_ids")
        all(id -> id isa Integer && !(id isa Bool) && haskey(by_id, id) && haskey(by_id[id], "unit_key"), members) ||
            throw(ArgumentError("invalid component rules plant members"))
        expected = Set(u["id"] for u in network["units"] if u["plant_id"] == object["plant_key"])
        length(members) == length(expected) && Set(by_id[id]["unit_key"] for id in members) == expected ||
            throw(ArgumentError("component rules plant membership differs from snapshot"))
    end
    rows = required_vector(rules, "rows")
    length(rows) <= 100000 || throw(ArgumentError("component rules row quota exceeded"))
    names = Set()
    object_units = Dict(object["id"] => only(filter(u -> u["id"] == object["unit_key"], network["units"])) for object in objects if haskey(object, "unit_key"))
    bounds = Dict{Tuple{Int,String,Int},Tuple{Float64,Float64}}()
    term_count = 0
    for row in rows
        for key in ("application_id", "revision_id", "name")
            isempty(required_string(row, key)) && throw(ArgumentError("missing component rules origin"))
        end
        row_period = get(row, "period", nothing)
        row_period isa Integer && !(row_period isa Bool) && 0 <= row_period < length(periods) ||
            throw(ArgumentError("component rules period outside snapshot"))
        get(row, "line", nothing) isa Integer && row["line"] > 0 || throw(ArgumentError("invalid component rules source line"))
        name = (row["application_id"], row["name"], row_period)
        name in names && throw(ArgumentError("duplicate component rules row"))
        push!(names, name)
        get(row, "relation", nothing) in ("<=", ">=", "==") || throw(ArgumentError("invalid component rules relation"))
        window = haskey(row, "window")
        window && !budget && throw(ArgumentError("budget capability required"))
        window_periods = window ? validate_budget_window(row, get(window_policies, row["application_id"], nothing), grid) : Set()
        get(row, "unit", nothing) in (window ? ("mwh", "m3", "hm3") : extended ? ("m3_per_s", "mw", "hm3", "mwh") : ("m3_per_s",)) || throw(ArgumentError("invalid component rules unit"))
        constant = get(row, "constant", nothing)
        constant isa Real && !(constant isa Bool) && isfinite(constant) || throw(ArgumentError("nonfinite component rules constant"))
        terms = required_vector(row, "terms")
        term_count += length(terms)
        term_count <= 500000 || throw(ArgumentError("component rules term quota exceeded"))
        row_objects = Set()
        coefficients = Dict{Tuple{Int,String,Int},Float64}()
        for term in terms
            Set(keys(term)) == Set(("object_id", "variable", "period", "coefficient", "unit")) ||
                throw(ArgumentError("unsupported component rules term fields"))
            id = get(term, "object_id", nothing)
            id isa Integer && !(id isa Bool) && id in object_ids || throw(ArgumentError("component rules object outside snapshot"))
            push!(row_objects, id)
            variable = get(term, "variable", nothing)
            object = by_id[id]
            expected_unit = if get(object, "kind", nothing) == "battery"
                extended ? get(Dict("carga" => "mw", "descarga" => "mw", "energia" => "mwh"), variable, nothing) : nothing
            elseif haskey(object, "component_key")
                variable == "caudal" ? "m3_per_s" : !extended ? nothing :
                    get(Dict("potencia" => "mw", "almacenamiento" => "hm3", "vertimiento" => "m3_per_s"), variable, nothing)
            elseif haskey(object, "unit_key")
                variable == "caudal" ? "m3_per_s" : extended && variable == "potencia" ? "mw" : nothing
            elseif extended && haskey(object, "node_key")
                variable == "almacenamiento" ? "hm3" : variable == "vertimiento" ? "m3_per_s" : nothing
            else
                nothing
            end
            coefficient_unit = if window
                get(Dict(("mw", "mwh") => "h", ("m3_per_s", "m3") => "s", ("m3_per_s", "hm3") => "hm3_per_m3_per_s"), (expected_unit, row["unit"]), nothing)
            else
                expected_unit == row["unit"] ? "dimensionless" : nothing
            end
            coefficient_unit !== nothing || throw(ArgumentError("unsupported component rules variable or unit"))
            period = get(term, "period", nothing)
            period isa Integer && !(period isa Bool) && 0 <= period <= row_period && (temporal || period == row_period) || throw(ArgumentError("unsupported component rules period reference"))
            if window
                period in window_periods || throw(ArgumentError("term outside budget window"))
            else
                period == row_period || haskey(temporal_policies, row["application_id"]) || throw(ArgumentError("previous period reference requires an initial policy"))
            end
            get(term, "unit", nothing) == coefficient_unit || throw(ArgumentError("invalid component rules coefficient unit"))
            coefficient = get(term, "coefficient", nothing)
            coefficient isa Real && !(coefficient isa Bool) && isfinite(coefficient) || throw(ArgumentError("nonfinite component rules coefficient"))
            key = (id, variable, period)
            coefficients[key] = get(coefficients, key, 0.0) + Float64(coefficient)
            isfinite(coefficients[key]) || throw(ArgumentError("nonfinite normalized component rules coefficient"))
        end
        extended || length(row_objects) <= 1 || throw(ArgumentError("multiple objects require hydraulic capability"))
        filter!(pair -> pair.second != 0, coefficients)
        length(coefficients) > 1 && continue
        coefficient = sum(values(coefficients); init=0.0)
        isfinite(coefficient) || throw(ArgumentError("nonfinite normalized component rules coefficient"))
        relation = row["relation"]
        if coefficient == 0
            valid = relation == "<=" ? constant <= 0 : relation == ">=" ? constant >= 0 : constant == 0
            valid || throw(ArgumentError("contradictory constant component rule $(row["name"])"))
        else
            (id, variable, term_period) = only(keys(coefficients))
            physical = if get(by_id[id], "kind", nothing) == "battery"
                battery = batteries[by_id[id]["component_key"]]
                variable == "carga" ? (0.0, Float64(battery["charge_power_max_mw"])) :
                    variable == "descarga" ? (0.0, Float64(battery["discharge_power_max_mw"])) :
                    (Float64(battery["energy_min_mwh"]), Float64(battery["energy_max_mwh"]))
            elseif haskey(by_id[id], "component_key")
                hydro = hydros[by_id[id]["component_key"]]
                variable == "caudal" ? (hydro_turbine_flow_lower_bound(hydro), hydro_turbine_flow_upper_bound(hydro)) :
                    variable == "potencia" ? (0.0, hydro_power_upper_bound(hydro)) :
                    variable == "almacenamiento" ? (hydro.storage_min_hm3, hydro.storage_max_hm3) : (0.0, Inf)
            elseif variable in ("caudal", "potencia")
                unit = object_units[id]
                curve = unit["curves"]["flow_power"]
                if variable == "caudal"
                    lower = get(unit, "min_flow_m3s", nothing)
                    upper = get(unit, "max_flow_m3s", nothing)
                    (max(Float64(first(curve)["flow_m3s"]), lower === nothing ? 0.0 : Float64(lower)),
                     min(Float64(last(curve)["flow_m3s"]), upper === nothing ? Inf : Float64(upper)))
                else
                    upper = get(unit, "max_power_mw", nothing)
                    (0.0, min(Float64(last(curve)["power_mw"]), upper === nothing ? Inf : Float64(upper)))
                end
            elseif variable == "almacenamiento"
                reservoir = only(filter(n -> n["id"] == by_id[id]["node_key"], network["nodes"]))["reservoir"]
                (Float64(reservoir["storage_min_hm3"]), Float64(reservoir["storage_max_hm3"]))
            else
                (0.0, Inf)
            end
            lower, upper = get(bounds, (id, variable, term_period), physical)
            bound = -Float64(constant) / coefficient
            isfinite(bound) || throw(ArgumentError("nonfinite normalized component rule bound"))
            if relation == "=="
                lower, upper = max(lower, bound), min(upper, bound)
            elseif (relation == "<=" && coefficient > 0) || (relation == ">=" && coefficient < 0)
                upper = min(upper, bound)
            else
                lower = max(lower, bound)
            end
            lower <= upper || throw(ArgumentError("contradictory component rule $(row["name"]) at period $(row_period + 1)"))
            bounds[(id, variable, term_period)] = (lower, upper)
        end
    end
end
