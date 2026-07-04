import dataclasses
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)
from app.validation import ValidationResult


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
        )


def spot_price_import_request() -> CatalogImportRequest:
    return CatalogImportRequest(
        set_name="Spot price Jan 2026",
        version_label="v1",
        data_kind="real",
        timezone="America/Santiago",
        timestamp_column="period_start",
        duration_hours_column="hours",
        signal_mappings=[
            CatalogSignalMappingRequest(
                source_column="spot_price",
                signal_key="price_usd_per_mwh",
            )
        ],
    )


class TimeSeriesCatalogImportTests(unittest.TestCase):
    def test_rejects_duplicate_timestamps_with_row_context(self):
        with self.assertRaisesRegex(
            ValueError,
            r"row 3: duplicate timestamp '2026-01-01T00:00:00'.*row 2",
        ):
            prepare_time_series_catalog_import(
                rows=[
                    {
                        "period_start": "2026-01-01T00:00:00",
                        "hours": "1.0",
                        "spot_price": "55.0",
                    },
                    {
                        "period_start": "2026-01-01T00:00:00",
                        "hours": "1.0",
                        "spot_price": "60.0",
                    },
                ],
                request=spot_price_import_request(),
            )

    def test_rejects_unordered_timestamps_with_row_context(self):
        with self.assertRaisesRegex(
            ValueError,
            r"row 3: timestamp '2026-01-01T00:00:00' must come after row 2",
        ):
            prepare_time_series_catalog_import(
                rows=[
                    {
                        "period_start": "2026-01-01T01:00:00",
                        "hours": "1.0",
                        "spot_price": "55.0",
                    },
                    {
                        "period_start": "2026-01-01T00:00:00",
                        "hours": "1.0",
                        "spot_price": "60.0",
                    },
                ],
                request=spot_price_import_request(),
            )

    def test_rejects_overlapping_periods_from_incoherent_durations(self):
        with self.assertRaisesRegex(
            ValueError,
            r"row 3: period starts before row 2 ends",
        ):
            prepare_time_series_catalog_import(
                rows=[
                    {
                        "period_start": "2026-01-01T00:00:00",
                        "hours": "2.0",
                        "spot_price": "55.0",
                    },
                    {
                        "period_start": "2026-01-01T01:00:00",
                        "hours": "1.0",
                        "spot_price": "60.0",
                    },
                ],
                request=spot_price_import_request(),
            )

    def test_rejects_malformed_timestamp_with_row_context(self):
        with self.assertRaisesRegex(
            ValueError,
            r"row 2: timestamp 'not-a-date' must be ISO-8601",
        ):
            prepare_time_series_catalog_import(
                rows=[
                    {
                        "period_start": "not-a-date",
                        "hours": "1.0",
                        "spot_price": "55.0",
                    },
                ],
                request=spot_price_import_request(),
            )

    def test_rejects_nonnumeric_values_with_row_and_column_context(self):
        with self.assertRaisesRegex(
            ValueError,
            r"row 3: spot_price must be numeric",
        ):
            prepare_time_series_catalog_import(
                rows=[
                    {
                        "period_start": "2026-01-01T00:00:00",
                        "hours": "1.0",
                        "spot_price": "55.0",
                    },
                    {
                        "period_start": "2026-01-01T01:00:00",
                        "hours": "1.0",
                        "spot_price": "not-a-number",
                    },
                ],
                request=spot_price_import_request(),
            )

    def test_rejects_negative_values_for_nonnegative_signals(self):
        with self.assertRaisesRegex(
            ValueError,
            r"row 3: column 'demand' mapped to load_demand_mw must be nonnegative",
        ):
            prepare_time_series_catalog_import(
                rows=[
                    {
                        "period_start": "2026-01-01T00:00:00",
                        "hours": "1.0",
                        "demand": "12.5",
                    },
                    {
                        "period_start": "2026-01-01T01:00:00",
                        "hours": "1.0",
                        "demand": "-1.0",
                    },
                ],
                request=CatalogImportRequest(
                    set_name="Demand Jan 2026",
                    version_label="v1",
                    data_kind="real",
                    timezone="America/Santiago",
                    timestamp_column="period_start",
                    duration_hours_column="hours",
                    signal_mappings=[
                        CatalogSignalMappingRequest(
                            source_column="demand",
                            signal_key="load_demand_mw",
                        )
                    ],
                ),
            )

    def test_rejects_invalid_iana_timezone(self):
        with self.assertRaisesRegex(
            ValueError,
            r"timezone 'America/Springfield' is not a valid IANA timezone",
        ):
            prepare_time_series_catalog_import(
                rows=[
                    {
                        "period_start": "2026-01-01T00:00:00",
                        "hours": "1.0",
                        "spot_price": "55.0",
                    },
                ],
                request=CatalogImportRequest(
                    set_name="Spot price Jan 2026",
                    version_label="v1",
                    data_kind="real",
                    timezone="America/Springfield",
                    timestamp_column="period_start",
                    duration_hours_column="hours",
                    signal_mappings=[
                        CatalogSignalMappingRequest(
                            source_column="spot_price",
                            signal_key="price_usd_per_mwh",
                        )
                    ],
                ),
            )

    def test_rejects_nonpositive_durations_with_row_context(self):
        with self.assertRaisesRegex(
            ValueError,
            r"row 2: hours must be positive",
        ):
            prepare_time_series_catalog_import(
                rows=[
                    {
                        "period_start": "2026-01-01T00:00:00",
                        "hours": "0.0",
                        "spot_price": "55.0",
                    },
                ],
                request=spot_price_import_request(),
            )

    def test_deep_import_module_normalizes_rows_without_http_or_ui(self):
        prepared = prepare_time_series_catalog_import(
            rows=[
                {
                    "period_start": "2026-01-01T00:00:00",
                    "hours": "1.0",
                    "spot_price": "55.0",
                },
                {
                    "period_start": "2026-01-01T01:00:00",
                    "hours": "1.0",
                    "spot_price": "60.0",
                },
            ],
            request=CatalogImportRequest(
                set_name="Spot price Jan 2026",
                version_label="v1",
                data_kind="real",
                timezone="America/Santiago",
                timestamp_column="period_start",
                duration_hours_column="hours",
                signal_mappings=[
                    CatalogSignalMappingRequest(
                        source_column="spot_price",
                        signal_key="price_usd_per_mwh",
                    )
                ],
            ),
        )

        self.assertEqual(len(prepared.signals), 1)
        self.assertEqual(prepared.signals[0].signal_key, "price_usd_per_mwh")
        self.assertEqual(prepared.signals[0].unit, "USD/MWh")
        self.assertEqual(prepared.signals[0].source_column, "spot_price")
        self.assertEqual(prepared.signals[0].source_unit, "USD/MWh")
        self.assertEqual(
            [period.timestamp_start for period in prepared.periods],
            [
                "2026-01-01T00:00:00-03:00",
                "2026-01-01T01:00:00-03:00",
            ],
        )
        self.assertEqual(
            [value.value_numeric for value in prepared.values],
            [55.0, 60.0],
        )
        self.assertTrue(prepared.content_hash.startswith("sha256:"))

    def test_deep_import_module_supports_multiple_signal_mappings(self):
        prepared = prepare_time_series_catalog_import(
            rows=[
                {
                    "period_start": "2026-01-01T00:00:00",
                    "hours": "1.0",
                    "buy_price": "55.0",
                    "sell_price": "45.0",
                },
                {
                    "period_start": "2026-01-01T01:00:00",
                    "hours": "1.0",
                    "buy_price": "60.0",
                    "sell_price": "48.0",
                },
            ],
            request=CatalogImportRequest(
                set_name="Dual price Jan 2026",
                version_label="v1",
                data_kind="real",
                timezone="America/Santiago",
                timestamp_column="period_start",
                duration_hours_column="hours",
                signal_mappings=[
                    CatalogSignalMappingRequest(
                        source_column="buy_price",
                        signal_key="import_price_usd_per_mwh",
                    ),
                    CatalogSignalMappingRequest(
                        source_column="sell_price",
                        signal_key="export_price_usd_per_mwh",
                    ),
                ],
            ),
        )

        self.assertEqual(
            [signal.signal_key for signal in prepared.signals],
            ["import_price_usd_per_mwh", "export_price_usd_per_mwh"],
        )
        self.assertEqual(
            [signal.source_column for signal in prepared.signals],
            ["buy_price", "sell_price"],
        )
        self.assertEqual(
            [value.signal_key for value in prepared.values],
            [
                "import_price_usd_per_mwh",
                "export_price_usd_per_mwh",
                "import_price_usd_per_mwh",
                "export_price_usd_per_mwh",
            ],
        )
        self.assertEqual(
            [value.value_numeric for value in prepared.values],
            [55.0, 45.0, 60.0, 48.0],
        )

    def test_deep_import_module_rejects_unit_mismatch_with_column_context(self):
        with self.assertRaisesRegex(
            ValueError,
            "column 'spot_price'.*canonical unit 'USD/MWh'",
        ):
            prepare_time_series_catalog_import(
                rows=[
                    {
                        "period_start": "2026-01-01T00:00:00",
                        "hours": "1.0",
                        "spot_price": "55.0",
                    }
                ],
                request=CatalogImportRequest(
                    set_name="Spot price Jan 2026",
                    version_label="v1",
                    data_kind="real",
                    timezone="America/Santiago",
                    timestamp_column="period_start",
                    duration_hours_column="hours",
                    signal_mappings=[
                        CatalogSignalMappingRequest(
                            source_column="spot_price",
                            signal_key="price_usd_per_mwh",
                            source_unit="CLP/MWh",
                        )
                    ],
                ),
            )

    def make_client_and_context(self, input_source_root: Path):
        client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                input_source_root=input_source_root,
            )
        )
        project = client.post(
            "/api/projects",
            json={"name": "TS-2 Catalog Project"},
        ).json()
        scenario = client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Catalog import"},
        ).json()
        client.post(
            f"/api/scenarios/{scenario['id']}/draft",
            json={
                "document": {
                    "schema_version": "bess_editor_draft.v1",
                    "case": {"name": "ts2_catalog_case"},
                    "pcc": {"id": "bus_1", "type": "bus"},
                    "grid": {"id": "grid_1"},
                    "assets": [],
                    "time_series": {"sources": []},
                    "solver": {"name": "HiGHS", "options": {}},
                }
            },
        )
        return client, project, scenario

    def test_failed_import_persists_no_partial_set_and_can_be_retried(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, _project, scenario = self.make_client_and_context(input_source_root)
            invalid_csv_text = (
                "period_start,hours,spot_price\n"
                "2026-01-01T00:00:00,1.0,55.0\n"
                "2026-01-01T01:00:00,1.0,not-a-number\n"
            )
            import_payload = {
                "set_name": "Spot price Jan 2026",
                "version_label": "v1",
                "data_kind": "real",
                "timezone": "America/Santiago",
                "timestamp_column": "period_start",
                "duration_hours_column": "hours",
                "signal_mappings": [
                    {
                        "source_column": "spot_price",
                        "signal_key": "price_usd_per_mwh",
                    }
                ],
            }

            invalid_upload = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("price.csv", invalid_csv_text, "text/csv")},
            )
            invalid_source = invalid_upload.json()["source"]
            failed_import = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{invalid_source['id']}/catalog-import",
                json=import_payload,
            )
            self.assertEqual(failed_import.status_code, 400)
            self.assertIn("row 3", failed_import.json()["detail"])

            corrected_csv_text = (
                "period_start,hours,spot_price\n"
                "2026-01-01T00:00:00,1.0,55.0\n"
                "2026-01-01T01:00:00,1.0,60.0\n"
            )
            corrected_upload = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("price.csv", corrected_csv_text, "text/csv")},
            )
            corrected_source = corrected_upload.json()["source"]
            retried_import = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{corrected_source['id']}/catalog-import",
                json=import_payload,
            )

            self.assertEqual(retried_import.status_code, 201)
            created_set = retried_import.json()["time_series_set"]
            self.assertEqual(created_set["version_label"], "v1")
            self.assertEqual(created_set["period_count"], 2)

    def test_persistence_failure_mid_import_leaves_no_partial_set(self):
        store = AnalystStore("sqlite:///:memory:")
        project = store.create_project(name="TS-2 partial import project")
        scenario = store.create_scenario(project_id=project["id"], name="Catalog import")
        valid_import = prepare_time_series_catalog_import(
            rows=[
                {
                    "period_start": "2026-01-01T00:00:00",
                    "hours": "1.0",
                    "spot_price": "55.0",
                },
            ],
            request=spot_price_import_request(),
        )
        source = {
            "id": "csv_source_1",
            "original_filename": "price.csv",
            "media_type": "text/csv",
            "checksum": "sha256:test",
        }
        poisoned_import = dataclasses.replace(
            valid_import,
            values=[
                dataclasses.replace(value, signal_key="unknown_signal_key")
                for value in valid_import.values
            ],
        )

        with self.assertRaises(Exception):
            store.import_time_series_catalog_set(
                scenario_id=scenario["id"],
                source=source,
                prepared_import=poisoned_import,
            )

        created_set = store.import_time_series_catalog_set(
            scenario_id=scenario["id"],
            source=source,
            prepared_import=valid_import,
        )
        self.assertEqual(created_set["version_label"], "v1")
        self.assertEqual(created_set["period_count"], 1)

    def test_csv_source_imports_a_project_time_series_set_and_reads_it_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)
            csv_text = (
                "period_start,hours,buy_price,sell_price\n"
                "2026-01-01T00:00:00,1.0,55.0,45.0\n"
                "2026-01-01T01:00:00,1.0,60.0,48.0\n"
            )

            upload_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("price.csv", csv_text, "text/csv")},
            )
            self.assertEqual(upload_response.status_code, 201)
            source = upload_response.json()["source"]

            import_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{source['id']}/catalog-import",
                json={
                    "set_name": "Dual price Jan 2026",
                    "version_label": "v1",
                    "data_kind": "real",
                    "timezone": "America/Santiago",
                    "timestamp_column": "period_start",
                    "duration_hours_column": "hours",
                    "signal_mappings": [
                        {
                            "source_column": "buy_price",
                            "signal_key": "import_price_usd_per_mwh",
                            "source_unit": "USD/MWh",
                        },
                        {
                            "source_column": "sell_price",
                            "signal_key": "export_price_usd_per_mwh",
                            "source_unit": "USD/MWh",
                        },
                    ],
                },
            )

            self.assertEqual(import_response.status_code, 201)
            created_set = import_response.json()["time_series_set"]
            self.assertEqual(created_set["project_id"], project["id"])
            self.assertEqual(created_set["name"], "Dual price Jan 2026")
            self.assertEqual(created_set["version_number"], 1)
            self.assertEqual(created_set["version_label"], "v1")
            self.assertEqual(created_set["revision_number"], 1)
            self.assertEqual(created_set["data_kind"], "real")
            self.assertEqual(created_set["timezone"], "America/Santiago")
            self.assertEqual(created_set["status"], "validated")
            self.assertEqual(created_set["signal_count"], 2)
            self.assertEqual(created_set["period_count"], 2)
            self.assertTrue(created_set["content_hash"].startswith("sha256:"))
            self.assertTrue(created_set["source_checksum"].startswith("sha256:"))

            detail_response = client.get(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}"
            )

            self.assertEqual(detail_response.status_code, 200)
            detail = detail_response.json()["time_series_set"]
            self.assertEqual(detail["id"], created_set["id"])
            self.assertEqual(detail["source"]["original_filename"], "price.csv")
            self.assertEqual(detail["source"]["media_type"], "text/csv")
            self.assertTrue(detail["source"]["checksum"].startswith("sha256:"))
            self.assertEqual(
                detail["signals"],
                [
                    {
                        "entity_key": None,
                        "entity_type": None,
                        "signal_key": "import_price_usd_per_mwh",
                        "source_column": "buy_price",
                        "source_unit": "USD/MWh",
                        "unit": "USD/MWh",
                    },
                    {
                        "entity_key": None,
                        "entity_type": None,
                        "signal_key": "export_price_usd_per_mwh",
                        "source_column": "sell_price",
                        "source_unit": "USD/MWh",
                        "unit": "USD/MWh",
                    },
                ],
            )
            self.assertEqual(
                detail["periods"],
                [
                    {
                        "period_index": 0,
                        "timestamp_start": "2026-01-01T00:00:00-03:00",
                        "timestamp_end": "2026-01-01T01:00:00-03:00",
                        "duration_hours": 1.0,
                    },
                    {
                        "period_index": 1,
                        "timestamp_start": "2026-01-01T01:00:00-03:00",
                        "timestamp_end": "2026-01-01T02:00:00-03:00",
                        "duration_hours": 1.0,
                    },
                ],
            )
            self.assertEqual(
                detail["values"],
                [
                    {
                        "period_index": 0,
                        "signal_key": "export_price_usd_per_mwh",
                        "value_numeric": 45.0,
                    },
                    {
                        "period_index": 0,
                        "signal_key": "import_price_usd_per_mwh",
                        "value_numeric": 55.0,
                    },
                    {
                        "period_index": 1,
                        "signal_key": "export_price_usd_per_mwh",
                        "value_numeric": 48.0,
                    },
                    {
                        "period_index": 1,
                        "signal_key": "import_price_usd_per_mwh",
                        "value_numeric": 60.0,
                    },
                ],
            )
            self.assertEqual(
                detail["revision_metadata"]["mapping"],
                {
                    "duration_hours_column": "hours",
                    "signals": [
                        {
                            "canonical_unit": "USD/MWh",
                            "signal_key": "import_price_usd_per_mwh",
                            "source_column": "buy_price",
                            "source_unit": "USD/MWh",
                        },
                        {
                            "canonical_unit": "USD/MWh",
                            "signal_key": "export_price_usd_per_mwh",
                            "source_column": "sell_price",
                            "source_unit": "USD/MWh",
                        },
                    ],
                    "timestamp_column": "period_start",
                },
            )
