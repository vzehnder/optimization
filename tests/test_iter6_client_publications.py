import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf
from tests.test_results_review import create_completed_run_with_result_artifacts


class Iteration6ClientPublicationTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.create_user("analyst@example.local", role="analyst", password="analyst pass")
        self.client_user = self.create_user("client@example.local", role="client", password="client pass")

    def tearDown(self):
        self.store.close()

    def test_client_downloads_only_allowlisted_artifacts_for_active_assigned_publication(self):
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
            self.store.assign_client_to_project(
                project_id=project_id,
                user_id=self.client_user["id"],
                assigned_by="analyst@example.local",
            )
            template = self.store.create_dashboard_template(
                project_id=project_id,
                name="Download Template",
                created_by="analyst@example.local",
            )
            analyst = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(analyst, "analyst@example.local", "analyst pass")
            publication = post_json_with_csrf(
                analyst,
                f"/api/runs/{run['id']}/publications",
                {
                    "dashboard_template_id": template["id"],
                    "public_title": "Download Review",
                    "allowed_artifact_types": ["summary_json"],
                },
            ).json()["publication"]
            post_json_with_csrf(analyst, f"/api/publications/{publication['id']}/publish")

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")
            detail = client.get(f"/api/client/projects/{project_id}/publications/{publication['id']}")

            self.assertEqual(detail.status_code, 200)
            downloads = detail.json()["downloads"]
            self.assertEqual([download["display_name"] for download in downloads], ["summary.json"])
            self.assertEqual(
                downloads[0]["download_url"],
                f"/api/client/projects/{project_id}/publications/{publication['id']}/artifacts/summary_json/download",
            )

            allowed = client.get(
                f"/client/projects/{project_id}/publications/{publication['id']}/artifacts/summary_json/download"
            )

            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(allowed.headers["content-type"], "application/json")
            self.assertIn('filename="summary.json"', allowed.headers["content-disposition"])
            self.assertEqual(allowed.json()["case_name"], "hybrid_system")
            self.assertEqual(
                client.get(
                    f"/client/projects/{project_id}/publications/{publication['id']}/artifacts/dispatch_csv/download"
                ).status_code,
                404,
            )
            self.assertEqual(
                client.get(
                    f"/client/projects/{project_id}/publications/{publication['id']}/artifacts/model_metadata_json/download"
                ).status_code,
                404,
            )

            self.create_user("other-client@example.local", role="client", password="client pass")
            unassigned = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(unassigned, "other-client@example.local", "client pass")
            self.assertEqual(
                unassigned.get(
                    f"/client/projects/{project_id}/publications/{publication['id']}/artifacts/summary_json/download"
                ).status_code,
                404,
            )

            draft = post_json_with_csrf(
                analyst,
                f"/api/runs/{run['id']}/publications",
                {
                    "dashboard_template_id": template["id"],
                    "public_title": "Draft Download Review",
                    "allowed_artifact_types": ["summary_json"],
                },
            ).json()["publication"]
            self.assertEqual(
                client.get(
                    f"/client/projects/{project_id}/publications/{draft['id']}/artifacts/summary_json/download"
                ).status_code,
                404,
            )
            anonymous = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.assertEqual(
                anonymous.get(
                    f"/client/projects/{project_id}/publications/{publication['id']}/artifacts/summary_json/download",
                    follow_redirects=False,
                ).status_code,
                303,
            )

    def test_published_publication_appears_in_assigned_client_portal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_result_artifacts(self.store, artifact_root)
            project_id = self.store.get_run_lineage(run["id"])["project_id"]
            self.store.assign_client_to_project(
                project_id=project_id,
                user_id=self.client_user["id"],
                assigned_by="analyst@example.local",
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
            analyst = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(analyst, "analyst@example.local", "analyst pass")
            draft = post_json_with_csrf(
                analyst,
                f"/api/runs/{run['id']}/publications",
                {
                    "dashboard_template_id": template["id"],
                    "public_title": "June Dispatch Review",
                    "analyst_notes": "Approved for client review.",
                },
            ).json()["publication"]
            hidden_draft = post_json_with_csrf(
                analyst,
                f"/api/runs/{run['id']}/publications",
                {
                    "dashboard_template_id": template["id"],
                    "public_title": "Draft Only",
                    "analyst_notes": "Still internal.",
                },
            ).json()["publication"]

            publish_response = post_json_with_csrf(analyst, f"/api/publications/{draft['id']}/publish")

            self.assertEqual(publish_response.status_code, 200)
            published = publish_response.json()["publication"]
            self.assertEqual(published["status"], "published")
            self.assertIsNotNone(published["published_at"])
            self.assertEqual(published["published_by"], "analyst@example.local")

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")
            project_page = client.get(f"/api/client/projects/{project_id}/publications")

            self.assertEqual(project_page.status_code, 200)
            publication_titles = [
                publication["public_title"]
                for publication in project_page.json()["publications"]
            ]
            self.assertEqual(publication_titles, ["June Dispatch Review"])

            publication_page = client.get(f"/api/client/projects/{project_id}/publications/{draft['id']}")

            self.assertEqual(publication_page.status_code, 200)
            detail = publication_page.json()
            self.assertEqual(detail["publication"]["public_title"], "June Dispatch Review")
            self.assertEqual(detail["publication"]["analyst_notes"], "Approved for client review.")
            self.assertEqual(detail["run"]["status"], "succeeded")
            self.assertEqual(detail["results"]["summary"]["objective_value_usd"], 1250.5)
            self.assertIsNotNone(detail["results"]["dispatch_table"])
            self.assertIsNone(detail["results"]["asset_dispatch_table"])

    def test_unpublishing_publication_removes_client_access_immediately(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_result_artifacts(self.store, artifact_root)
            project_id = self.store.get_run_lineage(run["id"])["project_id"]
            self.store.assign_client_to_project(
                project_id=project_id,
                user_id=self.client_user["id"],
                assigned_by="analyst@example.local",
            )
            template = self.store.create_dashboard_template(
                project_id=project_id,
                name="Client Summary",
                created_by="analyst@example.local",
            )
            analyst = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(analyst, "analyst@example.local", "analyst pass")
            publication = post_json_with_csrf(
                analyst,
                f"/api/runs/{run['id']}/publications",
                {
                    "dashboard_template_id": template["id"],
                    "public_title": "Revocable Review",
                    "analyst_notes": "Visible while published.",
                },
            ).json()["publication"]
            post_json_with_csrf(analyst, f"/api/publications/{publication['id']}/publish")

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")
            self.assertEqual(
                client.get(f"/api/client/projects/{project_id}/publications/{publication['id']}").status_code,
                200,
            )

            unpublish_response = post_json_with_csrf(analyst, f"/api/publications/{publication['id']}/unpublish")

            self.assertEqual(unpublish_response.status_code, 200)
            unpublished = unpublish_response.json()["publication"]
            self.assertEqual(unpublished["status"], "unpublished")
            self.assertIsNotNone(unpublished["unpublished_at"])
            project_page = client.get(f"/api/client/projects/{project_id}/publications")
            self.assertEqual(project_page.status_code, 200)
            self.assertEqual(project_page.json()["publications"], [])
            self.assertEqual(
                client.get(f"/api/client/projects/{project_id}/publications/{publication['id']}").status_code,
                404,
            )

    def test_internal_preview_uses_client_renderer_before_publication(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_result_artifacts(self.store, artifact_root)
            project_id = self.store.get_run_lineage(run["id"])["project_id"]
            self.store.assign_client_to_project(
                project_id=project_id,
                user_id=self.client_user["id"],
                assigned_by="analyst@example.local",
            )
            template = self.store.create_dashboard_template(
                project_id=project_id,
                name="Preview Template",
                show_summary=True,
                show_price_chart=False,
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
            analyst = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(analyst, "analyst@example.local", "analyst pass")
            publication = post_json_with_csrf(
                analyst,
                f"/api/runs/{run['id']}/publications",
                {
                    "dashboard_template_id": template["id"],
                    "public_title": "Previewable Review",
                    "analyst_notes": "Preview these assumptions.",
                },
            ).json()["publication"]

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")
            self.assertEqual(
                client.get(f"/api/client/projects/{project_id}/publications/{publication['id']}").status_code,
                404,
            )

            preview = analyst.get(f"/api/publications/{publication['id']}/preview")

            self.assertEqual(preview.status_code, 200)
            preview_body = preview.json()
            self.assertEqual(preview_body["publication"]["public_title"], "Previewable Review")
            self.assertEqual(preview_body["publication"]["analyst_notes"], "Preview these assumptions.")
            self.assertEqual(preview_body["run"]["status"], "succeeded")
            self.assertIsNotNone(preview_body["results"]["dispatch_table"])
            self.assertIsNone(preview_body["results"]["asset_dispatch_table"])
            self.assertEqual(client.get(f"/api/publications/{publication['id']}/preview").status_code, 403)

            post_json_with_csrf(analyst, f"/api/publications/{publication['id']}/publish")
            live = client.get(f"/api/client/projects/{project_id}/publications/{publication['id']}")
            self.assertEqual(live.status_code, 200)
            self.assertEqual(live.json()["publication"]["public_title"], "Previewable Review")

    def test_publication_api_exposes_preview_publish_and_unpublish_controls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_result_artifacts(self.store, artifact_root)
            project_id = self.store.get_run_lineage(run["id"])["project_id"]
            template = self.store.create_dashboard_template(
                project_id=project_id,
                name="Client Summary",
                created_by="analyst@example.local",
            )
            analyst = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(analyst, "analyst@example.local", "analyst pass")
            publication = post_json_with_csrf(
                analyst,
                f"/api/runs/{run['id']}/publications",
                {
                    "dashboard_template_id": template["id"],
                    "public_title": "Control Review",
                    "analyst_notes": "Use page controls.",
                },
            ).json()["publication"]

            list_response = analyst.get(f"/api/runs/{run['id']}/publications")
            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(list_response.json()["publications"][0]["id"], publication["id"])

            publish_response = post_json_with_csrf(analyst, f"/api/publications/{publication['id']}/publish")
            self.assertEqual(publish_response.status_code, 200)
            self.assertEqual(publish_response.json()["publication"]["status"], "published")

            unpublish_response = post_json_with_csrf(analyst, f"/api/publications/{publication['id']}/unpublish")
            self.assertEqual(unpublish_response.status_code, 200)
            unpublished = self.store.get_publication(publication["id"])
            self.assertEqual(unpublished["status"], "unpublished")

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
