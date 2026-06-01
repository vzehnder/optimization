import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.validation import ValidationResult


REPO_ROOT = Path(__file__).resolve().parents[1]


class DraftGeneratedSystemCaseTests(unittest.TestCase):
    def test_api_generates_and_validates_system_case_from_csv_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_csv(client, scenario["id"])

            preview_response = client.get(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case",
            )

            self.assertEqual(preview_response.status_code, 200)
            system_case = preview_response.json()["system_case"]
            self.assertEqual(system_case["case_name"], "csv_generated_case")
            self.assertEqual(len(system_case["time_series"]), 2)
            self.assertEqual(
                system_case["time_series"][0],
                {
                    "timestamp": "2026-01-01T00:00:00",
                    "duration_hours": 0.5,
                    "import_price_usd_per_mwh": 55.0,
                    "export_price_usd_per_mwh": 42.0,
                    "renewable_available_power_mw": {"solar_1": 3.5},
                    "load_demand_mw": {"load_1": 2.0},
                },
            )
            self.assertEqual(
                {edge["from"] for edge in system_case["edges"]},
                {"grid_1", "battery_1", "solar_1", "load_1"},
            )

            validation_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate",
            )

            self.assertEqual(validation_response.status_code, 200)
            payload = validation_response.json()
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["phase"], "julia")
            self.assertEqual(payload["validation"]["case_name"], "csv_generated_case")
            self.assertEqual(json.loads(validation_service.candidate_text), system_case)
            stored_draft = client.get(f"/api/scenarios/{scenario['id']}/draft").json()["draft"]["document"]
            stored_generated = stored_draft["generated_system_case"]
            self.assertEqual(stored_generated["system_case"], system_case)
            self.assertEqual(
                stored_generated["validation"],
                {
                    "ok": True,
                    "phase": "julia",
                    "message": "Validation succeeded",
                    "payload": {"status": "ok", "case_name": "csv_generated_case"},
                },
            )

    def test_python_mapping_errors_stop_generated_case_validation_before_julia(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_client_and_scenario(Path(temp_dir), validation_service)
            upload_bad_mapping(client, scenario["id"])

            response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate",
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn("Python time-series validation failed", response.json()["detail"])
            self.assertIn("duration_hours mapping is required", response.json()["detail"])
            self.assertEqual(validation_service.candidate_text, "")

    def test_api_surfaces_julia_validation_failure_for_generated_case(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RejectingValidationService()
            client, scenario = make_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_csv(client, scenario["id"])

            response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate",
            )

            self.assertEqual(response.status_code, 400)
            payload = response.json()
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["phase"], "julia")
            self.assertEqual(payload["message"], "Julia rejected generated case")
            self.assertEqual(payload["validation"]["status"], "error")
            self.assertNotEqual(validation_service.candidate_text, "")

    def test_draft_page_renders_readonly_preview_and_julia_validation_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RejectingValidationService()
            client, scenario = make_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_csv(client, scenario["id"])

            page = client.get(f"/scenarios/{scenario['id']}/draft")

            self.assertEqual(page.status_code, 200)
            self.assertIn('id="generated_system_case_preview" readonly', page.text)
            self.assertIn("import_price_usd_per_mwh", page.text)
            self.assertIn(
                f'action="/scenarios/{scenario["id"]}/draft/generated-system-case/validate"',
                page.text,
            )

            response = client.post(
                f"/scenarios/{scenario['id']}/draft/generated-system-case/validate",
            )

            self.assertEqual(response.status_code, 200)
            self.assertIn("Generated System Case Validation", response.text)
            self.assertIn("Invalid", response.text)
            self.assertIn("Julia rejected generated case", response.text)
            self.assertNotEqual(validation_service.candidate_text, "")

    def test_existing_paste_json_version_validation_path_still_uses_supplied_case(self):
        validation_service = RecordingValidationService()
        client = TestClient(
            create_app(
                validation_service=validation_service,
                database_url="sqlite:///:memory:",
            )
        )
        project = client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Legacy JSON path"},
        ).json()
        sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()

        response = client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": sample_text},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["case_name"], "hybrid_system")
        self.assertEqual(json.loads(validation_service.candidate_text), json.loads(sample_text))


class RecordingValidationService:
    def __init__(self):
        self.candidate_text = ""

    def validate_text(self, candidate_text):
        self.candidate_text = candidate_text
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok", "case_name": "csv_generated_case"},
        )


class RejectingValidationService:
    def __init__(self):
        self.candidate_text = ""

    def validate_text(self, candidate_text):
        self.candidate_text = candidate_text
        return ValidationResult(
            ok=False,
            phase="julia",
            message="Julia rejected generated case",
            payload={"status": "error", "message": "Julia rejected generated case"},
        )


def make_client_and_scenario(temp_root: Path, validation_service):
    client = TestClient(
        create_app(
            validation_service=validation_service,
            database_url="sqlite:///:memory:",
            input_source_root=temp_root / "input-sources",
        )
    )
    project = client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
    scenario = client.post(
        f"/api/projects/{project['id']}/scenarios",
        json={"name": "Base case"},
    ).json()
    client.post(
        f"/api/scenarios/{scenario['id']}/draft",
        json={"document": valid_draft_document()},
    )
    return client, scenario


def valid_draft_document():
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": "csv_generated_case"},
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
            {"id": "solar_1", "type": "renewable", "category": "solar"},
            {"id": "load_1", "type": "load"},
        ],
        "time_series": {"sources": []},
        "solver": {"name": "HiGHS", "options": {}},
    }


def upload_mapped_csv(client: TestClient, scenario_id: int) -> None:
    csv_text = (
        "period_start,hours,buy,sell,pv_available,site_demand\n"
        "2026-01-01T00:00:00,0.5,55.0,42.0,3.5,2.0\n"
        "2026-01-01T00:30:00,0.5,60.0,48.0,4.0,2.5\n"
    )
    upload = client.post(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
        files={"source_file": ("source.csv", csv_text, "text/csv")},
    ).json()["source"]
    mapping_response = client.put(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/{upload['id']}/mapping",
        json={
            "mapping": {
                "timestamp": "period_start",
                "duration_hours": "hours",
                "import_price_usd_per_mwh": "buy",
                "export_price_usd_per_mwh": "sell",
                "renewable_available_power_mw": {"solar_1": "pv_available"},
                "load_demand_mw": {"load_1": "site_demand"},
            }
        },
    )
    if mapping_response.status_code != 200:
        raise AssertionError(mapping_response.text)


def upload_bad_mapping(client: TestClient, scenario_id: int) -> None:
    csv_text = (
        "period_start,hours,buy,sell,pv_available,site_demand\n"
        "2026-01-01T00:00:00,0.5,55.0,42.0,3.5,2.0\n"
    )
    upload = client.post(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
        files={"source_file": ("source.csv", csv_text, "text/csv")},
    ).json()["source"]
    mapping_response = client.put(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/{upload['id']}/mapping",
        json={
            "mapping": {
                "timestamp": "period_start",
                "import_price_usd_per_mwh": "buy",
                "renewable_available_power_mw": {"solar_1": "pv_available"},
            }
        },
    )
    if mapping_response.status_code != 200:
        raise AssertionError(mapping_response.text)


if __name__ == "__main__":
    unittest.main()
