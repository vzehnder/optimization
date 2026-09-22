"""Trusted SDK entrypoint, shipped ONLY in the isolated OCI image."""
import ast
import json
import math
import platform
import sys
import traceback
from dataclasses import dataclass
from types import MappingProxyType
sys.path.insert(0, "/runtime")
from symbolic import Flow, collector

SDK = "reg-003.1"


class LogLimit(ValueError):
    pass


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str

    def __post_init__(self):
        if not math.isfinite(self.value):
            raise ValueError("La cantidad debe ser finita")

    def __mul__(self, other):
        from symbolic import Affine
        if isinstance(other, Affine):
            return other * self
        if isinstance(other, (int, float)):
            return Quantity(self.value * other, self.unit)
        if isinstance(other, Quantity) and other.unit == "dimensionless":
            return Quantity(self.value * other.value, self.unit)
        if self.unit == "dimensionless" and isinstance(other, Quantity):
            return Quantity(self.value * other.value, other.unit)
        raise ValueError("Producto dimensional no admitido en esta capacidad")

    __rmul__ = __mul__

    def __neg__(self):
        return Quantity(-self.value, self.unit)

    def __abs__(self):
        return Quantity(abs(self.value), self.unit)

    def __pow__(self, exponent):
        if self.unit != "dimensionless" or type(exponent) not in (int, float):
            raise ValueError("Las potencias numéricas requieren una base adimensional y exponente conocido")
        return Quantity(self.value ** exponent, "dimensionless")

    def compatible_value(self, other):
        if isinstance(other, Quantity) and other.unit == self.unit:
            return other.value
        if self.unit == "dimensionless" and type(other) in (int, float):
            return other
        raise ValueError("Las cantidades requieren unidades compatibles")

    def __add__(self, other):
        from symbolic import Affine
        if isinstance(other, Affine):
            return other + self
        return Quantity(self.value + self.compatible_value(other), self.unit)

    __radd__ = __add__

    def __sub__(self, other):
        from symbolic import Affine
        if isinstance(other, Affine):
            return Affine.lift(self) - other
        return Quantity(self.value - self.compatible_value(other), self.unit)

    def __rsub__(self, other):
        return -self + other

    def __truediv__(self, other):
        if isinstance(other, Quantity):
            if other.unit == self.unit:
                return Quantity(self.value / other.value, "dimensionless")
            if other.unit == "dimensionless":
                return Quantity(self.value / other.value, self.unit)
        if type(other) in (int, float):
            return Quantity(self.value / other, self.unit)
        raise ValueError("Divisor dimensional incompatible")

    def __lt__(self, other):
        return self.value < self.compatible_value(other)

    def __gt__(self, other):
        return self.value > self.compatible_value(other)

    def __le__(self, other):
        from symbolic import Affine
        return other >= self if isinstance(other, Affine) else self.value <= self.compatible_value(other)

    def __ge__(self, other):
        from symbolic import Affine
        return other <= self if isinstance(other, Affine) else self.value >= self.compatible_value(other)

    def __bool__(self):
        return bool(self.value)

    def __float__(self):
        if self.unit != "dimensionless":
            raise ValueError("No se pueden eliminar unidades de una cantidad dimensional")
        return float(self.value)

    def __int__(self):
        return int(float(self))


class FrozenContext:
    def __init__(self, values):
        object.__setattr__(self, "_values", MappingProxyType(values))

    def __getattr__(self, name):
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(f"Capacidad desconocida: {name}") from None

    def __setattr__(self, name, value):
        raise ValueError("El contexto es inmutable")


@dataclass(frozen=True)
class NumericSeries:
    alias: str
    values: tuple

    def __getitem__(self, period):
        if type(period) is not int or not 0 <= period < len(self.values):
            error = ValueError(f"Entrada {self.alias}: período fuera de la grilla")
            error.alias, error.period = self.alias, period
            raise error
        return self.values[period]


def main(payload):
    logs = []
    log_bytes = 0

    def limited_print(*args, sep=" ", end="\n"):
        nonlocal log_bytes
        message = sep.join(str(arg) for arg in args) + end
        log_bytes += len(message.encode())
        if log_bytes > 65536:
            raise LogLimit("Los logs exceden 64 KiB")
        logs.append(message)
    parameters = {
        p["name"]: p["value"] if p["type"] == "boolean" else Quantity(p["value"], p["unit"])
        for p in payload["parameters"]
    }
    rows, outputs = [], []
    obj = dict(payload["object"])
    values = {"parametros": FrozenContext(parameters)}
    if "grid" in payload:
        count = len(payload["grid"])
        if not 1 <= count <= 8784:
            raise ValueError("Cuota de períodos excedida")
        obj["caudal"] = Flow(obj["id"], count)
        values.update(periodos=tuple(range(count)), restriccion=collector(rows, count))
        entries = {}
        for entry in payload.get("inputs", []):
            if len(entry["values"]) != count or entry["alias"] in entries:
                raise ValueError("Entrada duplicada o sin cobertura completa")
            entries[entry["alias"]] = NumericSeries(entry["alias"], tuple(Quantity(v, entry["unit_key"]) for v in entry["values"]))
        def output(name, period, value):
            if not isinstance(name, str) or not 1 <= len(name) <= 200 or type(period) is not int or not 0 <= period < count:
                raise ValueError("Nombre o período de salida inválido")
            if len(outputs) >= 100000:
                raise ValueError("Cuota de salidas excedida")
            if type(value) in (float, int):
                value = Quantity(value, "dimensionless")
            if not isinstance(value, Quantity):
                raise ValueError("La salida debe ser numérica, no una decisión simbólica")
            outputs.append({"name": name, "period": period, "value": value.value, "unit": value.unit})
        values.update(entradas=FrozenContext(entries), salida=output)
    values["objeto"] = FrozenContext(obj)
    ctx = FrozenContext(values)
    tree = ast.parse(payload["code"], filename="regla.py")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.ClassDef)):
            error = ValueError("Sintaxis o importación no admitida")
            error.rule_line = node.lineno
            raise error
        if (isinstance(node, ast.Attribute) and node.attr.startswith("_")) or (
            isinstance(node, ast.Name) and node.id.startswith("_")
        ):
            error = ValueError("Acceso privado no admitido")
            error.rule_line = node.lineno
            raise error
    namespace = {"__builtins__": {"range": range, "len": len, "sum": sum, "min": min, "max": max,
                                "abs": abs, "enumerate": enumerate, "zip": zip, "float": float,
                                "int": int, "bool": bool, "print": limited_print}}
    exec(compile(tree, "regla.py", "exec"), namespace)
    result = namespace["construir"](ctx)
    if "grid" in payload:
        if result is not None:
            raise ValueError("Usa ctx.restriccion para emitir filas; no retornes un valor")
        return {"status": "succeeded", "ir": {"version": "affine_flow.v1", "rows": rows}, "outputs": outputs, "logs": "".join(logs)}
    if not isinstance(result, Quantity) or result.unit != "m3_per_s" or not math.isfinite(result.value):
        raise ValueError("El resultado debe ser un caudal finito con unidad m3_per_s")
    return {"status": "succeeded", "output": {"value": result.value, "unit": result.unit}, "logs": "".join(logs)}


if __name__ == "__main__":
    try:
        raw = sys.stdin.buffer.read(64 * 1024 * 1024 + 1)
        if len(raw) > 64 * 1024 * 1024:
            raise ValueError("Payload excesivo")
        result = main(json.loads(raw))
    except BaseException as error:
        line = getattr(error, "rule_line", None) or getattr(error, "lineno", None)
        for frame in traceback.extract_tb(error.__traceback__):
            if frame.filename == "regla.py":
                line = frame.lineno
        result = {"status": "failed", "error": {"code": "RULE_LOG_LIMIT" if isinstance(error, LogLimit) else "RULE_CODE_ERROR", "message": str(error)[:1000], "line": line}}
    result["runtime"] = {"sdk": SDK, "python": platform.python_version()}
    sys.stdout.write(json.dumps(result, allow_nan=False))
