import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.result_indexing import index_run_dispatch_results
from app.results import read_run_results
from app.validation import ValidationResult


class DispatchResultIndexingTests(unittest.TestCase):
    def test_indexes_supported_dispatch_csv_into_bbdd_linked_to_run_and_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)

                indexed = index_run_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=store.list_run_artifacts(run["id"]),
                    artifact_root=artifact_root,
                )

                self.assertIsNotNone(indexed)
                self.assertEqual(indexed["run_id"], run["id"])
                self.assertEqual(indexed["scenario_version_id"], run["scenario_version_id"])
                self.assertEqual(
                    indexed["columns"],
                    [
                        "timestamp",
                        "duration_hours",
                        "price_usd_per_mwh",
                        "grid_import_mw",
                        "grid_export_mw",
                        "market_value_usd",
                        "battery_charge_mw",
                        "battery_discharge_mw",
                        "battery_energy_mwh",
                        "period_profit_usd",
                    ],
                )
                self.assertEqual(indexed["rows"][0]["grid_import_mw"], "2.5")
                self.assertEqual(indexed["rows"][0]["battery_energy_mwh"], "20.0")
            finally:
                store.close()

    def test_read_run_results_prefers_indexed_dispatch_table_over_csv_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])
                index_run_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )

                dispatch_path = artifact_root / "runs" / "1" / "outputs" / "dispatch.csv"
                dispatch_path.unlink()

                results = read_run_results(run, artifacts, artifact_root, store=store)

                self.assertEqual(results["dispatch_table"]["rows"][0]["grid_import_mw"], "2.5")
                self.assertEqual(results["asset_dispatch_table"]["rows"][0]["asset_id"], "grid_1")
            finally:
                store.close()

    def test_results_api_prefers_indexed_dispatch_table_over_csv_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])
                index_run_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )
                dispatch_path = artifact_root / "runs" / "1" / "outputs" / "dispatch.csv"
                dispatch_path.unlink()
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
                self.assertEqual(
                    response.json()["results"]["dispatch_table"]["rows"][0]["grid_import_mw"],
                    "2.5",
                )
            finally:
                store.close()

    def test_indexer_accepts_relative_dispatch_artifact_paths(self):
        temp_root = Path.cwd() / ".tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])
                relative_dispatch_path = str(
                    (artifact_root / "runs" / "1" / "outputs" / "dispatch.csv").relative_to(Path.cwd())
                )
                relative_artifacts = [
                    {
                        **artifact,
                        "path": relative_dispatch_path if artifact["artifact_type"] == "dispatch_csv" else artifact["path"],
                    }
                    for artifact in artifacts
                ]

                indexed = index_run_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=relative_artifacts,
                    artifact_root=artifact_root,
                )

                self.assertIsNotNone(indexed)
                self.assertEqual(indexed["rows"][0]["battery_energy_mwh"], "20.0")
            finally:
                store.close()


def create_completed_run_with_core_dispatch_artifacts(store: AnalystStore, artifact_root: Path) -> dict:
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
        "timestamp,duration_hours,price_usd_per_mwh,grid_import_mw,grid_export_mw,market_value_usd,"
        "battery_charge_mw,battery_discharge_mw,battery_energy_mwh,period_profit_usd\n"
        "2026-01-01T00:00:00,1.0,45.0,2.5,0.0,-112.5,0.0,0.0,20.0,-112.5\n",
        encoding="utf-8",
    )
    asset_dispatch_path.write_text(
        "timestamp,asset_id,asset_type\n2026-01-01T00:00:00,grid_1,grid\n",
        encoding="utf-8",
    )

    project = store.create_project(name="TS4 Project")
    scenario = store.create_scenario(project_id=project["id"], name="Base case")
    scenario_version = store.create_scenario_version(
        scenario_id=scenario["id"],
        system_case_json={
            "schema_version": "bess_system_dispatch.v1",
            "case_name": "hybrid_system",
            "nodes": [],
            "time_series": [],
        },
        validation_payload={"status": "ok"},
    )
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
    def validate_text(self, candidate_text: str) -> ValidationResult:
        return ValidationResult(ok=True, phase="julia", message="ok", payload={"status": "ok"})


class RecordingRunQueue:
    def enqueue(self, run_id: int) -> None:
        raise AssertionError("runs should not be enqueued in TS4 indexing tests")

    def stop(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
