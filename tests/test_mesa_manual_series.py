"""MESA-012: manual support and explicit bindings through authenticated HTTP (S2)."""

import tempfile
import unittest
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf
from tests.mesa_execution_fixture import seed_executable_mesa
from tests.mesa_hydraulic_fixture import seed_hydraulic_mesa
from tests.test_ts3_case_variant_api import RecordingRunQueue, StubValidationService


class MesaManualSeriesApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database_url = f"sqlite:///{Path(self.temp.name) / 'mesa.sqlite3'}"
        self.store = AnalystStore(self.database_url)
        self.addCleanup(self.store.close)
        self.store.create_user(email="mesa@example.local", display_name="Analista", role="analyst",
                               password_hash=hash_password("mesa test pass"))
        self.fixture = seed_executable_mesa(self.store)
        self.client = TestClient(create_app(store=self.store, auth_enabled=True,
            run_queue=RecordingRunQueue(), validation_service=StubValidationService(), artifact_root=self.temp.name))
        self.addCleanup(self.client.close)
        login_json_with_csrf(self.client, "mesa@example.local", "mesa test pass")
        self.path = f"/api/scenarios/{self.fixture['scenario']['id']}/mesa"
        self.params = {"case_id": self.fixture["case"]["id"], "variant_id": self.fixture["variant"]["id"]}
        self.execution = {**self.params, "range_start": "2026-10-20T00:00:00", "range_end": "2026-10-20T02:00:00",
                          "timezone": "America/Santiago", "resolution_hours": 1}

    def post(self, suffix, document, status=201):
        response = post_json_with_csrf(self.client, self.path + suffix, document)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def create_payload(self):
        return {**self.params, "object_id": self.fixture["object"]["id"], "name": "Demanda de apoyo",
            "binding_role_key": "load_demand", "semantic_type_key": "load_demand", "unit_key": "mw",
            "timezone": "America/Santiago", "resolution_seconds": 3600,
            "points": [{"start": "2026-10-20T00:00:00-03:00", "end": "2026-10-20T01:00:00-03:00", "value": 20},
                       {"start": "2026-10-20T01:00:00-03:00", "end": "2026-10-20T02:00:00-03:00", "value": 30}],
            "reason": "Proyección manual de demanda", "confirm": True}

    def detail(self, signal_id):
        response = self.client.get(f"{self.path}/manual-series/{signal_id}", params=self.params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_explicit_binding_uses_the_published_revision_and_keeps_existing_snapshots(self):
        before = self.post("/execution/preview", self.execution, 200)
        run = self.post("/execution/runs", {**self.execution,
            "expected_preparation_hash": before["preparation_hash"], "idempotency_key": "before-binding"})
        snapshot_path = f"/api/scenario-versions/{run['scenario_version_id']}"
        frozen = self.client.get(snapshot_path).json()["scenario_version"]
        created = self.post("/manual-series", self.create_payload())
        detail = self.detail(created["signal_id"])
        self.assertEqual([d["binding_role_key"] for d in detail["destinations"]], ["load_demand"])
        self.assertEqual(detail["destinations"][0]["object_id"], self.fixture["object"]["id"])
        bound = self.post(f"/manual-series/{created['signal_id']}/binding", {**self.params,
            "expected": detail["expected"], "object_id": self.fixture["object"]["id"],
            "binding_role_key": "load_demand", "confirm": True, "reason": "Usar la proyección en esta variante"})
        self.assertEqual(bound["preparation_status"], "pending_validation")
        self.post("/execution/runs", {**self.execution, "expected_preparation_hash": before["preparation_hash"],
            "idempotency_key": "obsolete-preparation"}, 409)
        after = self.post("/execution/preview", self.execution, 200)
        self.assertNotEqual(after["preparation_hash"], before["preparation_hash"])
        self.assertIn(created["revision_id"], [b["set_revision_id"] for b in after["series_bindings"]])
        launched = self.post("/execution/runs", {**self.execution,
            "expected_preparation_hash": after["preparation_hash"], "idempotency_key": "after-binding"})
        snapshot = self.client.get(f"/api/scenario-versions/{launched['scenario_version_id']}").json()["scenario_version"]
        self.assertEqual([p["load_demand_mw"]["load_north"] for p in snapshot["system_case_json"]["time_series"]], [20, 30])
        self.assertEqual(self.client.get(snapshot_path).json()["scenario_version"], frozen)

    def test_manual_support_is_canonical_and_reloadable_without_changing_executable_inputs(self):
        before = self.post("/execution/preview", self.execution, 200)
        created = self.post("/manual-series", self.create_payload())
        for _ in range(2):
            response = self.client.get(self.path, params=self.params)
            self.assertEqual(response.status_code, 200, response.text)
            manual, = [c for c in response.json()["components"] if c["entity_type"] == "manual_series"]
            self.assertEqual(manual["name"], "Demanda de apoyo")
            series = manual["series"]
            self.assertEqual(series["signal_id"], created["signal_id"])
            self.assertEqual(series["revision_id"], created["revision_id"])
            self.assertEqual(series["revision_number"], 1)
            self.assertEqual(series["role"], "support")
            self.assertEqual(series["unit"], "MW")
            self.assertEqual(series["source"], "manual")
            self.assertEqual([p["value"] for p in series["points"]], [20, 30])
            self.assertIn("No participa", series["message"])
            self.assertEqual(manual["additional_series"], [])
        root = f"/api/projects/{self.fixture['project']['id']}/linkable-objects/{self.fixture['object']['id']}/time-series/object-series/{created['signal_id']}"
        canonical = self.client.get(root)
        self.assertEqual(canonical.status_code, 200, canonical.text)
        self.assertEqual(canonical.json()["object_series"]["source_expectation"]["kind"], "manual")
        after = self.post("/execution/preview", self.execution, 200)
        self.assertEqual(after["preparation_hash"], before["preparation_hash"])
        launched = self.post("/execution/runs", {**self.execution,
            "expected_preparation_hash": before["preparation_hash"], "idempotency_key": "support-only"})
        snapshot = self.client.get(f"/api/scenario-versions/{launched['scenario_version_id']}").json()["scenario_version"]
        self.assertEqual([p["load_demand_mw"]["load_north"] for p in snapshot["system_case_json"]["time_series"]], [10, 12])

    def test_manual_edits_keep_identity_and_require_rebinding_without_overwriting_another_editor(self):
        created = self.post("/manual-series", self.create_payload())
        signal_id = created["signal_id"]
        detail = self.detail(signal_id)
        self.post(f"/manual-series/{signal_id}/binding", {**self.params, "expected": detail["expected"],
            "object_id": detail["object_id"], "binding_role_key": "load_demand", "confirm": True, "reason": "Usar apoyo"})
        bound = self.detail(signal_id)
        before = self.post("/execution/preview", self.execution, 200)
        run = self.post("/execution/runs", {**self.execution, "expected_preparation_hash": before["preparation_hash"],
            "idempotency_key": "before-manual-edit"})
        snapshot_path = f"/api/scenario-versions/{run['scenario_version_id']}"
        frozen = self.client.get(snapshot_path).json()["scenario_version"]
        edit = {**self.params, "expected": bound["expected"], "unit": "MW",
            "points": [{**p, "value": value} for p, value in zip(bound["series"]["points"], [22, 33])],
            "confirm": True, "reason": "Actualizar proyección"}
        saved = self.post(f"/manual-series/{signal_id}/revisions", edit)
        for _ in range(2):
            current = self.detail(signal_id)
            self.assertEqual(current["series"]["signal_id"], signal_id)
            self.assertEqual(current["series"]["revision_id"], saved["revision_id"])
            self.assertEqual(current["series"]["revision_number"], 2)
            self.assertEqual([p["value"] for p in current["series"]["points"]], [22, 33])
            self.assertEqual(current["series"]["binding_state"], "stale")
        self.post(f"/manual-series/{signal_id}/revisions", edit, 409)
        self.post("/execution/runs", {**self.execution, "expected_preparation_hash": before["preparation_hash"],
            "idempotency_key": "outdated-manual"}, 409)
        self.post(f"/manual-series/{signal_id}/binding", {**self.params, "expected": current["expected"],
            "object_id": current["object_id"], "binding_role_key": "load_demand", "confirm": True, "reason": "Revalidar revisión"})
        self.assertEqual(self.detail(signal_id)["series"]["binding_state"], "valid_current")
        prepared = self.post("/execution/preview", self.execution, 200)
        self.assertIn(saved["revision_id"], [b["set_revision_id"] for b in prepared["series_bindings"]])
        self.assertEqual(self.client.get(snapshot_path).json()["scenario_version"], frozen)

    def test_hydraulic_support_does_not_offer_a_variant_binding_as_a_change_to_the_promoted_source(self):
        self.fixture = seed_hydraulic_mesa(self.store)
        self.path = f"/api/scenarios/{self.fixture['scenario']['id']}/mesa"
        self.params = {"case_id": self.fixture["case"]["id"], "variant_id": self.fixture["variant"]["id"]}
        inventory = self.client.get(self.path, params=self.params).json()
        reservoir = next(c for c in inventory["components"] if c["entity_id"] == "reservoir")
        self.fixture["object"] = {"id": reservoir["linkable_object_id"]}
        original = reservoir["series"]
        created = self.post("/manual-series", {**self.create_payload(), "name": "Aporte de apoyo",
            "binding_role_key": "natural_inflow", "semantic_type_key": "natural_inflow", "unit_key": "m3_per_s"})
        detail = self.detail(created["signal_id"])
        self.assertEqual(detail["series"]["unit"], "m3/s")
        self.assertEqual(detail["destinations"], [])
        self.assertIn("versión promovida", detail["scope_message"])
        self.post(f"/manual-series/{created['signal_id']}/binding", {**self.params, "expected": detail["expected"],
            "object_id": detail["object_id"], "binding_role_key": "natural_inflow", "confirm": True, "reason": "No debe modificar la fuente"}, 400)
        after = self.client.get(self.path, params=self.params).json()
        self.assertEqual(next(c["series"] for c in after["components"] if c["entity_id"] == "reservoir"), original)

    def test_invalid_values_periods_and_units_leave_no_partial_definition(self):
        root = f"/api/projects/{self.fixture['project']['id']}/linkable-objects/{self.fixture['object']['id']}/time-series"
        before = self.client.get(root).json()["summary"]
        payload = self.create_payload()
        cases = [
            {"unit_key": "m3_per_s"}, {"binding_role_key": "natural_inflow"},
            {"points": [{**payload["points"][0], "value": -1}, payload["points"][1]]},
            {"points": [{**payload["points"][0], "value": True}, payload["points"][1]]},
            {"points": [{**payload["points"][0], "end": "2026-10-20T00:30:00-03:00"}, payload["points"][1]]},
            {"points": [{**payload["points"][0], "start": "2026-10-20T00:00:00"}, payload["points"][1]]},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                self.post("/manual-series", {**payload, **changes}, 422)
                self.assertEqual(self.client.get(root).json()["summary"], before)

    def test_invalid_destination_and_obsolete_binding_cannot_replace_the_input(self):
        created = self.post("/manual-series", self.create_payload())
        detail = self.detail(created["signal_id"])
        binding = {**self.params, "expected": detail["expected"], "object_id": detail["object_id"],
                   "binding_role_key": "load_demand", "confirm": True, "reason": "Usar proyección"}
        mesa = self.client.get(self.path, params=self.params).json()
        solar = next(c for c in mesa["components"] if c["entity_id"] == "solar_north")
        for changes in ({"object_id": solar["linkable_object_id"]}, {"binding_role_key": "bess_discharge_power"}, {"confirm": False}):
            self.post(f"/manual-series/{created['signal_id']}/binding", {**binding, **changes}, 400)
        self.post(f"/manual-series/{created['signal_id']}/binding", binding)
        self.post(f"/manual-series/{created['signal_id']}/binding", binding, 409)
        self.assertEqual(self.detail(created["signal_id"])["series"]["binding_state"], "valid_current")

    def test_foreign_context_external_access_and_missing_csrf_are_refused(self):
        created = self.post("/manual-series", self.create_payload())
        other = seed_executable_mesa(self.store, name="Otro caso")
        for changes in ({"case_id": other["case"]["id"]}, {"variant_id": other["variant"]["id"]}, {"object_id": other["object"]["id"]}):
            self.post("/manual-series", {**self.create_payload(), **changes}, 404)
        other_path = f"/api/scenarios/{other['scenario']['id']}/mesa/manual-series/{created['signal_id']}"
        self.assertEqual(self.client.get(other_path, params={"case_id": other["case"]["id"], "variant_id": other["variant"]["id"]}).status_code, 404)
        self.assertEqual(self.client.post(self.path + "/manual-series", json=self.create_payload()).status_code, 403)
        external = TestClient(self.client.app)
        self.addCleanup(external.close)
        self.assertEqual(external.get(self.path + "/manual-series", params=self.params).status_code, 401)
        self.store.create_user(email="external@example.local", display_name="Externo", role="external", password_hash=hash_password("external pass"))
        login_json_with_csrf(external, "external@example.local", "external pass")
        self.assertEqual(external.get(self.path + "/manual-series", params=self.params).status_code, 404)
        self.assertEqual(post_json_with_csrf(external, self.path + "/manual-series", self.create_payload()).status_code, 404)

    def test_manual_publication_survives_restart_and_two_connections_cannot_overwrite_one_revision(self):
        created = self.post("/manual-series", self.create_payload())
        second_store = AnalystStore(self.database_url)
        self.addCleanup(second_store.close)
        second = TestClient(create_app(store=second_store, auth_enabled=True))
        self.addCleanup(second.close)
        login_json_with_csrf(second, "mesa@example.local", "mesa test pass")
        path = f"{self.path}/manual-series/{created['signal_id']}"
        recovered = second.get(path, params=self.params)
        self.assertEqual(recovered.status_code, 200, recovered.text)
        detail = recovered.json()
        self.assertEqual([p["value"] for p in detail["series"]["points"]], [20, 30])
        def edit(client, value):
            return post_json_with_csrf(client, path + "/revisions", {**self.params, "expected": detail["expected"], "unit": "MW",
                "points": [{**p, "value": value if i == 1 else 20} for i, p in enumerate(detail["series"]["points"])],
                "confirm": True, "reason": "Corrección concurrente"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(edit, client, value) for client, value in ((self.client, 35), (second, 40))]
            responses = [f.result() for f in futures]
        self.assertEqual(sorted(r.status_code for r in responses), [201, 409], [r.text for r in responses])
        current = second.get(path, params=self.params).json()
        self.assertEqual(current["series"]["revision_number"], 2)
        self.assertEqual([p["value"] for p in current["series"]["points"]], [20, 35 if responses[0].status_code == 201 else 40])

    def test_manual_inflow_can_be_bound_and_prepared_for_simple_hydro_v2(self):
        draft = self.store.get_scenario_draft(self.fixture["scenario"]["id"])["document"]
        example = json.loads((Path(__file__).parents[1] / "data/cases/linear_hydro_system/system_case.json").read_text())
        draft["assets"].append(next(n for n in example["nodes"] if n["type"] == "hydro"))
        self.store.create_or_replace_scenario_draft(scenario_id=self.fixture["scenario"]["id"], document=draft)
        self.store.materialize_project_linkable_objects(project_id=self.fixture["project"]["id"])
        # Adding the physical asset deliberately stales existing inputs. Restore
        # the fixture's four unchanged sources before exercising the new support.
        bindings = self.store.read_case_bindings(scenario_id=self.fixture["scenario"]["id"], variant_id=self.params["variant_id"])
        setup = {"expected_bindings_revision": bindings["meta"]["bindings_revision"], "operations": [
            {"client_operation_id": str(b["binding_id"]), "action": "revalidate_current", "binding_id": b["binding_id"],
             "expected_lifecycle_revision": b["lifecycle_revision"], "reason_code": "revalidated_current"}
            for b in bindings["items"] if b["status"] == "active"]}
        preview = self.store.prevalidate_case_binding_batch(scenario_id=self.fixture["scenario"]["id"], variant_id=self.params["variant_id"],
                                                           document=setup, actor_class="internal")
        self.store.commit_case_binding_batch(scenario_id=self.fixture["scenario"]["id"], variant_id=self.params["variant_id"], document=setup,
            actor_user={"id": 1, "email": "mesa-fixture", "role": "analyst"}, actor_class="internal", request_id="hydro-setup",
            prevalidation_token=preview["prevalidation_token"], if_match=preview["commit_etag"], idempotency_key="hydro-setup", confirmed=True)
        mesa = self.client.get(self.path, params=self.params).json()
        hydro = next(c for c in mesa["components"] if c["entity_id"] == "hydro_1")
        created = self.post("/manual-series", {**self.create_payload(), "object_id": hydro["linkable_object_id"], "name": "Aporte manual",
            "binding_role_key": "hydro_inflow", "semantic_type_key": "hydro_inflow", "unit_key": "m3_per_s"})
        detail = self.detail(created["signal_id"])
        self.post(f"/manual-series/{created['signal_id']}/binding", {**self.params, "expected": detail["expected"],
            "object_id": detail["object_id"], "binding_role_key": "hydro_inflow", "confirm": True, "reason": "Usar aporte manual"})
        prepared = self.post("/execution/preview", self.execution, 200)
        run = self.post("/execution/runs", {**self.execution, "expected_preparation_hash": prepared["preparation_hash"], "idempotency_key": "hydro-manual"})
        version = self.client.get(f"/api/scenario-versions/{run['scenario_version_id']}").json()["scenario_version"]
        self.assertEqual([p["hydro_inflow_m3s"]["hydro_1"] for p in version["system_case_json"]["time_series"]], [20, 30])

    def test_an_archived_manual_source_cannot_be_edited_or_rebound(self):
        created = self.post("/manual-series", self.create_payload())
        root = f"/api/projects/{self.fixture['project']['id']}/linkable-objects/{self.fixture['object']['id']}/time-series/object-series/{created['signal_id']}"
        current = self.client.get(root)
        csrf = self.client.get("/api/auth/csrf").json()["csrf_token"]
        response = self.client.post(root + "/archive", json={"reason_code": "unused", "reason_text": "Retirar apoyo"},
                                   headers={"If-Match": current.headers["etag"], "X-CSRF-Token": csrf})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get(f"{self.path}/manual-series/{created['signal_id']}", params=self.params).status_code, 404)
        self.assertFalse(any(c["entity_type"] == "manual_series" for c in self.client.get(self.path, params=self.params).json()["components"]))

    def test_unknown_timezone_cannot_publish_a_series_that_breaks_the_case_read(self):
        self.post("/manual-series", {**self.create_payload(), "timezone": "Mars/Unknown"}, 422)
        response = self.client.get(self.path, params=self.params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(any(c["entity_type"] == "manual_series" for c in response.json()["components"]))


if __name__ == "__main__":
    unittest.main()
