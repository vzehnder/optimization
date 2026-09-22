const COMPONENT_RULE_VERSION = "affine_flow.v1"

function validate_component_rules(document)
    haskey(document, "component_rules") || return
    rules = required_dict(document, "component_rules")
    required_string(document, "schema_version") == SYSTEM_SCHEMA_VERSION_V3 ||
        throw(ArgumentError("component rules require hydraulic v3"))
    get(rules, "version", nothing) == COMPONENT_RULE_VERSION ||
        throw(ArgumentError("unsupported component rules version"))
    periods = required_vector(document, "time_series")
    1 <= length(periods) <= 8784 || throw(ArgumentError("component rules period quota exceeded"))
    grid = required_vector(rules, "grid")
    expected_grid = [Dict("timestamp" => p["timestamp"], "duration_hours" => p["duration_hours"]) for p in periods]
    grid == expected_grid || throw(ArgumentError("component rules grid differs from snapshot"))
    units = Set(u["id"] for u in document["hydraulic_network"]["units"])
    objects = required_vector(rules, "objects")
    object_ids = Set{Int}()
    for object in objects
        id = get(object, "id", nothing)
        id isa Integer && !(id isa Bool) && id > 0 && !(id in object_ids) ||
            throw(ArgumentError("invalid component rules object identity"))
        get(object, "unit_key", nothing) in units || throw(ArgumentError("component rules unit outside snapshot"))
        push!(object_ids, id)
    end
    rows = required_vector(rules, "rows")
    length(rows) <= 100000 || throw(ArgumentError("component rules row quota exceeded"))
    names = Set()
    object_units = Dict(object["id"] => only(filter(u -> u["id"] == object["unit_key"], document["hydraulic_network"]["units"])) for object in objects)
    bounds = Dict{Tuple{Int,Int},Tuple{Float64,Float64}}()
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
        get(row, "unit", nothing) == "m3_per_s" || throw(ArgumentError("invalid component rules unit"))
        constant = get(row, "constant", nothing)
        constant isa Real && !(constant isa Bool) && isfinite(constant) || throw(ArgumentError("nonfinite component rules constant"))
        terms = required_vector(row, "terms")
        term_count += length(terms)
        term_count <= 500000 || throw(ArgumentError("component rules term quota exceeded"))
        row_objects = Set()
        for term in terms
            Set(keys(term)) == Set(("object_id", "variable", "period", "coefficient", "unit")) ||
                throw(ArgumentError("unsupported component rules term fields"))
            id = get(term, "object_id", nothing)
            id isa Integer && !(id isa Bool) && id in object_ids || throw(ArgumentError("component rules object outside snapshot"))
            push!(row_objects, id)
            get(term, "variable", nothing) == "caudal" || throw(ArgumentError("unsupported component rules variable"))
            period = get(term, "period", nothing)
            period isa Integer && !(period isa Bool) && period == row_period || throw(ArgumentError("unsupported component rules period reference"))
            get(term, "unit", nothing) == "dimensionless" || throw(ArgumentError("invalid component rules coefficient unit"))
            coefficient = get(term, "coefficient", nothing)
            coefficient isa Real && !(coefficient isa Bool) && isfinite(coefficient) || throw(ArgumentError("nonfinite component rules coefficient"))
        end
        length(row_objects) <= 1 || throw(ArgumentError("multiple objects require a later capability"))
        coefficient = sum((Float64(term["coefficient"]) for term in terms); init=0.0)
        isfinite(coefficient) || throw(ArgumentError("nonfinite normalized component rules coefficient"))
        relation = row["relation"]
        if coefficient == 0
            valid = relation == "<=" ? constant <= 0 : relation == ">=" ? constant >= 0 : constant == 0
            valid || throw(ArgumentError("contradictory constant component rule $(row["name"])"))
        else
            id = only(row_objects)
            unit = object_units[id]
            curve = unit["curves"]["flow_power"]
            lower = get(unit, "min_flow_m3s", nothing)
            upper = get(unit, "max_flow_m3s", nothing)
            physical = (lower === nothing ? Float64(first(curve)["flow_m3s"]) : Float64(lower),
                        upper === nothing ? Float64(last(curve)["flow_m3s"]) : Float64(upper))
            lower, upper = get(bounds, (id, row_period), physical)
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
            bounds[(id, row_period)] = (lower, upper)
        end
    end
end
