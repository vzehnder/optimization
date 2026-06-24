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


class Iteration5AcceptanceTests(unittest.TestCase):
    def test_final_hydro_acceptance_covers_linear_v1_v2_no_hydro_and_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            artifact_root = temp_root / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            validation_service = Iter5ValidationService()
            run_process = Iter5RunProcess()
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
                linear = complete_linear_hydro_flow(client, temp_root=temp_root)
                linear_results = client.get(f"/api/runs/{linear['run_id']}/results").json()["results"]
                self.assertEqual(linear_results["summary"]["schema_version"], "bess_system_dispatch.v2")
                self.assertEqual(
                    linear_results["summary"]["hydro_kpis_by_asset"]["hydro_lin_1"]["generation_mode"],
                    "linear",
                )
                self.assertIn("total_hydro_turbine_flow_m3s", linear_results["dispatch_table"]["columns"])
                self.assertTrue(linear_results["charts"]["hydro_power"]["available"])

                no_hydro = complete_no_hydro_v2_structured_flow(client, temp_root=temp_root)
                no_hydro_results = client.get(f"/api/runs/{no_hydro['run_id']}/results").json()["results"]
                self.assertEqual(no_hydro_results["summary"]["schema_version"], "bess_system_dispatch.v2")
                self.assertNotIn("hydro_totals", no_hydro_results["summary"])
                self.assertEqual(
                    [series["key"] for series in no_hydro_results["charts"]["price"]["series"]],
                    ["import_price_usd_per_mwh", "export_price_usd_per_mwh"],
                )
                self.assertFalse(no_hydro_results["charts"]["hydro_power"]["available"])

                legacy = complete_v1_paste_and_upload_flow(client)
                legacy_results = client.get(f"/api/runs/{legacy['run_id']}/results").json()["results"]
                self.assertEqual(legacy_results["summary"]["schema_version"], "bess_system_dispatch.v1")
                self.assertEqual(legacy_results["summary"]["price_mode"], "single_price")
                self.assertEqual(
                    [series["key"] for series in legacy_results["charts"]["price"]["series"]],
                    ["price_usd_per_mwh"],
                )

                error_scenario_id = create_linear_hydro_scenario(client, case_name="iter5_bad_hydro_inflow")
                bad_source = upload_linear_hydro_csv_source(client, error_scenario_id, inflow="-1.0")
                mapping_response = save_linear_hydro_mapping(client, error_scenario_id, bad_source["id"])
                self.assertEqual(mapping_response.status_code, 200)
                validation = mapping_response.json()["source"]["validation"]
                self.assertEqual(validation["error_category"], "python_validation")
                self.assertIn("hydro hydro_lin_1 inflow must be nonnegative", json.dumps(validation["errors"]))

                validation_response = client.post(
                    f"/api/scenarios/{error_scenario_id}/draft/generated-system-case/validate",
                )
                self.assertEqual(validation_response.status_code, 400)
                self.assertEqual(validation_response.json()["error_category"], "python_validation")
                self.assertIn("hydro hydro_lin_1 inflow must be nonnegative", validation_response.text)

                self.assertEqual(
                    run_process.completed_case_names,
                    ["iter5_linear_hydro_case", "iter5_no_hydro_v2_case", "hybrid_system"],
                )
            finally:
                store.close()

    def legacy_removed_piecewise_hydro_csv_xlsx_and_invalid_breakpoints_from_editor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            artifact_root = temp_root / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            validation_service = Iter5ValidationService()
            run_process = Iter5RunProcess()
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
                csv_completed = complete_piecewise_hydro_flow(
                    client,
                    case_name="iter5_piecewise_csv_case",
                    source_kind="csv",
                    expected_source_filename="piecewise_hydro.csv",
                    save_mode="ui",
                    temp_root=temp_root,
                )
                xlsx_completed = complete_piecewise_hydro_flow(
                    client,
                    case_name="iter5_piecewise_xlsx_case",
                    source_kind="xlsx",
                    expected_source_filename="piecewise_hydro.xlsx",
                    save_mode="api",
                    temp_root=temp_root,
                )

                for completed in [csv_completed, xlsx_completed]:
                    results = client.get(f"/api/runs/{completed['run_id']}/results").json()["results"]
                    self.assertEqual(results["summary"]["schema_version"], "bess_system_dispatch.v2")
                    self.assertEqual(
                        results["summary"]["hydro_kpis_by_asset"]["hydro_pw_1"]["generation_mode"],
                        "piecewise_linear",
                    )
                    self.assertIn("total_hydro_power_mw", results["dispatch_table"]["columns"])
                    self.assertIn("hydro_reservoir_elevation_masl", results["asset_dispatch_table"]["columns"])
                    self.assertEqual(results["asset_dispatch_table"]["rows"][0]["asset_type"], "hydro")
                    self.assertTrue(results["charts"]["hydro_power"]["available"])
                    self.assertTrue(results["charts"]["hydro_flows"]["available"])
                    self.assertTrue(results["charts"]["hydro_storage"]["available"])
                    self.assertTrue(results["charts"]["hydro_reservoir_elevation"]["available"])

                    run_page = client.get(f"/runs/{completed['run_id']}")
                    self.assertEqual(run_page.status_code, 200)
                    self.assertIn('id="plot-builder"', run_page.text)
                    self.assertIn("hydro_reservoir_elevation_masl", run_page.text)

                invalid_scenario_id = create_piecewise_scenario(
                    client,
                    case_name="iter5_invalid_piecewise_case",
                    save_mode="api",
                    generation_curve=[
                        {"flow_m3s": 0.0, "power_mw": 0.0},
                        {"flow_m3s": 15.0, "power_mw": 1.8},
                        {"flow_m3s": 15.0, "power_mw": 2.4},
                    ],
                )
                invalid_response = client.post(
                    f"/api/scenarios/{invalid_scenario_id}/draft/generated-system-case/validate",
                )
                self.assertEqual(invalid_response.status_code, 400)
                self.assertEqual(invalid_response.json()["error_category"], "julia_validation")
                self.assertIn("generation_curve flow_m3s must be strictly increasing", invalid_response.text)

                blocked_promote = client.post(
                    f"/api/scenarios/{invalid_scenario_id}/draft/generated-system-case/promote",
                )
                self.assertEqual(blocked_promote.status_code, 400)
                self.assertIn("validation must succeed before promotion", blocked_promote.text)

                self.assertEqual(validation_service.file_validation_count, 2)
                self.assertEqual(run_process.completed_case_names, ["iter5_piecewise_csv_case", "iter5_piecewise_xlsx_case"])
            finally:
                store.close()

    def test_iteration_5_issue_008_documentation_and_tracker_are_done(self):
        issue = (
            REPO_ROOT
            / "docs"
            / "iter5"
            / "issues"
            / "BESS-ITER5-008-prove-piecewise-hydro-from-editor-end-to-end.md"
        ).read_text(encoding="utf-8")
        tracker = (REPO_ROOT / "docs" / "iter5" / "issues" / "tracker_iter5.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_iter5_acceptance", issue)
        self.assertIn(
            "| BESS-ITER5-008 | Prove Piecewise Hydro From Editor End To End | AFK | ready-for-agent | Done |",
            tracker,
        )
        self.assertIn("BESS-ITER5-008 | Todo -> Done", tracker)
        self.assertIn("piecewise hydro", readme.lower())
        self.assertIn("data/cases/piecewise_hydro_system/system_case.json", readme)

    def test_iteration_5_issue_009_documentation_and_tracker_are_done(self):
        issue = (
            REPO_ROOT
            / "docs"
            / "iter5"
            / "issues"
            / "BESS-ITER5-009-finalize-iteration-5-acceptance-suite-and-docs.md"
        ).read_text(encoding="utf-8")
        tracker = (REPO_ROOT / "docs" / "iter5" / "issues" / "tracker_iter5.md").read_text(encoding="utf-8")
        manual = (REPO_ROOT / "docs" / "iter5" / "pruebas_manuales_iteracion5.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        for expected in [
            "Simple Reservoir Hydro Scope",
            "Hydro Units And Flow Conversion",
            "Hydro Generation Modes",
            "Reservoir Curves And Water Economics",
            "Hydro Structured Editor And Inflow Mapping",
            "Hydro Results And Artifacts",
            "Iteration 5 Acceptance Verification",
        ]:
            self.assertIn(expected, readme)

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_iter5_acceptance", issue)
        self.assertIn("| BESS-ITER5-009 | Finalize Iteration 5 Acceptance Suite And Docs | AFK | ready-for-agent | Done |", tracker)
        self.assertIn("BESS-ITER5-009 | Todo -> Done", tracker)
        self.assertIn("Final Iteration 5 Verification", tracker)
        self.assertIn("Cierre Iteracion 5", manual)
        self.assertIn("linear hydro", manual.lower())
        self.assertIn("piecewise hydro", manual.lower())


class Iter5ValidationService:
    def __init__(self):
        self.text_validation_count = 0
        self.file_validation_count = 0

    def validate_text(self, candidate_text):
        self.text_validation_count += 1
        document = json.loads(candidate_text)
        for node in document.get("nodes", []):
            if not isinstance(node, dict) or node.get("type") != "hydro":
                continue
            if node.get("generation_mode") != "piecewise_linear":
                continue
            curve = node.get("generation_curve")
            previous_flow = None
            for point in curve or []:
                flow = float(point["flow_m3s"])
                if previous_flow is not None and flow <= previous_flow:
                    return ValidationResult(
                        ok=False,
                        phase="julia",
                        message=f"hydro {node['id']} generation_curve flow_m3s must be strictly increasing",
                        payload={
                            "status": "error",
                            "message": f"hydro {node['id']} generation_curve flow_m3s must be strictly increasing",
                        },
                        exit_code=7,
                        raw_stdout="",
                        raw_stderr='{"status":"error"}\n',
                    )
                previous_flow = flow
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


class Iter5RunProcess:
    def __init__(self):
        self.completed_case_names = []

    def __call__(self, command, **kwargs):
        input_path = next(Path(item) for item in command if str(item).endswith("system_case.json"))
        output_root = Path(command[command.index("--output-root") + 1])
        system_case = json.loads(input_path.read_text(encoding="utf-8"))
        case_name = system_case["case_name"]
        self.completed_case_names.append(case_name)
        output_dir = output_root / case_name / f"piecewise-run-{len(self.completed_case_names)}"
        output_dir.mkdir(parents=True)
        summary_path = output_dir / "summary.json"
        hydro_nodes = [node for node in system_case["nodes"] if node.get("type") == "hydro"]
        if hydro_nodes:
            hydro = hydro_nodes[0]
            hydro_id = hydro["id"]
            generation_mode = hydro.get("generation_mode", "linear")
            summary = {
                "case_name": case_name,
                "schema_version": system_case["schema_version"],
                "run_timestamp": output_dir.name,
                "solver_name": "HiGHS",
                "solver_status": "OPTIMAL",
                "termination_status": "OPTIMAL",
                "objective_value_usd": 350.0,
                "hydro_totals": {
                    "total_hydro_generation_mwh": 6.2,
                    "total_turbine_volume_hm3": 0.19,
                    "total_spill_volume_hm3": 0.01,
                    "total_spill_penalty_usd": 1.0,
                    "terminal_water_value_usd": 0.0,
                },
                "hydro_kpis_by_asset": {
                    hydro_id: {
                        "generation_mode": generation_mode,
                        "total_hydro_generation_mwh": 6.2,
                        "total_turbine_volume_hm3": 0.19,
                        "total_spill_volume_hm3": 0.01,
                        "initial_storage_hm3": 2.5,
                        "final_storage_hm3": 3.1,
                        "initial_reservoir_elevation_masl": 707.5,
                        "final_reservoir_elevation_masl": 711.0,
                        "total_spill_penalty_usd": 1.0,
                        "terminal_water_value_usd": 0.0,
                    }
                },
            }
            summary_path.write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")
            write_hydro_outputs(output_dir, hydro_id=hydro_id, generation_mode=generation_mode)
        else:
            separate_prices = "import_price_usd_per_mwh" in system_case["time_series"][0]
            price_mode = "separate_import_export" if separate_prices else "single_price"
            summary_path.write_text(
                json.dumps(
                    {
                        "case_name": case_name,
                        "schema_version": system_case["schema_version"],
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
            write_non_hydro_outputs(output_dir, separate_prices=separate_prices)
        (output_dir / "system_case_resolved.json").write_text(
            json.dumps(system_case, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        metadata = {
            "model_name": "one_bus_system_dispatch",
            "schema_version": system_case["schema_version"],
        }
        if hydro_nodes:
            metadata.update(
                {
                    "hydro_generation_modes": {
                        hydro_nodes[0]["id"]: hydro_nodes[0].get("generation_mode", "linear"),
                    },
                    "piecewise_linear_library": "PiecewiseLinearOpt",
                }
            )
        (output_dir / "model_metadata.json").write_text(
            json.dumps(metadata, sort_keys=True) + "\n",
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


def complete_piecewise_hydro_flow(
    client,
    *,
    case_name,
    source_kind,
    expected_source_filename,
    save_mode,
    temp_root,
):
    scenario_id = create_piecewise_scenario(client, case_name=case_name, save_mode=save_mode)
    if source_kind == "csv":
        source = upload_piecewise_csv_source(client, scenario_id)
    elif source_kind == "xlsx":
        source = upload_piecewise_xlsx_source(client, scenario_id)
    else:
        raise AssertionError(f"unknown source kind {source_kind}")

    mapping = {
        "timestamp": "period_start",
        "duration_hours": "hours",
        "import_price_usd_per_mwh": "buy_price",
        "export_price_usd_per_mwh": "sell_price",
        "hydro_inflow_m3s": {"hydro_pw_1": "hydro_inflow_m3s"},
    }
    mapping_response = client.put(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/{source['id']}/mapping",
        json={"mapping": mapping},
    )
    if mapping_response.status_code != 200:
        raise AssertionError(mapping_response.text)

    preview_response = client.get(f"/api/scenarios/{scenario_id}/draft/generated-system-case")
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()["system_case"]
    hydro = next(node for node in preview["nodes"] if node["type"] == "hydro")
    assert preview["schema_version"] == "bess_system_dispatch.v2"
    assert hydro["generation_mode"] == "piecewise_linear"
    assert hydro["generation_curve"] == default_piecewise_generation_curve()
    assert hydro["generation_curve"][-1]["power_mw"] < hydro["generation_curve"][-2]["power_mw"]
    assert preview["time_series"][0]["hydro_inflow_m3s"] == {"hydro_pw_1": 30.0}

    validation_response = client.post(f"/api/scenarios/{scenario_id}/draft/generated-system-case/validate")
    assert validation_response.status_code == 200, validation_response.text
    promote_response = client.post(f"/api/scenarios/{scenario_id}/draft/generated-system-case/promote")
    assert promote_response.status_code == 201, promote_response.text
    version = promote_response.json()
    stored_version = client.get(f"/api/scenario-versions/{version['id']}").json()["scenario_version"]
    assert stored_version["system_case_json"] == preview
    generation_metadata = stored_version["generation_metadata"]
    assert generation_metadata["source"]["original_filename"] == expected_source_filename
    assert generation_metadata["mapping"]["hydro_inflow_m3s"] == {"hydro_pw_1": "hydro_inflow_m3s"}
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
        "system_case_resolved_json",
        "model_metadata_json",
    }
    return {"run_id": run_id, "version_id": version["id"]}


def complete_linear_hydro_flow(client, *, temp_root):
    scenario_id = create_linear_hydro_scenario(client, case_name="iter5_linear_hydro_case")
    source = upload_linear_hydro_csv_source(client, scenario_id)
    mapping_response = save_linear_hydro_mapping(client, scenario_id, source["id"])
    assert mapping_response.status_code == 200, mapping_response.text

    preview_response = client.get(f"/api/scenarios/{scenario_id}/draft/generated-system-case")
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()["system_case"]
    hydro = next(node for node in preview["nodes"] if node["type"] == "hydro")
    assert preview["schema_version"] == "bess_system_dispatch.v2"
    assert hydro["generation_mode"] == "linear"
    assert hydro["power_per_flow_mw_per_m3s"] == 0.08
    assert preview["time_series"][0]["hydro_inflow_m3s"] == {"hydro_lin_1": 25.0}

    validation_response = client.post(f"/api/scenarios/{scenario_id}/draft/generated-system-case/validate")
    assert validation_response.status_code == 200, validation_response.text
    promote_response = client.post(f"/api/scenarios/{scenario_id}/draft/generated-system-case/promote")
    assert promote_response.status_code == 201, promote_response.text
    version = promote_response.json()
    stored_version = client.get(f"/api/scenario-versions/{version['id']}").json()["scenario_version"]
    assert stored_version["system_case_json"] == preview
    assert stored_version["generation_metadata"]["mapping"]["hydro_inflow_m3s"] == {
        "hydro_lin_1": "hydro_inflow_m3s"
    }
    assert str(temp_root) not in json.dumps(stored_version["generation_metadata"])

    run_response = client.post(f"/api/scenario-versions/{version['id']}/runs")
    assert run_response.status_code == 201, run_response.text
    run_id = run_response.json()["id"]
    run = client.get(f"/api/runs/{run_id}").json()["run"]
    assert run["status"] == "succeeded"
    artifacts = client.get(f"/api/runs/{run_id}/artifacts").json()["artifacts"]
    assert "system_case_resolved_json" in {artifact["artifact_type"] for artifact in artifacts}
    return {"run_id": run_id, "version_id": version["id"]}


def complete_no_hydro_v2_structured_flow(client, *, temp_root):
    project = client.post("/api/projects", json={"name": "iter5 no hydro project"}).json()
    scenario = client.post(
        f"/api/projects/{project['id']}/scenarios",
        json={"name": "v2 structured case without hydro"},
    ).json()
    draft_response = client.post(
        f"/api/scenarios/{scenario['id']}/draft",
        json={"document": no_hydro_draft_document("iter5_no_hydro_v2_case")},
    )
    assert draft_response.status_code == 201, draft_response.text
    source = upload_no_hydro_csv_source(client, scenario["id"])
    mapping = {
        "timestamp": "period_start",
        "duration_hours": "hours",
        "import_price_usd_per_mwh": "buy_price",
        "export_price_usd_per_mwh": "sell_price",
        "renewable_available_power_mw": {"solar_1": "solar_mw"},
        "load_demand_mw": {"load_1": "load_mw"},
    }
    mapping_response = client.put(
        f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{source['id']}/mapping",
        json={"mapping": mapping},
    )
    assert mapping_response.status_code == 200, mapping_response.text
    preview_response = client.get(f"/api/scenarios/{scenario['id']}/draft/generated-system-case")
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()["system_case"]
    assert preview["schema_version"] == "bess_system_dispatch.v2"
    assert not [node for node in preview["nodes"] if node["type"] == "hydro"]

    validation_response = client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")
    assert validation_response.status_code == 200, validation_response.text
    promote_response = client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote")
    assert promote_response.status_code == 201, promote_response.text
    version = promote_response.json()
    stored_version = client.get(f"/api/scenario-versions/{version['id']}").json()["scenario_version"]
    assert stored_version["system_case_json"] == preview
    assert str(temp_root) not in json.dumps(stored_version["generation_metadata"])

    run_response = client.post(f"/api/scenario-versions/{version['id']}/runs")
    assert run_response.status_code == 201, run_response.text
    run_id = run_response.json()["id"]
    run = client.get(f"/api/runs/{run_id}").json()["run"]
    assert run["status"] == "succeeded"
    return {"run_id": run_id, "version_id": version["id"]}


def complete_v1_paste_and_upload_flow(client):
    project = client.post("/api/projects", json={"name": "iter5 legacy project"}).json()
    sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text(
        encoding="utf-8"
    )
    paste_scenario = client.post(
        f"/api/projects/{project['id']}/scenarios",
        json={"name": "Paste v1"},
    ).json()
    paste_version_response = client.post(
        f"/api/scenarios/{paste_scenario['id']}/versions",
        json={"system_case_json": sample_text},
    )
    assert paste_version_response.status_code == 201, paste_version_response.text
    paste_version = paste_version_response.json()
    run_response = client.post(f"/api/scenario-versions/{paste_version['id']}/runs")
    assert run_response.status_code == 201, run_response.text

    upload_scenario = client.post(
        f"/api/projects/{project['id']}/scenarios",
        json={"name": "Upload v1"},
    ).json()
    upload_response = client.post(
        f"/api/scenarios/{upload_scenario['id']}/versions/upload",
        files={"system_case_file": ("system_case.json", sample_text, "application/json")},
    )
    assert upload_response.status_code == 201, upload_response.text
    assert upload_response.json()["schema_version"] == "bess_system_dispatch.v1"
    return {"run_id": run_response.json()["id"], "version_id": paste_version["id"]}


def create_piecewise_scenario(client, *, case_name, save_mode, generation_curve=None):
    project = client.post("/api/projects", json={"name": f"{case_name} project"}).json()
    scenario = client.post(
        f"/api/projects/{project['id']}/scenarios",
        json={"name": f"{case_name} scenario"},
    ).json()
    document = piecewise_hydro_draft_document(
        case_name,
        generation_curve=generation_curve or default_piecewise_generation_curve(),
    )
    if save_mode == "ui":
        add_hydro = client.post(
            f"/scenarios/{scenario['id']}/draft/assets",
            data={"asset_type": "hydro"},
            follow_redirects=False,
        )
        assert add_hydro.status_code == 303, add_hydro.text
        draft_page = client.get(f"/scenarios/{scenario['id']}/draft")
        assert draft_page.status_code == 200, draft_page.text
        assert 'name="hydro_generation_curve_json"' in draft_page.text
        response = client.post(
            f"/scenarios/{scenario['id']}/draft/structure",
            data=piecewise_hydro_form_data(document),
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
    elif save_mode == "api":
        response = client.post(
            f"/api/scenarios/{scenario['id']}/draft",
            json={"document": document},
        )
        assert response.status_code == 201, response.text
    else:
        raise AssertionError(f"unknown save_mode {save_mode}")
    return scenario["id"]


def create_linear_hydro_scenario(client, *, case_name):
    project = client.post("/api/projects", json={"name": f"{case_name} project"}).json()
    scenario = client.post(
        f"/api/projects/{project['id']}/scenarios",
        json={"name": f"{case_name} scenario"},
    ).json()
    response = client.post(
        f"/api/scenarios/{scenario['id']}/draft",
        json={"document": linear_hydro_draft_document(case_name)},
    )
    assert response.status_code == 201, response.text
    return scenario["id"]


def piecewise_hydro_draft_document(case_name, *, generation_curve):
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": case_name},
        "pcc": {"id": "bus_1", "type": "bus"},
        "grid": {
            "id": "grid_1",
            "import_power_max_mw": 20.0,
            "export_power_max_mw": 20.0,
            "prevent_simultaneous_grid_import_export": True,
        },
        "assets": [
            {
                "id": "hydro_pw_1",
                "type": "hydro",
                "storage_min_hm3": 1.0,
                "storage_max_hm3": 5.0,
                "initial_storage_hm3": 2.5,
                "generation_mode": "piecewise_linear",
                "turbine_flow_min_m3s": 0.0,
                "turbine_flow_max_m3s": 60.0,
                "power_max_mw": 5.0,
                "minimum_release_m3s": 0.0,
                "spill_penalty_usd_per_hm3": 100.0,
                "terminal_condition": "none",
                "terminal_water_value_usd_per_hm3": 0.0,
                "generation_curve": generation_curve,
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


def linear_hydro_draft_document(case_name):
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": case_name},
        "pcc": {"id": "bus_1", "type": "bus"},
        "grid": {
            "id": "grid_1",
            "import_power_max_mw": 20.0,
            "export_power_max_mw": 20.0,
            "prevent_simultaneous_grid_import_export": True,
        },
        "assets": [
            {
                "id": "hydro_lin_1",
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


def no_hydro_draft_document(case_name):
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


def piecewise_hydro_form_data(document):
    hydro = document["assets"][0]
    return {
        "case_name": document["case"]["name"],
        "pcc_id": document["pcc"]["id"],
        "grid_id": document["grid"]["id"],
        "grid_import_power_max_mw": str(document["grid"]["import_power_max_mw"]),
        "grid_export_power_max_mw": str(document["grid"]["export_power_max_mw"]),
        "grid_prevent_simultaneous_grid_import_export": "on",
        "hydro_id": hydro["id"],
        "hydro_storage_min_hm3": str(hydro["storage_min_hm3"]),
        "hydro_storage_max_hm3": str(hydro["storage_max_hm3"]),
        "hydro_initial_storage_hm3": str(hydro["initial_storage_hm3"]),
        "hydro_generation_mode": hydro["generation_mode"],
        "hydro_turbine_flow_min_m3s": str(hydro["turbine_flow_min_m3s"]),
        "hydro_turbine_flow_max_m3s": str(hydro["turbine_flow_max_m3s"]),
        "hydro_power_max_mw": str(hydro["power_max_mw"]),
        "hydro_minimum_release_m3s": str(hydro["minimum_release_m3s"]),
        "hydro_spill_penalty_usd_per_hm3": str(hydro["spill_penalty_usd_per_hm3"]),
        "hydro_terminal_condition": hydro["terminal_condition"],
        "hydro_terminal_water_value_usd_per_hm3": str(hydro["terminal_water_value_usd_per_hm3"]),
        "hydro_generation_curve_json": json.dumps(hydro["generation_curve"]),
        "hydro_reservoir_curve_json": json.dumps(hydro["reservoir_curve"]),
        "solver_name": document["solver"]["name"],
        "solver_options_json": json.dumps(document["solver"]["options"]),
    }


def default_piecewise_generation_curve():
    return [
        {"flow_m3s": 0.0, "power_mw": 0.0},
        {"flow_m3s": 15.0, "power_mw": 1.8},
        {"flow_m3s": 30.0, "power_mw": 2.4},
        {"flow_m3s": 45.0, "power_mw": 4.0},
        {"flow_m3s": 60.0, "power_mw": 3.8},
    ]


def upload_piecewise_csv_source(client, scenario_id):
    csv_text = (
        "period_start,hours,buy_price,sell_price,hydro_inflow_m3s\n"
        "2026-01-01T00:00:00,1.0,55.0,45.0,30.0\n"
        "2026-01-01T01:00:00,1.0,60.0,90.0,35.0\n"
    )
    response = client.post(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
        files={"source_file": ("piecewise_hydro.csv", csv_text, "text/csv")},
    )
    if response.status_code != 201:
        raise AssertionError(response.text)
    return response.json()["source"]


def upload_piecewise_xlsx_source(client, scenario_id):
    response = client.post(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
        data={"sheet_name": "Inputs"},
        files={
            "source_file": (
                "piecewise_hydro.xlsx",
                make_xlsx_bytes(
                    [
                        ["period_start", "hours", "buy_price", "sell_price", "hydro_inflow_m3s"],
                        ["2026-01-01T00:00:00", 1.0, 55.0, 45.0, 30.0],
                        ["2026-01-01T01:00:00", 1.0, 60.0, 90.0, 35.0],
                    ]
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    if response.status_code != 201:
        raise AssertionError(response.text)
    return response.json()["source"]


def upload_linear_hydro_csv_source(client, scenario_id, *, inflow="25.0"):
    csv_text = (
        "period_start,hours,buy_price,sell_price,hydro_inflow_m3s\n"
        f"2026-01-01T00:00:00,1.0,55.0,45.0,{inflow}\n"
        "2026-01-01T01:00:00,1.0,60.0,90.0,30.0\n"
    )
    response = client.post(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
        files={"source_file": ("linear_hydro.csv", csv_text, "text/csv")},
    )
    if response.status_code != 201:
        raise AssertionError(response.text)
    return response.json()["source"]


def save_linear_hydro_mapping(client, scenario_id, source_id):
    return client.put(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/mapping",
        json={
            "mapping": {
                "timestamp": "period_start",
                "duration_hours": "hours",
                "import_price_usd_per_mwh": "buy_price",
                "export_price_usd_per_mwh": "sell_price",
                "hydro_inflow_m3s": {"hydro_lin_1": "hydro_inflow_m3s"},
            }
        },
    )


def upload_no_hydro_csv_source(client, scenario_id):
    csv_text = (
        "period_start,hours,buy_price,sell_price,solar_mw,load_mw\n"
        "2026-01-01T00:00:00,0.5,55.0,42.0,3.5,2.0\n"
        "2026-01-01T00:30:00,0.5,60.0,48.0,4.0,2.5\n"
    )
    response = client.post(
        f"/api/scenarios/{scenario_id}/draft/time-series-sources/upload",
        files={"source_file": ("no_hydro.csv", csv_text, "text/csv")},
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


def write_hydro_outputs(output_dir, *, hydro_id, generation_mode):
    first_power = "2.4" if generation_mode == "piecewise_linear" else "2.0"
    second_power = "3.8" if generation_mode == "piecewise_linear" else "3.0"
    (output_dir / "dispatch.csv").write_text(
        "timestamp,duration_hours,import_price_usd_per_mwh,export_price_usd_per_mwh,"
        "grid_import_mw,grid_export_mw,net_grid_export_mw,total_hydro_power_mw,"
        "total_hydro_inflow_m3s,total_hydro_turbine_flow_m3s,total_hydro_spill_flow_m3s,"
        "total_hydro_storage_hm3,total_hydro_spill_penalty_usd,total_hydro_terminal_water_value_usd,"
        "period_profit_usd\n"
        f"2026-01-01T00:00:00,1.0,55.0,45.0,0.0,{first_power},{first_power},{first_power},30.0,30.0,0.0,2.608,0.0,0.0,108.0\n"
        f"2026-01-01T01:00:00,1.0,60.0,90.0,0.0,{second_power},{second_power},{second_power},35.0,30.0,5.0,2.608,1.8,0.0,340.2\n",
        encoding="utf-8",
    )
    (output_dir / "asset_dispatch.csv").write_text(
        "timestamp,duration_hours,asset_id,asset_type,hydro_power_mw,hydro_inflow_m3s,"
        "hydro_turbine_flow_m3s,hydro_spill_flow_m3s,hydro_inflow_volume_hm3,"
        "hydro_turbine_volume_hm3,hydro_spill_volume_hm3,hydro_storage_hm3,"
        "hydro_reservoir_elevation_masl,hydro_spill_penalty_usd,hydro_terminal_water_value_usd\n"
        f"2026-01-01T00:00:00,1.0,{hydro_id},hydro,{first_power},30.0,30.0,0.0,0.108,0.108,0.0,2.608,713.04,0.0,0.0\n"
        f"2026-01-01T01:00:00,1.0,{hydro_id},hydro,{second_power},35.0,30.0,5.0,0.126,0.108,0.018,2.608,713.04,1.8,0.0\n",
        encoding="utf-8",
    )


def write_non_hydro_outputs(output_dir, *, separate_prices):
    if separate_prices:
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
        return

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
