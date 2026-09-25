"""Validate sandbox output independently of the SDK before storing or solving it."""
import math

IR_VERSION = "affine_flow.v1"
HYDRAULIC_IR_VERSION = "affine_hydraulic.v1"
TEMPORAL_IR_VERSION = "affine_temporal.v1"
BUDGET_IR_VERSION = "affine_budget.v1"


def hydro_bounds(hydro):
    curve = hydro.get("generation_curve", [])
    piecewise = hydro["generation_mode"] == "piecewise_linear"
    lower = hydro.get("turbine_flow_min_m3s")
    upper = hydro.get("turbine_flow_max_m3s")
    lower = lower if lower is not None else curve[0]["flow_m3s"] if piecewise else 0
    upper = upper if upper is not None else curve[-1]["flow_m3s"]
    power = hydro.get("power_max_mw")
    power = power if power is not None else max(p["power_mw"] for p in curve) if piecewise else hydro["power_per_flow_mw_per_m3s"] * upper
    return {"caudal": (lower, upper), "potencia": (0, power), "vertimiento": (0, float("inf")),
            "almacenamiento": (hydro["storage_min_hm3"], hydro["storage_max_hm3"])}


class RuleBoundsError(ValueError):
    def __init__(self, row, conflicting_rows=None):
        super().__init__(f"Mínimo mayor que máximo conocido en {row['name']}, período {row['period'] + 1}")
        self.problem = {"code": "RULE_BOUNDS_CONFLICT", "message": str(self), "period": row["period"],
                        "line": row["line"], "name": row["name"]}
        if len(row["terms"]) == 1:
            self.problem.update(object_id=row["terms"][0]["object_id"], variable=row["terms"][0]["variable"])
        self.conflicting_rows = conflicting_rows or [row]
        self.problem["conflicts"] = [{key: item[key] for key in ("name", "period", "line", "application_id", "revision_id") if key in item}
                                     for item in self.conflicting_rows]


def validate_model_bounds(rows, objects, document):
    """Intersect scalar affine bounds; multi-variable feasibility remains the solver's job."""
    network = document.get("hydraulic_network")
    physical = {}
    for obj in objects:
        if obj["kind"] == "hydro":
            hydro = next(n for n in document["nodes"] if n["id"] == obj["component_key"] and n["type"] == "hydro")
            physical.update({(obj["id"], variable): bounds for variable, bounds in hydro_bounds(hydro).items()})
        elif obj["kind"] == "battery":
            battery = next(n for n in document["nodes"] if n["id"] == obj["component_key"] and n["type"] == "battery")
            physical[obj["id"], "carga"] = (0, battery["charge_power_max_mw"])
            physical[obj["id"], "descarga"] = (0, battery["discharge_power_max_mw"])
            physical[obj["id"], "energia"] = (battery["energy_min_mwh"], battery["energy_max_mwh"])
        elif obj["kind"] == "grid":
            node = next(n for n in document["nodes"] if n["id"] == obj["component_key"] and n["type"] == "grid")
            for variable, field in (("importacion", "import_power_max_mw"), ("exportacion", "export_power_max_mw")):
                upper = node.get(field)
                physical[obj["id"], variable] = (0, float("inf") if upper is None else upper)
        elif obj["kind"] == "renewable":
            for variable in ("generacion", "recorte"):
                physical[obj["id"], variable] = (0, float("inf"))
                for t, period in enumerate(document["time_series"]):
                    physical[obj["id"], variable, t] = (0, period["renewable_available_power_mw"][obj["component_key"]])
        elif obj["kind"] == "hydraulic_unit":
            unit = next(u for u in network["units"] if u["id"] == obj["unit_key"])
            curve = unit["curves"]["flow_power"]
            flow_min = max(curve[0]["flow_m3s"], unit.get("min_flow_m3s") or 0)
            flow_max = min(curve[-1]["flow_m3s"], unit["max_flow_m3s"] if unit.get("max_flow_m3s") is not None else float("inf"))
            physical[obj["id"], "caudal"] = (flow_min, flow_max)
            physical[obj["id"], "potencia"] = (0, min(curve[-1]["power_mw"], unit["max_power_mw"] if unit.get("max_power_mw") is not None else float("inf")))
        elif obj["kind"] == "hydraulic_node":
            reservoir = next(n["reservoir"] for n in network["nodes"] if n["id"] == obj["node_key"])
            physical[obj["id"], "almacenamiento"] = (reservoir["storage_min_hm3"], reservoir["storage_max_hm3"])
            physical[obj["id"], "vertimiento"] = (0, float("inf"))
    bounds, origins = {}, {}
    for row in rows:
        terms, relation, constant = row["terms"], row["relation"], row["constant"]
        if not terms:
            if not (constant <= 0 if relation == "<=" else constant >= 0 if relation == ">=" else constant == 0):
                raise RuleBoundsError(row)
        elif len(terms) == 1:
            term = terms[0]
            identity = (term["object_id"], term["variable"])
            key = (*identity, term["period"])
            lo, hi = bounds.get(key, physical.get(key, physical[identity]))
            lo_row, hi_row = origins.get(key, (None, None))
            coefficient = term["coefficient"]
            bound = finite(-constant / coefficient)
            if relation == "==":
                if bound > lo:
                    lo_row = row
                if bound < hi:
                    hi_row = row
                lo, hi = max(lo, bound), min(hi, bound)
            elif (relation == "<=" and coefficient > 0) or (relation == ">=" and coefficient < 0):
                if bound < hi:
                    hi_row = row
                hi = min(hi, bound)
            else:
                if bound > lo:
                    lo_row = row
                lo = max(lo, bound)
            if lo > hi:
                raise RuleBoundsError(row, [item for item in (lo_row, hi_row) if item is not None])
            bounds[key] = (lo, hi)
            origins[key] = (lo_row, hi_row)


def validate_bounds(rows, unit, period_count):
    if unit.get("type") == "hydro":
        lower, upper = hydro_bounds(unit)["caudal"]
    else:
        curve = unit["curves"]["flow_power"]
        lower, upper = curve[0]["flow_m3s"], curve[-1]["flow_m3s"]
        lower = max(lower, unit.get("min_flow_m3s") if unit.get("min_flow_m3s") is not None else lower)
        upper = min(upper, unit.get("max_flow_m3s") if unit.get("max_flow_m3s") is not None else upper)
    bounds = [[lower, upper] for _ in range(period_count)]
    for row in rows:
        lo, hi = bounds[row["period"]]
        coefficient = sum(t["coefficient"] for t in row["terms"])
        relation, constant = row["relation"], row["constant"]
        if not coefficient:
            valid = constant <= 0 if relation == "<=" else constant >= 0 if relation == ">=" else constant == 0
            if not valid:
                raise RuleBoundsError(row)
            continue
        bound = finite(-constant / coefficient)
        if relation == "==":
            lo, hi = max(lo, bound), min(hi, bound)
        elif (relation == "<=" and coefficient > 0) or (relation == ">=" and coefficient < 0):
            hi = min(hi, bound)
        else:
            lo = max(lo, bound)
        if lo > hi:
            raise RuleBoundsError(row)
        bounds[row["period"]] = [lo, hi]
    return [{"period": t, "minimum": lo, "maximum": hi, "unit": "m3_per_s"} for t, (lo, hi) in enumerate(bounds)]


def validate_ir(ir, object_id, period_count, objects=None, *, grid=None, windows=None, temporal=None):
    if not isinstance(ir, dict) or set(ir) != {"version", "rows"} or ir["version"] not in {IR_VERSION, HYDRAULIC_IR_VERSION, TEMPORAL_IR_VERSION, BUDGET_IR_VERSION}:
        raise ValueError("Contrato de restricciones desconocido")
    budget = ir["version"] == BUDGET_IR_VERSION
    expected_windows = []
    if budget:
        from runtime.component_rules.windows import build_windows
        expected_windows = build_windows(grid, windows)
    from app.rule_objects import VARIABLES
    allowed = {object_id: {"caudal": "m3_per_s"}} if ir["version"] == IR_VERSION else {
        item["id"]: VARIABLES[item["kind"]] for item in (objects or []) if item["kind"] != "hydraulic_plant"}
    rows = ir["rows"]
    if not isinstance(rows, list) or len(rows) > 100000 or not 1 <= period_count <= 8784:
        raise ValueError("Cuota de restricciones o períodos excedida")
    names, total, normalized = set(), 0, []
    for row in rows:
        window = row.get("window")
        fields = {"name", "line", "period", "relation", "unit", "constant", "terms"}
        if window is not None:
            if not budget or window not in expected_windows or row["period"] != window["periods"][-1]:
                raise ValueError("Ventana fuera del snapshot o incompatible con la política")
            fields.add("window")
        if set(row) != fields:
            raise ValueError("Fila de restricciones inválida")
        period = row["period"]
        if type(period) is not int or not 0 <= period < period_count:
            raise ValueError("Período fuera del snapshot")
        if not isinstance(row["name"], str) or not 1 <= len(row["name"]) <= 200 or (row["name"], period) in names:
            raise ValueError("Nombre de restricción vacío o duplicado")
        names.add((row["name"], period))
        if type(row["line"]) is not int or row["line"] < 1 or row["relation"] not in {"<=", ">=", "=="} or row["unit"] not in ({"mwh", "m3", "hm3"} if window else {"m3_per_s"} if ir["version"] == IR_VERSION else {"m3_per_s", "mw", "hm3", "mwh"}):
            raise ValueError("Origen, relación o unidad inválidos")
        finite(row["constant"])
        terms = row["terms"]
        if not isinstance(terms, list):
            raise ValueError("Términos inválidos")
        total += len(terms)
        if total > 500000:
            raise ValueError("Cuota de términos excedida")
        coefficients = {}
        for term in terms:
            if set(term) != {"object_id", "variable", "period", "coefficient", "unit"}:
                raise ValueError("Término inválido")
            variable_unit = allowed.get(term["object_id"], {}).get(term["variable"])
            coefficient_unit = ({("mw", "mwh"): "h", ("m3_per_s", "m3"): "s",
                                 ("m3_per_s", "hm3"): "hm3_per_m3_per_s"}.get((variable_unit, row["unit"]))
                                if window else "dimensionless")
            if coefficient_unit is None:
                raise ValueError("La integral requiere potencia o caudal con unidades compatibles")
            if type(term["object_id"]) is not int or (coefficient_unit == "dimensionless" and variable_unit != row["unit"]):
                raise ValueError("Objeto o variable fuera del snapshot")
            previous_allowed = ir["version"] == TEMPORAL_IR_VERSION or (budget and temporal)
            if type(term["period"]) is not int or not 0 <= term["period"] <= period or (not window and not previous_allowed and term["period"] != period) or term["unit"] != coefficient_unit:
                raise ValueError("Referencia temporal o unidad no soportada")
            if window and term["period"] not in window["periods"]:
                raise ValueError("Término fuera de la ventana")
            key = (term["object_id"], term["variable"], term["period"], coefficient_unit)
            coefficients[key] = finite(coefficients.get(key, 0.0) + finite(term["coefficient"]))
        normalized.append({**row, "terms": [{"object_id": oid, "variable": variable, "period": term_period,
                                            "coefficient": coefficient, "unit": coefficient_unit}
                                           for (oid, variable, term_period, coefficient_unit), coefficient in sorted(coefficients.items()) if coefficient]})
    return {"version": ir["version"], "rows": sorted(normalized, key=lambda row: (row["period"], row["name"]))}


def finite(value):
    if type(value) not in {int, float} or not math.isfinite(value):
        raise ValueError("Coeficientes y constantes deben ser finitos")
    return value


def validate_outputs(outputs, period_count):
    if not isinstance(outputs, list) or len(outputs) > 100000:
        raise ValueError("Cuota de salidas numéricas excedida")
    names, units = set(), {}
    for row in outputs:
        if not isinstance(row, dict) or set(row) != {"name", "period", "value", "unit"}:
            raise ValueError("Salida numérica inválida")
        name, period = row["name"], row["period"]
        if not isinstance(name, str) or not 1 <= len(name) <= 200 or type(period) is not int or not 0 <= period < period_count:
            raise ValueError("Nombre o período de salida inválido")
        if (name, period) in names or row["unit"] not in {"m3_per_s", "dimensionless", "mw", "usd_per_mwh", "hm3", "mwh"}:
            raise ValueError("Salida duplicada o unidad desconocida")
        if units.setdefault(name, row["unit"]) != row["unit"]:
            raise ValueError("La unidad de una salida no puede cambiar entre períodos")
        names.add((name, period))
        finite(row["value"])
    return sorted(outputs, key=lambda row: (row["period"], row["name"]))
