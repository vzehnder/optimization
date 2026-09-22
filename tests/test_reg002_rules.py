"""REG-002 behavior at authenticated HTTP, with isolated persistence and OCI."""
import os
import time
import tempfile
import uuid
import unittest

from tests import test_reg001_rules as baseline
from tests.test_reg001_rules import PAYLOAD
from tests.auth_test_helpers import post_json_with_csrf, put_json_with_csrf
from tests.test_reg002_runtime import CODE, PARAMETERS
from tests.test_hydro_diagram_acceptance import complete_v3_nodes
from tests.test_ts7_003_linkable_object_register import HydraulicFixture
from tests.test_ts7_009_run_materialization import RecordingRunQueue


class EngineBoundary:
    """A controllable external validation boundary; Julia has its own real suite."""
    def __init__(self):
        self.after_validation = None
        self.capabilities = ["affine_flow.v1"]

    def validate_text(self, text):
        from app.validation import ValidationResult
        if self.after_validation:
            self.after_validation()
        return ValidationResult(ok=True, phase="julia", message="Validated", payload={"status": "ok", "component_rule_versions": self.capabilities})


class RuleApplicationApiTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"
    def setUp(self):
        from app.persistence import AnalystStore
        from app.auth import hash_password
        from app.main import create_app
        from fastapi.testclient import TestClient
        from tests.auth_test_helpers import login_json_with_csrf
        self.temporary = tempfile.TemporaryDirectory(prefix="reg002-")
        self.store = AnalystStore(self.database_url)
        self.token = uuid.uuid4().hex
        self.project = self.store.create_project(name=f"REG-002 {self.token}")
        fixture = HydraulicFixture(self.store, self.project["id"], prefix=self.token)
        self.obj = self.store.register_linkable_object(project_id=self.project["id"], object_kind="hydraulic_unit", subtype_id=fixture.ids["hydraulic_unit"])
        self.user = self.store.create_user(email=f"{self.token}@rules.test", display_name="Analista", role="analyst", password_hash=hash_password("test password"))
        self.engine = EngineBoundary()
        self.client = TestClient(create_app(store=self.store, auth_enabled=True, validation_service=self.engine, run_queue=RecordingRunQueue(), artifact_root=self.temporary.name))
        self.client.__enter__()
        login_json_with_csrf(self.client, self.user["email"], "test password")
        self.root = f"/api/projects/{self.project['id']}/linkable-objects/{self.obj['id']}/rules"

    tearDown = baseline.RuleApiTests.tearDown

    def hydraulic_scope(self):
        scenario = self.store.create_scenario(project_id=self.project["id"], name="Cuatro períodos")
        diagram = self.store.get_or_create_hydraulic_diagram(scenario["id"])
        nodes = complete_v3_nodes()
        nodes[0]["natural_inflow_series"]["points"] = [
            {"timestamp": f"2026-01-01T0{t}:00:00", "duration_hours": 1, "value_m3s": 0} for t in range(4)]
        self.store.save_hydraulic_diagram(scenario_id=scenario["id"], revision=diagram["revision"], nodes=nodes,
                                        reaches=[{"technical_key": "reach", "display_name": "Tramo", "from_node_key": "reservoir_alpha", "to_node_key": "junction_in", "reach_type": "river"}])
        target = self.client.get(f"/api/scenarios/{scenario['id']}/hydraulic-plants/plant_laja/units/unit_1/rule-context").json()
        self.root = f"/api/projects/{self.project['id']}/linkable-objects/{target['object_id']}/rules"
        variant = self.client.get(f"/api/scenarios/{scenario['id']}/case/default-variant").json()["variant"]
        return {"scenario_id": scenario["id"], "variant_id": variant["id"], "range_start": "2026-01-01T00:00:00", "range_end": "2026-01-01T04:00:00"}

    def compile_published(self, scope, code=CODE):
        rule = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": code, "parameters": PARAMETERS}).json()
        path = f"{self.root}/{rule['id']}"
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        response = post_json_with_csrf(self.client, path + "/tests", {"expected_revision": 1, "publication_id": publication["id"], "scope": scope})
        self.assertEqual(response.status_code, 202, response.text)
        job = response.json()
        deadline = time.monotonic() + 20
        while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.05)
            job = self.client.get(f"{path}/tests/{job['id']}").json()
        self.assertEqual(job["status"], "succeeded", job)
        return path, publication, job

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_preview_applies_a_published_revision_to_one_variant_and_deactivation_keeps_history(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydraulic_scope()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, publication, job = self.compile_published(scope)
        self.assertEqual(len(job["result"]["ir"]["rows"]), 4)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Máximo operativo", "accept_empty": False})
        self.assertEqual(applied.status_code, 201, applied.text)
        app = applied.json()
        self.assertEqual((app["publication_id"], app["variant_id"], app["status"]), (publication["id"], scope["variant_id"], "active"))
        deactivated = post_json_with_csrf(self.client, f"{path}/applications/{app['id']}/deactivate", {"expected_revision": app["revision"], "reason": "Recuperar base"})
        self.assertEqual(deactivated.status_code, 200, deactivated.text)
        history = self.client.get(path + "/applications").json()["items"]
        self.assertEqual((history[0]["status"], history[0]["events"][-1]["reason"], history[0]["events"][-1]["actor"]), ("inactive", "Recuperar base", self.user["id"]))

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_variant_run_freezes_rules_and_retries_the_same_request_without_recompiling(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        from tests.auth_test_helpers import csrf_headers
        scope = self.hydraulic_scope()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, publication, job = self.compile_published(scope)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Máximo 5 m3/s"})
        self.assertEqual(applied.status_code, 201, applied.text)
        run_path = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
        body = {key: scope[key] for key in ("range_start", "range_end")}
        headers = {**csrf_headers(self.client), "X-Request-Id": "reg002-idempotent"}
        first = self.client.post(run_path, json=body, headers=headers)
        self.assertEqual(first.status_code, 201, first.text)
        second = self.client.post(run_path, json=body, headers=headers)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()["id"], first.json()["id"])
        version = self.client.get(f"/api/scenario-versions/{first.json()['scenario_version_id']}").json()["scenario_version"]
        block = version["system_case_json"]["component_rules"]
        self.assertEqual(len(block["rows"]), 4)
        self.assertEqual(block["applications"][0]["publication_id"], publication["id"])
        self.assertEqual(block["applications"][0]["parameters"][0]["value"], 5)
        self.assertEqual(block["applications"][0]["ir_hash"], applied.json()["ir_hash"])
        sources = version["generation_metadata"]["series_bindings"]
        self.assertEqual(sources[0]["signal_key"], "natural_inflow_m3s")
        self.assertGreater(sources[0]["time_series_set_id"], 0)
        self.assertEqual(len(sources[0]["content_hash"]), 64)
        deactivated = post_json_with_csrf(self.client, f"{path}/applications/{applied.json()['id']}/deactivate", {"expected_revision": 1, "reason": "Finalizar prueba"})
        self.assertEqual(deactivated.status_code, 200, deactivated.text)
        replay = self.client.post(run_path, json=body, headers=headers)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json()["id"], first.json()["id"])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_empty_constraints_require_explicit_acceptance(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydraulic_scope()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, _, job = self.compile_published(scope, code="def construir(ctx):\n    pass\n")
        self.assertEqual(job["result"]["ir"]["rows"], [])
        refused = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Sin condiciones"})
        self.assertEqual(refused.status_code, 422, refused.text)
        accepted = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Acepto sin condiciones", "accept_empty": True})
        self.assertEqual(accepted.status_code, 201, accepted.text)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_legacy_series_variant_keeps_sources_and_rejects_an_old_engine_atomically(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        from app.time_series_catalog import CatalogImportRequest, CatalogSignalMappingRequest, prepare_time_series_catalog_import
        scope = self.hydraulic_scope()
        inflow = self.store.import_time_series_catalog_set(
            scenario_id=scope["scenario_id"], source={"id": "inflow", "original_filename": "inflow.csv", "media_type": "text/csv", "checksum": "sha256:fixture"},
            prepared_import=prepare_time_series_catalog_import(
                rows=[{"timestamp": f"2026-01-01T0{t}:00:00", "hours": "1", "flow": "0"} for t in range(4)],
                request=CatalogImportRequest(set_name="Aporte", version_label="v1", data_kind="real", timezone="UTC", timestamp_column="timestamp", duration_hours_column="hours",
                    signal_mappings=[CatalogSignalMappingRequest(source_column="flow", signal_key="natural_inflow_m3s")]),
            ),
        )
        self.store.upsert_case_time_series_binding(case_input_variant_id=scope["variant_id"], signal_key="natural_inflow_m3s", entity_type="hydraulic_node", entity_id="reservoir_alpha", time_series_set_id=inflow["id"])
        scope.update(range_start=inflow["horizon"]["start"], range_end=inflow["horizon"]["end"])
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, _, job = self.compile_published(scope)
        response = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Fuente legada"})
        self.assertEqual(response.status_code, 201, response.text)
        run_path = f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run"
        body = {key: scope[key] for key in ("range_start", "range_end")}
        self.engine.capabilities = []
        refused = post_json_with_csrf(self.client, run_path, body)
        self.assertEqual(refused.status_code, 409, refused.text)
        self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/versions").json()["versions"], [])
        self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/runs").json()["runs"], [])
        self.engine.capabilities = ["affine_flow.v1"]
        accepted = post_json_with_csrf(self.client, run_path, body)
        self.assertEqual(accepted.status_code, 201, accepted.text)
        version = self.client.get(f"/api/scenario-versions/{accepted.json()['scenario_version_id']}").json()["scenario_version"]
        self.assertEqual(version["generation_metadata"]["series_bindings"][0]["time_series_set_id"], inflow["id"])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_unruled_historical_version_cannot_bypass_an_active_application(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydraulic_scope()
        version = self.store.create_scenario_version(scenario_id=scope["scenario_id"], system_case_json=self.store.generate_hydraulic_v3_preview(scope["scenario_id"]), validation_payload={"status": "ok"})
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, _, job = self.compile_published(scope)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Respetar máximo"})
        self.assertEqual(applied.status_code, 201, applied.text)
        response = post_json_with_csrf(self.client, f"/api/scenario-versions/{version['id']}/runs")
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("reglas", response.text.lower())

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_new_publication_during_compilation_requires_an_explicit_new_preview(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydraulic_scope()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, _, job = self.compile_published(scope)
        updated = put_json_with_csrf(self.client, path, {**PAYLOAD, "code": CODE + "\n# revisión nueva", "parameters": PARAMETERS, "expected_revision": 1})
        self.assertEqual(updated.status_code, 200, updated.text)
        published = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 2})
        self.assertEqual(published.status_code, 201, published.text)
        response = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Aplicar prueba anterior"})
        self.assertEqual(response.status_code, 409, response.text)

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_disabling_rules_during_materialization_leaves_no_version_or_run(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        from unittest.mock import patch
        scope = self.hydraulic_scope()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, _, job = self.compile_published(scope)
        applied = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Límite"})
        self.assertEqual(applied.status_code, 201, applied.text)
        self.engine.after_validation = lambda: os.environ.__setitem__("RULE_ENABLED_PROJECTS", "")
        with patch.dict(os.environ, {"RULE_ENABLED_PROJECTS": "*"}):
            response = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run", {"range_start": scope["range_start"], "range_end": scope["range_end"]})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/versions").json()["versions"], [])
        self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/runs").json()["runs"], [])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_deactivation_during_validation_cancels_the_entire_materialization(self):
        from fastapi.testclient import TestClient
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        scope = self.hydraulic_scope()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, _, job = self.compile_published(scope)
        application = post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Operación"}).json()
        other = TestClient(self.client.app)
        other.cookies.update(self.client.cookies)
        def concurrent_edit():
            response = post_json_with_csrf(other, f"{path}/applications/{application['id']}/deactivate", {"expected_revision": 1, "reason": "Cambio concurrente"})
            self.assertEqual(response.status_code, 200, response.text)
        self.engine.after_validation = concurrent_edit
        response = post_json_with_csrf(self.client, f"/api/scenarios/{scope['scenario_id']}/case/variants/{scope['variant_id']}/run", {"range_start": scope["range_start"], "range_end": scope["range_end"]})
        other.close()
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/versions").json()["versions"], [])
        self.assertEqual(self.client.get(f"/api/scenarios/{scope['scenario_id']}/runs").json()["runs"], [])

    @unittest.skipUnless(os.environ.get("RULE_RUNTIME_IMAGE"), "pinned OCI image required")
    def test_scheduled_execution_reports_that_active_rules_are_not_supported(self):
        from app.rule_worker import RuleWorker
        from app.rule_runtime import OCIExecutor
        from app.auth import hash_password
        from tests.auth_test_helpers import login_json_with_csrf
        scope = self.hydraulic_scope()
        with RuleWorker(self.store, OCIExecutor.from_env()):
            path, _, job = self.compile_published(scope)
        self.assertEqual(post_json_with_csrf(self.client, path + "/applications", {"job_id": job["id"], "reason": "Límite"}).status_code, 201)
        admin = self.store.create_user(email=f"admin-{self.token}@rules.test", display_name="Admin", role="admin", password_hash=hash_password("test password"))
        login_json_with_csrf(self.client, admin["email"], "test password")
        schedule = post_json_with_csrf(self.client, "/api/admin/schedules", {"scenario_id": scope["scenario_id"], "case_input_variant_id": scope["variant_id"], "display_name": "Con reglas", "range_start": scope["range_start"] + "+00:00", "range_end": scope["range_end"] + "+00:00", "cadence": "daily", "next_run_at": "2026-09-21T00:00:00+00:00"})
        self.assertEqual(schedule.status_code, 201, schedule.text)
        response = post_json_with_csrf(self.client, "/api/admin/schedules/run-due", {"now": "2026-09-21T01:00:00+00:00"})
        self.assertEqual(response.status_code, 200, response.text)
        tick = next(t for t in response.json()["ticks"] if t["schedule_id"] == schedule.json()["schedule"]["id"])
        self.assertEqual(tick["status"], "failed")
        self.assertIn("reglas", tick["error_message"].lower())

    def test_publishing_pins_immutable_code_without_following_draft_edits(self):
        rule = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": CODE, "parameters": PARAMETERS}).json()
        path = f"{self.root}/{rule['id']}"
        published = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1})
        self.assertEqual(published.status_code, 201, published.text)
        revision = published.json()
        self.assertEqual((revision["status"], revision["code"], revision["parameters"][0]["value"]), ("published", CODE, 5))
        edited = put_json_with_csrf(self.client, path, {**PAYLOAD, "code": CODE + "\n# siguiente", "expected_revision": 1})
        self.assertEqual(edited.status_code, 200, edited.text)
        historical = self.client.get(f"{path}/publications/{revision['id']}")
        self.assertEqual(historical.json()["code"], CODE)
        self.assertEqual(post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).status_code, 409)

    def test_preview_rejects_an_invalid_range_as_a_contract_error(self):
        scope = self.hydraulic_scope()
        rule = post_json_with_csrf(self.client, self.root, {**PAYLOAD, "code": CODE, "parameters": PARAMETERS}).json()
        path = f"{self.root}/{rule['id']}"
        publication = post_json_with_csrf(self.client, path + "/publications", {"expected_revision": 1}).json()
        response = post_json_with_csrf(self.client, path + "/tests", {"expected_revision": 1, "publication_id": publication["id"], "scope": {**scope, "range_start": "fecha inválida"}})
        self.assertEqual(response.status_code, 422, response.text)


@unittest.skipUnless(os.environ.get("POSTGRES_TEST_DATABASE_URL"), "isolated PostgreSQL URL required")
class PostgresRuleApplicationApiTests(RuleApplicationApiTests):
    database_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
