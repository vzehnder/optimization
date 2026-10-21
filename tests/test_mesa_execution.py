"""MESA-007: observable execution and recovery at the authenticated HTTP seam."""

import tempfile
import unittest
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf
from tests.mesa_execution_fixture import seed_executable_mesa
from tests.mesa_hydraulic_fixture import seed_hydraulic_mesa
from tests.test_ts3_case_variant_api import RecordingRunQueue, StubValidationService


class MesaExecutionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database_url = f"sqlite:///{Path(self.temp.name) / 'mesa.sqlite3'}"
        self.store = AnalystStore(self.database_url)
        self.addCleanup(self.store.close)
        self.store.create_user(email="mesa@example.local", display_name="Analista", role="analyst",
                               password_hash=hash_password("mesa test pass"))
        self.fixture = seed_executable_mesa(self.store)
        self.queue = RecordingRunQueue()
        self.client = self.connect(self.store)
        self.path = f"/api/scenarios/{self.fixture['scenario']['id']}/mesa/execution"
        self.params = {"case_id": self.fixture["case"]["id"], "variant_id": self.fixture["variant"]["id"]}
        self.payload = {**self.params, "range_start": "2026-10-20T00:00:00", "range_end": "2026-10-20T02:00:00",
                        "timezone": "America/Santiago", "resolution_hours": 1}

    def connect(self, store):
        client = TestClient(create_app(store=store, auth_enabled=True, run_queue=self.queue,
                                      validation_service=StubValidationService(), artifact_root=self.temp.name))
        self.addCleanup(client.close)
        login_json_with_csrf(client, "mesa@example.local", "mesa test pass")
        return client

    def preview(self):
        response = post_json_with_csrf(self.client, self.path + "/preview", self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def launch(self, prepared, key="mesa-request-1", **changes):
        return post_json_with_csrf(self.client, self.path + "/runs", {
            **self.payload, "expected_preparation_hash": prepared["preparation_hash"],
            "idempotency_key": key, **changes,
        })

    def test_prepared_electrical_run_freezes_inputs_and_is_recovered_from_another_connection(self):
        prepared = self.preview()
        self.assertEqual(prepared["period_count"], 2)
        launched = self.launch(prepared)
        self.assertEqual(launched.status_code, 201, launched.text)
        run = launched.json()
        other_store = AnalystStore(self.database_url)
        self.addCleanup(other_store.close)
        other = self.connect(other_store)
        recovered = other.get(self.path, params=self.params)
        self.assertEqual(recovered.status_code, 200, recovered.text)
        self.assertEqual(recovered.json()["run"]["id"], run["id"])
        self.assertEqual(recovered.json()["run"]["status"], "queued")
        snapshot = other.get(f"/api/scenario-versions/{run['scenario_version_id']}").json()["scenario_version"]
        self.assertEqual([p["load_demand_mw"]["load_north"] for p in snapshot["system_case_json"]["time_series"]], [10, 12])
        self.assertEqual(snapshot["generation_metadata"]["mesa_execution"]["timezone"], "America/Santiago")
        self.assertEqual(snapshot["generation_metadata"]["input_variant"]["id"], self.params["variant_id"])
        self.assertEqual(len(snapshot["generation_metadata"]["series_bindings"]), 4)

    def test_retry_after_reconnecting_returns_the_same_run(self):
        prepared = self.preview()
        first = self.launch(prepared)
        self.assertEqual(first.status_code, 201, first.text)
        other_store = AnalystStore(self.database_url)
        self.addCleanup(other_store.close)
        self.client = self.connect(other_store)
        retry = self.launch(prepared)
        self.assertEqual(retry.status_code, 201, retry.text)
        self.assertEqual(retry.json()["id"], first.json()["id"])
        runs = self.client.get(f"/api/scenarios/{self.fixture['scenario']['id']}/runs").json()["runs"]
        self.assertEqual([run["id"] for run in runs], [first.json()["id"]])

    def edit_demand(self, value):
        path = f"{self.path.removesuffix('/execution')}/inputs/{self.fixture['object']['id']}/load_demand_mw"
        edit = self.client.get(path, params=self.params).json()
        points = [dict(p) for p in edit["series"]["points"]]
        points[1]["value"] = value
        response = post_json_with_csrf(self.client, path + "/revisions", {
            **self.params, "expected": edit["expected"], "unit": "MW", "points": points,
            "confirm": True, "reason": "Cambio antes de ejecutar",
        })
        self.assertEqual(response.status_code, 201, response.text)

    def test_changed_input_rejects_the_previously_validated_preparation(self):
        prepared = self.preview()
        self.edit_demand(15)
        rejected = self.launch(prepared)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertIn("validar", rejected.text)
        self.assertEqual(self.client.get(self.path, params=self.params).json()["run"], None)

    def test_run_requires_the_exact_preparation_fingerprint(self):
        prepared = self.preview()
        rejected = self.launch(prepared, expected_preparation_hash="0" * 64)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(self.client.get(self.path, params=self.params).json()["run"], None)

    def test_edit_then_revalidate_executes_the_saved_values(self):
        self.edit_demand(15)
        prepared = self.preview()
        launched = self.launch(prepared)
        self.assertEqual(launched.status_code, 201, launched.text)
        version = self.client.get(f"/api/scenario-versions/{launched.json()['scenario_version_id']}").json()["scenario_version"]
        self.assertEqual([p["load_demand_mw"]["load_north"] for p in version["system_case_json"]["time_series"]], [10, 15])

    def test_resolution_must_match_inputs_without_resampling(self):
        response = post_json_with_csrf(self.client, self.path + "/preview", {**self.payload, "resolution_hours": 2})
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("resolución", response.json()["detail"])

    def test_equivalent_offset_dates_preserve_the_requested_instants(self):
        self.payload.update(range_start="2026-10-20T03:00:00+00:00", range_end="2026-10-20T05:00:00+00:00")
        prepared = self.preview()
        self.assertEqual(prepared["range_start"], "2026-10-20T00:00:00-03:00")
        self.assertEqual(prepared["range_end"], "2026-10-20T02:00:00-03:00")

    def test_daylight_saving_invalid_local_hour_is_explained_before_coverage(self):
        response = post_json_with_csrf(self.client, self.path + "/preview", {
            **self.payload, "range_start": "2026-09-06T00:00:00", "range_end": "2026-09-06T02:00:00",
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("no existe", response.json()["detail"])

    def test_unknown_zone_ambiguous_hour_and_incomplete_coverage_do_not_create_runs(self):
        cases = [
            ({"timezone": "Mars/Unknown"}, "zona horaria"),
            ({"range_start": "2026-04-04T23:00:00", "range_end": "2026-04-05T01:00:00"}, "ambigua"),
            ({"range_end": "2026-10-20T03:00:00"}, "coverage"),
            ({"range_start": "2026-10-20T00:30:00"}, "resampling"),
        ]
        for changes, message in cases:
            with self.subTest(changes=changes):
                response = post_json_with_csrf(self.client, self.path + "/preview", {**self.payload, **changes})
                self.assertEqual(response.status_code, 400, response.text)
                self.assertIn(message, response.json()["detail"])
        self.assertIsNone(self.client.get(self.path, params=self.params).json()["run"])

    def test_a_different_display_zone_cannot_relabel_the_local_solver_grid(self):
        response = post_json_with_csrf(self.client, self.path + "/preview", {
            **self.payload, "timezone": "UTC", "range_start": "2026-10-20T03:00:00", "range_end": "2026-10-20T05:00:00",
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("zona", response.json()["detail"])

    def test_simultaneous_requests_across_connections_create_one_run(self):
        prepared = self.preview()
        other_store = AnalystStore(self.database_url)
        self.addCleanup(other_store.close)
        other = self.connect(other_store)
        payload = {**self.payload, "expected_preparation_hash": prepared["preparation_hash"], "idempotency_key": "concurrent"}
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(post_json_with_csrf, client, self.path + "/runs", payload) for client in [self.client, other]]
            responses = [future.result() for future in futures]
        self.assertEqual([r.status_code for r in responses], [201, 201], [r.text for r in responses])
        self.assertEqual(responses[0].json()["id"], responses[1].json()["id"])
        self.assertEqual(len(self.client.get(f"/api/scenarios/{self.fixture['scenario']['id']}/runs").json()["runs"]), 1)

    def test_reused_key_with_different_request_is_a_conflict_and_prior_snapshot_stays_frozen(self):
        prepared = self.preview()
        first = self.launch(prepared).json()
        self.assertEqual(self.launch(prepared, range_end="2026-10-20T01:00:00").status_code, 409)
        self.edit_demand(15)
        self.assertEqual(self.launch(prepared).json()["id"], first["id"])
        snapshot = self.client.get(f"/api/scenario-versions/{first['scenario_version_id']}").json()["scenario_version"]
        self.assertEqual([p["load_demand_mw"]["load_north"] for p in snapshot["system_case_json"]["time_series"]], [10, 12])

    def test_context_and_authentication_are_checked_for_prepare_execute_and_recovery(self):
        prepared = self.preview()
        other = seed_executable_mesa(self.store, name="Otro caso")
        for changed in ({"case_id": other["case"]["id"]}, {"variant_id": other["variant"]["id"]}):
            self.assertEqual(post_json_with_csrf(self.client, self.path + "/preview", {**self.payload, **changed}).status_code, 404)
            self.assertEqual(self.launch(prepared, **changed).status_code, 404)
            self.assertEqual(self.client.get(self.path, params={**self.params, **changed}).status_code, 404)
        self.assertEqual(self.client.post(self.path + "/preview", json=self.payload).status_code, 403)
        anonymous = TestClient(self.client.app)
        self.addCleanup(anonymous.close)
        self.assertEqual(anonymous.get(self.path, params=self.params).status_code, 401)
        self.store.create_user(email="external@example.local", display_name="Externo", role="external", password_hash=hash_password("external pass"))
        login_json_with_csrf(anonymous, "external@example.local", "external pass")
        self.assertEqual(post_json_with_csrf(anonymous, self.path + "/preview", self.payload).status_code, 404)
        self.assertEqual(anonymous.get(self.path, params=self.params).status_code, 404)

    def test_electrical_execution_explicitly_refuses_the_hydraulic_network_contract(self):
        fixture = seed_hydraulic_mesa(self.store)
        response = post_json_with_csrf(self.client, f"/api/scenarios/{fixture['scenario']['id']}/mesa/execution/preview", {
            **self.payload, "case_id": fixture["case"]["id"], "variant_id": fixture["variant"]["id"],
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("eléctrica", response.json()["detail"])

    def test_change_during_engine_validation_cannot_commit_an_obsolete_snapshot(self):
        entered, release = threading.Event(), threading.Event()
        class WaitingEngine(StubValidationService):
            def validate_text(self, candidate_text):
                entered.set()
                if not release.wait(15):
                    raise TimeoutError("No llegó la edición concurrente")
                return super().validate_text(candidate_text)
        prepared = self.preview()
        other_store = AnalystStore(self.database_url)
        self.addCleanup(other_store.close)
        client = TestClient(create_app(store=other_store, auth_enabled=True,
            validation_service=WaitingEngine(), run_queue=self.queue, artifact_root=self.temp.name))
        self.addCleanup(client.close)
        login_json_with_csrf(client, "mesa@example.local", "mesa test pass")
        payload = {**self.payload, "expected_preparation_hash": prepared["preparation_hash"], "idempotency_key": "during-validation"}
        with ThreadPoolExecutor(max_workers=1) as workers:
            future = workers.submit(post_json_with_csrf, client, self.path + "/runs", payload)
            try:
                self.assertTrue(entered.wait(10))
                self.edit_demand(15)
            finally:
                release.set()
            response = future.result()
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIsNone(self.client.get(self.path, params=self.params).json()["run"])

    def test_legacy_variant_can_revalidate_changed_parameters_from_the_mesa(self):
        from tests.test_ts3_case_variant_api import CaseInputVariantApiTests
        legacy = CaseInputVariantApiTests()
        legacy.setUp()
        self.addCleanup(legacy.store.close)
        self.addCleanup(legacy.client.close)
        root = f"/api/scenarios/{legacy.scenario['id']}"
        variant = legacy.client.get(root + "/case/default-variant").json()["variant"]
        legacy.client.post(f"{root}/case/variants/{variant['id']}/bindings", json={
            "signal_key": "import_price_usd_per_mwh", "time_series_set_id": legacy.price_set["id"],
        })
        payload = {"case_id": variant["case_id"], "variant_id": variant["id"], "range_start": "2026-01-01T00:00:00",
                   "range_end": "2026-01-01T02:00:00", "timezone": "America/Santiago", "resolution_hours": 1}
        legacy.client.post(f"{root}/case/variants/{variant['id']}/validate", json={
            "range_start": payload["range_start"], "range_end": payload["range_end"],
        })
        document = legacy.client.get(root + "/draft").json()["draft"]["document"]
        document["assets"][0]["initial_energy_mwh"] = 5
        saved = legacy.client.put(root + "/draft", json={"document": document})
        self.assertEqual(saved.status_code, 200, saved.text)
        prepared = legacy.client.post(root + "/mesa/execution/preview", json=payload)
        self.assertEqual(prepared.status_code, 200, prepared.text)
        run = legacy.client.post(root + "/mesa/execution/runs", json={**payload,
            "expected_preparation_hash": prepared.json()["preparation_hash"], "idempotency_key": "legacy"})
        self.assertEqual(run.status_code, 201, run.text)

    def test_real_worker_completes_and_outputs_are_readable_in_the_same_mesa(self):
        with TestClient(create_app(store=self.store, auth_enabled=True, artifact_root=self.temp.name)) as client:
            self.client = client
            login_json_with_csrf(client, "mesa@example.local", "mesa test pass")
            self.edit_demand(15)
            prepared = self.preview()
            response = self.launch(prepared)
            self.assertEqual(response.status_code, 201, response.text)
            run_id = response.json()["id"]
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                recovered = client.get(self.path, params=self.params).json()["run"]
                self.assertEqual(recovered["id"], run_id)
                if recovered["status"] in ("succeeded", "failed"):
                    break
                time.sleep(0.1)
            self.assertEqual(recovered["status"], "succeeded", recovered)
            self.assertEqual(recovered["success_payload"]["termination_status"], "OPTIMAL")
            mesa = client.get(self.path.removesuffix("/execution"), params={**self.params, "run_id": run_id})
            self.assertEqual(mesa.status_code, 200, mesa.text)
            battery = next(c for c in mesa.json()["components"] if c["entity_id"] == "battery_1")
            self.assertEqual(battery["series"]["status"], "available")
            self.assertEqual(len(battery["series"]["points"]), 2)
            self.assertEqual(battery["series"]["run_id"], run_id)

    def test_real_worker_failure_is_recoverable_and_keeps_saved_inputs_without_outputs(self):
        with TestClient(create_app(store=self.store, auth_enabled=True, artifact_root=self.temp.name)) as client:
            self.client = client
            login_json_with_csrf(client, "mesa@example.local", "mesa test pass")
            self.edit_demand(100)
            prepared = self.preview()
            response = self.launch(prepared)
            self.assertEqual(response.status_code, 201, response.text)
            run_id = response.json()["id"]
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                run = client.get(self.path, params=self.params).json()["run"]
                if run["status"] in ("succeeded", "failed"):
                    break
                time.sleep(0.1)
            self.assertEqual(run["status"], "failed", run)
            self.assertTrue(run["error_message"])
            mesa_path = self.path.removesuffix("/execution")
            self.assertEqual(client.get(mesa_path, params={**self.params, "run_id": run_id}).status_code, 404)
            mesa = client.get(mesa_path, params=self.params).json()
            demand = next(c for c in mesa["components"] if c["entity_id"] == "load_north")
            self.assertEqual([p["value"] for p in demand["series"]["points"]], [10, 100])


if __name__ == "__main__":
    unittest.main()
