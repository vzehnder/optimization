import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.results import read_run_results


class ResultsReaderTests(unittest.TestCase):
    def test_reads_summary_artifact_for_completed_run_without_mutating_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            output_dir = artifact_root / "runs" / "1" / "outputs"
            output_dir.mkdir(parents=True)
            summary_path = output_dir / "summary.json"
            dispatch_path = output_dir / "dispatch.csv"
            asset_dispatch_path = output_dir / "asset_dispatch.csv"
            summary_text = json.dumps(
                {
                    "case_name": "hybrid_system",
                    "run_timestamp": "run-001",
                    "solver_name": "HiGHS",
                    "solver_status": "OPTIMAL",
                    "termination_status": "OPTIMAL",
                    "objective_value_usd": 1250.5,
                    "model_version": "0.1.0",
                },
                sort_keys=True,
            ) + "\n"
            summary_path.write_text(summary_text, encoding="utf-8")
            dispatch_path.write_text("timestamp,grid_import_mw\n2026-01-01T00:00:00,0.0\n", encoding="utf-8")
            asset_dispatch_path.write_text("timestamp,asset_id,asset_type\n2026-01-01T00:00:00,grid_1,grid\n", encoding="utf-8")
            before_stat = summary_path.stat()

            store = AnalystStore("sqlite:///:memory:")
            try:
                scenario_version = create_persisted_scenario_version(store)
                run = store.create_run(scenario_version_id=scenario_version["id"])
                store.mark_run_running(
                    run["id"],
                    workspace_path=str(artifact_root / "runs" / str(run["id"])),
                    input_snapshot_path=str(artifact_root / "runs" / str(run["id"]) / "input" / "system_case.json"),
                )
                run = store.mark_run_succeeded(
                    run["id"],
                    exit_code=0,
                    stdout="{}",
                    stderr="",
                    success_payload={"termination_status": "OPTIMAL"},
                    output_dir=str(output_dir),
                    summary_path=str(summary_path),
                )
                store.register_run_artifact(
                    run_id=run["id"],
                    artifact_type="summary_json",
                    path=str(summary_path),
                    display_name="summary.json",
                    media_type="application/json",
                )
                store.register_run_artifact(
                    run_id=run["id"],
                    artifact_type="dispatch_csv",
                    path=str(dispatch_path),
                    display_name="dispatch.csv",
                    media_type="text/csv",
                )
                store.register_run_artifact(
                    run_id=run["id"],
                    artifact_type="asset_dispatch_csv",
                    path=str(asset_dispatch_path),
                    display_name="asset_dispatch.csv",
                    media_type="text/csv",
                )

                results = read_run_results(run, store.list_run_artifacts(run["id"]), artifact_root)

                self.assertEqual(results["summary"]["case_name"], "hybrid_system")
                self.assertEqual(results["summary"]["termination_status"], "OPTIMAL")
                self.assertEqual(results["summary"]["objective_value_usd"], 1250.5)
                after_stat = summary_path.stat()
                self.assertEqual(summary_path.read_text(encoding="utf-8"), summary_text)
                self.assertEqual(after_stat.st_size, before_stat.st_size)
                self.assertEqual(after_stat.st_mtime_ns, before_stat.st_mtime_ns)
            finally:
                store.close()


class ResultsApiTests(unittest.TestCase):
    def test_results_api_returns_summary_and_result_tables_for_completed_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_result_artifacts(store, artifact_root)
                client = TestClient(
                    create_app(
                        validation_service=StubValidationService(),
                        store=store,
                        run_queue=RecordingRunQueue(),
                        artifact_root=artifact_root,
                    )
                )

                response = client.get(f"/api/runs/{run['id']}/results")

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["results"]["summary"]["case_name"], "hybrid_system")
                self.assertEqual(payload["results"]["summary"]["termination_status"], "OPTIMAL")
                self.assertIn("period_profit_usd", payload["results"]["dispatch_table"]["columns"])
                self.assertEqual(payload["results"]["dispatch_table"]["rows"][0]["grid_import_mw"], "2.5")
                self.assertEqual(payload["results"]["asset_dispatch_table"]["rows"][0]["asset_id"], "grid_1")
            finally:
                store.close()

    def test_results_api_reports_missing_result_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            output_dir = artifact_root / "runs" / "1" / "outputs"
            output_dir.mkdir(parents=True)
            summary_path = output_dir / "summary.json"
            summary_path.write_text('{"termination_status":"OPTIMAL"}\n', encoding="utf-8")
            store = AnalystStore("sqlite:///:memory:")
            try:
                scenario_version = create_persisted_scenario_version(store)
                run = store.create_run(scenario_version_id=scenario_version["id"])
                store.mark_run_running(
                    run["id"],
                    workspace_path=str(artifact_root / "runs" / str(run["id"])),
                    input_snapshot_path=str(artifact_root / "runs" / str(run["id"]) / "input" / "system_case.json"),
                )
                run = store.mark_run_succeeded(
                    run["id"],
                    exit_code=0,
                    stdout="{}",
                    stderr="",
                    success_payload={"termination_status": "OPTIMAL"},
                    output_dir=str(output_dir),
                    summary_path=str(summary_path),
                )
                store.register_run_artifact(
                    run_id=run["id"],
                    artifact_type="summary_json",
                    path=str(summary_path),
                    display_name="summary.json",
                    media_type="application/json",
                )
                client = TestClient(
                    create_app(
                        validation_service=StubValidationService(),
                        store=store,
                        run_queue=RecordingRunQueue(),
                        artifact_root=artifact_root,
                    )
                )

                response = client.get(f"/api/runs/{run['id']}/results")

                self.assertEqual(response.status_code, 404)
                self.assertIn("dispatch.csv artifact is not registered", response.json()["message"])
            finally:
                store.close()

    def test_results_api_reports_malformed_result_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_result_artifacts(store, artifact_root)
                summary_path = Path(store.get_run(run["id"])["summary_path"])
                summary_path.write_text('{"termination_status": ', encoding="utf-8")
                client = TestClient(
                    create_app(
                        validation_service=StubValidationService(),
                        store=store,
                        run_queue=RecordingRunQueue(),
                        artifact_root=artifact_root,
                    )
                )

                response = client.get(f"/api/runs/{run['id']}/results")

                self.assertEqual(response.status_code, 422)
                self.assertIn("summary.json is malformed JSON", response.json()["message"])
            finally:
                store.close()


class ResultsTemplateTests(unittest.TestCase):
    def test_completed_run_page_renders_summary_and_result_tables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_result_artifacts(store, artifact_root)
                client = TestClient(
                    create_app(
                        validation_service=StubValidationService(),
                        store=store,
                        run_queue=RecordingRunQueue(),
                        artifact_root=artifact_root,
                    )
                )

                response = client.get(f"/runs/{run['id']}")

                self.assertEqual(response.status_code, 200)
                self.assertIn("Run Summary", response.text)
                self.assertIn("hybrid_system", response.text)
                self.assertIn("Objective Value", response.text)
                self.assertIn("System Dispatch", response.text)
                self.assertIn("Asset Dispatch", response.text)
                self.assertIn("grid_import_mw", response.text)
                self.assertIn("period_profit_usd", response.text)
                self.assertIn("grid_1", response.text)
            finally:
                store.close()

    def test_reads_dispatch_and_asset_dispatch_tables_with_iteration_2_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            output_dir = artifact_root / "runs" / "1" / "outputs"
            output_dir.mkdir(parents=True)
            summary_path = output_dir / "summary.json"
            dispatch_path = output_dir / "dispatch.csv"
            asset_dispatch_path = output_dir / "asset_dispatch.csv"
            summary_path.write_text('{"termination_status":"OPTIMAL"}\n', encoding="utf-8")
            dispatch_columns = [
                "timestamp",
                "duration_hours",
                "price_usd_per_mwh",
                "grid_import_mw",
                "grid_export_mw",
                "net_grid_export_mw",
                "renewable_used_mw",
                "renewable_curtailed_mw",
                "load_demand_mw",
                "battery_charge_mw",
                "battery_discharge_mw",
                "battery_net_discharge_mw",
                "battery_energy_mwh",
                "battery_delta_soc_abs_mwh",
                "market_value_usd",
                "battery_degradation_cost_usd",
                "curtailment_penalty_usd",
                "period_profit_usd",
            ]
            dispatch_text = (
                ",".join(dispatch_columns)
                + "\n"
                + "2026-01-01T00:00:00,1.0,45.0,2.5,0.0,-2.5,4.0,0.0,6.5,0.0,0.0,0.0,20.0,0.0,-112.5,0.0,0.0,-112.5\n"
            )
            dispatch_path.write_text(dispatch_text, encoding="utf-8")
            asset_columns = [
                "timestamp",
                "duration_hours",
                "price_usd_per_mwh",
                "asset_id",
                "asset_type",
                "grid_import_mw",
                "grid_export_mw",
                "renewable_used_mw",
                "renewable_curtailed_mw",
                "load_demand_mw",
                "battery_charge_mw",
                "battery_discharge_mw",
                "battery_energy_mwh",
                "battery_delta_soc_abs_mwh",
            ]
            asset_dispatch_text = (
                ",".join(asset_columns)
                + "\n"
                + "2026-01-01T00:00:00,1.0,45.0,grid_1,grid,2.5,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0\n"
            )
            asset_dispatch_path.write_text(asset_dispatch_text, encoding="utf-8")
            before_dispatch_stat = dispatch_path.stat()
            before_asset_dispatch_stat = asset_dispatch_path.stat()

            store = AnalystStore("sqlite:///:memory:")
            try:
                scenario_version = create_persisted_scenario_version(store)
                run = store.create_run(scenario_version_id=scenario_version["id"])
                store.mark_run_running(
                    run["id"],
                    workspace_path=str(artifact_root / "runs" / str(run["id"])),
                    input_snapshot_path=str(artifact_root / "runs" / str(run["id"]) / "input" / "system_case.json"),
                )
                run = store.mark_run_succeeded(
                    run["id"],
                    exit_code=0,
                    stdout="{}",
                    stderr="",
                    success_payload={"termination_status": "OPTIMAL"},
                    output_dir=str(output_dir),
                    summary_path=str(summary_path),
                )
                store.register_run_artifact(
                    run_id=run["id"],
                    artifact_type="summary_json",
                    path=str(summary_path),
                    display_name="summary.json",
                    media_type="application/json",
                )
                store.register_run_artifact(
                    run_id=run["id"],
                    artifact_type="dispatch_csv",
                    path=str(dispatch_path),
                    display_name="dispatch.csv",
                    media_type="text/csv",
                )
                store.register_run_artifact(
                    run_id=run["id"],
                    artifact_type="asset_dispatch_csv",
                    path=str(asset_dispatch_path),
                    display_name="asset_dispatch.csv",
                    media_type="text/csv",
                )

                results = read_run_results(run, store.list_run_artifacts(run["id"]), artifact_root)

                self.assertEqual(results["dispatch_table"]["columns"], dispatch_columns)
                self.assertEqual(results["dispatch_table"]["rows"][0]["grid_import_mw"], "2.5")
                self.assertEqual(results["dispatch_table"]["rows"][0]["period_profit_usd"], "-112.5")
                self.assertEqual(results["asset_dispatch_table"]["columns"], asset_columns)
                self.assertEqual(results["asset_dispatch_table"]["rows"][0]["asset_id"], "grid_1")
                self.assertEqual(results["asset_dispatch_table"]["rows"][0]["asset_type"], "grid")
                after_dispatch_stat = dispatch_path.stat()
                after_asset_dispatch_stat = asset_dispatch_path.stat()
                self.assertEqual(dispatch_path.read_text(encoding="utf-8"), dispatch_text)
                self.assertEqual(asset_dispatch_path.read_text(encoding="utf-8"), asset_dispatch_text)
                self.assertEqual(after_dispatch_stat.st_mtime_ns, before_dispatch_stat.st_mtime_ns)
                self.assertEqual(after_asset_dispatch_stat.st_mtime_ns, before_asset_dispatch_stat.st_mtime_ns)
            finally:
                store.close()


def create_persisted_scenario_version(store):
    project = store.create_project(name="Hybrid PMGD")
    scenario = store.create_scenario(project_id=project["id"], name="Base case")
    return store.create_scenario_version(
        scenario_id=scenario["id"],
        system_case_json={
            "schema_version": "bess_system_dispatch.v1",
            "case_name": "hybrid_system",
            "nodes": [],
            "time_series": [],
        },
        validation_payload={"status": "ok"},
    )


def create_completed_run_with_result_artifacts(store, artifact_root):
    output_dir = artifact_root / "runs" / "1" / "outputs"
    output_dir.mkdir(parents=True)
    summary_path = output_dir / "summary.json"
    dispatch_path = output_dir / "dispatch.csv"
    asset_dispatch_path = output_dir / "asset_dispatch.csv"
    summary_path.write_text(
        json.dumps(
            {
                "case_name": "hybrid_system",
                "solver_status": "OPTIMAL",
                "termination_status": "OPTIMAL",
                "objective_value_usd": 1250.5,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    dispatch_path.write_text(
        "timestamp,duration_hours,price_usd_per_mwh,grid_import_mw,grid_export_mw,net_grid_export_mw,"
        "renewable_used_mw,renewable_curtailed_mw,load_demand_mw,battery_charge_mw,battery_discharge_mw,"
        "battery_net_discharge_mw,battery_energy_mwh,battery_delta_soc_abs_mwh,market_value_usd,"
        "battery_degradation_cost_usd,curtailment_penalty_usd,period_profit_usd\n"
        "2026-01-01T00:00:00,1.0,45.0,2.5,0.0,-2.5,4.0,0.0,6.5,0.0,0.0,0.0,20.0,0.0,-112.5,0.0,0.0,-112.5\n",
        encoding="utf-8",
    )
    asset_dispatch_path.write_text(
        "timestamp,duration_hours,price_usd_per_mwh,asset_id,asset_type,grid_import_mw,grid_export_mw,"
        "renewable_used_mw,renewable_curtailed_mw,load_demand_mw,battery_charge_mw,battery_discharge_mw,"
        "battery_energy_mwh,battery_delta_soc_abs_mwh\n"
        "2026-01-01T00:00:00,1.0,45.0,grid_1,grid,2.5,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0\n",
        encoding="utf-8",
    )

    scenario_version = create_persisted_scenario_version(store)
    run = store.create_run(scenario_version_id=scenario_version["id"])
    store.mark_run_running(
        run["id"],
        workspace_path=str(artifact_root / "runs" / str(run["id"])),
        input_snapshot_path=str(artifact_root / "runs" / str(run["id"]) / "input" / "system_case.json"),
    )
    run = store.mark_run_succeeded(
        run["id"],
        exit_code=0,
        stdout="{}",
        stderr="",
        success_payload={"termination_status": "OPTIMAL"},
        output_dir=str(output_dir),
        summary_path=str(summary_path),
    )
    for artifact_type, path, display_name, media_type in [
        ("summary_json", summary_path, "summary.json", "application/json"),
        ("dispatch_csv", dispatch_path, "dispatch.csv", "text/csv"),
        ("asset_dispatch_csv", asset_dispatch_path, "asset_dispatch.csv", "text/csv"),
    ]:
        store.register_run_artifact(
            run_id=run["id"],
            artifact_type=artifact_type,
            path=str(path),
            display_name=display_name,
            media_type=media_type,
        )
    return run


class StubValidationService:
    def validate_text(self, candidate_text):
        raise AssertionError("validation should not run in results tests")


class RecordingRunQueue:
    def enqueue(self, run_id):
        raise AssertionError("runs should not be enqueued in results tests")

    def stop(self):
        pass


if __name__ == "__main__":
    unittest.main()
