"""Temporal arithmetic through the real OCI boundary."""
import os
import threading
import unittest
import uuid

from app.rule_runtime import OCIExecutor
from tests.test_reg004_runtime import OBJECTS

GRID = [{"timestamp": "2026-01-01T00:00:00Z", "duration_hours": 0.5},
        {"timestamp": "2026-01-01T00:30:00Z", "duration_hours": 2},
        {"timestamp": "2026-01-01T02:30:00Z", "duration_hours": 1}]
PARAMETERS = [{"name": "subida", "type": "number", "unit": "mw_per_h", "value": 4},
              {"name": "bajada", "type": "number", "unit": "mw_per_h", "value": 2}]
CODE = '''def construir(ctx):
    for paso in ctx.transiciones(ctx.objeto.potencia):
        diferencia = paso.actual - paso.anterior
        ctx.restriccion("subida", paso.periodo, diferencia <= ctx.parametros.subida * paso.horas)
        ctx.restriccion("bajada", paso.periodo, -diferencia <= ctx.parametros.bajada * paso.horas)
'''


@unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
class TemporalRuntimeTests(unittest.TestCase):
    def execute(self, **changes):
        payload = {"code": CODE, "parameters": PARAMETERS, "object": {"id": 7, "key": "unit"},
                   "objects": [OBJECTS[0]], "grid": GRID,
                   "temporal": {"first_period": "omit", "initial_values": []}, **changes}
        return OCIExecutor.from_env().execute(payload, uuid.uuid4().hex, threading.Event())

    def test_both_ramps_use_distance_between_starts_and_keep_previous_terms(self):
        result = self.execute()
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual(result["ir"]["version"], "affine_temporal.v1")
        self.assertEqual([(r["name"], r["period"], r["constant"],
                           [(t["period"], t["coefficient"]) for t in r["terms"]]) for r in result["ir"]["rows"]],
                         [("bajada", 1, -1, [(0, 1), (1, -1)]), ("subida", 1, -2, [(0, -1), (1, 1)]),
                          ("bajada", 2, -4, [(1, 1), (2, -1)]), ("subida", 2, -8, [(1, -1), (2, 1)])])
        self.assertEqual(result["temporal"]["omitted_periods"], [0])

    def test_one_period_uses_declared_value_unit_and_instant_or_explicit_omission(self):
        policy = {"first_period": "initial", "initial_values": [{"object_id": 7, "variable": "potencia",
                  "value": 2, "unit": "mw", "timestamp": "2025-12-31T23:30:00Z"}]}
        result = self.execute(grid=GRID[:1], temporal=policy)
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual([(r["name"], r["period"], r["constant"]) for r in result["ir"]["rows"]],
                         [("bajada", 0, 1), ("subida", 0, -4)])
        self.assertEqual(result["temporal"]["omitted_periods"], [])
        omitted = self.execute(grid=GRID[:1])
        self.assertEqual(omitted["status"], "succeeded", omitted)
        self.assertEqual(omitted["ir"]["rows"], [])
        self.assertEqual(omitted["temporal"]["omitted_periods"], [0])

    def test_invalid_temporal_references_report_the_affected_period_and_line(self):
        for index in (-1, 3):
            with self.subTest(index=index):
                result = self.execute(code=f'def construir(ctx):\n    ctx.restriccion("r", 0, ctx.objeto.potencia[{index}] <= ctx.objeto.potencia[0])\n')
                self.assertEqual(result["status"], "failed", result)
                self.assertEqual((result["error"].get("period"), result["error"]["line"]), (index, 2))
        future = self.execute(code='def construir(ctx):\n    ctx.restriccion("r", 0, ctx.objeto.potencia[1] <= ctx.objeto.potencia[0])\n')
        self.assertEqual(future["status"], "failed", future)
        self.assertEqual((future["error"].get("period"), future["error"].get("line")), (0, 2))

    def test_ramp_dimension_and_initial_time_errors_are_localized(self):
        bad = self.execute(parameters=[{**p, "unit": "m3_per_s_per_h"} for p in PARAMETERS])
        self.assertEqual(bad["status"], "failed", bad)
        self.assertEqual((bad["error"].get("period"), bad["error"]["line"]), (1, 4))
        for timestamp in ("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"):
            bad = self.execute(temporal={"first_period": "initial", "initial_values": [{"object_id": 7,
                "variable": "potencia", "value": 2, "unit": "mw", "timestamp": timestamp}]})
            self.assertEqual(bad["status"], "failed", bad)
            self.assertEqual((bad["error"].get("period"), bad["error"]["line"]), (0, 2))

    def test_period_collection_cannot_wrap_negative_indices(self):
        result = self.execute(code='def construir(ctx):\n    t = ctx.periodos[-1]\n    ctx.restriccion("r", t, ctx.objeto.potencia[t] <= ctx.objeto.potencia[0])\n')
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual((result["error"]["period"], result["error"]["line"]), (-1, 2))
