"""Deterministic windows shared by the trusted validator and isolated SDK."""
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def fail(message, period=0):
    error = ValueError(message)
    error.period = period
    raise error


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def build_windows(grid, policy):
    if not policy:
        fail("Declara la zona y política de ventanas antes de integrar")
    if not grid:
        fail("La ventana no contiene períodos")
    starts, ends = [], []
    for t, point in enumerate(grid):
        hours = point["duration_hours"]
        if type(hours) not in (int, float) or not math.isfinite(hours) or hours <= 0:
            fail("La duración del período debe ser positiva y finita", t)
        start = instant(point["timestamp"])
        if ends and start != ends[-1]:
            fail("La ventana requiere intervalos contiguos sin huecos ni solapamientos", t)
        starts.append(start)
        ends.append(start + timedelta(hours=hours))
    if policy["kind"] == "civil_day":
        zone = ZoneInfo(policy["timezone"])
        grouped = {}
        for t, start in enumerate(starts):
            grouped.setdefault(start.astimezone(zone).date(), []).append(t)
        result = []
        for day, periods in grouped.items():
            lower = datetime.combine(day, datetime.min.time(), zone).astimezone(timezone.utc)
            upper = datetime.combine(day + timedelta(days=1), datetime.min.time(), zone).astimezone(timezone.utc)
            start, end = starts[periods[0]], ends[periods[-1]]
            if end > upper:
                fail("El intervalo cruza un borde de día civil; ajusta la grilla", periods[-1])
            partial = start != lower or end != upper
            if partial and policy["partial"] != "allow":
                fail("Día parcial: acepta explícitamente la ventana parcial sin prorratear el presupuesto", periods[0])
            result.append({"start": stamp(start), "end": stamp(end), "duration_hours": (end - start).total_seconds() / 3600,
                           "periods": periods, "partial": partial})
        return result
    if policy["kind"] != "horizon":
        fail("Tipo de ventana no soportado")
    return [{"start": stamp(starts[0]), "end": stamp(ends[-1]),
             "duration_hours": (ends[-1] - starts[0]).total_seconds() / 3600,
             "periods": list(range(len(grid))), "partial": False}]


@dataclass(frozen=True)
class Window:
    inicio: str
    fin: str
    horas: float
    periodos: tuple
    parcial: bool
    _durations: tuple

    @classmethod
    def from_snapshot(cls, window, grid):
        return cls(window["start"], window["end"], window["duration_hours"], tuple(window["periods"]),
                   window["partial"], tuple(p["duration_hours"] for p in grid))

    def _snapshot(self):
        return {"start": self.inicio, "end": self.fin, "duration_hours": self.horas,
                "periods": list(self.periodos), "partial": self.parcial}

    def integral(self, series):
        from symbolic import Affine, Flow
        if not isinstance(series, Flow) or series.unit not in {"mw", "m3_per_s"}:
            fail("La integral requiere una variable de potencia o caudal", self.periodos[0])
        factor = 3600 if series.unit == "m3_per_s" else 1
        terms = tuple((oid, variable, t, c * self._durations[t] * factor)
                      for t in self.periodos for oid, variable, _, c in series[t].terms)
        return Affine(terms, unit="m3" if series.unit == "m3_per_s" else "mwh")
