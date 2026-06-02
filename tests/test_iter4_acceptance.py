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


class Iteration4AcceptanceTests(unittest.TestCase):
    def test_structured_csv_xlsx_and_legacy_json_flows_reach_run_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            artifact_root = temp_root / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            validation_service = Iter4ValidationService()
            run_process = Iter4RunProcess()
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
                csv_run = complete_structured_flow(
                    client,
                    case_name="iter4_csv_case",
                    source_kind="csv",
                    expected_source_filename="prices.csv",
                    temp_root=temp_root,
                )
                xlsx_run = complete_structured_flow(
                    client,
                    case_name="iter4_xlsx_case",
                    source_kind="xlsx",
                    expected_source_filename="prices.xlsx",
                    temp_root=temp_root,
                )

                for completed in [csv_run, xlsx_run]:
                    results = client.get(f"/api/runs/{completed['run_id']}/results").json()["results"]
                    self.assertEqual(results["summary"]["price_mode"], "separate_import_export")
                    self.assertIn("import_cost_usd", results["dispatch_table"]["columns"])
                    self.assertIn("export_revenue_usd", results["dispatch_table"]["columns"])
                    self.assertIn("net_market_value_usd", results["dispatch_table"]["columns"])
                    self.assertEqual(
                        [series["key"] for series in results["charts"]["price"]["series"]],
                        ["import_price_usd_per_mwh", "export_price_usd_per_mwh"],
                    )
                    run_page = client.get(f"/runs/{completed['run_id']}")
                    self.assertEqual(run_page.status_code, 200)
                    self.assertIn("Basic Charts", run_page.text)
                    self.assertIn("System Dispatch", run_page.text)

                project = client.post("/api/projects", json={"name": "Legacy JSON"}).json()
                paste_scenario = client.post(
                    f"/api/projects/{project['id']}/scenarios",
                    json={"name": "Pasted legacy single-price case"},
                ).json()
                sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text(
                    encoding="utf-8"
                )
                paste_version = client.post(
                    f"/api/scenarios/{paste_scenario['id']}/versions",
                    json={"system_case_json": sample_text},
                ).json()
                legacy_run = client.post(f"/api/scenario-versions/{paste_version['id']}/runs").json()
                legacy_results = client.get(f"/api/runs/{legacy_run['id']}/results").json()["results"]
                self.assertEqual(legacy_results["summary"]["price_mode"], "single_price")
                self.assertIn("price_usd_per_mwh", legacy_results["dispatch_table"]["columns"])
                self.assertEqual(
                    [series["key"] for series in legacy_results["charts"]["price"]["series"]],
                    ["price_usd_per_mwh"],
                )

                upload_scenario = client.post(
                    f"/api/projects/{project['id']}/scenarios",
                    json={"name": "Uploaded legacy single-price case"},
                ).json()
                upload_response = client.post(
                    f"/api/scenarios/{upload_scenario['id']}/versions/upload",
                    files={"system_case_file": ("system_case.json", sample_text, "application/json")},
                )
                self.assertEqual(upload_response.status_code, 201)
                self.assertEqual(upload_response.json()["case_name"], "hybrid_system")

                self.assertGreaterEqual(validation_service.text_validation_count, 4)
                self.assertEqual(validation_service.file_validation_count, 3)
                self.assertEqual(len(run_process.completed_case_names), 3)
            finally:
                store.close()

    def test_iteration_4_documentation_and_tracker_cover_final_acceptance(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        issue = (
            REPO_ROOT
            / "docs"
            / "iter4"
            / "issues"
            / "BESS-ITER4-009-finalize-iteration-4-acceptance-suite-and-docs.md"
        ).read_text(encoding="utf-8")
        tracker = (REPO_ROOT / "docs" / "iter4" / "issues" / "tracker_iter4.md").read_text(encoding="utf-8")

        for expected in [
            "Use The Structured Draft Editor",
            "Supported Assets And One-Bus Assumptions",
            "CSV And XLSX Source Files",
            "Column Mapping Rules And Units",
            "Legacy Single Price And Separate Import/Export Prices",
            "Draft Validation, Preview, And Promotion",
            "Iteration 4 Acceptance Verification",
        ]:
            self.assertIn(expected, readme)

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_iter4_acceptance", issue)
        self.assertIn("| BESS-ITER4-009 | Finalize Iteration 4 Acceptance Suite And Docs | AFK | ready-for-agent | Done |", tracker)
        self.assertIn("Final Iteration 4 Verification", tracker)
        self.assertIn(".\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v", tracker)
        self.assertIn('julia --project=. -e "import Pkg; Pkg.test()"', tracker)


class Iter4ValidationService:
    def __init__(self):
        self.text_validation_count = 0
        self.file_validation_count = 0

    def validate_text(self, candidate_text):
        self.text_validation_count += 1
        document = json.loads(candidate_text)
        return validation_success_for(document)

    def validate_file(self, candidate_path):
        self.file_validation_count += 1
        document = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
        return validation_success_for(document)


def validation_success_for(document):
    return ValidationResult(
        ok=True,
        phase="julia",
        message="Validation succeeded",
        payload={
            "status": "ok",
            "case_name": document["case_name"],
            "schema_version": document["schema_version"],
            "period_count": len(document["time_series"]),
        },
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


class Iter4RunProcess:
    def __init__(self):
        self.completed_case_names = []

    def __call__(self, command, **kwargs):
        input_path = next(Path(item) for item in command if str(item).endswith("system_case.json"))
        output_root = Path(command[command.index("--output-root") + 1])
        system_case = json.loads(input_path.read_text(encoding="utf-8"))
        case_name = system_case["case_name"]
        self.completed_case_names.append(case_name)
        separate_prices = "import_price_usd_per_mwh" in system_case["time_series"][0]
        output_dir = output_root / case_name / f"acceptance-run-{len(self.completed_case_names)}"
        output_dir.mkdir(parents=True)
        summary_path = output_dir / "summary.json"
        price_mode = "separate_import_export" if separate_prices else "single_price"
        summary_path.write_text(
            json.dumps(
                {
                    "case_name": case_name,
                    "run_timestamp": output_dir.name,
                    "solver_name": "HiGHS",
                    "solver_status": "OPTIMAL",
                    "termination_status": "OPTIMAL",
                    "objective_value_usd": 125.0,
                    "price_mode": price_mode,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if separate_prices:
            write_separate_price_outputs(output_dir)
        else:
            write_single_price_outputs(output_dir)
        (output_dir / "model_metadata.json").write_text(
            json.dumps(
                {
                    "model_name": "one_bus_system_dispatch",
                    "schema_version": "bess_system_dispatch.v1",
                    "price_mode": price_mode,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "case_name": case_name,
                    "run_timestamp": output_dir.name,
                    "output_dir": str(output_dir),
                    "summary_path": str(summary_path),
                    "termination_status": "OPTIMAL",
                }
            ),
            stderr="",
        )


def complete_structured_flow(client, *, case_name, source_kind, expected_source_filename, temp_root):
    project = client.post("/api/projects", json={"name": f"{case_name} project"}).json()
    scenario = client.post(
        f"/api/projects/{project['id']}/scenarios",
        json={"name": f"{case_name} scenario"},
    ).json()
    client.post(
        f"/api/scenarios/{scenario['id']}/draft",
        json={"document": draft_document(case_name)},
    )
    if source_kind == "csv":
        source = upload_csv_source(client, scenario["id"])
    elif source_kind == "xlsx":
        source = upload_xlsx_source(client, scenario["id"])
    else:
        raise AssertionError(f"unknown source kind {source_kind}")
    self_mapping = {
        "timestamp": "period_start",
        "duration_hours": "hours",
        "import_price_usd_per_mwh": "buy_price",
        "export_price_usd_per_mwh": "sell_price",
        "renewable_available_power_mw": {"solar_1": "solar_mw"},
        "load_demand_mw": {"load_1": "load_mw"},
    }
    mapping_response = client.put(
        f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{source['id']}/mapping",
        json={"mapping": self_mapping},
    )
    if mapping_response.status_code != 200:
        raise AssertionError(mapping_response.text)

    preview_response = client.get(f"/api/scenarios/{scenario['id']}/draft/generated-system-case")
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()["system_case"]
    assert preview["case_name"] == case_name
    assert preview["time_series"][0]["import_price_usd_per_mwh"] == 55.0

    validation_response = client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")
    assert validation_response.status_code == 200, validation_response.text
    promote_response = client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote")
    assert promote_response.status_code == 201, promote_response.text
    version = promote_response.json()
    stored_version = client.get(f"/api/scenario-versions/{version['id']}").json()["scenario_version"]
    assert stored_version["system_case_json"] == preview
    generation_metadata = stored_version["generation_metadata"]
    assert generation_metadata["source"]["original_filename"] == expected_source_filename
    assert generation_metadata["mapping"]["import_price_usd_per_mwh"] == "buy_price"
    assert str(temp_root) not in json.dumps(generation_metadata)

    run_response = client.post(f"/api/scenario-versions/{version['id']}/runs")
    assert run_response.status_code == 201, run_response.text
    run_id = run_response.json()["id"]
    run = client.get(f"/api/runs/{run_id}").json()["run"]
    assert run["status"] == "succeeded"
    artifacts = client.get(f"/api/runs/{run_id}/artifacts").json()["artifacts"]
    artifact_types = {artifact["artifact_type"] for artifact in artifacts}
    assert artifact_types == {
        "input_snapshot",
        "stdout_log",
        "stderr_log",
        "summary_json",
        "dispatch_csv",
        "asset_dispatch_csv",
        "model_metadata_json",
    }
    summary_artifact = next(artifact for artifact in artifacts if artifact["artifact_type"] == "summary_json")
    summary_download = client.get(summary_artifact["download_url"])
    assert summary_download.status_code == 200
    return {"run_id": run_id, "version_id": version["id"]}


def draft_document(case_name):
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": case_name},
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


def upload_csv_source(client, scenario_id):
    csv_text = (
        "period_start,hours,buy_price,sell_price,solar_mw,load_mw\n"
        "2026-01-01T00:00:00,0.5,55.0,42.0,3.5,2.0\n"
        "2026-01-01T00:30:00,0.5,60.0,48.0,4.0,2.5\n"
    )
    response = client.post(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
        files={"source_file": ("prices.csv", csv_text, "text/csv")},
    )
    if response.status_code != 201:
        raise AssertionError(response.text)
    return response.json()["source"]


def upload_xlsx_source(client, scenario_id):
    response = client.post(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
        files={
            "source_file": (
                "prices.xlsx",
                make_xlsx_bytes(
                    [
                        ["period_start", "hours", "buy_price", "sell_price", "solar_mw", "load_mw"],
                        ["2026-01-01T00:00:00", 0.5, 55.0, 42.0, 3.5, 2.0],
                        ["2026-01-01T00:30:00", 0.5, 60.0, 48.0, 4.0, 2.5],
                    ]
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    if response.status_code != 201:
        raise AssertionError(response.text)
    return response.json()["source"]


def make_xlsx_bytes(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Inputs"
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def write_separate_price_outputs(output_dir):
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
        "2026-01-01T00:00:00,0.5,55.0,42.0,grid_1,grid,2.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0\n",
        encoding="utf-8",
    )


def write_single_price_outputs(output_dir):
    (output_dir / "dispatch.csv").write_text(
        "timestamp,duration_hours,price_usd_per_mwh,grid_import_mw,grid_export_mw,net_grid_export_mw,"
        "renewable_used_mw,renewable_curtailed_mw,load_demand_mw,battery_charge_mw,battery_discharge_mw,"
        "battery_net_discharge_mw,battery_energy_mwh,battery_delta_soc_abs_mwh,market_value_usd,"
        "battery_degradation_cost_usd,curtailment_penalty_usd,period_profit_usd\n"
        "2026-01-01T00:00:00,1.0,45.0,2.5,0.0,-2.5,4.0,0.0,6.5,0.0,0.0,0.0,20.0,0.0,-112.5,0.0,0.0,-112.5\n",
        encoding="utf-8",
    )
    (output_dir / "asset_dispatch.csv").write_text(
        "timestamp,duration_hours,price_usd_per_mwh,asset_id,asset_type,grid_import_mw,grid_export_mw,"
        "renewable_used_mw,renewable_curtailed_mw,load_demand_mw,battery_charge_mw,battery_discharge_mw,"
        "battery_energy_mwh,battery_delta_soc_abs_mwh\n"
        "2026-01-01T00:00:00,1.0,45.0,grid_1,grid,2.5,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
