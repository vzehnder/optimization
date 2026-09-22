"""Budget policy and frozen integrals through the authenticated HTTP boundary."""
import os
import unittest

from tests import test_reg003_rules as hourly
from tests.test_reg001_rules import PAYLOAD
from tests.auth_test_helpers import post_json_with_csrf


class BudgetRuleApiTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    setUp = hourly.HourlyRuleApiTests.setUp
    tearDown = hourly.HourlyRuleApiTests.tearDown
    hydraulic_scope = hourly.HourlyRuleApiTests.hydraulic_scope
    preview = hourly.HourlyRuleApiTests.preview

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_budget_preview_application_and_run_keep_policy_windows_and_component_terms(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        from tests.test_reg006_runtime import CODE, POLICY
        scope = self.hydraulic_scope()
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": CODE, "windows": POLICY,
            "parameters": [{"name": "energia", "type": "number", "unit": "mwh", "value": 12}]})
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            job = self.preview(scope, path, publication)
            self.assertEqual(job["status"], "succeeded", job)
            self.assertEqual(job["result"]["bounds"], [])
            self.assertEqual(job["result"]["windows"], POLICY)
            self.assertEqual(job["result"]["ir"]["rows"][0]["window"]["duration_hours"], 4)
            applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Energía verificada"})
            self.assertEqual(applied.status_code, 201, applied.text)
            self.assertEqual(applied.json()["windows"], POLICY)
            target = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
            body = {k: scope[k] for k in ("range_start", "range_end")}
            self.assertEqual(post_json_with_csrf(self.client, target, body).status_code, 409)
            self.engine.capabilities.append("affine_budget.v1")
            run = post_json_with_csrf(self.client, target, body)
            self.assertEqual(run.status_code, 201, run.text)
            lineage = self.client.get(f"/api/runs/{run.json()['id']}").json()["run"]["materialized_lineage"]
            self.assertEqual(lineage["component_rules"][0]["windows"], POLICY)
            version_path = f"/api/scenario-versions/{run.json()['scenario_version_id']}"
            version = self.client.get(version_path).json()["scenario_version"]
            block = version["system_case_json"]["component_rules"]
            self.assertEqual(block["version"], "affine_budget.v1")
            self.assertEqual(block["applications"][0]["windows"], POLICY)
            self.assertEqual(block["applications"][0]["ir"], job["result"]["ir"])
            self.assertEqual(block["grid"][0]["timestamp"], "2026-01-01T00:00:00")
            self.assertEqual(post_json_with_csrf(self.client, target, {**body, "range_start": "2026-01-01T01:00:00Z"}).status_code, 409)
            self.assertEqual(self.client.get(version_path).json()["scenario_version"], version)

    def test_window_policy_requires_a_known_iana_zone_and_explicit_partial_choice(self):
        for policy in ({"kind": "civil_day", "timezone": "Mars/Base", "partial": "reject"},
                       {"kind": "civil_day", "timezone": "+03:00", "partial": "allow"},
                       {"kind": "civil_day", "timezone": "UTC"}):
            with self.subTest(policy=policy):
                response = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "windows": policy})
                self.assertEqual(response.status_code, 422, response.text)

    def test_budget_policy_and_units_survive_saving_and_publication(self):
        policy = {"kind": "civil_day", "timezone": "America/Santiago", "partial": "reject"}
        parameters = [{"name": name, "type": "number", "unit": unit, "value": value}
                      for name, unit, value in (("agua", "m3", 36000), ("energia", "mwh", 12))]
        saved = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "windows": policy, "parameters": parameters})
        self.assertEqual(saved.status_code, 201, saved.text)
        path = self.root + "/" + saved.json()["id"]
        self.assertEqual(self.client.get(path).json()["windows"], policy)
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1})
        self.assertEqual(publication.status_code, 201, publication.text)
        self.assertEqual(publication.json()["windows"], policy)
        self.assertEqual([p["unit"] for p in publication.json()["parameters"]], ["m3", "mwh"])


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL required")
class BudgetRulePostgresTests(BudgetRuleApiTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
