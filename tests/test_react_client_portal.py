import unittest
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import (
    login_json_with_csrf,
    post_json_with_csrf,
    put_json_with_csrf,
)
from tests.test_results_review import create_completed_run_with_result_artifacts


class ReactClientPortalApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.analyst = self.create_user(
            "analyst@example.local",
            role="analyst",
            password="analyst pass",
        )
        self.client_user = self.create_user(
            "client@example.local",
            role="external",
            password="client pass",
        )
        self.other_client = self.create_user(
            "other-client@example.local",
            role="external",
            password="client pass",
        )

    def tearDown(self):
        self.store.close()

    def test_client_projects_api_lists_only_assigned_projects(self):
        assigned = self.store.create_project(
            name="Assigned Project",
            description="Visible to client",
        )
        unassigned = self.store.create_project(
            name="Unassigned Project",
            description="Hidden from client",
        )
        self.store.set_external_project_access(
            project_id=assigned["id"],
            user_id=self.client_user["id"],
            portal_view=True,
            operate=False,
            updated_by="analyst@example.local",
        )
        self.store.set_external_project_access(
            project_id=unassigned["id"],
            user_id=self.other_client["id"],
            portal_view=True,
            operate=False,
            updated_by="analyst@example.local",
        )
        client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.login(client, "client@example.local", "client pass")

        response = client.get("/api/client/projects")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                project["branding"]["display_name"]
                for project in response.json()["projects"]
            ],
            ["Assigned Project"],
        )

        internal = TestClient(create_app(store=self.store, auth_enabled=True))
        self.login(internal, "analyst@example.local", "analyst pass")
        self.assertEqual(internal.get("/api/client/projects").status_code, 403)
        self.assertEqual(
            TestClient(create_app(store=self.store, auth_enabled=True))
            .get("/api/client/projects")
            .status_code,
            401,
        )

    def test_client_publication_api_detail_downloads_and_revocations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_result_artifacts(self.store, artifact_root)
            project_id = self.store.get_run_lineage(run["id"])["project_id"]
            metadata_path = artifact_root / "runs" / "1" / "outputs" / "model_metadata.json"
            metadata_path.write_text('{"schema_version":"bess_system_dispatch.v1"}\n', encoding="utf-8")
            self.store.register_run_artifact(
                run_id=run["id"],
                artifact_type="model_metadata_json",
                path=str(metadata_path),
                display_name="model_metadata.json",
                media_type="application/json",
            )
            self.store.set_external_project_access(
                project_id=project_id,
                user_id=self.client_user["id"],
                portal_view=True,
                operate=False,
                updated_by="analyst@example.local",
            )
            template = self.store.create_dashboard_template(
                project_id=project_id,
                name="Client Summary",
                show_summary=True,
                show_price_chart=True,
                show_grid_chart=True,
                show_renewable_chart=False,
                show_bess_chart=False,
                show_hydro_chart=False,
                show_profit_chart=False,
                show_system_dispatch_table=True,
                show_asset_dispatch_table=False,
                table_preview_limit=1,
                created_by="analyst@example.local",
            )
            analyst = TestClient(
                create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True)
            )
            self.login(analyst, "analyst@example.local", "analyst pass")
            publication = post_json_with_csrf(
                analyst,
                f"/api/runs/{run['id']}/publications",
                {
                    "dashboard_template_id": template["id"],
                    "public_title": "Client Dispatch Review",
                    "analyst_notes": "Approved for client.",
                    "allowed_artifact_types": ["summary_json"],
                },
            ).json()["publication"]
            hidden_draft = post_json_with_csrf(
                analyst,
                f"/api/runs/{run['id']}/publications",
                {
                    "dashboard_template_id": template["id"],
                    "public_title": "Draft Only",
                    "analyst_notes": "Not shared.",
                    "allowed_artifact_types": ["summary_json"],
                },
            ).json()["publication"]
            post_json_with_csrf(analyst, f"/api/publications/{publication['id']}/publish")
            configure_portal = put_json_with_csrf(
                analyst,
                f"/api/projects/{project_id}/portal-configuration",
                {
                    "document": {
    "schema_version": "portal_config.v1",
    "display_name": "Portal cliente",
    "sections": {
        "kpis": {
            "enabled": True,
            "label": "Resumen",
            "items": [
                {
                    "id": "beneficio_total",
                    "path": "objective_value_usd",
                    "label": "Beneficio total",
                    "unit": "USD",
                    "decimals": 0,
                    "sign": "auto",
                    "emphasis": "strong",
                }
            ],
        },
        "charts": {"enabled": False, "label": "Resultados", "items": []},
        "tables": {"enabled": False, "label": "Detalle", "items": []},
        "downloads": {"enabled": True, "label": "Descargas"},
    },
},
                    "status": "active",
                    "expected_revision": 0,
                },
            )
            self.assertEqual(configure_portal.status_code, 200)

            client = TestClient(
                create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True)
            )
            self.login(client, "client@example.local", "client pass")
            publications_response = client.get(f"/api/client/projects/{project_id}/publications")

            self.assertEqual(publications_response.status_code, 200)
            publications_payload = publications_response.json()
            self.assertEqual(
                publications_payload["branding"],
                {"display_name": "Portal cliente", "logo_url": None},
            )
            self.assertEqual(
                [item["public_title"] for item in publications_payload["publications"]],
                ["Client Dispatch Review"],
            )

            detail_response = client.get(
                f"/api/client/projects/{project_id}/publications/{publication['id']}"
            )

            self.assertEqual(detail_response.status_code, 200)
            detail = detail_response.json()
            self.assertEqual(detail["publication"]["public_title"], "Client Dispatch Review")
            self.assertEqual(detail["publication"]["analyst_notes"], "Approved for client.")
            self.assertEqual(detail["results_state"], "available")
            self.assertEqual(
                detail["results_block"]["kpis"],
                [
                    {
                        "id": "beneficio_total",
                        "label": "Beneficio total",
                        "value": 1250.5,
                        "unit": "USD",
                        "decimals": 0,
                        "sign": "auto",
                        "emphasis": "strong",
                    }
                ],
            )
            self.assertGreater(detail["downloads"][0]["byte_size"], 0)
            self.assertEqual(
                detail["downloads"],
                [
                    {
                        "label": "summary.json",
                        "media_type": "application/json",
                        "byte_size": detail["downloads"][0]["byte_size"],
                        "download_url": (
                            f"/api/client/projects/{project_id}/publications/{publication['id']}"
                            "/artifacts/summary_json/download"
                        ),
                    }
                ],
            )
            self.assertEqual(
                client.get(
                    f"/api/client/projects/{project_id}/publications/{hidden_draft['id']}"
                ).status_code,
                404,
            )

            allowed = client.get(detail["downloads"][0]["download_url"])
            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(allowed.headers["content-type"], "application/json")
            self.assertIn('filename="summary.json"', allowed.headers["content-disposition"])
            self.assertEqual(
                client.get(
                    f"/api/client/projects/{project_id}/publications/{publication['id']}"
                    "/artifacts/dispatch_csv/download"
                ).status_code,
                404,
            )

            self.store.revoke_external_project_access(
                project_id=project_id,
                user_id=self.client_user["id"],
                updated_by="analyst@example.local",
            )
            self.assertEqual(client.get(f"/api/client/projects/{project_id}/publications").status_code, 404)
            self.assertEqual(
                client.get(
                    f"/api/client/projects/{project_id}/publications/{publication['id']}"
                ).status_code,
                404,
            )
            self.assertEqual(client.get(detail["downloads"][0]["download_url"]).status_code, 404)

            self.store.set_external_project_access(
                project_id=project_id,
                user_id=self.client_user["id"],
                portal_view=True,
                operate=False,
                updated_by="analyst@example.local",
            )
            post_json_with_csrf(analyst, f"/api/publications/{publication['id']}/unpublish")
            self.assertEqual(
                client.get(
                    f"/api/client/projects/{project_id}/publications/{publication['id']}"
                ).status_code,
                404,
            )
            self.assertEqual(client.get(detail["downloads"][0]["download_url"]).status_code, 404)

            self.store.set_user_active(self.client_user["id"], False, updated_by="analyst@example.local")
            self.assertEqual(client.get("/api/client/projects").status_code, 401)

    def create_user(self, email, *, role, password):
        return self.store.create_user(
            email=email,
            display_name=email,
            role=role,
            password_hash=hash_password(password),
            created_by="test",
        )

    def login(self, client, email, password):
        response = login_json_with_csrf(client, email, password)
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
