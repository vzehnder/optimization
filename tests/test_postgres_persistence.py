import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app.auth import session_expires_at
from app.database import database_url_from_env
from app.persistence import AnalystStore


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class DatabaseEnvironmentTests(unittest.TestCase):
    def test_postgresql_url_is_built_from_separate_components(self):
        environment = {
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "5432",
            "DB_NAME": "energy_dispatch",
            "DB_USER": "energy_dispatch_user",
            "DB_PASSWORD": "reserved:/?#[]@!$&'()*+,;=",
        }
        with patch.dict(os.environ, environment, clear=True):
            database_url = database_url_from_env()

        self.assertEqual(
            database_url,
            "postgresql://energy_dispatch_user:"
            "reserved%3A%2F%3F%23%5B%5D%40%21%24%26%27%28%29%2A%2B%2C%3B%3D"
            "@127.0.0.1:5432/energy_dispatch",
        )

    def test_incomplete_postgresql_components_are_rejected(self):
        with patch.dict(os.environ, {"DB_HOST": "127.0.0.1"}, clear=True):
            with self.assertRaisesRegex(ValueError, "missing"):
                database_url_from_env()

    def test_explicit_database_url_remains_supported(self):
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "sqlite:///:memory:", "DB_HOST": "ignored"},
            clear=True,
        ):
            self.assertEqual(database_url_from_env(), "sqlite:///:memory:")


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "POSTGRES_TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
class PostgresPersistenceTests(unittest.TestCase):
    def test_core_workflow_uses_postgresql(self):
        store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        suffix = uuid.uuid4().hex
        try:
            admin = store.create_user(
                email=f"admin-{suffix}@example.com",
                password_hash="test-hash",
                role="admin",
            )
            session = store.create_auth_session(
                user_id=admin["id"],
                token_hash=f"token-{suffix}",
                expires_at=session_expires_at(),
            )
            self.assertEqual(session["user_id"], admin["id"])

            client = store.create_user(
                email=f"client-{suffix}@example.com",
                password_hash="test-hash",
                role="client",
            )
            project = store.create_project(name=f"PostgreSQL {suffix}")
            store.assign_client_to_project(project_id=project["id"], user_id=client["id"])
            store.assign_client_to_project(project_id=project["id"], user_id=client["id"])
            self.assertTrue(
                store.client_has_project_access(
                    project_id=project["id"],
                    user_id=client["id"],
                )
            )

            template = store.create_dashboard_template(
                project_id=project["id"],
                name="Default",
            )
            scenario = store.create_scenario(
                project_id=project["id"],
                name="Base",
            )
            document = {
                "schema_version": "bess_system_dispatch.v1",
                "case_name": f"postgres_{suffix}",
                "nodes": [],
                "time_series": [],
            }
            version = store.create_scenario_version(
                scenario_id=scenario["id"],
                system_case_json=document,
                validation_payload={"status": "ok"},
            )
            store.create_or_replace_scenario_draft(
                scenario_id=scenario["id"],
                source_version_id=version["id"],
                document={"case_name": "draft"},
            )

            with self.assertRaises(Exception):
                store.connection.execute(
                    "UPDATE scenario_versions SET case_name = ? WHERE id = ?",
                    ("mutated", version["id"]),
                )

            run = store.create_run(scenario_version_id=version["id"])
            store.mark_run_running(
                run["id"],
                workspace_path="workspace",
                input_snapshot_path="input.json",
            )
            run = store.mark_run_succeeded(
                run["id"],
                exit_code=0,
                stdout="{}",
                stderr="",
                success_payload={"status": "ok"},
                output_dir="outputs",
                summary_path="outputs/summary.json",
            )
            self.assertEqual(run["status"], "succeeded")

            with tempfile.TemporaryDirectory() as temporary_directory:
                artifact_path = Path(temporary_directory) / "summary.json"
                artifact_path.write_text("{}", encoding="utf-8")
                artifact = store.register_run_artifact(
                    run_id=run["id"],
                    artifact_type="summary_json",
                    path=str(artifact_path),
                    display_name="summary.json",
                    media_type="application/json",
                )
                updated_artifact = store.register_run_artifact(
                    run_id=run["id"],
                    artifact_type="summary_json",
                    path=str(artifact_path),
                    display_name="summary.json",
                    media_type="application/json",
                )
                self.assertEqual(updated_artifact["id"], artifact["id"])

            publication = store.create_publication_draft(
                run_id=run["id"],
                dashboard_template_id=template["id"],
                public_title="PostgreSQL result",
            )
            publication = store.publish_publication(publication["id"])
            self.assertEqual(publication["status"], "published")
        finally:
            store.close()
