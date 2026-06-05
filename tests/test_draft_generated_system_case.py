import json
import subprocess
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import create_app
from app.persistence import AnalystStore
from app.runner import JuliaRunExecutor
from app.validation import ValidationResult


REPO_ROOT = Path(__file__).resolve().parents[1]


class DraftGeneratedSystemCaseTests(unittest.TestCase):
    def test_validated_draft_promotes_to_version_and_runs_through_existing_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            artifact_root = temp_root / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            validation_service = DraftPromotionValidationService()
            run_process = DraftPromotionRunProcess()
            executor = JuliaRunExecutor(
                store=store,
                repo_root=REPO_ROOT,
                artifact_root=artifact_root,
                julia_executable="julia",
                runner=run_process,
                validation_service=validation_service,
            )
            client = TestClient(
                create_app(
                    validation_service=validation_service,
                    store=store,
                    run_queue=SynchronousRunQueue(executor),
                    artifact_root=artifact_root,
                    input_source_root=temp_root / "input-sources",
                )
            )
            try:
                project = client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
                scenario = client.post(
                    f"/api/projects/{project['id']}/scenarios",
                    json={"name": "Structured case"},
                ).json()
                client.post(
                    f"/api/scenarios/{scenario['id']}/draft",
                    json={"document": valid_draft_document()},
                )
                upload_mapped_csv(client, scenario["id"])

                validation_response = client.post(
                    f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate",
                )
                self.assertEqual(validation_response.status_code, 200)
                generated_case = validation_response.json()["system_case"]

                promote_response = client.post(
                    f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote",
                )

                self.assertEqual(promote_response.status_code, 201)
                version = promote_response.json()
                self.assertEqual(version["version_number"], 1)
                self.assertEqual(version["case_name"], "csv_generated_case")
                stored_version = client.get(f"/api/scenario-versions/{version['id']}").json()[
                    "scenario_version"
                ]
                self.assertEqual(stored_version["system_case_json"], generated_case)
                self.assertEqual(json.loads(validation_service.text_candidates[-1]), generated_case)
                generation_metadata = stored_version["generation_metadata"]
                self.assertEqual(generation_metadata["kind"], "structured_draft")
                self.assertEqual(generation_metadata["source"]["original_filename"], "source.csv")
                self.assertEqual(generation_metadata["source"]["media_type"], "text/csv")
                self.assertEqual(generation_metadata["mapping"]["duration_hours"], "hours")
                self.assertIn("generated_at", generation_metadata)
                self.assertNotIn("stored_path", generation_metadata["source"])
                self.assertNotIn(str(temp_root), json.dumps(generation_metadata))

                draft_document = client.get(f"/api/scenarios/{scenario['id']}/draft").json()["draft"]["document"]
                draft_document["case"]["name"] = "still_editable_after_promotion"
                edit_response = client.put(
                    f"/api/scenarios/{scenario['id']}/draft",
                    json={"document": draft_document},
                )
                self.assertEqual(edit_response.status_code, 200)
                stored_version_after_edit = client.get(f"/api/scenario-versions/{version['id']}").json()[
                    "scenario_version"
                ]
                self.assertEqual(stored_version_after_edit["system_case_json"], generated_case)

                run_response = client.post(f"/api/scenario-versions/{version['id']}/runs")
                self.assertEqual(run_response.status_code, 201)
                run = client.get(f"/api/runs/{run_response.json()['id']}").json()["run"]
                self.assertEqual(run["status"], "succeeded")
                self.assertEqual(validation_service.file_validation_count, 1)
                self.assertTrue(run_process.completed_commands)

                artifacts = client.get(f"/api/runs/{run['id']}/artifacts").json()["artifacts"]
                artifact_types = {artifact["artifact_type"] for artifact in artifacts}
                self.assertEqual(
                    artifact_types,
                    {
                        "input_snapshot",
                        "stdout_log",
                        "stderr_log",
                        "summary_json",
                        "dispatch_csv",
                        "asset_dispatch_csv",
                        "model_metadata_json",
                    },
                )
                results_response = client.get(f"/api/runs/{run['id']}/results")
                self.assertEqual(results_response.status_code, 200)
                self.assertEqual(results_response.json()["results"]["summary"]["case_name"], "csv_generated_case")

                run_page = client.get(f"/runs/{run['id']}")
                self.assertEqual(run_page.status_code, 200)
                self.assertIn("Run Summary", run_page.text)
                self.assertIn("Basic Charts", run_page.text)
                self.assertIn("System Dispatch", run_page.text)
            finally:
                store.close()

    def test_draft_page_promotes_only_after_successful_generated_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_csv(client, scenario["id"])

            unvalidated_page = client.get(f"/scenarios/{scenario['id']}/draft")
            self.assertEqual(unvalidated_page.status_code, 200)
            self.assertNotIn("Promote To Scenario Version", unvalidated_page.text)

            blocked_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote",
            )
            self.assertEqual(blocked_response.status_code, 400)
            self.assertIn("must be validated before promotion", blocked_response.json()["detail"])

            validation_page = client.post(
                f"/scenarios/{scenario['id']}/draft/generated-system-case/validate",
            )
            self.assertEqual(validation_page.status_code, 200)
            self.assertIn("Valid: Validation succeeded", validation_page.text)
            self.assertIn("Promote To Scenario Version", validation_page.text)
            self.assertIn(
                f'action="/scenarios/{scenario["id"]}/draft/generated-system-case/promote"',
                validation_page.text,
            )

            promote_response = client.post(
                f"/scenarios/{scenario['id']}/draft/generated-system-case/promote",
                follow_redirects=False,
            )
            self.assertEqual(promote_response.status_code, 303)
            self.assertRegex(promote_response.headers["location"], rf"^/scenarios/{scenario['id']}#version-\d+$")

            scenario_page = client.get(f"/scenarios/{scenario['id']}")
            self.assertEqual(scenario_page.status_code, 200)
            self.assertIn("Version 1", scenario_page.text)
            self.assertIn("csv_generated_case", scenario_page.text)
            self.assertIn("Launch Run", scenario_page.text)

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

    def test_api_generates_and_validates_system_case_from_xlsx_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_xlsx(client, scenario["id"])

            preview_response = client.get(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case",
            )

            self.assertEqual(preview_response.status_code, 200)
            system_case = preview_response.json()["system_case"]
            self.assertEqual(system_case["case_name"], "csv_generated_case")
            self.assertEqual(len(system_case["time_series"]), 2)
            self.assertEqual(system_case["time_series"][0]["import_price_usd_per_mwh"], 55.0)
            self.assertEqual(system_case["time_series"][0]["renewable_available_power_mw"], {"solar_1": 3.5})

            validation_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate",
            )

            self.assertEqual(validation_response.status_code, 200)
            self.assertEqual(validation_response.json()["status"], "ok")
            self.assertEqual(json.loads(validation_service.candidate_text), system_case)

    def test_api_generates_v2_periods_with_hydro_inflow_from_csv_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_hydro_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_hydro_csv(client, scenario["id"])

            preview_response = client.get(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case",
            )

            self.assertEqual(preview_response.status_code, 200)
            system_case = preview_response.json()["system_case"]
            self.assertEqual(system_case["schema_version"], "bess_system_dispatch.v2")
            self.assertEqual(
                system_case["time_series"][0],
                {
                    "timestamp": "2026-01-01T00:00:00",
                    "duration_hours": 1.0,
                    "import_price_usd_per_mwh": 55.0,
                    "export_price_usd_per_mwh": 45.0,
                    "renewable_available_power_mw": {},
                    "load_demand_mw": {},
                    "hydro_inflow_m3s": {"hydro_1": 25.0},
                },
            )

    def test_promoted_hydro_generated_version_retains_hydro_mapping_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            validation_service = RecordingValidationService()
            client, scenario = make_hydro_client_and_scenario(temp_root, validation_service)
            upload_mapped_hydro_csv(client, scenario["id"])

            validation_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate",
            )
            self.assertEqual(validation_response.status_code, 200)
            promote_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote",
            )

            self.assertEqual(promote_response.status_code, 201)
            version = promote_response.json()
            stored_version = client.get(f"/api/scenario-versions/{version['id']}").json()[
                "scenario_version"
            ]
            generation_metadata = stored_version["generation_metadata"]
            self.assertEqual(
                generation_metadata["mapping"]["hydro_inflow_m3s"],
                {"hydro_1": "hydro_inflow_m3s"},
            )
            self.assertEqual(generation_metadata["source"]["original_filename"], "source.csv")
            self.assertNotIn("stored_path", generation_metadata["source"])
            self.assertNotIn(str(temp_root), json.dumps(generation_metadata))

    def test_python_mapping_errors_stop_generated_case_validation_before_julia(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_client_and_scenario(Path(temp_dir), validation_service)
            upload_bad_mapping(client, scenario["id"])

            response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate",
            )

            self.assertEqual(response.status_code, 400)
            payload = response.json()
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["phase"], "python_validation")
            self.assertEqual(payload["error_category"], "mapping")
            self.assertIn("Python time-series validation failed", payload["detail"])
            self.assertIn("duration_hours mapping is required", payload["detail"])
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
            self.assertEqual(payload["error_category"], "julia_validation")
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


class DraftPromotionValidationService:
    def __init__(self):
        self.text_candidates = []
        self.file_validation_count = 0

    def validate_text(self, candidate_text):
        self.text_candidates.append(candidate_text)
        document = json.loads(candidate_text)
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={
                "status": "ok",
                "case_name": document["case_name"],
                "schema_version": document["schema_version"],
            },
            exit_code=0,
            raw_stdout='{"status":"ok"}\n',
            raw_stderr="",
        )

    def validate_file(self, candidate_path):
        self.file_validation_count += 1
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
            exit_code=0,
            raw_stdout='{"status":"ok"}\n',
            raw_stderr="",
        )


class SynchronousRunQueue:
    def __init__(self, executor):
        self.executor = executor

    def enqueue(self, run_id):
        self.executor.execute(run_id)

    def stop(self):
        pass


class DraftPromotionRunProcess:
    def __init__(self):
        self.completed_commands = []

    def __call__(self, command, **kwargs):
        self.completed_commands.append((command, kwargs))
        output_root = Path(command[command.index("--output-root") + 1])
        output_dir = output_root / "csv_generated_case" / "draft-promotion-run"
        output_dir.mkdir(parents=True)
        summary_path = output_dir / "summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "case_name": "csv_generated_case",
                    "solver_name": "HiGHS",
                    "solver_status": "OPTIMAL",
                    "termination_status": "OPTIMAL",
                    "objective_value_usd": 10.0,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (output_dir / "dispatch.csv").write_text(
            "timestamp,duration_hours,import_price_usd_per_mwh,export_price_usd_per_mwh,"
            "grid_import_mw,grid_export_mw,net_grid_export_mw,renewable_used_mw,renewable_curtailed_mw,"
            "load_demand_mw,battery_charge_mw,battery_discharge_mw,battery_net_discharge_mw,"
            "battery_energy_mwh,battery_delta_soc_abs_mwh,import_cost_usd,export_revenue_usd,"
            "net_market_value_usd,market_value_usd,battery_degradation_cost_usd,curtailment_penalty_usd,"
            "period_profit_usd\n"
            "2026-01-01T00:00:00,0.5,55.0,42.0,2.0,0.0,-2.0,3.5,0.0,2.0,"
            "1.5,0.0,-1.5,5.425,1.425,55.0,0.0,-55.0,-55.0,0.0,0.0,-55.0\n",
            encoding="utf-8",
        )
        (output_dir / "asset_dispatch.csv").write_text(
            "timestamp,duration_hours,import_price_usd_per_mwh,export_price_usd_per_mwh,"
            "asset_id,asset_type,grid_import_mw,grid_export_mw,renewable_used_mw,renewable_curtailed_mw,"
            "load_demand_mw,battery_charge_mw,battery_discharge_mw,battery_energy_mwh,"
            "battery_delta_soc_abs_mwh\n"
            "2026-01-01T00:00:00,0.5,55.0,42.0,grid_1,grid,2.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0\n"
            "2026-01-01T00:00:00,0.5,55.0,42.0,solar_1,renewable,0.0,0.0,3.5,0.0,0.0,0.0,0.0,0.0,0.0\n"
            "2026-01-01T00:00:00,0.5,55.0,42.0,battery_1,battery,0.0,0.0,0.0,0.0,0.0,1.5,0.0,5.425,1.425\n",
            encoding="utf-8",
        )
        (output_dir / "model_metadata.json").write_text(
            json.dumps({"model_name": "one_bus_system_dispatch"}) + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "case_name": "csv_generated_case",
                    "run_timestamp": "draft-promotion-run",
                    "output_dir": str(output_dir),
                    "summary_path": str(summary_path),
                    "termination_status": "OPTIMAL",
                }
            ),
            stderr="",
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


def make_hydro_client_and_scenario(temp_root: Path, validation_service):
    client = TestClient(
        create_app(
            validation_service=validation_service,
            database_url="sqlite:///:memory:",
            input_source_root=temp_root / "input-sources",
        )
    )
    project = client.post("/api/projects", json={"name": "Hydro PMGD"}).json()
    scenario = client.post(
        f"/api/projects/{project['id']}/scenarios",
        json={"name": "Hydro base"},
    ).json()
    client.post(
        f"/api/scenarios/{scenario['id']}/draft",
        json={"document": valid_hydro_draft_document()},
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


def valid_hydro_draft_document():
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": "hydro_generated_case"},
        "pcc": {"id": "bus_1", "type": "bus"},
        "grid": {
            "id": "grid_1",
            "import_power_max_mw": 20.0,
            "export_power_max_mw": 20.0,
            "prevent_simultaneous_grid_import_export": True,
        },
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
                "power_max_mw": 3.0,
                "minimum_release_m3s": 0.0,
                "spill_penalty_usd_per_hm3": 100.0,
                "terminal_condition": "min_terminal",
                "terminal_storage_min_hm3": 2.0,
                "terminal_water_value_usd_per_hm3": 500.0,
                "reservoir_curve": [
                    {"storage_hm3": 1.0, "elevation_masl": 700.0},
                    {"storage_hm3": 3.0, "elevation_masl": 710.0},
                    {"storage_hm3": 5.0, "elevation_masl": 720.0},
                ],
            }
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


def upload_mapped_hydro_csv(client: TestClient, scenario_id: int) -> None:
    csv_text = (
        "period_start,hours,buy_price,sell_price,hydro_inflow_m3s\n"
        "2026-01-01T00:00:00,1.0,55.0,45.0,25.0\n"
        "2026-01-01T01:00:00,1.0,60.0,80.0,30.0\n"
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
                "import_price_usd_per_mwh": "buy_price",
                "export_price_usd_per_mwh": "sell_price",
                "hydro_inflow_m3s": {"hydro_1": "hydro_inflow_m3s"},
            }
        },
    )
    if mapping_response.status_code != 200:
        raise AssertionError(mapping_response.text)


def upload_mapped_xlsx(client: TestClient, scenario_id: int) -> None:
    upload = client.post(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
        files={
            "source_file": (
                "source.xlsx",
                make_xlsx_bytes(
                    [
                        ["period_start", "hours", "buy", "sell", "pv_available", "site_demand"],
                        ["2026-01-01T00:00:00", 0.5, 55.0, 42.0, 3.5, 2.0],
                        ["2026-01-01T00:30:00", 0.5, 60.0, 48.0, 4.0, 2.5],
                    ]
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
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


def make_xlsx_bytes(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Inputs"
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
