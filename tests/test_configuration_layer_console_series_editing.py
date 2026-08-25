"""BESS-CONFIG-010: editing one exposed series without touching canonical data.

The operator works with external group and column ids only. The first accepted
edit forks a flat operational copy that belongs to the console variant; the
canonical set and every other variant keep their ids, revisions and values.
"""

import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.console_series import ConsoleSeriesError
from app.input_variants import InputVariantRangeError
from app.main import create_app
from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    CatalogValueEdit,
    prepare_time_series_catalog_import,
)
from tests.auth_test_helpers import (
    csrf_headers,
    delete_with_csrf,
    login_json_with_csrf,
    post_json_with_csrf,
    put_json_with_csrf,
)


CONSOLE_DOCUMENT = {
    "schema_version": "operator_console_config.v1",
    "public_identity": {
        "name": "Plan diario Planta Norte",
        "description": "Ajuste de demanda y corrida diaria",
    },
    "parameters": [],
    "groups": [
        {
            "id": "potencia",
            "label": "Potencia",
            "granularities": ["day", "full_horizon"],
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
                        {"id": "base", "label": "Demanda base", "time_series_set_id": 1}
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


class ConsoleSeriesEditingPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Planta Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
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
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.source_variant["id"],
            signal_key="load_demand_mw",
            time_series_set_id=self.demand_set["id"],
        )
        self.console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.source_variant["id"],
            document=self.document(),
            created_by_user_id=self.analyst["id"],
        )

    def tearDown(self):
        self.store.close()

    def document(self):
        group = CONSOLE_DOCUMENT["groups"][0]
        column = group["columns"][0]
        return {
            **CONSOLE_DOCUMENT,
            "groups": [
                {
                    **group,
                    "columns": [
                        {
                            **column,
                            "source_options": [
                                {
                                    "id": "base",
                                    "label": "Demanda base",
                                    "time_series_set_id": self.demand_set["id"],
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def test_loading_a_group_returns_public_columns_and_rows_for_the_range(self):
        loaded = self.store.resolve_operator_console_group_values(
            self.console["id"],
            group_id="potencia",
            range_start=self.demand_set["horizon"]["start"],
            range_end=self.demand_set["horizon"]["end"],
            granularity="full_horizon",
        )

        self.assertEqual(
            loaded["columns"],
            [
                {
                    "id": "demanda",
                    "label": "Demanda",
                    "unit": "MW",
                    "nonnegative": True,
                    "editable": True,
                }
            ],
        )
        self.assertEqual(
            loaded["rows"],
            [
                {
                    "index": index,
                    "timestamp": f"2026-01-01T{index:02d}:00:00-03:00",
                    "values": {"demanda": float(10 + index)},
                }
                for index in range(4)
            ],
        )

    def load(self, **overrides):
        request = {
            "group_id": "potencia",
            "range_start": self.demand_set["horizon"]["start"],
            "range_end": self.demand_set["horizon"]["end"],
            "granularity": "full_horizon",
        }
        request.update(overrides)
        return self.store.resolve_operator_console_group_values(
            self.console["id"], **request
        )

    def save(self, cells, *, expected_token=None, **overrides):
        request = {
            "group_id": "potencia",
            "range_start": self.demand_set["horizon"]["start"],
            "range_end": self.demand_set["horizon"]["end"],
            "granularity": "full_horizon",
            "expected_token": expected_token or self.load()["token"],
            "cells": cells,
            "note": "Ajuste manual",
            "actor_user_id": self.operator["id"],
        }
        request.update(overrides)
        if "lease_token" not in request:
            request["lease_token"] = self.store.acquire_operator_console_group_lease(
                self.console["id"],
                group_id=str(request["group_id"]),
                user_id=int(request["actor_user_id"]),
            )["token"]
        return self.store.save_operator_console_group_values(
            self.console["id"], **request
        )

    def test_a_first_edit_forks_a_flat_copy_and_rebinds_only_the_console_variant(self):
        canonical_before = self.store.get_time_series_set(
            self.project["id"], self.demand_set["id"]
        )

        self.save([{"column_id": "demanda", "row_index": 1, "value": 99.5}])

        canonical_after = self.store.get_time_series_set(
            self.project["id"], self.demand_set["id"]
        )
        self.assertEqual(canonical_after, canonical_before)

        copies = self.store.list_operator_console_series_copies(self.console["id"])
        self.assertEqual(len(copies), 1)
        copy = copies[0]
        self.assertEqual(copy["origin_set_id"], self.demand_set["id"])
        self.assertEqual(
            copy["origin_revision_number"], self.demand_set["revision_number"]
        )
        self.assertIsNone(copy["archived_at"])
        self.assertNotEqual(copy["time_series_set_id"], self.demand_set["id"])

        console_bindings = self.store.list_case_time_series_bindings(
            self.console["owned_variant_id"]
        )
        self.assertEqual(
            [binding["time_series_set_id"] for binding in console_bindings],
            [copy["time_series_set_id"]],
        )
        source_bindings = self.store.list_case_time_series_bindings(
            self.source_variant["id"]
        )
        self.assertEqual(
            [binding["time_series_set_id"] for binding in source_bindings],
            [self.demand_set["id"]],
        )

    def test_the_operational_copy_is_flat_non_derived_with_inert_lineage(self):
        self.save([{"column_id": "demanda", "row_index": 1, "value": 99.5}])
        copy = self.store.list_operator_console_series_copies(self.console["id"])[0]

        copied_set = self.store.get_time_series_set(
            self.project["id"], copy["time_series_set_id"]
        )
        revisions = self.store.list_time_series_set_revisions(
            self.project["id"], copy["time_series_set_id"]
        )

        self.assertEqual(
            self.store.get_time_series_set_validation_dependencies(
                copy["time_series_set_id"]
            ),
            [],
        )
        self.assertFalse(
            self.store.evaluate_time_series_set_staleness(
                self.project["id"], copy["time_series_set_id"]
            )["stale"]
        )
        self.assertEqual(
            [revision["revision_number"] for revision in revisions], [2, 1]
        )
        self.assertEqual(
            copied_set["revision_metadata"]["origin"],
            {
                "time_series_set_id": self.demand_set["id"],
                "revision_number": self.demand_set["revision_number"],
            },
        )
        self.assertEqual(
            [value["value_numeric"] for value in copied_set["values"]],
            [10.0, 99.5, 12.0, 13.0],
        )

    def test_the_edited_values_are_what_the_console_reads_back(self):
        before = self.load()

        self.save([{"column_id": "demanda", "row_index": 1, "value": 99.5}])
        after = self.load()

        self.assertEqual(
            [row["values"]["demanda"] for row in after["rows"]],
            [10.0, 99.5, 12.0, 13.0],
        )
        self.assertNotEqual(after["token"], before["token"])

    def test_a_stale_token_is_rejected_without_writing_anything(self):
        stale_token = self.load()["token"]
        self.save([{"column_id": "demanda", "row_index": 0, "value": 21.0}])
        canonical_before = self.store.get_time_series_set(
            self.project["id"], self.demand_set["id"]
        )
        copy = self.store.list_operator_console_series_copies(self.console["id"])[0]
        copied_before = self.store.get_time_series_set(
            self.project["id"], copy["time_series_set_id"]
        )

        with self.assertRaises(ConsoleSeriesError) as raised:
            self.save(
                [{"column_id": "demanda", "row_index": 0, "value": 33.0}],
                expected_token=stale_token,
            )

        self.assertEqual(raised.exception.status_code, 412)
        self.assertEqual(
            self.store.get_time_series_set(self.project["id"], self.demand_set["id"]),
            canonical_before,
        )
        self.assertEqual(
            self.store.get_time_series_set(
                self.project["id"], copy["time_series_set_id"]
            ),
            copied_before,
        )

    def test_an_invalid_cell_rejects_the_whole_block_in_external_coordinates(self):
        invalid_blocks = {
            "outside the loaded range": (
                [
                    {"column_id": "demanda", "row_index": 0, "value": 21.0},
                    {"column_id": "demanda", "row_index": 9, "value": 22.0},
                ],
                "tramo",
            ),
            "negative on a nonnegative signal": (
                [{"column_id": "demanda", "row_index": 0, "value": -1.0}],
                "negativos",
            ),
            "not a number": (
                [{"column_id": "demanda", "row_index": 0, "value": "21,0"}],
                "numerico",
            ),
            "unknown column": (
                [{"column_id": "inexistente", "row_index": 0, "value": 21.0}],
                "columna",
            ),
        }

        for name, (cells, expected) in invalid_blocks.items():
            with self.subTest(name):
                with self.assertRaises(ConsoleSeriesError) as raised:
                    self.save(cells)
                error = raised.exception
                self.assertEqual(error.status_code, 400)
                self.assertIn(expected, error.cells[0]["message"])
                self.assertEqual(error.cells[0]["group_id"], "potencia")
                self.assertEqual(
                    self.store.list_operator_console_series_copies(self.console["id"]),
                    [],
                )

    def test_a_read_only_column_cannot_be_edited(self):
        group = self.document()["groups"][0]
        column = group["columns"][0]
        self.store.save_operator_console(
            self.console["id"],
            document={
                **self.document(),
                "groups": [
                    {**group, "columns": [{**column, "editable": False}]}
                ],
            },
            status="active",
            expected_revision=self.console["revision"],
            updated_by_user_id=self.analyst["id"],
        )

        with self.assertRaises(ConsoleSeriesError) as raised:
            self.save([{"column_id": "demanda", "row_index": 0, "value": 21.0}])

        self.assertEqual(
            raised.exception.cells[0]["message"], "la columna no es editable"
        )
        self.assertEqual(
            self.store.list_operator_console_series_copies(self.console["id"]), []
        )

    def test_every_invalid_cell_is_validated_and_at_most_one_hundred_reported(self):
        cells = [
            {"column_id": "demanda", "row_index": index % 4, "value": -1.0}
            for index in range(150)
        ]

        with self.assertRaises(ConsoleSeriesError) as raised:
            self.save(cells)

        error = raised.exception
        self.assertEqual(error.total_cells, 150)
        self.assertEqual(len(error.cells), 100)

    def test_a_range_the_group_does_not_cover_is_refused(self):
        with self.assertRaises(InputVariantRangeError):
            self.load(range_end="2026-01-02T00:00:00-03:00")

    def test_a_granularity_wider_than_configured_is_refused(self):
        with self.assertRaises(ConsoleSeriesError) as raised:
            self.load(granularity="week")

        self.assertIn("granularity", str(raised.exception))
    def test_only_the_lease_holder_may_save(self):
        other = self.store.create_user(
            email="other@example.local",
            display_name="Otro Operador",
            role="external",
            password_hash="test-hash",
        )
        lease = self.store.acquire_operator_console_group_lease(
            self.console["id"], group_id="potencia", user_id=self.operator["id"]
        )

        with self.assertRaises(ConsoleSeriesError) as raised:
            self.save(
                [{"column_id": "demanda", "row_index": 0, "value": 21.0}],
                lease_token=lease["token"],
                actor_user_id=other["id"],
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            self.store.list_operator_console_series_copies(self.console["id"]), []
        )

    def test_a_second_editor_cannot_take_a_held_lease(self):
        other = self.store.create_user(
            email="other@example.local",
            display_name="Otro Operador",
            role="external",
            password_hash="test-hash",
        )
        self.store.acquire_operator_console_group_lease(
            self.console["id"], group_id="potencia", user_id=self.operator["id"]
        )

        with self.assertRaises(ConsoleSeriesError) as raised:
            self.store.acquire_operator_console_group_lease(
                self.console["id"], group_id="potencia", user_id=other["id"]
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            self.store.describe_operator_console_group_lease(
                self.console["id"], group_id="potencia"
            )["holder_name"],
            "Olga Operadora",
        )

    def test_a_released_lease_is_free_for_the_next_editor(self):
        other = self.store.create_user(
            email="other@example.local",
            display_name="Otro Operador",
            role="external",
            password_hash="test-hash",
        )
        lease = self.store.acquire_operator_console_group_lease(
            self.console["id"], group_id="potencia", user_id=self.operator["id"]
        )
        self.store.release_operator_console_group_lease(
            self.console["id"],
            group_id="potencia",
            user_id=self.operator["id"],
            lease_token=lease["token"],
        )

        taken = self.store.acquire_operator_console_group_lease(
            self.console["id"], group_id="potencia", user_id=other["id"]
        )

        self.assertEqual(taken["holder_name"], "Otro Operador")
        self.assertEqual(
            self.store.describe_operator_console_group_lease(
                self.console["id"], group_id="potencia"
            )["holder_user_id"],
            other["id"],
        )

    def test_an_unheld_group_reports_no_editing_lock(self):
        self.assertEqual(
            self.store.describe_operator_console_group_lease(
                self.console["id"], group_id="potencia"
            ),
            {"holder_user_id": None, "holder_name": None, "expires_at": None},
        )

    def test_the_holder_keeps_the_lease_across_the_copy_fork(self):
        lease = self.store.acquire_operator_console_group_lease(
            self.console["id"], group_id="potencia", user_id=self.operator["id"]
        )

        self.save(
            [{"column_id": "demanda", "row_index": 0, "value": 21.0}],
            lease_token=lease["token"],
        )
        self.save(
            [{"column_id": "demanda", "row_index": 2, "value": 22.0}],
            lease_token=lease["token"],
        )

        self.assertEqual(
            len(self.store.list_operator_console_series_copies(self.console["id"])), 1
        )
        self.assertEqual(
            [row["values"]["demanda"] for row in self.load()["rows"]],
            [21.0, 11.0, 22.0, 13.0],
        )

CONSOLE_DRAFT_DOCUMENT = {
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


class ConsoleMultiSetPersistenceTests(unittest.TestCase):
    """One configured group may atomically span several operational copies."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Planta Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=CONSOLE_DRAFT_DOCUMENT
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.source_variant = self.store.get_or_create_default_input_variant(
            self.case["id"]
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
        demand_column = CONSOLE_DOCUMENT["groups"][0]["columns"][0]
        document = {
            **CONSOLE_DOCUMENT,
            "groups": [
                {
                    **CONSOLE_DOCUMENT["groups"][0],
                    "granularities": ["day", "week", "month", "full_horizon"],
                    "columns": [
                        {
                            **demand_column,
                            "source_options": [
                                {
                                    "id": "base",
                                    "label": "Demanda base",
                                    "time_series_set_id": self.demand_set["id"],
                                }
                            ],
                        },
                        {
                            "id": "precio",
                            "signal": {
                                "entity_type": "grid",
                                "entity_id": "grid_1",
                                "signal_key": "price_usd_per_mwh",
                            },
                            "label": "Precio",
                            "editable": True,
                            "source_options": [
                                {
                                    "id": "base",
                                    "label": "Precio base",
                                    "time_series_set_id": self.price_set["id"],
                                }
                            ],
                            "default_source_option_id": "base",
                        },
                    ],
                }
            ],
        }
        self.console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.source_variant["id"],
            document=document,
            created_by_user_id=None,
        )
        self.range_start = self.demand_set["horizon"]["start"]
        self.range_end = self.demand_set["horizon"]["end"]

    def tearDown(self):
        self.store.close()

    def load(self):
        return self.store.resolve_operator_console_group_values(
            self.console["id"],
            group_id="potencia",
            range_start=self.range_start,
            range_end=self.range_end,
            granularity="full_horizon",
        )

    def test_every_configured_granularity_keeps_the_same_native_group_range(self):
        for granularity in ("day", "week", "month", "full_horizon"):
            with self.subTest(granularity=granularity):
                loaded = self.store.resolve_operator_console_group_values(
                    self.console["id"],
                    group_id="potencia",
                    range_start=self.range_start,
                    range_end=self.range_end,
                    granularity=granularity,
                )
                self.assertEqual(loaded["granularity"], granularity)
                self.assertEqual(
                    loaded["range"],
                    {"start": self.range_start, "end": self.range_end},
                )
                self.assertEqual(len(loaded["rows"]), 4)

    def test_one_save_creates_a_revision_and_new_hash_for_each_touched_copy(self):
        self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.console["owned_variant_id"],
            range_start=self.range_start,
            range_end=self.range_end,
        )
        loaded = self.load()
        originals = {
            time_series_set["id"]: self.store.get_time_series_set(
                self.project["id"], time_series_set["id"]
            )
            for time_series_set in (self.demand_set, self.price_set)
        }
        lease = self.store.acquire_operator_console_group_lease(
            self.console["id"], group_id="potencia", user_id=self.operator["id"]
        )

        saved = self.store.save_operator_console_group_values(
            self.console["id"],
            group_id="potencia",
            range_start=self.range_start,
            range_end=self.range_end,
            granularity="full_horizon",
            expected_token=loaded["token"],
            lease_token=lease["token"],
            cells=[
                {"column_id": "demanda", "row_index": 1, "value": 101.5},
                {"column_id": "precio", "row_index": 2, "value": 88.25},
            ],
            note="Ajuste conjunto",
            actor_user_id=self.operator["id"],
        )

        self.assertEqual(saved["rows"][1]["values"]["demanda"], 101.5)
        self.assertEqual(saved["rows"][2]["values"]["precio"], 88.25)
        copies = self.store.list_operator_console_series_copies(self.console["id"])
        self.assertEqual(
            {copy["origin_set_id"] for copy in copies},
            {self.demand_set["id"], self.price_set["id"]},
        )
        for copy in copies:
            copied_set = self.store.get_time_series_set(
                self.project["id"], copy["time_series_set_id"]
            )
            self.assertEqual(copied_set["revision_number"], 2)
            self.assertNotEqual(
                copied_set["content_hash"], originals[copy["origin_set_id"]]["content_hash"]
            )
        for set_id, before in originals.items():
            self.assertEqual(
                self.store.get_time_series_set(self.project["id"], set_id), before
            )
        dependencies = {
            (dependency["dependency_type"], dependency["dependency_id"]): dependency[
                "hash"
            ]
            for dependency in self.store.get_case_input_variant_validation_dependencies(
                self.console["owned_variant_id"]
            )
        }
        for copy in copies:
            copied_set = self.store.get_time_series_set(
                self.project["id"], copy["time_series_set_id"]
            )
            self.assertEqual(
                dependencies[("time_series_set", str(copy["time_series_set_id"]))],
                copied_set["content_hash"],
            )

    def test_one_invalid_cell_leaves_both_existing_copies_and_dependencies_unchanged(self):
        self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.console["owned_variant_id"],
            range_start=self.range_start,
            range_end=self.range_end,
        )
        loaded = self.load()
        lease = self.store.acquire_operator_console_group_lease(
            self.console["id"], group_id="potencia", user_id=self.operator["id"]
        )
        self.store.save_operator_console_group_values(
            self.console["id"],
            group_id="potencia",
            range_start=self.range_start,
            range_end=self.range_end,
            granularity="full_horizon",
            expected_token=loaded["token"],
            lease_token=lease["token"],
            cells=[
                {"column_id": "demanda", "row_index": 0, "value": 20.0},
                {"column_id": "precio", "row_index": 0, "value": 60.0},
            ],
            actor_user_id=self.operator["id"],
        )
        copies = self.store.list_operator_console_series_copies(self.console["id"])
        before_sets = {
            copy["time_series_set_id"]: self.store.get_time_series_set(
                self.project["id"], copy["time_series_set_id"]
            )
            for copy in copies
        }
        before_dependencies = self.store.get_case_input_variant_validation_dependencies(
            self.console["owned_variant_id"]
        )

        with self.assertRaises(ConsoleSeriesError) as raised:
            self.store.save_operator_console_group_values(
                self.console["id"],
                group_id="potencia",
                range_start=self.range_start,
                range_end=self.range_end,
                granularity="full_horizon",
                expected_token=self.load()["token"],
                lease_token=lease["token"],
                cells=[
                    {"column_id": "demanda", "row_index": 1, "value": 21.0},
                    {"column_id": "precio", "row_index": 1, "value": float("nan")},
                ],
                actor_user_id=self.operator["id"],
            )

        self.assertEqual(raised.exception.cells[0]["column_id"], "precio")
        self.assertEqual(
            self.store.list_operator_console_series_copies(self.console["id"]), copies
        )
        self.assertEqual(
            {
                copy["time_series_set_id"]: self.store.get_time_series_set(
                    self.project["id"], copy["time_series_set_id"]
                )
                for copy in copies
            },
            before_sets,
        )
        self.assertEqual(
            self.store.get_case_input_variant_validation_dependencies(
                self.console["owned_variant_id"]
            ),
            before_dependencies,
        )

    def test_a_conflict_in_one_copy_leaves_the_other_copy_and_all_revisions_unchanged(self):
        loaded = self.load()
        lease = self.store.acquire_operator_console_group_lease(
            self.console["id"], group_id="potencia", user_id=self.operator["id"]
        )
        self.store.save_operator_console_group_values(
            self.console["id"],
            group_id="potencia",
            range_start=self.range_start,
            range_end=self.range_end,
            granularity="full_horizon",
            expected_token=loaded["token"],
            lease_token=lease["token"],
            cells=[
                {"column_id": "demanda", "row_index": 0, "value": 20.0},
                {"column_id": "precio", "row_index": 0, "value": 60.0},
            ],
            actor_user_id=self.operator["id"],
        )
        stale_token = self.load()["token"]
        copies = self.store.list_operator_console_series_copies(self.console["id"])
        price_copy = next(
            copy
            for copy in copies
            if copy["origin_set_id"] == self.price_set["id"]
        )
        self.store.edit_time_series_set_values(
            project_id=self.project["id"],
            time_series_set_id=price_copy["time_series_set_id"],
            edits=[
                CatalogValueEdit(
                    period_index=2,
                    signal_key="price_usd_per_mwh",
                    value_text="77.0",
                )
            ],
            created_by="engineer@example.local",
        )
        before_sets = {
            copy["time_series_set_id"]: self.store.get_time_series_set(
                self.project["id"], copy["time_series_set_id"]
            )
            for copy in copies
        }
        before_dependencies = self.store.get_case_input_variant_validation_dependencies(
            self.console["owned_variant_id"]
        )

        with self.assertRaises(ConsoleSeriesError) as raised:
            self.store.save_operator_console_group_values(
                self.console["id"],
                group_id="potencia",
                range_start=self.range_start,
                range_end=self.range_end,
                granularity="full_horizon",
                expected_token=stale_token,
                lease_token=lease["token"],
                cells=[
                    {"column_id": "demanda", "row_index": 1, "value": 21.0},
                    {"column_id": "precio", "row_index": 1, "value": 61.0},
                ],
                actor_user_id=self.operator["id"],
            )

        self.assertEqual(raised.exception.status_code, 412)
        self.assertEqual(raised.exception.total_cells, 2)
        self.assertEqual(
            {
                copy["time_series_set_id"]: self.store.get_time_series_set(
                    self.project["id"], copy["time_series_set_id"]
                )
                for copy in copies
            },
            before_sets,
        )
        self.assertEqual(
            self.store.get_case_input_variant_validation_dependencies(
                self.console["owned_variant_id"]
            ),
            before_dependencies,
        )


class ConsoleSeriesEditingRunTests(unittest.TestCase):
    """An edited copy is what the next run consumes; canonical data is not."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="Planta Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=CONSOLE_DRAFT_DOCUMENT
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.source_variant = self.store.get_or_create_default_input_variant(
            self.case["id"]
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
        group = CONSOLE_DOCUMENT["groups"][0]
        column = group["columns"][0]
        self.console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.source_variant["id"],
            document={
                **CONSOLE_DOCUMENT,
                "groups": [
                    {
                        **group,
                        "columns": [
                            {
                                **column,
                                "source_options": [
                                    {
                                        "id": "base",
                                        "label": "Demanda base",
                                        "time_series_set_id": self.demand_set["id"],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
            created_by_user_id=None,
        )
        self.range_start = self.demand_set["horizon"]["start"]
        self.range_end = self.demand_set["horizon"]["end"]

    def tearDown(self):
        self.store.close()

    def edit_demand(self, value=99.5, row_index=1):
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
            cells=[
                {"column_id": "demanda", "row_index": row_index, "value": value}
            ],
            note="Ajuste manual",
            actor_user_id=self.operator["id"],
        )

    def test_a_run_after_an_edit_uses_the_edited_copy(self):
        canonical_before = self.store.get_time_series_set(
            self.project["id"], self.demand_set["id"]
        )

        self.edit_demand()
        materialized = self.store.materialize_operator_console_run(
            self.console["id"],
            range_start=self.range_start,
            range_end=self.range_end,
        )

        demand = [
            row["load_demand_mw"]["load_1"]
            for row in materialized["system_case"]["time_series"]
        ]
        self.assertEqual(demand, [10.0, 99.5, 12.0, 13.0])
        self.assertEqual(
            self.store.get_time_series_set(self.project["id"], self.demand_set["id"]),
            canonical_before,
        )

    def test_a_run_after_source_selection_uses_the_new_copy_and_stays_validated(self):
        forecast_set = import_demand_set(
            self.store,
            self.scenario["id"],
            name="Pronostico actualizado",
            first_value=20,
        )
        document = self.console["document"]
        group = document["groups"][0]
        column = group["columns"][0]
        self.console = self.store.save_operator_console(
            self.console["id"],
            document={
                **document,
                "groups": [
                    {
                        **group,
                        "columns": [
                            {
                                **column,
                                "source_options": [
                                    *column["source_options"],
                                    {
                                        "id": "pronostico",
                                        "label": "Pronostico actualizado",
                                        "time_series_set_id": forecast_set["id"],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
            status="active",
            expected_revision=self.console["revision"],
            updated_by_user_id=None,
        )
        self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.console["owned_variant_id"],
            range_start=self.range_start,
            range_end=self.range_end,
        )

        self.store.replace_operator_console_series_selections(
            self.console["id"],
            selections=[
                {
                    "group_id": "potencia",
                    "column_id": "demanda",
                    "source_option_id": "pronostico",
                }
            ],
            actor_user_id=self.operator["id"],
        )

        staleness = self.store.evaluate_case_input_variant_staleness(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.console["owned_variant_id"],
        )
        self.assertEqual(
            {"validated": staleness["validated"], "stale": staleness["stale"]},
            {"validated": True, "stale": False},
        )
        materialized = self.store.materialize_operator_console_run(
            self.console["id"],
            range_start=self.range_start,
            range_end=self.range_end,
        )
        self.assertEqual(
            [
                row["load_demand_mw"]["load_1"]
                for row in materialized["system_case"]["time_series"]
            ],
            [20.0, 21.0, 22.0, 23.0],
        )

    def test_the_save_keeps_the_validated_console_variant_fresh(self):
        self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.console["owned_variant_id"],
            range_start=self.range_start,
            range_end=self.range_end,
        )

        self.edit_demand()

        staleness = self.store.evaluate_case_input_variant_staleness(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.console["owned_variant_id"],
        )
        self.assertEqual(
            {"validated": staleness["validated"], "stale": staleness["stale"]},
            {"validated": True, "stale": False},
        )

    def test_the_save_refreshes_only_the_copied_set_dependency(self):
        self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.console["owned_variant_id"],
            range_start=self.range_start,
            range_end=self.range_end,
        )
        before = {
            (dependency["dependency_type"], dependency["dependency_id"]): dependency[
                "hash"
            ]
            for dependency in self.store.get_case_input_variant_validation_dependencies(
                self.console["owned_variant_id"]
            )
        }

        self.edit_demand()

        after = {
            (dependency["dependency_type"], dependency["dependency_id"]): dependency[
                "hash"
            ]
            for dependency in self.store.get_case_input_variant_validation_dependencies(
                self.console["owned_variant_id"]
            )
        }
        copy = self.store.list_operator_console_series_copies(self.console["id"])[0]
        unchanged_keys = {
            key for key in before if key[0] != "time_series_set"
        } | {("time_series_set", str(self.price_set["id"]))}
        self.assertEqual(
            {key: after[key] for key in unchanged_keys},
            {key: before[key] for key in unchanged_keys},
        )
        self.assertNotIn(("time_series_set", str(self.demand_set["id"])), after)
        self.assertEqual(
            after[("time_series_set", str(copy["time_series_set_id"]))],
            self.store.get_time_series_set(
                self.project["id"], copy["time_series_set_id"]
            )["content_hash"],
        )

    def test_editing_one_console_leaves_every_other_variant_untouched(self):
        other_console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.source_variant["id"],
            document=self.store.get_operator_console(self.console["id"])["document"],
            created_by_user_id=None,
        )

        self.edit_demand()

        for variant_id in (
            self.source_variant["id"],
            other_console["owned_variant_id"],
        ):
            with self.subTest(variant_id=variant_id):
                self.assertEqual(
                    [
                        binding["time_series_set_id"]
                        for binding in self.store.list_case_time_series_bindings(
                            variant_id
                        )
                    ],
                    [self.demand_set["id"], self.price_set["id"]],
                )



class ConsoleSeriesEditingApiTests(unittest.TestCase):
    """What the operator surface exposes and refuses over HTTP."""

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
        self.other_operator = self.store.create_user(
            email="other@example.local",
            display_name="Otro Operador",
            role="external",
            password_hash=hash_password("other pass"),
        )
        self.project = self.store.create_project(name="Planta Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Operacion diaria"
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        for user in (self.operator, self.other_operator):
            self.store.set_external_project_access(
                project_id=self.project["id"],
                user_id=user["id"],
                portal_view=False,
                operate=True,
                updated_by="admin@example.local",
            )
        self.demand_set = import_demand_set(self.store, self.scenario["id"])
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="load_demand_mw",
            time_series_set_id=self.demand_set["id"],
        )
        group = CONSOLE_DOCUMENT["groups"][0]
        column = group["columns"][0]
        document = {
            **CONSOLE_DOCUMENT,
            "groups": [
                {
                    **group,
                    "columns": [
                        {
                            **column,
                            "source_options": [
                                {
                                    "id": "base",
                                    "label": "Demanda base",
                                    "time_series_set_id": self.demand_set["id"],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        console = self.store.create_operator_console(
            case_id=self.case["id"],
            source_variant_id=self.variant["id"],
            document=document,
            created_by_user_id=self.analyst["id"],
        )
        self.console = self.store.save_operator_console(
            console["id"],
            document=document,
            status="active",
            expected_revision=1,
            updated_by_user_id=self.analyst["id"],
        )
        self.values_path = (
            f"/api/console/{self.console['id']}/groups/potencia/values"
        )
        self.lease_path = f"/api/console/{self.console['id']}/groups/potencia/lease"
        self.range = {
            "start": self.demand_set["horizon"]["start"],
            "end": self.demand_set["horizon"]["end"],
            "granularity": "full_horizon",
        }
        self.login("operator@example.local", "operator pass")

    def tearDown(self):
        self.store.close()

    def login(self, email, password):
        self.assertEqual(
            login_json_with_csrf(self.client, email, password).status_code, 200
        )

    def load_values(self):
        response = self.client.get(self.values_path, params=self.range)
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def take_lease(self):
        response = post_json_with_csrf(self.client, self.lease_path)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["lease"]["token"]

    def put_values(self, cells, *, etag, lease_token, **overrides):
        payload = {
            "range_start": self.range["start"],
            "range_end": self.range["end"],
            "granularity": self.range["granularity"],
            "lease_token": lease_token,
            "note": "Ajuste manual",
            "cells": cells,
        }
        payload.update(overrides)
        headers = csrf_headers(self.client)
        headers["If-Match"] = etag
        return self.client.put(self.values_path, json=payload, headers=headers)

    def add_forecast_option(self):
        forecast_set = import_demand_set(
            self.store,
            self.scenario["id"],
            name="Pronostico actualizado",
            first_value=20,
        )
        document = self.console["document"]
        group = document["groups"][0]
        column = group["columns"][0]
        self.console = self.store.save_operator_console(
            self.console["id"],
            document={
                **document,
                "groups": [
                    {
                        **group,
                        "columns": [
                            {
                                **column,
                                "source_options": [
                                    *column["source_options"],
                                    {
                                        "id": "pronostico",
                                        "label": "Pronostico actualizado",
                                        "time_series_set_id": forecast_set["id"],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
            status="active",
            expected_revision=self.console["revision"],
            updated_by_user_id=self.analyst["id"],
        )
        return forecast_set

    def test_series_options_expose_only_the_configured_public_choices(self):
        self.add_forecast_option()

        response = self.client.get(
            f"/api/console/{self.console['id']}/series-options"
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {
                "selections": [
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "selected_source_option_id": "base",
                        "options": [
                            {"id": "base", "label": "Demanda base"},
                            {
                                "id": "pronostico",
                                "label": "Pronostico actualizado",
                            },
                        ],
                    }
                ]
            },
        )
        for forbidden in (
            "time_series_set_id",
            "copy_id",
            "signal_key",
            "binding_id",
            "origin_set_id",
        ):
            self.assertNotIn(forbidden, response.text)

    def test_selecting_a_public_source_updates_the_next_values_load(self):
        self.add_forecast_option()

        response = put_json_with_csrf(
            self.client,
            f"/api/console/{self.console['id']}/series-selections",
            {
                "selections": [
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "source_option_id": "pronostico",
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["selections"][0]["selected_source_option_id"],
            "pronostico",
        )
        self.assertEqual(
            [
                row["values"]["demanda"]
                for row in self.load_values().json()["group_values"]["rows"]
            ],
            [20.0, 21.0, 22.0, 23.0],
        )
        for forbidden in (
            "time_series_set_id",
            "copy_id",
            "signal_key",
            "binding_id",
            "origin_set_id",
        ):
            self.assertNotIn(forbidden, response.text)

    def test_duplicate_column_selections_are_rejected_without_writing(self):
        self.add_forecast_option()

        response = put_json_with_csrf(
            self.client,
            f"/api/console/{self.console['id']}/series-selections",
            {
                "selections": [
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "source_option_id": "pronostico",
                    },
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "source_option_id": "base",
                    },
                ]
            },
        )

        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(
            self.store.list_operator_console_series_copies(self.console["id"]), []
        )
        self.assertEqual(
            self.client.get(
                f"/api/console/{self.console['id']}/series-options"
            ).json()["selections"][0]["selected_source_option_id"],
            "base",
        )

    def test_guessed_options_and_technical_selection_fields_are_refused(self):
        self.add_forecast_option()
        path = f"/api/console/{self.console['id']}/series-selections"

        guessed = put_json_with_csrf(
            self.client,
            path,
            {
                "selections": [
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "source_option_id": "inventada",
                    }
                ]
            },
        )
        technical = put_json_with_csrf(
            self.client,
            path,
            {
                "selections": [
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "source_option_id": "pronostico",
                        "time_series_set_id": self.demand_set["id"],
                    }
                ]
            },
        )

        self.assertEqual(guessed.status_code, 400, guessed.text)
        self.assertEqual(technical.status_code, 422, technical.text)
        self.assertEqual(
            self.store.list_operator_console_series_copies(self.console["id"]), []
        )
        self.assertEqual(
            self.client.get(
                f"/api/console/{self.console['id']}/series-options"
            ).json()["selections"][0]["selected_source_option_id"],
            "base",
        )

    def test_the_console_payload_announces_the_configured_groups(self):
        response = self.client.get(f"/api/console/{self.console['id']}")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["groups"],
            [
                {
                    "id": "potencia",
                    "label": "Potencia",
                    "granularities": ["day", "full_horizon"],
                    "columns": [
                        {
                            "id": "demanda",
                            "label": "Demanda",
                            "unit": "MW",
                            "nonnegative": True,
                            "editable": True,
                        }
                    ],
                }
            ],
        )

    def test_loading_values_returns_the_grid_and_an_opaque_etag(self):
        response = self.load_values()

        payload = response.json()["group_values"]
        self.assertEqual(payload["group_id"], "potencia")
        self.assertEqual(payload["granularity"], "full_horizon")
        self.assertEqual(
            payload["range"],
            {"start": self.range["start"], "end": self.range["end"]},
        )
        self.assertEqual(
            [row["values"]["demanda"] for row in payload["rows"]],
            [10.0, 11.0, 12.0, 13.0],
        )
        etag = response.headers["etag"].strip('"')
        self.assertRegex(etag, r"^[0-9a-f]{32}$")
        self.assertNotIn(self.demand_set["content_hash"], etag)

    def test_an_operator_saves_one_cell_and_reads_the_edited_grid_back(self):
        loaded = self.load_values()
        lease_token = self.take_lease()

        response = self.put_values(
            [{"column_id": "demanda", "row_index": 1, "value": 99.5}],
            etag=loaded.headers["etag"],
            lease_token=lease_token,
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()["group_values"]
        self.assertEqual(
            [row["values"]["demanda"] for row in payload["rows"]],
            [10.0, 99.5, 12.0, 13.0],
        )
        self.assertNotEqual(response.headers["etag"], loaded.headers["etag"])
        self.assertEqual(
            [row["values"]["demanda"] for row in self.load_values().json()["group_values"]["rows"]],
            [10.0, 99.5, 12.0, 13.0],
        )

    def test_saving_without_a_matching_if_match_is_refused(self):
        loaded = self.load_values()
        lease_token = self.take_lease()
        first = self.put_values(
            [{"column_id": "demanda", "row_index": 1, "value": 99.5}],
            etag=loaded.headers["etag"],
            lease_token=lease_token,
        )
        self.assertEqual(first.status_code, 200, first.text)

        stale = self.put_values(
            [{"column_id": "demanda", "row_index": 1, "value": 12.5}],
            etag=loaded.headers["etag"],
            lease_token=lease_token,
        )
        missing = self.client.put(
            self.values_path,
            json={
                "range_start": self.range["start"],
                "range_end": self.range["end"],
                "granularity": self.range["granularity"],
                "lease_token": lease_token,
                "cells": [{"column_id": "demanda", "row_index": 1, "value": 12.5}],
            },
            headers=csrf_headers(self.client),
        )

        self.assertEqual(stale.status_code, 412, stale.text)
        self.assertEqual(missing.status_code, 428, missing.text)
        self.assertEqual(
            [row["values"]["demanda"] for row in self.load_values().json()["group_values"]["rows"]],
            [10.0, 99.5, 12.0, 13.0],
        )

    def test_a_stale_block_reports_every_submitted_cell_in_external_coordinates(self):
        loaded = self.load_values()
        lease_token = self.take_lease()
        first = self.put_values(
            [{"column_id": "demanda", "row_index": 0, "value": 20.0}],
            etag=loaded.headers["etag"],
            lease_token=lease_token,
        )
        self.assertEqual(first.status_code, 200, first.text)

        stale = self.put_values(
            [
                {"column_id": "demanda", "row_index": 1, "value": 21.0},
                {"column_id": "demanda", "row_index": 2, "value": 22.0},
            ],
            etag=loaded.headers["etag"],
            lease_token=lease_token,
        )

        self.assertEqual(stale.status_code, 412, stale.text)
        self.assertEqual(
            stale.json()["save_error"],
            {
                "message": "los datos cambiaron mientras editabas; vuelve a cargar el tramo",
                "cells": [
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "row_index": 1,
                        "message": "los datos cambiaron mientras editabas",
                    },
                    {
                        "group_id": "potencia",
                        "column_id": "demanda",
                        "row_index": 2,
                        "message": "los datos cambiaron mientras editabas",
                    },
                ],
                "total_cells": 2,
                "shown_cells": 2,
            },
        )

    def test_a_rejected_block_names_its_cells_in_external_coordinates(self):
        loaded = self.load_values()
        lease_token = self.take_lease()

        response = self.put_values(
            [
                {"column_id": "demanda", "row_index": 0, "value": 21.0},
                {"column_id": "demanda", "row_index": 1, "value": -3.0},
            ],
            etag=loaded.headers["etag"],
            lease_token=lease_token,
        )

        self.assertEqual(response.status_code, 400, response.text)
        save_error = response.json()["save_error"]
        self.assertEqual(save_error["total_cells"], 1)
        self.assertEqual(save_error["shown_cells"], 1)
        self.assertEqual(
            save_error["cells"][0]["group_id"], "potencia"
        )
        self.assertEqual(save_error["cells"][0]["column_id"], "demanda")
        self.assertEqual(save_error["cells"][0]["row_index"], 1)
        self.assertEqual(
            [row["values"]["demanda"] for row in self.load_values().json()["group_values"]["rows"]],
            [10.0, 11.0, 12.0, 13.0],
        )

    def test_an_uncovered_save_range_reports_the_submitted_cell_and_writes_nothing(self):
        loaded = self.load_values()
        lease_token = self.take_lease()

        response = self.put_values(
            [{"column_id": "demanda", "row_index": 0, "value": 21.0}],
            etag=loaded.headers["etag"],
            lease_token=lease_token,
            range_end="2026-01-02T00:00:00-03:00",
        )

        self.assertEqual(response.status_code, 400, response.text)
        save_error = response.json()["save_error"]
        self.assertEqual(save_error["total_cells"], 1)
        self.assertEqual(
            save_error["cells"],
            [
                {
                    "group_id": "potencia",
                    "column_id": "demanda",
                    "row_index": 0,
                    "message": "el tramo elegido no tiene cobertura completa",
                }
            ],
        )
        self.assertEqual(
            self.store.list_operator_console_series_copies(self.console["id"]), []
        )

    def test_a_second_operator_is_locked_out_and_sees_who_is_editing(self):
        self.take_lease()
        self.login("other@example.local", "other pass")

        lease_response = post_json_with_csrf(self.client, self.lease_path)
        shell = self.client.get(f"/api/console/{self.console['id']}")

        self.assertEqual(lease_response.status_code, 409, lease_response.text)
        self.assertEqual(
            shell.json()["run_gate"],
            {
                "can_run": False,
                "reason": "edicion_de_otro_usuario",
                "message": "Olga Operadora esta editando este grupo.",
                "contact": None,
                "editing_locked_by": "Olga Operadora",
                "review_requested_at": None,
            },
        )

    def test_releasing_the_lease_reopens_the_group_and_the_run_gate(self):
        lease_token = self.take_lease()

        released = delete_with_csrf(
            self.client, f"{self.lease_path}?lease_token={lease_token}"
        )
        self.login("other@example.local", "other pass")
        retaken = post_json_with_csrf(self.client, self.lease_path)

        self.assertEqual(released.status_code, 204, released.text)
        self.assertEqual(retaken.status_code, 200, retaken.text)
        self.assertEqual(
            self.client.get(f"/api/console/{self.console['id']}").json()["run_gate"][
                "editing_locked_by"
            ],
            None,
        )

    def test_the_holder_extends_the_lease_with_a_heartbeat(self):
        lease_token = self.take_lease()

        response = put_json_with_csrf(
            self.client, self.lease_path, {"lease_token": lease_token}
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["lease"]["holder_name"], "Olga Operadora")

    def test_the_group_values_payload_carries_no_internal_metadata(self):
        loaded = self.load_values()
        lease_token = self.take_lease()
        saved = self.put_values(
            [{"column_id": "demanda", "row_index": 1, "value": 99.5}],
            etag=loaded.headers["etag"],
            lease_token=lease_token,
        )
        shell = self.client.get(f"/api/console/{self.console['id']}")

        forbidden = (
            "signal_key",
            "time_series_set_id",
            "set_id",
            "revision",
            "content_hash",
            "period_index",
            "entity_id",
            "entity_type",
            "variant_id",
            "origin_set_id",
            "case_id",
            "scenario_id",
        )
        for name, response in {
            "values": loaded,
            "saved": saved,
            "shell": shell,
        }.items():
            for key in forbidden:
                with self.subTest(response=name, key=key):
                    self.assertNotIn(key, response.text)

    def test_a_column_whose_series_is_unbound_closes_the_console_actionably(self):
        document = self.store.get_operator_console(self.console["id"])["document"]
        group = document["groups"][0]
        column = group["columns"][0]
        self.store.save_operator_console(
            self.console["id"],
            document={
                **document,
                "groups": [
                    {
                        **group,
                        "columns": [
                            {
                                **column,
                                "signal": {
                                    **column["signal"],
                                    "signal_key": "renewable_available_power_mw",
                                },
                            }
                        ],
                    }
                ],
            },
            status="active",
            expected_revision=self.console["revision"],
            updated_by_user_id=self.analyst["id"],
        )

        shell = self.client.get(f"/api/console/{self.console['id']}")
        values = self.client.get(self.values_path, params=self.range)

        self.assertEqual(shell.status_code, 200, shell.text)
        self.assertEqual(shell.json()["groups"], [])
        self.assertEqual(
            {
                "can_run": shell.json()["run_gate"]["can_run"],
                "reason": shell.json()["run_gate"]["reason"],
                "contact": shell.json()["run_gate"]["contact"],
            },
            {"can_run": False, "reason": "campo_no_disponible", "contact": "Ana Analista"},
        )
        self.assertEqual(values.status_code, 409, values.text)

    def test_a_foreign_console_group_is_not_found(self):
        response = self.client.get(
            f"/api/console/{self.console['id']}/groups/inexistente/values",
            params=self.range,
        )

        self.assertEqual(response.status_code, 404, response.text)


if __name__ == "__main__":
    unittest.main()
