import unittest
from datetime import datetime, timedelta

from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    CatalogValueEdit,
    prepare_time_series_catalog_import,
)


def price_import_request(*, signal_key="import_price_usd_per_mwh", version_label="v1"):
    return CatalogImportRequest(
        set_name="Spot price",
        version_label=version_label,
        data_kind="real",
        timezone="America/Santiago",
        timestamp_column="period_start",
        duration_hours_column="hours",
        signal_mappings=[
            CatalogSignalMappingRequest(source_column="spot_price", signal_key=signal_key),
        ],
    )


def price_rows(start, count, *, value=50.0):
    rows = []
    for hour in range(count):
        instant = start + timedelta(hours=hour)
        rows.append(
            {
                "period_start": instant.isoformat(),
                "hours": "1.0",
                "spot_price": str(value + hour),
            }
        )
    return rows


def signal_import_request(*, set_name, signal_key, version_label="v1", value_column="value"):
    return CatalogImportRequest(
        set_name=set_name,
        version_label=version_label,
        data_kind="real",
        timezone="America/Santiago",
        timestamp_column="period_start",
        duration_hours_column="hours",
        signal_mappings=[
            CatalogSignalMappingRequest(source_column=value_column, signal_key=signal_key),
        ],
    )


def timed_rows(start, durations, *, value=50.0, value_column="spot_price"):
    rows = []
    cursor = start
    for index, duration in enumerate(durations):
        rows.append(
            {
                "period_start": cursor.isoformat(),
                "hours": str(duration),
                value_column: str(value + index),
            }
        )
        cursor += timedelta(hours=duration)
    return rows


class DefaultInputVariantTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS-3 project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-3 scenario"
        )

    def test_case_gets_a_default_variant_created_lazily(self):
        case = self.store.get_or_create_case_for_scenario(self.scenario["id"])

        variant = self.store.get_or_create_default_input_variant(case["id"])

        self.assertTrue(variant["is_default"])
        self.assertEqual(variant["case_id"], case["id"])
        self.assertEqual(variant["display_name"], "Default")

    def test_default_variant_is_created_only_once(self):
        case = self.store.get_or_create_case_for_scenario(self.scenario["id"])

        first = self.store.get_or_create_default_input_variant(case["id"])
        second = self.store.get_or_create_default_input_variant(case["id"])

        self.assertEqual(first["id"], second["id"])


class CaseTimeSeriesBindingTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS-3 project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-3 scenario"
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        prepared = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 1, 1), 3),
            request=price_import_request(),
        )
        self.price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_1",
                "original_filename": "price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test",
            },
            prepared_import=prepared,
        )

    def test_bind_price_signal_to_variant(self):
        binding = self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.price_set["id"],
        )

        self.assertEqual(binding["signal_key"], "import_price_usd_per_mwh")
        self.assertEqual(binding["time_series_set_id"], self.price_set["id"])
        bindings = self.store.list_case_time_series_bindings(self.variant["id"])
        self.assertEqual(len(bindings), 1)

    def test_rebinding_same_signal_replaces_previous_set(self):
        other_prepared = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 1, 1), 3, value=90.0),
            request=price_import_request(version_label="v2"),
        )
        other_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_2",
                "original_filename": "price_v2.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test2",
            },
            prepared_import=other_prepared,
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.price_set["id"],
        )

        rebound = self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=other_set["id"],
        )

        self.assertEqual(rebound["time_series_set_id"], other_set["id"])
        bindings = self.store.list_case_time_series_bindings(self.variant["id"])
        self.assertEqual(len(bindings), 1)

    def test_same_signal_key_can_bind_multiple_entities(self):
        first_load_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_load_1",
                "original_filename": "load_1.csv",
                "media_type": "text/csv",
                "checksum": "sha256:load1",
            },
            prepared_import=prepare_time_series_catalog_import(
                rows=price_rows(datetime(2026, 1, 1), 3, value=10.0),
                request=signal_import_request(
                    set_name="Load alpha",
                    signal_key="load_demand_mw",
                    value_column="spot_price",
                ),
            ),
        )
        second_load_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_load_2",
                "original_filename": "load_2.csv",
                "media_type": "text/csv",
                "checksum": "sha256:load2",
            },
            prepared_import=prepare_time_series_catalog_import(
                rows=price_rows(datetime(2026, 1, 1), 3, value=20.0),
                request=signal_import_request(
                    set_name="Load beta",
                    signal_key="load_demand_mw",
                    value_column="spot_price",
                ),
            ),
        )

        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_1",
            time_series_set_id=first_load_set["id"],
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_2",
            time_series_set_id=second_load_set["id"],
        )

        bindings = self.store.list_case_time_series_bindings(self.variant["id"])
        self.assertEqual(
            [
                (binding["signal_key"], binding["entity_type"], binding["entity_id"], binding["time_series_set_id"])
                for binding in bindings
            ],
            [
                ("load_demand_mw", "component:load", "load_1", first_load_set["id"]),
                ("load_demand_mw", "component:load", "load_2", second_load_set["id"]),
            ],
        )


class CaseInputVariantLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS-3 project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-3 scenario"
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.default_variant = self.store.get_or_create_default_input_variant(self.case["id"])
        prepared = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 1, 1), 3),
            request=price_import_request(),
        )
        self.default_price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_1",
                "original_filename": "price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test",
            },
            prepared_import=prepared,
        )
        other_prepared = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 1, 1), 3, value=90.0),
            request=price_import_request(version_label="v2"),
        )
        self.alternate_price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_2",
                "original_filename": "price_v2.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test2",
            },
            prepared_import=other_prepared,
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.default_variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.default_price_set["id"],
        )

    def test_clone_copies_bindings_but_rebinding_clone_keeps_default_intact(self):
        clone = self.store.clone_case_input_variant(
            case_id=self.case["id"],
            source_variant_id=self.default_variant["id"],
            display_name="Stress prices",
        )

        self.assertFalse(clone["is_default"])
        self.assertEqual(clone["display_name"], "Stress prices")
        self.assertNotEqual(clone["id"], self.default_variant["id"])

        clone_bindings = self.store.list_case_time_series_bindings(clone["id"])
        self.assertEqual(
            [binding["time_series_set_id"] for binding in clone_bindings],
            [self.default_price_set["id"]],
        )

        self.store.upsert_case_time_series_binding(
            case_input_variant_id=clone["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.alternate_price_set["id"],
        )

        default_bindings = self.store.list_case_time_series_bindings(self.default_variant["id"])
        clone_bindings = self.store.list_case_time_series_bindings(clone["id"])
        self.assertEqual(
            [binding["time_series_set_id"] for binding in default_bindings],
            [self.default_price_set["id"]],
        )
        self.assertEqual(
            [binding["time_series_set_id"] for binding in clone_bindings],
            [self.alternate_price_set["id"]],
        )

    def test_create_variants_generate_distinct_keys_for_same_display_name(self):
        first = self.store.create_case_input_variant(
            case_id=self.case["id"],
            display_name="Stress prices",
        )
        second = self.store.create_case_input_variant(
            case_id=self.case["id"],
            display_name="Stress prices",
        )

        self.assertEqual(first["variant_key"], "stress_prices")
        self.assertEqual(second["variant_key"], "stress_prices_2")


def grid_battery_draft_document():
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
            },
        ],
        "time_series": {"sources": []},
        "solver": {"name": "HiGHS", "options": {}},
    }


class MaterializeSystemCaseForVariantTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS-3 project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-3 scenario"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=grid_battery_draft_document()
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        prepared = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 1, 1), 3),
            request=price_import_request(),
        )
        self.price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_1",
                "original_filename": "price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test",
            },
            prepared_import=prepared,
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.price_set["id"],
        )

    def test_materializes_system_case_with_bound_price_series(self):
        result = self.store.materialize_system_case_for_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            range_start=self.price_set["horizon"]["start"],
            range_end=self.price_set["horizon"]["end"],
        )

        system_case = result["system_case"]
        self.assertEqual(system_case["case_name"], "grid_battery_case")
        self.assertEqual(len(system_case["time_series"]), 3)
        self.assertEqual(system_case["time_series"][0]["import_price_usd_per_mwh"], 50.0)
        self.assertEqual(
            [row["signal_key"] for row in result["series_bindings"]],
            ["import_price_usd_per_mwh"],
        )
        self.assertEqual(result["series_bindings"][0]["time_series_set_id"], self.price_set["id"])

    def test_success_records_validated_revision_and_content_hash_for_binding(self):
        result = self.store.materialize_system_case_for_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            range_start=self.price_set["horizon"]["start"],
            range_end=self.price_set["horizon"]["end"],
        )

        self.assertEqual(
            result["series_bindings"],
            [
                {
                    "signal_key": "import_price_usd_per_mwh",
                    "entity_type": None,
                    "entity_id": None,
                    "time_series_set_id": self.price_set["id"],
                    "version_number": self.price_set["version_number"],
                    "version_label": self.price_set["version_label"],
                    "revision_number": self.price_set["revision_number"],
                    "content_hash": self.price_set["content_hash"],
                    "validated_range": {
                        "start": self.price_set["horizon"]["start"],
                        "end": self.price_set["horizon"]["end"],
                    },
                }
            ],
        )

    def test_range_not_covered_by_binding_raises(self):
        from app.input_variants import InputVariantRangeError

        with self.assertRaises(InputVariantRangeError):
            self.store.materialize_system_case_for_variant(
                scenario_id=self.scenario["id"],
                case_input_variant_id=self.variant["id"],
                range_start="2026-01-01T00:00:00",
                range_end="2026-01-02T00:00:00",
            )

    def test_materializes_even_when_draft_has_an_unvalidated_legacy_source(self):
        from app.time_series_ingestion import attach_time_series_source

        document_with_source = attach_time_series_source(
            grid_battery_draft_document(),
            {
                "id": "csv_legacy_1",
                "original_filename": "ts3_price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:legacy",
            },
        )
        self.store.update_scenario_draft(
            scenario_id=self.scenario["id"], document=document_with_source
        )

        result = self.store.materialize_system_case_for_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            range_start=self.price_set["horizon"]["start"],
            range_end=self.price_set["horizon"]["end"],
        )

        self.assertEqual(len(result["system_case"]["time_series"]), 3)


def grid_battery_load_draft_document():
    document = grid_battery_draft_document()
    document["assets"].append({"id": "load_1", "type": "load"})
    return document


def grid_battery_two_loads_draft_document():
    document = grid_battery_draft_document()
    document["assets"].append({"id": "load_1", "type": "load"})
    document["assets"].append({"id": "load_2", "type": "load"})
    return document


class MaterializeVariantRequiredSignalsTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS-3 project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-3 scenario"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=grid_battery_load_draft_document()
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        prepared = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 1, 1), 3),
            request=price_import_request(),
        )
        self.price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_1",
                "original_filename": "price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test",
            },
            prepared_import=prepared,
        )

    def test_run_with_missing_load_binding_raises_naming_the_missing_signal(self):
        from app.required_signals import MissingRequiredSignalsError

        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.price_set["id"],
        )

        with self.assertRaises(MissingRequiredSignalsError) as raised:
            self.store.materialize_system_case_for_variant(
                scenario_id=self.scenario["id"],
                case_input_variant_id=self.variant["id"],
                range_start=self.price_set["horizon"]["start"],
                range_end=self.price_set["horizon"]["end"],
            )

        self.assertIn("load_demand_mw", str(raised.exception))

    def test_run_with_every_required_signal_bound_succeeds(self):
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.price_set["id"],
        )
        load_prepared = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 1, 1), 3, value=1.0),
            request=CatalogImportRequest(
                set_name="Load",
                version_label="v1",
                data_kind="real",
                timezone="America/Santiago",
                timestamp_column="period_start",
                duration_hours_column="hours",
                signal_mappings=[
                    CatalogSignalMappingRequest(source_column="spot_price", signal_key="load_demand_mw"),
                ],
            ),
        )
        load_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_2",
                "original_filename": "load.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test2",
            },
            prepared_import=load_prepared,
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_1",
            time_series_set_id=load_set["id"],
        )

        result = self.store.materialize_system_case_for_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            range_start=self.price_set["horizon"]["start"],
            range_end=self.price_set["horizon"]["end"],
        )

        self.assertEqual(len(result["system_case"]["time_series"]), 3)
        self.assertEqual(
            sorted(row["signal_key"] for row in result["series_bindings"]),
            ["import_price_usd_per_mwh", "load_demand_mw"],
        )

    def test_mismatched_periods_between_bound_sets_raise_explicit_error(self):
        from app.input_variants import InputVariantRangeError

        long_price_prepared = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 1, 1), 4),
            request=price_import_request(version_label="v2"),
        )
        long_price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_3",
                "original_filename": "price_4h.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test3",
            },
            prepared_import=long_price_prepared,
        )
        load_prepared = prepare_time_series_catalog_import(
            rows=timed_rows(datetime(2026, 1, 1), [2.0, 2.0], value=1.0),
            request=CatalogImportRequest(
                set_name="Load",
                version_label="v1",
                data_kind="real",
                timezone="America/Santiago",
                timestamp_column="period_start",
                duration_hours_column="hours",
                signal_mappings=[
                    CatalogSignalMappingRequest(source_column="spot_price", signal_key="load_demand_mw"),
                ],
            ),
        )
        load_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_4",
                "original_filename": "load_2h.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test4",
            },
            prepared_import=load_prepared,
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=long_price_set["id"],
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_1",
            time_series_set_id=load_set["id"],
        )

        with self.assertRaisesRegex(InputVariantRangeError, "horizon incompatible.*load_demand_mw"):
            self.store.materialize_system_case_for_variant(
                scenario_id=self.scenario["id"],
                case_input_variant_id=self.variant["id"],
                range_start=long_price_set["horizon"]["start"],
                range_end=long_price_set["horizon"]["end"],
            )


class MaterializeVariantEntityScopedSignalsTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS-3 project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-3 scenario"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=grid_battery_two_loads_draft_document()
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        self.price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_price",
                "original_filename": "price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:price",
            },
            prepared_import=prepare_time_series_catalog_import(
                rows=price_rows(datetime(2026, 1, 1), 3),
                request=signal_import_request(
                    set_name="Price",
                    signal_key="price_usd_per_mwh",
                    value_column="spot_price",
                ),
            ),
        )
        self.load_alpha_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_load_1",
                "original_filename": "load_1.csv",
                "media_type": "text/csv",
                "checksum": "sha256:load1",
            },
            prepared_import=prepare_time_series_catalog_import(
                rows=price_rows(datetime(2026, 1, 1), 3, value=10.0),
                request=signal_import_request(
                    set_name="Load alpha",
                    signal_key="load_demand_mw",
                    value_column="spot_price",
                ),
            ),
        )
        self.load_beta_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_load_2",
                "original_filename": "load_2.csv",
                "media_type": "text/csv",
                "checksum": "sha256:load2",
            },
            prepared_import=prepare_time_series_catalog_import(
                rows=price_rows(datetime(2026, 1, 1), 3, value=20.0),
                request=signal_import_request(
                    set_name="Load beta",
                    signal_key="load_demand_mw",
                    value_column="spot_price",
                ),
            ),
        )

    def test_materializes_entity_scoped_load_bindings_as_asset_map(self):
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="price_usd_per_mwh",
            entity_type="grid",
            entity_id="grid_1",
            time_series_set_id=self.price_set["id"],
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_1",
            time_series_set_id=self.load_alpha_set["id"],
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_2",
            time_series_set_id=self.load_beta_set["id"],
        )

        result = self.store.materialize_system_case_for_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            range_start=self.price_set["horizon"]["start"],
            range_end=self.price_set["horizon"]["end"],
        )

        self.assertEqual(
            result["system_case"]["time_series"][0]["load_demand_mw"],
            {"load_1": 10.0, "load_2": 20.0},
        )


class VariantStalenessTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS-3 project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-3 scenario"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=grid_battery_draft_document()
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        prepared = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 1, 1), 3),
            request=price_import_request(),
        )
        self.price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_1",
                "original_filename": "price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test",
            },
            prepared_import=prepared,
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.price_set["id"],
        )

    def _materialize(self):
        return self.store.materialize_system_case_for_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            range_start=self.price_set["horizon"]["start"],
            range_end=self.price_set["horizon"]["end"],
        )

    def _staleness(self):
        return self.store.evaluate_case_input_variant_staleness(
            scenario_id=self.scenario["id"], case_input_variant_id=self.variant["id"]
        )

    def test_never_validated_variant_is_not_stale(self):
        staleness = self._staleness()

        self.assertFalse(staleness["validated"])
        self.assertFalse(staleness["stale"])
        self.assertEqual(staleness["reasons"], [])

    def test_successful_materialize_records_validation_then_variant_is_not_stale(self):
        self._materialize()

        staleness = self._staleness()

        self.assertTrue(staleness["validated"])
        self.assertFalse(staleness["stale"])

    def test_series_revision_change_after_validation_marks_variant_stale(self):
        from app.variant_staleness import VariantStaleError

        self._materialize()

        self.store.edit_time_series_set_values(
            project_id=self.project["id"],
            time_series_set_id=self.price_set["id"],
            edits=[
                CatalogValueEdit(
                    period_index=0, signal_key="import_price_usd_per_mwh", value_text="999.0"
                )
            ],
        )

        staleness = self._staleness()
        self.assertTrue(staleness["stale"])
        self.assertEqual(
            [reason["dependency_type"] for reason in staleness["reasons"]],
            ["time_series_set"],
        )

        with self.assertRaises(VariantStaleError):
            self._materialize()

    def test_parameter_only_change_after_validation_marks_variant_stale(self):
        self._materialize()

        document = grid_battery_draft_document()
        document["assets"][0]["charge_power_max_mw"] = 999.0
        self.store.update_scenario_draft(scenario_id=self.scenario["id"], document=document)

        staleness = self._staleness()
        self.assertTrue(staleness["stale"])
        self.assertEqual(
            sorted(reason["dependency_type"] for reason in staleness["reasons"]),
            ["parameters"],
        )

    def test_validate_case_input_variant_revalidates_and_clears_stale_marker(self):
        self._materialize()
        self.store.edit_time_series_set_values(
            project_id=self.project["id"],
            time_series_set_id=self.price_set["id"],
            edits=[
                CatalogValueEdit(
                    period_index=0, signal_key="import_price_usd_per_mwh", value_text="999.0"
                )
            ],
        )
        self.assertTrue(self._staleness()["stale"])

        self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            range_start=self.price_set["horizon"]["start"],
            range_end=self.price_set["horizon"]["end"],
        )

        self.assertFalse(self._staleness()["stale"])
        result = self._materialize()
        self.assertNotEqual(result["series_bindings"][0]["content_hash"], self.price_set["content_hash"])
        self.assertFalse(self._staleness()["stale"])
