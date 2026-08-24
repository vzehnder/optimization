import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import (
    delete_with_csrf,
    login_json_with_csrf,
    post_json_with_csrf,
    put_json_with_csrf,
)


class ConfigurationLayerAccessMigrationTests(unittest.TestCase):
    def test_legacy_client_role_is_rejected_after_cutover(self):
        store = AnalystStore("sqlite:///:memory:")
        try:
            with self.assertRaisesRegex(ValueError, "unsupported user role: client"):
                store.create_user(
                    email="legacy-client@example.local",
                    display_name="Legacy Client",
                    role="client",
                    password_hash="test-hash",
                )
        finally:
            store.close()

    def test_legacy_client_assignment_migrates_without_expanding_access(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "configuration-layer.sqlite3"
            database_url = f"sqlite:///{database_path}"
            legacy_connection = sqlite3.connect(database_path)
            legacy_connection.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    display_name TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    deactivated_at TEXT,
                    CHECK (role IN ('admin', 'analyst', 'client'))
                );
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL
                );
                CREATE TABLE project_client_access (
                    project_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    assigned_at TEXT NOT NULL,
                    assigned_by TEXT NOT NULL,
                    PRIMARY KEY (project_id, user_id),
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                INSERT INTO projects VALUES
                    (1, 'Assigned', '', '2026-08-22T12:00:00+00:00', 'admin'),
                    (2, 'Unassigned', '', '2026-08-22T12:00:00+00:00', 'admin');
                INSERT INTO users VALUES (
                    1, 'client@example.local', 'Legacy Client', 'client',
                    'test-hash', 1, '2026-08-22T12:00:00+00:00',
                    '2026-08-22T12:00:00+00:00', 'admin', NULL
                );
                INSERT INTO project_client_access VALUES (
                    1, 1, '2026-08-22T12:01:00+00:00',
                    'legacy-admin@example.local'
                );
                """
            )
            legacy_connection.close()

            migrated_store = AnalystStore(database_url)
            try:
                migrated_user = migrated_store.get_user(1)
                assignment = migrated_store.get_project_external_access(1, 1)

                self.assertEqual(migrated_user["role"], "external")
                self.assertTrue(assignment["portal_view"])
                self.assertFalse(assignment["operate"])
                self.assertEqual(
                    assignment["updated_by"], "legacy-admin@example.local"
                )
                self.assertTrue(
                    migrated_store.external_has_project_capability(
                        user_id=1,
                        project_id=1,
                        capability="portal_view",
                    )
                )
                self.assertFalse(
                    migrated_store.external_has_project_capability(
                        user_id=1,
                        project_id=1,
                        capability="operate",
                    )
                )
                self.assertFalse(
                    migrated_store.external_has_project_capability(
                        user_id=1,
                        project_id=2,
                        capability="portal_view",
                    )
                )
            finally:
                migrated_store.close()

            reopened_store = AnalystStore(database_url)
            try:
                self.assertEqual(
                    reopened_store.get_project_external_access(1, 1)["updated_by"],
                    "legacy-admin@example.local",
                )
            finally:
                reopened_store.close()


class ConfigurationLayerAccessApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.store.create_user(
            email="admin@example.local",
            display_name="Admin",
            role="admin",
            password_hash=hash_password("admin pass"),
        )
        response = login_json_with_csrf(
            self.client, "admin@example.local", "admin pass"
        )
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        self.store.close()

    def test_admin_can_create_an_external_identity(self):
        response = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "operator@example.local",
                "display_name": "External Operator",
                "role": "external",
                "password": "operator pass",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["role"], "external")

    def test_admin_api_rejects_the_legacy_client_role(self):
        response = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "legacy-client@example.local",
                "display_name": "Legacy Client",
                "role": "client",
                "password": "client pass",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_admin_can_manage_independent_project_capabilities(self):
        project = post_json_with_csrf(
            self.client,
            "/api/projects",
            {"name": "Configured Project", "description": ""},
        ).json()
        external_user = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "external@example.local",
                "display_name": "External User",
                "role": "external",
                "password": "external pass",
            },
        ).json()["user"]
        access_path = (
            f"/api/admin/projects/{project['id']}/external-access/"
            f"{external_user['id']}"
        )

        granted = put_json_with_csrf(
            self.client,
            access_path,
            {"portal_view": True, "operate": False},
        )
        self.assertEqual(granted.status_code, 200)
        self.assertEqual(
            {
                "portal_view": granted.json()["external_access"]["portal_view"],
                "operate": granted.json()["external_access"]["operate"],
                "updated_by": granted.json()["external_access"]["updated_by"],
            },
            {
                "portal_view": True,
                "operate": False,
                "updated_by": "admin@example.local",
            },
        )

        changed = put_json_with_csrf(
            self.client,
            access_path,
            {"portal_view": False, "operate": True},
        )
        self.assertEqual(changed.status_code, 200)
        listed = self.client.get(
            f"/api/admin/projects/{project['id']}/external-access"
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            [
                (
                    item["email"],
                    item["portal_view"],
                    item["operate"],
                    item["updated_by"],
                )
                for item in listed.json()["external_access"]
            ],
            [("external@example.local", False, True, "admin@example.local")],
        )

        revoked = delete_with_csrf(self.client, access_path)
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(
            {
                "portal_view": revoked.json()["external_access"]["portal_view"],
                "operate": revoked.json()["external_access"]["operate"],
                "updated_by": revoked.json()["external_access"]["updated_by"],
            },
            {
                "portal_view": False,
                "operate": False,
                "updated_by": "admin@example.local",
            },
        )

    def test_legacy_client_access_admin_endpoint_is_retired(self):
        project = post_json_with_csrf(
            self.client,
            "/api/projects",
            {"name": "Configured Project", "description": ""},
        ).json()

        response = self.client.get(
            f"/api/admin/projects/{project['id']}/client-access"
        )

        self.assertEqual(response.status_code, 404)

    def test_portal_view_changes_apply_on_the_next_external_request(self):
        project = post_json_with_csrf(
            self.client,
            "/api/projects",
            {"name": "Visible only with portal capability", "description": ""},
        ).json()
        external_user = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "viewer@example.local",
                "display_name": "External Viewer",
                "role": "external",
                "password": "viewer pass",
            },
        ).json()["user"]
        access_path = (
            f"/api/admin/projects/{project['id']}/external-access/"
            f"{external_user['id']}"
        )
        put_json_with_csrf(
            self.client,
            access_path,
            {"portal_view": False, "operate": True},
        )

        external_session = TestClient(
            create_app(store=self.store, auth_enabled=True)
        )
        login = login_json_with_csrf(
            external_session, "viewer@example.local", "viewer pass"
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["landing_path"], "/react/console")
        self.assertEqual(
            external_session.get("/api/client/projects").status_code,
            404,
        )

        put_json_with_csrf(
            self.client,
            access_path,
            {"portal_view": True, "operate": True},
        )
        visible_projects = external_session.get("/api/client/projects")
        self.assertEqual(visible_projects.status_code, 200)
        self.assertEqual(
            [
                item["branding"]["display_name"]
                for item in visible_projects.json()["projects"]
            ],
            ["Visible only with portal capability"],
        )
        self.assertEqual(
            external_session.get(
                f"/api/client/projects/{project['id']}/publications"
            ).status_code,
            200,
        )

        put_json_with_csrf(
            self.client,
            access_path,
            {"portal_view": False, "operate": False},
        )
        self.assertEqual(
            external_session.get("/api/client/projects").status_code,
            404,
        )
        self.assertEqual(
            external_session.get(
                f"/api/client/projects/{project['id']}/publications"
            ).status_code,
            404,
        )

    def test_operate_only_external_cannot_enter_the_portal_api(self):
        project = post_json_with_csrf(
            self.client,
            "/api/projects",
            {"name": "Operate only", "description": ""},
        ).json()
        external_user = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "operator@example.local",
                "display_name": "Operator",
                "role": "external",
                "password": "operator pass",
            },
        ).json()["user"]
        put_json_with_csrf(
            self.client,
            (
                f"/api/admin/projects/{project['id']}/external-access/"
                f"{external_user['id']}"
            ),
            {"portal_view": False, "operate": True},
        )
        external_session = TestClient(
            create_app(store=self.store, auth_enabled=True)
        )
        login_json_with_csrf(
            external_session,
            "operator@example.local",
            "operator pass",
        )

        response = external_session.get("/api/client/projects")

        self.assertEqual(response.status_code, 404)

    def test_analyst_cannot_administer_external_capabilities(self):
        project = post_json_with_csrf(
            self.client,
            "/api/projects",
            {"name": "Admin-only access", "description": ""},
        ).json()
        external_user = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "external@example.local",
                "display_name": "External",
                "role": "external",
                "password": "external pass",
            },
        ).json()["user"]
        self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        analyst_session = TestClient(
            create_app(store=self.store, auth_enabled=True)
        )
        login = login_json_with_csrf(
            analyst_session, "analyst@example.local", "analyst pass"
        )
        self.assertEqual(login.status_code, 200)
        access_path = (
            f"/api/admin/projects/{project['id']}/external-access/"
            f"{external_user['id']}"
        )

        self.assertEqual(
            analyst_session.get(
                f"/api/admin/projects/{project['id']}/external-access"
            ).status_code,
            403,
        )
        self.assertEqual(
            put_json_with_csrf(
                analyst_session,
                access_path,
                {"portal_view": True, "operate": True},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                f"/api/admin/projects/{project['id']}/external-access"
            ).json()["external_access"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
