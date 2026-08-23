import os
import re
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.auth import session_expires_at
from app.database import ID_TABLES, database_url_from_env, postgres_schema_from_sqlite
from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class IdTableRegistrationTests(unittest.TestCase):
    def test_all_autoincrement_id_tables_are_registered_for_postgres_returning(self):
        # On PostgreSQL the compatibility layer only appends ``RETURNING id`` for
        # tables listed in ID_TABLES. A table with an autoincrement id that is
        # missing from the set silently returns lastrowid 0, which breaks any
        # foreign key that references the freshly inserted row.
        source = (
            Path(__file__).resolve().parents[1] / "app" / "persistence.py"
        ).read_text(encoding="utf-8")
        autoincrement_tables = set(
            re.findall(
                r"CREATE TABLE IF NOT EXISTS ([a-z_]+)\s*\(\s*"
                r"id INTEGER PRIMARY KEY AUTOINCREMENT",
                source,
            )
        )
        self.assertTrue(autoincrement_tables, "no autoincrement id tables found")
        missing = sorted(autoincrement_tables - ID_TABLES)
        self.assertEqual(missing, [], f"tables missing from ID_TABLES: {missing}")


class DatabaseEnvironmentTests(unittest.TestCase):
    def test_sqlite_blob_columns_translate_to_postgresql_bytea(self):
        schema = postgres_schema_from_sqlite(
            "CREATE TABLE portal_configurations (logo_bytes BLOB);"
        )

        self.assertIn("logo_bytes BYTEA", schema)
        self.assertNotIn("logo_bytes BLOB", schema)

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
    def test_portal_logo_round_trips_as_bytea(self):
        store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        project_id = 0
        try:
            project = store.create_project(name=f"Portal brand {uuid.uuid4().hex}")
            project_id = project["id"]

            saved = store.save_portal_logo(
                project_id,
                logo_bytes=b"\x89PNG\r\n\x1a\npostgres-logo",
                logo_media_type="image/png",
                expected_revision=0,
                updated_by_user_id=None,
            )

            self.assertEqual(saved["logo_bytes"], b"\x89PNG\r\n\x1a\npostgres-logo")
            self.assertEqual(saved["logo_media_type"], "image/png")
            self.assertEqual(saved["revision"], 1)
        finally:
            if project_id:
                store.delete_project(project_id)
            store.close()

    def test_configuration_access_migration_is_idempotent(self):
        suffix = uuid.uuid4().hex
        store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        project_id = 0
        client_id = 0
        try:
            project = store.create_project(name=f"External access {suffix}")
            legacy_client = store.create_user(
                email=f"legacy-client-{suffix}@example.com",
                password_hash="test-hash",
                role="external",
            )
            store.set_external_project_access(
                project_id=project["id"],
                user_id=legacy_client["id"],
                portal_view=True,
                operate=False,
                updated_by=f"admin-{suffix}@example.com",
            )
            store.connection.execute(
                "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check"
            )
            store.connection.execute(
                "UPDATE users SET role = 'client' WHERE id = ?",
                (legacy_client["id"],),
            )
            store.connection.commit()
            project_id = project["id"]
            client_id = legacy_client["id"]
        finally:
            store.close()

        reopened_store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        try:
            self.assertEqual(reopened_store.get_user(client_id)["role"], "external")
            assignment = reopened_store.get_project_external_access(
                project_id, client_id
            )
            self.assertTrue(assignment["portal_view"])
            self.assertFalse(assignment["operate"])
            self.assertEqual(
                assignment["updated_by"], f"admin-{suffix}@example.com"
            )
        finally:
            reopened_store.close()

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
                role="external",
            )
            project = store.create_project(name=f"PostgreSQL {suffix}")
            store.set_external_project_access(
                project_id=project["id"],
                user_id=client["id"],
                portal_view=True,
                operate=False,
                updated_by="test",
            )
            store.set_external_project_access(
                project_id=project["id"],
                user_id=client["id"],
                portal_view=True,
                operate=False,
                updated_by="test",
            )
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

    def test_upsert_case_time_series_binding_handles_null_and_scoped_entity_columns(self):
        # psycopg cannot infer a parameter's type from a bare ``? IS NULL``
        # comparison with no other typed context in the same statement, so an
        # unscoped (entity_type/entity_id both NULL) upsert on PostgreSQL used
        # to raise ``psycopg.errors.IndeterminateDatatype: could not determine
        # data type of parameter``. SQLite never hit this because it infers
        # untyped parameters permissively, so this regression only reproduces
        # against a real PostgreSQL backend.
        store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        suffix = uuid.uuid4().hex
        try:
            project = store.create_project(name=f"PostgreSQL entity scope {suffix}")
            scenario = store.create_scenario(project_id=project["id"], name="Base")
            case = store.get_or_create_case_for_scenario(scenario["id"])
            variant = store.get_or_create_default_input_variant(case["id"])

            rows = [
                {
                    "period_start": (datetime(2026, 1, 1) + timedelta(hours=hour)).isoformat(),
                    "hours": "1.0",
                    "value": str(50.0 + hour),
                }
                for hour in range(2)
            ]
            prepared = prepare_time_series_catalog_import(
                rows=rows,
                request=CatalogImportRequest(
                    set_name=f"Price {suffix}",
                    version_label="v1",
                    data_kind="real",
                    timezone="America/Santiago",
                    timestamp_column="period_start",
                    duration_hours_column="hours",
                    signal_mappings=[
                        CatalogSignalMappingRequest(
                            source_column="value", signal_key="price_usd_per_mwh"
                        ),
                    ],
                ),
            )
            time_series_set = store.import_time_series_catalog_set(
                scenario_id=scenario["id"],
                source={
                    "id": f"csv_source_{suffix}",
                    "original_filename": "price.csv",
                    "media_type": "text/csv",
                    "checksum": f"sha256:{suffix}",
                },
                prepared_import=prepared,
            )

            unscoped = store.upsert_case_time_series_binding(
                case_input_variant_id=variant["id"],
                signal_key="price_usd_per_mwh",
                time_series_set_id=time_series_set["id"],
            )
            self.assertIsNone(unscoped["entity_type"])
            self.assertIsNone(unscoped["entity_id"])

            # Re-upserting the same unscoped binding exercises the
            # ``entity_type IS NULL AND ? IS NULL`` existence-check branch a
            # second time, matching the existing row instead of inserting.
            rebind = store.upsert_case_time_series_binding(
                case_input_variant_id=variant["id"],
                signal_key="price_usd_per_mwh",
                time_series_set_id=time_series_set["id"],
            )
            self.assertEqual(rebind["id"], unscoped["id"])

            scoped = store.upsert_case_time_series_binding(
                case_input_variant_id=variant["id"],
                signal_key="load_demand_mw",
                entity_type="component:load",
                entity_id="load_1",
                time_series_set_id=time_series_set["id"],
            )
            self.assertEqual(scoped["entity_type"], "component:load")
            self.assertEqual(scoped["entity_id"], "load_1")
            self.assertNotEqual(scoped["id"], unscoped["id"])
        finally:
            store.close()
