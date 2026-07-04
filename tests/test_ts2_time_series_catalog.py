import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.time_series_catalog import CatalogImportRequest, prepare_time_series_catalog_import
from app.validation import ValidationResult


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
        )


class TimeSeriesCatalogImportTests(unittest.TestCase):
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
                value_column="spot_price",
                signal_key="price_usd_per_mwh",
            ),
        )

        self.assertEqual(prepared.signal.signal_key, "price_usd_per_mwh")
        self.assertEqual(prepared.signal.unit, "USD/MWh")
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

    def test_csv_source_imports_a_project_time_series_set_and_reads_it_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)
            csv_text = (
                "period_start,hours,spot_price\n"
                "2026-01-01T00:00:00,1.0,55.0\n"
                "2026-01-01T01:00:00,1.0,60.0\n"
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
                    "set_name": "Spot price Jan 2026",
                    "version_label": "v1",
                    "data_kind": "real",
                    "timezone": "America/Santiago",
                    "timestamp_column": "period_start",
                    "duration_hours_column": "hours",
                    "value_column": "spot_price",
                    "signal_key": "price_usd_per_mwh",
                },
            )

            self.assertEqual(import_response.status_code, 201)
            created_set = import_response.json()["time_series_set"]
            self.assertEqual(created_set["project_id"], project["id"])
            self.assertEqual(created_set["name"], "Spot price Jan 2026")
            self.assertEqual(created_set["version_number"], 1)
            self.assertEqual(created_set["version_label"], "v1")
            self.assertEqual(created_set["revision_number"], 1)
            self.assertEqual(created_set["data_kind"], "real")
            self.assertEqual(created_set["timezone"], "America/Santiago")
            self.assertEqual(created_set["status"], "validated")
            self.assertEqual(created_set["signal_count"], 1)
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
                        "signal_key": "price_usd_per_mwh",
                        "unit": "USD/MWh",
                    }
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
                        "signal_key": "price_usd_per_mwh",
                        "value_numeric": 55.0,
                    },
                    {
                        "period_index": 1,
                        "signal_key": "price_usd_per_mwh",
                        "value_numeric": 60.0,
                    },
                ],
            )
