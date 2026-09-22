"""Affine flow expressions; only this frozen capability enters user Python."""
import inspect
from dataclasses import dataclass


@dataclass(frozen=True, eq=False)
class Affine:
    terms: tuple
    constant: float = 0.0
    unit: str = "m3_per_s"

    @staticmethod
    def lift(value):
        if isinstance(value, Affine):
            return value
        if getattr(value, "unit", None) in {"m3_per_s", "mw", "hm3"}:
            return Affine((), value.value, value.unit)
        raise ValueError("La expresión requiere una cantidad con unidad compatible")

    def __add__(self, other):
        if type(other) in (int, float) and other == 0:
            return self
        other = self.lift(other)
        if self.unit != other.unit:
            raise ValueError("Las expresiones requieren unidades compatibles")
        return Affine(self.terms + other.terms, self.constant + other.constant, self.unit)

    __radd__ = __add__

    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + -self.lift(other)

    def __rsub__(self, other):
        return self.lift(other) - self

    def __mul__(self, value):
        if getattr(value, "unit", None) == "dimensionless":
            value = value.value
        if type(value) not in (int, float):
            raise ValueError("Solo se permite multiplicar decisiones por datos adimensionales")
        return Affine(tuple((oid, variable, t, c * value) for oid, variable, t, c in self.terms), self.constant * value, self.unit)

    __rmul__ = __mul__

    def __truediv__(self, value):
        if getattr(value, "unit", None) == "dimensionless":
            value = value.value
        if type(value) not in (int, float) or value == 0:
            raise ValueError("Solo se permite dividir por datos adimensionales distintos de cero")
        return self * (1 / value)

    def compare(self, other, relation):
        difference = self - other
        return Relation(difference.terms, difference.constant, relation, difference.unit)

    def __le__(self, other):
        return self.compare(other, "<=")

    def __ge__(self, other):
        return self.compare(other, ">=")

    def __eq__(self, other):
        return self.compare(other, "==")

    def __bool__(self):
        raise ValueError("Una expresión simbólica no es un booleano")


@dataclass(frozen=True)
class Relation:
    terms: tuple
    constant: float
    relation: str
    unit: str

    def __bool__(self):
        raise ValueError("Una restricción simbólica no es un booleano")


@dataclass(frozen=True)
class Flow:
    object_id: int
    count: int
    variable: str = "caudal"
    unit: str = "m3_per_s"
    member_ids: tuple = ()

    def __getitem__(self, period):
        if type(period) is not int or not 0 <= period < self.count:
            raise ValueError("Período fuera de la grilla")
        return Affine(tuple((identity, self.variable, period, 1.0) for identity in (self.member_ids or (self.object_id,))), unit=self.unit)


def collector(rows, count):
    def emit(name, period, relation):
        if not isinstance(name, str) or not name or len(name) > 200:
            raise ValueError("Nombre de restricción inválido")
        if type(period) is not int or not 0 <= period < count or not isinstance(relation, Relation):
            raise ValueError("Restricción o período inválido")
        if len(rows) >= 100000:
            raise ValueError("Cuota de restricciones excedida")
        rows.append({"name": name, "period": period, "line": inspect.currentframe().f_back.f_lineno,
                     "relation": relation.relation, "unit": relation.unit, "constant": relation.constant,
                     "terms": [{"object_id": oid, "period": t, "variable": variable, "coefficient": c,
                                "unit": "dimensionless"} for oid, variable, t, c in relation.terms]})
    return emit
