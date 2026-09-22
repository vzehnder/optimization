"""Validate sandbox output independently of the SDK before storing or solving it."""
import math

IR_VERSION = "affine_flow.v1"
HYDRAULIC_IR_VERSION = "affine_hydraulic.v1"


class RuleBoundsError(ValueError):
    def __init__(self, row):
        super().__init__(f"Mínimo mayor que máximo conocido en {row['name']}, período {row['period'] + 1}")
        self.problem = {"code": "RULE_BOUNDS_CONFLICT", "message": str(self), "period": row["period"],
                        "line": row["line"], "name": row["name"]}
        if len(row["terms"]) == 1:
            self.problem.update(object_id=row["terms"][0]["object_id"], variable=row["terms"][0]["variable"])


def validate_model_bounds(rows, objects, document):
    """Intersect scalar affine bounds; multi-variable feasibility remains the solver's job."""
    network = document["hydraulic_network"]
    physical = {}
    for obj in objects:
        if obj["kind"] == "hydraulic_unit":
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
    bounds = {}
    for row in rows:
        terms, relation, constant = row["terms"], row["relation"], row["constant"]
        if not terms:
            if not (constant <= 0 if relation == "<=" else constant >= 0 if relation == ">=" else constant == 0):
                raise RuleBoundsError(row)
        elif len(terms) == 1:
            term = terms[0]
            identity = (term["object_id"], term["variable"])
            key = (*identity, row["period"])
            lo, hi = bounds.get(key, physical[identity])
            coefficient = term["coefficient"]
            bound = finite(-constant / coefficient)
            if relation == "==":
                lo, hi = max(lo, bound), min(hi, bound)
            elif (relation == "<=" and coefficient > 0) or (relation == ">=" and coefficient < 0):
                hi = min(hi, bound)
            else:
                lo = max(lo, bound)
            if lo > hi:
                raise RuleBoundsError(row)
            bounds[key] = (lo, hi)


def validate_bounds(rows, unit, period_count):
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


def validate_ir(ir, object_id, period_count, objects=None):
    if not isinstance(ir, dict) or set(ir) != {"version", "rows"} or ir["version"] not in {IR_VERSION, HYDRAULIC_IR_VERSION}:
        raise ValueError("Contrato de restricciones desconocido")
    from app.rule_objects import VARIABLES
    allowed = {object_id: {"caudal": "m3_per_s"}} if ir["version"] == IR_VERSION else {
        item["id"]: VARIABLES[item["kind"]] for item in (objects or []) if item["kind"] != "hydraulic_plant"}
    rows = ir["rows"]
    if not isinstance(rows, list) or len(rows) > 100000 or not 1 <= period_count <= 8784:
        raise ValueError("Cuota de restricciones o períodos excedida")
    names, total, normalized = set(), 0, []
    for row in rows:
        if set(row) != {"name", "line", "period", "relation", "unit", "constant", "terms"}:
            raise ValueError("Fila de restricciones inválida")
        period = row["period"]
        if type(period) is not int or not 0 <= period < period_count:
            raise ValueError("Período fuera del snapshot")
        if not isinstance(row["name"], str) or not 1 <= len(row["name"]) <= 200 or (row["name"], period) in names:
            raise ValueError("Nombre de restricción vacío o duplicado")
        names.add((row["name"], period))
        if type(row["line"]) is not int or row["line"] < 1 or row["relation"] not in {"<=", ">=", "=="} or row["unit"] not in ({"m3_per_s"} if ir["version"] == IR_VERSION else {"m3_per_s", "mw", "hm3"}):
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
            if type(term["object_id"]) is not int or allowed.get(term["object_id"], {}).get(term["variable"]) != row["unit"]:
                raise ValueError("Objeto o variable fuera del snapshot")
            if type(term["period"]) is not int or term["period"] != period or term["unit"] != "dimensionless":
                raise ValueError("Referencia temporal o unidad no soportada")
            key = (term["object_id"], term["variable"])
            coefficients[key] = finite(coefficients.get(key, 0.0) + finite(term["coefficient"]))
        normalized.append({**row, "terms": [{"object_id": oid, "variable": variable, "period": period,
                                            "coefficient": coefficient, "unit": "dimensionless"}
                                           for (oid, variable), coefficient in sorted(coefficients.items()) if coefficient]})
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
        if (name, period) in names or row["unit"] not in {"m3_per_s", "dimensionless", "mw", "usd_per_mwh", "hm3"}:
            raise ValueError("Salida duplicada o unidad desconocida")
        if units.setdefault(name, row["unit"]) != row["unit"]:
            raise ValueError("La unidad de una salida no puede cambiar entre períodos")
        names.add((name, period))
        finite(row["value"])
    return sorted(outputs, key=lambda row: (row["period"], row["name"]))
