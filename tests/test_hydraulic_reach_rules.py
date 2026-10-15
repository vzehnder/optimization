"""Reach rules through authenticated HTTP, trusted SDK fixtures and frozen runs."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from app.rule_ir import validate_ir, validate_model_bounds, RuleBoundsError
from app.rule_runtime import SDK_VERSION
from app.rule_worker import RuleWorker
from tests.auth_test_helpers import post_json_with_csrf
from tests.test_reg001_rules import PAYLOAD
from tests import test_reg003_rules as hourly

CODE = '''def construir(ctx):
    for t in ctx.periodos:
        ctx.restriccion("suma", t, ctx.objeto.caudal[t] >= ctx.objetos.b.caudal[t] + ctx.objetos.c.caudal[t])
'''
LOCAL_CODE = '''def construir(ctx):
    for t in ctx.periodos:
        ctx.restriccion("maximo", t, ctx.objeto.caudal[t] <= ctx.parametros.capacidad)
'''


class TrustedFixtureExecutor:
    """Runs only the two authored fixture programs; not an OCI security test."""
    def describe(self):
        return {"image": "fixture", "sdk": SDK_VERSION, "policy": "fixture"}

    def remove(self, _):
        pass

    def execute(self, payload, *_):
        assert payload["code"] in (CODE, LOCAL_CODE)
        result = subprocess.run([sys.executable, str(Path(__file__).parents[1] / "runtime/component_rules/entry.py")],
                                input=json.dumps(payload), capture_output=True, text=True, check=True, timeout=10)
        value = json.loads(result.stdout)
        if value["status"] == "succeeded":
            value["ir"] = validate_ir(value["ir"], payload["object"]["id"], len(payload["grid"]), payload["objects"])
            validate_model_bounds(value["ir"]["rows"], payload["objects"], payload["compilation"]["system_case"])
        return value


class ReachRuleTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = hourly.HourlyRuleApiTests.setUp
    tearDown = hourly.HourlyRuleApiTests.tearDown
    hydraulic_scope = hourly.HourlyRuleApiTests.hydraulic_scope
    preview = hourly.HourlyRuleApiTests.preview
    source = hourly.HourlyRuleApiTests.source

    def fixture(self):
        scope = self.hydraulic_scope()
        diagram = self.store.get_hydraulic_diagram(scope["scenario_id"])
        base = diagram["reaches"][0]
        reaches = [base] + [{**base, "technical_key": key, "display_name": key, "reach_type": "bypass"} for key in ("b", "c")]
        self.store.save_hydraulic_diagram(scenario_id=scope["scenario_id"], revision=diagram["revision"], nodes=diagram["nodes"], reaches=reaches)
        response = self.client.get(f"/api/scenarios/{scope['scenario_id']}/hydraulic-reaches/reach/rule-context")
        self.assertEqual(response.status_code, 200, response.text)
        object_id = response.json()["object_id"]
        self.root = f"/api/projects/{self.project['id']}/linkable-objects/{object_id}/rules"
        response = self.client.get(self.root + "/object-candidates", params={"scenario_id": scope["scenario_id"]})
        self.assertEqual(response.status_code, 200, response.text)
        return scope, {o["key"]: o for o in response.json()["items"]}

    def test_reach_rule_can_be_published_compiled_applied_and_frozen_in_a_run(self):
        scope, objects = self.fixture()
        self.assertEqual(self.client.get(self.root).json()["object"]["kind"], "hydraulic_reach")
        aliases = [{"alias": key, "object_id": objects[key]["id"]} for key in ("b", "c")]
        response = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": CODE, "parameters": [], "aliases": aliases, "scenario_id": scope["scenario_id"]})
        self.assertEqual(response.status_code, 201, response.text)
        path = self.root + "/" + response.json()["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, TrustedFixtureExecutor()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        self.assertEqual(job["result"]["ir"]["version"], "affine_hydraulic.v1")
        terms = {t["object_id"]: t["coefficient"] for t in job["result"]["ir"]["rows"][0]["terms"]}
        self.assertEqual(terms, {objects["reach"]["id"]: 1, objects["b"]["id"]: -1, objects["c"]["id"]: -1})
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Balance operativo de canales"})
        self.assertEqual(applied.status_code, 201, applied.text)
        self.engine.capabilities.append("affine_hydraulic.v1")
        run = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run", {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(run.status_code, 201, run.text)
        document = self.store.get_scenario_version(run.json()["scenario_version_id"])["system_case_json"]
        self.assertEqual({o["reach_key"] for o in document["component_rules"]["objects"]}, {"reach", "b", "c"})
        self.assertEqual(len(document["component_rules"]["rows"]), 4)
        # Changing the topology must make the application stale/invalid.
        diagram = self.store.get_hydraulic_diagram(scope["scenario_id"])
        self.store.save_hydraulic_diagram(scenario_id=scope["scenario_id"], revision=diagram["revision"], nodes=diagram["nodes"], reaches=[r for r in diagram["reaches"] if r["technical_key"] != "c"])
        self.assertIn(self.client.get(path + "/applications").json()["items"][0]["validation_status"], {"invalid", "stale"})

    def test_local_reach_flow_contract_is_upgraded_for_solver_and_inputs_are_compatible(self):
        scope, objects = self.fixture()
        self.source()
        inputs = self.client.get(self.root + "/input-candidates").json()["items"]
        self.assertTrue(any(p["binding_role_key"] == "rule_inflow" for p in inputs))
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": LOCAL_CODE, "scenario_id": scope["scenario_id"]}).json()
        path = self.root + "/" + saved["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, TrustedFixtureExecutor()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "succeeded", job)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Capacidad canal"})
        self.assertEqual(applied.status_code, 201, applied.text)
        self.engine.capabilities.append("affine_hydraulic.v1")
        run = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run", {k: scope[k] for k in ("range_start", "range_end")})
        self.assertEqual(run.status_code, 201, run.text)
        document = self.store.get_scenario_version(run.json()["scenario_version_id"])["system_case_json"]
        self.assertEqual(document["component_rules"]["version"], "affine_hydraulic.v1")
        obj = objects["reach"]
        row = {"name": "impossible", "line": 3, "period": 0, "relation": "<=", "unit": "m3_per_s", "constant": 1,
               "terms": [{"object_id": obj["id"], "variable": "caudal", "period": 0, "coefficient": 1, "unit": "dimensionless"}]}
        with self.assertRaises(RuleBoundsError):
            validate_model_bounds([row], [obj], document)
        row["constant"] = -2
        document["time_series"][0]["minimum_flow_m3s"] = {"reach": 3}
        with self.assertRaises(RuleBoundsError):
            validate_model_bounds([row], [obj], document)
        invalid = copy.deepcopy(row)
        invalid["terms"][0]["variable"] = "potencia"
        with self.assertRaises(ValueError):
            validate_ir({"version": "affine_hydraulic.v1", "rows": [invalid]}, obj["id"], 4, [obj])

    def test_unknown_reach_context_and_wrong_project_are_rejected(self):
        scope, objects = self.fixture()
        self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/hydraulic-reaches/missing/rule-context").status_code, 404)
        other = self.store.create_project(name="Other")
        self.assertEqual(self.client.get(f"/api/projects/{other['id']}/linkable-objects/{objects['reach']['id']}/rules").status_code, 404)
        self.client.cookies.clear()
        self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/hydraulic-reaches/reach/rule-context").status_code, 401)
