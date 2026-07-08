import unittest

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import delete_with_csrf, login_json_with_csrf, post_json_with_csrf


class Iteration6ProjectAccessTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.create_user("admin@example.local", role="admin", password="admin pass")
        self.login("admin@example.local", "admin pass")

    def tearDown(self):
        self.store.close()

    def test_admin_can_create_list_and_deactivate_users(self):
        create_response = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "client@example.local",
                "display_name": "Client User",
                "role": "client",
                "password": "client pass",
            },
        )

        self.assertEqual(create_response.status_code, 201)
        created_user = create_response.json()["user"]
        self.assertEqual(created_user["email"], "client@example.local")
        self.assertEqual(created_user["display_name"], "Client User")
        self.assertEqual(created_user["role"], "client")
        self.assertTrue(created_user["is_active"])
        self.assertNotIn("password_hash", created_user)
        stored_user = self.store.get_user(created_user["id"])
        self.assertNotEqual(stored_user["password_hash"], "client pass")
        self.assertTrue(stored_user["password_hash"].startswith("pbkdf2_sha256$"))

        analyst_response = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "analyst@example.local",
                "display_name": "Analyst User",
                "role": "analyst",
                "password": "analyst pass",
            },
        )
        self.assertEqual(analyst_response.status_code, 201)
        self.assertEqual(analyst_response.json()["user"]["role"], "analyst")
        second_admin_response = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "second-admin@example.local",
                "display_name": "Second Admin",
                "role": "admin",
                "password": "admin pass",
            },
        )
        self.assertEqual(second_admin_response.status_code, 201)
        self.assertEqual(second_admin_response.json()["user"]["role"], "admin")

        list_response = self.client.get("/api/admin/users")
        self.assertEqual(list_response.status_code, 200)
        listed_users = list_response.json()["users"]
        self.assertEqual(
            [(user["email"], user["role"], user["is_active"]) for user in listed_users],
            [
                ("admin@example.local", "admin", True),
                ("client@example.local", "client", True),
                ("analyst@example.local", "analyst", True),
                ("second-admin@example.local", "admin", True),
            ],
        )
        self.assertTrue(all("password_hash" not in user for user in listed_users))

        active_client_session = TestClient(create_app(store=self.store, auth_enabled=True))
        active_login = login_json_with_csrf(active_client_session, "client@example.local", "client pass")
        self.assertEqual(active_login.status_code, 200)
        self.assertEqual(active_login.json()["redirect_path"], "/react/client")

        deactivate_response = post_json_with_csrf(
            self.client,
            f"/api/admin/users/{created_user['id']}/deactivate",
        )
        self.assertEqual(deactivate_response.status_code, 200)
        self.assertFalse(deactivate_response.json()["user"]["is_active"])
        self.assertIsNone(active_client_session.get("/api/auth/me").json()["user"])

        logged_out_client = TestClient(create_app(store=self.store, auth_enabled=True))
        login_response = login_json_with_csrf(logged_out_client, "client@example.local", "client pass")
        self.assertEqual(login_response.status_code, 401)

    def test_admin_user_creation_rejects_invalid_and_duplicate_input_safely(self):
        invalid_email = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "not-an-email",
                "display_name": "Invalid User",
                "role": "client",
                "password": "client pass",
            },
        )
        self.assertEqual(invalid_email.status_code, 400)
        self.assertEqual(invalid_email.json()["detail"], "valid email is required")

        first_create = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "client@example.local",
                "display_name": "Client User",
                "role": "client",
                "password": "client pass",
            },
        )
        self.assertEqual(first_create.status_code, 201)

        duplicate = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": "CLIENT@example.local",
                "display_name": "Duplicate User",
                "role": "client",
                "password": "client pass",
            },
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["detail"], "email already exists")

    def test_admin_assigns_clients_to_projects_and_client_portal_filters_access(self):
        first_project = post_json_with_csrf(
            self.client,
            "/api/projects",
            {"name": "Assigned Project", "description": "Client can see this"},
        ).json()
        second_project = post_json_with_csrf(
            self.client,
            "/api/projects",
            {"name": "Portfolio Project", "description": "Same client, second project"},
        ).json()
        unassigned_project = post_json_with_csrf(
            self.client,
            "/api/projects",
            {"name": "Private Project", "description": "Client must not see this"},
        ).json()
        first_client = self.create_client_user("client@example.local")
        second_client = self.create_client_user("other-client@example.local")

        assign_first = post_json_with_csrf(
            self.client,
            f"/api/admin/projects/{first_project['id']}/client-access",
            {"user_id": first_client["id"]},
        )
        self.assertEqual(assign_first.status_code, 201)
        assign_second = post_json_with_csrf(
            self.client,
            f"/api/admin/projects/{second_project['id']}/client-access",
            {"user_id": first_client["id"]},
        )
        self.assertEqual(assign_second.status_code, 201)
        assign_shared = post_json_with_csrf(
            self.client,
            f"/api/admin/projects/{first_project['id']}/client-access",
            {"user_id": second_client["id"]},
        )
        self.assertEqual(assign_shared.status_code, 201)

        access_response = self.client.get(f"/api/admin/projects/{first_project['id']}/client-access")
        self.assertEqual(access_response.status_code, 200)
        self.assertEqual(
            [assignment["email"] for assignment in access_response.json()["client_access"]],
            ["client@example.local", "other-client@example.local"],
        )

        client_session = TestClient(create_app(store=self.store, auth_enabled=True))
        login_response = login_json_with_csrf(client_session, "client@example.local", "client pass")
        self.assertEqual(login_response.status_code, 200)

        portal_response = client_session.get("/api/client/projects")
        self.assertEqual(portal_response.status_code, 200)
        portal_projects = [project["name"] for project in portal_response.json()["projects"]]
        self.assertEqual(portal_projects, ["Assigned Project", "Portfolio Project"])

        assigned_detail = client_session.get(f"/api/client/projects/{first_project['id']}/publications")
        self.assertEqual(assigned_detail.status_code, 200)
        self.assertEqual(assigned_detail.json()["project"]["name"], "Assigned Project")

        guessed_detail = client_session.get(f"/api/client/projects/{unassigned_project['id']}/publications")
        self.assertEqual(guessed_detail.status_code, 404)

        remove_response = delete_with_csrf(
            self.client,
            f"/api/admin/projects/{first_project['id']}/client-access/{first_client['id']}"
        )
        self.assertEqual(remove_response.status_code, 200)
        revoked_portal = client_session.get("/api/client/projects")
        self.assertNotIn("Assigned Project", [project["name"] for project in revoked_portal.json()["projects"]])
        self.assertEqual(client_session.get(f"/api/client/projects/{first_project['id']}/publications").status_code, 404)

    def test_analysts_cannot_manage_users_or_client_project_access(self):
        project = post_json_with_csrf(
            self.client,
            "/api/projects",
            {"name": "Restricted Access Project", "description": ""},
        ).json()
        client_user = self.create_client_user("client@example.local")
        self.create_user("analyst@example.local", role="analyst", password="analyst pass")
        analyst_session = TestClient(create_app(store=self.store, auth_enabled=True))
        login_response = login_json_with_csrf(analyst_session, "analyst@example.local", "analyst pass")
        self.assertEqual(login_response.status_code, 200)

        self.assertEqual(analyst_session.get("/api/admin/users").status_code, 403)
        self.assertEqual(
            post_json_with_csrf(
                analyst_session,
                "/api/admin/users",
                {
                    "email": "blocked@example.local",
                    "display_name": "Blocked",
                    "role": "client",
                    "password": "blocked pass",
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            post_json_with_csrf(
                analyst_session,
                f"/api/admin/projects/{project['id']}/client-access",
                {"user_id": client_user["id"]},
            ).status_code,
            403,
        )
        self.assertEqual(
            post_json_with_csrf(analyst_session, "/api/admin/runs/rebuild-results").status_code,
            403,
        )

    def create_client_user(self, email):
        response = post_json_with_csrf(
            self.client,
            "/api/admin/users",
            {
                "email": email,
                "display_name": email,
                "role": "client",
                "password": "client pass",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["user"]

    def create_user(self, email, *, role, password):
        return self.store.create_user(
            email=email,
            display_name=email,
            role=role,
            password_hash=hash_password(password),
            created_by="test",
        )

    def login(self, email, password):
        response = login_json_with_csrf(self.client, email, password)
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
