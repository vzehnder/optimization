import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.test_results_review import (
    create_completed_run_with_hydro_result_artifacts,
    create_completed_run_with_result_artifacts,
)


class Iteration6DashboardTemplateTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.create_user("admin@example.local", role="admin", password="admin pass")
        self.login(self.client, "admin@example.local", "admin pass")

    def tearDown(self):
        self.store.close()

    def test_internal_user_can_create_list_and_update_project_dashboard_templates(self):
        project = self.client.post(
            "/api/projects",
            json={"name": "Template Project", "description": "Client dashboard curation"},
        ).json()
        scenario = self.store.create_scenario(project_id=project["id"], name="Base")
        version = self.store.create_scenario_version(
            scenario_id=scenario["id"],
            system_case_json={
                "schema_version": "bess_system_dispatch.v1",
                "case_name": "template_case",
                "nodes": [],
                "time_series": [],
            },
            validation_payload={"status": "ok"},
        )
        run = self.store.create_run(scenario_version_id=version["id"])
        before_version = self.store.get_scenario_version(version["id"], include_document=False)
        before_run = self.store.get_run(run["id"])

        create_response = self.client.post(
            f"/api/projects/{project['id']}/dashboard-templates",
            json={
                "name": "Executive Client View",
                "show_summary": True,
                "show_price_chart": True,
                "show_grid_chart": True,
                "show_renewable_chart": False,
                "show_bess_chart": True,
                "show_hydro_chart": False,
                "show_profit_chart": True,
                "show_system_dispatch_table": True,
                "show_asset_dispatch_table": False,
                "table_preview_limit": 7,
            },
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()["dashboard_template"]
        self.assertEqual(created["project_id"], project["id"])
        self.assertEqual(created["name"], "Executive Client View")
        self.assertTrue(created["show_price_chart"])
        self.assertFalse(created["show_renewable_chart"])
        self.assertEqual(created["table_preview_limit"], 7)
        self.assertEqual(created["created_by"], "admin@example.local")

        list_response = self.client.get(f"/api/projects/{project['id']}/dashboard-templates")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            [(template["id"], template["name"]) for template in list_response.json()["dashboard_templates"]],
            [(created["id"], "Executive Client View")],
        )

        update_response = self.client.put(
            f"/api/dashboard-templates/{created['id']}",
            json={
                "name": "External Reviewer View",
                "show_summary": False,
                "show_price_chart": False,
                "show_grid_chart": True,
                "show_renewable_chart": True,
                "show_bess_chart": False,
                "show_hydro_chart": True,
                "show_profit_chart": False,
                "show_system_dispatch_table": False,
                "show_asset_dispatch_table": True,
                "table_preview_limit": 3,
            },
        )

        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()["dashboard_template"]
        self.assertEqual(updated["name"], "External Reviewer View")
        self.assertFalse(updated["show_summary"])
        self.assertTrue(updated["show_hydro_chart"])
        self.assertTrue(updated["show_asset_dispatch_table"])
        self.assertEqual(updated["table_preview_limit"], 3)
        self.assertEqual(updated["updated_by"], "admin@example.local")
        self.assertEqual(self.store.get_scenario_version(version["id"], include_document=False), before_version)
        self.assertEqual(self.store.get_run(run["id"]), before_run)

    def test_dashboard_template_rendering_filters_existing_result_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_hydro_result_artifacts(self.store, artifact_root)
            project_id = self.project_id_for_run(run["id"])
            template = self.store.create_dashboard_template(
                project_id=project_id,
                name="Client Hydro View",
                show_summary=True,
                show_price_chart=False,
                show_grid_chart=True,
                show_renewable_chart=False,
                show_bess_chart=False,
                show_hydro_chart=True,
                show_profit_chart=False,
                show_system_dispatch_table=True,
                show_asset_dispatch_table=False,
                table_preview_limit=1,
                created_by="admin@example.local",
            )
            client = TestClient(
                create_app(
                    store=self.store,
                    artifact_root=artifact_root,
                    auth_enabled=True,
                )
            )
            self.login(client, "admin@example.local", "admin pass")

            response = client.get(f"/api/dashboard-templates/{template['id']}/runs/{run['id']}/results")

            self.assertEqual(response.status_code, 200)
            dashboard = response.json()["dashboard"]
            results = dashboard["results"]
            self.assertEqual(dashboard["template"]["name"], "Client Hydro View")
            self.assertEqual(results["summary"]["case_name"], "hydro_system")
            self.assertEqual(
                list(results["charts"].keys()),
                [
                    "all_series",
                    "grid_import_export",
                    "hydro_power",
                    "hydro_flows",
                    "hydro_storage",
                    "hydro_reservoir_elevation",
                ],
            )
            self.assertTrue(results["charts"]["hydro_power"]["available"])
            self.assertEqual(len(results["dispatch_table"]["rows"]), 1)
            self.assertIsNone(results["asset_dispatch_table"])

    def test_dashboard_template_rendering_handles_legacy_price_and_missing_hydro(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_result_artifacts(self.store, artifact_root)
            project_id = self.project_id_for_run(run["id"])
            template = self.store.create_dashboard_template(
                project_id=project_id,
                name="Legacy Compatible View",
                show_summary=False,
                show_price_chart=True,
                show_grid_chart=False,
                show_renewable_chart=False,
                show_bess_chart=False,
                show_hydro_chart=True,
                show_profit_chart=False,
                show_system_dispatch_table=False,
                show_asset_dispatch_table=False,
                table_preview_limit=5,
                created_by="admin@example.local",
            )
            client = TestClient(
                create_app(
                    store=self.store,
                    artifact_root=artifact_root,
                    auth_enabled=True,
                )
            )
            self.login(client, "admin@example.local", "admin pass")

            response = client.get(f"/api/dashboard-templates/{template['id']}/runs/{run['id']}/results")

            self.assertEqual(response.status_code, 200)
            results = response.json()["dashboard"]["results"]
            self.assertIsNone(results["summary"])
            self.assertTrue(results["charts"]["price"]["available"])
            self.assertEqual(results["charts"]["price"]["series"][0]["key"], "price_usd_per_mwh")
            self.assertFalse(results["charts"]["hydro_power"]["available"])
            self.assertIn("total_hydro_power_mw", results["charts"]["hydro_power"]["missing_columns"])
            self.assertIsNone(results["dispatch_table"])
            self.assertIsNone(results["asset_dispatch_table"])

    def test_dashboard_templates_remain_project_scoped_and_client_blocked(self):
        first_project = self.client.post(
            "/api/projects",
            json={"name": "Template Owner", "description": ""},
        ).json()
        second_project = self.client.post(
            "/api/projects",
            json={"name": "Other Project", "description": ""},
        ).json()
        template_response = self.client.post(
            f"/api/projects/{first_project['id']}/dashboard-templates",
            json={"name": "Owner Only View"},
        )
        self.assertEqual(template_response.status_code, 201)
        template = template_response.json()["dashboard_template"]

        second_list = self.client.get(f"/api/projects/{second_project['id']}/dashboard-templates")
        self.assertEqual(second_list.status_code, 200)
        self.assertEqual(second_list.json()["dashboard_templates"], [])

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_result_artifacts(self.store, artifact_root)
            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "admin@example.local", "admin pass")
            scoped_response = client.get(f"/api/dashboard-templates/{template['id']}/runs/{run['id']}/results")
            self.assertEqual(scoped_response.status_code, 404)

        client_user = self.create_user("client@example.local", role="client", password="client pass")
        client_session = TestClient(create_app(store=self.store, auth_enabled=True))
        self.login(client_session, "client@example.local", "client pass")
        self.assertEqual(
            client_session.get(f"/api/projects/{first_project['id']}/dashboard-templates").status_code,
            403,
        )
        self.assertEqual(client_user["role"], "client")

    def project_id_for_run(self, run_id):
        run = self.store.get_run(run_id)
        version = self.store.get_scenario_version(run["scenario_version_id"], include_document=False)
        scenario = self.store.get_scenario(version["scenario_id"])
        return scenario["project_id"]

    def create_user(self, email, *, role, password):
        return self.store.create_user(
            email=email,
            display_name=email,
            role=role,
            password_hash=hash_password(password),
            created_by="test",
        )

    def login(self, client, email, password):
        response = client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)


if __name__ == "__main__":
    unittest.main()
