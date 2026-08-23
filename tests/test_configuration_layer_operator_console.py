import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.operator_console import (
    OperatorConsoleConfigurationError,
    StaleOperatorConsoleError,
    validate_operator_console_config_document,
)
from app.persistence import AnalystStore
from tests.auth_test_helpers import (
    login_json_with_csrf,
    post_json_with_csrf,
    put_json_with_csrf,
)


NORMATIVE_DOCUMENT = {
    "schema_version": "operator_console_config.v1",
    "public_identity": {
        "name": "Plan diario Planta Norte",
        "description": "Ajuste de disponibilidad y corrida diaria",
    },
    "parameters": [
        {
            "id": "potencia_bess",
            "pointer": {"asset_id": "battery_1", "field": "power_max_mw"},
            "label": "Potencia maxima BESS",
            "unit": "MW",
            "min": 0,
            "max": 100,
            "default": 40,
        }
    ],
    "groups": [
        {
            "id": "potencia",
            "label": "Potencia",
            "granularities": ["day", "week", "month", "full_horizon"],
            "columns": [
                {
                    "id": "demanda",
                    "signal": {
                        "entity_type": "component:load",
                        "entity_id": "load_1",
                        "signal_key": "load_demand_mw",
                    },
                    "label": "Demanda",
                    "editable": True,
                    "source_options": [
                        {"id": "base", "label": "Demanda base", "time_series_set_id": 18}
                    ],
                    "default_source_option_id": "base",
                }
            ],
        }
    ],
    "results": {"kpis": [], "charts": [], "tables": []},
}


class OperatorConsoleConfigDocumentValidationTests(unittest.TestCase):
    def test_the_normative_document_is_accepted_and_normalized(self):
        validated = validate_operator_console_config_document(NORMATIVE_DOCUMENT)

        self.assertEqual(validated, NORMATIVE_DOCUMENT)

    def test_an_unknown_schema_version_is_rejected(self):
        document = {**NORMATIVE_DOCUMENT, "schema_version": "operator_console_config.v2"}

        with self.assertRaisesRegex(OperatorConsoleConfigurationError, "schema version"):
            validate_operator_console_config_document(document)

    def test_a_malformed_document_is_rejected(self):
        malformed_documents = {
            "missing public identity": {
                key: value
                for key, value in NORMATIVE_DOCUMENT.items()
                if key != "public_identity"
            },
            "unknown top level key": {**NORMATIVE_DOCUMENT, "locale": "es-CL"},
            "groups is not a list": {**NORMATIVE_DOCUMENT, "groups": {}},
            "group without columns": {
                **NORMATIVE_DOCUMENT,
                "groups": [
                    {
                        "id": "vacio",
                        "label": "Vacio",
                        "granularities": ["day"],
                        "columns": [],
                    }
                ],
            },
            "parameter without pointer": {
                **NORMATIVE_DOCUMENT,
                "parameters": [
                    {
                        "id": "potencia_bess",
                        "label": "Potencia",
                        "unit": "MW",
                        "min": 0,
                        "max": 100,
                        "default": 40,
                    }
                ],
            },
        }

        for name, document in malformed_documents.items():
            with self.subTest(name):
                with self.assertRaises(OperatorConsoleConfigurationError):
                    validate_operator_console_config_document(document)

    def test_duplicate_ids_are_rejected(self):
        duplicate_parameter_ids = {
            **NORMATIVE_DOCUMENT,
            "parameters": [
                NORMATIVE_DOCUMENT["parameters"][0],
                {**NORMATIVE_DOCUMENT["parameters"][0], "label": "Otro"},
            ],
        }
        group = NORMATIVE_DOCUMENT["groups"][0]
        duplicate_column_ids = {
            **NORMATIVE_DOCUMENT,
            "groups": [
                {
                    **group,
                    "columns": [group["columns"][0], {**group["columns"][0], "label": "Otra"}],
                }
            ],
        }

        for name, document in {
            "parameters": duplicate_parameter_ids,
            "columns": duplicate_column_ids,
        }.items():
            with self.subTest(name):
                with self.assertRaisesRegex(OperatorConsoleConfigurationError, "duplicate"):
                    validate_operator_console_config_document(document)

    def test_granularities_are_a_closed_enum(self):
        document = {
            **NORMATIVE_DOCUMENT,
            "groups": [
                {**NORMATIVE_DOCUMENT["groups"][0], "granularities": ["day", "quarter"]}
            ],
        }

        with self.assertRaisesRegex(OperatorConsoleConfigurationError, "full_horizon"):
            validate_operator_console_config_document(document)

    def test_a_default_source_option_must_be_declared_by_its_column(self):
        group = NORMATIVE_DOCUMENT["groups"][0]
        document = {
            **NORMATIVE_DOCUMENT,
            "groups": [
                {
                    **group,
                    "columns": [
                        {**group["columns"][0], "default_source_option_id": "inexistente"}
                    ],
                }
            ],
        }

        with self.assertRaisesRegex(
            OperatorConsoleConfigurationError, "default_source_option_id"
        ):
            validate_operator_console_config_document(document)

    def test_structural_validation_never_resolves_pointers_signals_sources_or_ranges(self):
        """A document that points nowhere is still structurally valid.

        Semantic problems are a fail-closed console state, not a malformed
        document, so validation stays offline and pure.
        """

        document = {
            **NORMATIVE_DOCUMENT,
            "parameters": [
                {
                    **NORMATIVE_DOCUMENT["parameters"][0],
                    "pointer": {"asset_id": "asset_que_no_existe", "field": "campo_borrado"},
                }
            ],
            "groups": [
                {
                    **NORMATIVE_DOCUMENT["groups"][0],
                    "columns": [
                        {
                            **NORMATIVE_DOCUMENT["groups"][0]["columns"][0],
                            "signal": {
                                "entity_type": "component:load",
                                "entity_id": "load_borrado",
                                "signal_key": "senal_inexistente",
                            },
                            "source_options": [
                                {"id": "base", "label": "Base", "time_series_set_id": 999999}
                            ],
                        }
                    ],
                }
            ],
        }

        validated = validate_operator_console_config_document(document)

        self.assertEqual(
            validated["parameters"][0]["pointer"],
            {"asset_id": "asset_que_no_existe", "field": "campo_borrado"},
        )
        self.assertEqual(
            validated["groups"][0]["columns"][0]["source_options"][0]["time_series_set_id"],
            999999,
        )



class OperatorConsolePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Planta Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.source_variant = self.store.get_or_create_default_input_variant(self.case["id"])
        self.analyst = self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash="test-hash",
        )

    def tearDown(self):
        self.store.close()

    def create_console(self, document=None):
        return self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.source_variant["id"],
            document=document or NORMATIVE_DOCUMENT,
            created_by_user_id=self.analyst["id"],
        )

    def test_a_case_starts_without_consoles(self):
        self.assertEqual(self.store.list_operator_consoles(self.case["id"]), [])

    def test_creating_a_console_records_identity_audit_and_draft_status(self):
        console = self.create_console()

        self.assertEqual(
            {
                "case_id": console["case_id"],
                "status": console["status"],
                "revision": console["revision"],
                "created_by_user_id": console["created_by_user_id"],
                "prepared_by_user_id": console["prepared_by_user_id"],
                "updated_by_user_id": console["updated_by_user_id"],
                "waiting_since": console["waiting_since"],
            },
            {
                "case_id": self.case["id"],
                "status": "draft",
                "revision": 1,
                "created_by_user_id": self.analyst["id"],
                "prepared_by_user_id": self.analyst["id"],
                "updated_by_user_id": self.analyst["id"],
                "waiting_since": None,
            },
        )
        self.assertTrue(console["created_at"])
        self.assertTrue(console["updated_at"])
        self.assertEqual(console["document"], NORMATIVE_DOCUMENT)

    def test_creation_clones_a_variant_owned_only_by_the_console(self):
        console = self.create_console()
        other = self.create_console()

        owned_variant = self.store.get_case_input_variant(console["owned_variant_id"])
        self.assertNotEqual(console["owned_variant_id"], self.source_variant["id"])
        self.assertNotEqual(console["owned_variant_id"], other["owned_variant_id"])
        self.assertEqual(owned_variant["case_id"], self.case["id"])
        self.assertFalse(owned_variant["is_default"])

    def test_creating_a_console_never_touches_the_source_variant(self):
        before = self.store.get_case_input_variant(self.source_variant["id"])

        self.create_console()

        self.assertEqual(self.store.get_case_input_variant(self.source_variant["id"]), before)

    def test_saving_a_document_increments_revision_and_keeps_identity_and_variant(self):
        console = self.create_console()
        renamed = {
            **NORMATIVE_DOCUMENT,
            "public_identity": {"name": "Plan diario v2", "description": "Actualizado"},
        }

        saved = self.store.save_operator_console(
            console["id"],
            document=renamed,
            status="active",
            expected_revision=1,
            updated_by_user_id=self.analyst["id"],
        )

        self.assertEqual(
            {
                "id": saved["id"],
                "owned_variant_id": saved["owned_variant_id"],
                "revision": saved["revision"],
                "status": saved["status"],
                "document": saved["document"],
            },
            {
                "id": console["id"],
                "owned_variant_id": console["owned_variant_id"],
                "revision": 2,
                "status": "active",
                "document": renamed,
            },
        )
        self.assertEqual(len(self.store.list_operator_consoles(self.case["id"])), 1)

    def test_a_stale_expected_revision_is_rejected_without_writing(self):
        console = self.create_console()

        with self.assertRaises(StaleOperatorConsoleError) as raised:
            self.store.save_operator_console(
                console["id"],
                document=NORMATIVE_DOCUMENT,
                status="active",
                expected_revision=7,
                updated_by_user_id=self.analyst["id"],
            )

        self.assertEqual(raised.exception.current_revision, 1)
        stored = self.store.get_operator_console(console["id"])
        self.assertEqual(
            {"revision": stored["revision"], "status": stored["status"]},
            {"revision": 1, "status": "draft"},
        )


class InternalOperatorConsoleApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.project = self.store.create_project(name="Planta Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        self.login_analyst()

    def tearDown(self):
        self.store.close()

    def login_analyst(self):
        self.assertEqual(
            login_json_with_csrf(
                self.client, "analyst@example.local", "analyst pass"
            ).status_code,
            200,
        )

    def create_console(self, document=None):
        response = post_json_with_csrf(
            self.client,
            f"/api/scenarios/{self.scenario['id']}/consoles",
            {
                "source_variant_id": self.variant["id"],
                "document": document or NORMATIVE_DOCUMENT,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["operator_console"]

    def test_an_analyst_creates_a_draft_console_from_a_chosen_source_variant(self):
        console = self.create_console()

        self.assertEqual(
            {
                "status": console["status"],
                "revision": console["revision"],
                "prepared_by": console["prepared_by"],
                "document": console["document"],
            },
            {
                "status": "draft",
                "revision": 1,
                "prepared_by": "analyst@example.local",
                "document": NORMATIVE_DOCUMENT,
            },
        )
        self.assertNotEqual(console["owned_variant"]["id"], self.variant["id"])

    def test_the_scenario_workspace_lists_its_consoles(self):
        console = self.create_console()

        response = self.client.get(f"/api/scenarios/{self.scenario['id']}/consoles")

        self.assertEqual(response.status_code, 200)
        listed = response.json()["operator_consoles"]
        self.assertEqual([entry["id"] for entry in listed], [console["id"]])
        self.assertEqual(listed[0]["blocking"]["reason"], None)

    def test_an_analyst_activates_a_console_in_place(self):
        console = self.create_console()

        response = put_json_with_csrf(
            self.client,
            f"/api/scenarios/{self.scenario['id']}/consoles/{console['id']}",
            {
                "document": NORMATIVE_DOCUMENT,
                "status": "active",
                "expected_revision": 1,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        activated = response.json()["operator_console"]
        self.assertEqual(
            {
                "id": activated["id"],
                "owned_variant_id": activated["owned_variant"]["id"],
                "status": activated["status"],
                "revision": activated["revision"],
            },
            {
                "id": console["id"],
                "owned_variant_id": console["owned_variant"]["id"],
                "status": "active",
                "revision": 2,
            },
        )

    def test_an_analyst_deactivates_an_active_console_back_to_draft(self):
        console = self.create_console()
        activated = put_json_with_csrf(
            self.client,
            f"/api/scenarios/{self.scenario['id']}/consoles/{console['id']}",
            {"document": NORMATIVE_DOCUMENT, "status": "active", "expected_revision": 1},
        ).json()["operator_console"]

        response = put_json_with_csrf(
            self.client,
            f"/api/scenarios/{self.scenario['id']}/consoles/{console['id']}",
            {
                "document": NORMATIVE_DOCUMENT,
                "status": "draft",
                "expected_revision": activated["revision"],
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["operator_console"]["status"], "draft")

    def test_an_invalid_document_is_rejected_without_partial_persistence(self):
        console = self.create_console()
        invalid_documents = {
            "unknown schema version": {
                **NORMATIVE_DOCUMENT,
                "schema_version": "operator_console_config.v9",
            },
            "malformed groups": {**NORMATIVE_DOCUMENT, "groups": "todas"},
            "invalid granularity": {
                **NORMATIVE_DOCUMENT,
                "groups": [
                    {**NORMATIVE_DOCUMENT["groups"][0], "granularities": ["decade"]}
                ],
            },
        }

        for name, document in invalid_documents.items():
            with self.subTest(name):
                response = put_json_with_csrf(
                    self.client,
                    f"/api/scenarios/{self.scenario['id']}/consoles/{console['id']}",
                    {"document": document, "status": "active", "expected_revision": 1},
                )

                self.assertEqual(response.status_code, 400, response.text)
                stored = self.store.get_operator_console(console["id"])
                self.assertEqual(
                    {"revision": stored["revision"], "status": stored["status"]},
                    {"revision": 1, "status": "draft"},
                )

    def test_a_stale_expected_revision_is_rejected_with_conflict(self):
        console = self.create_console()

        response = put_json_with_csrf(
            self.client,
            f"/api/scenarios/{self.scenario['id']}/consoles/{console['id']}",
            {"document": NORMATIVE_DOCUMENT, "status": "active", "expected_revision": 0},
        )

        self.assertEqual(response.status_code, 409, response.text)

    def test_a_console_from_another_scenario_is_not_reachable(self):
        console = self.create_console()
        other_scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Otro escenario"
        )

        response = self.client.get(
            f"/api/scenarios/{other_scenario['id']}/consoles/{console['id']}"
        )

        self.assertEqual(response.status_code, 404)


class OperatorConsoleShellTests(unittest.TestCase):
    """The external console surface: what an operator may list and open."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.store.create_user(
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
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        self.store.set_external_project_access(
            project_id=self.project["id"],
            user_id=self.operator["id"],
            portal_view=False,
            operate=True,
            updated_by="admin@example.local",
        )

    def tearDown(self):
        self.store.close()

    def login(self, email, password):
        self.assertEqual(
            login_json_with_csrf(self.client, email, password).status_code, 200
        )

    def create_console(self, *, status, name="Plan diario Planta Norte", scenario=None):
        scenario = scenario or self.scenario
        case = self.store.get_or_create_case_for_scenario(scenario["id"])
        variant = self.store.get_or_create_default_input_variant(case["id"])
        document = {
            **NORMATIVE_DOCUMENT,
            "public_identity": {"name": name, "description": "Ajuste diario"},
        }
        console = self.store.create_operator_console(
            case_id=case["id"],
            source_variant_id=variant["id"],
            document=document,
            created_by_user_id=self.store.get_user_by_email("analyst@example.local")["id"],
        )
        if status == "active":
            console = self.store.save_operator_console(
                console["id"],
                document=document,
                status="active",
                expected_revision=1,
                updated_by_user_id=None,
            )
        return console

    def test_an_operator_lists_only_active_consoles_of_assigned_projects(self):
        active = self.create_console(status="active")
        self.create_console(status="draft", name="Borrador interno")
        foreign_project = self.store.create_project(name="Planta Sur")
        foreign_scenario = self.store.create_scenario(
            project_id=foreign_project["id"], name="Otra operacion"
        )
        self.create_console(status="active", name="Plan ajeno", scenario=foreign_scenario)
        self.login("operator@example.local", "operator pass")

        response = self.client.get("/api/console")

        self.assertEqual(response.status_code, 200, response.text)
        listed = response.json()["consoles"]
        self.assertEqual(
            [(entry["console"]["id"], entry["console"]["name"]) for entry in listed],
            [(active["id"], "Plan diario Planta Norte")],
        )
        self.assertEqual(listed[0]["project"], {"name": "Planta Norte"})

    def test_an_operator_opens_an_active_console_with_identity_and_preparer(self):
        console = self.create_console(status="active")
        self.login("operator@example.local", "operator pass")

        response = self.client.get(f"/api/console/{console['id']}")

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(
            payload["console"],
            {
                "id": console["id"],
                "name": "Plan diario Planta Norte",
                "description": "Ajuste diario",
                "prepared_by": "Ana Analista",
                "updated_at": console["updated_at"],
            },
        )

    def test_a_draft_a_foreign_and_a_guessed_console_are_all_not_found(self):
        draft = self.create_console(status="draft")
        foreign_project = self.store.create_project(name="Planta Sur")
        foreign_scenario = self.store.create_scenario(
            project_id=foreign_project["id"], name="Otra operacion"
        )
        foreign = self.create_console(
            status="active", name="Plan ajeno", scenario=foreign_scenario
        )
        self.login("operator@example.local", "operator pass")

        for name, console_id in {
            "draft": draft["id"],
            "foreign": foreign["id"],
            "guessed": 987654,
        }.items():
            with self.subTest(name):
                response = self.client.get(f"/api/console/{console_id}")
                self.assertEqual(response.status_code, 404, response.text)

    def test_revoking_operate_hides_the_console_on_the_next_request(self):
        console = self.create_console(status="active")
        self.login("operator@example.local", "operator pass")
        self.assertEqual(self.client.get(f"/api/console/{console['id']}").status_code, 200)

        self.store.revoke_external_project_access(
            project_id=self.project["id"],
            user_id=self.operator["id"],
            updated_by="admin@example.local",
        )

        self.assertEqual(self.client.get(f"/api/console/{console['id']}").status_code, 404)
        self.assertEqual(self.client.get("/api/console").json()["consoles"], [])

    def test_an_internal_analyst_tests_a_draft_console_with_a_return_path(self):
        console = self.create_console(status="draft")
        self.login("analyst@example.local", "analyst pass")

        response = self.client.get(f"/api/console/{console['id']}")

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["console"]["name"], "Plan diario Planta Norte")
        self.assertEqual(
            payload["internal_test"],
            {
                "return_path": f"/scenarios/{self.scenario['id']}/consoles/{console['id']}",
                "tester": "analyst@example.local",
            },
        )

    def test_the_console_list_works_when_authentication_is_disabled(self):
        console = self.create_console(status="active")
        open_client = TestClient(create_app(store=self.store, auth_enabled=False))

        response = open_client.get("/api/console")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [entry["console"]["id"] for entry in response.json()["consoles"]],
            [console["id"]],
        )

    def test_the_operator_payload_carries_no_internal_metadata(self):
        console = self.create_console(status="active")
        self.login("operator@example.local", "operator pass")

        serialized = self.client.get(f"/api/console/{console['id']}").text

        for forbidden in [
            "internal_test",
            "scenario_id",
            "case_id",
            "variant_id",
            "owned_variant",
            "revision",
            "document",
            "signal_key",
            "asset_id",
            "time_series_set_id",
            "schema_version",
        ]:
            with self.subTest(forbidden):
                self.assertNotIn(forbidden, serialized)


class OperatorConsoleMigrationTests(unittest.TestCase):
    def test_opening_an_existing_database_creates_no_consoles(self):
        """Consoles are always an explicit analyst decision, never a migration."""

        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory) / 'existing.sqlite3'}"
            seed = AnalystStore(database_url)
            project = seed.create_project(name="Proyecto heredado")
            scenario = seed.create_scenario(project_id=project["id"], name="Escenario")
            case = seed.get_or_create_case_for_scenario(scenario["id"])
            seed.get_or_create_default_input_variant(case["id"])
            seed.create_dashboard_template(project_id=project["id"], name="Tablero")
            seed.close()

            reopened = AnalystStore(database_url)
            try:
                self.assertEqual(reopened.list_all_operator_consoles(), [])
            finally:
                reopened.close()


if __name__ == "__main__":
    unittest.main()
