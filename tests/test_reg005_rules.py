"""Temporal policies and snapshots at the authenticated HTTP boundary."""
import os
import unittest

from tests import test_reg003_rules as hourly
from tests.test_reg001_rules import PAYLOAD
from tests.auth_test_helpers import post_json_with_csrf
from tests.test_reg005_runtime import CODE, GRID, PARAMETERS


class TemporalRuleApiTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = hourly.HourlyRuleApiTests.setUp
    tearDown = hourly.HourlyRuleApiTests.tearDown
    hydraulic_scope = hourly.HourlyRuleApiTests.hydraulic_scope
    preview = hourly.HourlyRuleApiTests.preview

    def ramp_scope(self):
        scope = self.hydraulic_scope()
        diagram = self.store.get_hydraulic_diagram(scope["scenario_id"])
        reservoir = next(n for n in diagram["nodes"] if n["technical_key"] == "reservoir_alpha")
        reservoir["natural_inflow_series"] = {"points": [{**p, "value_m3s": 0} for p in GRID]}
        self.store.save_hydraulic_diagram(scenario_id=scope["scenario_id"], revision=diagram["revision"],
                                        nodes=diagram["nodes"], reaches=diagram["reaches"])
        return {**scope, "range_end": "2026-01-01T03:30:00Z"}

    def test_initial_policy_and_ramp_units_survive_saving_and_publication(self):
        scope = self.hydraulic_scope()
        identity = self.client.get(self.root).json()["object"]["id"]
        temporal = {"first_period": "initial", "initial_values": [{
            "object_id": identity, "variable": "potencia", "value": 2,
            "unit": "mw", "timestamp": "2025-12-31T23:30:00Z"}]}
        payload = {**PAYLOAD, "scenario_id": scope["scenario_id"], "temporal": temporal,
                   "parameters": [{"name": "subida", "type": "number", "unit": "mw_per_h", "value": 4}]}
        saved = post_json_with_csrf(self.client, self.root, payload)
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        self.assertEqual(self.client.get(path).json()["temporal"], temporal)
        published = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1})
        self.assertEqual(published.status_code, 201, published.text)
        self.assertEqual(published.json()["temporal"], temporal)
        self.assertEqual(published.json()["parameters"][0]["unit"], "mw_per_h")

    def test_initial_contract_rejects_missing_ambiguous_or_incompatible_values(self):
        scope = self.hydraulic_scope()
        identity = self.client.get(self.root).json()["object"]["id"]
        initial = {"object_id": identity, "variable": "potencia", "value": 2,
                   "unit": "mw", "timestamp": "2025-12-31T23:30:00Z"}
        policies = [{"first_period": "initial", "initial_values": []},
                    {"first_period": "omit", "initial_values": [initial]},
                    {"first_period": "initial", "initial_values": [initial, initial]}]
        policies += [{"first_period": "initial", "initial_values": [{**initial, **change}]} for change in
                     ({"object_id": 999999}, {"unit": "m3_per_s"}, {"variable": "almacenamiento"},
                      {"timestamp": "2025-12-31T23:30:00"}, {"timestamp": "invalid"})]
        for policy in policies:
            with self.subTest(policy=policy):
                response = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "scenario_id": scope["scenario_id"], "temporal": policy})
                self.assertEqual(response.status_code, 422, response.text)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_flow_ramps_keep_the_initial_value_and_do_not_masquerade_as_hourly_bounds(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.ramp_scope()
        identity = self.client.get(self.root).json()["object"]["id"]
        policy = {"first_period": "initial", "initial_values": [{"object_id": identity, "variable": "caudal", "value": 2,
                  "unit": "m3_per_s", "timestamp": "2025-12-31T23:30:00Z"}]}
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": CODE.replace("potencia", "caudal"),
            "parameters": [{**p, "unit": "m3_per_s_per_h"} for p in PARAMETERS], "temporal": policy})
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
            self.assertEqual(job["status"], "succeeded", job)
            self.assertEqual(job["result"]["bounds"], [])
            self.assertEqual([r["constant"] for r in job["result"]["ir"]["rows"]], [1, -4, -1, -2, -4, -8])
            applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Condición inicial"})
            self.assertEqual(applied.status_code, 201, applied.text)
            self.assertEqual(applied.json()["temporal"], policy)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_bounds_on_previous_decisions_intersect_at_the_referenced_period(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.ramp_scope()
        code = '''def construir(ctx):
    ctx.restriccion("minimo", 0, ctx.objeto.caudal[0] >= ctx.parametros.minimo)
    ctx.restriccion("previo", 1, ctx.objeto.caudal[0] <= ctx.parametros.maximo)
'''
        parameters = [{"name": name, "type": "number", "unit": "m3_per_s", "value": value} for name, value in (("minimo", 5), ("maximo", 3))]
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": code, "parameters": parameters,
            "temporal": {"first_period": "omit", "initial_values": []}})
        path = self.root + "/" + saved.json()["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
        self.assertEqual(job["status"], "failed", job)
        self.assertEqual(job["result"]["error"]["code"], "RULE_BOUNDS_CONFLICT")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_temporal_preview_run_snapshot_and_new_horizon_preserve_exact_references(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.ramp_scope()
        temporal = {"first_period": "omit", "initial_values": []}
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": CODE, "parameters": PARAMETERS, "temporal": temporal})
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
            self.assertEqual(job["status"], "succeeded", job)
            self.assertEqual([r["constant"] for r in job["result"]["ir"]["rows"]], [-1, -2, -4, -8])
            self.assertEqual(job["result"].get("bounds"), [])
            self.assertEqual(job["result"]["temporal"]["omitted_periods"], [0])
            application = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Rampas verificadas"})
            self.assertEqual(application.status_code, 201, application.text)
            run_path = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
            body = {k: scope[k] for k in ("range_start", "range_end")}
            unsupported = post_json_with_csrf(self.client, run_path, body)
            self.assertEqual(unsupported.status_code, 409, unsupported.text)
            self.engine.capabilities.append("affine_temporal.v1")
            run = post_json_with_csrf(self.client, run_path, body)
            self.assertEqual(run.status_code, 201, run.text)
            version_path = f"/api/scenario-versions/{run.json()['scenario_version_id']}"
            version = self.client.get(version_path).json()["scenario_version"]
            block = version["system_case_json"]["component_rules"]
            self.assertEqual(block["version"], "affine_temporal.v1")
            self.assertEqual(block["applications"][0]["temporal"], temporal)
            self.assertEqual(block["applications"][0]["ir"], job["result"]["ir"])
            self.assertEqual([p["duration_hours"] for p in block["grid"]], [0.5, 2, 1])
            changed = {**scope, "range_start": "2026-01-01T00:30:00Z"}
            blocked = post_json_with_csrf(self.client, run_path, {k: changed[k] for k in body})
            self.assertEqual(blocked.status_code, 409, blocked.text)
            new_job = self.preview(changed, path, publication)
            self.assertEqual(new_job["status"], "succeeded", new_job)
            self.assertEqual([(r["period"], r["constant"]) for r in new_job["result"]["ir"]["rows"]], [(1, -4), (1, -8)])
            self.assertEqual(self.client.get(version_path).json()["scenario_version"], version)


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL required")
class TemporalRulePostgresTests(TemporalRuleApiTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
