"""Trusted SDK entrypoint, shipped ONLY in the isolated OCI image."""
import ast
import json
import math
import platform
import sys
import traceback
from dataclasses import dataclass
from types import MappingProxyType

SDK = "reg-001.1"


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
        if isinstance(other, (int, float)):
            return Quantity(self.value * other, self.unit)
        if isinstance(other, Quantity) and other.unit == "dimensionless":
            return Quantity(self.value * other.value, self.unit)
        if self.unit == "dimensionless" and isinstance(other, Quantity):
            return Quantity(self.value * other.value, other.unit)
        raise ValueError("Producto dimensional no admitido en esta capacidad")

    __rmul__ = __mul__


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
    ctx = FrozenContext({"parametros": FrozenContext(parameters), "objeto": FrozenContext(payload["object"])})
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
