"""MESA-011: hydraulic asset changes observed through authenticated HTTP."""

import tempfile
import unittest
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.runner import JuliaRunExecutor, LocalRunQueue
from app.validation import JuliaValidationService
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf
from tests.mesa_hydraulic_execution_fixture import seed_executable_hydraulic_mesa


class MesaHydraulicAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database_url = f"sqlite:///{Path(self.temp.name) / 'assets.sqlite3'}"
        self.store = AnalystStore(self.database_url)
        self.addCleanup(self.store.close)
        self.store.create_user(email="mesa@example.local", display_name="Analista", role="analyst",
                               password_hash=hash_password("mesa test pass"))
        self.fixture = seed_executable_hydraulic_mesa(self.store)
        validation = JuliaValidationService(runner=lambda *args, **kwargs:
            subprocess.CompletedProcess(args, 0, '{"status":"ok"}', ''))
        queue = LocalRunQueue(executor=JuliaRunExecutor(store=self.store, artifact_root=self.temp.name,
            validation_service=validation, runner=lambda *args, **kwargs:
                subprocess.CompletedProcess(args, 1, '', 'No solve in this HTTP freshness fixture.')))
        self.addCleanup(queue.stop)
        self.client = TestClient(create_app(store=self.store, auth_enabled=True,
            run_queue=queue, validation_service=validation, artifact_root=self.temp.name))
        self.addCleanup(self.client.close)
        login_json_with_csrf(self.client, "mesa@example.local", "mesa test pass")
        self.scenario_path = f"/api/scenarios/{self.fixture['scenario']['id']}"
        self.diagram_path = self.scenario_path + "/hydraulic-diagram"
        self.execution_path = self.scenario_path + "/mesa/hydraulic-execution"
        self.options = {"case_id": self.fixture["case"]["id"], "source_scenario_version_id": self.fixture["version"]["id"],
            "range_start": "2026-10-20T00:00:00Z", "range_end": "2026-10-20T02:00:00Z",
            "resolution_hours": 2, "objective": "energy", "terminal_water_values_usd_per_hm3": {"reservoir": 0}}

    def diagram(self):
        response = self.client.get(self.diagram_path)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["diagram"]

    def save(self, diagram):
        csrf = self.client.get("/api/auth/csrf").json()["csrf_token"]
        return self.client.put(self.diagram_path, headers={"X-CSRF-Token": csrf}, json={
            "revision": diagram["revision"], "viewport": diagram["layout"]["viewport"],
            "nodes": diagram["nodes"], "reaches": diagram["reaches"]})

    def preview(self):
        response = post_json_with_csrf(self.client, self.execution_path + "/preview", self.options)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def launch(self, preview, key):
        return post_json_with_csrf(self.client, self.execution_path + "/runs", {
            **self.options, "expected_preparation_hash": preview["preparation_hash"], "idempotency_key": key})

    def test_asset_edit_invalidates_preparation_and_preserves_accepted_snapshot_and_retry(self):
        prepared = self.preview()
        accepted = self.launch(prepared, "accepted")
        self.assertEqual(accepted.status_code, 201, accepted.text)
        version_url = f"/api/scenario-versions/{accepted.json()['scenario_version_id']}"
        frozen = self.client.get(version_url).json()
        diagram = self.diagram()
        diagram["nodes"].append({"component_type": "reservoir", "technical_key": "new_reservoir",
            "display_name": "Embalse borrador", "x": 500, "y": 0})
        saved = self.save(diagram)
        self.assertEqual(saved.status_code, 200, saved.text)
        rejected = self.launch(prepared, "after-edit")
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertIn("validar", rejected.text)
        self.assertEqual(self.client.get(version_url).json(), frozen)
        self.assertEqual(self.launch(prepared, "accepted").json()["id"], accepted.json()["id"])
        self.assertEqual(len(self.client.get(self.scenario_path + "/runs").json()["runs"]), 1)


if __name__ == "__main__":
    unittest.main()
