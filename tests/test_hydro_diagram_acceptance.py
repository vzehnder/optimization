import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.runner import JuliaRunExecutor
from app.validation import ValidationResult


REPO_ROOT = Path(__file__).resolve().parents[1]


class HydroDiagramAcceptanceTests(unittest.TestCase):
    def test_minimal_v3_diagram_workflow_reaches_run_results_and_preserves_v1_v2(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            artifact_root = temp_root / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            validation_service = HydroAcceptanceValidationService()
            run_process = HydroAcceptanceRunProcess()
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
                project = client.post(
                    "/api/projects",
                    json={"name": "Hydro Diagram Iter1 Acceptance"},
                ).json()
                scenario = client.post(
                    f"/api/projects/{project['id']}/scenarios",
                    json={"name": "Hydraulic v3 acceptance"},
                ).json()
                created = client.post(
                    f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
                )
                self.assertEqual(created.status_code, 201, created.text)

                diagram = save_complete_v3_diagram(
                    client,
                    scenario["id"],
                    created.json()["diagram"]["revision"],
                )
                self.assertEqual(
                    {node["technical_key"] for node in diagram["nodes"]},
                    {"reservoir_alpha", "junction_in", "junction_out", "plant_laja"},
                )

                topology = client.post(
                    f"/api/scenarios/{scenario['id']}/hydraulic-diagram/validate"
                )
                self.assertEqual(topology.status_code, 200, topology.text)
                self.assertTrue(topology.json()["validation"]["ok"])

                preview_response = client.post(
                    f"/api/scenarios/{scenario['id']}/hydraulic-diagram/v3-preview"
                )
                self.assertEqual(preview_response.status_code, 200, preview_response.text)
                preview = preview_response.json()["validation"]["system_case"]
                self.assertEqual(preview["schema_version"], "bess_system_dispatch.v3")
                self.assertEqual(preview["hydraulic_network"]["nodes"][0]["id"], "reservoir_alpha")
                self.assertEqual(
                    preview["time_series"][0]["natural_inflow_m3s"],
                    {"reservoir_alpha": 5.0},
                )

                promote_response = client.post(
                    f"/api/scenarios/{scenario['id']}/hydraulic-diagram/promote"
                )
                self.assertEqual(promote_response.status_code, 201, promote_response.text)
                version = promote_response.json()
                stored_version = client.get(
                    f"/api/scenario-versions/{version['id']}"
                ).json()["scenario_version"]
                self.assertEqual(stored_version["system_case_json"], preview)

                snapshot = client.get(
                    f"/api/scenario-versions/{version['id']}/hydraulic-diagram-snapshot"
                )
                self.assertEqual(snapshot.status_code, 200, snapshot.text)
                snapshot_layout = snapshot.json()["snapshot"]["layout_snapshot"]
                self.assertIn(
                    "reservoir_alpha",
                    {node["technical_key"] for node in snapshot_layout["nodes"]},
                )
                self.assertIn(
                    "reach_reservoir_intake",
                    {reach["technical_key"] for reach in snapshot_layout["reaches"]},
                )

                run_response = client.post(f"/api/scenario-versions/{version['id']}/runs")
                self.assertEqual(run_response.status_code, 201, run_response.text)
                run_id = run_response.json()["id"]
                run = client.get(f"/api/runs/{run_id}").json()["run"]
                self.assertEqual(run["status"], "succeeded")

                results = client.get(f"/api/runs/{run_id}/results").json()["results"]
                self.assertEqual(results["summary"]["schema_version"], "bess_system_dispatch.v3")
                self.assertGreater(
                    results["summary"]["hydraulic_v3_totals"]["total_generation_mwh"],
                    0.0,
                )
                self.assertIn("total_hydro_inflow_m3s", results["dispatch_table"]["columns"])
                self.assertIn("hydro_reservoir_elevation_masl", results["asset_dispatch_table"]["columns"])
                self.assertTrue(results["charts"]["hydro_power"]["available"])
                self.assertTrue(results["charts"]["hydro_flows"]["available"])
                self.assertTrue(results["charts"]["hydro_storage"]["available"])
                self.assertTrue(results["charts"]["hydro_reservoir_elevation"]["available"])

                artifacts = client.get(f"/api/runs/{run_id}/artifacts").json()["artifacts"]
                artifact_types = {artifact["artifact_type"] for artifact in artifacts}
                self.assertIn("system_case_resolved_json", artifact_types)
                self.assertIn("model_metadata_json", artifact_types)

                v1_run = create_version_and_run(
                    client,
                    project["id"],
                    "Legacy v1 acceptance",
                    REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json",
                )
                v2_run = create_version_and_run(
                    client,
                    project["id"],
                    "Legacy v2 acceptance",
                    REPO_ROOT / "data" / "cases" / "linear_hydro_system" / "system_case.json",
                )
                self.assertEqual(
                    client.get(f"/api/runs/{v1_run}/results").json()["results"]["summary"][
                        "schema_version"
                    ],
                    "bess_system_dispatch.v1",
                )
                self.assertEqual(
                    client.get(f"/api/runs/{v2_run}/results").json()["results"]["summary"][
                        "schema_version"
                    ],
                    "bess_system_dispatch.v2",
                )
                self.assertEqual(
                    run_process.completed_schema_versions,
                    [
                        "bess_system_dispatch.v3",
                        "bess_system_dispatch.v1",
                        "bess_system_dispatch.v2",
                    ],
                )
            finally:
                store.close()

    def test_iteration_1_documentation_tracker_and_manual_checklist_are_done(self):
        issue = (
            REPO_ROOT
            / "docs"
            / "hydro_diagram"
            / "iter1"
            / "issues"
            / "BESS-HYDRO-DIAGRAM-011-finalize-acceptance-suite-docs-and-db-checkpoint.md"
        ).read_text(encoding="utf-8")
        tracker = (
            REPO_ROOT
            / "docs"
            / "hydro_diagram"
            / "iter1"
            / "issues"
            / "tracker_hydro_diagram_iter1.md"
        ).read_text(encoding="utf-8")
        manual = (
            REPO_ROOT
            / "docs"
            / "hydro_diagram"
            / "iter1"
            / "pruebas_manuales_iteracion1.md"
        ).read_text(encoding="utf-8")
        checkpoint = (
            REPO_ROOT / "docs" / "db" / "hydro_diagram_db_checkpoint.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_hydro_diagram_acceptance", issue)
        self.assertIn(
            "| BESS-HYDRO-DIAGRAM-011 | Finalize Acceptance Suite Docs And DB Checkpoint | AFK | ready-for-agent | Done |",
            tracker,
        )
        self.assertIn("BESS-HYDRO-DIAGRAM-011 | Todo -> Done", tracker)
        self.assertIn("Final Hydro Diagram Iteration 1 Verification", tracker)
        self.assertIn("Cierre Iteracion Hydro Diagram 1", manual)
        self.assertIn("tests.test_hydro_diagram_acceptance", manual)
        self.assertIn("topology import", manual.lower())
        self.assertIn("head-dependent generation", manual.lower())
        self.assertIn("BESS-HYDRO-DIAGRAM-011", checkpoint)


class HydroAcceptanceValidationService:
    def __init__(self):
        self.text_validation_count = 0
        self.file_validation_count = 0

    def validate_text(self, candidate_text):
        self.text_validation_count += 1
        return validation_success_for(json.loads(candidate_text))

    def validate_file(self, candidate_path):
        self.file_validation_count += 1
        return validation_success_for(
            json.loads(Path(candidate_path).read_text(encoding="utf-8"))
        )


def validation_success_for(document):
    payload = {
        "status": "ok",
        "case_name": document["case_name"],
        "schema_version": document["schema_version"],
        "period_count": len(document.get("time_series", [])),
    }
    if document["schema_version"] == "bess_system_dispatch.v3":
        network = document.get("hydraulic_network", {})
        payload["hydraulic_network"] = {
            "nodes": len(network.get("nodes", [])),
            "reaches": len(network.get("reaches", [])),
            "plants": len(network.get("plants", [])),
            "units": len(network.get("units", [])),
        }
    return ValidationResult(
        ok=True,
        phase="julia",
        message="Validation succeeded",
        payload=payload,
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


class HydroAcceptanceRunProcess:
    def __init__(self):
        self.completed_schema_versions = []

    def __call__(self, command, **kwargs):
        input_path = next(Path(item) for item in command if str(item).endswith("system_case.json"))
        output_root = Path(command[command.index("--output-root") + 1])
        system_case = json.loads(input_path.read_text(encoding="utf-8"))
        schema_version = system_case["schema_version"]
        case_name = system_case["case_name"]
        self.completed_schema_versions.append(schema_version)
        output_dir = output_root / case_name / f"hydro-acceptance-run-{len(self.completed_schema_versions)}"
        output_dir.mkdir(parents=True)

        if schema_version == "bess_system_dispatch.v3":
            write_v3_outputs(output_dir, system_case)
        elif schema_version == "bess_system_dispatch.v2":
            write_v2_outputs(output_dir, system_case)
        else:
            write_v1_outputs(output_dir, system_case)

        (output_dir / "system_case_resolved.json").write_text(
            json.dumps(system_case, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "model_metadata.json").write_text(
            json.dumps(
                {
                    "model_name": "one_bus_system_dispatch",
                    "schema_version": schema_version,
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
                    "summary_path": str(output_dir / "summary.json"),
                    "termination_status": "OPTIMAL",
                }
            ),
            stderr="",
        )


def write_v3_outputs(output_dir, system_case):
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "case_name": system_case["case_name"],
                "schema_version": "bess_system_dispatch.v3",
                "solver_name": "HiGHS",
                "solver_status": "OPTIMAL",
                "termination_status": "OPTIMAL",
                "objective_value_usd": 500.0,
                "hydraulic_v3_totals": {
                    "total_generation_mwh": 55.0,
                    "total_turbine_volume_hm3": 0.288,
                    "total_spill_volume_hm3": 0.0,
                    "total_spill_penalty_usd": 0.0,
                    "final_storage_hm3": 19.96,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "dispatch.csv").write_text(
        "timestamp,duration_hours,total_hydro_power_mw,total_hydro_inflow_m3s,"
        "total_hydro_turbine_flow_m3s,total_hydro_spill_flow_m3s,total_hydro_storage_hm3,"
        "total_hydro_spill_penalty_usd,total_hydro_terminal_water_value_usd,period_profit_usd\n"
        "2026-01-01T00:00:00,1.0,25.0,5.0,20.0,0.0,19.946,0.0,0.0,250.0\n"
        "2026-01-01T01:00:00,1.0,30.0,6.0,20.0,0.0,19.896,0.0,0.0,300.0\n",
        encoding="utf-8",
    )
    (output_dir / "asset_dispatch.csv").write_text(
        "timestamp,duration_hours,asset_id,asset_type,hydro_power_mw,hydro_inflow_m3s,"
        "hydro_turbine_flow_m3s,hydro_spill_flow_m3s,hydro_storage_hm3,"
        "hydro_reservoir_elevation_masl,hydro_spill_penalty_usd,hydro_terminal_water_value_usd\n"
        "2026-01-01T00:00:00,1.0,unit_1,hydraulic_unit,25.0,0.0,20.0,0.0,0.0,0.0,0.0,0.0\n"
        "2026-01-01T00:00:00,1.0,reservoir_alpha,hydraulic_reservoir,0.0,5.0,0.0,0.0,19.946,719.9,0.0,0.0\n"
        "2026-01-01T01:00:00,1.0,unit_1,hydraulic_unit,30.0,0.0,20.0,0.0,0.0,0.0,0.0,0.0\n"
        "2026-01-01T01:00:00,1.0,reservoir_alpha,hydraulic_reservoir,0.0,6.0,0.0,0.0,19.896,719.8,0.0,0.0\n",
        encoding="utf-8",
    )


def write_v2_outputs(output_dir, system_case):
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "case_name": system_case["case_name"],
                "schema_version": "bess_system_dispatch.v2",
                "solver_status": "OPTIMAL",
                "termination_status": "OPTIMAL",
                "objective_value_usd": 250.0,
                "hydro_totals": {"total_hydro_generation_mwh": 3.0},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "dispatch.csv").write_text(
        "timestamp,duration_hours,import_price_usd_per_mwh,export_price_usd_per_mwh,"
        "grid_import_mw,grid_export_mw,net_grid_export_mw,total_hydro_power_mw,"
        "total_hydro_inflow_m3s,total_hydro_turbine_flow_m3s,total_hydro_spill_flow_m3s,"
        "total_hydro_storage_hm3,period_profit_usd\n"
        "2026-01-01T00:00:00,1.0,55.0,45.0,0.0,2.0,2.0,2.0,30.0,20.0,0.0,2.6,90.0\n",
        encoding="utf-8",
    )
    (output_dir / "asset_dispatch.csv").write_text(
        "timestamp,duration_hours,asset_id,asset_type,hydro_power_mw,hydro_reservoir_elevation_masl\n"
        "2026-01-01T00:00:00,1.0,hydro_1,hydro,2.0,710.0\n",
        encoding="utf-8",
    )


def write_v1_outputs(output_dir, system_case):
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "case_name": system_case["case_name"],
                "schema_version": "bess_system_dispatch.v1",
                "solver_status": "OPTIMAL",
                "termination_status": "OPTIMAL",
                "objective_value_usd": 125.0,
                "price_mode": "single_price",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "dispatch.csv").write_text(
        "timestamp,duration_hours,price_usd_per_mwh,grid_import_mw,grid_export_mw,"
        "net_grid_export_mw,battery_charge_mw,battery_discharge_mw,battery_energy_mwh,"
        "period_profit_usd\n"
        "2026-01-01T00:00:00,1.0,45.0,1.0,0.0,-1.0,1.0,0.0,5.0,-45.0\n",
        encoding="utf-8",
    )
    (output_dir / "asset_dispatch.csv").write_text(
        "timestamp,duration_hours,price_usd_per_mwh,asset_id,asset_type,battery_charge_mw,"
        "battery_discharge_mw,battery_energy_mwh\n"
        "2026-01-01T00:00:00,1.0,45.0,battery_1,battery,1.0,0.0,5.0\n",
        encoding="utf-8",
    )


def save_complete_v3_diagram(client, scenario_id, revision):
    response = client.put(
        f"/api/scenarios/{scenario_id}/hydraulic-diagram",
        json={
            "revision": revision,
            "nodes": complete_v3_nodes(),
            "reaches": [
                {
                    "technical_key": "reach_reservoir_intake",
                    "display_name": "Reservoir to intake",
                    "from_node_key": "reservoir_alpha",
                    "to_node_key": "junction_in",
                    "reach_type": "river",
                }
            ],
        },
    )
    if response.status_code != 200:
        raise AssertionError(response.text)
    return response.json()["diagram"]


def complete_v3_nodes():
    return [
        {
            "component_type": "reservoir",
            "technical_key": "reservoir_alpha",
            "display_name": "Reservoir Alpha",
            "x": 120.0,
            "y": 80.0,
            "reservoir": {
                "storage_min_hm3": 5.0,
                "storage_max_hm3": 50.0,
                "initial_storage_hm3": 20.0,
                "terminal_condition": "min_terminal",
                "terminal_storage_min_hm3": 10.0,
                "terminal_water_value_usd_per_hm3": 8.0,
            },
            "storage_elevation_curve": {
                "version_label": "v1",
                "points": [
                    {"x_value": 5.0, "y_value": 700.0},
                    {"x_value": 50.0, "y_value": 760.0},
                ],
            },
            "natural_inflow_series": {
                "version_label": "v1",
                "points": [
                    {
                        "timestamp": "2026-01-01T00:00:00",
                        "duration_hours": 1.0,
                        "value_m3s": 5.0,
                    },
                    {
                        "timestamp": "2026-01-01T01:00:00",
                        "duration_hours": 1.0,
                        "value_m3s": 6.0,
                    },
                ],
            },
        },
        {
            "component_type": "junction",
            "technical_key": "junction_in",
            "display_name": "Intake",
            "x": 300.0,
            "y": 80.0,
        },
        {
            "component_type": "junction",
            "technical_key": "junction_out",
            "display_name": "Tailrace",
            "x": 480.0,
            "y": 120.0,
        },
        {
            "component_type": "plant",
            "technical_key": "plant_laja",
            "display_name": "Plant Laja",
            "x": 390.0,
            "y": 200.0,
            "plant": {"non_modeled": False, "max_power_mw": 30.0},
            "units": [
                {
                    "technical_key": "unit_1",
                    "display_name": "Unit 1",
                    "is_active": True,
                    "intake_node_key": "junction_in",
                    "discharge_node_key": "junction_out",
                    "min_power_mw": 0.0,
                    "max_power_mw": 30.0,
                    "min_flow_m3s": 0.0,
                    "max_flow_m3s": 40.0,
                    "flow_power_curve": {
                        "version_label": "v1",
                        "points": [
                            {"x_value": 0.0, "y_value": 0.0},
                            {"x_value": 40.0, "y_value": 30.0},
                        ],
                    },
                }
            ],
        },
    ]


def create_version_and_run(client, project_id, scenario_name, case_path):
    scenario = client.post(
        f"/api/projects/{project_id}/scenarios",
        json={"name": scenario_name},
    ).json()
    version_response = client.post(
        f"/api/scenarios/{scenario['id']}/versions",
        json={"system_case_json": case_path.read_text(encoding="utf-8")},
    )
    if version_response.status_code != 201:
        raise AssertionError(version_response.text)
    version = version_response.json()
    run_response = client.post(f"/api/scenario-versions/{version['id']}/runs")
    if run_response.status_code != 201:
        raise AssertionError(run_response.text)
    return run_response.json()["id"]


if __name__ == "__main__":
    unittest.main()
