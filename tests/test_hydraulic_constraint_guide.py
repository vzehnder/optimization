"""Compile every authored Python example shipped in the downloaded manual."""
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

from app.rule_ir import validate_ir, validate_outputs

ROOT = Path(__file__).parents[1]


class GuideExamplesTests(unittest.TestCase):
    def test_all_documented_programs_compile_with_the_documented_units_and_policies(self):
        guide = (ROOT / "frontend/src/hydraulicConstraintGuide.md").read_text(encoding="utf-8")
        examples = re.findall(r"```python\n(.*?)\n```", guide, re.S)
        self.assertGreaterEqual(len(examples), 11)
        objects = [{"id": n, "kind": "hydraulic_reach", "variables": {"caudal": "m3_per_s"}} for n in range(1, 6)]
        objects.append({"id": 6, "kind": "hydraulic_node", "variables": {"vertimiento": "m3_per_s", "almacenamiento": "hm3"}})
        grid = [{"timestamp": f"2026-01-01T0{t}:00:00Z", "duration_hours": 1} for t in range(3)]
        for index, code in enumerate(examples):
            with self.subTest(example=index + 1):
                parameters = [{"name": key, "type": "number", "unit": "m3_per_s", "value": 20} for key in ("limite", "minimo", "maximo", "margen", "capacidad")]
                parameters += [{"name": "fraccion", "type": "number", "unit": "dimensionless", "value": 0.5},
                               {"name": "agua", "type": "number", "unit": "hm3", "value": 0.036},
                               {"name": "activar", "type": "boolean", "unit": "dimensionless", "value": True}]
                parameters += [{"name": key, "type": "number", "unit": "m3_per_s_per_h", "value": 2} for key in ("subida", "bajada")]
                payload = {"code": code, "object": {"id": 1}, "objects": objects, "grid": grid, "parameters": parameters,
                           "aliases": [{"alias": alias, "object_id": n} for alias, n in (("b", 2), ("c", 3), ("principal", 4), ("canal", 5), ("embalse", 6))],
                           "inputs": [{"alias": "afluente", "unit_key": "m3_per_s", "values": [1, 2, 3]},
                                      {"alias": "disponibilidad", "unit_key": "dimensionless", "values": [1, 0.5, 0]}]}
                if "ctx.transiciones" in code:
                    payload["temporal"] = {"first_period": "omit", "initial_values": []}
                if "ctx.ventanas" in code:
                    payload["windows"] = {"kind": "horizon", "timezone": "UTC", "partial": "reject"}
                process = subprocess.run([sys.executable, str(ROOT / "runtime/component_rules/entry.py")],
                                         input=json.dumps(payload), text=True, capture_output=True, check=True, timeout=10)
                result = json.loads(process.stdout)
                self.assertEqual(result["status"], "succeeded", result)
                ir = validate_ir(result["ir"], 1, len(grid), objects, grid=grid, temporal=payload.get("temporal"), windows=payload.get("windows"))
                self.assertTrue(ir["rows"])
                validate_outputs(result["outputs"], len(grid))
