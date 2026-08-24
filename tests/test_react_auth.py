import unittest

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore


class ReactAuthenticationContractTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))

    def tearDown(self):
        self.store.close()

    def test_json_bootstrap_login_logout_deactivation_and_csrf_contract(self):
        csrf = self.csrf_token()

        blocked_bootstrap = self.client.post(
            "/api/auth/bootstrap",
            json={
                "email": "admin@example.local",
                "display_name": "Admin User",
                "password": "admin pass",
            },
        )
        self.assertEqual(blocked_bootstrap.status_code, 403)

        bootstrap = self.client.post(
            "/api/auth/bootstrap",
            json={
                "email": "admin@example.local",
                "display_name": "Admin User",
                "password": "admin pass",
            },
            headers=self.csrf_header(csrf),
        )
        self.assertEqual(bootstrap.status_code, 201)
        self.assertEqual(bootstrap.json()["landing_path"], "/react/projects")
        self.assertEqual(bootstrap.json()["user"]["role"], "admin")
        self.assertIn("httponly", bootstrap.headers["set-cookie"].lower())
        self.assertTrue(self.store.list_users()[0]["password_hash"].startswith("pbkdf2_sha256$"))

        closed_bootstrap = self.client.post(
            "/api/auth/bootstrap",
            json={
                "email": "other@example.local",
                "display_name": "Other User",
                "password": "other pass",
            },
            headers=self.csrf_header(csrf),
        )
        self.assertEqual(closed_bootstrap.status_code, 403)
        self.assertEqual(closed_bootstrap.json()["detail"], "bootstrap is closed")

        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["email"], "admin@example.local")
        self.assertFalse(me.json()["bootstrap_required"])

        project_without_csrf = self.client.post(
            "/api/projects",
            json={"name": "Blocked project"},
        )
        self.assertEqual(project_without_csrf.status_code, 403)
        self.assertEqual(project_without_csrf.json()["detail"], "csrf token required")

        logout = self.client.post("/api/auth/logout", headers=self.csrf_header(csrf))
        self.assertEqual(logout.status_code, 204)
        self.assertIsNone(self.client.get("/api/auth/me").json()["user"])

        bad_login = self.client.post(
            "/api/auth/login",
            json={"email": "admin@example.local", "password": "wrong"},
            headers=self.csrf_header(csrf),
        )
        self.assertEqual(bad_login.status_code, 401)
        self.assertEqual(bad_login.json()["detail"], "Invalid email or password.")

        login = self.client.post(
            "/api/auth/login",
            json={
                "email": "admin@example.local",
                "password": "admin pass",
                "next": "/react/system",
            },
            headers=self.csrf_header(csrf),
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["landing_path"], "/react/system")
        self.assertEqual(login.json()["user"]["email"], "admin@example.local")

        unsafe_login = TestClient(create_app(store=self.store, auth_enabled=True))
        unsafe_csrf = unsafe_login.get("/api/auth/csrf").json()["csrf_token"]
        unsafe_response = unsafe_login.post(
            "/api/auth/login",
            json={
                "email": "admin@example.local",
                "password": "admin pass",
                "next": "https://example.invalid/phish",
            },
            headers=self.csrf_header(unsafe_csrf),
        )
        self.assertEqual(unsafe_response.status_code, 200)
        self.assertEqual(unsafe_response.json()["landing_path"], "/react/projects")

        self.store.set_user_active(self.store.list_users()[0]["id"], False, updated_by="test")
        self.assertIsNone(self.client.get("/api/auth/me").json()["user"])
        blocked_after_deactivation = self.client.post(
            "/api/projects",
            json={"name": "Still blocked"},
            headers=self.csrf_header(csrf),
        )
        self.assertEqual(blocked_after_deactivation.status_code, 401)

    def test_production_cookie_secure_flag_is_configurable(self):
        self.store.create_user(
            email="admin@example.local",
            display_name="Admin User",
            role="admin",
            password_hash=hash_password("admin pass"),
            created_by="test",
        )
        client = TestClient(
            create_app(
                store=self.store,
                auth_enabled=True,
                session_cookie_secure=True,
            ),
            base_url="https://testserver",
        )
        csrf = client.get("/api/auth/csrf").json()["csrf_token"]

        response = client.post(
            "/api/auth/login",
            json={"email": "admin@example.local", "password": "admin pass"},
            headers=self.csrf_header(csrf),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("secure", response.headers["set-cookie"].lower())

    def csrf_token(self):
        response = self.client.get("/api/auth/csrf")
        self.assertEqual(response.status_code, 200)
        token = response.json()["csrf_token"]
        self.assertGreater(len(token), 20)
        return token

    @staticmethod
    def csrf_header(token):
        return {"X-CSRF-Token": token}


if __name__ == "__main__":
    unittest.main()
