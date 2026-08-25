"""BESS-CONFIG-014: fail closed and request engineer review after external changes.

An operator save attests only the operational copies it wrote. Anything an
analyst moved underneath the console blocks it before a version or a run
exists, translated into the operator's vocabulary, with the preparer's public
name and nothing else.
"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.operator_console import (
    CONSOLE_REVIEWABLE_REASONS,
    CONSOLE_RUN_GATE_REASONS,
    OperatorConsoleConfigurationError,
    build_console_run_gate,
)
from app.persistence import AnalystStore
from app.surface_payloads import build_console_payload
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


CASE_DRAFT_DOCUMENT = {
    "schema_version": "bess_editor_draft.v1",
    "case": {"name": "console_case", "description": ""},
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
        },
        {"id": "load_1", "type": "load"},
    ],
    "time_series": {"sources": []},
    "solver": {"name": "HiGHS", "options": {}},
}


def case_draft_with_discharge_power(discharge_power_max_mw):
    return {
        **CASE_DRAFT_DOCUMENT,
        "assets": [
            {
                **CASE_DRAFT_DOCUMENT["assets"][0],
                "discharge_power_max_mw": discharge_power_max_mw,
            },
            CASE_DRAFT_DOCUMENT["assets"][1],
        ],
    }


def console_document(demand_set_id, *, pointer_field="discharge_power_max_mw"):
    return {
        "schema_version": "operator_console_config.v1",
        "public_identity": {
            "name": "Plan diario Planta Norte",
            "description": "Ajuste de demanda y corrida diaria",
        },
        "parameters": [
            {
                "id": "potencia_bess",
                "pointer": {"asset_id": "battery_1", "field": pointer_field},
                "label": "Potencia maxima BESS",
                "unit": "MW",
                "min": 0,
                "max": 100,
                "default": 4,
            }
        ],
        "groups": [
            {
                "id": "potencia",
                "label": "Potencia",
                "granularities": ["full_horizon"],
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
                            {
                                "id": "base",
                                "label": "Demanda base",
                                "time_series_set_id": demand_set_id,
                            }
                        ],
                        "default_source_option_id": "base",
                    }
                ],
            }
        ],
        "results": {"kpis": [], "charts": [], "tables": []},
    }


def import_demand_set(store, scenario_id, *, name="Demanda base", first_value=10):
    start = datetime(2026, 1, 1)
    prepared = prepare_time_series_catalog_import(
        rows=[
            {
                "period_start": (start + timedelta(hours=offset)).isoformat(),
                "hours": "1.0",
                "demand": str(first_value + offset),
            }
            for offset in range(4)
        ],
        request=CatalogImportRequest(
            set_name=name,
            version_label="v1",
            data_kind="real",
            timezone="America/Santiago",
            timestamp_column="period_start",
            duration_hours_column="hours",
            signal_mappings=[
                CatalogSignalMappingRequest(
                    source_column="demand", signal_key="load_demand_mw"
                )
            ],
        ),
    )
    return store.import_time_series_catalog_set(
        scenario_id=scenario_id,
        source={
            "id": f"{name}-source",
            "original_filename": "demanda.csv",
            "media_type": "text/csv",
            "checksum": f"sha256:{name}",
        },
        prepared_import=prepared,
    )


def import_price_set(store, scenario_id):
    start = datetime(2026, 1, 1)
    prepared = prepare_time_series_catalog_import(
        rows=[
            {
                "period_start": (start + timedelta(hours=offset)).isoformat(),
                "hours": "1.0",
                "spot": str(50 + offset),
            }
            for offset in range(4)
        ],
        request=CatalogImportRequest(
            set_name="Precio spot",
            version_label="v1",
            data_kind="real",
            timezone="America/Santiago",
            timestamp_column="period_start",
            duration_hours_column="hours",
            signal_mappings=[
                CatalogSignalMappingRequest(
                    source_column="spot", signal_key="price_usd_per_mwh"
                )
            ],
        ),
    )
    return store.import_time_series_catalog_set(
        scenario_id=scenario_id,
        source={
            "id": "precio-source",
            "original_filename": "precio.csv",
            "media_type": "text/csv",
            "checksum": "sha256:precio",
        },
        prepared_import=prepared,
    )


class ConsoleRunGateTests(unittest.TestCase):
    """The single translation from internal state to the operator's gate."""

    def test_a_moved_dependency_closes_the_gate_with_an_actionable_spanish_reason(self):
        gate = build_console_run_gate(
            moved_dependency=True,
            contact="Ana Analista",
            review_requested_at="2026-08-25T12:00:00",
        )

        self.assertEqual(
            gate,
            {
                "can_run": False,
                "reason": "dependencia_movida",
                "message": "Los datos base cambiaron; solicita revision de ingenieria.",
                "contact": "Ana Analista",
                "editing_locked_by": None,
                "review_requested_at": "2026-08-25T12:00:00",
            },
        )

    def test_an_unavailable_parameter_and_an_unavailable_series_read_differently(self):
        parameter_gate = build_console_run_gate(
            unavailable_parameter=True, contact="Ana Analista"
        )
        series_gate = build_console_run_gate(
            unavailable_series=True, contact="Ana Analista"
        )

        self.assertEqual(
            (parameter_gate["reason"], parameter_gate["message"]),
            (
                "campo_no_disponible",
                "Un parametro configurado ya no esta disponible.",
            ),
        )
        self.assertEqual(
            (series_gate["reason"], series_gate["message"]),
            ("campo_no_disponible", "Una serie configurada ya no esta disponible."),
        )

    def test_another_editor_wins_over_every_engineering_block_and_names_nobody_else(self):
        gate = build_console_run_gate(
            editing_locked_by="Otro Operador",
            unavailable_parameter=True,
            moved_dependency=True,
            contact="Ana Analista",
            review_requested_at="2026-08-25T12:00:00",
        )

        self.assertEqual(
            gate,
            {
                "can_run": False,
                "reason": "edicion_de_otro_usuario",
                "message": "Otro Operador esta editando este grupo.",
                "contact": None,
                "editing_locked_by": "Otro Operador",
                "review_requested_at": None,
            },
        )

    def test_a_broken_field_is_reported_ahead_of_a_moved_dependency(self):
        gate = build_console_run_gate(
            unavailable_parameter=True, moved_dependency=True, contact="Ana Analista"
        )

        self.assertEqual(gate["reason"], "campo_no_disponible")

    def test_an_open_gate_carries_no_reason_message_contact_or_pending_review(self):
        gate = build_console_run_gate(
            contact="Ana Analista", review_requested_at="2026-08-25T12:00:00"
        )

        self.assertEqual(
            gate,
            {
                "can_run": True,
                "reason": None,
                "message": "",
                "contact": None,
                "editing_locked_by": None,
                "review_requested_at": None,
            },
        )

    def test_every_gate_reason_is_declared_public_and_reviewable_ones_are_a_subset(self):
        self.assertEqual(
            set(CONSOLE_RUN_GATE_REASONS),
            {"edicion_de_otro_usuario", "campo_no_disponible", "dependencia_movida"},
        )
        self.assertTrue(
            set(CONSOLE_REVIEWABLE_REASONS).issubset(set(CONSOLE_RUN_GATE_REASONS))
        )


class ConsoleFailClosedPersistenceTestCase(unittest.TestCase):
    """One prepared console: active, validated and runnable before each test."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Planta Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=CASE_DRAFT_DOCUMENT
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.source_variant = self.store.get_or_create_default_input_variant(
            self.case["id"]
        )
        self.analyst = self.store.create_user(
            email="analyst@example.local",
            display_name="Ana Analista",
            role="analyst",
            password_hash="test-hash",
        )
        self.operator = self.store.create_user(
            email="operator@example.local",
            display_name="Olga Operadora",
            role="external",
            password_hash="test-hash",
        )
        self.demand_set = import_demand_set(self.store, self.scenario["id"])
        self.price_set = import_price_set(self.store, self.scenario["id"])
        for signal_key, entity_type, entity_id, time_series_set in (
            ("load_demand_mw", "component:load", "load_1", self.demand_set),
            ("price_usd_per_mwh", "grid", "grid_1", self.price_set),
        ):
            self.store.upsert_case_time_series_binding(
                case_input_variant_id=self.source_variant["id"],
                signal_key=signal_key,
                entity_type=entity_type,
                entity_id=entity_id,
                time_series_set_id=time_series_set["id"],
            )
        self.range_start = self.demand_set["horizon"]["start"]
        self.range_end = self.demand_set["horizon"]["end"]
        self.console = self.activate(
            self.store.create_operator_console(
                case_id=self.case["id"],
                source_variant_id=self.source_variant["id"],
                document=console_document(self.demand_set["id"]),
                created_by_user_id=self.analyst["id"],
            )
        )
        self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.console["owned_variant_id"],
            range_start=self.range_start,
            range_end=self.range_end,
        )

    def tearDown(self):
        self.store.close()

    def activate(self, console):
        return self.store.save_operator_console(
            console["id"],
            document=console["document"],
            status="active",
            expected_revision=int(console["revision"]),
            updated_by_user_id=self.analyst["id"],
        )

    def change_case_parameter(self, discharge_power_max_mw=6.0):
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"],
            document=case_draft_with_discharge_power(discharge_power_max_mw),
        )


class ConsoleBlockDescriptionTests(ConsoleFailClosedPersistenceTestCase):
    """What the store reports as blocking, before any public translation."""

    def test_a_prepared_console_reports_no_block_at_all(self):
        block = self.store.describe_operator_console_block(self.console["id"])

        self.assertEqual(
            block,
            {
                "editing_locked_by": None,
                "unavailable_parameter": False,
                "unavailable_series": False,
                "moved_dependency": False,
                "reasons": [],
            },
        )

    def test_an_analyst_parameter_change_moves_the_dependency_with_internal_detail(self):
        self.change_case_parameter()

        block = self.store.describe_operator_console_block(self.console["id"])

        self.assertTrue(block["moved_dependency"])
        self.assertFalse(block["unavailable_parameter"])
        self.assertEqual(
            [reason["dependency_type"] for reason in block["reasons"]], ["parameters"]
        )

    def test_a_configured_pointer_that_no_longer_resolves_is_an_unavailable_field(self):
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.source_variant["id"],
            document=console_document(
                self.demand_set["id"], pointer_field="inexistent_field"
            ),
            created_by_user_id=self.analyst["id"],
        )

        block = self.store.describe_operator_console_block(console["id"])

        self.assertTrue(block["unavailable_parameter"])
        self.assertFalse(block["unavailable_series"])

    def test_the_editing_holder_only_blocks_the_other_viewers(self):
        self.store.acquire_operator_console_group_lease(
            self.console["id"], group_id="potencia", user_id=self.operator["id"]
        )

        holder_block = self.store.describe_operator_console_block(
            self.console["id"], viewer_user_id=self.operator["id"]
        )
        other_block = self.store.describe_operator_console_block(
            self.console["id"], viewer_user_id=self.analyst["id"]
        )

        self.assertIsNone(holder_block["editing_locked_by"])
        self.assertEqual(other_block["editing_locked_by"], "Olga Operadora")


class ConsoleReviewRequestPersistenceTests(ConsoleFailClosedPersistenceTestCase):
    """`waiting_since` is the whole review mechanism: no queue behind it."""

    def test_a_blocked_console_records_when_the_operator_started_waiting(self):
        self.change_case_parameter()

        console = self.store.request_operator_console_review(self.console["id"])

        self.assertIsNotNone(console["waiting_since"])
        self.assertEqual(
            self.store.get_operator_console(self.console["id"])["waiting_since"],
            console["waiting_since"],
        )

    def test_a_second_request_keeps_the_original_wait_and_never_escalates(self):
        self.change_case_parameter()
        first = self.store.request_operator_console_review(self.console["id"])

        second = self.store.request_operator_console_review(self.console["id"])

        self.assertEqual(second["waiting_since"], first["waiting_since"])

    def test_requesting_review_changes_nothing_but_the_wait(self):
        self.change_case_parameter()
        before = self.store.get_operator_console(self.console["id"])

        after = self.store.request_operator_console_review(self.console["id"])

        self.assertEqual(
            {key: value for key, value in after.items() if key != "waiting_since"},
            {key: value for key, value in before.items() if key != "waiting_since"},
        )

    def test_a_runnable_console_cannot_be_marked_as_waiting(self):
        with self.assertRaises(OperatorConsoleConfigurationError) as raised:
            self.store.request_operator_console_review(self.console["id"])

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIsNone(
            self.store.get_operator_console(self.console["id"])["waiting_since"]
        )

    def test_another_operator_editing_is_not_an_engineering_block(self):
        self.store.acquire_operator_console_group_lease(
            self.console["id"], group_id="potencia", user_id=self.operator["id"]
        )

        with self.assertRaises(OperatorConsoleConfigurationError):
            self.store.request_operator_console_review(self.console["id"])

    def test_an_unavailable_configured_field_is_worth_a_review_request(self):
        console = self.activate(
            self.store.create_operator_console(
                case_id=self.case["id"],
                source_variant_id=self.source_variant["id"],
                document=console_document(
                    self.demand_set["id"], pointer_field="inexistent_field"
                ),
                created_by_user_id=self.analyst["id"],
            )
        )

        requested = self.store.request_operator_console_review(console["id"])

        self.assertIsNotNone(requested["waiting_since"])


class ConsolePayloadBoundaryTests(unittest.TestCase):
    """The gate that leaves the boundary is an allowlist, not a projection."""

    def test_raw_staleness_detail_cannot_ride_along_with_the_public_gate(self):
        payload = build_console_payload(
            console={
                "id": 7,
                "document": {"public_identity": {"name": "Plan", "description": ""}},
                "updated_at": "2026-08-25T10:00:00",
            },
            prepared_by="Ana Analista",
            run_gate={
                "can_run": False,
                "reason": "dependencia_movida",
                "message": "Los datos base cambiaron; solicita revision de ingenieria.",
                "contact": "Ana Analista",
                "editing_locked_by": None,
                "review_requested_at": "2026-08-25T12:00:00",
                "reasons": [
                    {
                        "dependency_type": "parameters",
                        "dependency_id": None,
                        "detail": "case parameters changed since last validation",
                    }
                ],
                "owned_variant_id": 42,
            },
        )

        self.assertEqual(
            payload["run_gate"],
            {
                "can_run": False,
                "reason": "dependencia_movida",
                "message": "Los datos base cambiaron; solicita revision de ingenieria.",
                "contact": "Ana Analista",
                "editing_locked_by": None,
                "review_requested_at": "2026-08-25T12:00:00",
            },
        )


class ConsoleSaveAttestationTests(ConsoleFailClosedPersistenceTestCase):
    """A save attests the copies it wrote, and nothing whatsoever besides."""

    def save_a_demand_cell(self, value=99.5):
        loaded = self.store.resolve_operator_console_group_values(
            self.console["id"],
            group_id="potencia",
            range_start=self.range_start,
            range_end=self.range_end,
            granularity="full_horizon",
        )
        lease = self.store.acquire_operator_console_group_lease(
            self.console["id"], group_id="potencia", user_id=self.operator["id"]
        )
        return self.store.save_operator_console_group_values(
            self.console["id"],
            group_id="potencia",
            range_start=self.range_start,
            range_end=self.range_end,
            granularity="full_horizon",
            expected_token=loaded["token"],
            lease_token=lease["token"],
            cells=[{"column_id": "demanda", "row_index": 1, "value": value}],
            note="Ajuste manual",
            actor_user_id=self.operator["id"],
        )

    def test_an_accepted_save_runs_immediately_when_nothing_else_moved(self):
        self.save_a_demand_cell()

        block = self.store.describe_operator_console_block(self.console["id"])

        self.assertEqual(
            (block["moved_dependency"], block["unavailable_parameter"]), (False, False)
        )

    def test_saving_a_series_cannot_attest_a_parameter_the_analyst_moved(self):
        self.change_case_parameter()

        self.save_a_demand_cell()

        block = self.store.describe_operator_console_block(self.console["id"])
        self.assertTrue(block["moved_dependency"])
        self.assertEqual(
            [reason["dependency_type"] for reason in block["reasons"]], ["parameters"]
        )

    def test_an_operator_mutation_never_rewrites_the_topology_or_parameter_hash(self):
        recorded_before = {
            (dependency["dependency_type"], dependency["dependency_id"]): dependency[
                "hash"
            ]
            for dependency in self.store.get_case_input_variant_validation_dependencies(
                self.console["owned_variant_id"]
            )
            if dependency["dependency_type"] in {"topology", "parameters"}
        }
        self.change_case_parameter()

        self.save_a_demand_cell()

        recorded_after = {
            (dependency["dependency_type"], dependency["dependency_id"]): dependency[
                "hash"
            ]
            for dependency in self.store.get_case_input_variant_validation_dependencies(
                self.console["owned_variant_id"]
            )
            if dependency["dependency_type"] in {"topology", "parameters"}
        }
        self.assertEqual(recorded_after, recorded_before)

    def test_saving_a_series_cannot_repair_a_configured_field_that_is_gone(self):
        broken = self.activate(
            self.store.create_operator_console(
                case_id=self.case["id"],
                source_variant_id=self.source_variant["id"],
                document=console_document(
                    self.demand_set["id"], pointer_field="inexistent_field"
                ),
                created_by_user_id=self.analyst["id"],
            )
        )
        loaded = self.store.resolve_operator_console_group_values(
            broken["id"],
            group_id="potencia",
            range_start=self.range_start,
            range_end=self.range_end,
            granularity="full_horizon",
        )
        lease = self.store.acquire_operator_console_group_lease(
            broken["id"], group_id="potencia", user_id=self.operator["id"]
        )
        self.store.save_operator_console_group_values(
            broken["id"],
            group_id="potencia",
            range_start=self.range_start,
            range_end=self.range_end,
            granularity="full_horizon",
            expected_token=loaded["token"],
            lease_token=lease["token"],
            cells=[{"column_id": "demanda", "row_index": 0, "value": 42.0}],
            note="Ajuste manual",
            actor_user_id=self.operator["id"],
        )

        self.assertTrue(
            self.store.describe_operator_console_block(broken["id"])[
                "unavailable_parameter"
            ]
        )


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


class ConsoleFailClosedApiTests(unittest.TestCase):
    """What an operator sees, and may ask for, once the ground moved."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.artifact_temp = tempfile.TemporaryDirectory()
        self.run_queue = RecordingRunQueue()
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                store=self.store,
                auth_enabled=True,
                run_queue=self.run_queue,
                artifact_root=Path(self.artifact_temp.name),
            )
        )
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
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=CASE_DRAFT_DOCUMENT
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.source_variant = self.store.get_or_create_default_input_variant(
            self.case["id"]
        )
        self.store.set_external_project_access(
            project_id=self.project["id"],
            user_id=self.operator["id"],
            portal_view=False,
            operate=True,
            updated_by="admin@example.local",
        )
        self.demand_set = import_demand_set(self.store, self.scenario["id"])
        self.price_set = import_price_set(self.store, self.scenario["id"])
        for signal_key, entity_type, entity_id, time_series_set in (
            ("load_demand_mw", "component:load", "load_1", self.demand_set),
            ("price_usd_per_mwh", "grid", "grid_1", self.price_set),
        ):
            self.store.upsert_case_time_series_binding(
                case_input_variant_id=self.source_variant["id"],
                signal_key=signal_key,
                entity_type=entity_type,
                entity_id=entity_id,
                time_series_set_id=time_series_set["id"],
            )
        self.range_start = self.demand_set["horizon"]["start"]
        self.range_end = self.demand_set["horizon"]["end"]
        self.console = self.create_console(status="active")
        self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.console["owned_variant_id"],
            range_start=self.range_start,
            range_end=self.range_end,
        )

    def tearDown(self):
        self.store.close()
        self.artifact_temp.cleanup()

    def create_console(self, *, status, pointer_field="discharge_power_max_mw"):
        document = console_document(
            self.demand_set["id"], pointer_field=pointer_field
        )
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.source_variant["id"],
            document=document,
            created_by_user_id=self.analyst["id"],
        )
        if status == "active":
            console = self.store.save_operator_console(
                console["id"],
                document=document,
                status="active",
                expected_revision=int(console["revision"]),
                updated_by_user_id=self.analyst["id"],
            )
        return console

    def login(self, email, password):
        self.assertEqual(
            login_json_with_csrf(self.client, email, password).status_code, 200
        )

    def move_the_case_parameter(self):
        self.login("analyst@example.local", "analyst pass")
        response = put_json_with_csrf(
            self.client,
            f"/api/scenarios/{self.scenario['id']}/draft",
            {"document": case_draft_with_discharge_power(6.0)},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def test_an_analyst_parameter_change_closes_the_gate_for_the_operator(self):
        self.move_the_case_parameter()
        self.login("operator@example.local", "operator pass")

        response = self.client.get(f"/api/console/{self.console['id']}")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["run_gate"],
            {
                "can_run": False,
                "reason": "dependencia_movida",
                "message": "Los datos base cambiaron; solicita revision de ingenieria.",
                "contact": "Ana Analista",
                "editing_locked_by": None,
                "review_requested_at": None,
            },
        )

    def test_a_moved_dependency_creates_neither_a_version_nor_a_run(self):
        self.move_the_case_parameter()
        self.login("operator@example.local", "operator pass")

        response = post_json_with_csrf(
            self.client,
            f"/api/console/{self.console['id']}/runs",
            {"range_start": self.range_start, "range_end": self.range_end},
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["run_gate"]["reason"], "dependencia_movida")
        self.assertEqual(self.store.list_scenario_versions(self.scenario["id"]), [])
        self.assertEqual(self.store.list_scenario_runs(self.scenario["id"]), [])
        self.assertEqual(self.run_queue.enqueued_run_ids, [])

    def test_an_operator_requests_review_and_sees_the_wait_on_the_next_load(self):
        self.move_the_case_parameter()
        self.login("operator@example.local", "operator pass")

        requested = post_json_with_csrf(
            self.client, f"/api/console/{self.console['id']}/request-review"
        )

        self.assertEqual(requested.status_code, 200, requested.text)
        waiting_since = requested.json()["run_gate"]["review_requested_at"]
        self.assertIsNotNone(waiting_since)
        reloaded = self.client.get(f"/api/console/{self.console['id']}")
        self.assertEqual(
            reloaded.json()["run_gate"]["review_requested_at"], waiting_since
        )

    def test_requesting_review_reaches_the_preparer_only_through_the_console_list(self):
        self.move_the_case_parameter()
        self.login("operator@example.local", "operator pass")
        post_json_with_csrf(
            self.client, f"/api/console/{self.console['id']}/request-review"
        )

        self.login("analyst@example.local", "analyst pass")
        listed = self.client.get(f"/api/scenarios/{self.scenario['id']}/consoles")

        self.assertEqual(listed.status_code, 200, listed.text)
        entry = listed.json()["operator_consoles"][0]
        self.assertIsNotNone(entry["waiting_since"])
        self.assertEqual(entry["blocking"]["reason"], "dependencia_movida")
        self.assertEqual(
            [reason["dependency_type"] for reason in entry["blocking"]["reasons"]],
            ["parameters"],
        )

    def test_a_runnable_console_refuses_the_review_request_and_records_no_wait(self):
        self.login("operator@example.local", "operator pass")

        response = post_json_with_csrf(
            self.client, f"/api/console/{self.console['id']}/request-review"
        )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertTrue(response.json()["run_gate"]["can_run"])
        self.assertIsNone(
            self.store.get_operator_console(self.console["id"])["waiting_since"]
        )

    def test_an_unavailable_configured_field_closes_the_gate_and_accepts_a_request(self):
        console = self.create_console(status="active", pointer_field="inexistent_field")
        self.login("operator@example.local", "operator pass")

        shell = self.client.get(f"/api/console/{console['id']}")
        requested = post_json_with_csrf(
            self.client, f"/api/console/{console['id']}/request-review"
        )

        self.assertEqual(shell.json()["run_gate"]["reason"], "campo_no_disponible")
        self.assertEqual(requested.status_code, 200, requested.text)
        self.assertIsNotNone(requested.json()["run_gate"]["review_requested_at"])

    def test_saving_a_case_change_warns_about_the_active_consoles_it_blocked(self):
        draft_console = self.create_console(status="draft")

        response = self.move_the_case_parameter()

        self.assertEqual(
            response.json()["affected_consoles"],
            [
                {
                    "id": self.console["id"],
                    "name": "Plan diario Planta Norte",
                    "reason": "dependencia_movida",
                }
            ],
        )
        self.assertNotIn(
            draft_console["id"],
            [entry["id"] for entry in response.json()["affected_consoles"]],
        )

    def test_the_warning_never_cancels_the_analyst_save(self):
        self.move_the_case_parameter()

        draft = self.client.get(f"/api/scenarios/{self.scenario['id']}/draft")

        self.assertEqual(
            draft.json()["draft"]["document"]["assets"][0]["discharge_power_max_mw"],
            6.0,
        )

    def test_a_case_change_that_blocks_nobody_warns_about_nobody(self):
        self.login("analyst@example.local", "analyst pass")

        response = put_json_with_csrf(
            self.client,
            f"/api/scenarios/{self.scenario['id']}/draft",
            {"document": CASE_DRAFT_DOCUMENT},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["affected_consoles"], [])

    def test_a_draft_and_a_foreign_console_cannot_be_marked_as_waiting(self):
        draft = self.create_console(status="draft")
        foreign_project = self.store.create_project(name="Planta Sur")
        foreign_scenario = self.store.create_scenario(
            project_id=foreign_project["id"], name="Otra operacion"
        )
        foreign_case = self.store.get_or_create_case_for_scenario(
            foreign_scenario["id"]
        )
        foreign_variant = self.store.get_or_create_default_input_variant(
            foreign_case["id"]
        )
        foreign_document = console_document(self.demand_set["id"])
        foreign = self.store.create_operator_console(
            case_id=foreign_case["id"],
            source_variant_id=foreign_variant["id"],
            document=foreign_document,
            created_by_user_id=self.analyst["id"],
        )
        foreign = self.store.save_operator_console(
            foreign["id"],
            document=foreign_document,
            status="active",
            expected_revision=int(foreign["revision"]),
            updated_by_user_id=self.analyst["id"],
        )
        self.login("operator@example.local", "operator pass")

        for console_id in (draft["id"], foreign["id"], 9999):
            with self.subTest(console_id=console_id):
                response = post_json_with_csrf(
                    self.client, f"/api/console/{console_id}/request-review"
                )
                self.assertEqual(response.status_code, 404, response.text)
        self.assertIsNone(
            self.store.get_operator_console(draft["id"])["waiting_since"]
        )
        self.assertIsNone(
            self.store.get_operator_console(foreign["id"])["waiting_since"]
        )


if __name__ == "__main__":
    unittest.main()
