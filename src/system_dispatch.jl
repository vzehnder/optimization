using CSV
using DataFrames
using Dates
using HiGHS
using JSON3
using JuMP
using PiecewiseLinearOpt

const SYSTEM_SCHEMA_VERSION = "bess_system_dispatch.v1"
const SYSTEM_SCHEMA_VERSION_V2 = "bess_system_dispatch.v2"
const SYSTEM_SUPPORTED_SCHEMA_VERSIONS = Set([SYSTEM_SCHEMA_VERSION, SYSTEM_SCHEMA_VERSION_V2])
const SYSTEM_BUS_NODE_TYPES = Set(["bus", "pcc"])
const SYSTEM_KNOWN_NODE_TYPES = Set(["bus", "pcc", "battery", "renewable", "grid", "load", "hydro"])
const HM3_PER_M3S_HOUR = 3600.0 / 1_000_000.0

struct SystemNode
    id::String
    type::String
    attributes::Dict{String,Any}
end

struct SystemEdge
    from::String
    to::String
end

struct SystemPeriodData
    timestamp::DateTime
    price_usd_per_mwh::Union{Float64,Nothing}
    import_price_usd_per_mwh::Float64
    export_price_usd_per_mwh::Float64
    uses_separate_prices::Bool
    duration_hours::Float64
    renewable_available_power_mw::Dict{String,Float64}
    load_demand_mw::Dict{String,Float64}
    hydro_inflow_m3s::Dict{String,Float64}
end

struct SystemGraphData
    schema_version::String
    case_name::String
    nodes::Vector{SystemNode}
    edges::Vector{SystemEdge}
    time_series::Vector{SystemPeriodData}
    constraints::Dict{String,Any}
    solver::SolverConfig
    source_path::Union{String,Nothing}
end

struct BatteryAssetParameters
    id::String
    parameters::BESSParameters
    constraints::ConstraintConfig
end

struct RenewableAssetParameters
    id::String
    curtailment_penalty_usd_per_mwh::Float64
end

struct GridAssetParameters
    id::String
    import_power_max_mw::Union{Float64,Nothing}
    export_power_max_mw::Union{Float64,Nothing}
    prevent_simultaneous_grid_import_export::Bool
end

struct LoadAssetParameters
    id::String
end

struct HydroAssetParameters
    id::String
    storage_min_hm3::Float64
    storage_max_hm3::Float64
    initial_storage_hm3::Float64
    terminal_condition::String
    terminal_storage_min_hm3::Union{Float64,Nothing}
    terminal_water_value_usd_per_hm3::Float64
    spill_penalty_usd_per_hm3::Float64
    minimum_release_m3s::Float64
    generation_mode::String
    power_per_flow_mw_per_m3s::Union{Float64,Nothing}
    power_max_mw::Union{Float64,Nothing}
    turbine_flow_min_m3s::Union{Float64,Nothing}
    turbine_flow_max_m3s::Union{Float64,Nothing}
    generation_curve::Vector{Tuple{Float64,Float64}}
    reservoir_curve::Vector{Tuple{Float64,Float64}}
end

struct SystemOptimizationData
    case_name::String
    schema_version::String
    bus_id::String
    batteries::Vector{BatteryAssetParameters}
    renewables::Vector{RenewableAssetParameters}
    grids::Vector{GridAssetParameters}
    loads::Vector{LoadAssetParameters}
    hydros::Vector{HydroAssetParameters}
    timestamp::Vector{DateTime}
    price_usd_per_mwh::Vector{Union{Float64,Nothing}}
    import_price_usd_per_mwh::Vector{Float64}
    export_price_usd_per_mwh::Vector{Float64}
    uses_separate_prices::Vector{Bool}
    duration_hours::Vector{Float64}
    renewable_available_power_mw::Matrix{Float64}
    load_demand_mw::Matrix{Float64}
    hydro_inflow_m3s::Matrix{Float64}
    solver::SolverConfig
    graph::SystemGraphData
end

struct SystemDispatchModel
    model::JuMP.Model
    p_battery_charge_mw::Matrix{JuMP.VariableRef}
    p_battery_discharge_mw::Matrix{JuMP.VariableRef}
    battery_energy_mwh::Matrix{JuMP.VariableRef}
    battery_delta_soc_abs_mwh::Union{Nothing,Matrix{JuMP.VariableRef}}
    is_battery_charging::Union{Nothing,Matrix{JuMP.VariableRef}}
    p_renewable_used_mw::Matrix{JuMP.VariableRef}
    p_renewable_curtailed_mw::Matrix{JuMP.VariableRef}
    p_grid_import_mw::Matrix{JuMP.VariableRef}
    p_grid_export_mw::Matrix{JuMP.VariableRef}
    is_grid_importing::Union{Nothing,Matrix{JuMP.VariableRef}}
    hydro_turbine_flow_m3s::Matrix{JuMP.VariableRef}
    hydro_spill_flow_m3s::Matrix{JuMP.VariableRef}
    hydro_power_mw::Matrix{JuMP.VariableRef}
    hydro_storage_hm3::Matrix{JuMP.VariableRef}
    hydro_reservoir_elevation_masl::Matrix{JuMP.VariableRef}
end

struct SystemDispatchResult
    case_name::String
    solver_name::String
    solver_status::String
    termination_status::String
    objective_value_usd::Float64
    p_battery_charge_mw::Matrix{Float64}
    p_battery_discharge_mw::Matrix{Float64}
    battery_energy_mwh::Matrix{Float64}
    battery_delta_soc_abs_mwh::Matrix{Float64}
    p_renewable_used_mw::Matrix{Float64}
    p_renewable_curtailed_mw::Matrix{Float64}
    p_grid_import_mw::Matrix{Float64}
    p_grid_export_mw::Matrix{Float64}
    market_value_usd::Vector{Float64}
    import_cost_usd::Vector{Float64}
    export_revenue_usd::Vector{Float64}
    battery_degradation_cost_usd::Matrix{Float64}
    curtailment_penalty_usd::Matrix{Float64}
    hydro_turbine_flow_m3s::Matrix{Float64}
    hydro_spill_flow_m3s::Matrix{Float64}
    hydro_power_mw::Matrix{Float64}
    hydro_storage_hm3::Matrix{Float64}
    hydro_reservoir_elevation_masl::Matrix{Float64}
    hydro_inflow_volume_hm3::Matrix{Float64}
    hydro_turbine_volume_hm3::Matrix{Float64}
    hydro_spill_volume_hm3::Matrix{Float64}
    hydro_spill_penalty_usd::Matrix{Float64}
    hydro_terminal_water_value_usd::Vector{Float64}
end

struct SystemRunOutput
    case_name::String
    run_timestamp::String
    output_dir::String
    dispatch_path::String
    asset_dispatch_path::String
    summary_path::String
    system_case_resolved_path::String
    model_metadata_path::String
    result::SystemDispatchResult
end

function load_system_case(path::AbstractString)::SystemGraphData
    resolved_path = resolve_system_case_path(path)
    document = try
        JSON3.read(read(resolved_path, String), Dict{String,Any})
    catch error
        throw(ArgumentError("system_case JSON could not be parsed: $(sprint(showerror, error))"))
    end

    system_case = SystemGraphData(
        required_string(document, "schema_version"),
        required_string(document, "case_name"),
        parse_system_nodes(required_vector(document, "nodes")),
        parse_system_edges(required_vector(document, "edges")),
        parse_system_periods(required_vector(document, "time_series")),
        optional_dict(document, "constraints"),
        load_solver_config(required_value(document, "solver")),
        abspath(resolved_path),
    )

    return validate_system_case(system_case)
end

function validate_system_case(system_case::SystemGraphData)::SystemGraphData
    if !(system_case.schema_version in SYSTEM_SUPPORTED_SCHEMA_VERSIONS)
        throw(ArgumentError(
            "schema_version must be one of $(join(sort(collect(SYSTEM_SUPPORTED_SCHEMA_VERSIONS)), ", ")); got $(system_case.schema_version)",
        ))
    end

    node_ids = String[]
    for node in system_case.nodes
        if !(node.type in SYSTEM_KNOWN_NODE_TYPES)
            throw(ArgumentError("node $(node.id) has unsupported type $(node.type)"))
        end
        if node.id in node_ids
            throw(ArgumentError("node id $(node.id) is duplicated"))
        end
        if node.type == "hydro" && system_case.schema_version != SYSTEM_SCHEMA_VERSION_V2
            throw(ArgumentError("hydro nodes require schema_version $(SYSTEM_SCHEMA_VERSION_V2)"))
        end
        push!(node_ids, node.id)
    end

    bus_nodes = [node for node in system_case.nodes if node.type in SYSTEM_BUS_NODE_TYPES]
    if isempty(bus_nodes)
        throw(ArgumentError("system graph must contain exactly one bus or PCC node; found 0"))
    elseif length(bus_nodes) > 1
        throw(ArgumentError("system graph must contain exactly one bus or PCC node; found $(length(bus_nodes))"))
    end

    node_id_set = Set(node_ids)
    for edge in system_case.edges
        if !(edge.from in node_id_set)
            throw(ArgumentError("edge references missing node id $(edge.from)"))
        end
        if !(edge.to in node_id_set)
            throw(ArgumentError("edge references missing node id $(edge.to)"))
        end
    end

    validate_system_connectivity(system_case, bus_nodes[1].id)
    validate_system_time_series(system_case.time_series)
    validate_system_asset_time_series(system_case)
    for node in system_case.nodes
        if node.type == "battery"
            parse_system_battery_asset(node)
        elseif node.type == "renewable"
            parse_system_renewable_asset(node)
        elseif node.type == "grid"
            parse_system_grid_asset(node)
        elseif node.type == "hydro"
            parse_system_hydro_asset(node)
        end
    end

    return system_case
end

function normalize_system_case(system_case::SystemGraphData)::SystemOptimizationData
    validate_system_case(system_case)

    bus_id = only([node.id for node in system_case.nodes if node.type in SYSTEM_BUS_NODE_TYPES])
    batteries = BatteryAssetParameters[]
    renewables = RenewableAssetParameters[]
    grids = GridAssetParameters[]
    loads = LoadAssetParameters[]
    hydros = HydroAssetParameters[]

    for node in system_case.nodes
        if node.type == "battery"
            push!(batteries, parse_system_battery_asset(node))
        elseif node.type == "renewable"
            push!(renewables, parse_system_renewable_asset(node))
        elseif node.type == "grid"
            push!(grids, parse_system_grid_asset(node))
        elseif node.type == "load"
            push!(loads, parse_system_load_asset(node))
        elseif node.type == "hydro"
            push!(hydros, parse_system_hydro_asset(node))
        end
    end

    if isempty(batteries)
        throw(ArgumentError("system graph must contain at least one battery node"))
    end
    if isempty(renewables)
        throw(ArgumentError("system graph must contain at least one renewable node"))
    end
    if isempty(grids)
        throw(ArgumentError("system graph must contain at least one grid node"))
    end

    timestamps = [period.timestamp for period in system_case.time_series]
    prices = [period.price_usd_per_mwh for period in system_case.time_series]
    import_prices = [period.import_price_usd_per_mwh for period in system_case.time_series]
    export_prices = [period.export_price_usd_per_mwh for period in system_case.time_series]
    uses_separate_prices = [period.uses_separate_prices for period in system_case.time_series]
    durations = [period.duration_hours for period in system_case.time_series]
    availability = zeros(length(renewables), length(system_case.time_series))
    load_demand = zeros(length(loads), length(system_case.time_series))
    hydro_inflow = zeros(length(hydros), length(system_case.time_series))

    for (renewable_index, renewable) in enumerate(renewables)
        for (period_index, period) in enumerate(system_case.time_series)
            if !haskey(period.renewable_available_power_mw, renewable.id)
                throw(ArgumentError(
                    "renewable_available_power_mw for asset $(renewable.id) is required at time_series[$period_index]",
                ))
            end

            value = period.renewable_available_power_mw[renewable.id]
            if !isfinite(value) || value < 0
                throw(ArgumentError(
                    "renewable_available_power_mw[$(renewable.id)] at time_series[$period_index] must be nonnegative; got $value",
                ))
            end
            availability[renewable_index, period_index] = value
        end
    end

    for (load_index, load) in enumerate(loads)
        for (period_index, period) in enumerate(system_case.time_series)
            load_demand[load_index, period_index] = period.load_demand_mw[load.id]
        end
    end

    for (hydro_index, hydro) in enumerate(hydros)
        for (period_index, period) in enumerate(system_case.time_series)
            hydro_inflow[hydro_index, period_index] = period.hydro_inflow_m3s[hydro.id]
        end
    end

    return SystemOptimizationData(
        system_case.case_name,
        system_case.schema_version,
        bus_id,
        batteries,
        renewables,
        grids,
        loads,
        hydros,
        timestamps,
        prices,
        import_prices,
        export_prices,
        uses_separate_prices,
        durations,
        availability,
        load_demand,
        hydro_inflow,
        system_case.solver,
        system_case,
    )
end

function parse_system_renewable_asset(node::SystemNode)::RenewableAssetParameters
    penalty = optional_float(
        get(node.attributes, "curtailment_penalty_usd_per_mwh", 0.0),
        "curtailment_penalty_usd_per_mwh",
    )
    if !isfinite(penalty) || penalty < 0
        throw(ArgumentError(
            "renewable $(node.id) curtailment_penalty_usd_per_mwh must be nonnegative; got $penalty",
        ))
    end

    return RenewableAssetParameters(node.id, penalty)
end

function parse_system_load_asset(node::SystemNode)::LoadAssetParameters
    return LoadAssetParameters(node.id)
end

function parse_system_grid_asset(node::SystemNode)::GridAssetParameters
    import_limit = optional_float(get(node.attributes, "import_power_max_mw", nothing), "import_power_max_mw")
    export_limit = optional_float(get(node.attributes, "export_power_max_mw", nothing), "export_power_max_mw")
    if import_limit !== nothing && (!isfinite(import_limit) || import_limit < 0)
        throw(ArgumentError("grid $(node.id) import_power_max_mw must be nonnegative; got $import_limit"))
    end
    if export_limit !== nothing && (!isfinite(export_limit) || export_limit < 0)
        throw(ArgumentError("grid $(node.id) export_power_max_mw must be nonnegative; got $export_limit"))
    end

    return GridAssetParameters(
        node.id,
        import_limit,
        export_limit,
        optional_bool(node.attributes, "prevent_simultaneous_grid_import_export", true),
    )
end

function parse_system_battery_asset(node::SystemNode)::BatteryAssetParameters
    battery = BatteryAssetParameters(
        node.id,
        BESSParameters(
            required_float(node.attributes, "charge_power_max_mw"),
            required_float(node.attributes, "discharge_power_max_mw"),
            required_float(node.attributes, "energy_min_mwh"),
            required_float(node.attributes, "energy_max_mwh"),
            required_float(node.attributes, "initial_energy_mwh"),
            required_float(node.attributes, "charge_efficiency"),
            required_float(node.attributes, "discharge_efficiency"),
            required_float(node.attributes, "degradation_cost_per_mwh_delta_soc"),
        ),
        ConstraintConfig(
            optional_bool(node.attributes, "prevent_simultaneous_charge_discharge", true),
            optional_string(node.attributes, "terminal_condition", "equal_initial"),
            optional_float(get(node.attributes, "terminal_energy_min_mwh", nothing), "terminal_energy_min_mwh"),
            optional_bool(node.attributes, "degradation_linear_delta_soc", true),
        ),
    )

    validate_system_battery(node.id, battery.parameters, battery.constraints)
    return battery
end

function parse_system_hydro_asset(node::SystemNode)::HydroAssetParameters
    storage_min = required_float(node.attributes, "storage_min_hm3")
    storage_max = required_float(node.attributes, "storage_max_hm3")
    initial_storage = required_float(node.attributes, "initial_storage_hm3")
    terminal_condition = optional_string(node.attributes, "terminal_condition", "none")
    terminal_storage_min = optional_float(
        get(node.attributes, "terminal_storage_min_hm3", nothing),
        "terminal_storage_min_hm3",
    )
    terminal_water_value = optional_float(
        get(node.attributes, "terminal_water_value_usd_per_hm3", 0.0),
        "terminal_water_value_usd_per_hm3",
    )
    spill_penalty = optional_float(
        get(node.attributes, "spill_penalty_usd_per_hm3", 0.0),
        "spill_penalty_usd_per_hm3",
    )
    minimum_release = optional_float(get(node.attributes, "minimum_release_m3s", 0.0), "minimum_release_m3s")
    generation_mode = required_string(node.attributes, "generation_mode")
    power_per_flow = optional_float(
        get(node.attributes, "power_per_flow_mw_per_m3s", nothing),
        "power_per_flow_mw_per_m3s",
    )
    power_max = optional_float(get(node.attributes, "power_max_mw", nothing), "power_max_mw")
    turbine_flow_min = optional_float(get(node.attributes, "turbine_flow_min_m3s", nothing), "turbine_flow_min_m3s")
    turbine_flow_max = optional_float(get(node.attributes, "turbine_flow_max_m3s", nothing), "turbine_flow_max_m3s")
    generation_curve = generation_mode == "piecewise_linear" ?
                       parse_hydro_generation_curve(required_vector(node.attributes, "generation_curve"), node.id) :
                       Tuple{Float64,Float64}[]
    reservoir_curve = parse_hydro_reservoir_curve(required_vector(node.attributes, "reservoir_curve"), node.id)

    hydro = HydroAssetParameters(
        node.id,
        storage_min,
        storage_max,
        initial_storage,
        terminal_condition,
        terminal_storage_min,
        terminal_water_value,
        spill_penalty,
        minimum_release,
        generation_mode,
        power_per_flow,
        power_max,
        turbine_flow_min,
        turbine_flow_max,
        generation_curve,
        reservoir_curve,
    )

    validate_system_hydro(hydro)
    return hydro
end

function validate_system_hydro(hydro::HydroAssetParameters)
    if !isfinite(hydro.storage_min_hm3) || !isfinite(hydro.storage_max_hm3) ||
       !(hydro.storage_min_hm3 < hydro.storage_max_hm3)
        throw(ArgumentError(
            "hydro $(hydro.id) storage_min_hm3 must be less than storage_max_hm3",
        ))
    end
    if !isfinite(hydro.initial_storage_hm3) ||
       hydro.initial_storage_hm3 < hydro.storage_min_hm3 ||
       hydro.initial_storage_hm3 > hydro.storage_max_hm3
        throw(ArgumentError("hydro $(hydro.id) initial_storage_hm3 must be within storage bounds"))
    end
    if !(hydro.terminal_condition in ("none", "equal_initial", "min_terminal"))
        throw(ArgumentError("hydro $(hydro.id) terminal_condition must be one of none, equal_initial, min_terminal"))
    end
    if hydro.terminal_condition == "min_terminal" && hydro.terminal_storage_min_hm3 === nothing
        throw(ArgumentError("hydro $(hydro.id) terminal_storage_min_hm3 is required when terminal_condition is min_terminal"))
    end
    if hydro.terminal_storage_min_hm3 !== nothing &&
       (hydro.terminal_storage_min_hm3 < hydro.storage_min_hm3 ||
        hydro.terminal_storage_min_hm3 > hydro.storage_max_hm3)
        throw(ArgumentError("hydro $(hydro.id) terminal_storage_min_hm3 must be within storage bounds"))
    end
    if !isfinite(hydro.terminal_water_value_usd_per_hm3) || hydro.terminal_water_value_usd_per_hm3 < 0
        throw(ArgumentError("hydro $(hydro.id) terminal_water_value_usd_per_hm3 must be nonnegative"))
    end
    if !isfinite(hydro.spill_penalty_usd_per_hm3) || hydro.spill_penalty_usd_per_hm3 < 0
        throw(ArgumentError("hydro $(hydro.id) spill_penalty_usd_per_hm3 must be nonnegative"))
    end
    if !isfinite(hydro.minimum_release_m3s) || hydro.minimum_release_m3s < 0
        throw(ArgumentError("hydro $(hydro.id) minimum_release_m3s must be nonnegative"))
    end
    if !(hydro.generation_mode in ("linear", "piecewise_linear"))
        throw(ArgumentError("hydro $(hydro.id) generation_mode must be one of linear, piecewise_linear"))
    end
    if hydro.generation_mode == "linear"
        if hydro.power_per_flow_mw_per_m3s === nothing
            throw(ArgumentError("hydro $(hydro.id) power_per_flow_mw_per_m3s is required for linear generation"))
        end
        if !isfinite(hydro.power_per_flow_mw_per_m3s) || hydro.power_per_flow_mw_per_m3s < 0
            throw(ArgumentError("hydro $(hydro.id) power_per_flow_mw_per_m3s must be nonnegative"))
        end
        if hydro.turbine_flow_max_m3s === nothing
            throw(ArgumentError("hydro $(hydro.id) turbine_flow_max_m3s is required for linear generation"))
        end
    end
    if hydro.power_max_mw !== nothing && (!isfinite(hydro.power_max_mw) || hydro.power_max_mw < 0)
        throw(ArgumentError("hydro $(hydro.id) power_max_mw must be nonnegative"))
    end
    if hydro.turbine_flow_min_m3s !== nothing &&
       (!isfinite(hydro.turbine_flow_min_m3s) || hydro.turbine_flow_min_m3s < 0)
        throw(ArgumentError("hydro $(hydro.id) turbine_flow_min_m3s must be nonnegative"))
    end
    if hydro.turbine_flow_max_m3s !== nothing &&
       (!isfinite(hydro.turbine_flow_max_m3s) || hydro.turbine_flow_max_m3s < 0)
        throw(ArgumentError("hydro $(hydro.id) turbine_flow_max_m3s must be nonnegative"))
    end
    if hydro.turbine_flow_min_m3s !== nothing &&
       hydro.turbine_flow_max_m3s !== nothing &&
       hydro.turbine_flow_min_m3s > hydro.turbine_flow_max_m3s
        throw(ArgumentError("hydro $(hydro.id) turbine_flow_min_m3s must not exceed turbine_flow_max_m3s"))
    end
    if hydro.generation_mode == "piecewise_linear"
        curve_min = first(hydro.generation_curve)[1]
        curve_max = last(hydro.generation_curve)[1]
        for (name, value) in (
            ("turbine_flow_min_m3s", hydro.turbine_flow_min_m3s),
            ("turbine_flow_max_m3s", hydro.turbine_flow_max_m3s),
        )
            if value !== nothing && (value < curve_min || value > curve_max)
                throw(ArgumentError("hydro $(hydro.id) $name must lie within generation_curve domain"))
            end
        end
    end

    curve_min = first(hydro.reservoir_curve)[1]
    curve_max = last(hydro.reservoir_curve)[1]
    storage_values = [
        hydro.storage_min_hm3,
        hydro.storage_max_hm3,
        hydro.initial_storage_hm3,
    ]
    if hydro.terminal_storage_min_hm3 !== nothing
        push!(storage_values, hydro.terminal_storage_min_hm3)
    end
    for value in storage_values
        if value < curve_min || value > curve_max
            throw(ArgumentError("hydro $(hydro.id) storage values must lie within reservoir_curve domain"))
        end
    end
end

function parse_hydro_generation_curve(curve_values, hydro_id::String)::Vector{Tuple{Float64,Float64}}
    if length(curve_values) < 2
        throw(ArgumentError("hydro $hydro_id generation_curve must contain at least two breakpoints"))
    end

    curve = Tuple{Float64,Float64}[]
    previous_flow = nothing
    for (index, point) in enumerate(curve_values)
        point_dict = to_string_key_dict(point)
        flow = parse_required_float(
            required_value(point_dict, "flow_m3s"),
            "generation_curve[$index].flow_m3s",
        )
        power = parse_required_float(
            required_value(point_dict, "power_mw"),
            "generation_curve[$index].power_mw",
        )
        if !isfinite(flow) || flow < 0
            throw(ArgumentError("hydro $hydro_id generation_curve flow_m3s must be nonnegative and finite"))
        end
        if previous_flow !== nothing && !(previous_flow < flow)
            throw(ArgumentError("hydro $hydro_id generation_curve flow_m3s must be strictly increasing"))
        end
        if !isfinite(power) || power < 0
            throw(ArgumentError("hydro $hydro_id generation_curve power_mw must be nonnegative and finite"))
        end
        push!(curve, (flow, power))
        previous_flow = flow
    end

    return curve
end

function parse_hydro_reservoir_curve(curve_values, hydro_id::String)::Vector{Tuple{Float64,Float64}}
    if length(curve_values) < 2
        throw(ArgumentError("hydro $hydro_id reservoir_curve must contain at least two breakpoints"))
    end

    curve = Tuple{Float64,Float64}[]
    previous_storage = nothing
    previous_elevation = nothing
    for (index, point) in enumerate(curve_values)
        point_dict = to_string_key_dict(point)
        storage = parse_required_float(
            required_value(point_dict, "storage_hm3"),
            "reservoir_curve[$index].storage_hm3",
        )
        elevation = parse_required_float(
            required_value(point_dict, "elevation_masl"),
            "reservoir_curve[$index].elevation_masl",
        )
        if !isfinite(storage)
            throw(ArgumentError("hydro $hydro_id reservoir_curve storage_hm3 must be finite"))
        end
        if !isfinite(elevation)
            throw(ArgumentError("hydro $hydro_id reservoir_curve elevation_masl must be finite"))
        end
        if previous_storage !== nothing && !(previous_storage < storage)
            throw(ArgumentError("hydro $hydro_id reservoir_curve storage_hm3 must be strictly increasing"))
        end
        if previous_elevation !== nothing && elevation < previous_elevation
            throw(ArgumentError("hydro $hydro_id reservoir_curve elevation_masl must be nondecreasing"))
        end
        push!(curve, (storage, elevation))
        previous_storage = storage
        previous_elevation = elevation
    end

    return curve
end

function build_system_dispatch_model(data::SystemOptimizationData)::SystemDispatchModel
    if data.solver.name != "HiGHS"
        throw(ArgumentError("only HiGHS solver is supported; got $(data.solver.name)"))
    end

    n_batteries = length(data.batteries)
    n_renewables = length(data.renewables)
    n_grids = length(data.grids)
    n_loads = length(data.loads)
    n_hydros = length(data.hydros)
    n_periods = length(data.timestamp)

    model = Model(HiGHS.Optimizer)
    set_silent(model)

    for (name, value) in data.solver.options
        set_optimizer_attribute(model, name, value)
    end

    @variable(model, p_battery_charge_mw[1:n_batteries, 1:n_periods] >= 0)
    @variable(model, p_battery_discharge_mw[1:n_batteries, 1:n_periods] >= 0)
    @variable(model, battery_energy_mwh[1:n_batteries, 1:n_periods])
    @variable(model, p_renewable_used_mw[1:n_renewables, 1:n_periods] >= 0)
    @variable(model, p_renewable_curtailed_mw[1:n_renewables, 1:n_periods] >= 0)
    @variable(model, hydro_turbine_flow_m3s[1:n_hydros, 1:n_periods] >= 0)
    @variable(model, hydro_spill_flow_m3s[1:n_hydros, 1:n_periods] >= 0)
    @variable(model, hydro_power_mw[1:n_hydros, 1:n_periods] >= 0)
    @variable(model, hydro_storage_hm3[1:n_hydros, 1:n_periods])
    @variable(model, hydro_reservoir_elevation_masl[1:n_hydros, 1:n_periods])

    grid_import_bounds = system_grid_import_bounds(data)
    grid_export_bounds = system_grid_export_bounds(data)
    @variable(model, 0 <= p_grid_import_mw[grid in 1:n_grids, period in 1:n_periods] <= grid_import_bounds[grid])
    @variable(model, 0 <= p_grid_export_mw[grid in 1:n_grids, period in 1:n_periods] <= grid_export_bounds[grid])

    is_grid_importing = nothing
    if any(grid.prevent_simultaneous_grid_import_export for grid in data.grids)
        @variable(model, is_grid_importing[1:n_grids, 1:n_periods], Bin)

        for (grid_index, grid) in enumerate(data.grids)
            if grid.prevent_simultaneous_grid_import_export
                @constraint(
                    model,
                    [period in 1:n_periods],
                    p_grid_import_mw[grid_index, period] <= grid_import_bounds[grid_index] * is_grid_importing[grid_index, period]
                )
                @constraint(
                    model,
                    [period in 1:n_periods],
                    p_grid_export_mw[grid_index, period] <=
                    grid_export_bounds[grid_index] * (1 - is_grid_importing[grid_index, period])
                )
            else
                @constraint(model, [period in 1:n_periods], is_grid_importing[grid_index, period] == 0)
            end
        end
    end

    delta_soc_abs_mwh = nothing
    if any(battery.constraints.degradation_linear_delta_soc for battery in data.batteries)
        @variable(model, 0 <= delta_soc_abs_mwh[1:n_batteries, 1:n_periods])
    end

    is_battery_charging = nothing
    if any(battery.constraints.prevent_simultaneous_charge_discharge for battery in data.batteries)
        @variable(model, is_battery_charging[1:n_batteries, 1:n_periods], Bin)
    end

    for (battery_index, battery_asset) in enumerate(data.batteries)
        bess = battery_asset.parameters
        constraints = battery_asset.constraints

        @constraint(
            model,
            [period in 1:n_periods],
            p_battery_charge_mw[battery_index, period] <= bess.charge_power_max_mw
        )
        @constraint(
            model,
            [period in 1:n_periods],
            p_battery_discharge_mw[battery_index, period] <= bess.discharge_power_max_mw
        )
        @constraint(
            model,
            [period in 1:n_periods],
            bess.energy_min_mwh <= battery_energy_mwh[battery_index, period] <= bess.energy_max_mwh
        )

        if constraints.prevent_simultaneous_charge_discharge
            @constraint(
                model,
                [period in 1:n_periods],
                p_battery_charge_mw[battery_index, period] <=
                bess.charge_power_max_mw * is_battery_charging[battery_index, period]
            )
            @constraint(
                model,
                [period in 1:n_periods],
                p_battery_discharge_mw[battery_index, period] <=
                bess.discharge_power_max_mw * (1 - is_battery_charging[battery_index, period])
            )
        elseif is_battery_charging !== nothing
            @constraint(model, [period in 1:n_periods], is_battery_charging[battery_index, period] == 0)
        end

        @constraint(
            model,
            battery_energy_mwh[battery_index, 1] ==
            bess.initial_energy_mwh +
            bess.charge_efficiency * p_battery_charge_mw[battery_index, 1] * data.duration_hours[1] -
            (p_battery_discharge_mw[battery_index, 1] / bess.discharge_efficiency) * data.duration_hours[1]
        )

        for period in 2:n_periods
            @constraint(
                model,
                battery_energy_mwh[battery_index, period] ==
                battery_energy_mwh[battery_index, period - 1] +
                bess.charge_efficiency * p_battery_charge_mw[battery_index, period] * data.duration_hours[period] -
                (p_battery_discharge_mw[battery_index, period] / bess.discharge_efficiency) * data.duration_hours[period]
            )
        end

        if constraints.terminal_condition == "equal_initial"
            @constraint(model, battery_energy_mwh[battery_index, n_periods] == bess.initial_energy_mwh)
        elseif constraints.terminal_condition == "min_terminal"
            @constraint(model, battery_energy_mwh[battery_index, n_periods] >= constraints.terminal_energy_min_mwh)
        end

        if constraints.degradation_linear_delta_soc
            @constraint(
                model,
                delta_soc_abs_mwh[battery_index, 1] >= battery_energy_mwh[battery_index, 1] - bess.initial_energy_mwh
            )
            @constraint(
                model,
                delta_soc_abs_mwh[battery_index, 1] >= bess.initial_energy_mwh - battery_energy_mwh[battery_index, 1]
            )

            for period in 2:n_periods
                @constraint(
                    model,
                    delta_soc_abs_mwh[battery_index, period] >=
                    battery_energy_mwh[battery_index, period] - battery_energy_mwh[battery_index, period - 1]
                )
                @constraint(
                    model,
                    delta_soc_abs_mwh[battery_index, period] >=
                    battery_energy_mwh[battery_index, period - 1] - battery_energy_mwh[battery_index, period]
                )
            end
        elseif delta_soc_abs_mwh !== nothing
            @constraint(model, [period in 1:n_periods], delta_soc_abs_mwh[battery_index, period] == 0)
        end
    end

    for (hydro_index, hydro) in enumerate(data.hydros)
        @constraint(
            model,
            [period in 1:n_periods],
            hydro.storage_min_hm3 <= hydro_storage_hm3[hydro_index, period] <= hydro.storage_max_hm3
        )
        @constraint(
            model,
            [period in 1:n_periods],
            hydro_turbine_flow_m3s[hydro_index, period] <= hydro_turbine_flow_upper_bound(hydro)
        )
        turbine_flow_lower_bound = hydro_turbine_flow_lower_bound(hydro)
        if turbine_flow_lower_bound > 0.0
            @constraint(
                model,
                [period in 1:n_periods],
                hydro_turbine_flow_m3s[hydro_index, period] >= turbine_flow_lower_bound
            )
        end
        @constraint(
            model,
            [period in 1:n_periods],
            hydro_turbine_flow_m3s[hydro_index, period] + hydro_spill_flow_m3s[hydro_index, period] >=
            hydro.minimum_release_m3s
        )
        if hydro.generation_mode == "linear"
            @constraint(
                model,
                [period in 1:n_periods],
                hydro_power_mw[hydro_index, period] ==
                hydro.power_per_flow_mw_per_m3s * hydro_turbine_flow_m3s[hydro_index, period]
            )
        else
            flow_breakpoints = hydro_generation_flow_breakpoints(hydro)
            power_breakpoints = hydro_generation_power_breakpoints(hydro)
            for period in 1:n_periods
                piecewise_power = PiecewiseLinearOpt.piecewiselinear(
                    model,
                    hydro_turbine_flow_m3s[hydro_index, period],
                    flow_breakpoints,
                    power_breakpoints,
                )
                @constraint(model, hydro_power_mw[hydro_index, period] == piecewise_power)
            end
        end
        if hydro.power_max_mw !== nothing
            @constraint(
                model,
                [period in 1:n_periods],
                hydro_power_mw[hydro_index, period] <= hydro.power_max_mw
            )
        end
        storage_breakpoints = hydro_reservoir_storage_breakpoints(hydro)
        elevation_breakpoints = hydro_reservoir_elevation_breakpoints(hydro)
        for period in 1:n_periods
            piecewise_elevation = PiecewiseLinearOpt.piecewiselinear(
                model,
                hydro_storage_hm3[hydro_index, period],
                storage_breakpoints,
                elevation_breakpoints,
            )
            @constraint(model, hydro_reservoir_elevation_masl[hydro_index, period] == piecewise_elevation)
        end

        @constraint(
            model,
            hydro_storage_hm3[hydro_index, 1] ==
            hydro.initial_storage_hm3 +
            data.hydro_inflow_m3s[hydro_index, 1] * data.duration_hours[1] * HM3_PER_M3S_HOUR -
            hydro_turbine_flow_m3s[hydro_index, 1] * data.duration_hours[1] * HM3_PER_M3S_HOUR -
            hydro_spill_flow_m3s[hydro_index, 1] * data.duration_hours[1] * HM3_PER_M3S_HOUR
        )

        for period in 2:n_periods
            @constraint(
                model,
                hydro_storage_hm3[hydro_index, period] ==
                hydro_storage_hm3[hydro_index, period - 1] +
                data.hydro_inflow_m3s[hydro_index, period] * data.duration_hours[period] * HM3_PER_M3S_HOUR -
                hydro_turbine_flow_m3s[hydro_index, period] * data.duration_hours[period] * HM3_PER_M3S_HOUR -
                hydro_spill_flow_m3s[hydro_index, period] * data.duration_hours[period] * HM3_PER_M3S_HOUR
            )
        end

        if hydro.terminal_condition == "equal_initial"
            @constraint(model, hydro_storage_hm3[hydro_index, n_periods] == hydro.initial_storage_hm3)
        elseif hydro.terminal_condition == "min_terminal"
            @constraint(model, hydro_storage_hm3[hydro_index, n_periods] >= hydro.terminal_storage_min_hm3)
        end
    end

    @constraint(
        model,
        [renewable in 1:n_renewables, period in 1:n_periods],
        p_renewable_used_mw[renewable, period] + p_renewable_curtailed_mw[renewable, period] ==
        data.renewable_available_power_mw[renewable, period]
    )

    @constraint(
        model,
        [period in 1:n_periods],
        sum(p_grid_import_mw[grid, period] for grid in 1:n_grids) +
        sum(p_renewable_used_mw[renewable, period] for renewable in 1:n_renewables) +
        sum(p_battery_discharge_mw[battery, period] for battery in 1:n_batteries) +
        sum(hydro_power_mw[hydro, period] for hydro in 1:n_hydros) ==
        sum(p_grid_export_mw[grid, period] for grid in 1:n_grids) +
        sum(p_battery_charge_mw[battery, period] for battery in 1:n_batteries) +
        sum(data.load_demand_mw[load, period] for load in 1:n_loads)
    )

    market_value_objective = sum(
        (
            data.export_price_usd_per_mwh[period] *
            sum(p_grid_export_mw[grid, period] for grid in 1:n_grids) -
            data.import_price_usd_per_mwh[period] *
            sum(p_grid_import_mw[grid, period] for grid in 1:n_grids)
        ) *
        data.duration_hours[period] for period in 1:n_periods
    )

    battery_degradation_cost_objective = sum(
        battery_asset.constraints.degradation_linear_delta_soc ?
        battery_asset.parameters.degradation_cost_per_mwh_delta_soc * delta_soc_abs_mwh[battery_index, period] :
        0.0 for (battery_index, battery_asset) in enumerate(data.batteries), period in 1:n_periods
    )

    curtailment_penalty_objective = sum(
        data.renewables[renewable].curtailment_penalty_usd_per_mwh *
        p_renewable_curtailed_mw[renewable, period] *
        data.duration_hours[period] for renewable in 1:n_renewables, period in 1:n_periods
    )

    hydro_spill_penalty_objective = sum(
        data.hydros[hydro].spill_penalty_usd_per_hm3 *
        hydro_spill_flow_m3s[hydro, period] *
        data.duration_hours[period] *
        HM3_PER_M3S_HOUR for hydro in 1:n_hydros, period in 1:n_periods;
        init = 0.0,
    )
    hydro_terminal_water_value_objective = sum(
        data.hydros[hydro].terminal_water_value_usd_per_hm3 *
        hydro_storage_hm3[hydro, n_periods] for hydro in 1:n_hydros;
        init = 0.0,
    )

    @objective(
        model,
        Max,
        market_value_objective -
        battery_degradation_cost_objective -
        curtailment_penalty_objective -
        hydro_spill_penalty_objective +
        hydro_terminal_water_value_objective
    )

    return SystemDispatchModel(
        model,
        p_battery_charge_mw,
        p_battery_discharge_mw,
        battery_energy_mwh,
        delta_soc_abs_mwh,
        is_battery_charging,
        p_renewable_used_mw,
        p_renewable_curtailed_mw,
        p_grid_import_mw,
        p_grid_export_mw,
        is_grid_importing,
        hydro_turbine_flow_m3s,
        hydro_spill_flow_m3s,
        hydro_power_mw,
        hydro_storage_hm3,
        hydro_reservoir_elevation_masl,
    )
end

function solve_system_dispatch(system_case::SystemGraphData)::SystemDispatchResult
    return solve_system_dispatch(normalize_system_case(system_case))
end

function solve_system_dispatch(data::SystemOptimizationData)::SystemDispatchResult
    dispatch_model = build_system_dispatch_model(data)
    optimize!(dispatch_model.model)

    termination = string(termination_status(dispatch_model.model))
    solver_status = raw_solver_status(dispatch_model.model, termination)
    if !has_values(dispatch_model.model)
        throw(ErrorException("optimization finished without primal values; termination_status=$termination"))
    end

    p_battery_charge = value.(dispatch_model.p_battery_charge_mw)
    p_battery_discharge = value.(dispatch_model.p_battery_discharge_mw)
    battery_energy = value.(dispatch_model.battery_energy_mwh)
    p_renewable_used = value.(dispatch_model.p_renewable_used_mw)
    p_renewable_curtailed = value.(dispatch_model.p_renewable_curtailed_mw)
    p_grid_import = value.(dispatch_model.p_grid_import_mw)
    p_grid_export = value.(dispatch_model.p_grid_export_mw)
    hydro_turbine_flow = value.(dispatch_model.hydro_turbine_flow_m3s)
    hydro_spill_flow = value.(dispatch_model.hydro_spill_flow_m3s)
    hydro_power = value.(dispatch_model.hydro_power_mw)
    hydro_storage = value.(dispatch_model.hydro_storage_hm3)
    hydro_elevation = value.(dispatch_model.hydro_reservoir_elevation_masl)

    battery_delta_soc_abs = realized_system_delta_soc_abs(data, battery_energy)
    grid_import = period_sum(p_grid_import, length(data.timestamp))
    grid_export = period_sum(p_grid_export, length(data.timestamp))
    import_cost = data.import_price_usd_per_mwh .* grid_import .* data.duration_hours
    export_revenue = data.export_price_usd_per_mwh .* grid_export .* data.duration_hours
    market_value = export_revenue .- import_cost
    battery_degradation_cost = zeros(size(battery_delta_soc_abs))
    for (battery_index, battery_asset) in enumerate(data.batteries)
        if battery_asset.constraints.degradation_linear_delta_soc
            battery_degradation_cost[battery_index, :] .=
                battery_asset.parameters.degradation_cost_per_mwh_delta_soc .* battery_delta_soc_abs[battery_index, :]
        end
    end

    curtailment_penalty = zeros(size(p_renewable_curtailed))
    for (renewable_index, renewable) in enumerate(data.renewables)
        curtailment_penalty[renewable_index, :] .=
            renewable.curtailment_penalty_usd_per_mwh .* p_renewable_curtailed[renewable_index, :] .* data.duration_hours
    end
    hydro_inflow_volume = hydro_volume_matrix(data.hydro_inflow_m3s, data.duration_hours)
    hydro_turbine_volume = hydro_volume_matrix(hydro_turbine_flow, data.duration_hours)
    hydro_spill_volume = hydro_volume_matrix(hydro_spill_flow, data.duration_hours)
    hydro_spill_penalty = zeros(size(hydro_spill_volume))
    hydro_terminal_value = zeros(length(data.hydros))
    for (hydro_index, hydro) in enumerate(data.hydros)
        hydro_spill_penalty[hydro_index, :] .=
            hydro.spill_penalty_usd_per_hm3 .* hydro_spill_volume[hydro_index, :]
        hydro_terminal_value[hydro_index] =
            hydro.terminal_water_value_usd_per_hm3 * hydro_storage[hydro_index, end]
    end

    return SystemDispatchResult(
        data.case_name,
        data.solver.name,
        solver_status,
        termination,
        objective_value(dispatch_model.model),
        p_battery_charge,
        p_battery_discharge,
        battery_energy,
        battery_delta_soc_abs,
        p_renewable_used,
        p_renewable_curtailed,
        p_grid_import,
        p_grid_export,
        market_value,
        import_cost,
        export_revenue,
        battery_degradation_cost,
        curtailment_penalty,
        hydro_turbine_flow,
        hydro_spill_flow,
        hydro_power,
        hydro_storage,
        hydro_elevation,
        hydro_inflow_volume,
        hydro_turbine_volume,
        hydro_spill_volume,
        hydro_spill_penalty,
        hydro_terminal_value,
    )
end

function run_system_case(
    path::AbstractString;
    output_root::AbstractString = "outputs",
    run_timestamp = nothing,
)::SystemRunOutput
    resolved_path = resolve_system_case_path(path)
    system_case = load_system_case(resolved_path)
    optimization_data = normalize_system_case(system_case)
    result = solve_system_dispatch(optimization_data)

    return write_system_run_outputs(
        system_case,
        optimization_data,
        result;
        output_root,
        run_timestamp,
        source_identifiers = system_case_source_identifiers(resolved_path),
    )
end

function write_system_run_outputs(
    system_case::SystemGraphData,
    data::SystemOptimizationData,
    result::SystemDispatchResult;
    output_root::AbstractString = "outputs",
    run_timestamp = nothing,
    source_identifiers = Dict{String,Any}(),
)::SystemRunOutput
    run_timestamp_id = format_run_timestamp(run_timestamp)
    case_output_root = joinpath(output_root, data.case_name)
    output_dir, resolved_run_timestamp = unique_run_output_dir(case_output_root, run_timestamp_id)
    mkpath(output_dir)

    dispatch_path = joinpath(output_dir, "dispatch.csv")
    asset_dispatch_path = joinpath(output_dir, "asset_dispatch.csv")
    summary_path = joinpath(output_dir, "summary.json")
    system_case_resolved_path = joinpath(output_dir, "system_case_resolved.json")
    model_metadata_path = joinpath(output_dir, "model_metadata.json")

    CSV.write(dispatch_path, system_dispatch_dataframe(data, result))
    CSV.write(asset_dispatch_path, system_asset_dispatch_dataframe(data, result))
    write_json_file(summary_path, system_summary_dict(data, result, resolved_run_timestamp, source_identifiers))
    write_json_file(system_case_resolved_path, system_case_dict(system_case))
    write_json_file(model_metadata_path, system_model_metadata_dict(data))

    return SystemRunOutput(
        data.case_name,
        resolved_run_timestamp,
        output_dir,
        dispatch_path,
        asset_dispatch_path,
        summary_path,
        system_case_resolved_path,
        model_metadata_path,
        result,
    )
end

function resolve_system_case_path(path::AbstractString)::String
    return isdir(path) ? joinpath(path, "system_case.json") : String(path)
end

function parse_system_nodes(nodes)::Vector{SystemNode}
    parsed_nodes = SystemNode[]
    for (index, node) in enumerate(nodes)
        try
            node_dict = to_string_key_dict(node)
            id = required_string(node_dict, "id")
            type = required_string(node_dict, "type")
            attributes = Dict{String,Any}(
                string(key) => value for (key, value) in pairs(node_dict) if !(string(key) in ("id", "type"))
            )
            push!(parsed_nodes, SystemNode(id, type, attributes))
        catch error
            throw(ArgumentError("nodes[$index] is invalid: $(sprint(showerror, error))"))
        end
    end

    return parsed_nodes
end

function parse_system_edges(edges)::Vector{SystemEdge}
    parsed_edges = SystemEdge[]
    supported_fields = Set(["from", "to"])

    for (index, edge) in enumerate(edges)
        try
            edge_dict = to_string_key_dict(edge)
            unsupported_fields = setdiff(Set(keys(edge_dict)), supported_fields)
            if !isempty(unsupported_fields)
                field = first(sort(collect(unsupported_fields)))
                throw(ArgumentError(
                    "edges[$index] field $field is not supported; edges are logical connectivity only",
                ))
            end

            push!(parsed_edges, SystemEdge(
                required_string(edge_dict, "from"),
                required_string(edge_dict, "to"),
            ))
        catch error
            if error isa ArgumentError
                rethrow()
            end
            throw(ArgumentError("edges[$index] is invalid: $(sprint(showerror, error))"))
        end
    end

    return parsed_edges
end

function parse_system_periods(periods)::Vector{SystemPeriodData}
    parsed_periods = SystemPeriodData[]

    for (index, period) in enumerate(periods)
        try
            period_dict = to_string_key_dict(period)
            renewable_values = Dict{String,Float64}()
            raw_renewable_values = get(period_dict, "renewable_available_power_mw", Dict{String,Any}())
            for (asset_id, value) in pairs(to_string_key_dict(raw_renewable_values))
                renewable_values[string(asset_id)] = parse_required_float(
                    value,
                    "time_series[$index].renewable_available_power_mw[$asset_id]",
                )
            end

            load_values = Dict{String,Float64}()
            raw_load_values = get(period_dict, "load_demand_mw", Dict{String,Any}())
            for (asset_id, value) in pairs(to_string_key_dict(raw_load_values))
                load_values[string(asset_id)] = parse_required_float(
                    value,
                    "time_series[$index].load_demand_mw[$asset_id]",
                )
            end

            hydro_values = Dict{String,Float64}()
            raw_hydro_values = get(period_dict, "hydro_inflow_m3s", Dict{String,Any}())
            for (asset_id, value) in pairs(to_string_key_dict(raw_hydro_values))
                hydro_values[string(asset_id)] = parse_required_float(
                    value,
                    "time_series[$index].hydro_inflow_m3s[$asset_id]",
                )
            end

            legacy_price, import_price, export_price, uses_separate_prices = parse_system_period_prices(
                period_dict,
                index,
            )

            push!(parsed_periods, SystemPeriodData(
                parse_required_datetime(required_value(period_dict, "timestamp"), "time_series[$index].timestamp"),
                legacy_price,
                import_price,
                export_price,
                uses_separate_prices,
                parse_required_float(required_value(period_dict, "duration_hours"), "time_series[$index].duration_hours"),
                renewable_values,
                load_values,
                hydro_values,
            ))
        catch error
            throw(ArgumentError("time_series[$index] is invalid: $(sprint(showerror, error))"))
        end
    end

    return parsed_periods
end

function parse_system_period_prices(period_dict::Dict{String,Any}, index::Int)
    has_legacy_price = haskey(period_dict, "price_usd_per_mwh") && period_dict["price_usd_per_mwh"] !== nothing
    has_import_price =
        haskey(period_dict, "import_price_usd_per_mwh") && period_dict["import_price_usd_per_mwh"] !== nothing
    has_export_price =
        haskey(period_dict, "export_price_usd_per_mwh") && period_dict["export_price_usd_per_mwh"] !== nothing

    if has_import_price != has_export_price
        throw(ArgumentError(
            "time_series[$index] must provide both import_price_usd_per_mwh and export_price_usd_per_mwh when using separate prices",
        ))
    end

    if has_import_price
        legacy_price = has_legacy_price ?
                       parse_required_float(period_dict["price_usd_per_mwh"], "time_series[$index].price_usd_per_mwh") :
                       nothing
        import_price = parse_required_float(
            period_dict["import_price_usd_per_mwh"],
            "time_series[$index].import_price_usd_per_mwh",
        )
        export_price = parse_required_float(
            period_dict["export_price_usd_per_mwh"],
            "time_series[$index].export_price_usd_per_mwh",
        )
        return legacy_price, import_price, export_price, true
    end

    legacy_price = parse_required_float(
        required_value(period_dict, "price_usd_per_mwh"),
        "time_series[$index].price_usd_per_mwh",
    )
    return legacy_price, legacy_price, legacy_price, false
end

function validate_system_connectivity(system_case::SystemGraphData, bus_id::String)
    adjacency = Dict{String,Vector{String}}(node.id => String[] for node in system_case.nodes)
    for edge in system_case.edges
        push!(adjacency[edge.from], edge.to)
        push!(adjacency[edge.to], edge.from)
    end

    seen = Set([bus_id])
    queue = [bus_id]
    while !isempty(queue)
        current = popfirst!(queue)
        for neighbor in adjacency[current]
            if !(neighbor in seen)
                push!(seen, neighbor)
                push!(queue, neighbor)
            end
        end
    end

    for node in system_case.nodes
        if !(node.type in SYSTEM_BUS_NODE_TYPES) && !(node.id in seen)
            throw(ArgumentError("asset node $(node.id) is disconnected from bus $(bus_id)"))
        end
    end
end

function validate_system_asset_time_series(system_case::SystemGraphData)
    renewable_ids = [node.id for node in system_case.nodes if node.type == "renewable"]
    load_ids = [node.id for node in system_case.nodes if node.type == "load"]
    hydro_ids = [node.id for node in system_case.nodes if node.type == "hydro"]

    for (period_index, period) in enumerate(system_case.time_series)
        for renewable_id in renewable_ids
            validate_required_nonnegative_series_value(
                period.renewable_available_power_mw,
                "renewable_available_power_mw",
                renewable_id,
                period_index,
            )
        end
        for load_id in load_ids
            validate_required_nonnegative_series_value(
                period.load_demand_mw,
                "load_demand_mw",
                load_id,
                period_index,
            )
        end
        for hydro_id in hydro_ids
            validate_required_nonnegative_series_value(
                period.hydro_inflow_m3s,
                "hydro_inflow_m3s",
                hydro_id,
                period_index,
            )
        end
    end
end

function validate_required_nonnegative_series_value(
    values::Dict{String,Float64},
    field_name::AbstractString,
    asset_id::AbstractString,
    period_index::Int,
)
    if !haskey(values, asset_id)
        throw(ArgumentError("$field_name for asset $asset_id is required at time_series[$period_index]"))
    end

    value = values[asset_id]
    if !isfinite(value) || value < 0
        throw(ArgumentError("$field_name[$asset_id] at time_series[$period_index] must be nonnegative; got $value"))
    end
end

function validate_system_time_series(periods::Vector{SystemPeriodData})
    if isempty(periods)
        throw(ArgumentError("time_series must contain at least one period"))
    end

    for index in 2:length(periods)
        if !(periods[index - 1].timestamp < periods[index].timestamp)
            throw(ArgumentError(
                "timestamps must be strictly increasing; timestamp[$(index - 1)]=$(periods[index - 1].timestamp), timestamp[$index]=$(periods[index].timestamp)",
            ))
        end
    end

    for (index, period) in enumerate(periods)
        if period.price_usd_per_mwh !== nothing && !isfinite(period.price_usd_per_mwh)
            throw(ArgumentError("price_usd_per_mwh[$index] must be finite; got $(period.price_usd_per_mwh)"))
        end
        if !period.uses_separate_prices && period.price_usd_per_mwh === nothing
            throw(ArgumentError("price_usd_per_mwh[$index] is required when separate prices are not provided"))
        end
        if !isfinite(period.import_price_usd_per_mwh)
            throw(ArgumentError(
                "import_price_usd_per_mwh[$index] must be finite; got $(period.import_price_usd_per_mwh)",
            ))
        end
        if !isfinite(period.export_price_usd_per_mwh)
            throw(ArgumentError(
                "export_price_usd_per_mwh[$index] must be finite; got $(period.export_price_usd_per_mwh)",
            ))
        end
        if !isfinite(period.duration_hours) || !(period.duration_hours > 0)
            throw(ArgumentError("duration_hours[$index] must be positive; got $(period.duration_hours)"))
        end
    end
end

function validate_system_battery(id::String, bess::BESSParameters, constraints::ConstraintConfig)
    try
        validate_case_data(CaseData(
            "battery_$id",
            bess,
            TimeSeriesData([DateTime("2026-01-01T00:00:00")], [0.0], [1.0]),
            constraints,
            SolverConfig("HiGHS", Dict{String,Any}()),
            HorizonConfig("full_horizon", nothing, nothing, nothing, nothing),
        ))
    catch error
        throw(ArgumentError("battery $id $(plain_error_message(error))"))
    end
end

function system_grid_import_bounds(data::SystemOptimizationData)::Vector{Float64}
    derived_bound = derived_system_grid_bound(data)
    return [
        grid.import_power_max_mw === nothing ? derived_bound : grid.import_power_max_mw
        for grid in data.grids
    ]
end

function system_grid_export_bounds(data::SystemOptimizationData)::Vector{Float64}
    derived_bound = derived_system_grid_bound(data)
    return [
        grid.export_power_max_mw === nothing ? derived_bound : grid.export_power_max_mw
        for grid in data.grids
    ]
end

function derived_system_grid_bound(data::SystemOptimizationData)::Float64
    battery_power = sum(
        battery.parameters.charge_power_max_mw + battery.parameters.discharge_power_max_mw for battery in data.batteries
    )
    renewable_power = isempty(data.renewable_available_power_mw) ? 0.0 : maximum(data.renewable_available_power_mw)
    load_power = isempty(data.load_demand_mw) ? 0.0 : maximum(data.load_demand_mw)
    hydro_power = sum(
        hydro_power_upper_bound(hydro) for hydro in data.hydros;
        init = 0.0,
    )

    return max(1.0, battery_power + renewable_power + load_power + hydro_power)
end

function realized_system_delta_soc_abs(data::SystemOptimizationData, battery_energy_mwh::Matrix{Float64})::Matrix{Float64}
    delta_soc_abs = zeros(size(battery_energy_mwh))
    for (battery_index, battery_asset) in enumerate(data.batteries)
        previous_energy_mwh = battery_asset.parameters.initial_energy_mwh
        for period in axes(battery_energy_mwh, 2)
            delta_soc_abs[battery_index, period] = abs(battery_energy_mwh[battery_index, period] - previous_energy_mwh)
            previous_energy_mwh = battery_energy_mwh[battery_index, period]
        end
    end

    return delta_soc_abs
end

function period_sum(values::Matrix{Float64}, n_periods::Int)::Vector{Float64}
    if size(values, 1) == 0
        return zeros(n_periods)
    end

    return vec(sum(values; dims = 1))
end

function hydro_volume_matrix(flow_m3s::Matrix{Float64}, duration_hours::Vector{Float64})::Matrix{Float64}
    volumes = zeros(size(flow_m3s))
    for period in eachindex(duration_hours)
        volumes[:, period] .= flow_m3s[:, period] .* duration_hours[period] .* HM3_PER_M3S_HOUR
    end

    return volumes
end

function hydro_generation_flow_breakpoints(hydro::HydroAssetParameters)::Vector{Float64}
    return [point[1] for point in hydro.generation_curve]
end

function hydro_generation_power_breakpoints(hydro::HydroAssetParameters)::Vector{Float64}
    return [point[2] for point in hydro.generation_curve]
end

function hydro_reservoir_storage_breakpoints(hydro::HydroAssetParameters)::Vector{Float64}
    return [point[1] for point in hydro.reservoir_curve]
end

function hydro_reservoir_elevation_breakpoints(hydro::HydroAssetParameters)::Vector{Float64}
    return [point[2] for point in hydro.reservoir_curve]
end

function hydro_turbine_flow_lower_bound(hydro::HydroAssetParameters)::Float64
    if hydro.turbine_flow_min_m3s !== nothing
        return hydro.turbine_flow_min_m3s
    end
    if hydro.generation_mode == "piecewise_linear"
        return first(hydro.generation_curve)[1]
    end
    return 0.0
end

function hydro_turbine_flow_upper_bound(hydro::HydroAssetParameters)::Float64
    if hydro.turbine_flow_max_m3s !== nothing
        return hydro.turbine_flow_max_m3s
    end
    return last(hydro.generation_curve)[1]
end

function hydro_power_upper_bound(hydro::HydroAssetParameters)::Float64
    if hydro.power_max_mw !== nothing
        return hydro.power_max_mw
    end
    if hydro.generation_mode == "piecewise_linear"
        return maximum(hydro_generation_power_breakpoints(hydro))
    end
    return hydro.power_per_flow_mw_per_m3s * hydro_turbine_flow_upper_bound(hydro)
end

function reservoir_elevation_masl(hydro::HydroAssetParameters, storage_hm3::Float64)::Float64
    curve = hydro.reservoir_curve
    if storage_hm3 <= first(curve)[1]
        return first(curve)[2]
    elseif storage_hm3 >= last(curve)[1]
        return last(curve)[2]
    end

    for index in 2:length(curve)
        previous_storage, previous_elevation = curve[index - 1]
        next_storage, next_elevation = curve[index]
        if storage_hm3 <= next_storage
            fraction = (storage_hm3 - previous_storage) / (next_storage - previous_storage)
            return previous_elevation + fraction * (next_elevation - previous_elevation)
        end
    end

    return last(curve)[2]
end

function uses_separate_price_case(data::SystemOptimizationData)::Bool
    return any(data.uses_separate_prices)
end

function system_price_mode(data::SystemOptimizationData)::String
    return uses_separate_price_case(data) ? "separate_import_export" : "legacy_single_price"
end

function legacy_price_vector(data::SystemOptimizationData)::Vector{Float64}
    return [price === nothing ? NaN : price for price in data.price_usd_per_mwh]
end

function system_dispatch_dataframe(data::SystemOptimizationData, result::SystemDispatchResult)::DataFrame
    n_periods = length(data.timestamp)
    grid_import = period_sum(result.p_grid_import_mw, n_periods)
    grid_export = period_sum(result.p_grid_export_mw, n_periods)
    renewable_used = period_sum(result.p_renewable_used_mw, n_periods)
    renewable_curtailed = period_sum(result.p_renewable_curtailed_mw, n_periods)
    load_demand = period_sum(data.load_demand_mw, n_periods)
    battery_charge = period_sum(result.p_battery_charge_mw, n_periods)
    battery_discharge = period_sum(result.p_battery_discharge_mw, n_periods)
    battery_energy = period_sum(result.battery_energy_mwh, n_periods)
    battery_delta_soc_abs = period_sum(result.battery_delta_soc_abs_mwh, n_periods)
    battery_degradation_cost = period_sum(result.battery_degradation_cost_usd, n_periods)
    curtailment_penalty = period_sum(result.curtailment_penalty_usd, n_periods)
    hydro_spill_penalty = period_sum(result.hydro_spill_penalty_usd, n_periods)
    hydro_terminal_value = zeros(n_periods)
    if n_periods > 0
        hydro_terminal_value[end] = sum(result.hydro_terminal_water_value_usd)
    end
    period_profit =
        result.market_value_usd .- battery_degradation_cost .- curtailment_penalty .- hydro_spill_penalty .+ hydro_terminal_value
    frame = DataFrame(
        timestamp = string.(data.timestamp),
        duration_hours = data.duration_hours,
    )

    if uses_separate_price_case(data)
        frame.import_price_usd_per_mwh = data.import_price_usd_per_mwh
        frame.export_price_usd_per_mwh = data.export_price_usd_per_mwh
    else
        frame.price_usd_per_mwh = legacy_price_vector(data)
    end

    frame.grid_import_mw = grid_import
    frame.grid_export_mw = grid_export
    frame.net_grid_export_mw = grid_export .- grid_import
    frame.renewable_used_mw = renewable_used
    frame.renewable_curtailed_mw = renewable_curtailed
    frame.load_demand_mw = load_demand
    if !isempty(data.hydros)
        frame.total_hydro_power_mw = period_sum(result.hydro_power_mw, n_periods)
        frame.total_hydro_inflow_m3s = period_sum(data.hydro_inflow_m3s, n_periods)
        frame.total_hydro_turbine_flow_m3s = period_sum(result.hydro_turbine_flow_m3s, n_periods)
        frame.total_hydro_spill_flow_m3s = period_sum(result.hydro_spill_flow_m3s, n_periods)
        frame.total_hydro_storage_hm3 = period_sum(result.hydro_storage_hm3, n_periods)
        frame.total_hydro_spill_penalty_usd = hydro_spill_penalty
        frame.total_hydro_terminal_water_value_usd = hydro_terminal_value
    end
    frame.battery_charge_mw = battery_charge
    frame.battery_discharge_mw = battery_discharge
    frame.battery_net_discharge_mw = battery_discharge .- battery_charge
    frame.battery_energy_mwh = battery_energy
    frame.battery_delta_soc_abs_mwh = battery_delta_soc_abs

    if uses_separate_price_case(data)
        frame.import_cost_usd = result.import_cost_usd
        frame.export_revenue_usd = result.export_revenue_usd
        frame.net_market_value_usd = result.market_value_usd
    end

    frame.market_value_usd = result.market_value_usd
    frame.battery_degradation_cost_usd = battery_degradation_cost
    frame.curtailment_penalty_usd = curtailment_penalty
    frame.period_profit_usd = period_profit

    return frame
end

function system_asset_dispatch_dataframe(data::SystemOptimizationData, result::SystemDispatchResult)::DataFrame
    timestamp = String[]
    duration_hours = Float64[]
    price_usd_per_mwh = Vector{Union{Float64,Missing}}()
    import_price_usd_per_mwh = Float64[]
    export_price_usd_per_mwh = Float64[]
    asset_id = String[]
    asset_type = String[]
    grid_import_mw = Float64[]
    grid_export_mw = Float64[]
    renewable_used_mw = Float64[]
    renewable_curtailed_mw = Float64[]
    load_demand_mw = Float64[]
    battery_charge_mw = Float64[]
    battery_discharge_mw = Float64[]
    battery_energy_mwh = Float64[]
    battery_delta_soc_abs_mwh = Float64[]

    for period in eachindex(data.timestamp)
        for (grid_index, grid) in enumerate(data.grids)
            push_system_asset_row!(
                timestamp,
                duration_hours,
                price_usd_per_mwh,
                import_price_usd_per_mwh,
                export_price_usd_per_mwh,
                asset_id,
                asset_type,
                grid_import_mw,
                grid_export_mw,
                renewable_used_mw,
                renewable_curtailed_mw,
                load_demand_mw,
                battery_charge_mw,
                battery_discharge_mw,
                battery_energy_mwh,
                battery_delta_soc_abs_mwh,
                data,
                period,
                grid.id,
                "grid",
                result.p_grid_import_mw[grid_index, period],
                result.p_grid_export_mw[grid_index, period],
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            )
        end

        for (renewable_index, renewable) in enumerate(data.renewables)
            push_system_asset_row!(
                timestamp,
                duration_hours,
                price_usd_per_mwh,
                import_price_usd_per_mwh,
                export_price_usd_per_mwh,
                asset_id,
                asset_type,
                grid_import_mw,
                grid_export_mw,
                renewable_used_mw,
                renewable_curtailed_mw,
                load_demand_mw,
                battery_charge_mw,
                battery_discharge_mw,
                battery_energy_mwh,
                battery_delta_soc_abs_mwh,
                data,
                period,
                renewable.id,
                "renewable",
                0.0,
                0.0,
                result.p_renewable_used_mw[renewable_index, period],
                result.p_renewable_curtailed_mw[renewable_index, period],
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            )
        end

        for (load_index, load) in enumerate(data.loads)
            push_system_asset_row!(
                timestamp,
                duration_hours,
                price_usd_per_mwh,
                import_price_usd_per_mwh,
                export_price_usd_per_mwh,
                asset_id,
                asset_type,
                grid_import_mw,
                grid_export_mw,
                renewable_used_mw,
                renewable_curtailed_mw,
                load_demand_mw,
                battery_charge_mw,
                battery_discharge_mw,
                battery_energy_mwh,
                battery_delta_soc_abs_mwh,
                data,
                period,
                load.id,
                "load",
                0.0,
                0.0,
                0.0,
                0.0,
                data.load_demand_mw[load_index, period],
                0.0,
                0.0,
                0.0,
                0.0,
            )
        end

        for (battery_index, battery) in enumerate(data.batteries)
            push_system_asset_row!(
                timestamp,
                duration_hours,
                price_usd_per_mwh,
                import_price_usd_per_mwh,
                export_price_usd_per_mwh,
                asset_id,
                asset_type,
                grid_import_mw,
                grid_export_mw,
                renewable_used_mw,
                renewable_curtailed_mw,
                load_demand_mw,
                battery_charge_mw,
                battery_discharge_mw,
                battery_energy_mwh,
                battery_delta_soc_abs_mwh,
                data,
                period,
                battery.id,
                "battery",
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                result.p_battery_charge_mw[battery_index, period],
                result.p_battery_discharge_mw[battery_index, period],
                result.battery_energy_mwh[battery_index, period],
                result.battery_delta_soc_abs_mwh[battery_index, period],
            )
        end
    end

    frame = DataFrame(
        timestamp = timestamp,
        duration_hours = duration_hours,
    )

    if uses_separate_price_case(data)
        frame.import_price_usd_per_mwh = import_price_usd_per_mwh
        frame.export_price_usd_per_mwh = export_price_usd_per_mwh
    else
        frame.price_usd_per_mwh = price_usd_per_mwh
    end

    frame.asset_id = asset_id
    frame.asset_type = asset_type
    frame.grid_import_mw = grid_import_mw
    frame.grid_export_mw = grid_export_mw
    frame.renewable_used_mw = renewable_used_mw
    frame.renewable_curtailed_mw = renewable_curtailed_mw
    frame.load_demand_mw = load_demand_mw
    frame.battery_charge_mw = battery_charge_mw
    frame.battery_discharge_mw = battery_discharge_mw
    frame.battery_energy_mwh = battery_energy_mwh
    frame.battery_delta_soc_abs_mwh = battery_delta_soc_abs_mwh

    if !isempty(data.hydros)
        frame.hydro_power_mw = zeros(nrow(frame))
        frame.hydro_inflow_m3s = zeros(nrow(frame))
        frame.hydro_turbine_flow_m3s = zeros(nrow(frame))
        frame.hydro_spill_flow_m3s = zeros(nrow(frame))
        frame.hydro_inflow_volume_hm3 = zeros(nrow(frame))
        frame.hydro_turbine_volume_hm3 = zeros(nrow(frame))
        frame.hydro_spill_volume_hm3 = zeros(nrow(frame))
        frame.hydro_storage_hm3 = zeros(nrow(frame))
        frame.hydro_reservoir_elevation_masl = zeros(nrow(frame))
        frame.hydro_spill_penalty_usd = zeros(nrow(frame))
        frame.hydro_terminal_water_value_usd = zeros(nrow(frame))

        hydro_timestamp = String[]
        hydro_duration_hours = Float64[]
        hydro_price_usd_per_mwh = Vector{Union{Float64,Missing}}()
        hydro_import_price_usd_per_mwh = Float64[]
        hydro_export_price_usd_per_mwh = Float64[]
        hydro_asset_id = String[]
        hydro_asset_type = String[]
        hydro_grid_import_mw = Float64[]
        hydro_grid_export_mw = Float64[]
        hydro_renewable_used_mw = Float64[]
        hydro_renewable_curtailed_mw = Float64[]
        hydro_load_demand_mw = Float64[]
        hydro_battery_charge_mw = Float64[]
        hydro_battery_discharge_mw = Float64[]
        hydro_battery_energy_mwh = Float64[]
        hydro_battery_delta_soc_abs_mwh = Float64[]
        hydro_power_mw = Float64[]
        hydro_inflow_m3s = Float64[]
        hydro_turbine_flow_m3s = Float64[]
        hydro_spill_flow_m3s = Float64[]
        hydro_inflow_volume_hm3 = Float64[]
        hydro_turbine_volume_hm3 = Float64[]
        hydro_spill_volume_hm3 = Float64[]
        hydro_storage_hm3 = Float64[]
        hydro_reservoir_elevation_masl = Float64[]
        hydro_spill_penalty_usd = Float64[]
        hydro_terminal_water_value_usd = Float64[]

        for period in eachindex(data.timestamp)
            for (hydro_index, hydro) in enumerate(data.hydros)
                push!(hydro_timestamp, string(data.timestamp[period]))
                push!(hydro_duration_hours, data.duration_hours[period])
                legacy_price = data.price_usd_per_mwh[period]
                push!(hydro_price_usd_per_mwh, legacy_price === nothing ? missing : legacy_price)
                push!(hydro_import_price_usd_per_mwh, data.import_price_usd_per_mwh[period])
                push!(hydro_export_price_usd_per_mwh, data.export_price_usd_per_mwh[period])
                push!(hydro_asset_id, hydro.id)
                push!(hydro_asset_type, "hydro")
                push!(hydro_grid_import_mw, 0.0)
                push!(hydro_grid_export_mw, 0.0)
                push!(hydro_renewable_used_mw, 0.0)
                push!(hydro_renewable_curtailed_mw, 0.0)
                push!(hydro_load_demand_mw, 0.0)
                push!(hydro_battery_charge_mw, 0.0)
                push!(hydro_battery_discharge_mw, 0.0)
                push!(hydro_battery_energy_mwh, 0.0)
                push!(hydro_battery_delta_soc_abs_mwh, 0.0)
                push!(hydro_power_mw, result.hydro_power_mw[hydro_index, period])
                push!(hydro_inflow_m3s, data.hydro_inflow_m3s[hydro_index, period])
                push!(hydro_turbine_flow_m3s, result.hydro_turbine_flow_m3s[hydro_index, period])
                push!(hydro_spill_flow_m3s, result.hydro_spill_flow_m3s[hydro_index, period])
                push!(hydro_inflow_volume_hm3, result.hydro_inflow_volume_hm3[hydro_index, period])
                push!(hydro_turbine_volume_hm3, result.hydro_turbine_volume_hm3[hydro_index, period])
                push!(hydro_spill_volume_hm3, result.hydro_spill_volume_hm3[hydro_index, period])
                push!(hydro_storage_hm3, result.hydro_storage_hm3[hydro_index, period])
                push!(hydro_reservoir_elevation_masl, result.hydro_reservoir_elevation_masl[hydro_index, period])
                push!(hydro_spill_penalty_usd, result.hydro_spill_penalty_usd[hydro_index, period])
                terminal_value = period == length(data.timestamp) ? result.hydro_terminal_water_value_usd[hydro_index] : 0.0
                push!(hydro_terminal_water_value_usd, terminal_value)
            end
        end

        hydro_frame = DataFrame(
            timestamp = hydro_timestamp,
            duration_hours = hydro_duration_hours,
        )
        if uses_separate_price_case(data)
            hydro_frame.import_price_usd_per_mwh = hydro_import_price_usd_per_mwh
            hydro_frame.export_price_usd_per_mwh = hydro_export_price_usd_per_mwh
        else
            hydro_frame.price_usd_per_mwh = hydro_price_usd_per_mwh
        end
        hydro_frame.asset_id = hydro_asset_id
        hydro_frame.asset_type = hydro_asset_type
        hydro_frame.grid_import_mw = hydro_grid_import_mw
        hydro_frame.grid_export_mw = hydro_grid_export_mw
        hydro_frame.renewable_used_mw = hydro_renewable_used_mw
        hydro_frame.renewable_curtailed_mw = hydro_renewable_curtailed_mw
        hydro_frame.load_demand_mw = hydro_load_demand_mw
        hydro_frame.battery_charge_mw = hydro_battery_charge_mw
        hydro_frame.battery_discharge_mw = hydro_battery_discharge_mw
        hydro_frame.battery_energy_mwh = hydro_battery_energy_mwh
        hydro_frame.battery_delta_soc_abs_mwh = hydro_battery_delta_soc_abs_mwh
        hydro_frame.hydro_power_mw = hydro_power_mw
        hydro_frame.hydro_inflow_m3s = hydro_inflow_m3s
        hydro_frame.hydro_turbine_flow_m3s = hydro_turbine_flow_m3s
        hydro_frame.hydro_spill_flow_m3s = hydro_spill_flow_m3s
        hydro_frame.hydro_inflow_volume_hm3 = hydro_inflow_volume_hm3
        hydro_frame.hydro_turbine_volume_hm3 = hydro_turbine_volume_hm3
        hydro_frame.hydro_spill_volume_hm3 = hydro_spill_volume_hm3
        hydro_frame.hydro_storage_hm3 = hydro_storage_hm3
        hydro_frame.hydro_reservoir_elevation_masl = hydro_reservoir_elevation_masl
        hydro_frame.hydro_spill_penalty_usd = hydro_spill_penalty_usd
        hydro_frame.hydro_terminal_water_value_usd = hydro_terminal_water_value_usd
        append!(frame, hydro_frame)
    end

    return frame
end

function push_system_asset_row!(
    timestamp,
    duration_hours,
    price_usd_per_mwh,
    import_price_usd_per_mwh,
    export_price_usd_per_mwh,
    asset_id,
    asset_type,
    grid_import_mw,
    grid_export_mw,
    renewable_used_mw,
    renewable_curtailed_mw,
    load_demand_mw,
    battery_charge_mw,
    battery_discharge_mw,
    battery_energy_mwh,
    battery_delta_soc_abs_mwh,
    data::SystemOptimizationData,
    period::Int,
    current_asset_id::String,
    current_asset_type::String,
    current_grid_import_mw::Float64,
    current_grid_export_mw::Float64,
    current_renewable_used_mw::Float64,
    current_renewable_curtailed_mw::Float64,
    current_load_demand_mw::Float64,
    current_battery_charge_mw::Float64,
    current_battery_discharge_mw::Float64,
    current_battery_energy_mwh::Float64,
    current_battery_delta_soc_abs_mwh::Float64,
)
    push!(timestamp, string(data.timestamp[period]))
    push!(duration_hours, data.duration_hours[period])
    legacy_price = data.price_usd_per_mwh[period]
    push!(price_usd_per_mwh, legacy_price === nothing ? missing : legacy_price)
    push!(import_price_usd_per_mwh, data.import_price_usd_per_mwh[period])
    push!(export_price_usd_per_mwh, data.export_price_usd_per_mwh[period])
    push!(asset_id, current_asset_id)
    push!(asset_type, current_asset_type)
    push!(grid_import_mw, current_grid_import_mw)
    push!(grid_export_mw, current_grid_export_mw)
    push!(renewable_used_mw, current_renewable_used_mw)
    push!(renewable_curtailed_mw, current_renewable_curtailed_mw)
    push!(load_demand_mw, current_load_demand_mw)
    push!(battery_charge_mw, current_battery_charge_mw)
    push!(battery_discharge_mw, current_battery_discharge_mw)
    push!(battery_energy_mwh, current_battery_energy_mwh)
    push!(battery_delta_soc_abs_mwh, current_battery_delta_soc_abs_mwh)
end

function system_summary_dict(
    data::SystemOptimizationData,
    result::SystemDispatchResult,
    run_timestamp::String,
    source_identifiers,
)::Dict{String,Any}
    summary = Dict{String,Any}(
        "case_name" => data.case_name,
        "run_timestamp" => run_timestamp,
        "solver_name" => result.solver_name,
        "solver_status" => result.solver_status,
        "termination_status" => result.termination_status,
        "objective_value_usd" => result.objective_value_usd,
        "price_mode" => system_price_mode(data),
        "source_identifiers" => Dict{String,Any}(string(key) => value for (key, value) in pairs(source_identifiers)),
        "model_version" => package_version_string(),
    )

    if !isempty(data.hydros)
        hydro_kpis_by_asset = Dict{String,Any}()
        for (hydro_index, hydro) in enumerate(data.hydros)
            hydro_kpis_by_asset[hydro.id] = Dict{String,Any}(
                "total_hydro_generation_mwh" => sum(
                    result.hydro_power_mw[hydro_index, period] * data.duration_hours[period]
                    for period in eachindex(data.duration_hours)
                ),
                "total_turbine_volume_hm3" => sum(result.hydro_turbine_volume_hm3[hydro_index, :]),
                "total_spill_volume_hm3" => sum(result.hydro_spill_volume_hm3[hydro_index, :]),
                "initial_storage_hm3" => hydro.initial_storage_hm3,
                "final_storage_hm3" => result.hydro_storage_hm3[hydro_index, end],
                "initial_reservoir_elevation_masl" => reservoir_elevation_masl(hydro, hydro.initial_storage_hm3),
                "final_reservoir_elevation_masl" => result.hydro_reservoir_elevation_masl[hydro_index, end],
                "total_spill_penalty_usd" => sum(result.hydro_spill_penalty_usd[hydro_index, :]),
                "terminal_water_value_usd" => result.hydro_terminal_water_value_usd[hydro_index],
            )
        end
        summary["hydro_kpis_by_asset"] = hydro_kpis_by_asset
        summary["hydro_totals"] = Dict{String,Any}(
            "total_hydro_generation_mwh" => sum(
                result.hydro_power_mw[hydro, period] * data.duration_hours[period]
                for hydro in axes(result.hydro_power_mw, 1), period in eachindex(data.duration_hours)
            ),
            "total_turbine_volume_hm3" => sum(result.hydro_turbine_volume_hm3),
            "total_spill_volume_hm3" => sum(result.hydro_spill_volume_hm3),
            "total_spill_penalty_usd" => sum(result.hydro_spill_penalty_usd),
            "terminal_water_value_usd" => sum(result.hydro_terminal_water_value_usd),
        )
    end

    return summary
end

function system_model_metadata_dict(data::SystemOptimizationData)::Dict{String,Any}
    metadata = Dict{String,Any}(
        "model_name" => "one_bus_hybrid_system_dispatch",
        "schema_version" => data.schema_version,
        "bus_id" => data.bus_id,
        "price_mode" => system_price_mode(data),
        "number_of_periods" => length(data.timestamp),
        "asset_ids" => Dict{String,Any}(
            "batteries" => [battery.id for battery in data.batteries],
            "renewables" => [renewable.id for renewable in data.renewables],
            "grids" => [grid.id for grid in data.grids],
            "loads" => [load.id for load in data.loads],
            "hydros" => [hydro.id for hydro in data.hydros],
        ),
        "active_constraint_flags" => Dict{String,Any}(
            "one_bus_balance" => true,
            "renewable_availability_balance" => true,
            "battery_energy_balance" => true,
            "battery_terminal_condition" => any(
                battery.constraints.terminal_condition != "none" for battery in data.batteries
            ),
            "battery_degradation_linear_delta_soc" => any(
                battery.constraints.degradation_linear_delta_soc for battery in data.batteries
            ),
            "hydro_storage_balance" => !isempty(data.hydros),
            "hydro_linear_generation" => any(hydro.generation_mode == "linear" for hydro in data.hydros),
            "hydro_piecewise_generation" => any(
                hydro.generation_mode == "piecewise_linear" for hydro in data.hydros
            ),
            "hydro_reservoir_elevation_curve" => !isempty(data.hydros),
            "hydro_power_max" => any(hydro.power_max_mw !== nothing for hydro in data.hydros),
            "hydro_minimum_release" => any(hydro.minimum_release_m3s > 0 for hydro in data.hydros),
            "hydro_terminal_condition" => any(hydro.terminal_condition != "none" for hydro in data.hydros),
        ),
        "unit_conventions" => Dict{String,Any}(
            "power" => "MW",
            "energy" => "MWh",
            "price" => "USD/MWh",
            "duration" => "hours",
            "revenue_and_cost" => "USD",
            "reservoir_storage" => "hm3",
            "hydro_flow" => "m3/s",
            "reservoir_elevation" => "masl",
            "water_value" => "USD/hm3",
        ),
    )
    if !isempty(data.hydros)
        metadata["hydro_generation_modes"] = Dict{String,Any}(
            hydro.id => hydro.generation_mode for hydro in data.hydros
        )
        metadata["hydro_unit_conventions"] = Dict{String,Any}(
            "storage" => "hm3",
            "flow" => "m3/s",
            "elevation" => "masl",
            "terminal_water_value" => "USD/hm3",
            "spill_penalty" => "USD/hm3",
        )
        metadata["piecewise_linear_library"] = "PiecewiseLinearOpt"
    end

    return metadata
end

function system_case_dict(system_case::SystemGraphData)::Dict{String,Any}
    return Dict{String,Any}(
        "schema_version" => system_case.schema_version,
        "case_name" => system_case.case_name,
        "nodes" => [
            merge(Dict{String,Any}("id" => node.id, "type" => node.type), node.attributes)
            for node in system_case.nodes
        ],
        "edges" => [
            Dict{String,Any}("from" => edge.from, "to" => edge.to)
            for edge in system_case.edges
        ],
        "time_series" => [system_period_dict(period) for period in system_case.time_series],
        "constraints" => system_case.constraints,
        "solver" => Dict{String,Any}(
            "name" => system_case.solver.name,
            "options" => Dict{String,Any}(string(key) => value for (key, value) in pairs(system_case.solver.options)),
        ),
    )
end

function system_period_dict(period::SystemPeriodData)::Dict{String,Any}
    period_dict = Dict{String,Any}(
        "timestamp" => string(period.timestamp),
        "duration_hours" => period.duration_hours,
        "renewable_available_power_mw" => period.renewable_available_power_mw,
        "load_demand_mw" => period.load_demand_mw,
    )
    if !isempty(period.hydro_inflow_m3s)
        period_dict["hydro_inflow_m3s"] = period.hydro_inflow_m3s
    end

    if period.uses_separate_prices
        period_dict["import_price_usd_per_mwh"] = period.import_price_usd_per_mwh
        period_dict["export_price_usd_per_mwh"] = period.export_price_usd_per_mwh
        if period.price_usd_per_mwh !== nothing
            period_dict["price_usd_per_mwh"] = period.price_usd_per_mwh
        end
    else
        period_dict["price_usd_per_mwh"] = period.price_usd_per_mwh
    end

    return period_dict
end

function system_case_source_identifiers(path::AbstractString)::Dict{String,Any}
    return Dict{String,Any}(
        "system_case" => abspath(path),
    )
end

function required_vector(config, key::AbstractString)
    value = required_value(config, key)
    if !(value isa AbstractVector)
        throw(ArgumentError("$key must be an array; got $(repr(value))"))
    end

    return value
end

function optional_dict(config, key::AbstractString)::Dict{String,Any}
    if !haskey(config, key) || config[key] === nothing
        return Dict{String,Any}()
    end

    return to_string_key_dict(config[key])
end

function optional_bool(config, key::AbstractString, default::Bool)::Bool
    if !haskey(config, key) || config[key] === nothing
        return default
    end

    value = config[key]
    if !(value isa Bool)
        throw(ArgumentError("$key must be boolean; got $(repr(value))"))
    end

    return value
end

function optional_string(config, key::AbstractString, default::String)::String
    if !haskey(config, key) || config[key] === nothing
        return default
    end

    return parse_required_string(config[key], key)
end

function to_string_key_dict(value)::Dict{String,Any}
    if value isa Dict
        return Dict{String,Any}(string(key) => item for (key, item) in pairs(value))
    end

    return Dict{String,Any}(string(key) => item for (key, item) in pairs(value))
end

function plain_error_message(error)::String
    return error isa ArgumentError ? error.msg : sprint(showerror, error)
end
