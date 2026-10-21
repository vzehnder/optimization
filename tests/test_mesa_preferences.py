"""MESA-003: visual preferences observed only through authenticated HTTP."""

import copy
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf, put_json_with_csrf
from tests.mesa_fixture import seed_mesa_case
from tests.test_ts4_run_comparison import create_indexed_run


class MesaPreferencesApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database_url = f"sqlite:///{Path(self.directory.name) / 'mesa.db'}"
        self.store = AnalystStore(self.database_url)
        self.store.create_user(email="mesa@example.local", display_name="Analista", role="analyst", password_hash=hash_password("mesa test pass"))
        self.fixture = seed_mesa_case(self.store)
        self.open_client()
        self.path = f"/api/scenarios/{self.fixture['scenario']['id']}/mesa/preferences?case_id={self.fixture['case']['id']}"

    def open_client(self):
        self.client = TestClient(create_app(store=self.store, auth_enabled=True, artifact_root=Path(self.directory.name)))
        self.assertEqual(login_json_with_csrf(self.client, "mesa@example.local", "mesa test pass").status_code, 200)

    def tearDown(self):
        self.client.close()
        self.store.close()
        self.directory.cleanup()

    def configuration(self):
        return {
            "schema_version": 1, "active_tab_id": "general",
            "tabs": [{"id": "general", "title": "Vista general", "layout": "2x2", "panels": [
                {"id": f"view-{i}", "title": title, "mode": mode,
                 "component": {"linkable_object_id": self.fixture["object"]["id"], "entity_type": "component:load", "entity_id": "load_north"},
                 "series_keys": ["load_demand_mw"]}
                for i, (title, mode) in enumerate([
                    ("Consumo", "chart"), ("Detalle", "table"), ("Operación", "chart"), ("Auditoría", "table")
                ])
            ]}],
        }

    def save(self, configuration, revision):
        return put_json_with_csrf(self.client, self.path, {"expected_revision": revision, "configuration": configuration})

    def test_four_panel_configurations_survive_reduction_reload_and_restore(self):
        configuration = self.configuration()
        response = self.save(configuration, 0)
        self.assertEqual(response.status_code, 200, response.text)
        configuration["tabs"][0]["layout"] = "1x1"
        response = self.save(configuration, response.json()["revision"])
        self.assertEqual(response.status_code, 200, response.text)
        # Reopen the persisted database and app, not merely the HTTP client.
        self.client.close()
        self.store.close()
        self.store = AnalystStore(self.database_url)
        self.open_client()
        restored = self.client.get(self.path).json()
        self.assertEqual(restored["configuration"], configuration)
        restored["configuration"]["tabs"][0]["layout"] = "2x2"
        response = self.save(restored["configuration"], restored["revision"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get(self.path).json()["configuration"], self.configuration())

    def test_stale_writer_cannot_overwrite_and_can_reload_before_retrying(self):
        initial = self.configuration()
        first = self.save(initial, 0)
        self.assertEqual(first.status_code, 200, first.text)
        changed = copy.deepcopy(initial)
        changed["tabs"][0]["title"] = "Otra sesión"
        for stale_revision in (0, 99):
            response = self.save(changed, stale_revision)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(self.client.get(self.path).json(), first.json())
        latest = self.client.get(self.path).json()
        response = self.save(changed, latest["revision"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get(self.path).json()["configuration"]["tabs"][0]["title"], "Otra sesión")

    def test_visual_preferences_are_private_and_do_not_modify_case_inputs(self):
        sid = self.fixture["scenario"]["id"]
        vid = self.fixture["variant"]["id"]
        paths = [f"/api/scenarios/{sid}/draft", f"/api/scenarios/{sid}/case/default-variant",
                 f"/api/scenarios/{sid}/case-variants/{vid}/time-series-bindings",
                 f"/api/scenarios/{sid}/mesa?case_id={self.fixture['case']['id']}&variant_id={vid}",
                 f"/api/scenarios/{sid}/versions", f"/api/scenarios/{sid}/runs"]
        before = []
        for path in paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            before.append(response.json())
        first = self.save(self.configuration(), 0)
        self.assertEqual(first.status_code, 200, first.text)
        config = self.configuration()
        config["tabs"][0]["panels"] = []
        self.assertEqual(self.save(config, 1).status_code, 200)
        for path, expected in zip(paths, before):
            body = self.client.get(path).json()
            if "meta" in body:
                body["meta"].pop("request_id", None)
                expected["meta"].pop("request_id", None)
            self.assertEqual(body, expected, path)
        other = seed_mesa_case(self.store, name="Caso separado")
        other_path = f"/api/scenarios/{other['scenario']['id']}/mesa/preferences?case_id={other['case']['id']}"
        self.assertEqual(self.client.get(other_path).json()["revision"], 0)
        mismatched = f"/api/scenarios/{sid}/mesa/preferences?case_id={other['case']['id']}"
        self.assertEqual(self.client.get(mismatched).status_code, 404)
        self.assertEqual(put_json_with_csrf(self.client, mismatched, {"expected_revision": 0, "configuration": config}).status_code, 404)
        self.store.create_user(email="second@example.local", display_name="Otra analista", role="analyst", password_hash=hash_password("second pass"))
        other_client = TestClient(self.client.app)
        try:
            self.assertEqual(other_client.get(self.path).status_code, 401)
            login_json_with_csrf(other_client, "second@example.local", "second pass")
            self.assertEqual(other_client.get(self.path).json()["revision"], 0)
            self.assertEqual(put_json_with_csrf(other_client, self.path, {"expected_revision": 0, "configuration": self.configuration()}).status_code, 200)
            self.assertEqual(self.client.get(self.path).json()["configuration"], config)
        finally:
            other_client.close()
        for role in ("external",):
            self.store.create_user(email=f"{role}@example.local", display_name=role, role=role, password_hash=hash_password("external pass"))
            external = TestClient(self.client.app)
            try:
                login_json_with_csrf(external, f"{role}@example.local", "external pass")
                self.assertEqual(external.get(self.path).status_code, 404)
                self.assertEqual(put_json_with_csrf(external, self.path, {"expected_revision": 0, "configuration": config}).status_code, 404)
            finally:
                external.close()
        self.assertEqual(self.client.put(self.path, json={"expected_revision": 2, "configuration": config}).status_code, 403)

    def test_invalid_configuration_cannot_replace_the_readable_visual_document(self):
        saved = self.save(self.configuration(), 0).json()
        invalid = []
        config = self.configuration()
        config["active_tab_id"] = "missing"
        invalid.append(config)
        config = self.configuration()
        config["tabs"].append(copy.deepcopy(config["tabs"][0]))
        invalid.append(config)
        config = self.configuration()
        config["tabs"][0]["panels"][1]["id"] = "view-0"
        invalid.append(config)
        config = self.configuration()
        config["tabs"][0]["panels"][0]["series_keys"] = ["load_demand_mw", "load_demand_mw"]
        invalid.append(config)
        config = self.configuration()
        config["tabs"][0]["panels"][0]["series_keys"] = [" "]
        invalid.append(config)
        config = self.configuration()
        config["tabs"][0]["panels"][0]["points"] = [10, 12]
        invalid.append(config)
        config = self.configuration()
        config["schema_version"] = 2
        invalid.append(config)
        for config in invalid:
            with self.subTest(config=config):
                response = self.save(config, saved["revision"])
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.client.get(self.path).json(), saved)

    def test_configuring_views_keeps_existing_snapshot_and_indexed_results(self):
        run = create_indexed_run(self.store, Path(self.directory.name),
            scenario_id=self.fixture["scenario"]["id"], objective_value_usd=1000,
            input_variant={"id": self.fixture["variant"]["id"], "display_name": "Default"})
        paths = [f"/api/scenario-versions/{run['scenario_version_id']}", f"/api/runs/{run['id']}/results"]
        before = []
        for path in paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            before.append(response.json())
        config = self.configuration()
        self.assertEqual(self.save(config, 0).status_code, 200)
        config["tabs"][0]["panels"] = []
        self.assertEqual(self.save(config, 1).status_code, 200)
        for path, expected in zip(paths, before):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), expected)
