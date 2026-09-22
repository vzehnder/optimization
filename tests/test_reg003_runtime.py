"""Hourly calculations at the real isolated Python boundary."""
import os
import threading
import time
import unittest
import uuid
from datetime import datetime, timedelta

from app.rule_runtime import OCIExecutor
from tests.test_reg002_runtime import GRID

CODE = '''def construir(ctx):
    for t in ctx.periodos:
        minimo = ctx.entradas.afluente[t] * ctx.parametros.fraccion
        maximo = ctx.parametros.capacidad * ctx.entradas.disponibilidad[t]
        ctx.restriccion("minimo", t, ctx.objeto.caudal[t] >= minimo)
        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= maximo)
        ctx.salida("minimo", t, minimo)
        ctx.salida("maximo", t, maximo)
'''
PARAMETERS = [{"name": "capacidad", "type": "number", "unit": "m3_per_s", "value": 20},
              {"name": "fraccion", "type": "number", "unit": "dimensionless", "value": 0.25}]
INPUTS = [{"alias": "afluente", "unit_key": "m3_per_s", "values": [8, 12, 16, 20]},
          {"alias": "disponibilidad", "unit_key": "dimensionless", "values": [1, 0.5, 0.75, 1]}]


@unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
class HourlyRuntimeTests(unittest.TestCase):
    def execute(self, code=CODE, **kwargs):
        return OCIExecutor.from_env().execute({"code": code, "object": {"id": 7, "key": "unit"},
                    "parameters": PARAMETERS, "grid": GRID, "inputs": INPUTS, **kwargs}, uuid.uuid4().hex, threading.Event())

    def test_hourly_inputs_produce_limits_and_numeric_curves_with_units(self):
        result = self.execute()
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual([r["constant"] for r in result["ir"]["rows"] if r["name"] == "minimo"], [-2, -3, -4, -5])
        self.assertEqual([r["constant"] for r in result["ir"]["rows"] if r["name"] == "maximo"], [-20, -10, -15, -20])
        self.assertEqual([(r["name"], r["period"], r["value"], r["unit"]) for r in result["outputs"]],
                         [("maximo", 0, 20, "m3_per_s"), ("minimo", 0, 2, "m3_per_s"),
                          ("maximo", 1, 10, "m3_per_s"), ("minimo", 1, 3, "m3_per_s"),
                          ("maximo", 2, 15, "m3_per_s"), ("minimo", 2, 4, "m3_per_s"),
                          ("maximo", 3, 20, "m3_per_s"), ("minimo", 3, 5, "m3_per_s")])

    def test_known_input_data_can_use_nonlinear_calculations_without_nonlinear_decisions(self):
        result = self.execute('''def construir(ctx):
    for t in ctx.periodos:
        factor = 1 - ctx.entradas.disponibilidad[t] ** 2
        limite = abs(-ctx.entradas.afluente[t]) * factor
        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= limite)
''')
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual([r["constant"] for r in result["ir"]["rows"]], [0, -9, -7, 0])

    def test_full_annual_horizon_is_not_sampled_and_over_quota_is_bounded(self):
        grid = [{"timestamp": (datetime(2024, 1, 1) + timedelta(hours=t)).isoformat(), "duration_hours": 1} for t in range(8784)]
        inputs = [{**entry, "values": entry["values"] * 2196} for entry in INPUTS]
        started = time.monotonic()
        result = self.execute(grid=grid, inputs=inputs)
        elapsed = time.monotonic() - started
        self.assertEqual(result["status"], "succeeded", result.get("error"))
        self.assertEqual((len(result["ir"]["rows"]), len(result["outputs"])), (17568, 17568))
        self.assertEqual(result["outputs"][-1], {"name": "minimo", "period": 8783, "value": 5, "unit": "m3_per_s"})
        started = time.monotonic()
        exceeded = self.execute(grid=[*grid, grid[-1]], inputs=inputs)
        rejected_elapsed = time.monotonic() - started
        self.assertEqual(exceeded["status"], "failed", exceeded)
        self.assertIn("Cuota", exceeded["error"]["message"])
        self.assertLess(elapsed, 30)
        self.assertLess(rejected_elapsed, 30)
        print(f"REG003 annual: 8784 periods, 17568 rows/outputs, {elapsed:.3f}s; 8785 rejected in {rejected_elapsed:.3f}s")

    def test_annual_compilation_can_be_cancelled_without_publishing_partial_results(self):
        cancel = threading.Event()
        timer = threading.Timer(1, cancel.set)
        timer.start()
        try:
            result = OCIExecutor.from_env().execute({"code": "def construir(ctx):\n    while True: pass", "parameters": PARAMETERS,
                       "object": {"id": 7, "key": "unit"}, "grid": GRID * 2196, "inputs": []}, uuid.uuid4().hex, cancel)
        finally:
            timer.cancel()
        self.assertEqual(result, {"status": "cancelled"})
