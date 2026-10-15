"""Compile the diagram's shared plant conduits into ordinary hydraulic reaches."""

import math


def normalize_initial_transit(raw):
    result = {}
    flow = float(raw.get("initial_flow_m3s") or 0)
    if not math.isfinite(flow) or flow < 0:
        raise ValueError("initial_flow_m3s must be finite and nonnegative")
    if flow:
        result["initial_flow_m3s"] = flow
    arrivals = raw.get("initial_arrivals")
    if arrivals is not None:
        if arrivals and not float(raw.get("travel_time_hours") or 0):
            raise ValueError("initial arrivals require a positive travel time")
        if flow:
            raise ValueError("choose initial_flow_m3s or initial_arrivals, not both")
        result["initial_arrivals"] = []
        for point in arrivals:
            duration, value = float(point["duration_hours"]), float(point["value_m3s"])
            if not math.isfinite(duration) or duration <= 0 or not math.isfinite(value) or value < 0:
                raise ValueError("initial arrivals require positive durations and finite nonnegative flows")
            result["initial_arrivals"].append({"timestamp": point["timestamp"], "duration_hours": duration, "value_m3s": value})
    return result


def normalize_link_transit(raw, units):
    valid = {
        f"{side}:{unit[field]}"
        for unit in units
        for side, field in (("in", "intake_node_key"), ("out", "discharge_node_key"))
        if unit.get(field)
    }
    result = {}
    for key, value in (raw or {}).items():
        if key not in valid:
            continue  # A reassigned/deleted connection must not keep an orphan delay.
        hours = float(value.get("travel_time_hours", 0))
        unit = value.get("travel_time_unit", "hours")
        if not math.isfinite(hours) or hours < 0:
            raise ValueError("hydraulic travel time must be finite and nonnegative")
        if unit not in {"seconds", "minutes", "hours", "days"}:
            raise ValueError("unsupported hydraulic travel time unit")
        result[key] = {"travel_time_hours": hours, "travel_time_unit": unit}
        result[key].update(normalize_initial_transit(value))
    return result


def compile_plant_transit(nodes, reaches, units, diagram_nodes):
    used = {item["id"] for item in nodes + reaches + units}

    def identifier(base):
        candidate, suffix = base, 1
        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used.add(candidate)
        return candidate

    for plant in diagram_nodes:
        if plant["component_type"] != "plant":
            continue
        for key, parameters in plant.get("link_transit", {}).items():
            if parameters["travel_time_hours"] == 0:
                continue  # Preserve legacy graph identities when transport is instantaneous.
            direction, external = key.split(":", 1)
            side = "intake" if direction == "in" else "discharge"
            field = f"{side}_node"
            connected = [u for u in units if u["plant_id"] == plant["technical_key"] and u[field] == external]
            if not connected:
                continue
            base = f"__plant_link__{plant['technical_key']}__{key}"
            internal = identifier(base + "__node")
            nodes.append({"id": internal, "type": "junction"})
            reaches.append({
                "id": identifier(base),
                "display_name": f"{plant['display_name']} · {side} · {external}",
                "from_node": external if direction == "in" else internal,
                "to_node": internal if direction == "in" else external,
                "type": "canal" if direction == "in" else "tailrace",
                "routing_method": "fixed_delay",
                "travel_time_hours": parameters["travel_time_hours"],
                **normalize_initial_transit(parameters),
                "diagram_link": {"plant_key": plant["technical_key"], "node_key": external, "side": side},
            })
            for unit in connected:
                unit[field] = internal
