import unittest

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import delete_with_csrf, post_json_with_csrf


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
        active_login = active_client_session.post(
            "/login",
            data={"email": "client@example.local", "password": "client pass"},
            follow_redirects=False,
        )
        self.assertEqual(active_login.status_code, 303)
        self.assertEqual(active_client_session.get("/client").status_code, 200)

        deactivate_response = post_json_with_csrf(
            self.client,
            f"/api/admin/users/{created_user['id']}/deactivate",
        )
        self.assertEqual(deactivate_response.status_code, 200)
        self.assertFalse(deactivate_response.json()["user"]["is_active"])
        after_deactivation = active_client_session.get("/client", follow_redirects=False)
        self.assertEqual(after_deactivation.status_code, 303)
        self.assertTrue(after_deactivation.headers["location"].startswith("/login?next=/client"))

        logged_out_client = TestClient(create_app(store=self.store, auth_enabled=True))
        login_response = logged_out_client.post(
            "/login",
            data={"email": "client@example.local", "password": "client pass"},
            follow_redirects=False,
        )
        self.assertEqual(login_response.status_code, 401)

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
        login_response = client_session.post(
            "/login",
            data={"email": "client@example.local", "password": "client pass"},
            follow_redirects=False,
        )
        self.assertEqual(login_response.status_code, 303)

        portal_response = client_session.get("/client")
        self.assertEqual(portal_response.status_code, 200)
        self.assertIn("Assigned Project", portal_response.text)
        self.assertIn("Portfolio Project", portal_response.text)
        self.assertNotIn("Private Project", portal_response.text)

        assigned_detail = client_session.get(f"/client/projects/{first_project['id']}")
        self.assertEqual(assigned_detail.status_code, 200)
        self.assertIn("Assigned Project", assigned_detail.text)
        self.assertNotIn("Create Scenario", assigned_detail.text)

        guessed_detail = client_session.get(f"/client/projects/{unassigned_project['id']}")
        self.assertEqual(guessed_detail.status_code, 404)

        remove_response = delete_with_csrf(
            self.client,
            f"/api/admin/projects/{first_project['id']}/client-access/{first_client['id']}"
        )
        self.assertEqual(remove_response.status_code, 200)
        revoked_portal = client_session.get("/client")
        self.assertNotIn("Assigned Project", revoked_portal.text)
        self.assertEqual(client_session.get(f"/client/projects/{first_project['id']}").status_code, 404)

    def test_analysts_cannot_manage_users_or_client_project_access(self):
        project = post_json_with_csrf(
            self.client,
            "/api/projects",
            {"name": "Restricted Access Project", "description": ""},
        ).json()
        client_user = self.create_client_user("client@example.local")
        self.create_user("analyst@example.local", role="analyst", password="analyst pass")
        analyst_session = TestClient(create_app(store=self.store, auth_enabled=True))
        login_response = analyst_session.post(
            "/login",
            data={"email": "analyst@example.local", "password": "analyst pass"},
            follow_redirects=False,
        )
        self.assertEqual(login_response.status_code, 303)

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
        response = self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)


if __name__ == "__main__":
    unittest.main()
