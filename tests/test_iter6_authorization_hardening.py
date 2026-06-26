import unittest
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf
from tests.test_results_review import create_completed_run_with_result_artifacts


class Iteration6AuthorizationHardeningTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.create_user("analyst@example.local", role="analyst", password="analyst pass")
        self.client_user = self.create_user("client@example.local", role="client", password="client pass")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))

    def tearDown(self):
        self.store.close()

    def test_client_can_read_own_session_but_not_analyst_apis(self):
        self.login(self.client, "client@example.local", "client pass")

        me_response = self.client.get("/api/auth/me")

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["user"]["email"], "client@example.local")
        self.assertEqual(me_response.json()["user"]["role"], "client")
        self.assertEqual(self.client.get("/api/projects").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/system-cases/validate",
                json={"system_case_json": "{}"},
            ).status_code,
            403,
        )

    def test_client_is_redirected_from_legacy_bookmarks_and_blocked_from_mutation_apis(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            run = create_completed_run_with_result_artifacts(self.store, artifact_root)
            lineage = self.store.get_run_lineage(run["id"])
            project_id = lineage["project_id"]
            scenario_id = lineage["scenario_id"]
            version_id = lineage["scenario_version_id"]
            template = self.store.create_dashboard_template(
                project_id=project_id,
                name="Auth Template",
                created_by="analyst@example.local",
            )
            publication = self.store.create_publication_draft(
                run_id=run["id"],
                dashboard_template_id=template["id"],
                public_title="Internal Draft",
                allowed_artifact_types=["summary_json"],
                created_by="analyst@example.local",
            )

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")

            for path, react_path in [
                (f"/projects/{project_id}", f"/react/projects/{project_id}"),
                (f"/scenarios/{scenario_id}", f"/react/scenarios/{scenario_id}"),
                (f"/scenarios/{scenario_id}/draft", f"/react/scenarios/{scenario_id}/draft"),
                (f"/runs/{run['id']}", f"/react/runs/{run['id']}"),
                ("/system-cases/validate", "/react/system"),
                (f"/publications/{publication['id']}/preview", f"/react/publications/{publication['id']}/preview"),
            ]:
                with self.subTest(path=path):
                    response = client.get(path, follow_redirects=False)
                    self.assertEqual(response.status_code, 303)
                    self.assertEqual(response.headers["location"], react_path)

            mutation_routes = [
                ("post", f"/api/scenarios/{scenario_id}/draft", {"json": {"document": {}}}),
                ("post", f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload", {}),
                ("post", f"/api/scenarios/{scenario_id}/draft/generated-system-case/validate", {}),
                ("post", f"/api/scenarios/{scenario_id}/draft/generated-system-case/promote", {}),
                ("post", f"/api/scenario-versions/{version_id}/runs", {}),
                ("get", f"/api/runs/{run['id']}/artifacts", {}),
                ("get", f"/api/runs/{run['id']}/results", {}),
                ("get", f"/api/run-artifacts/{self.store.list_run_artifacts(run['id'])[0]['id']}/download", {}),
            ]
            for method, path, kwargs in mutation_routes:
                with self.subTest(path=path):
                    response = getattr(client, method)(path, **kwargs)
                    self.assertEqual(response.status_code, 403)

    def test_project_publication_and_user_revocation_block_client_downloads_immediately(self):
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
                name="Download Template",
                created_by="analyst@example.local",
            )
            publication = self.store.create_publication_draft(
                run_id=run["id"],
                dashboard_template_id=template["id"],
                public_title="Revocation Review",
                allowed_artifact_types=["summary_json"],
                created_by="analyst@example.local",
            )
            self.store.publish_publication(publication["id"], published_by="analyst@example.local")
            download_path = (
                f"/client/projects/{project_id}/publications/{publication['id']}"
                "/artifacts/summary_json/download"
            )

            client = TestClient(create_app(store=self.store, artifact_root=artifact_root, auth_enabled=True))
            self.login(client, "client@example.local", "client pass")
            self.assertEqual(client.get(download_path).status_code, 200)

            self.store.remove_client_project_access(project_id=project_id, user_id=self.client_user["id"])
            self.assertEqual(client.get(download_path).status_code, 404)

            self.store.assign_client_to_project(
                project_id=project_id,
                user_id=self.client_user["id"],
                assigned_by="analyst@example.local",
            )
            self.assertEqual(client.get(download_path).status_code, 200)

            self.store.unpublish_publication(publication["id"], unpublished_by="analyst@example.local")
            self.assertEqual(client.get(download_path).status_code, 404)

            self.store.publish_publication(publication["id"], published_by="analyst@example.local")
            self.assertEqual(client.get(download_path).status_code, 200)

            self.store.set_user_active(self.client_user["id"], False, updated_by="analyst@example.local")
            deactivated_response = client.get(download_path, follow_redirects=False)
            self.assertEqual(deactivated_response.status_code, 303)
            self.assertEqual(
                deactivated_response.headers["location"],
                f"/react/client/projects/{project_id}/publications/{publication['id']}/artifacts/summary_json/download",
            )

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
