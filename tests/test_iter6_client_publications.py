import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
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
            publication = analyst.post(
                f"/api/runs/{run['id']}/publications",
                json={
                    "dashboard_template_id": template["id"],
                    "public_title": "Download Review",
                    "allowed_artifact_types": ["summary_json"],
                },
            ).json()["publication"]
            analyst.post(f"/api/publications/{publication['id']}/publish")

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")
            page = client.get(f"/client/projects/{project_id}/publications/{publication['id']}")

            self.assertEqual(page.status_code, 200)
            self.assertIn("summary.json", page.text)
            self.assertIn(
                f"/client/projects/{project_id}/publications/{publication['id']}/artifacts/summary_json/download",
                page.text,
            )
            self.assertNotIn("dispatch.csv", page.text)
            self.assertNotIn("model_metadata.json", page.text)

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

            draft = analyst.post(
                f"/api/runs/{run['id']}/publications",
                json={
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
            draft = analyst.post(
                f"/api/runs/{run['id']}/publications",
                json={
                    "dashboard_template_id": template["id"],
                    "public_title": "June Dispatch Review",
                    "analyst_notes": "Approved for client review.",
                },
            ).json()["publication"]
            hidden_draft = analyst.post(
                f"/api/runs/{run['id']}/publications",
                json={
                    "dashboard_template_id": template["id"],
                    "public_title": "Draft Only",
                    "analyst_notes": "Still internal.",
                },
            ).json()["publication"]

            publish_response = analyst.post(f"/api/publications/{draft['id']}/publish")

            self.assertEqual(publish_response.status_code, 200)
            published = publish_response.json()["publication"]
            self.assertEqual(published["status"], "published")
            self.assertIsNotNone(published["published_at"])
            self.assertEqual(published["published_by"], "analyst@example.local")

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")
            project_page = client.get(f"/client/projects/{project_id}")

            self.assertEqual(project_page.status_code, 200)
            self.assertIn("June Dispatch Review", project_page.text)
            self.assertNotIn("Draft Only", project_page.text)
            self.assertIn(f"/client/projects/{project_id}/publications/{draft['id']}", project_page.text)
            self.assertNotIn(f"/client/projects/{project_id}/publications/{hidden_draft['id']}", project_page.text)

            publication_page = client.get(f"/client/projects/{project_id}/publications/{draft['id']}")

            self.assertEqual(publication_page.status_code, 200)
            self.assertIn("June Dispatch Review", publication_page.text)
            self.assertIn("Approved for client review.", publication_page.text)
            self.assertIn("Run Status", publication_page.text)
            self.assertIn("succeeded", publication_page.text)
            self.assertIn("Scenario Version", publication_page.text)
            self.assertIn("Objective Value", publication_page.text)
            self.assertIn("1250.5", publication_page.text)
            self.assertIn("Interactive Plots", publication_page.text)
            self.assertIn("System Dispatch", publication_page.text)
            self.assertNotIn("Asset Dispatch", publication_page.text)
            self.assertNotIn("Publication Drafts", publication_page.text)
            self.assertNotIn("Update Publication", publication_page.text)
            self.assertNotIn("Create Scenario", publication_page.text)

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
            publication = analyst.post(
                f"/api/runs/{run['id']}/publications",
                json={
                    "dashboard_template_id": template["id"],
                    "public_title": "Revocable Review",
                    "analyst_notes": "Visible while published.",
                },
            ).json()["publication"]
            analyst.post(f"/api/publications/{publication['id']}/publish")

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")
            self.assertEqual(
                client.get(f"/client/projects/{project_id}/publications/{publication['id']}").status_code,
                200,
            )

            unpublish_response = analyst.post(f"/api/publications/{publication['id']}/unpublish")

            self.assertEqual(unpublish_response.status_code, 200)
            unpublished = unpublish_response.json()["publication"]
            self.assertEqual(unpublished["status"], "unpublished")
            self.assertIsNotNone(unpublished["unpublished_at"])
            project_page = client.get(f"/client/projects/{project_id}")
            self.assertEqual(project_page.status_code, 200)
            self.assertNotIn("Revocable Review", project_page.text)
            self.assertEqual(
                client.get(f"/client/projects/{project_id}/publications/{publication['id']}").status_code,
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
            publication = analyst.post(
                f"/api/runs/{run['id']}/publications",
                json={
                    "dashboard_template_id": template["id"],
                    "public_title": "Previewable Review",
                    "analyst_notes": "Preview these assumptions.",
                },
            ).json()["publication"]

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")
            self.assertEqual(
                client.get(f"/client/projects/{project_id}/publications/{publication['id']}").status_code,
                404,
            )

            preview = analyst.get(f"/publications/{publication['id']}/preview")

            self.assertEqual(preview.status_code, 200)
            for snippet in [
                "Previewable Review",
                "Preview these assumptions.",
                "Run Status",
                "succeeded",
                "Objective Value",
                "Interactive Plots",
                "System Dispatch",
            ]:
                self.assertIn(snippet, preview.text)
            self.assertNotIn("Publication Drafts", preview.text)
            self.assertNotIn("Update Publication", preview.text)
            self.assertNotIn("Asset Dispatch", preview.text)
            self.assertEqual(client.get(f"/publications/{publication['id']}/preview").status_code, 403)

            analyst.post(f"/api/publications/{publication['id']}/publish")
            live = client.get(f"/client/projects/{project_id}/publications/{publication['id']}")
            self.assertEqual(live.status_code, 200)
            for snippet in ["Previewable Review", "Interactive Plots", "System Dispatch"]:
                self.assertIn(snippet, live.text)

    def test_run_page_exposes_preview_publish_and_unpublish_controls(self):
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
            publication = analyst.post(
                f"/api/runs/{run['id']}/publications",
                json={
                    "dashboard_template_id": template["id"],
                    "public_title": "Control Review",
                    "analyst_notes": "Use page controls.",
                },
            ).json()["publication"]

            draft_page = analyst.get(f"/runs/{run['id']}")
            self.assertEqual(draft_page.status_code, 200)
            self.assertIn(f"/publications/{publication['id']}/preview", draft_page.text)
            self.assertIn(f"/publications/{publication['id']}/publish", draft_page.text)
            self.assertIn("Publish Publication", draft_page.text)

            publish_response = analyst.post(
                f"/publications/{publication['id']}/publish",
                follow_redirects=False,
            )

            self.assertEqual(publish_response.status_code, 303)
            self.assertEqual(publish_response.headers["location"], f"/runs/{run['id']}")
            published_page = analyst.get(f"/runs/{run['id']}")
            self.assertIn("published", published_page.text)
            self.assertIn(f"/publications/{publication['id']}/unpublish", published_page.text)
            self.assertIn("Unpublish Publication", published_page.text)

            unpublish_response = analyst.post(
                f"/publications/{publication['id']}/unpublish",
                follow_redirects=False,
            )

            self.assertEqual(unpublish_response.status_code, 303)
            self.assertEqual(unpublish_response.headers["location"], f"/runs/{run['id']}")
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
        response = client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)


if __name__ == "__main__":
    unittest.main()
