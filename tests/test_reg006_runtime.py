"""Water and energy budgets compiled through the real OCI runtime."""
import os
import threading
import unittest
import uuid
from datetime import datetime, timedelta

from app.rule_runtime import OCIExecutor
from tests.test_reg004_runtime import OBJECTS
from tests.test_reg005_runtime import GRID

POLICY = {"kind": "horizon", "timezone": "UTC", "partial": "reject"}
CODE = '''def construir(ctx):
    for ventana in ctx.ventanas():
        ctx.restriccion("energia", ventana, ventana.integral(ctx.objeto.potencia) <= ctx.parametros.energia)
'''


@unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
class BudgetRuntimeTests(unittest.TestCase):
    def execute(self, **changes):
        payload = {"code": CODE, "parameters": [{"name": "energia", "type": "number", "unit": "mwh", "value": 12}],
                   "object": {"id": 7, "key": "unit"}, "objects": [OBJECTS[0]], "grid": GRID,
                   "windows": POLICY, **changes}
        return OCIExecutor.from_env().execute(payload, uuid.uuid4().hex, threading.Event())

    def test_civil_days_keep_the_real_23_or_25_utc_intervals_including_midnight_changes(self):
        cases = [("America/New_York", "2024-03-10T05:00:00Z", 23, "2024-03-11T04:00:00Z"),
                 ("America/New_York", "2024-11-03T04:00:00Z", 25, "2024-11-04T05:00:00Z"),
                 ("America/Santiago", "2024-09-08T04:00:00Z", 23, "2024-09-09T03:00:00Z"),
                 ("America/Santiago", "2024-04-06T03:00:00Z", 25, "2024-04-07T04:00:00Z")]
        for zone, start, hours, end in cases:
            with self.subTest(zone=zone, start=start):
                first = datetime.fromisoformat(start.replace("Z", "+00:00"))
                grid = [{"timestamp": (first + timedelta(hours=t)).isoformat(), "duration_hours": 1} for t in range(hours)]
                result = self.execute(grid=grid, windows={"kind": "civil_day", "timezone": zone, "partial": "reject"})
                self.assertEqual(result["status"], "succeeded", result)
                self.assertEqual(len(result["ir"]["rows"]), 1)
                row = result["ir"]["rows"][0]
                self.assertEqual(row["window"], {"start": start, "end": end, "duration_hours": hours,
                                               "periods": list(range(hours)), "partial": False})
                self.assertEqual((len(row["terms"]), row["constant"]), (hours, -12))

    def test_horizon_energy_weights_every_period_by_its_actual_hours(self):
        result = self.execute()
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual(result["ir"]["version"], "affine_budget.v1")
        row = result["ir"]["rows"][0]
        self.assertEqual((row["constant"], row["unit"]), (-12, "mwh"))
        self.assertEqual([(t["period"], t["coefficient"], t["unit"]) for t in row["terms"]],
                         [(0, 0.5, "h"), (1, 2, "h"), (2, 1, "h")])
        self.assertEqual(row["window"], {"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T03:30:00Z",
                         "duration_hours": 3.5, "periods": [0, 1, 2], "partial": False})

    def test_partial_days_need_consent_and_crossing_intervals_never_get_prorated(self):
        policy = {"kind": "civil_day", "timezone": "UTC", "partial": "reject"}
        rejected = self.execute(windows=policy)
        self.assertEqual(rejected["status"], "failed", rejected)
        self.assertEqual((rejected["error"]["line"], rejected["error"]["period"]), (2, 0))
        allowed = self.execute(windows={**policy, "partial": "allow"})
        self.assertEqual(allowed["status"], "succeeded", allowed)
        self.assertEqual((allowed["ir"]["rows"][0]["window"]["partial"], allowed["ir"]["rows"][0]["constant"]), (True, -12))
        crossing = self.execute(windows={**policy, "partial": "allow"}, grid=[
            {"timestamp": "2026-01-01T23:30:00Z", "duration_hours": 2}])
        self.assertEqual(crossing["status"], "failed", crossing)
        self.assertEqual((crossing["error"]["line"], crossing["error"]["period"]), (2, 0))
        self.assertIn("borde", crossing["error"]["message"])

    def test_empty_windows_and_wrong_dimensions_report_the_source_line_and_period(self):
        empty = self.execute(grid=[])
        self.assertEqual(empty["status"], "failed", empty)
        self.assertEqual((empty["error"].get("line"), empty["error"].get("period")), (2, 0))
        incompatible = self.execute(parameters=[{"name": "energia", "type": "number", "unit": "mw", "value": 12}])
        self.assertEqual(incompatible["status"], "failed", incompatible)
        self.assertEqual((incompatible["error"].get("line"), incompatible["error"].get("period")), (3, 2))
        unweighted = self.execute(code='def construir(ctx):\n    for v in ctx.ventanas():\n        ctx.restriccion("energia", v, sum(ctx.objeto.potencia[t] for t in v.periodos) <= ctx.parametros.energia)\n')
        self.assertEqual(unweighted["status"], "failed", unweighted)
        self.assertEqual((unweighted["error"]["line"], unweighted["error"]["period"]), (3, 2))

    def test_water_integrals_add_components_and_convert_explicitly_from_m3_to_hm3(self):
        for unit, conversion, budget, expected in (("m3", "", 36000, [1800, 7200, 3600]),
                                                  ("hm3", '.a("hm3")', 0.036, [0.0018, 0.0072, 0.0036])):
            with self.subTest(unit=unit):
                result = self.execute(objects=OBJECTS, aliases=[{"alias": "otra", "object_id": 8}],
                    parameters=[{"name": "agua", "type": "number", "unit": unit, "value": budget}],
                    code='def construir(ctx):\n    for v in ctx.ventanas():\n        agua = v.integral(ctx.objeto.caudal) + v.integral(ctx.objetos.otra.caudal)\n        ctx.restriccion("agua", v, agua' + conversion + ' <= ctx.parametros.agua)\n')
                self.assertEqual(result["status"], "succeeded", result)
                row = result["ir"]["rows"][0]
                self.assertEqual((row["unit"], row["constant"]), (unit, -budget))
                self.assertEqual([(t["object_id"], t["period"]) for t in row["terms"]],
                                 [(7, 0), (7, 1), (7, 2), (8, 0), (8, 1), (8, 2)])
                for term, coefficient in zip(row["terms"], expected * 2):
                    self.assertAlmostEqual(term["coefficient"], coefficient)
                    self.assertEqual(term["unit"], "s" if unit == "m3" else "hm3_per_m3_per_s")
