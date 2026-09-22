"""Symbolic SDK contract through the real OCI boundary."""
import os
import threading
import unittest
import uuid

from app.rule_runtime import OCIExecutor

CODE = 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= ctx.parametros.limite)\n'
PARAMETERS = [{"name": "limite", "type": "number", "unit": "m3_per_s", "value": 5}]
GRID = [{"timestamp": f"2026-01-01T0{t}:00:00", "duration_hours": 1} for t in range(4)]


@unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
class SymbolicRuntimeTests(unittest.TestCase):
    def execute(self, code=CODE):
        return OCIExecutor.from_env().execute(
            {"code": code, "parameters": PARAMETERS, "object": {"id": 7, "key": "unit"}, "grid": GRID},
            uuid.uuid4().hex, threading.Event(),
        )

    def test_python_emits_named_affine_rows_for_the_entire_grid(self):
        result = self.execute()
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual(result["ir"], {
            "version": "affine_flow.v1",
            "rows": [{"name": "maximo", "line": 3, "period": t, "relation": "<=", "unit": "m3_per_s", "constant": -5.0,
                      "terms": [{"object_id": 7, "variable": "caudal", "period": t, "coefficient": 1.0, "unit": "dimensionless"}]}
                     for t in range(4)],
        })

    def test_affine_arithmetic_preserves_relations_and_combines_repeated_terms(self):
        result = self.execute('''def construir(ctx):
    for t in ctx.periodos:
        q = ctx.objeto.caudal[t]
        ctx.restriccion("a", t, (q + q) / 2 - ctx.parametros.limite <= ctx.parametros.limite)
        ctx.restriccion("b", t, -q >= -ctx.parametros.limite)
        ctx.restriccion("c", t, 2 * q == 2 * ctx.parametros.limite)
''')
        self.assertEqual(result["status"], "succeeded", result)
        rows = result["ir"]["rows"][:3]
        self.assertEqual([(r["relation"], r["constant"], r["terms"][0]["coefficient"]) for r in rows],
                         [("<=", -10, 1), (">=", 5, -1), ("==", -10, 2)])

    def test_symbolic_conditions_and_nonlinear_decisions_fail_with_source_location(self):
        for expression in ("q * q", "q / q", "q ** 2", "abs(q)", "min(q, ctx.parametros.limite)",
                           "bool(q)", "bool(q <= ctx.parametros.limite)",
                           "ctx.parametros.limite <= q <= ctx.parametros.limite", "ctx.objeto.caudal[-1]"):
            with self.subTest(expression=expression):
                result = self.execute(f"def construir(ctx):\n    q = ctx.objeto.caudal[0]\n    value = {expression}\n")
                self.assertEqual(result["status"], "failed", result)
                self.assertEqual(result["error"]["line"], 3, result)

    def test_known_quantities_can_be_calculated_and_used_in_python_conditions(self):
        result = self.execute('''def construir(ctx):
    limite = ctx.parametros.limite / 2 + ctx.parametros.limite / 2
    if limite > ctx.parametros.limite * 0:
        for t in ctx.periodos:
            ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= limite)
''')
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual([row["constant"] for row in result["ir"]["rows"]], [-5, -5, -5, -5])
