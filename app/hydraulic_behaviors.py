"""Physical laws attached to reaches, independent of optional operating rules."""
import math


ELEVATION_FLOW_CURVE_SPEC = {
    "curve_key": "elevation_flow",
    "base_entity_type": "hydraulic_reach",
    "axis_x_name": "elevation_masl",
    "axis_x_unit": "masl",
    "axis_y_name": "flow_m3s",
    "axis_y_unit": "m3s",
}


def normalize_flow_behavior(behavior, normalize_curve):
    if behavior is None:
        return None
    if behavior.get("kind") != "seepage":
        raise ValueError("unsupported hydraulic flow behavior")
    timing = behavior.get("level_timing", "start")
    if timing not in ("start", "end"):
        raise ValueError("seepage level_timing must be start or end")
    curve = normalize_curve(behavior.get("curve") or {})
    if any(not math.isfinite(p[k]) for p in curve["points"] for k in ("x_value", "y_value")):
        raise ValueError("seepage curve points must be finite")
    return {"kind": "seepage", "level_timing": timing, "curve": curve}


def _interpolate(points, x):
    for a, b in zip(points, points[1:]):
        if a["x_value"] <= x <= b["x_value"]:
            return a["y_value"] + (x - a["x_value"]) * (b["y_value"] - a["y_value"]) / (b["x_value"] - a["x_value"])
    return None


def validate_flow_behaviors(diagram):
    nodes = {n["technical_key"]: n for n in diagram["nodes"]}
    errors = []
    for reach in diagram["reaches"]:
        behavior = reach.get("flow_behavior")
        if behavior is None:
            continue

        def error(code, message):
            errors.append({"severity": "error", "code": code, "message": message,
                           "entity_type": "case_hydraulic_reach", "entity_id": reach["entity_id"],
                           "technical_key": reach["technical_key"]})

        source = nodes.get(reach["from_node_key"])
        if source is None or source["component_type"] != "reservoir":
            error("seepage_requires_reservoir", "La filtración según cota requiere un embalse como origen del tramo.")
            continue
        points = (behavior.get("curve") or {}).get("points", [])
        if (len(points) < 2 or any(not math.isfinite(p[k]) for p in points for k in ("x_value", "y_value"))
                or any(p["y_value"] < 0 for p in points)
                or any(a["x_value"] >= b["x_value"] for a, b in zip(points, points[1:]))):
            error("invalid_elevation_flow_curve", "La curva de filtración requiere al menos dos puntos finitos, cotas estrictamente crecientes y caudales no negativos.")
            continue
        reservoir = source.get("reservoir")
        levels = (source.get("storage_elevation_curve") or {}).get("points", [])
        # Reservoir validation reports incomplete/invalid volume–elevation curves.
        if not reservoir or len(levels) < 2 or any(a["x_value"] >= b["x_value"] for a, b in zip(levels, levels[1:])):
            continue
        bounds = [_interpolate(levels, reservoir[key]) for key in ("storage_min_hm3", "storage_max_hm3")]
        if all(v is not None for v in bounds) and (points[0]["x_value"] > bounds[0] or points[-1]["x_value"] < bounds[1]):
            error("elevation_flow_domain", "La curva de filtración debe cubrir todo el rango de cotas operativo del embalse de origen; no se extrapola.")
    return errors


def flow_behavior_snapshot(behavior):
    if behavior is None:
        return None
    return {"kind": behavior["kind"], "level_timing": behavior["level_timing"],
            "curve": [{"elevation_masl": p["x_value"], "flow_m3s": p["y_value"]}
                      for p in (behavior.get("curve") or {}).get("points", [])]}
