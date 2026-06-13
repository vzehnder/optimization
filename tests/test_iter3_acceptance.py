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


class Iteration3AcceptanceTests(unittest.TestCase):
    def test_private_analyst_flow_succeeds_and_failed_runs_remain_auditable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            validation_service = AcceptanceValidationService()
            run_process = AcceptanceRunProcess()
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
                )
            )
            try:
                sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text(
                    encoding="utf-8"
                )

                project = client.post(
                    "/api/projects",
                    json={"name": "Hybrid PMGD", "description": "Iteration 3 acceptance"},
                ).json()
                scenario = client.post(
                    f"/api/projects/{project['id']}/scenarios",
                    json={"name": "Base case", "description": "Analyst-managed system case"},
                ).json()

                version_response = client.post(
                    f"/api/scenarios/{scenario['id']}/versions",
                    json={"system_case_json": sample_text},
                )
                self.assertEqual(version_response.status_code, 201)
                version = version_response.json()
                self.assertEqual(version["version_number"], 1)
                self.assertEqual(version["case_name"], "hybrid_system")
                self.assertEqual(version["schema_version"], "bess_system_dispatch.v1")
                self.assertGreater(version["period_count"], 0)
                self.assertEqual(validation_service.text_validation_phases, ["julia"])

                invalid_response = client.post(
                    f"/api/scenarios/{scenario['id']}/versions",
                    json={"system_case_json": '{"schema_version": '},
                )
                self.assertEqual(invalid_response.status_code, 400)
                self.assertEqual(invalid_response.json()["phase"], "json")
                versions_after_invalid = client.get(f"/api/scenarios/{scenario['id']}/versions").json()["versions"]
                self.assertEqual([item["version_number"] for item in versions_after_invalid], [1])

                run_response = client.post(f"/api/scenario-versions/{version['id']}/runs")
                self.assertEqual(run_response.status_code, 201)
                run_id = run_response.json()["id"]
                completed_run = client.get(f"/api/runs/{run_id}").json()["run"]
                self.assertEqual(completed_run["status"], "succeeded")
                self.assertEqual(completed_run["exit_code"], 0)
                self.assertTrue(Path(completed_run["input_snapshot_path"]).is_file())
                self.assertEqual(validation_service.file_validation_count, 1)

                artifacts = client.get(f"/api/runs/{run_id}/artifacts").json()["artifacts"]
                artifacts_by_type = {artifact["artifact_type"]: artifact for artifact in artifacts}
                self.assertEqual(
                    set(artifacts_by_type),
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

                results_response = client.get(f"/api/runs/{run_id}/results")
                self.assertEqual(results_response.status_code, 200)
                results = results_response.json()["results"]
                self.assertEqual(results["summary"]["termination_status"], "OPTIMAL")
                self.assertIn("period_profit_usd", results["dispatch_table"]["columns"])
                self.assertEqual(results["asset_dispatch_table"]["rows"][0]["asset_id"], "grid_1")
                self.assertTrue(results["charts"]["grid_import_export"]["available"])
                self.assertTrue(results["charts"]["renewable_used_curtailed"]["available"])
                self.assertTrue(results["charts"]["bess_charge_discharge_soc"]["available"])
                self.assertTrue(results["charts"]["period_profit"]["available"])
                self.assertEqual(results["charts"]["source_rows"]["asset_dispatch"], 3)

                run_page = client.get(f"/runs/{run_id}")
                self.assertEqual(run_page.status_code, 200)
                self.assertIn("Run Summary", run_page.text)
                self.assertIn("Basic Charts", run_page.text)
                self.assertIn("System Dispatch", run_page.text)
                self.assertIn("Asset Dispatch", run_page.text)
                self.assertIn(artifacts_by_type["summary_json"]["download_url"], run_page.text)

                summary_download = client.get(artifacts_by_type["summary_json"]["download_url"])
                self.assertEqual(summary_download.status_code, 200)
                self.assertEqual(summary_download.json()["case_name"], "hybrid_system")

                dispatch_download = client.get(artifacts_by_type["dispatch_csv"]["download_url"])
                self.assertEqual(dispatch_download.status_code, 200)
                self.assertIn(b"period_profit_usd", dispatch_download.content)

                run_process.fail_next = True
                failed_run_response = client.post(f"/api/scenario-versions/{version['id']}/runs")
                self.assertEqual(failed_run_response.status_code, 201)
                failed_run_id = failed_run_response.json()["id"]
                failed_run = client.get(f"/api/runs/{failed_run_id}").json()["run"]
                self.assertEqual(failed_run["status"], "failed")
                self.assertEqual(failed_run["exit_code"], 23)
                self.assertIn("optimization failed before solve", failed_run["error_message"])
                self.assertTrue(Path(failed_run["stdout_log_path"]).is_file())
                self.assertTrue(Path(failed_run["stderr_log_path"]).is_file())

                failed_artifacts = client.get(f"/api/runs/{failed_run_id}/artifacts").json()["artifacts"]
                failed_artifacts_by_type = {artifact["artifact_type"]: artifact for artifact in failed_artifacts}
                self.assertEqual(set(failed_artifacts_by_type), {"input_snapshot", "stdout_log", "stderr_log"})

                stderr_download = client.get(failed_artifacts_by_type["stderr_log"]["download_url"])
                self.assertEqual(stderr_download.status_code, 200)
                self.assertIn(b"optimization failed before solve", stderr_download.content)

                failed_run_page = client.get(f"/runs/{failed_run_id}")
                self.assertEqual(failed_run_page.status_code, 200)
                self.assertIn("failed", failed_run_page.text)
                self.assertIn("optimization failed before solve", failed_run_page.text)
            finally:
                store.close()

    def test_iteration_3_documentation_covers_local_setup_and_verification(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        tracker = (REPO_ROOT / "docs" / "iter3" / "issues" / "tracker_iter3.md").read_text(encoding="utf-8")

        for expected in [
            "Run The Analyst Web App",
            "DATABASE_URL",
            "ARTIFACT_ROOT",
            "uvicorn app.main:app",
            "Validate And Save A Scenario Version",
            "Launch A Manual Run",
            "Auditable Artifacts And Downloads",
            "Iteration 3 Acceptance Verification",
        ]:
            self.assertIn(expected, readme)

        self.assertIn("Final Iteration 3 Verification", tracker)
        self.assertIn(".\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v", tracker)
        self.assertIn('julia --project=. -e "import Pkg; Pkg.test()"', tracker)


class AcceptanceValidationService:
    def __init__(self):
        self.text_validation_phases = []
        self.file_validation_count = 0

    def validate_text(self, candidate_text):
        try:
            document = json.loads(candidate_text)
        except json.JSONDecodeError as error:
            return ValidationResult(
                ok=False,
                phase="json",
                message=f"Malformed JSON: {error.msg} at line {error.lineno}, column {error.colno}",
                payload={"status": "error", "message": error.msg, "line": error.lineno, "column": error.colno},
            )

        self.text_validation_phases.append("julia")
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
        )

    def validate_file(self, candidate_path):
        self.file_validation_count += 1
        document = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
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
        )


class SynchronousRunQueue:
    def __init__(self, executor):
        self.executor = executor
        self.enqueued_run_ids = []

    def enqueue(self, run_id):
        self.enqueued_run_ids.append(run_id)
        self.executor.execute(run_id)

    def stop(self):
        pass


class AcceptanceRunProcess:
    def __init__(self):
        self.fail_next = False

    def __call__(self, command, **kwargs):
        if self.fail_next:
            self.fail_next = False
            return subprocess.CompletedProcess(
                command,
                23,
                stdout="solver stdout\n",
                stderr='{"status":"error","message":"optimization failed before solve"}\n',
            )

        output_root = Path(command[command.index("--output-root") + 1])
        output_dir = output_root / "hybrid_system" / "acceptance-run"
        output_dir.mkdir(parents=True)
        summary_path = output_dir / "summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "case_name": "hybrid_system",
                    "run_timestamp": "acceptance-run",
                    "solver_name": "HiGHS",
                    "solver_status": "OPTIMAL",
                    "termination_status": "OPTIMAL",
                    "objective_value_usd": 1250.5,
                    "model_version": "0.1.0",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (output_dir / "dispatch.csv").write_text(
            "timestamp,duration_hours,price_usd_per_mwh,grid_import_mw,grid_export_mw,net_grid_export_mw,"
            "renewable_used_mw,renewable_curtailed_mw,load_demand_mw,battery_charge_mw,battery_discharge_mw,"
            "battery_net_discharge_mw,battery_energy_mwh,battery_delta_soc_abs_mwh,market_value_usd,"
            "battery_degradation_cost_usd,curtailment_penalty_usd,period_profit_usd\n"
            "2026-01-01T00:00:00,1.0,45.0,2.5,0.0,-2.5,4.0,0.0,6.5,0.0,0.0,0.0,20.0,0.0,-112.5,0.0,0.0,-112.5\n"
            "2026-01-01T01:00:00,1.0,80.0,0.0,1.5,1.5,3.0,1.0,4.0,0.0,1.0,1.0,18.9,1.1,120.0,2.2,0.0,117.8\n",
            encoding="utf-8",
        )
        (output_dir / "asset_dispatch.csv").write_text(
            "timestamp,duration_hours,price_usd_per_mwh,asset_id,asset_type,grid_import_mw,grid_export_mw,"
            "renewable_used_mw,renewable_curtailed_mw,load_demand_mw,battery_charge_mw,battery_discharge_mw,"
            "battery_energy_mwh,battery_delta_soc_abs_mwh\n"
            "2026-01-01T00:00:00,1.0,45.0,grid_1,grid,2.5,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0\n"
            "2026-01-01T00:00:00,1.0,45.0,solar_1,renewable,0.0,0.0,4.0,0.0,0.0,0.0,0.0,0.0,0.0\n"
            "2026-01-01T00:00:00,1.0,45.0,battery_1,battery,0.0,0.0,0.0,0.0,0.0,0.0,0.0,20.0,0.0\n",
            encoding="utf-8",
        )
        (output_dir / "model_metadata.json").write_text(
            json.dumps({"model_name": "one_bus_system_dispatch", "schema_version": "bess_system_dispatch.v1"}) + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "case_name": "hybrid_system",
                    "run_timestamp": "acceptance-run",
                    "output_dir": str(output_dir),
                    "summary_path": str(summary_path),
                    "termination_status": "OPTIMAL",
                }
            ),
            stderr="",
        )


if __name__ == "__main__":
    unittest.main()
