import unittest

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf, put_json_with_csrf


class Iteration6PublicationDraftTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.create_user("analyst@example.local", role="analyst", password="analyst pass")
        self.login(self.client, "analyst@example.local", "analyst pass")

    def tearDown(self):
        self.store.close()

    def test_internal_user_can_create_publication_draft_from_succeeded_run(self):
        project, scenario, version, run = self.create_succeeded_run()
        template = self.store.create_dashboard_template(
            project_id=project["id"],
            name="Client Summary",
            created_by="analyst@example.local",
        )
        before_version = self.store.get_scenario_version(version["id"])
        before_run = self.store.get_run(run["id"])

        response = post_json_with_csrf(
            self.client,
            f"/api/runs/{run['id']}/publications",
            {
                "dashboard_template_id": template["id"],
                "public_title": "June Dispatch Review",
                "analyst_notes": "Approved for client review.",
            },
        )

        self.assertEqual(response.status_code, 201)
        publication = response.json()["publication"]
        self.assertEqual(publication["project_id"], project["id"])
        self.assertEqual(publication["scenario_id"], scenario["id"])
        self.assertEqual(publication["scenario_version_id"], version["id"])
        self.assertEqual(publication["run_id"], run["id"])
        self.assertEqual(publication["dashboard_template_id"], template["id"])
        self.assertEqual(publication["public_title"], "June Dispatch Review")
        self.assertEqual(publication["analyst_notes"], "Approved for client review.")
        self.assertEqual(publication["status"], "draft")
        self.assertEqual(
            publication["allowed_artifact_types"],
            ["summary_json", "dispatch_csv", "asset_dispatch_csv"],
        )
        self.assertEqual(publication["created_by"], "analyst@example.local")
        self.assertEqual(publication["updated_by"], "analyst@example.local")
        self.assertIsNone(publication["published_at"])
        self.assertIsNone(publication["published_by"])
        self.assertIsNone(publication["unpublished_at"])
        self.assertEqual(self.store.get_scenario_version(version["id"]), before_version)
        self.assertEqual(self.store.get_run(run["id"]), before_run)

        list_response = self.client.get(f"/api/runs/{run['id']}/publications")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            [(item["id"], item["public_title"]) for item in list_response.json()["publications"]],
            [(publication["id"], "June Dispatch Review")],
        )

    def test_internal_user_can_edit_publication_draft_fields_and_allowlist(self):
        project, _scenario, version, run = self.create_succeeded_run()
        first_template = self.store.create_dashboard_template(
            project_id=project["id"],
            name="Initial View",
            created_by="analyst@example.local",
        )
        second_template = self.store.create_dashboard_template(
            project_id=project["id"],
            name="Technical Appendix View",
            show_price_chart=False,
            created_by="analyst@example.local",
        )
        publication = post_json_with_csrf(
            self.client,
            f"/api/runs/{run['id']}/publications",
            {
                "dashboard_template_id": first_template["id"],
                "public_title": "Initial Title",
                "analyst_notes": "Initial notes",
            },
        ).json()["publication"]
        before_version = self.store.get_scenario_version(version["id"])
        before_run = self.store.get_run(run["id"])

        response = put_json_with_csrf(
            self.client,
            f"/api/publications/{publication['id']}",
            {
                "dashboard_template_id": second_template["id"],
                "public_title": "Updated Client Title",
                "analyst_notes": "Updated assumptions.",
                "allowed_artifact_types": ["summary_json", "model_metadata_json"],
            },
        )

        self.assertEqual(response.status_code, 200)
        updated = response.json()["publication"]
        self.assertEqual(updated["id"], publication["id"])
        self.assertEqual(updated["dashboard_template_id"], second_template["id"])
        self.assertEqual(updated["public_title"], "Updated Client Title")
        self.assertEqual(updated["analyst_notes"], "Updated assumptions.")
        self.assertEqual(updated["allowed_artifact_types"], ["summary_json", "model_metadata_json"])
        self.assertEqual(updated["status"], "draft")
        self.assertEqual(updated["created_at"], publication["created_at"])
        self.assertEqual(updated["created_by"], "analyst@example.local")
        self.assertEqual(updated["updated_by"], "analyst@example.local")
        self.assertEqual(self.store.get_scenario_version(version["id"]), before_version)
        self.assertEqual(self.store.get_run(run["id"]), before_run)

    def test_publication_api_creates_draft_with_default_downloads(self):
        project, _scenario, _version, run = self.create_succeeded_run()
        template = self.store.create_dashboard_template(
            project_id=project["id"],
            name="Client Portal View",
            created_by="analyst@example.local",
        )

        artifacts = self.store.list_run_artifacts(run["id"])
        self.assertEqual(
            [artifact["artifact_type"] for artifact in artifacts],
            [
                "input_snapshot",
                "stdout_log",
                "stderr_log",
                "summary_json",
                "dispatch_csv",
                "asset_dispatch_csv",
                "model_metadata_json",
            ],
        )

        response = post_json_with_csrf(
            self.client,
            f"/api/runs/{run['id']}/publications",
            {
                "dashboard_template_id": template["id"],
                "public_title": "Board Review",
                "analyst_notes": "Visible notes.",
                "allowed_artifact_types": ["summary_json", "dispatch_csv", "asset_dispatch_csv"],
            },
        )

        self.assertEqual(response.status_code, 201)
        publication = response.json()["publication"]
        self.assertEqual(publication["public_title"], "Board Review")
        self.assertEqual(publication["status"], "draft")
        self.assertEqual(publication["allowed_artifact_types"], ["summary_json", "dispatch_csv", "asset_dispatch_csv"])

    def test_only_internal_users_can_publish_succeeded_runs_with_project_template(self):
        project, _scenario, version, succeeded_run = self.create_succeeded_run()
        template = self.store.create_dashboard_template(
            project_id=project["id"],
            name="Valid Template",
            created_by="analyst@example.local",
        )
        queued_run = self.store.create_run(scenario_version_id=version["id"], triggered_by="test")
        running_run = self.store.create_run(scenario_version_id=version["id"], triggered_by="test")
        self.store.mark_run_running(
            running_run["id"],
            workspace_path="artifacts/runs/running",
            input_snapshot_path="artifacts/runs/running/input/system_case.json",
        )
        failed_run = self.store.create_run(scenario_version_id=version["id"], triggered_by="test")
        self.store.mark_run_failed(
            failed_run["id"],
            exit_code=1,
            stdout="",
            stderr="failed",
            error_payload={"status": "error"},
        )

        for run in [queued_run, running_run, failed_run]:
            response = post_json_with_csrf(
                self.client,
                f"/api/runs/{run['id']}/publications",
                {
                    "dashboard_template_id": template["id"],
                    "public_title": "Blocked Publication",
                },
            )
            self.assertEqual(response.status_code, 400)

        other_project = self.store.create_project(name="Other Project", created_by="test")
        other_template = self.store.create_dashboard_template(
            project_id=other_project["id"],
            name="Other Project Template",
            created_by="test",
        )
        scoped_response = post_json_with_csrf(
            self.client,
            f"/api/runs/{succeeded_run['id']}/publications",
            {
                "dashboard_template_id": other_template["id"],
                "public_title": "Wrong Template",
            },
        )
        self.assertEqual(scoped_response.status_code, 404)

        self.create_user("client@example.local", role="client", password="client pass")
        client_session = TestClient(create_app(store=self.store, auth_enabled=True))
        self.login(client_session, "client@example.local", "client pass")
        client_response = post_json_with_csrf(
            client_session,
            f"/api/runs/{succeeded_run['id']}/publications",
            {
                "dashboard_template_id": template["id"],
                "public_title": "Client Attempt",
            },
        )
        self.assertEqual(client_response.status_code, 403)

    def create_succeeded_run(self):
        project = self.store.create_project(name="Publication Project", created_by="test")
        scenario = self.store.create_scenario(project_id=project["id"], name="Base Case", created_by="test")
        version = self.store.create_scenario_version(
            scenario_id=scenario["id"],
            system_case_json={
                "schema_version": "bess_system_dispatch.v1",
                "case_name": "publication_case",
                "nodes": [],
                "time_series": [],
            },
            validation_payload={"status": "ok"},
            created_by="test",
        )
        run = self.store.create_run(scenario_version_id=version["id"], triggered_by="test")
        run = self.store.mark_run_succeeded(
            run["id"],
            exit_code=0,
            stdout="{}",
            stderr="",
            success_payload={"termination_status": "OPTIMAL"},
            output_dir="artifacts/runs/1/outputs",
            summary_path="artifacts/runs/1/outputs/summary.json",
        )
        for artifact_type in [
            "input_snapshot",
            "stdout_log",
            "stderr_log",
            "summary_json",
            "dispatch_csv",
            "asset_dispatch_csv",
            "model_metadata_json",
        ]:
            self.store.register_run_artifact(
                run_id=run["id"],
                artifact_type=artifact_type,
                path=f"artifacts/runs/1/{artifact_type}",
                display_name=f"{artifact_type}.txt",
                media_type="text/plain",
                byte_size=1,
            )
        return project, scenario, version, run

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
