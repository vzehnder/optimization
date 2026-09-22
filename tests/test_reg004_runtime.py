"""Multi-object symbolic behavior through the real isolated runtime."""
import os
import threading
import unittest
import uuid

from app.rule_runtime import OCIExecutor
from tests.test_reg002_runtime import GRID

OBJECTS = [
    {"id": 7, "kind": "hydraulic_unit", "unit_key": "unit", "variables": {"caudal": "m3_per_s", "potencia": "mw"}},
    {"id": 8, "kind": "hydraulic_unit", "unit_key": "second", "variables": {"caudal": "m3_per_s", "potencia": "mw"}},
    {"id": 9, "kind": "hydraulic_plant", "plant_key": "plant", "variables": {"potencia": "mw"}, "member_ids": [7, 8]},
    {"id": 10, "kind": "hydraulic_node", "node_key": "reservoir", "variables": {"almacenamiento": "hm3", "vertimiento": "m3_per_s"}},
]


@unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
class RelatedRuntimeTests(unittest.TestCase):
    def execute(self, expression, parameters=None):
        return OCIExecutor.from_env().execute({
            "code": 'def construir(ctx):\n    for t in ctx.periodos:\n        ctx.restriccion("conjunto", t, ' + expression + ')\n',
            "parameters": parameters or [{"name": "limite", "type": "number", "unit": "mw", "value": 10}],
            "object": {"id": 7, "key": "unit"}, "objects": OBJECTS,
            "aliases": [{"alias": name, "object_id": identity} for name, identity in (("otra", 8), ("central", 9), ("embalse", 10))],
            "grid": GRID,
        }, uuid.uuid4().hex, threading.Event())

    def test_shared_power_limit_and_plant_alias_expand_to_the_same_real_decisions(self):
        for expression in ("ctx.objeto.potencia[t] + ctx.objetos.otra.potencia[t]", "ctx.objetos.central.potencia[t]"):
            with self.subTest(expression=expression):
                result = self.execute(expression + " <= ctx.parametros.limite")
                self.assertEqual(result["status"], "succeeded", result)
                self.assertEqual(result["ir"]["version"], "affine_hydraulic.v1")
                self.assertEqual([(r["unit"], r["constant"], [(t["object_id"], t["variable"], t["coefficient"]) for t in r["terms"]])
                                  for r in result["ir"]["rows"]], [("mw", -10, [(7, "potencia", 1), (8, "potencia", 1)])] * 4)

    def test_invalid_referenced_decisions_report_the_alias_and_source_line(self):
        for expression in ("ctx.objetos.otra.potencia[t] * ctx.objetos.otra.potencia[t] <= ctx.parametros.limite",
                           "ctx.objetos.otra.caudal[t] <= ctx.parametros.limite",
                           "ctx.objetos.otra.cota[t] <= ctx.parametros.limite"):
            with self.subTest(expression=expression):
                result = self.execute(expression)
                self.assertEqual(result["status"], "failed", result)
                self.assertEqual((result["error"]["alias"], result["error"]["line"]), ("otra", 3))

    def test_a_declared_plant_map_requires_the_hydraulic_contract_even_for_local_flow_rows(self):
        result = self.execute("ctx.objeto.caudal[t] <= ctx.parametros.limite", [{"name": "limite", "type": "number", "unit": "m3_per_s", "value": 10}])
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual(result["ir"]["version"], "affine_hydraulic.v1")
