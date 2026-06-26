import unittest

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import (
    bootstrap_admin_with_csrf,
    login_json_with_csrf,
    post_json_with_csrf,
)


class Iteration6AuthTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))

    def tearDown(self):
        self.store.close()

    def test_first_admin_bootstrap_creates_hashed_local_user(self):
        response = bootstrap_admin_with_csrf(
            self.client,
            "admin@example.local",
            "correct horse battery staple",
            "Admin",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["redirect_path"], "/react/projects")
        users = self.store.list_users()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["email"], "admin@example.local")
        self.assertEqual(users[0]["role"], "admin")
        self.assertTrue(users[0]["is_active"])
        self.assertNotEqual(users[0]["password_hash"], "correct horse battery staple")
        self.assertTrue(users[0]["password_hash"].startswith("pbkdf2_sha256$"))

    def test_internal_user_can_login_access_analyst_api_and_logout(self):
        self.create_user("analyst@example.local", role="analyst", password="let me work")

        unauthenticated_page = self.client.get("/projects", follow_redirects=False)
        self.assertEqual(unauthenticated_page.status_code, 303)
        self.assertEqual(unauthenticated_page.headers["location"], "/react/projects")

        login_response = login_json_with_csrf(self.client, "analyst@example.local", "let me work")
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["redirect_path"], "/react/projects")

        project_response = post_json_with_csrf(
            self.client,
            "/api/projects",
            {"name": "Authenticated project", "description": "Auth smoke"},
        )
        self.assertEqual(project_response.status_code, 201)
        self.assertEqual(project_response.json()["name"], "Authenticated project")

        logout_response = post_json_with_csrf(self.client, "/api/auth/logout")
        self.assertEqual(logout_response.status_code, 204)
        after_logout = self.client.get("/api/projects")
        self.assertEqual(after_logout.status_code, 401)

    def test_invalid_credentials_and_deactivated_users_do_not_create_sessions(self):
        inactive = self.create_user("client@example.local", role="client", password="client pass")
        self.store.set_user_active(inactive["id"], False)

        wrong_password = login_json_with_csrf(self.client, "client@example.local", "wrong")
        self.assertEqual(wrong_password.status_code, 401)
        self.assertNotIn("bess_session=", wrong_password.headers.get("set-cookie", ""))

        inactive_login = login_json_with_csrf(self.client, "client@example.local", "client pass")
        self.assertEqual(inactive_login.status_code, 401)
        self.assertEqual(self.client.get("/api/projects").status_code, 401)

    def test_client_users_land_in_portal_and_cannot_access_analyst_routes(self):
        self.create_user("client@example.local", role="client", password="client pass")

        login_response = login_json_with_csrf(
            self.client,
            "client@example.local",
            "client pass",
            next_path="/react/projects",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["redirect_path"], "/react/client")

        portal_response = self.client.get("/api/client/projects")
        self.assertEqual(portal_response.status_code, 200)
        self.assertEqual(portal_response.json()["projects"], [])

        analyst_page = self.client.get("/projects", follow_redirects=False)
        self.assertEqual(analyst_page.status_code, 303)
        self.assertEqual(analyst_page.headers["location"], "/react/projects")
        analyst_api = self.client.post("/api/projects", json={"name": "Forbidden"})
        self.assertEqual(analyst_api.status_code, 403)

    def test_bootstrap_closes_after_first_user_exists(self):
        self.create_user("admin@example.local", role="admin", password="admin pass")

        response = bootstrap_admin_with_csrf(self.client, "other@example.local", "other pass")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(self.store.list_users()), 1)

    def create_user(self, email, *, role, password):
        return self.store.create_user(
            email=email,
            display_name=email,
            role=role,
            password_hash=hash_password(password),
            created_by="test",
        )


if __name__ == "__main__":
    unittest.main()
