import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import bootstrap_admin_with_csrf, csrf_headers, post_json_with_csrf


class GuidedImportPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.client = TestClient(create_app(
            store=self.store, auth_enabled=True,
            input_source_root=Path(self.temp.name),
        ))
        bootstrap_admin_with_csrf(self.client, "ux003@example.local", "import-test-pass")
        self.project = post_json_with_csrf(self.client, "/api/projects", {"name": "UX003"}).json()
        scenario = post_json_with_csrf(self.client, f"/api/projects/{self.project['id']}/scenarios", {"name": "Precios"}).json()
        self.root = f"/api/scenarios/{scenario['id']}/draft/time-series-sources"
        self.scenario_id = scenario["id"]
        self.payload = {
            "set_name": "Precios enero", "version_label": "v1", "data_kind": "real",
            "timezone": "UTC", "timestamp_column": "timestamp", "duration_hours_column": "hours",
            "signal_mappings": [{"source_column": "price", "signal_key": "price_usd_per_mwh", "source_unit": "USD/MWh"}],
        }

    def upload(self, content):
        response = self.client.post(f"{self.root}/upload", headers=csrf_headers(self.client),
            files={"source_file": ("precios.csv", content, "text/csv")})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["source"]

    def test_reviews_known_values_and_coverage_without_creating_a_catalog_set(self):
        source = self.upload("timestamp,hours,price\n2026-01-01T00:00:00+00:00,1,55\n2026-01-01T01:00:00+00:00,1,60\n")
        response = post_json_with_csrf(self.client, f"{self.root}/{source['id']}/catalog-preview", self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()["preview"]
        self.assertEqual(preview["period_count"], 2)
        self.assertEqual(preview["coverage_start"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(preview["coverage_end"], "2026-01-01T02:00:00+00:00")
        self.assertEqual(preview["resolution_hours"], 1)
        self.assertEqual([row["price_usd_per_mwh"] for row in preview["rows"]], [55, 60])
        sets = self.client.get(f"/api/projects/{self.project['id']}/time-series-sets").json()["time_series_sets"]
        self.assertEqual(sets, [])

    def test_invalid_xlsx_value_identifies_sheet_row_and_column_before_import(self):
        book = Workbook()
        book.active.title = "Notas"
        book.active.append(["nota"])
        sheet = book.create_sheet("Precios")
        sheet.append(["timestamp", "hours", "price"])
        sheet.append(["2026-01-01T00:00:00+00:00", 1, "1,234"])
        content = BytesIO()
        book.save(content)
        response = self.client.post(f"{self.root}/upload", headers=csrf_headers(self.client),
            data={"sheet_name": "Precios"}, files={"source_file": ("precios.xlsx", content.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        self.assertEqual(response.status_code, 201, response.text)
        source = response.json()["source"]
        response = post_json_with_csrf(self.client, f"{self.root}/{source['id']}/catalog-preview", self.payload)
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json().get("location"), {"sheet": "Precios", "row": 2, "column": "price"})
        self.assertEqual(self.client.get(f"/api/projects/{self.project['id']}/time-series-sets").json()["time_series_sets"], [])

    def test_import_route_is_selected_by_server_cutover_state(self):
        path = f"/api/scenarios/{self.scenario_id}/draft/time-series-import-options"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["mode"], "project_catalog")
        with tempfile.TemporaryDirectory() as recovery:
            self.store.take_c0_recovery_point(actor="internal_admin", copy_directory=Path(recovery))
            self.store.backfill_time_series_c2(actor="internal_admin")
            self.store.backfill_time_series_c3(actor="internal_admin")
            self.store.backfill_time_series_c4(actor="internal_admin")
            self.store.verify_time_series_c5_shadow(actor="internal_admin")
            self.store.cut_over_time_series_c6(actor="internal_admin")
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["mode"], "protected")

    def test_a_gap_is_located_before_confirming_a_continuous_file_import(self):
        source = self.upload("timestamp,hours,price\n2026-01-01T00:00:00+00:00,1,55\n2026-01-01T02:00:00+00:00,1,60\n")
        response = post_json_with_csrf(self.client, f"{self.root}/{source['id']}/catalog-preview", self.payload)
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()["location"], {"sheet": None, "row": 3, "column": "timestamp"})

    def test_confirming_a_changed_source_requires_review_again_and_creates_nothing(self):
        source = self.upload("timestamp,hours,price\n2026-01-01T00:00:00+00:00,1,55\n")
        preview = post_json_with_csrf(self.client, f"{self.root}/{source['id']}/catalog-preview", self.payload).json()["preview"]
        from tests.auth_test_helpers import put_json_with_csrf
        changed = put_json_with_csrf(self.client, f"{self.root}/{source['id']}/rows", {"rows": [{"timestamp": "2026-01-01T00:00:00+00:00", "hours": "1", "price": "70"}]})
        self.assertEqual(changed.status_code, 200, changed.text)
        response = post_json_with_csrf(self.client, f"{self.root}/{source['id']}/catalog-import", {**self.payload, "expected_preview_hash": preview.get("content_hash", "missing")})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.client.get(f"/api/projects/{self.project['id']}/time-series-sets").json()["time_series_sets"], [])

    def test_temporal_errors_identify_the_cell_that_requires_correction(self):
        for timestamp, hours, column in [("not-a-date", "1", "timestamp"), ("2026-01-01T00:00:00Z", "0", "hours")]:
            with self.subTest(timestamp=timestamp, hours=hours):
                source = self.upload(f"timestamp,hours,price\n{timestamp},{hours},55\n")
                response = post_json_with_csrf(self.client, f"{self.root}/{source['id']}/catalog-preview", self.payload)
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(response.json()["location"], {"sheet": None, "row": 2, "column": column})
