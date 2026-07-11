import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)
from app.validation import ValidationResult


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(ok=True, phase="julia", message="ok", payload={"status": "ok"})


class RecordingRunQueue:
    def enqueue(self, run_id):
        pass

    def stop(self):
        pass


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


def demand_price_rows_with_gap(start, hours, missing_hours):
    rows = []
    for hour in hours:
        if hour in missing_hours:
            continue
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


class TimeSeriesTransformationApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                run_queue=RecordingRunQueue(),
            )
        )
        self.store = self.client.app.state.analyst_store
        self.project = self.store.create_project(name="TS-6 API project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-6 API scenario"
        )
        prepared = prepare_time_series_catalog_import(
            rows=demand_price_rows(datetime(2026, 1, 1), 3),
            request=CatalogImportRequest(
                set_name="Demand and price base",
                version_label="v1",
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
            ),
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

    def test_apply_scale_signal_returns_the_derived_set(self):
        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/"
            f"{self.source_set['id']}/transformations",
            json={
                "transformation_type": "scale_signal",
                "parameters": {"signal_key": "load_demand_mw", "scale_factor": 1.5},
            },
        )

        self.assertEqual(response.status_code, 201)
        derived = response.json()["time_series_set"]
        self.assertEqual(derived["data_kind"], "derived")
        self.assertNotEqual(derived["id"], self.source_set["id"])

    def test_unknown_transformation_type_returns_a_400_error(self):
        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/"
            f"{self.source_set['id']}/transformations",
            json={"transformation_type": "run_arbitrary_script", "parameters": {}},
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertIn("unsupported transformation_type", body["detail"])

    def test_invalid_parameters_return_a_400_error_before_any_write(self):
        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/"
            f"{self.source_set['id']}/transformations",
            json={
                "transformation_type": "scale_signal",
                "parameters": {"signal_key": "unknown_signal", "scale_factor": 2.0},
            },
        )

        self.assertEqual(response.status_code, 400)
        list_response = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        )
        self.assertEqual(len(list_response.json()["time_series_sets"]), 1)

    def test_unknown_time_series_set_returns_404(self):
        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/999999/transformations",
            json={
                "transformation_type": "scale_signal",
                "parameters": {"signal_key": "load_demand_mw", "scale_factor": 1.5},
            },
        )

        self.assertEqual(response.status_code, 404)


class ResampleTransformationApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                run_queue=RecordingRunQueue(),
            )
        )
        self.store = self.client.app.state.analyst_store
        self.project = self.store.create_project(name="TS-6 resample API project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-6 resample API scenario"
        )
        prepared = prepare_time_series_catalog_import(
            rows=demand_price_rows(datetime(2026, 1, 1), 4),
            request=CatalogImportRequest(
                set_name="Demand and price base",
                version_label="v1",
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
            ),
        )
        self.source_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_resample_api",
                "original_filename": "demand_price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test-resample-api",
            },
            prepared_import=prepared,
        )

    def test_apply_resample_returns_the_derived_set_at_the_target_resolution(self):
        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/"
            f"{self.source_set['id']}/transformations",
            json={
                "transformation_type": "resample",
                "parameters": {
                    "target_resolution_hours": 2.0,
                    "signal_methods": {
                        "load_demand_mw": "mean",
                        "import_price_usd_per_mwh": "mean",
                    },
                },
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        derived = response.json()["time_series_set"]
        self.assertEqual(derived["data_kind"], "derived")
        self.assertEqual(len(derived["periods"]), 2)

    def test_physically_meaningless_method_returns_a_400_error(self):
        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/"
            f"{self.source_set['id']}/transformations",
            json={
                "transformation_type": "resample",
                "parameters": {
                    "target_resolution_hours": 2.0,
                    "signal_methods": {
                        "load_demand_mw": "mean",
                        "import_price_usd_per_mwh": "sum",
                    },
                },
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertIn("not physically meaningful", body["detail"])


class InterpolateGapsTransformationApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                run_queue=RecordingRunQueue(),
            )
        )
        self.store = self.client.app.state.analyst_store
        self.project = self.store.create_project(name="TS-6 interpolate API project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-6 interpolate API scenario"
        )
        prepared = prepare_time_series_catalog_import(
            rows=demand_price_rows_with_gap(datetime(2026, 1, 1), range(5), {2}),
            request=CatalogImportRequest(
                set_name="Demand and price with gap",
                version_label="v1",
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
            ),
        )
        self.source_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_gap_api",
                "original_filename": "demand_price_gap.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test-gap-api",
            },
            prepared_import=prepared,
        )

    def test_apply_interpolate_gaps_returns_the_derived_set_with_the_gap_filled(self):
        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/"
            f"{self.source_set['id']}/transformations",
            json={
                "transformation_type": "interpolate_gaps",
                "parameters": {"method": "linear", "max_gap_hours": 2.0},
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        derived = response.json()["time_series_set"]
        self.assertEqual(derived["data_kind"], "derived")
        self.assertEqual(len(derived["periods"]), 5)
        self.assertEqual(
            derived["revision_metadata"]["transformation"]["execution"][
                "filled_period_indexes"
            ],
            [2],
        )

    def test_gap_larger_than_max_returns_a_400_error(self):
        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/"
            f"{self.source_set['id']}/transformations",
            json={
                "transformation_type": "interpolate_gaps",
                "parameters": {"method": "linear", "max_gap_hours": 0.5},
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertIn("exceeds max_gap_hours", body["detail"])


if __name__ == "__main__":
    unittest.main()
