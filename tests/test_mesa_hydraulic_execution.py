"""MESA-008 behavior through authenticated HTTP and the existing real worker."""

import tempfile
import time
import unittest
import threading
import subprocess
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.validation import JuliaValidationService
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf
from tests.mesa_hydraulic_execution_fixture import seed_executable_hydraulic_mesa, add_unbound_electrical_draft
from tests.mesa_hydraulic_fixture import seed_hydraulic_mesa_run
from tests.test_ts3_case_variant_api import RecordingRunQueue, StubValidationService


class MesaHydraulicExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database_url = f"sqlite:///{Path(self.temp.name) / 'mesa.sqlite3'}"
        self.store = AnalystStore(self.database_url)
        self.addCleanup(self.store.close)
        self.store.create_user(email="mesa@example.local", display_name="Analista", role="analyst",
                               password_hash=hash_password("mesa test pass"))
        self.fixture = seed_executable_hydraulic_mesa(self.store)
        self.queue = RecordingRunQueue()
        self.client = self.connect(self.store)
        self.path = f"/api/scenarios/{self.fixture['scenario']['id']}/mesa/hydraulic-execution"
        self.params = {"case_id": self.fixture["case"]["id"]}
        self.payload = {**self.params, "source_scenario_version_id": self.fixture["version"]["id"],
            "range_start": "2026-10-20T00:00:00+00:00", "range_end": "2026-10-20T02:00:00+00:00",
            "resolution_hours": 2, "objective": "market_value", "price_time_series_set_id": self.fixture["prices"]["id"],
            "terminal_water_values_usd_per_hm3": {"reservoir": 1}, "mip_rel_gap": 0.01}

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

    def launch(self, prepared, key="hydraulic-request-1", **changes):
        return post_json_with_csrf(self.client, self.path + "/runs", {
            **self.payload, "expected_preparation_hash": prepared["preparation_hash"], "idempotency_key": key, **changes})

    def test_network_mesa_ignores_unbound_electrical_draft_and_can_prepare_and_launch(self):
        draft = add_unbound_electrical_draft(self.store, self.fixture)
        scenario_id = self.fixture["scenario"]["id"]
        variant_id = self.fixture["variant"]["id"]
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        for selected in ({}, {"run_id": run["id"]}):
            response = self.client.get(self.path.removesuffix("/hydraulic-execution"),
                params={**self.params, "variant_id": variant_id, **selected})
            self.assertEqual(response.status_code, 200, response.text)
            mesa = response.json()
            self.assertEqual(mesa["context"]["model_contract"], "bess_system_dispatch.v3")
            self.assertIn("reservoir", [c["entity_id"] for c in mesa["components"]])
            self.assertNotIn("hydro_1", [c["entity_id"] for c in mesa["components"]])
        prepared = self.preview()
        self.assertEqual(prepared["period_count"], 1)
        self.assertEqual(prepared["preview_periods"][0]["natural_inflow_m3s"], {"reservoir": 3})
        self.assertEqual(prepared["preview_periods"][0]["price_usd_per_mwh"], 50)
        launched = self.launch(prepared)
        self.assertEqual(launched.status_code, 201, launched.text)
        snapshot = self.store.get_scenario_version(launched.json()["scenario_version_id"])
        self.assertEqual(snapshot["system_case_json"]["schema_version"], "bess_system_dispatch.v3")
        self.assertEqual(self.store.get_scenario_draft(scenario_id)["document"], draft)
        self.assertEqual(self.store.list_case_time_series_bindings(variant_id), [])

    def test_old_electrical_form_directs_a_network_case_back_to_hydraulic_preparation(self):
        add_unbound_electrical_draft(self.store, self.fixture)
        response = post_json_with_csrf(self.client, self.path.replace("/hydraulic-execution", "/execution") + "/preview", {
            **self.params, "variant_id": self.fixture["variant"]["id"],
            "range_start": self.payload["range_start"], "range_end": self.payload["range_end"],
            "timezone": "UTC", "resolution_hours": 1,
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("Preparar ejecución hidráulica", response.json()["detail"])
        self.assertNotIn("missing required bindings", response.text)
        self.assertEqual(self.store.list_scenario_runs(self.fixture["scenario"]["id"]), [])

    def test_real_network_run_recovers_and_exposes_plant_power_and_reservoir_volume(self):
        with TestClient(create_app(store=self.store, auth_enabled=True, artifact_root=self.temp.name)) as client:
            self.client = client
            login_json_with_csrf(client, "mesa@example.local", "mesa test pass")
            prepared = self.preview()
            self.assertEqual(prepared["period_count"], 1)
            self.assertEqual(prepared["preview_periods"][0]["natural_inflow_m3s"], {"reservoir": 3})
            self.assertEqual(prepared["preview_periods"][0]["price_usd_per_mwh"], 50)
            launched = self.launch(prepared)
            self.assertEqual(launched.status_code, 201, launched.text)
            run_id = launched.json()["id"]
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                state = client.get(self.path, params=self.params)
                self.assertEqual(state.status_code, 200, state.text)
                run = state.json()["run"]
                self.assertEqual(run["id"], run_id)
                if run["status"] in ("succeeded", "failed"):
                    break
                time.sleep(0.1)
            self.assertEqual(run["status"], "succeeded", run)
            mesa = client.get(self.path.removesuffix('/hydraulic-execution'), params={**self.params,
                "variant_id": self.fixture["variant"]["id"], "run_id": run_id})
            self.assertEqual(mesa.status_code, 200, mesa.text)
            components = {c["entity_id"]: c for c in mesa.json()["components"]}
            def output(entity, name):
                component = components[entity]
                return next(s for s in [component["series"], *component["additional_series"]] if s["name"] == name)
            power = output("plant_1", "Potencia hidráulica")
            storage = output("reservoir", "Volumen almacenado")
            self.assertEqual(power["status"], "available")
            self.assertEqual(power["run_id"], run_id)
            self.assertEqual([p["value"] for p in power["points"]], [30])
            self.assertAlmostEqual(storage["points"][0]["value"], 9.7336)
            other_store = AnalystStore(self.database_url)
            self.addCleanup(other_store.close)
            other = self.connect(other_store)
            recovered = other.get(self.path, params=self.params).json()["run"]
            self.assertEqual((recovered["id"], recovered["status"]), (run_id, "succeeded"))

    def test_retry_after_reconnecting_returns_one_run_and_conflicting_key_is_rejected(self):
        prepared = self.preview()
        first = self.launch(prepared)
        self.assertEqual(first.status_code, 201, first.text)
        other_store = AnalystStore(self.database_url)
        self.addCleanup(other_store.close)
        self.client = self.connect(other_store)
        retry = self.launch(prepared)
        self.assertEqual(retry.status_code, 201, retry.text)
        self.assertEqual(retry.json()["id"], first.json()["id"])
        conflict = self.launch(prepared, mip_rel_gap=0.02)
        self.assertEqual(conflict.status_code, 409, conflict.text)
        runs = self.client.get(f"/api/scenarios/{self.fixture['scenario']['id']}/runs").json()["runs"]
        self.assertEqual([r["id"] for r in runs], [first.json()["id"]])

    def edit_price(self, value):
        csrf = self.client.get('/api/auth/csrf').json()['csrf_token']
        response = self.client.put(f"/api/projects/{self.fixture['project']['id']}/time-series-sets/{self.fixture['prices']['id']}/values",
            json={"edits": [{"period_index": 0, "signal_key": "price_usd_per_mwh", "value": str(value)}]},
            headers={"X-CSRF-Token": csrf})
        self.assertEqual(response.status_code, 200, response.text)

    def test_changed_cmg_blocks_old_preparation_but_keeps_the_accepted_snapshot(self):
        prepared = self.preview()
        first = self.launch(prepared).json()
        self.edit_price(50)
        rejected = self.launch(prepared, key="another-request")
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertIn("validar", rejected.text)
        self.assertEqual(self.launch(prepared).json()["id"], first["id"])
        snapshot = self.client.get(f"/api/scenario-versions/{first['scenario_version_id']}").json()["scenario_version"]
        self.assertEqual(snapshot["system_case_json"]["time_series"][0]["price_usd_per_mwh"], 50)
        versions = self.client.get(f"/api/scenarios/{self.fixture['scenario']['id']}/versions").json()["versions"]
        self.assertEqual(len(versions), 2)
        current = self.preview()
        self.assertEqual(current["preview_periods"][0]["price_usd_per_mwh"], 70)

    def test_cmg_change_while_external_validator_runs_creates_no_snapshot_or_run(self):
        prepared = self.preview()
        entered, release = threading.Event(), threading.Event()
        def validation_process(*args, **kwargs):
            entered.set()
            if not release.wait(15):
                raise TimeoutError("Test did not release the external validator")
            return subprocess.CompletedProcess(args, 0, '{"status":"ok"}', '')
        client = TestClient(create_app(store=self.store, auth_enabled=True, run_queue=self.queue,
            validation_service=JuliaValidationService(runner=validation_process), artifact_root=self.temp.name))
        self.addCleanup(client.close)
        login_json_with_csrf(client, "mesa@example.local", "mesa test pass")
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(post_json_with_csrf, client, self.path + '/runs', {
                **self.payload, "expected_preparation_hash": prepared["preparation_hash"], "idempotency_key": "during-validation"})
            try:
                self.assertTrue(entered.wait(10))
                other = AnalystStore(self.database_url)
                self.addCleanup(other.close)
                self.client = self.connect(other)
                self.edit_price(50)
            finally:
                release.set()
            response = result.result(timeout=15)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIsNone(self.client.get(self.path, params=self.params).json()["run"])
        versions = self.client.get(f"/api/scenarios/{self.fixture['scenario']['id']}/versions").json()["versions"]
        self.assertEqual(len(versions), 1)

    def test_snapshot_keeps_exact_options_source_and_promoted_diagram(self):
        prepared = self.preview()
        response = self.launch(prepared)
        self.assertEqual(response.status_code, 201, response.text)
        version_id = response.json()["scenario_version_id"]
        snapshot = self.client.get(f"/api/scenario-versions/{version_id}/hydraulic-diagram-snapshot")
        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        self.assertEqual(snapshot.json()["snapshot"]["source_case_id"], self.params["case_id"])
        version = self.client.get(f"/api/scenario-versions/{version_id}").json()["scenario_version"]
        self.assertEqual(version["system_case_json"]["solver"]["options"]["mip_rel_gap"], 0.01)
        self.assertEqual(version["system_case_json"]["time_series"], prepared["preview_periods"])
        self.assertEqual(version["generation_metadata"]["source_scenario_version_id"], self.fixture["version"]["id"])
        self.assertNotIn("input_variant", version["generation_metadata"])

    def test_source_picker_identifies_frozen_network_components_and_coverage(self):
        response = self.client.get(self.path + '/sources', params=self.params)
        self.assertEqual(response.status_code, 200, response.text)
        sources = response.json()["sources"]
        self.assertEqual([s["id"] for s in sources], [self.fixture["version"]["id"]])
        source = sources[0]
        self.assertEqual(source["range_start"], "2026-10-20T00:00:00+00:00")
        self.assertEqual(source["range_end"], "2026-10-20T02:00:00+00:00")
        self.assertEqual({c["entity_id"] for c in source["components"]},
                         {"reservoir", "intake", "outlet", "plant_1", "unit_1", "reach"})
        self.assertEqual(source["terminal_water_values_usd_per_hm3"], {"reservoir": 0})

    def test_version_based_run_is_selectable_from_another_view_variant_of_the_same_case(self):
        # Completed-run fixture tests selection; the real worker test above verifies outputs.
        run = self.launch(self.preview()).json()
        self.store.mark_run_succeeded(run["id"], exit_code=0, stdout="", stderr="",
            success_payload={"termination_status": "OPTIMAL"}, output_dir=self.temp.name, summary_path=str(Path(self.temp.name) / 'summary.json'))
        variant = self.store.create_case_input_variant(case_id=self.params["case_id"], display_name="Otra vista")
        response = self.client.get(self.path.removesuffix('/hydraulic-execution'), params={**self.params,
            "variant_id": variant["id"], "run_id": run["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["selected_run"]["id"], run["id"])

    def test_objective_price_water_gap_and_coverage_errors_do_not_create_runs(self):
        for changes, status, message in (
            ({"price_time_series_set_id": None}, 400, "CMg"),
            ({"objective": "energy"}, 400, "agua"),
            ({"terminal_water_values_usd_per_hm3": {"missing-reservoir": 1}}, 400, "missing-reservoir"),
            ({"mip_rel_gap": -0.1}, 422, "mip_rel_gap"),
            ({"terminal_water_values_usd_per_hm3": {"reservoir": "NaN"}}, 422, "reservoir"),
            ({"resolution_hours": 3}, 400, "pasos completos"),
            ({"range_end": "2026-10-21T00:00:00Z"}, 400, "cubre"),
            ({"range_start": "2026-10-20T02:00:00Z"}, 400, "positivos"),
        ):
            with self.subTest(changes=changes):
                response = post_json_with_csrf(self.client, self.path + '/preview', {**self.payload, **changes})
                self.assertEqual(response.status_code, status, response.text)
                self.assertIn(message, response.text)
        good = post_json_with_csrf(self.client, self.path + '/preview', {**self.payload,
            "objective": "energy", "price_time_series_set_id": None, "terminal_water_values_usd_per_hm3": {"reservoir": 0}, "mip_rel_gap": 0})
        self.assertEqual(good.status_code, 200, good.text)
        self.assertNotIn("price_usd_per_mwh", good.json()["preview_periods"][0])
        self.assertIsNone(self.client.get(self.path, params=self.params).json()["run"])

    def test_context_permissions_and_csrf_apply_to_sources_prepare_run_and_recovery(self):
        prepared = self.preview()
        other = seed_executable_hydraulic_mesa(self.store, name="Otra red")
        for changes in ({"case_id": other["case"]["id"]}, {"source_scenario_version_id": other["version"]["id"]},
                        {"price_time_series_set_id": other["prices"]["id"]}):
            response = post_json_with_csrf(self.client, self.path + '/preview', {**self.payload, **changes})
            self.assertEqual(response.status_code, 404, response.text)
            self.assertEqual(self.launch(prepared, **changes).status_code, 404)
        for suffix in ('', '/sources'):
            self.assertEqual(self.client.get(self.path + suffix, params={"case_id": other['case']['id']}).status_code, 404)
        self.assertEqual(self.client.post(self.path + '/preview', json=self.payload).status_code, 403)
        self.assertEqual(self.client.post(self.path + '/runs', json=self.payload).status_code, 403)
        anonymous = TestClient(self.client.app)
        self.addCleanup(anonymous.close)
        self.assertEqual(anonymous.get(self.path, params=self.params).status_code, 401)
        self.store.create_user(email="external@example.local", display_name="Externo", role="external", password_hash=hash_password("external pass"))
        login_json_with_csrf(anonymous, "external@example.local", "external pass")
        for suffix in ('', '/sources'):
            self.assertEqual(anonymous.get(self.path + suffix, params=self.params).status_code, 404)
        for suffix in ('/preview', '/runs'):
            self.assertEqual(post_json_with_csrf(anonymous, self.path + suffix, self.payload).status_code, 404)

    def test_concurrent_retries_from_two_connections_create_one_snapshot_and_run(self):
        prepared = self.preview()
        other_store = AnalystStore(self.database_url)
        self.addCleanup(other_store.close)
        other = self.connect(other_store)
        barrier = threading.Barrier(2)
        def launch(client):
            barrier.wait(timeout=10)
            return post_json_with_csrf(client, self.path + '/runs', {**self.payload,
                "expected_preparation_hash": prepared["preparation_hash"], "idempotency_key": "concurrent"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(launch, client) for client in (self.client, other)]
            responses = [f.result(timeout=20) for f in futures]
        self.assertEqual([r.status_code for r in responses], [201, 201], [r.text for r in responses])
        self.assertEqual(responses[0].json()['id'], responses[1].json()['id'])
        root = f"/api/scenarios/{self.fixture['scenario']['id']}"
        self.assertEqual(len(other.get(root + '/runs').json()['runs']), 1)
        self.assertEqual(len(other.get(root + '/versions').json()['versions']), 2)

    def test_real_validator_identifies_unit_with_invalid_topology_or_unsupported_pumping(self):
        client = TestClient(create_app(store=self.store, auth_enabled=True, run_queue=self.queue,
            artifact_root=self.temp.name))
        self.addCleanup(client.close)
        login_json_with_csrf(client, "mesa@example.local", "mesa test pass")
        for change in ({"intake_node": "missing_intake"}, {"can_pump": True}):
            with self.subTest(change=change):
                document = copy.deepcopy(self.fixture["version"]["system_case_json"]) if "system_case_json" in self.fixture["version"] else self.store.get_scenario_version(self.fixture["version"]["id"])["system_case_json"]
                document["hydraulic_network"]["units"][0].update(change)
                version = self.store.create_scenario_version(scenario_id=self.fixture["scenario"]["id"],
                    system_case_json=document, validation_payload={"status": "fixture-invalid"})
                response = post_json_with_csrf(client, self.path + '/preview', {**self.payload, "source_scenario_version_id": version["id"]})
                self.assertEqual(response.status_code, 400, response.text)
                self.assertIn("unit_1", response.json()["detail"])
        self.assertIsNone(client.get(self.path, params=self.params).json()["run"])
