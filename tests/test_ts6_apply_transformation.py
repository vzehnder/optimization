import unittest
from datetime import datetime, timedelta

from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)
from app.transformations import TransformationError


def demand_price_import_request(*, version_label="v1"):
    return CatalogImportRequest(
        set_name="Demand and price base",
        version_label=version_label,
        data_kind="real",
        timezone="America/Santiago",
        timestamp_column="period_start",
        duration_hours_column="hours",
        signal_mappings=[
            CatalogSignalMappingRequest(source_column="demand", signal_key="load_demand_mw"),
            CatalogSignalMappingRequest(
                source_column="price", signal_key="import_price_usd_per_mwh"
            ),
        ],
    )


def demand_price_rows(start, count):
    rows = []
    for hour in range(count):
        instant = start + timedelta(hours=hour)
        rows.append(
            {
                "period_start": instant.isoformat(),
                "hours": "1.0",
                "demand": str(100.0 + hour),
                "price": str(50.0 + hour),
            }
        )
    return rows


class ApplyTimeSeriesTransformationTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS-6 project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-6 scenario"
        )
        prepared = prepare_time_series_catalog_import(
            rows=demand_price_rows(datetime(2026, 1, 1), 3),
            request=demand_price_import_request(),
        )
        self.source_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_1",
                "original_filename": "demand_price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test",
            },
            prepared_import=prepared,
        )

    def test_scale_signal_creates_a_derived_set_with_only_the_target_signal_scaled(self):
        derived = self.store.apply_time_series_transformation(
            project_id=self.project["id"],
            time_series_set_id=self.source_set["id"],
            transformation_type="scale_signal",
            raw_parameters={"signal_key": "load_demand_mw", "scale_factor": 1.5},
            created_by="analyst@example.com",
        )

        self.assertEqual(derived["data_kind"], "derived")
        self.assertNotEqual(derived["id"], self.source_set["id"])
        values_by_key = {
            (value["period_index"], value["signal_key"]): value["value_numeric"]
            for value in derived["values"]
        }
        self.assertAlmostEqual(values_by_key[(0, "load_demand_mw")], 150.0)
        self.assertAlmostEqual(values_by_key[(1, "load_demand_mw")], 151.5)
        self.assertAlmostEqual(values_by_key[(0, "import_price_usd_per_mwh")], 50.0)

    def test_source_set_is_unchanged_after_transformation(self):
        self.store.apply_time_series_transformation(
            project_id=self.project["id"],
            time_series_set_id=self.source_set["id"],
            transformation_type="scale_signal",
            raw_parameters={"signal_key": "load_demand_mw", "scale_factor": 1.5},
        )

        reloaded_source = self.store.get_time_series_set(
            self.project["id"], self.source_set["id"]
        )
        self.assertEqual(reloaded_source["content_hash"], self.source_set["content_hash"])
        values_by_key = {
            (value["period_index"], value["signal_key"]): value["value_numeric"]
            for value in reloaded_source["values"]
        }
        self.assertAlmostEqual(values_by_key[(0, "load_demand_mw")], 100.0)

    def test_unknown_transformation_type_is_rejected_before_any_write(self):
        sets_before = len(self.store.list_time_series_sets(self.project["id"]))

        with self.assertRaises(TransformationError):
            self.store.apply_time_series_transformation(
                project_id=self.project["id"],
                time_series_set_id=self.source_set["id"],
                transformation_type="run_arbitrary_script",
                raw_parameters={},
            )

        self.assertEqual(
            len(self.store.list_time_series_sets(self.project["id"])), sets_before
        )

    def test_invalid_parameters_are_rejected_before_any_write(self):
        sets_before = len(self.store.list_time_series_sets(self.project["id"]))

        with self.assertRaises(TransformationError):
            self.store.apply_time_series_transformation(
                project_id=self.project["id"],
                time_series_set_id=self.source_set["id"],
                transformation_type="scale_signal",
                raw_parameters={"signal_key": "unknown_signal", "scale_factor": 2.0},
            )

        self.assertEqual(
            len(self.store.list_time_series_sets(self.project["id"])), sets_before
        )

    def test_derived_set_records_full_lineage_in_latest_revision_metadata(self):
        derived = self.store.apply_time_series_transformation(
            project_id=self.project["id"],
            time_series_set_id=self.source_set["id"],
            transformation_type="scale_signal",
            raw_parameters={"signal_key": "load_demand_mw", "scale_factor": 1.5},
        )

        transformation = derived["revision_metadata"]["transformation"]
        self.assertEqual(transformation["type"], "scale_signal")
        self.assertEqual(transformation["implementation_version"], 1)
        self.assertEqual(transformation["parameter_schema_version"], 1)
        self.assertEqual(
            transformation["parameters"],
            {"signal_key": "load_demand_mw", "scale_factor": 1.5},
        )
        self.assertEqual(len(transformation["inputs"]), 1)
        lineage_input = transformation["inputs"][0]
        self.assertEqual(lineage_input["time_series_set_id"], self.source_set["id"])
        self.assertEqual(lineage_input["revision_number"], self.source_set["revision_number"])
        self.assertEqual(lineage_input["content_hash"], self.source_set["content_hash"])

    def test_derived_set_is_bindable_in_a_case_input_variant(self):
        derived = self.store.apply_time_series_transformation(
            project_id=self.project["id"],
            time_series_set_id=self.source_set["id"],
            transformation_type="scale_signal",
            raw_parameters={"signal_key": "load_demand_mw", "scale_factor": 1.5},
        )
        case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        variant = self.store.get_or_create_default_input_variant(case["id"])

        binding = self.store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="load_demand_mw",
            time_series_set_id=derived["id"],
        )

        self.assertEqual(binding["time_series_set_id"], derived["id"])

    def test_rerunning_same_transformation_converges_without_duplicates(self):
        first = self.store.apply_time_series_transformation(
            project_id=self.project["id"],
            time_series_set_id=self.source_set["id"],
            transformation_type="scale_signal",
            raw_parameters={"signal_key": "load_demand_mw", "scale_factor": 1.5},
        )
        sets_after_first = self.store.list_time_series_sets(self.project["id"])

        second = self.store.apply_time_series_transformation(
            project_id=self.project["id"],
            time_series_set_id=self.source_set["id"],
            transformation_type="scale_signal",
            raw_parameters={"signal_key": "load_demand_mw", "scale_factor": 1.5},
        )
        sets_after_second = self.store.list_time_series_sets(self.project["id"])

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["content_hash"], second["content_hash"])
        self.assertEqual(len(sets_after_first), len(sets_after_second))

    def test_different_parameters_produce_a_second_derived_set(self):
        first = self.store.apply_time_series_transformation(
            project_id=self.project["id"],
            time_series_set_id=self.source_set["id"],
            transformation_type="scale_signal",
            raw_parameters={"signal_key": "load_demand_mw", "scale_factor": 1.5},
        )
        second = self.store.apply_time_series_transformation(
            project_id=self.project["id"],
            time_series_set_id=self.source_set["id"],
            transformation_type="scale_signal",
            raw_parameters={"signal_key": "load_demand_mw", "scale_factor": 2.0},
        )

        self.assertNotEqual(first["id"], second["id"])


if __name__ == "__main__":
    unittest.main()
