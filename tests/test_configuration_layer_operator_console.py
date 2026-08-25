import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.operator_console import (
    OperatorConsoleConfigurationError,
    StaleOperatorConsoleError,
    validate_operator_console_config_document,
)
from app.persistence import AnalystStore, derive_case_hierarchy_provenance
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)
from app.validation import ValidationResult
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


def operator_draft_document():
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": "grid_battery_case", "description": ""},
        "pcc": {"id": "bus_1", "type": "bus"},
        "grid": {
            "id": "grid_1",
            "import_power_max_mw": 10.0,
            "export_power_max_mw": 10.0,
            "prevent_simultaneous_grid_import_export": True,
        },
        "assets": [
            {
                "id": "battery_1",
                "type": "battery",
                "charge_power_max_mw": 4.0,
                "discharge_power_max_mw": 4.0,
                "energy_min_mwh": 0.0,
                "energy_max_mwh": 8.0,
                "initial_energy_mwh": 4.0,
                "charge_efficiency": 0.95,
                "discharge_efficiency": 0.95,
                "degradation_cost_per_mwh_delta_soc": 0.0,
                "terminal_condition": "none",
                "prevent_simultaneous_charge_discharge": True,
                "degradation_linear_delta_soc": True,
            }
        ],
        "time_series": {"sources": []},
        "solver": {"name": "HiGHS", "options": {}},
    }


def console_document_with_scalar_parameter(*, groups=None):
    """A console whose only configured surface is one resolvable scalar.

    `groups` defaults to the normative group, whose named source points at a
    set these tests never import: that is a legitimate `campo_no_disponible`.
    Tests about parameters and periods pass `groups=[]` so the only thing they
    can trip over is the behaviour they are about.
    """

    return {
        **NORMATIVE_DOCUMENT,
        "parameters": [
            {
                **NORMATIVE_DOCUMENT["parameters"][0],
                "pointer": {
                    "asset_id": "battery_1",
                    "field": "charge_power_max_mw",
                },
            }
        ],
        "groups": NORMATIVE_DOCUMENT["groups"] if groups is None else groups,
    }


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
        )


class RecordingRunQueue:
    def __init__(self):
        self.enqueued_run_ids = []

    def enqueue(self, run_id):
        self.enqueued_run_ids.append(run_id)

    def stop(self):
        pass


def create_console_price_set(store, scenario_id):
    start = datetime(2026, 1, 1)
    prepared = prepare_time_series_catalog_import(
        rows=[
            {
                "period_start": (start + timedelta(hours=offset)).isoformat(),
                "hours": "1.0",
                "spot_price": str(50 + offset),
            }
            for offset in range(3)
        ],
        request=CatalogImportRequest(
            set_name="Console price",
            version_label="v1",
            data_kind="real",
            timezone="America/Santiago",
            timestamp_column="period_start",
            duration_hours_column="hours",
            signal_mappings=[
                CatalogSignalMappingRequest(
                    source_column="spot_price",
                    signal_key="import_price_usd_per_mwh",
                )
            ],
        ),
    )
    return store.import_time_series_catalog_set(
        scenario_id=scenario_id,
        source={
            "id": "console_period_prices",
            "original_filename": "prices.csv",
            "media_type": "text/csv",
            "checksum": "sha256:console-period-prices",
        },
        prepared_import=prepared,
    )


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

    def test_parameter_ranges_must_contain_the_declared_default(self):
        for name, parameter in {
            "reversed": {
                **NORMATIVE_DOCUMENT["parameters"][0],
                "min": 100,
                "max": 0,
                "default": 40,
            },
            "default outside": {
                **NORMATIVE_DOCUMENT["parameters"][0],
                "min": 0,
                "max": 10,
                "default": 40,
            },
        }.items():
            with self.subTest(name):
                with self.assertRaisesRegex(
                    OperatorConsoleConfigurationError, "parameter range"
                ):
                    validate_operator_console_config_document(
                        {**NORMATIVE_DOCUMENT, "parameters": [parameter]}
                    )

    def test_two_external_parameters_cannot_target_the_same_scalar(self):
        duplicate_pointer = {
            **NORMATIVE_DOCUMENT,
            "parameters": [
                NORMATIVE_DOCUMENT["parameters"][0],
                {
                    **NORMATIVE_DOCUMENT["parameters"][0],
                    "id": "potencia_bess_secundaria",
                },
            ],
        }

        with self.assertRaisesRegex(
            OperatorConsoleConfigurationError, "duplicate parameter pointer"
        ):
            validate_operator_console_config_document(duplicate_pointer)

    def test_console_results_use_the_shared_result_configuration_grammar(self):
        valid = {
            **NORMATIVE_DOCUMENT,
            "results": {
                "kpis": [
                    {
                        "id": "beneficio_total",
                        "path": "objective_value_usd",
                        "label": "Beneficio total",
                        "unit": "USD",
                        "decimals": 1,
                        "sign": "auto",
                        "emphasis": "strong",
                    }
                ],
                "charts": [],
                "tables": [],
            },
        }
        malformed = {
            **NORMATIVE_DOCUMENT,
            "results": {
                "kpis": [
                    {
                        "id": "beneficio_total",
                        "path": "objective_value_usd",
                        "label": "Beneficio total",
                    }
                ],
                "charts": [],
                "tables": [],
            },
        }

        self.assertEqual(
            validate_operator_console_config_document(valid)["results"],
            valid["results"],
        )
        with self.assertRaisesRegex(
            OperatorConsoleConfigurationError, "results"
        ):
            validate_operator_console_config_document(malformed)



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

    def test_console_period_is_the_available_horizon_of_its_bound_series(self):
        price_set = create_console_price_set(self.store, self.scenario["id"])
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.source_variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=price_set["id"],
        )
        console = self.create_console()

        period = self.store.resolve_operator_console_period(console["id"])

        self.assertEqual(
            period,
            {
                "available_start": price_set["horizon"]["start"],
                "available_end": price_set["horizon"]["end"],
                "selected_start": price_set["horizon"]["start"],
                "selected_end": price_set["horizon"]["end"],
            },
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
        # The normative document names a source this scenario never imported,
        # so the internal row reports the block an engineer has to correct.
        self.assertEqual(listed[0]["blocking"]["reason"], "campo_no_disponible")

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
        self.artifact_temp = tempfile.TemporaryDirectory()
        self.validation_service = StubValidationService()
        self.run_queue = RecordingRunQueue()
        self.client = TestClient(
            create_app(
                validation_service=self.validation_service,
                store=self.store,
                auth_enabled=True,
                run_queue=self.run_queue,
                artifact_root=Path(self.artifact_temp.name),
            )
        )
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
        self.artifact_temp.cleanup()

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

    def test_an_operator_sees_only_configured_scalar_parameters_with_effective_values(self):
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=operator_draft_document()
        )
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.variant["id"],
            document=console_document_with_scalar_parameter(),
            created_by_user_id=self.store.get_user_by_email("analyst@example.local")["id"],
        )
        console = self.store.save_operator_console(
            console["id"],
            document=console_document_with_scalar_parameter(),
            status="active",
            expected_revision=1,
            updated_by_user_id=None,
        )
        self.login("operator@example.local", "operator pass")

        response = self.client.get(f"/api/console/{console['id']}")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["parameters"],
            [
                {
                    "id": "potencia_bess",
                    "label": "Potencia maxima BESS",
                    "unit": "MW",
                    "min": 0,
                    "max": 100,
                    "default": 40,
                    "value": 4.0,
                }
            ],
        )

    def test_an_operator_replaces_a_parameter_override_by_external_id(self):
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=operator_draft_document()
        )
        document = console_document_with_scalar_parameter()
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.variant["id"],
            document=document,
            created_by_user_id=self.store.get_user_by_email("analyst@example.local")["id"],
        )
        console = self.store.save_operator_console(
            console["id"],
            document=document,
            status="active",
            expected_revision=1,
            updated_by_user_id=None,
        )
        self.login("operator@example.local", "operator pass")

        response = put_json_with_csrf(
            self.client,
            f"/api/console/{console['id']}/parameters",
            {"parameters": [{"id": "potencia_bess", "value": 6.5}]},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["parameters"][0]["value"], 6.5)
        self.assertEqual(
            self.client.get(f"/api/console/{console['id']}").json()["parameters"][0][
                "value"
            ],
            6.5,
        )

    def test_parameter_override_replacement_is_atomic_for_invalid_values(self):
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=operator_draft_document()
        )
        document = console_document_with_scalar_parameter()
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.variant["id"],
            document=document,
            created_by_user_id=self.store.get_user_by_email("analyst@example.local")["id"],
        )
        console = self.store.save_operator_console(
            console["id"],
            document=document,
            status="active",
            expected_revision=1,
            updated_by_user_id=None,
        )
        self.login("operator@example.local", "operator pass")
        endpoint = f"/api/console/{console['id']}/parameters"
        saved = put_json_with_csrf(
            self.client,
            endpoint,
            {"parameters": [{"id": "potencia_bess", "value": 6.5}]},
        )
        self.assertEqual(saved.status_code, 200, saved.text)

        for invalid_parameters in (
            [{"id": "asset_1.import_power_max_mw", "value": 9}],
            [{"id": "potencia_bess", "value": 101}],
        ):
            with self.subTest(parameters=invalid_parameters):
                response = put_json_with_csrf(
                    self.client,
                    endpoint,
                    {"parameters": invalid_parameters},
                )
                self.assertEqual(response.status_code, 400, response.text)
                persisted = self.store.list_operator_console_parameter_overrides(
                    console["id"]
                )
                self.assertEqual(len(persisted), 1)
                self.assertEqual(persisted[0]["asset_id"], "battery_1")
                self.assertEqual(persisted[0]["field"], "charge_power_max_mw")
                self.assertEqual(persisted[0]["value"], 6.5)

    def test_parameter_override_boundary_rejects_canonical_pointers(self):
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=operator_draft_document()
        )
        document = console_document_with_scalar_parameter()
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.variant["id"],
            document=document,
            created_by_user_id=self.store.get_user_by_email("analyst@example.local")["id"],
        )
        console = self.store.save_operator_console(
            console["id"],
            document=document,
            status="active",
            expected_revision=1,
            updated_by_user_id=None,
        )
        self.login("operator@example.local", "operator pass")

        response = put_json_with_csrf(
            self.client,
            f"/api/console/{console['id']}/parameters",
            {
                "parameters": [
                    {
                        "id": "potencia_bess",
                        "value": 9,
                        "asset_id": "grid_1",
                        "field": "import_power_max_mw",
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.store.list_operator_console_parameter_overrides(console["id"]), [])

    def test_an_unavailable_scalar_field_blocks_override_persistence(self):
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=operator_draft_document()
        )
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.variant["id"],
            document=NORMATIVE_DOCUMENT,
            created_by_user_id=self.store.get_user_by_email("analyst@example.local")["id"],
        )
        console = self.store.save_operator_console(
            console["id"],
            document=NORMATIVE_DOCUMENT,
            status="active",
            expected_revision=1,
            updated_by_user_id=None,
        )
        self.login("operator@example.local", "operator pass")

        response = put_json_with_csrf(
            self.client,
            f"/api/console/{console['id']}/parameters",
            {"parameters": [{"id": "potencia_bess", "value": 20}]},
        )

        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("unavailable scalar field", response.json()["detail"])
        self.assertEqual(self.store.list_operator_console_parameter_overrides(console["id"]), [])

    def test_an_unavailable_scalar_field_closes_the_run_gate_actionably(self):
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=operator_draft_document()
        )
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.variant["id"],
            document=NORMATIVE_DOCUMENT,
            created_by_user_id=self.store.get_user_by_email("analyst@example.local")["id"],
        )
        console = self.store.save_operator_console(
            console["id"],
            document=NORMATIVE_DOCUMENT,
            status="active",
            expected_revision=1,
            updated_by_user_id=None,
        )
        self.login("operator@example.local", "operator pass")

        response = self.client.get(f"/api/console/{console['id']}")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["run_gate"],
            {
                "can_run": False,
                "reason": "campo_no_disponible",
                "message": "Un parametro configurado ya no esta disponible.",
                "contact": "Ana Analista",
                "editing_locked_by": None,
                "review_requested_at": None,
            },
        )

    def test_a_closed_run_gate_creates_neither_version_nor_run(self):
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=operator_draft_document()
        )
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.variant["id"],
            document=NORMATIVE_DOCUMENT,
            created_by_user_id=self.store.get_user_by_email("analyst@example.local")["id"],
        )
        console = self.store.save_operator_console(
            console["id"],
            document=NORMATIVE_DOCUMENT,
            status="active",
            expected_revision=1,
            updated_by_user_id=None,
        )
        self.login("operator@example.local", "operator pass")

        response = post_json_with_csrf(
            self.client,
            f"/api/console/{console['id']}/runs",
            {
                "range_start": "2026-01-01T00:00:00",
                "range_end": "2026-01-01T01:00:00",
            },
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["run_gate"]["reason"], "campo_no_disponible")
        self.assertEqual(self.store.list_scenario_versions(self.scenario["id"]), [])
        self.assertEqual(self.store.list_scenario_runs(self.scenario["id"]), [])

    def test_an_uncovered_run_period_is_an_actionable_pre_engine_failure(self):
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=operator_draft_document()
        )
        price_set = create_console_price_set(self.store, self.scenario["id"])
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=price_set["id"],
        )
        document = console_document_with_scalar_parameter(groups=[])
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.variant["id"],
            document=document,
            created_by_user_id=self.store.get_user_by_email("analyst@example.local")["id"],
        )
        console = self.store.save_operator_console(
            console["id"],
            document=document,
            status="active",
            expected_revision=1,
            updated_by_user_id=None,
        )
        self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=console["owned_variant_id"],
            range_start=price_set["horizon"]["start"],
            range_end=price_set["horizon"]["end"],
        )
        self.login("operator@example.local", "operator pass")

        response = post_json_with_csrf(
            self.client,
            f"/api/console/{console['id']}/runs",
            {
                "range_start": "2025-12-31T23:00:00",
                "range_end": price_set["horizon"]["end"],
            },
        )

        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()["failure"]["cause"], "rango_sin_cobertura")
        self.assertIn("periodo", response.json()["failure"]["message"].lower())
        self.assertEqual(self.store.list_scenario_versions(self.scenario["id"]), [])
        self.assertEqual(self.store.list_scenario_runs(self.scenario["id"]), [])

    def test_an_operator_run_freezes_the_effective_override_and_exact_lineage(self):
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=operator_draft_document()
        )
        start = datetime(2026, 1, 1)
        prepared = prepare_time_series_catalog_import(
            rows=[
                {
                    "period_start": (start + timedelta(hours=offset)).isoformat(),
                    "hours": "1.0",
                    "spot_price": str(50 + offset),
                }
                for offset in range(3)
            ],
            request=CatalogImportRequest(
                set_name="Spot price",
                version_label="v1",
                data_kind="real",
                timezone="America/Santiago",
                timestamp_column="period_start",
                duration_hours_column="hours",
                signal_mappings=[
                    CatalogSignalMappingRequest(
                        source_column="spot_price",
                        signal_key="import_price_usd_per_mwh",
                    )
                ],
            ),
        )
        price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "console_prices",
                "original_filename": "prices.csv",
                "media_type": "text/csv",
                "checksum": "sha256:console-prices",
            },
            prepared_import=prepared,
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=price_set["id"],
        )
        document = console_document_with_scalar_parameter(groups=[])
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.variant["id"],
            document=document,
            created_by_user_id=self.store.get_user_by_email("analyst@example.local")["id"],
        )
        console = self.store.save_operator_console(
            console["id"],
            document=document,
            status="active",
            expected_revision=1,
            updated_by_user_id=None,
        )
        base_materialized = self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=console["owned_variant_id"],
            range_start=price_set["horizon"]["start"],
            range_end=price_set["horizon"]["end"],
        )
        base_parameter_hash = derive_case_hierarchy_provenance(
            base_materialized["system_case"]
        )["parameters"]["content_hash"]
        self.login("operator@example.local", "operator pass")
        override_response = put_json_with_csrf(
            self.client,
            f"/api/console/{console['id']}/parameters",
            {"parameters": [{"id": "potencia_bess", "value": 6.5}]},
        )
        self.assertEqual(override_response.status_code, 200, override_response.text)

        response = post_json_with_csrf(
            self.client,
            f"/api/console/{console['id']}/runs",
            {
                "range_start": price_set["horizon"]["start"],
                "range_end": price_set["horizon"]["end"],
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        public_run = response.json()["run"]
        self.assertEqual(public_run["state"], "en_espera")
        self.assertEqual(public_run["triggered_by"], "Olga Operadora")
        self.assertEqual(self.run_queue.enqueued_run_ids, [public_run["id"]])

        stored_run = self.store.get_run(public_run["id"])
        self.assertEqual(stored_run["triggered_by"], "operator@example.local")
        self.assertEqual(stored_run["triggered_by_user_id"], self.operator["id"])
        self.assertEqual(stored_run["trigger_type"], "operator_console")
        self.assertEqual(stored_run["operator_console_id"], console["id"])
        self.assertEqual(stored_run["operator_console_revision"], console["revision"])

        version = self.store.get_scenario_version(stored_run["scenario_version_id"])
        battery = next(
            node
            for node in version["system_case_json"]["nodes"]
            if node["id"] == "battery_1"
        )
        self.assertEqual(battery["charge_power_max_mw"], 6.5)
        self.assertEqual(
            version["generation_metadata"]["parameters"]["content_hash"],
            base_parameter_hash,
        )
        self.assertEqual(
            version["generation_metadata"]["operator_console"],
            {"id": console["id"], "revision": console["revision"]},
        )
        self.assertEqual(
            version["generation_metadata"]["parameter_overrides"],
            [{"id": "potencia_bess", "value": 6.5}],
        )
        draft = self.store.get_scenario_draft(self.scenario["id"])["document"]
        self.assertEqual(draft["assets"][0]["charge_power_max_mw"], 4.0)

    def test_console_run_history_is_reduced_and_scoped_to_its_console(self):
        console = self.create_console(status="active")
        other_console = self.create_console(status="active", name="Otra consola")
        version = self.store.create_scenario_version(
            scenario_id=self.scenario["id"],
            system_case_json={
                "schema_version": "bess_system_dispatch.v2",
                "case_name": "history_case",
                "nodes": [],
                "edges": [],
                "time_series": [],
            },
            validation_payload={"status": "ok"},
        )
        visible = self.store.create_run(
            scenario_version_id=version["id"],
            triggered_by="operator@example.local",
            trigger_type="operator_console",
            triggered_by_user_id=self.operator["id"],
            triggered_by_display_name="Olga Operadora",
            operator_console_id=console["id"],
            operator_console_revision=console["revision"],
        )
        self.store.create_run(
            scenario_version_id=version["id"],
            triggered_by="operator@example.local",
            trigger_type="operator_console",
            triggered_by_user_id=self.operator["id"],
            triggered_by_display_name="Olga Operadora",
            operator_console_id=other_console["id"],
            operator_console_revision=other_console["revision"],
        )
        self.login("operator@example.local", "operator pass")

        response = self.client.get(f"/api/console/{console['id']}/runs")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["history"],
            [
                {
                    "id": visible["id"],
                    "started_at": visible["created_at"],
                    "state": "en_espera",
                    "duration_seconds": None,
                    "triggered_by": "Olga Operadora",
                }
            ],
        )
        self.assertEqual(
            self.client.get(f"/api/console/{console['id']}").json()["history"],
            response.json()["history"],
        )
        for forbidden in [
            "scenario_version_id",
            "operator_console_id",
            "triggered_by_user_id",
            "materialized_lineage",
            "workspace_path",
        ]:
            with self.subTest(forbidden):
                self.assertNotIn(forbidden, response.text)

    def test_a_julia_failure_exposes_only_a_generic_message_and_reference(self):
        console = self.create_console(status="active")
        version = self.store.create_scenario_version(
            scenario_id=self.scenario["id"],
            system_case_json={
                "schema_version": "bess_system_dispatch.v2",
                "case_name": "failed_case",
                "nodes": [],
                "edges": [],
                "time_series": [],
            },
            validation_payload={"status": "ok"},
        )
        run = self.store.create_run(
            scenario_version_id=version["id"],
            triggered_by="operator@example.local",
            trigger_type="operator_console",
            triggered_by_user_id=self.operator["id"],
            triggered_by_display_name="Olga Operadora",
            operator_console_id=console["id"],
            operator_console_revision=console["revision"],
        )
        self.store.mark_run_running(
            run["id"],
            workspace_path="C:/secret/artifacts/runs/77",
            input_snapshot_path="C:/secret/artifacts/runs/77/input/system_case.json",
        )
        self.store.mark_run_failed(
            run["id"],
            exit_code=17,
            stdout="solver internals",
            stderr="private stack trace",
            error_payload={"message": "Julia exploded at C:/secret/model.jl"},
            error_message="Julia exploded at C:/secret/model.jl",
            stdout_log_path="C:/secret/stdout.log",
            stderr_log_path="C:/secret/stderr.log",
        )
        self.login("operator@example.local", "operator pass")

        response = self.client.get(
            f"/api/console/{console['id']}/runs/{run['id']}"
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["failure"],
            {
                "cause": "ejecucion_fallida",
                "message": "La ejecucion fallo. Comunica la referencia al ingeniero.",
                "reference": str(run["id"]),
            },
        )
        self.assertIsNone(response.json()["results_block"])
        for forbidden in [
            "stdout",
            "stderr",
            "exit_code",
            "error_message",
            "workspace_path",
            "input_snapshot_path",
            "C:/secret",
            "Julia exploded",
            "private stack trace",
            "solver internals",
        ]:
            with self.subTest(forbidden):
                self.assertNotIn(forbidden, response.text)

    def test_a_succeeded_run_returns_only_configured_shared_results(self):
        result_document = {
            **NORMATIVE_DOCUMENT,
            "results": {
                "kpis": [
                    {
                        "id": "beneficio_total",
                        "path": "objective_value_usd",
                        "label": "Beneficio total",
                        "unit": "USD",
                        "decimals": 1,
                        "sign": "auto",
                        "emphasis": "strong",
                    }
                ],
                "charts": [],
                "tables": [],
            },
        }
        console = self.create_console(status="draft")
        console = self.store.save_operator_console(
            console["id"],
            document=result_document,
            status="active",
            expected_revision=1,
            updated_by_user_id=None,
        )
        version = self.store.create_scenario_version(
            scenario_id=self.scenario["id"],
            system_case_json={
                "schema_version": "bess_system_dispatch.v2",
                "case_name": "safe_results_case",
                "nodes": [],
                "edges": [],
                "time_series": [],
            },
            validation_payload={"status": "ok"},
        )
        run = self.store.create_run(
            scenario_version_id=version["id"],
            triggered_by="operator@example.local",
            trigger_type="operator_console",
            triggered_by_user_id=self.operator["id"],
            triggered_by_display_name="Olga Operadora",
            operator_console_id=console["id"],
            operator_console_revision=console["revision"],
        )
        output_dir = Path(self.artifact_temp.name) / "runs" / str(run["id"]) / "outputs"
        output_dir.mkdir(parents=True)
        summary_path = output_dir / "summary.json"
        dispatch_path = output_dir / "dispatch.csv"
        asset_dispatch_path = output_dir / "asset_dispatch.csv"
        summary_path.write_text(
            '{"objective_value_usd":1250.5,"workspace_path":"C:/secret",'
            '"stdout":"private","case_name":"hidden","all_series":[1,2,3]}',
            encoding="utf-8",
        )
        dispatch_path.write_text(
            "timestamp,grid_import_mw,source_identifiers\n"
            "2026-01-01T00:00:00,2.5,secret\n",
            encoding="utf-8",
        )
        asset_dispatch_path.write_text(
            "timestamp,asset_id,asset_type\n2026-01-01T00:00:00,grid_1,grid\n",
            encoding="utf-8",
        )
        self.store.mark_run_running(
            run["id"],
            workspace_path=str(output_dir.parent),
            input_snapshot_path=str(output_dir.parent / "input" / "system_case.json"),
        )
        self.store.mark_run_succeeded(
            run["id"],
            exit_code=0,
            stdout="sensitive stdout",
            stderr="sensitive stderr",
            success_payload={"schema_version": "internal"},
            output_dir=str(output_dir),
            summary_path=str(summary_path),
        )
        for artifact_type, path, media_type in [
            ("summary_json", summary_path, "application/json"),
            ("dispatch_csv", dispatch_path, "text/csv"),
            ("asset_dispatch_csv", asset_dispatch_path, "text/csv"),
        ]:
            self.store.register_run_artifact(
                run_id=run["id"],
                artifact_type=artifact_type,
                path=str(path),
                display_name=path.name,
                media_type=media_type,
            )
        self.login("operator@example.local", "operator pass")

        response = self.client.get(
            f"/api/console/{console['id']}/runs/{run['id']}"
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["results_block"],
            {
                "labels": {
                    "kpis": "Indicadores",
                    "charts": "",
                    "tables": "",
                    "downloads": "",
                },
                "kpis": [
                    {
                        "id": "beneficio_total",
                        "label": "Beneficio total",
                        "value": 1250.5,
                        "unit": "USD",
                        "decimals": 1,
                        "sign": "auto",
                        "emphasis": "strong",
                    }
                ],
                "charts": [],
                "tables": [],
            },
        )
        for forbidden in [
            "workspace_path",
            "stdout",
            "stderr",
            "exit_code",
            "case_name",
            "schema_version",
            "asset_id",
            "source_identifiers",
            "all_series",
            str(Path(self.artifact_temp.name)),
        ]:
            with self.subTest(forbidden):
                self.assertNotIn(forbidden, response.text)

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

    def test_revocation_blocks_new_console_work_without_cancelling_a_started_run(self):
        console = self.create_console(status="active")
        version = self.store.create_scenario_version(
            scenario_id=self.scenario["id"],
            system_case_json={
                "schema_version": "bess_system_dispatch.v2",
                "case_name": "started_case",
                "nodes": [],
                "edges": [],
                "time_series": [],
            },
            validation_payload={"status": "ok"},
        )
        run = self.store.create_run(
            scenario_version_id=version["id"],
            triggered_by="operator@example.local",
            trigger_type="operator_console",
            triggered_by_user_id=self.operator["id"],
            triggered_by_display_name="Olga Operadora",
            operator_console_id=console["id"],
            operator_console_revision=console["revision"],
        )
        self.store.mark_run_running(
            run["id"],
            workspace_path="C:/artifacts/started",
            input_snapshot_path="C:/artifacts/started/input/system_case.json",
        )
        self.login("operator@example.local", "operator pass")
        self.store.revoke_external_project_access(
            project_id=self.project["id"],
            user_id=self.operator["id"],
            updated_by="admin@example.local",
        )

        mutation = put_json_with_csrf(
            self.client,
            f"/api/console/{console['id']}/parameters",
            {"parameters": []},
        )
        detail = self.client.get(
            f"/api/console/{console['id']}/runs/{run['id']}"
        )

        self.assertEqual(mutation.status_code, 404, mutation.text)
        self.assertEqual(detail.status_code, 404, detail.text)
        self.assertEqual(self.store.get_run(run["id"])["status"], "running")

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
