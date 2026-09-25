"""REG-001: behavior through authenticated HTTP, on both database engines."""
import os
import time
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf, put_json_with_csrf
from tests.test_ts7_003_linkable_object_register import HydraulicFixture


FORMULA = "def construir(ctx):\n    return ctx.parametros.capacidad * ctx.parametros.disponibilidad\n"
PAYLOAD = {
    "name": "Capacidad por disponibilidad",
    "code": FORMULA,
    "parameters": [
        {"name": "capacidad", "type": "number", "unit": "m3_per_s", "value": 80, "min": 0, "max": 100},
        {"name": "disponibilidad", "type": "number", "unit": "dimensionless", "value": 0.75, "min": 0, "max": 1},
    ],
    "expected_revision": 0,
}


class RuleApiTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="reg001-")
        database_url = self.database_url
        if database_url.startswith("sqlite") and "restart" in self._testMethodName:
            database_url = f"sqlite:///{self.temporary.name}/rules.sqlite3"
        self.store = AnalystStore(database_url)
        self.token = uuid.uuid4().hex
        self.project = self.store.create_project(name=f"REG-001 {self.token}")
        fixture = HydraulicFixture(self.store, self.project["id"], prefix=self.token)
        self.obj = self.store.register_linkable_object(
            project_id=self.project["id"], object_kind="hydraulic_unit",
            subtype_id=fixture.ids["hydraulic_unit"],
        )
        self.user = self.store.create_user(
            email=f"{self.token}@rules.test", display_name="Analista", role="analyst",
            password_hash=hash_password("test password"),
        )
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.client.__enter__()
        login_json_with_csrf(self.client, self.user["email"], "test password")
        self.root = f"/api/projects/{self.project['id']}/linkable-objects/{self.obj['id']}/rules"

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temporary.cleanup()

    def test_analyst_can_save_and_reopen_contextual_typed_draft(self):
        saved = post_json_with_csrf(self.client, self.root, PAYLOAD)
        self.assertEqual(saved.status_code, 201, saved.text)
        rule = saved.json()
        reopened = self.client.get(f"{self.root}/{rule['id']}")
        self.assertEqual(reopened.status_code, 200, reopened.text)
        self.assertEqual(
            {key: reopened.json()[key] for key in ("name", "code", "parameters", "revision", "status", "project_id", "object_id")},
            {**{key: PAYLOAD[key] for key in ("name", "code")},
             "parameters": [{**parameter, "object_id": None} for parameter in PAYLOAD["parameters"]],
             "revision": 1, "status": "draft", "project_id": self.project["id"], "object_id": self.obj["id"]},
        )


    def test_second_editor_cannot_overwrite_a_newer_draft(self):
        rule = post_json_with_csrf(self.client, self.root, PAYLOAD).json()
        path = f"{self.root}/{rule['id']}"
        update = {**PAYLOAD, "name": "Primera edición", "expected_revision": 1}
        first = put_json_with_csrf(self.client, path, update)
        self.assertEqual(first.status_code, 200, first.text)
        second = put_json_with_csrf(self.client, path, {**update, "name": "Edición atrasada"})
        self.assertEqual(second.status_code, 409, second.text)
        reopened = self.client.get(path).json()
        self.assertEqual((reopened["name"], reopened["revision"]), ("Primera edición", 2))

    def test_invalid_parameter_contract_is_rejected_before_saving(self):
        for parameter in (
            {"name": "capacidad", "type": "integer", "unit": "m3_per_s", "value": 1.5},
            {"name": "capacidad", "type": "number", "unit": "unknown", "value": 10},
            {"name": "capacidad", "type": "number", "unit": "m3_per_s", "value": 90, "max": 80},
        ):
            with self.subTest(parameter=parameter):
                response = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "parameters": [parameter]})
                self.assertEqual(response.status_code, 422, response.text)

    def test_preview_is_unavailable_without_a_live_isolated_worker(self):
        rule = post_json_with_csrf(self.client, self.root, PAYLOAD).json()
        response = post_json_with_csrf(self.client, f"{self.root}/{rule['id']}/tests", {"expected_revision": 1})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"]["code"], "RULE_RUNTIME_UNAVAILABLE")

    def test_project_switch_blocks_new_tests_but_keeps_drafts_readable(self):
        rule = post_json_with_csrf(self.client, self.root, PAYLOAD).json()
        with patch.dict(os.environ, {"RULE_ENABLED_PROJECTS": ""}):
            state = self.client.get(self.root).json()
            self.assertFalse(state["enabled"])
            self.assertEqual(self.client.get(f"{self.root}/{rule['id']}").status_code, 200)
            response = post_json_with_csrf(self.client, f"{self.root}/{rule['id']}/tests", {"expected_revision": 1})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"]["code"], "RULE_PROJECT_DISABLED")

    def test_contextual_list_reopens_saved_drafts_and_reports_runtime_availability(self):
        saved = post_json_with_csrf(self.client, self.root, PAYLOAD).json()
        response = self.client.get(self.root)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["items"], [{"id": saved["id"], "name": PAYLOAD["name"], "revision": 1,
                                                  "status": "draft", "applications": []}])
        self.assertEqual(response.json()["object"]["id"], self.obj["id"])
        self.assertIsNone(response.json()["runtime"])

    def test_external_users_and_foreign_object_routes_cannot_access_code_or_jobs(self):
        rule = post_json_with_csrf(self.client, self.root, PAYLOAD).json()
        other = self.store.create_project(name=f"Otro {self.token}")
        foreign = self.root.replace(f"projects/{self.project['id']}/", f"projects/{other['id']}/")
        self.assertEqual(self.client.get(f"{foreign}/{rule['id']}").status_code, 404)
        outsider = self.store.create_user(email=f"external-{self.token}@rules.test", display_name="Externo", role="external", password_hash=hash_password("test password"))
        login_json_with_csrf(self.client, outsider["email"], "test password")
        for method, suffix, payload in [
            ("get", "", None), ("get", f"/{rule['id']}", None),
            ("post", "", PAYLOAD), ("put", f"/{rule['id']}", {**PAYLOAD, "expected_revision": 1}),
            ("post", f"/{rule['id']}/tests", {"expected_revision": 1}),
            ("get", f"/{rule['id']}/tests/missing", None),
            ("post", f"/{rule['id']}/tests/missing/cancel", {}),
        ]:
            with self.subTest(method=method, suffix=suffix):
                response = self.client.get(self.root + suffix) if method == "get" else (
                    post_json_with_csrf if method == "post" else put_json_with_csrf
                )(self.client, self.root + suffix, payload)
                # The existing external-user boundary intentionally hides internal routes.
                self.assertEqual(response.status_code, 404, response.text)
                self.assertNotIn(FORMULA, response.text)

    def test_unit_editor_resolves_the_saved_unit_to_its_stable_rule_context(self):
        scenario = self.store.create_scenario(project_id=self.project["id"], name="Caso hidráulico")
        diagram = self.store.get_or_create_hydraulic_diagram(scenario["id"])
        self.store.save_hydraulic_diagram(scenario_id=scenario["id"], revision=diagram["revision"], nodes=[{
            "technical_key": "plant", "display_name": "Central", "component_type": "plant", "x": 0, "y": 0,
            "units": [{"technical_key": "unit", "display_name": "Unidad", "is_active": True}],
        }])
        path = f"/api/scenarios/{scenario['id']}/hydraulic-plants/plant/units/unit/rule-context"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        target = response.json()
        self.assertEqual(target["project_id"], self.project["id"])
        self.assertEqual(self.client.get(f"/api/projects/{target['project_id']}/linkable-objects/{target['object_id']}/rules").status_code, 200)
        self.assertEqual(self.client.get(path.replace("units/unit/", "units/missing/")).status_code, 404)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_preview_roundtrip_runs_outside_http_and_returns_frozen_hashes(self):
        from app.rule_runtime import OCIExecutor
        from app.rule_worker import RuleWorker
        with RuleWorker(self.store, OCIExecutor.from_env()):
            rule = post_json_with_csrf(self.client, self.root, PAYLOAD).json()
            started = post_json_with_csrf(self.client, f"{self.root}/{rule['id']}/tests", {"expected_revision": 1})
            self.assertEqual(started.status_code, 202, started.text)
            self.assertEqual(started.json()["runtime"]["sdk"], "reg-012.1")
            self.assertIn("sha256:", started.json()["runtime"]["image"])
            path = f"{self.root}/{rule['id']}/tests/{started.json()['id']}"
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                job = self.client.get(path).json()
                if job["status"] not in {"queued", "running"}:
                    break
                time.sleep(0.05)
            self.assertEqual(job["status"], "succeeded", job)
            self.assertEqual(job["result"]["output"], {"value": 60.0, "unit": "m3_per_s"})
            self.assertEqual(job["code_hash"], rule["code_hash"])
            self.assertEqual(len(job["context_hash"]), 64)
            self.assertEqual(job["draft_revision"], 1)
            self.assertFalse(job["applied"])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_user_can_cancel_loop_while_http_remains_responsive(self):
        from app.rule_runtime import OCIExecutor
        from app.rule_worker import RuleWorker
        with RuleWorker(self.store, OCIExecutor.from_env()):
            rule = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": "def construir(ctx):\n    while True:\n        pass\n"}).json()
            job = post_json_with_csrf(self.client, f"{self.root}/{rule['id']}/tests", {"expected_revision": 1}).json()
            path = f"{self.root}/{rule['id']}/tests/{job['id']}"
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and self.client.get(path).json()["status"] == "queued":
                time.sleep(0.05)
            self.assertEqual(self.client.get(f"{self.root}/{rule['id']}").status_code, 200)
            cancelled = post_json_with_csrf(self.client, path + "/cancel")
            self.assertEqual(cancelled.status_code, 200, cancelled.text)
            while time.monotonic() < deadline:
                result = self.client.get(path).json()
                if result["status"] == "cancelled":
                    break
                time.sleep(0.05)
            self.assertEqual(result["status"], "cancelled", result)
            self.assertEqual(OCIExecutor.from_env().control("ps", "-aq", "--filter", f"name=^/component-rule-{job['id']}$"), "")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_worker_restart_marks_interrupted_jobs_and_cleans_orphan_container(self):
        from app.rule_runtime import OCIExecutor
        from app.rule_worker import RuleWorker
        runtime = OCIExecutor.from_env()
        process = subprocess.Popen([sys.executable, "-m", "app.rule_worker"],
            env={**os.environ, "DATABASE_URL": self.store.database_url},
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 20
            while self.client.get(self.root).json()["runtime"] is None:
                if process.poll() is not None or time.monotonic() > deadline:
                    self.fail("Worker did not become ready")
                time.sleep(0.1)
            rule = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": "def construir(ctx):\n    while True: pass"}).json()
            job = post_json_with_csrf(self.client, f"{self.root}/{rule['id']}/tests", {"expected_revision": 1}).json()
            while not runtime.control("ps", "-q", "--filter", f"name=^/component-rule-{job['id']}$"):
                if time.monotonic() > deadline:
                    self.fail("Sandbox did not start")
                time.sleep(0.05)
            process.kill()
            process.wait(timeout=10)
            # The lease expiry is a public liveness contract (10 seconds).
            time.sleep(10.2)
            with RuleWorker(self.store, runtime):
                recovered = self.client.get(f"{self.root}/{rule['id']}/tests/{job['id']}").json()
                self.assertEqual(recovered["status"], "failed", recovered)
                self.assertEqual(recovered["result"]["error"]["code"], "RULE_INTERRUPTED")
                self.assertEqual(runtime.control("ps", "-aq", "--filter", f"name=^/component-rule-{job['id']}$"), "")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stderr.close()

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_queue_limits_each_user_and_expires_waiting_jobs(self):
        from app.rule_runtime import OCIExecutor
        from app.rule_worker import RuleWorker
        with RuleWorker(self.store, OCIExecutor.from_env(), queue_timeout=0.2):
            rule = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": "def construir(ctx):\n    while True: pass"}).json()
            path = f"{self.root}/{rule['id']}/tests"
            first = post_json_with_csrf(self.client, path, {"expected_revision": 1})
            self.assertEqual(first.status_code, 202, first.text)
            self.assertEqual(post_json_with_csrf(self.client, path, {"expected_revision": 1}).status_code, 429)
            for index in (2, 3):
                user = self.store.create_user(email=f"queue-{index}-{self.token}@rules.test", display_name="Analista", role="analyst", password_hash=hash_password("test password"))
                login_json_with_csrf(self.client, user["email"], "test password")
                response = post_json_with_csrf(self.client, path, {"expected_revision": 1})
                self.assertEqual(response.status_code, 202, response.text)
                job = response.json()
                if index == 2:
                    deadline = time.monotonic() + 3
                    while self.client.get(f"{path}/{job['id']}").json()["status"] == "queued" and time.monotonic() < deadline:
                        time.sleep(0.02)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                last = self.client.get(f"{path}/{job['id']}").json()
                if last["status"] == "failed":
                    break
                time.sleep(0.05)
            self.assertEqual(last["status"], "failed", last)
            self.assertEqual(last["result"]["error"]["code"], "RULE_QUEUE_TIMEOUT")

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_editing_a_draft_does_not_change_its_sealed_test_revision(self):
        from app.rule_runtime import OCIExecutor
        from app.rule_worker import RuleWorker
        with RuleWorker(self.store, OCIExecutor.from_env()):
            rule = post_json_with_csrf(self.client, self.root, PAYLOAD).json()
            path = f"{self.root}/{rule['id']}"
            job = post_json_with_csrf(self.client, path + "/tests", {"expected_revision": 1}).json()
            updated = put_json_with_csrf(self.client, path, {**PAYLOAD, "code": "def construir(ctx):\n    return ctx.parametros.capacidad", "expected_revision": 1})
            self.assertEqual(updated.status_code, 200, updated.text)
            revision = self.client.get(f"{path}/revisions/{job['id']}")
            self.assertEqual(revision.status_code, 200, revision.text)
            self.assertEqual(revision.json()["code"], FORMULA)
            self.assertEqual(revision.json()["status"], "sealed_preview")
            self.assertEqual(revision.json()["draft_revision"], 1)
            self.assertEqual(post_json_with_csrf(self.client, path + "/tests", {"expected_revision": 1}).status_code, 409)


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL URL required")
class PostgresRuleApiTests(RuleApiTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
