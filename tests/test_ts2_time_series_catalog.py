import dataclasses
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import create_app
from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    CatalogValueEdit,
    TimeSeriesCatalogError,
    prepare_time_series_catalog_import,
    validate_catalog_value_edits,
)
from app.time_series_catalog import TimeSeriesSignalDefinition
from app.validation import ValidationResult


def make_xlsx_bytes(rows, *, extra_sheet_name=None, extra_sheet_rows=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet"
    for row in rows:
        sheet.append(row)
    if extra_sheet_rows:
        extra = workbook.create_sheet(extra_sheet_name or "Extra")
        for row in extra_sheet_rows:
            extra.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


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

    def test_xlsx_source_on_chosen_sheet_imports_a_project_time_series_set(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)
            workbook_bytes = make_xlsx_bytes(
                [["ignored"]],
                extra_sheet_name="Prices",
                extra_sheet_rows=[
                    ["period_start", "hours", "spot_price"],
                    ["2026-01-01T00:00:00", 1.0, 55.0],
                    ["2026-01-01T01:00:00", 1.0, 60.0],
                ],
            )

            upload_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                data={"sheet_name": "Prices"},
                files={
                    "source_file": (
                        "prices.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
            self.assertEqual(upload_response.status_code, 201)
            source = upload_response.json()["source"]
            self.assertEqual(source["kind"], "xlsx")
            self.assertEqual(source["selected_sheet"], "Prices")
            self.assertEqual(source["available_sheets"], ["Sheet", "Prices"])

            import_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{source['id']}/catalog-import",
                json={
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
                },
            )

            self.assertEqual(import_response.status_code, 201)
            created_set = import_response.json()["time_series_set"]
            self.assertEqual(created_set["project_id"], project["id"])
            self.assertEqual(created_set["period_count"], 2)
            self.assertEqual(created_set["signal_count"], 1)

            detail_response = client.get(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}"
            )
            detail = detail_response.json()["time_series_set"]
            self.assertEqual(detail["source"]["original_filename"], "prices.xlsx")
            self.assertEqual(detail["source"]["selected_sheet"], "Prices")

    def test_xlsx_source_shares_centralized_validation_with_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, _project, scenario = self.make_client_and_context(input_source_root)
            workbook_bytes = make_xlsx_bytes(
                [
                    ["period_start", "hours", "spot_price"],
                    ["2026-01-01T00:00:00", 1.0, 55.0],
                    ["2026-01-01T00:00:00", 1.0, 60.0],
                ],
            )

            upload_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={
                    "source_file": (
                        "prices.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
            source = upload_response.json()["source"]

            import_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{source['id']}/catalog-import",
                json={
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
                },
            )

            self.assertEqual(import_response.status_code, 400)
            self.assertIn(
                "row 3: duplicate timestamp '2026-01-01T00:00:00' (already used by row 2)",
                import_response.json()["detail"],
            )

    def import_csv_set(
        self,
        client,
        scenario,
        *,
        set_name,
        version_label,
        signal_key="price_usd_per_mwh",
        source_column="spot_price",
    ):
        csv_text = (
            f"period_start,hours,{source_column}\n"
            "2026-01-01T00:00:00,1.0,55.0\n"
            "2026-01-01T01:00:00,1.0,60.0\n"
        )
        upload_response = client.post(
            f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
            files={"source_file": (f"{set_name}.csv", csv_text, "text/csv")},
        )
        source = upload_response.json()["source"]
        import_response = client.post(
            f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{source['id']}/catalog-import",
            json={
                "set_name": set_name,
                "version_label": version_label,
                "data_kind": "real",
                "timezone": "America/Santiago",
                "timestamp_column": "period_start",
                "duration_hours_column": "hours",
                "signal_mappings": [
                    {"source_column": source_column, "signal_key": signal_key}
                ],
            },
        )
        self.assertEqual(import_response.status_code, 201)
        return import_response.json()["time_series_set"]

    def test_project_catalog_lists_sets_with_summary_fields_ordered_by_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)
            self.import_csv_set(
                client, scenario, set_name="Spot price Jan 2026", version_label="v1"
            )
            self.import_csv_set(
                client, scenario, set_name="Demand Jan 2026", version_label="v1",
                signal_key="load_demand_mw", source_column="demand",
            )

            catalog_response = client.get(
                f"/api/projects/{project['id']}/time-series-sets"
            )

            self.assertEqual(catalog_response.status_code, 200)
            catalog = catalog_response.json()["time_series_sets"]
            self.assertEqual(
                [item["name"] for item in catalog],
                ["Demand Jan 2026", "Spot price Jan 2026"],
            )
            first = catalog[0]
            self.assertEqual(first["version_label"], "v1")
            self.assertEqual(first["data_kind"], "real")
            self.assertEqual(first["status"], "validated")
            self.assertEqual(first["timezone"], "America/Santiago")
            self.assertEqual(first["revision_number"], 1)
            self.assertTrue(first["content_hash"].startswith("sha256:"))
            self.assertEqual(first["signal_count"], 1)
            self.assertEqual(first["period_count"], 2)

    def test_project_catalog_only_lists_sets_for_that_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project_a, scenario_a = self.make_client_and_context(
                input_source_root
            )
            self.import_csv_set(
                client, scenario_a, set_name="Project A Prices", version_label="v1"
            )
            project_b = client.post(
                "/api/projects", json={"name": "TS-2 Catalog Project B"}
            ).json()
            scenario_b = client.post(
                f"/api/projects/{project_b['id']}/scenarios",
                json={"name": "Catalog import B"},
            ).json()
            client.post(
                f"/api/scenarios/{scenario_b['id']}/draft",
                json={
                    "document": {
                        "schema_version": "bess_editor_draft.v1",
                        "case": {"name": "ts2_catalog_case_b"},
                        "pcc": {"id": "bus_1", "type": "bus"},
                        "grid": {"id": "grid_1"},
                        "assets": [],
                        "time_series": {"sources": []},
                        "solver": {"name": "HiGHS", "options": {}},
                    }
                },
            )
            self.import_csv_set(
                client, scenario_b, set_name="Project B Prices", version_label="v1"
            )

            catalog_a = client.get(
                f"/api/projects/{project_a['id']}/time-series-sets"
            ).json()["time_series_sets"]
            catalog_b = client.get(
                f"/api/projects/{project_b['id']}/time-series-sets"
            ).json()["time_series_sets"]

            self.assertEqual([item["name"] for item in catalog_a], ["Project A Prices"])
            self.assertEqual([item["name"] for item in catalog_b], ["Project B Prices"])

    def test_project_catalog_404_for_unknown_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, _project, _scenario = self.make_client_and_context(input_source_root)

            response = client.get("/api/projects/999999/time-series-sets")

            self.assertEqual(response.status_code, 404)

    def test_time_series_set_detail_includes_horizon_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)
            created_set = self.import_csv_set(
                client, scenario, set_name="Spot price Jan 2026", version_label="v1"
            )

            detail = client.get(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}"
            ).json()["time_series_set"]

            self.assertEqual(
                detail["horizon"],
                {
                    "period_count": 2,
                    "start": "2026-01-01T00:00:00-03:00",
                    "end": "2026-01-01T02:00:00-03:00",
                },
            )


class ValidateCatalogValueEditsTests(unittest.TestCase):
    price_definitions = {
        "price_usd_per_mwh": TimeSeriesSignalDefinition(
            signal_key="price_usd_per_mwh", unit="USD/MWh"
        ),
        "load_demand_mw": TimeSeriesSignalDefinition(
            signal_key="load_demand_mw",
            unit="MW",
            entity_type="component:load",
            nonnegative=True,
        ),
    }

    def test_accepts_numeric_edits_for_known_signals_and_periods(self):
        prepared = validate_catalog_value_edits(
            edits=[
                CatalogValueEdit(
                    period_index=0, signal_key="price_usd_per_mwh", value_text="57.5"
                ),
                CatalogValueEdit(
                    period_index=1, signal_key="load_demand_mw", value_text="12.0"
                ),
            ],
            signal_definitions=self.price_definitions,
            known_period_indexes={0, 1},
        )

        self.assertEqual(
            [(edit.period_index, edit.signal_key, edit.value_numeric) for edit in prepared],
            [(0, "price_usd_per_mwh", 57.5), (1, "load_demand_mw", 12.0)],
        )

    def test_rejects_empty_edit_list(self):
        with self.assertRaisesRegex(TimeSeriesCatalogError, "at least one edit is required"):
            validate_catalog_value_edits(
                edits=[],
                signal_definitions=self.price_definitions,
                known_period_indexes={0},
            )

    def test_rejects_nonnumeric_edit_value(self):
        with self.assertRaisesRegex(
            TimeSeriesCatalogError,
            r"edit 1: price_usd_per_mwh at period 0 must be numeric",
        ):
            validate_catalog_value_edits(
                edits=[
                    CatalogValueEdit(
                        period_index=0,
                        signal_key="price_usd_per_mwh",
                        value_text="not-a-number",
                    )
                ],
                signal_definitions=self.price_definitions,
                known_period_indexes={0},
            )

    def test_rejects_negative_value_for_nonnegative_signal(self):
        with self.assertRaisesRegex(
            TimeSeriesCatalogError,
            r"edit 1: load_demand_mw at period 0 must be nonnegative",
        ):
            validate_catalog_value_edits(
                edits=[
                    CatalogValueEdit(
                        period_index=0, signal_key="load_demand_mw", value_text="-1.0"
                    )
                ],
                signal_definitions=self.price_definitions,
                known_period_indexes={0},
            )

    def test_rejects_unknown_signal_key(self):
        with self.assertRaisesRegex(
            TimeSeriesCatalogError, "signal_key 'unknown_signal' is not part of this time-series set"
        ):
            validate_catalog_value_edits(
                edits=[
                    CatalogValueEdit(
                        period_index=0, signal_key="unknown_signal", value_text="1.0"
                    )
                ],
                signal_definitions=self.price_definitions,
                known_period_indexes={0},
            )

    def test_rejects_unknown_period_index(self):
        with self.assertRaisesRegex(
            TimeSeriesCatalogError, "period 99 is not part of this time-series set"
        ):
            validate_catalog_value_edits(
                edits=[
                    CatalogValueEdit(
                        period_index=99, signal_key="price_usd_per_mwh", value_text="1.0"
                    )
                ],
                signal_definitions=self.price_definitions,
                known_period_indexes={0},
            )


class ManualValueEditTests(unittest.TestCase):
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
            json={"name": "TS-2 Manual Edit Project"},
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
                    "case": {"name": "ts2_manual_edit_case"},
                    "pcc": {"id": "bus_1", "type": "bus"},
                    "grid": {"id": "grid_1"},
                    "assets": [],
                    "time_series": {"sources": []},
                    "solver": {"name": "HiGHS", "options": {}},
                }
            },
        )
        return client, project, scenario

    def import_dual_signal_set(self, client, scenario):
        csv_text = (
            "period_start,hours,spot_price,demand\n"
            "2026-01-01T00:00:00,1.0,55.0,12.0\n"
            "2026-01-01T01:00:00,1.0,60.0,14.0\n"
        )
        upload_response = client.post(
            f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
            files={"source_file": ("price.csv", csv_text, "text/csv")},
        )
        source = upload_response.json()["source"]
        import_response = client.post(
            f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{source['id']}/catalog-import",
            json={
                "set_name": "Price and demand Jan 2026",
                "version_label": "v1",
                "data_kind": "real",
                "timezone": "America/Santiago",
                "timestamp_column": "period_start",
                "duration_hours_column": "hours",
                "signal_mappings": [
                    {"source_column": "spot_price", "signal_key": "price_usd_per_mwh"},
                    {"source_column": "demand", "signal_key": "load_demand_mw"},
                ],
            },
        )
        self.assertEqual(import_response.status_code, 201)
        return import_response.json()["time_series_set"]

    def test_manual_edit_creates_new_revision_and_recalculates_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)
            created_set = self.import_dual_signal_set(client, scenario)
            original_hash = created_set["content_hash"]

            edit_response = client.put(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}/values",
                json={
                    "edits": [
                        {
                            "period_index": 0,
                            "signal_key": "price_usd_per_mwh",
                            "value": "57.5",
                        }
                    ],
                    "change_summary": "Corrected spike on Jan 1st",
                },
            )

            self.assertEqual(edit_response.status_code, 200)
            updated_set = edit_response.json()["time_series_set"]
            self.assertEqual(updated_set["revision_number"], 2)
            self.assertNotEqual(updated_set["content_hash"], original_hash)
            edited_value = next(
                value
                for value in updated_set["values"]
                if value["period_index"] == 0 and value["signal_key"] == "price_usd_per_mwh"
            )
            self.assertEqual(edited_value["value_numeric"], 57.5)
            unedited_value = next(
                value
                for value in updated_set["values"]
                if value["period_index"] == 1 and value["signal_key"] == "price_usd_per_mwh"
            )
            self.assertEqual(unedited_value["value_numeric"], 60.0)

    def test_prior_revisions_remain_queryable_after_edit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)
            created_set = self.import_dual_signal_set(client, scenario)
            original_hash = created_set["content_hash"]

            client.put(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}/values",
                json={
                    "edits": [
                        {
                            "period_index": 0,
                            "signal_key": "price_usd_per_mwh",
                            "value": "57.5",
                        }
                    ]
                },
            )

            revisions = client.get(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}/revisions"
            ).json()["time_series_set_revisions"]

            self.assertEqual([revision["revision_number"] for revision in revisions], [2, 1])
            self.assertEqual(revisions[1]["content_hash"], original_hash)
            self.assertNotEqual(revisions[0]["content_hash"], original_hash)

    def test_invalid_manual_edit_rejected_without_creating_revision_or_changing_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)
            created_set = self.import_dual_signal_set(client, scenario)

            edit_response = client.put(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}/values",
                json={
                    "edits": [
                        {
                            "period_index": 0,
                            "signal_key": "price_usd_per_mwh",
                            "value": "not-a-number",
                        }
                    ]
                },
            )

            self.assertEqual(edit_response.status_code, 400)
            self.assertIn("must be numeric", edit_response.json()["detail"])

            detail = client.get(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}"
            ).json()["time_series_set"]
            self.assertEqual(detail["revision_number"], 1)
            self.assertEqual(detail["content_hash"], created_set["content_hash"])
            unchanged_value = next(
                value
                for value in detail["values"]
                if value["period_index"] == 0 and value["signal_key"] == "price_usd_per_mwh"
            )
            self.assertEqual(unchanged_value["value_numeric"], 55.0)

    def test_manual_edit_rejects_negative_value_for_nonnegative_signal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)
            created_set = self.import_dual_signal_set(client, scenario)

            edit_response = client.put(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}/values",
                json={
                    "edits": [
                        {"period_index": 0, "signal_key": "load_demand_mw", "value": "-2.0"}
                    ]
                },
            )

            self.assertEqual(edit_response.status_code, 400)
            self.assertIn("must be nonnegative", edit_response.json()["detail"])

    def test_manual_edit_rejects_unknown_signal_and_period(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)
            created_set = self.import_dual_signal_set(client, scenario)

            unknown_signal = client.put(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}/values",
                json={
                    "edits": [
                        {
                            "period_index": 0,
                            "signal_key": "hydro_inflow_m3s",
                            "value": "1.0",
                        }
                    ]
                },
            )
            self.assertEqual(unknown_signal.status_code, 400)
            self.assertIn("is not part of this time-series set", unknown_signal.json()["detail"])

            unknown_period = client.put(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}/values",
                json={
                    "edits": [
                        {
                            "period_index": 99,
                            "signal_key": "price_usd_per_mwh",
                            "value": "1.0",
                        }
                    ]
                },
            )
            self.assertEqual(unknown_period.status_code, 400)
            self.assertIn("is not part of this time-series set", unknown_period.json()["detail"])

    def test_manual_edit_requires_at_least_one_edit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)
            created_set = self.import_dual_signal_set(client, scenario)

            response = client.put(
                f"/api/projects/{project['id']}/time-series-sets/{created_set['id']}/values",
                json={"edits": []},
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn("at least one edit is required", response.json()["detail"])

    def test_manual_edit_404_for_unknown_set(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, _scenario = self.make_client_and_context(input_source_root)

            response = client.put(
                f"/api/projects/{project['id']}/time-series-sets/999999/values",
                json={
                    "edits": [
                        {"period_index": 0, "signal_key": "price_usd_per_mwh", "value": "1.0"}
                    ]
                },
            )

            self.assertEqual(response.status_code, 404)

    def test_persistence_edit_reuses_validation_and_updates_hash_directly(self):
        store = AnalystStore("sqlite:///:memory:")
        project = store.create_project(name="TS-2 direct edit project")
        scenario = store.create_scenario(project_id=project["id"], name="Catalog import")
        prepared = prepare_time_series_catalog_import(
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
        created_set = store.import_time_series_catalog_set(
            scenario_id=scenario["id"],
            source=source,
            prepared_import=prepared,
        )

        with self.assertRaisesRegex(TimeSeriesCatalogError, "must be numeric"):
            store.edit_time_series_set_values(
                project_id=project["id"],
                time_series_set_id=created_set["id"],
                edits=[
                    CatalogValueEdit(
                        period_index=0,
                        signal_key="price_usd_per_mwh",
                        value_text="bad",
                    )
                ],
            )

        updated_set = store.edit_time_series_set_values(
            project_id=project["id"],
            time_series_set_id=created_set["id"],
            edits=[
                CatalogValueEdit(
                    period_index=0, signal_key="price_usd_per_mwh", value_text="99.0"
                )
            ],
            created_by="ada@example.local",
        )

        self.assertEqual(updated_set["revision_number"], 2)
        self.assertEqual(updated_set["values"][0]["value_numeric"], 99.0)
        self.assertNotEqual(updated_set["content_hash"], created_set["content_hash"])
