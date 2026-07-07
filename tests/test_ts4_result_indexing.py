import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.result_indexing import index_run_asset_dispatch_results, index_run_dispatch_results
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

    def test_indexes_hydro_only_diagram_dispatch_csv_without_grid_or_battery_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_hydro_only_dispatch_artifacts(store, artifact_root)

                indexed = index_run_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=store.list_run_artifacts(run["id"]),
                    artifact_root=artifact_root,
                )

                self.assertIsNotNone(indexed)
                self.assertIn("total_hydro_power_mw", indexed["columns"])
                self.assertEqual(indexed["rows"][0]["total_hydro_storage_hm3"], "3.0")
            finally:
                store.close()

    def test_indexes_demand_renewable_and_economics_signal_keys_for_a_hybrid_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_full_hybrid_dispatch_artifacts(store, artifact_root)

                indexed = index_run_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=store.list_run_artifacts(run["id"]),
                    artifact_root=artifact_root,
                )

                self.assertIsNotNone(indexed)
                signal_keys = indexed["signal_keys"]
                self.assertEqual(signal_keys["load_demand_mw"], "load_demand_power_mw")
                self.assertEqual(signal_keys["renewable_used_mw"], "renewable_used_power_mw")
                self.assertEqual(signal_keys["renewable_curtailed_mw"], "renewable_curtailed_power_mw")
                self.assertEqual(signal_keys["period_profit_usd"], "period_profit_usd")
                self.assertEqual(signal_keys["battery_degradation_cost_usd"], "bess_degradation_cost_usd")
                self.assertEqual(signal_keys["export_revenue_usd"], "grid_export_revenue_usd")
            finally:
                store.close()

    def test_missing_signal_families_are_absent_from_signal_keys_without_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                core_run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                core_indexed = index_run_dispatch_results(
                    store=store,
                    run=core_run,
                    artifacts=store.list_run_artifacts(core_run["id"]),
                    artifact_root=artifact_root,
                )
                self.assertNotIn("total_hydro_power_mw", core_indexed["signal_keys"])
                self.assertNotIn("load_demand_mw", core_indexed["signal_keys"])

                hydro_run = create_completed_run_with_hydro_only_dispatch_artifacts(
                    store, artifact_root / "hydro"
                )
                hydro_indexed = index_run_dispatch_results(
                    store=store,
                    run=hydro_run,
                    artifacts=store.list_run_artifacts(hydro_run["id"]),
                    artifact_root=artifact_root / "hydro",
                )
                self.assertNotIn("battery_charge_mw", hydro_indexed["signal_keys"])
                self.assertNotIn("renewable_used_mw", hydro_indexed["signal_keys"])
                self.assertEqual(hydro_indexed["signal_keys"]["total_hydro_power_mw"], "hydro_generation_power_mw")
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


def create_completed_run_with_hydro_only_dispatch_artifacts(store: AnalystStore, artifact_root: Path) -> dict:
    output_dir = artifact_root / "runs" / "1" / "outputs"
    output_dir.mkdir(parents=True)
    summary_path = output_dir / "summary.json"
    dispatch_path = output_dir / "dispatch.csv"
    asset_dispatch_path = output_dir / "asset_dispatch.csv"
    summary_path.write_text(
        json.dumps(
            {
                "case_name": "hydraulic_diagram_system",
                "solver_status": "OPTIMAL",
                "termination_status": "OPTIMAL",
                "objective_value_usd": 900.0,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    dispatch_path.write_text(
        "timestamp,duration_hours,total_hydro_power_mw,total_hydro_inflow_m3s,"
        "total_hydro_turbine_flow_m3s,total_hydro_spill_flow_m3s,total_hydro_storage_hm3,"
        "total_hydro_reservoir_elevation_masl,total_hydro_terminal_water_value_usd\n"
        "2026-01-01T00:00:00,1.0,2.0,25.0,25.0,0.0,3.0,710.0,0.0\n",
        encoding="utf-8",
    )
    asset_dispatch_path.write_text(
        "timestamp,asset_id,asset_type\n2026-01-01T00:00:00,hydro_1,hydraulic_unit\n",
        encoding="utf-8",
    )

    project = store.create_project(name="TS4 Hydro Diagram Project")
    scenario = store.create_scenario(project_id=project["id"], name="Hydro diagram case")
    scenario_version = store.create_scenario_version(
        scenario_id=scenario["id"],
        system_case_json={
            "schema_version": "bess_system_dispatch.v1",
            "case_name": "hydraulic_diagram_system",
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


def create_completed_run_with_full_hybrid_dispatch_artifacts(store: AnalystStore, artifact_root: Path) -> dict:
    output_dir = artifact_root / "runs" / "1" / "outputs"
    output_dir.mkdir(parents=True)
    summary_path = output_dir / "summary.json"
    dispatch_path = output_dir / "dispatch.csv"
    asset_dispatch_path = output_dir / "asset_dispatch.csv"
    summary_path.write_text(
        json.dumps(
            {
                "case_name": "separate_price_hybrid_system",
                "solver_status": "OPTIMAL",
                "termination_status": "OPTIMAL",
                "objective_value_usd": 500.0,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    dispatch_path.write_text(
        "timestamp,duration_hours,import_price_usd_per_mwh,export_price_usd_per_mwh,"
        "grid_import_mw,grid_export_mw,renewable_used_mw,renewable_curtailed_mw,load_demand_mw,"
        "battery_charge_mw,battery_discharge_mw,battery_energy_mwh,import_cost_usd,"
        "export_revenue_usd,net_market_value_usd,market_value_usd,"
        "battery_degradation_cost_usd,curtailment_penalty_usd,period_profit_usd\n"
        "2026-01-01T00:00:00,1.0,10.0,100.0,5.0,0.0,3.0,1.0,8.0,0.0,5.0,20.0,0.0,"
        "-50.0,-50.0,-50.0,0.5,0.1,-50.6\n",
        encoding="utf-8",
    )
    asset_dispatch_path.write_text(
        "timestamp,asset_id,asset_type\n2026-01-01T00:00:00,grid_1,grid\n",
        encoding="utf-8",
    )

    project = store.create_project(name="TS4 Hybrid Project")
    scenario = store.create_scenario(project_id=project["id"], name="Separate price hybrid case")
    scenario_version = store.create_scenario_version(
        scenario_id=scenario["id"],
        system_case_json={
            "schema_version": "bess_system_dispatch.v1",
            "case_name": "separate_price_hybrid_system",
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


class AssetDispatchResultIndexingTests(unittest.TestCase):
    def test_indexes_multi_asset_dispatch_csv_into_bbdd_linked_to_run_and_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_multi_asset_dispatch_artifacts(store, artifact_root)

                indexed = index_run_asset_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=store.list_run_artifacts(run["id"]),
                    artifact_root=artifact_root,
                )

                self.assertIsNotNone(indexed)
                self.assertEqual(indexed["run_id"], run["id"])
                self.assertEqual(indexed["scenario_version_id"], run["scenario_version_id"])
                rows = indexed["rows"]
                self.assertEqual([row["asset_id"] for row in rows], ["grid_1", "battery_1", "solar_1"])
                self.assertEqual([row["asset_type"] for row in rows], ["grid", "battery", "renewable"])
                self.assertEqual(rows[1]["battery_energy_mwh"], "20.0")
                self.assertEqual(rows[2]["renewable_used_mw"], "3.0")
            finally:
                store.close()

    def test_read_run_results_prefers_indexed_asset_dispatch_table_over_csv_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_multi_asset_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])
                index_run_asset_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )

                asset_dispatch_path = artifact_root / "runs" / "1" / "outputs" / "asset_dispatch.csv"
                asset_dispatch_path.unlink()

                results = read_run_results(run, artifacts, artifact_root, store=store)

                self.assertEqual(
                    [row["asset_id"] for row in results["asset_dispatch_table"]["rows"]],
                    ["grid_1", "battery_1", "solar_1"],
                )
            finally:
                store.close()

    def test_results_api_prefers_indexed_asset_dispatch_table_over_csv_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_multi_asset_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])
                index_run_asset_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )
                asset_dispatch_path = artifact_root / "runs" / "1" / "outputs" / "asset_dispatch.csv"
                asset_dispatch_path.unlink()
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
                    [
                        row["asset_id"]
                        for row in response.json()["results"]["asset_dispatch_table"]["rows"]
                    ],
                    ["grid_1", "battery_1", "solar_1"],
                )
            finally:
                store.close()

    def test_read_run_results_falls_back_to_asset_dispatch_csv_when_not_indexed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_multi_asset_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])

                results = read_run_results(run, artifacts, artifact_root, store=store)

                self.assertEqual(
                    [row["asset_id"] for row in results["asset_dispatch_table"]["rows"]],
                    ["grid_1", "battery_1", "solar_1"],
                )
            finally:
                store.close()


def create_completed_run_with_multi_asset_dispatch_artifacts(store: AnalystStore, artifact_root: Path) -> dict:
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
                "objective_value_usd": 750.0,
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
        "timestamp,asset_id,asset_type,grid_import_mw,grid_export_mw,battery_charge_mw,"
        "battery_discharge_mw,battery_energy_mwh,renewable_used_mw,renewable_curtailed_mw\n"
        "2026-01-01T00:00:00,grid_1,grid,2.5,0.0,,,,,\n"
        "2026-01-01T00:00:00,battery_1,battery,,,0.0,0.0,20.0,,\n"
        "2026-01-01T00:00:00,solar_1,renewable,,,,,,3.0,0.0\n",
        encoding="utf-8",
    )

    project = store.create_project(name="TS4 Multi-Asset Project")
    scenario = store.create_scenario(project_id=project["id"], name="Multi-asset case")
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
