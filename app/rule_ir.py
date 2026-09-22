"""Validate sandbox output independently of the SDK before storing or solving it."""
import math

IR_VERSION = "affine_flow.v1"


def validate_ir(ir, object_id, period_count):
    if not isinstance(ir, dict) or set(ir) != {"version", "rows"} or ir["version"] != IR_VERSION:
        raise ValueError("Contrato de restricciones desconocido")
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
        if type(row["line"]) is not int or row["line"] < 1 or row["relation"] not in {"<=", ">=", "=="} or row["unit"] != "m3_per_s":
            raise ValueError("Origen, relación o unidad inválidos")
        finite(row["constant"])
        terms = row["terms"]
        if not isinstance(terms, list):
            raise ValueError("Términos inválidos")
        total += len(terms)
        if total > 500000:
            raise ValueError("Cuota de términos excedida")
        coefficient = 0.0
        for term in terms:
            if set(term) != {"object_id", "variable", "period", "coefficient", "unit"}:
                raise ValueError("Término inválido")
            if type(term["object_id"]) is not int or term["object_id"] != object_id or term["variable"] != "caudal":
                raise ValueError("Objeto o variable fuera del snapshot")
            if type(term["period"]) is not int or term["period"] != period or term["unit"] != "dimensionless":
                raise ValueError("Referencia temporal o unidad no soportada")
            coefficient += finite(term["coefficient"])
        finite(coefficient)
        normalized.append({**row, "terms": [{"object_id": object_id, "variable": "caudal", "period": period,
                                            "coefficient": coefficient, "unit": "dimensionless"}] if coefficient else []})
    return {"version": IR_VERSION, "rows": sorted(normalized, key=lambda row: (row["period"], row["name"]))}


def finite(value):
    if type(value) not in {int, float} or not math.isfinite(value):
        raise ValueError("Coeficientes y constantes deben ser finitos")
    return value
