"""BESS-CONFIG-008: one backend-calculated landing path and three roots."""

import unittest

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf


class LandingPathTests(unittest.TestCase):
    """Login and current-user agree on where a user lands."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.store.create_user(
            email="analyst@example.local",
            display_name="Ana Analista",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )

    def tearDown(self):
        self.store.close()

    def login(self, email, password, next_path=""):
        response = login_json_with_csrf(self.client, email, password, next_path)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_login_and_current_user_agree_on_the_internal_landing_path(self):
        login = self.login("analyst@example.local", "analyst pass")

        me = self.client.get("/api/auth/me")

        self.assertEqual(login["landing_path"], "/react/projects")
        self.assertEqual(me.json()["landing_path"], login["landing_path"])


CONSOLE_DOCUMENT = {
    "schema_version": "operator_console_config.v1",
    "public_identity": {"name": "Plan diario", "description": "Ajuste diario"},
    "parameters": [],
    "groups": [],
    "results": {"kpis": [], "charts": [], "tables": []},
}


class ExternalIdentityFixture:
    """An analyst, an external identity and one project to grant it."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.analyst = self.store.create_user(
            email="analyst@example.local",
            display_name="Ana Analista",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.operator = self.store.create_user(
            email="operator@example.local",
            display_name="Olga Operadora",
            role="external",
            password_hash=hash_password("operator pass"),
        )
        self.project = self.store.create_project(name="Planta Norte")

    def tearDown(self):
        self.store.close()

    def grant(self, *, portal_view, operate, project=None):
        self.store.set_external_project_access(
            project_id=(project or self.project)["id"],
            user_id=self.operator["id"],
            portal_view=portal_view,
            operate=operate,
            updated_by="admin@example.local",
        )

    def create_active_console(self, *, name="Plan diario", project=None):
        scenario = self.store.create_scenario(
            project_id=(project or self.project)["id"], name=name
        )
        case = self.store.get_or_create_case_for_scenario(scenario["id"])
        variant = self.store.get_or_create_default_input_variant(case["id"])
        document = {
            **CONSOLE_DOCUMENT,
            "public_identity": {"name": name, "description": "Ajuste diario"},
        }
        console = self.store.create_operator_console(
            case_id=case["id"],
            source_variant_id=variant["id"],
            document=document,
            created_by_user_id=self.analyst["id"],
        )
        return self.store.save_operator_console(
            console["id"],
            document=document,
            status="active",
            expected_revision=1,
            updated_by_user_id=None,
        )

    def login_operator(self, next_path=""):
        response = login_json_with_csrf(
            self.client, "operator@example.local", "operator pass", next_path
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()


class ExternalLandingPathTests(ExternalIdentityFixture, unittest.TestCase):
    """Where an external identity lands depends on its capabilities."""

    def test_an_operator_with_one_visible_console_lands_on_that_console(self):
        self.grant(portal_view=True, operate=True)
        console = self.create_active_console()

        landing = self.login_operator()["landing_path"]

        self.assertEqual(landing, f"/react/console/{console['id']}")

    def test_operate_beats_portal_view_when_consoles_are_zero_or_many(self):
        self.grant(portal_view=True, operate=True)

        with self.subTest("zero visible consoles"):
            self.assertEqual(self.login_operator()["landing_path"], "/react/console")

        self.create_active_console(name="Plan diario")
        self.create_active_console(name="Plan semanal")

        with self.subTest("several visible consoles"):
            self.assertEqual(self.login_operator()["landing_path"], "/react/console")

    def test_a_next_target_outside_the_users_roots_is_ignored(self):
        self.grant(portal_view=False, operate=True)
        console = self.create_active_console()

        with self.subTest("portal next without portal_view"):
            self.assertEqual(
                self.login_operator("/react/client/projects/1")["landing_path"],
                f"/react/console/{console['id']}",
            )

        with self.subTest("analyst next"):
            self.assertEqual(
                self.login_operator("/react/runs/99")["landing_path"],
                f"/react/console/{console['id']}",
            )

        self.grant(portal_view=True, operate=False)

        with self.subTest("console next without operate"):
            self.assertEqual(
                self.login_operator("/react/console")["landing_path"],
                "/react/client",
            )


class RootBoundaryTests(ExternalIdentityFixture, unittest.TestCase):
    """The boundary an external identity may never cross, id or not."""

    def known_run_id(self):
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Corrida conocida"
        )
        version = self.store.create_scenario_version(
            scenario_id=scenario["id"],
            system_case_json={"case_name": "known", "periods": []},
            validation_payload={"status": "ok"},
        )
        return self.store.create_run(scenario_version_id=version["id"])["id"]

    def test_an_external_identity_never_enters_the_analyst_root(self):
        self.grant(portal_view=True, operate=True)
        run_id = self.known_run_id()
        self.login_operator()

        for path in [
            "/api/projects",
            f"/api/projects/{self.project['id']}",
            f"/api/runs/{run_id}",
            "/api/admin/users",
        ]:
            with self.subTest(path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_an_internal_analyst_is_forbidden_from_user_administration(self):
        response = login_json_with_csrf(
            self.client, "analyst@example.local", "analyst pass", ""
        )
        self.assertEqual(response.status_code, 200, response.text)

        self.assertEqual(self.client.get("/api/admin/users").status_code, 403)


if __name__ == "__main__":
    unittest.main()
