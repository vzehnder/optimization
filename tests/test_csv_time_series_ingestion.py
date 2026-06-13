import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import create_app
from app.persistence import AnalystStore
from app.validation import ValidationResult


class CsvTimeSeriesIngestionTests(unittest.TestCase):
    def make_client_and_scenario(self, input_source_root):
        client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                input_source_root=input_source_root,
            )
        )
        project = client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()
        client.post(
            f"/api/scenarios/{scenario['id']}/draft",
            json={
                "document": {
                    "schema_version": "bess_editor_draft.v1",
                    "case": {"name": "csv_case"},
                    "pcc": {"id": "bus_1", "type": "bus"},
                    "grid": {"id": "grid_1"},
                    "assets": [
                        {"id": "solar_1", "type": "renewable"},
                        {"id": "load_1", "type": "load"},
                    ],
                    "time_series": {"sources": []},
                    "solver": {"name": "HiGHS", "options": {}},
                }
            },
        )
        return client, scenario

    def make_hydro_client_and_scenario(self, input_source_root):
        client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                input_source_root=input_source_root,
            )
        )
        project = client.post("/api/projects", json={"name": "Hydro PMGD"}).json()
        scenario = client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Hydro base"},
        ).json()
        client.post(
            f"/api/scenarios/{scenario['id']}/draft",
            json={
                "document": {
                    "schema_version": "bess_editor_draft.v1",
                    "case": {"name": "hydro_csv_case"},
                    "pcc": {"id": "bus_1", "type": "bus"},
                    "grid": {"id": "grid_1"},
                    "assets": [
                        {
                            "id": "hydro_1",
                            "type": "hydro",
                            "storage_min_hm3": 1.0,
                            "storage_max_hm3": 5.0,
                            "initial_storage_hm3": 2.5,
                            "generation_mode": "linear",
                            "power_per_flow_mw_per_m3s": 0.08,
                            "turbine_flow_max_m3s": 40.0,
                            "reservoir_curve": [
                                {"storage_hm3": 1.0, "elevation_masl": 700.0},
                                {"storage_hm3": 5.0, "elevation_masl": 720.0},
                            ],
                        }
                    ],
                    "time_series": {"sources": []},
                    "solver": {"name": "HiGHS", "options": {}},
                }
            },
        )
        return client, scenario

    def test_csv_upload_suggests_and_validates_hydro_inflow_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_hydro_client_and_scenario(input_source_root)
            csv_text = (
                "period_start,hours,buy_price,sell_price,hydro_1_inflow_m3s\n"
                "2026-01-01T00:00:00,1.0,55.0,45.0,25.0\n"
                "2026-01-01T01:00:00,1.0,60.0,80.0,30.0\n"
            )

            upload = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("hydro.csv", csv_text, "text/csv")},
            ).json()["source"]

            self.assertEqual(
                upload["mapping_suggestions"]["hydro_inflow_m3s"],
                {"hydro_1": "hydro_1_inflow_m3s"},
            )

            mapping = {
                "timestamp": "period_start",
                "duration_hours": "hours",
                "import_price_usd_per_mwh": "buy_price",
                "export_price_usd_per_mwh": "sell_price",
                "hydro_inflow_m3s": {"hydro_1": "hydro_1_inflow_m3s"},
            }
            response = client.put(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{upload['id']}/mapping",
                json={"mapping": mapping},
            )

            self.assertEqual(response.status_code, 200)
            source = response.json()["source"]
            self.assertEqual(source["mapping"], mapping)
            self.assertEqual(source["validation"], {"ok": True, "errors": []})
            self.assertEqual(source["validated_rows"][0]["hydro_inflow_m3s"], {"hydro_1": 25.0})
            self.assertEqual(source["validated_rows"][1]["hydro_inflow_m3s"], {"hydro_1": 30.0})

    def test_xlsx_upload_suggests_hydro_inflow_from_generic_single_hydro_column(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_hydro_client_and_scenario(input_source_root)
            workbook_bytes = make_xlsx_bytes(
                [
                    ["period_start", "hours", "buy_price", "sell_price", "hydro_inflow_m3s"],
                    ["2026-01-01T00:00:00", 1.0, 55.0, 45.0, 25.0],
                    ["2026-01-01T01:00:00", 1.0, 60.0, 80.0, 30.0],
                ],
            )

            response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={
                    "source_file": (
                        "hydro.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

            self.assertEqual(response.status_code, 201)
            source = response.json()["source"]
            self.assertEqual(source["kind"], "xlsx")
            self.assertEqual(
                source["mapping_suggestions"]["hydro_inflow_m3s"],
                {"hydro_1": "hydro_inflow_m3s"},
            )

    def test_hydro_mapping_validation_defaults_missing_inflow_and_rejects_bad_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_hydro_client_and_scenario(input_source_root)
            csv_text = (
                "period_start,hours,buy_price,sell_price,hydro_inflow_m3s\n"
                "2026-01-01T00:00:00,1.0,55.0,45.0,-1.0\n"
                "2026-01-01T01:00:00,1.0,60.0,80.0,abc\n"
                "2026-01-01T02:00:00,1.0,70.0,120.0,\n"
            )
            upload = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("hydro.csv", csv_text, "text/csv")},
            ).json()["source"]

            missing_response = client.put(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{upload['id']}/mapping",
                json={
                    "mapping": {
                        "timestamp": "period_start",
                        "duration_hours": "hours",
                        "import_price_usd_per_mwh": "buy_price",
                        "export_price_usd_per_mwh": "sell_price",
                    }
                },
            )
            self.assertEqual(missing_response.status_code, 200)
            missing_source = missing_response.json()["source"]
            self.assertEqual(missing_source["validation"], {"ok": True, "errors": []})
            self.assertEqual(missing_source["validated_rows"][0]["hydro_inflow_m3s"], {"hydro_1": 0.0})

            bad_values_response = client.put(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{upload['id']}/mapping",
                json={
                    "mapping": {
                        "timestamp": "period_start",
                        "duration_hours": "hours",
                        "import_price_usd_per_mwh": "buy_price",
                        "export_price_usd_per_mwh": "sell_price",
                        "hydro_inflow_m3s": {"hydro_1": "hydro_inflow_m3s"},
                    }
                },
            )

            self.assertEqual(bad_values_response.status_code, 200)
            validation = bad_values_response.json()["source"]["validation"]
            self.assertFalse(validation["ok"])
            self.assertEqual(validation["error_category"], "python_validation")
            errors = validation["errors"]
            self.assertIn("row 2: hydro hydro_1 inflow must be nonnegative", errors)
            self.assertIn("row 3: hydro hydro_1 inflow must be numeric", errors)
            self.assertIn("row 4: hydro hydro_1 inflow must be numeric", errors)
            self.assertEqual(bad_values_response.json()["source"]["validated_rows"], [])

    def test_csv_upload_is_stored_previewed_and_mapped_for_a_draft(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_client_and_scenario(input_source_root)
            csv_text = (
                "timestamp,duration_hours,price_usd_per_mwh,import_price_usd_per_mwh,export_price_usd_per_mwh,"
                "solar_1_available_mw,load_1_demand_mw\n"
                "2026-01-01T00:00:00,1.0,50.0,55.0,42.0,3.5,2.0\n"
                "2026-01-01T01:00:00,1.0,52.0,60.0,48.0,4.0,2.5\n"
            )

            response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("../source.csv", csv_text, "text/csv")},
            )

            self.assertEqual(response.status_code, 201)
            source = response.json()["source"]
            stored_path = Path(source["stored_path"])
            self.assertTrue(stored_path.is_file())
            self.assertEqual(stored_path.read_text(encoding="utf-8"), csv_text)
            self.assertEqual(stored_path.resolve().relative_to(input_source_root.resolve()), Path(stored_path.name))
            self.assertEqual(source["original_filename"], "source.csv")
            self.assertEqual(
                source["columns"],
                [
                    "timestamp",
                    "duration_hours",
                    "price_usd_per_mwh",
                    "import_price_usd_per_mwh",
                    "export_price_usd_per_mwh",
                    "solar_1_available_mw",
                    "load_1_demand_mw",
                ],
            )
            self.assertEqual(len(source["preview_rows"]), 2)
            self.assertEqual(source["preview_rows"][0]["timestamp"], "2026-01-01T00:00:00")
            self.assertEqual(source["mapping_suggestions"]["timestamp"], "timestamp")
            self.assertEqual(source["mapping_suggestions"]["duration_hours"], "duration_hours")
            self.assertEqual(source["mapping_suggestions"]["price_usd_per_mwh"], "price_usd_per_mwh")
            self.assertEqual(
                source["mapping_suggestions"]["import_price_usd_per_mwh"],
                "import_price_usd_per_mwh",
            )
            self.assertEqual(
                source["mapping_suggestions"]["export_price_usd_per_mwh"],
                "export_price_usd_per_mwh",
            )
            self.assertEqual(
                source["mapping_suggestions"]["renewable_available_power_mw"],
                {"solar_1": "solar_1_available_mw"},
            )
            self.assertEqual(
                source["mapping_suggestions"]["load_demand_mw"],
                {"load_1": "load_1_demand_mw"},
            )

            draft = client.get(f"/api/scenarios/{scenario['id']}/draft").json()["draft"]["document"]
            self.assertEqual(draft["time_series"]["active_source_id"], source["id"])
            self.assertEqual(draft["time_series"]["sources"][0]["id"], source["id"])

    def test_xlsx_upload_uses_first_sheet_and_reuses_mapping_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_client_and_scenario(input_source_root)
            workbook_bytes = make_xlsx_bytes(
                [
                    [
                        "period_start",
                        "hours",
                        "buy",
                        "sell",
                        "solar_1_available_mw",
                        "load_1_demand_mw",
                    ],
                    ["2026-01-01T00:00:00", 0.5, 55.0, 42.0, 3.5, 2.0],
                    ["2026-01-01T00:30:00", 0.5, 60.0, 48.0, 4.0, 2.5],
                ],
                extra_sheet_rows=[["ignored"], ["not active"]],
            )

            response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={
                    "source_file": (
                        "source.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

            self.assertEqual(response.status_code, 201)
            source = response.json()["source"]
            self.assertEqual(source["kind"], "xlsx")
            self.assertEqual(source["selected_sheet"], "Sheet")
            self.assertEqual(
                source["columns"],
                ["period_start", "hours", "buy", "sell", "solar_1_available_mw", "load_1_demand_mw"],
            )
            self.assertEqual(source["preview_rows"][0]["period_start"], "2026-01-01T00:00:00")
            self.assertEqual(source["mapping_suggestions"]["timestamp"], "period_start")
            self.assertEqual(
                source["mapping_suggestions"]["renewable_available_power_mw"],
                {"solar_1": "solar_1_available_mw"},
            )

            mapping_response = client.put(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{source['id']}/mapping",
                json={
                    "mapping": {
                        "timestamp": "period_start",
                        "duration_hours": "hours",
                        "import_price_usd_per_mwh": "buy",
                        "export_price_usd_per_mwh": "sell",
                        "renewable_available_power_mw": {"solar_1": "solar_1_available_mw"},
                        "load_demand_mw": {"load_1": "load_1_demand_mw"},
                    }
                },
            )

            self.assertEqual(mapping_response.status_code, 200)
            mapped_source = mapping_response.json()["source"]
            self.assertEqual(mapped_source["validation"], {"ok": True, "errors": []})
            self.assertEqual(mapped_source["validated_rows"][1]["load_demand_mw"], {"load_1": 2.5})

    def test_xlsx_upload_can_read_selected_sheet(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_client_and_scenario(input_source_root)
            workbook_bytes = make_xlsx_bytes(
                [["ignored"], ["not active"]],
                extra_sheet_name="Inputs",
                extra_sheet_rows=[
                    ["period_start", "hours", "buy", "sell", "solar_1_available_mw", "load_1_demand_mw"],
                    ["2026-01-01T00:00:00", 1.0, 55.0, 42.0, 3.5, 2.0],
                ],
            )

            response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                data={"sheet_name": "Inputs"},
                files={
                    "source_file": (
                        "source.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

            self.assertEqual(response.status_code, 201)
            source = response.json()["source"]
            self.assertEqual(source["selected_sheet"], "Inputs")
            self.assertEqual(source["columns"][0], "period_start")
            self.assertEqual(source["preview_rows"][0]["load_1_demand_mw"], "2")

    def test_xlsx_upload_rejects_unsupported_formulas_with_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_client_and_scenario(input_source_root)
            workbook_bytes = make_xlsx_bytes(
                [
                    ["period_start", "hours", "buy", "sell", "solar_1_available_mw", "load_1_demand_mw"],
                    ["2026-01-01T00:00:00", 1.0, "=50+5", 42.0, 3.5, 2.0],
                ],
            )

            response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={
                    "source_file": (
                        "source.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

            self.assertEqual(response.status_code, 400)
            payload = response.json()
            self.assertEqual(payload["error_category"], "source_file")
            self.assertIn("formulas", payload["detail"])
            self.assertIn("not supported", payload["detail"])

    def test_csv_upload_parse_failure_is_reported_as_source_file_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_client_and_scenario(input_source_root)

            response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("source.csv", b"\xff\xfe\x00", "text/csv")},
            )

            self.assertEqual(response.status_code, 400)
            payload = response.json()
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error_category"], "source_file")
            self.assertEqual(payload["phase"], "source_file")
            self.assertIn("UTF-8", payload["detail"])

    def test_draft_page_shows_source_file_error_category_for_bad_upload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_client_and_scenario(input_source_root)

            response = client.post(
                f"/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("source.csv", b"\xff\xfe\x00", "text/csv")},
            )

            self.assertEqual(response.status_code, 200)
            self.assertIn("Source-file error", response.text)
            self.assertIn("UTF-8", response.text)

    def test_manual_mapping_override_is_saved_and_validates_csv_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_client_and_scenario(input_source_root)
            csv_text = (
                "period_start,hours,buy,sell,pv_available,site_demand\n"
                "2026-01-01T00:00:00,0.5,55.0,42.0,3.5,2.0\n"
                "2026-01-01T00:30:00,0.5,60.0,48.0,4.0,2.5\n"
            )
            upload = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("source.csv", csv_text, "text/csv")},
            ).json()["source"]
            mapping = {
                "timestamp": "period_start",
                "duration_hours": "hours",
                "import_price_usd_per_mwh": "buy",
                "export_price_usd_per_mwh": "sell",
                "renewable_available_power_mw": {"solar_1": "pv_available"},
                "load_demand_mw": {"load_1": "site_demand"},
            }

            response = client.put(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{upload['id']}/mapping",
                json={"mapping": mapping},
            )

            self.assertEqual(response.status_code, 200)
            source = response.json()["source"]
            self.assertEqual(source["mapping"], mapping)
            self.assertEqual(source["validation"], {"ok": True, "errors": []})
            self.assertEqual(source["validated_rows"][0]["duration_hours"], 0.5)
            self.assertEqual(source["validated_rows"][0]["renewable_available_power_mw"], {"solar_1": 3.5})
            self.assertEqual(source["validated_rows"][1]["load_demand_mw"], {"load_1": 2.5})

            draft = client.get(f"/api/scenarios/{scenario['id']}/draft").json()["draft"]["document"]
            stored_source = draft["time_series"]["sources"][0]
            self.assertEqual(stored_source["mapping"], mapping)
            self.assertTrue(stored_source["validation"]["ok"])

    def test_blank_numeric_mappings_default_to_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_client_and_scenario(input_source_root)
            csv_text = (
                "period_start,hours,sell\n"
                "2026-01-01T00:00:00,0.5,42.0\n"
                "2026-01-01T00:30:00,0.5,48.0\n"
            )
            upload = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("source.csv", csv_text, "text/csv")},
            ).json()["source"]
            mapping = {
                "timestamp": "period_start",
                "duration_hours": "hours",
                "import_price_usd_per_mwh": None,
                "export_price_usd_per_mwh": "sell",
                "renewable_available_power_mw": {"solar_1": None},
                "load_demand_mw": {"load_1": ""},
            }

            response = client.put(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{upload['id']}/mapping",
                json={"mapping": mapping},
            )

            self.assertEqual(response.status_code, 200)
            source = response.json()["source"]
            self.assertEqual(source["validation"], {"ok": True, "errors": []})
            self.assertEqual(source["mapping"], mapping)
            self.assertEqual(source["validated_rows"][0]["price_usd_per_mwh"], 0.0)
            self.assertEqual(source["validated_rows"][0]["import_price_usd_per_mwh"], 0.0)
            self.assertEqual(source["validated_rows"][0]["export_price_usd_per_mwh"], 42.0)
            self.assertEqual(source["validated_rows"][0]["renewable_available_power_mw"], {"solar_1": 0.0})
            self.assertEqual(source["validated_rows"][0]["load_demand_mw"], {"load_1": 0.0})

    def test_mapping_validation_reports_missing_mappings_and_bad_csv_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_client_and_scenario(input_source_root)
            csv_text = (
                "timestamp,duration_hours,import_price_usd_per_mwh,export_price_usd_per_mwh,"
                "solar_1_available_mw,load_1_demand_mw\n"
                "2026-01-01T01:00:00,-1.0,55.0,42.0,-3.5,-2.0\n"
                "2026-01-01T00:00:00,abc,bad,48.0,4.0,not-a-number\n"
                "2026-01-01T00:00:00,1.0,60.0,50.0,5.0,2.5\n"
            )
            upload = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("source.csv", csv_text, "text/csv")},
            ).json()["source"]

            missing_response = client.put(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{upload['id']}/mapping",
                json={
                    "mapping": {
                        "timestamp": "timestamp",
                        "import_price_usd_per_mwh": "import_price_usd_per_mwh",
                    }
                },
            )
            self.assertEqual(missing_response.status_code, 200)
            missing_validation = missing_response.json()["source"]["validation"]
            self.assertEqual(missing_validation["error_category"], "mapping")
            missing_errors = missing_validation["errors"]
            self.assertIn("duration_hours mapping is required", missing_errors)
            self.assertNotIn("renewable_available_power_mw mapping is required for solar_1", missing_errors)
            self.assertNotIn("load_demand_mw mapping is required for load_1", missing_errors)

            bad_values_response = client.put(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{upload['id']}/mapping",
                json={
                    "mapping": {
                        "timestamp": "timestamp",
                        "duration_hours": "duration_hours",
                        "import_price_usd_per_mwh": "import_price_usd_per_mwh",
                        "export_price_usd_per_mwh": "export_price_usd_per_mwh",
                        "renewable_available_power_mw": {"solar_1": "solar_1_available_mw"},
                        "load_demand_mw": {"load_1": "load_1_demand_mw"},
                    }
                },
            )

            self.assertEqual(bad_values_response.status_code, 200)
            validation = bad_values_response.json()["source"]["validation"]
            self.assertFalse(validation["ok"])
            self.assertEqual(validation["error_category"], "python_validation")
            errors = validation["errors"]
            self.assertIn("row 2: duration_hours must be positive", errors)
            self.assertIn("row 2: renewable solar_1 availability must be nonnegative", errors)
            self.assertIn("row 2: load load_1 demand must be nonnegative", errors)
            self.assertIn("row 3: timestamps must be sorted ascending", errors)
            self.assertIn("row 3: duration_hours must be numeric", errors)
            self.assertIn("row 3: import_price_usd_per_mwh must be numeric", errors)
            self.assertIn("row 3: load load_1 must be numeric", errors)
            self.assertIn("row 4: duplicate timestamp 2026-01-01T00:00:00", errors)
            self.assertEqual(bad_values_response.json()["source"]["validated_rows"], [])

    def test_draft_page_uploads_previews_maps_and_validates_csv_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_client_and_scenario(input_source_root)

            draft_page = client.get(f"/scenarios/{scenario['id']}/draft")
            self.assertEqual(draft_page.status_code, 200)
            self.assertIn('name="source_file"', draft_page.text)
            self.assertIn(f'action="/scenarios/{scenario["id"]}/draft/time-series-sources/upload"', draft_page.text)

            csv_text = (
                "period_start,hours,buy,sell,pv_available,site_demand\n"
                "2026-01-01T00:00:00,1.0,55.0,42.0,3.5,2.0\n"
            )
            upload_response = client.post(
                f"/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("source.csv", csv_text, "text/csv")},
                follow_redirects=False,
            )
            self.assertEqual(upload_response.status_code, 303)
            self.assertEqual(upload_response.headers["location"], f"/scenarios/{scenario['id']}/draft")

            uploaded_page = client.get(f"/scenarios/{scenario['id']}/draft")
            self.assertEqual(uploaded_page.status_code, 200)
            self.assertIn("CSV Time-Series Source", uploaded_page.text)
            self.assertIn("period_start", uploaded_page.text)
            self.assertIn("pv_available", uploaded_page.text)
            self.assertIn('name="mapping_timestamp"', uploaded_page.text)
            self.assertIn('name="mapping_renewable_available_power_mw__solar_1"', uploaded_page.text)

            source_id = client.get(f"/api/scenarios/{scenario['id']}/draft").json()["draft"]["document"][
                "time_series"
            ]["active_source_id"]
            mapping_response = client.post(
                f"/scenarios/{scenario['id']}/draft/time-series-sources/{source_id}/mapping",
                data={
                    "mapping_timestamp": "period_start",
                    "mapping_duration_hours": "hours",
                    "mapping_import_price_usd_per_mwh": "buy",
                    "mapping_export_price_usd_per_mwh": "sell",
                    "mapping_renewable_available_power_mw__solar_1": "pv_available",
                    "mapping_load_demand_mw__load_1": "site_demand",
                },
                follow_redirects=False,
            )
            self.assertEqual(mapping_response.status_code, 303)

            validated_page = client.get(f"/scenarios/{scenario['id']}/draft")
            self.assertIn("Time-Series Validation", validated_page.text)
            self.assertIn("Valid mapped rows: 1", validated_page.text)

    def test_draft_page_upload_creates_initial_draft_when_none_is_saved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client = TestClient(
                create_app(
                    validation_service=StubValidationService(),
                    store=AnalystStore("sqlite:///:memory:"),
                    run_queue=NoopRunQueue(),
                    input_source_root=input_source_root,
                )
            )
            project = client.post("/api/projects", json={"name": "Unsaved Draft Upload"}).json()
            scenario = client.post(
                f"/api/projects/{project['id']}/scenarios",
                json={"name": "Upload before explicit save"},
            ).json()

            draft_page = client.get(f"/scenarios/{scenario['id']}/draft")
            self.assertEqual(draft_page.status_code, 200)
            self.assertIn("No active draft saved yet", draft_page.text)

            upload_response = client.post(
                f"/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={
                    "source_file": (
                        "time_series_20h.csv",
                        (
                            "period_start,hours,buy_price,sell_price\n"
                            "2026-01-01T00:00:00,1.0,55.0,45.0\n"
                        ),
                        "text/csv",
                    )
                },
                follow_redirects=False,
            )

            self.assertEqual(upload_response.status_code, 303)
            saved_draft = client.get(f"/api/scenarios/{scenario['id']}/draft").json()["draft"]
            self.assertEqual(saved_draft["document"]["case"]["name"], scenario["name"])
            self.assertEqual(
                saved_draft["document"]["time_series"]["sources"][0]["original_filename"],
                "time_series_20h.csv",
            )
            uploaded_page = client.get(f"/scenarios/{scenario['id']}/draft")
            self.assertIn("time_series_20h.csv", uploaded_page.text)

    def test_draft_page_maps_hydro_inflow_source_from_form(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, scenario = self.make_hydro_client_and_scenario(input_source_root)
            csv_text = (
                "period_start,hours,buy_price,sell_price,hydro_inflow_m3s\n"
                "2026-01-01T00:00:00,1.0,55.0,45.0,25.0\n"
            )
            upload_response = client.post(
                f"/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("hydro.csv", csv_text, "text/csv")},
                follow_redirects=False,
            )
            self.assertEqual(upload_response.status_code, 303)

            uploaded_page = client.get(f"/scenarios/{scenario['id']}/draft")
            self.assertEqual(uploaded_page.status_code, 200)
            self.assertIn('name="mapping_hydro_inflow_m3s__hydro_1"', uploaded_page.text)

            source_id = client.get(f"/api/scenarios/{scenario['id']}/draft").json()["draft"]["document"][
                "time_series"
            ]["active_source_id"]
            mapping_response = client.post(
                f"/scenarios/{scenario['id']}/draft/time-series-sources/{source_id}/mapping",
                data={
                    "mapping_timestamp": "period_start",
                    "mapping_duration_hours": "hours",
                    "mapping_import_price_usd_per_mwh": "buy_price",
                    "mapping_export_price_usd_per_mwh": "sell_price",
                    "mapping_hydro_inflow_m3s__hydro_1": "hydro_inflow_m3s",
                },
                follow_redirects=False,
            )

            self.assertEqual(mapping_response.status_code, 303)
            validated_page = client.get(f"/scenarios/{scenario['id']}/draft")
            self.assertIn("Time-Series Validation", validated_page.text)
            self.assertIn("Valid mapped rows: 1", validated_page.text)


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
        )


class NoopRunQueue:
    def enqueue(self, run_id):
        pass

    def stop(self):
        pass


def make_xlsx_bytes(rows, *, extra_sheet_name="Extra", extra_sheet_rows=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet"
    for row in rows:
        sheet.append(row)
    if extra_sheet_rows:
        extra = workbook.create_sheet(extra_sheet_name)
        for row in extra_sheet_rows:
            extra.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
