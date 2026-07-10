"""BESS-TS5-009: retention and cleanup for rebuildable derived result data.

Accepted TS-5 retention boundary: only TS-4 result indexes are cleanup
targets; artifacts, scenario-version snapshots, uploaded sources and revision
history stay immutable audit data. Cleanup must be admin-only, idempotent and
must close the loop with the existing TS4 rebuild path.
"""

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.result_indexing import rebuild_run_results
from app.result_retention import cleanup_project_result_data, cleanup_run_result_data
from app.results import read_run_results
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf
from tests.test_results_review import create_completed_run_with_result_artifacts


IMMUTABLE_TARGETS = [
    "artifacts",
    "scenario_versions",
    "time_series_sources",
    "time_series_set_revisions",
]


def create_completed_run_with_result_artifacts_for_project(
    store: AnalystStore,
    artifact_root: Path,
    *,
    project_id: int,
    scenario_name: str,
) -> dict:
    scenario = store.create_scenario(project_id=project_id, name=scenario_name)
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
    output_dir = artifact_root / "runs" / str(run["id"]) / "outputs"
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


class RunResultRetentionModuleTests(unittest.TestCase):
    def test_cleanup_run_removes_only_rebuildable_indexes_and_results_fall_back_to_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_result_artifacts(store, artifact_root)
                rebuild_run_results(store=store, run=run, artifact_root=artifact_root)

                outcome = cleanup_run_result_data(
                    store=store,
                    run_id=run["id"],
                    targets=["dispatch_table", "asset_dispatch_table", "summary", *IMMUTABLE_TARGETS],
                )

                self.assertEqual(outcome["run_id"], run["id"])
                self.assertEqual(
                    outcome["removed"],
                    ["dispatch_table", "asset_dispatch_table", "summary"],
                )
                self.assertEqual(outcome["failed"], {})
                for target in IMMUTABLE_TARGETS:
                    self.assertIn(target, outcome["kept"])
                    self.assertIn("immutable audit data", outcome["kept"][target])

                self.assertIsNone(store.get_run_dispatch_result_index(run["id"]))
                self.assertIsNone(store.get_run_asset_dispatch_result_index(run["id"]))
                self.assertIsNone(store.get_run_summary_result_index(run["id"]))
                self.assertEqual(len(store.list_run_artifacts(run["id"])), 3)
                self.assertEqual(
                    store.get_scenario_version(run["scenario_version_id"])["id"],
                    run["scenario_version_id"],
                )

                results = read_run_results(
                    run,
                    store.list_run_artifacts(run["id"]),
                    artifact_root,
                    store=store,
                )
                self.assertEqual(results["summary"]["termination_status"], "OPTIMAL")
                self.assertEqual(results["dispatch_table"]["rows"][0]["grid_import_mw"], "2.5")
                self.assertEqual(results["asset_dispatch_table"]["rows"][0]["asset_id"], "grid_1")
            finally:
                store.close()

    def test_cleanup_run_is_idempotent_and_rebuild_can_restore_removed_indexes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_result_artifacts(store, artifact_root)
                rebuild_run_results(store=store, run=run, artifact_root=artifact_root)

                first = cleanup_run_result_data(store=store, run_id=run["id"])
                second = cleanup_run_result_data(store=store, run_id=run["id"])

                self.assertEqual(
                    first["removed"],
                    ["dispatch_table", "asset_dispatch_table", "summary"],
                )
                self.assertEqual(second["removed"], [])
                self.assertEqual(
                    second["kept"]["dispatch_table"],
                    "already absent",
                )
                self.assertEqual(
                    second["kept"]["asset_dispatch_table"],
                    "already absent",
                )
                self.assertEqual(second["kept"]["summary"], "already absent")

                rebuild = rebuild_run_results(store=store, run=run, artifact_root=artifact_root)

                self.assertEqual(rebuild["status"], "indexed")
                self.assertEqual(
                    set(rebuild["indexed"]),
                    {"dispatch_table", "asset_dispatch_table", "summary"},
                )
            finally:
                store.close()


class ProjectResultRetentionModuleTests(unittest.TestCase):
    def test_cleanup_project_reports_removed_and_already_absent_surfaces_per_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                indexed_run = create_completed_run_with_result_artifacts(store, root / "indexed")
                rebuild_run_results(store=store, run=indexed_run, artifact_root=root / "indexed")
                project_id = store.get_run_project_id(indexed_run["id"])
                absent_run = create_completed_run_with_result_artifacts_for_project(
                    store,
                    root / "absent",
                    project_id=project_id,
                    scenario_name="Second case",
                )

                report = cleanup_project_result_data(
                    store=store,
                    project_id=project_id,
                    targets=["dispatch_table", "summary", "artifacts"],
                )

                self.assertEqual(report["project_id"], project_id)
                self.assertEqual(len(report["runs"]), 2)
                by_run_id = {item["run_id"]: item for item in report["runs"]}
                self.assertEqual(by_run_id[indexed_run["id"]]["removed"], ["dispatch_table", "summary"])
                self.assertEqual(by_run_id[indexed_run["id"]]["failed"], {})
                self.assertIn("artifacts", by_run_id[indexed_run["id"]]["kept"])
                self.assertEqual(by_run_id[absent_run["id"]]["removed"], [])
                self.assertEqual(by_run_id[absent_run["id"]]["kept"]["dispatch_table"], "already absent")
                self.assertEqual(by_run_id[absent_run["id"]]["kept"]["summary"], "already absent")
            finally:
                store.close()


class ResultRetentionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.artifact_root = Path(self.temp_dir.name) / "artifacts"
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.run = create_completed_run_with_result_artifacts(self.store, self.artifact_root)
        rebuild_run_results(store=self.store, run=self.run, artifact_root=self.artifact_root)
        self.project_id = self.store.get_run_project_id(self.run["id"])

        self.store.create_user(
            email="admin@example.local",
            display_name="Admin",
            role="admin",
            password_hash=hash_password("admin pass"),
            created_by="test",
        )
        self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
            created_by="test",
        )
        self.admin = TestClient(
            create_app(store=self.store, auth_enabled=True, artifact_root=self.artifact_root)
        )
        self.analyst = TestClient(
            create_app(store=self.store, auth_enabled=True, artifact_root=self.artifact_root)
        )
        self.login(self.admin, "admin@example.local", "admin pass")
        self.login(self.analyst, "analyst@example.local", "analyst pass")

    def login(self, client, email, password):
        response = login_json_with_csrf(client, email, password)
        self.assertEqual(response.status_code, 200)

    def test_admin_run_cleanup_endpoint_reports_removed_and_refused_targets(self):
        response = post_json_with_csrf(
            self.admin,
            f"/api/admin/runs/{self.run['id']}/cleanup-results",
            {"targets": ["dispatch_table", "summary", "artifacts"]},
        )

        self.assertEqual(response.status_code, 200)
        cleanup = response.json()["cleanup"]
        self.assertEqual(cleanup["run_id"], self.run["id"])
        self.assertEqual(cleanup["removed"], ["dispatch_table", "summary"])
        self.assertIn("artifacts", cleanup["kept"])

    def test_project_cleanup_endpoint_is_admin_only(self):
        analyst_response = post_json_with_csrf(
            self.analyst,
            f"/api/admin/projects/{self.project_id}/cleanup-results",
            {"targets": ["dispatch_table"]},
        )
        self.assertEqual(analyst_response.status_code, 403)

        admin_response = post_json_with_csrf(
            self.admin,
            f"/api/admin/projects/{self.project_id}/cleanup-results",
            {"targets": ["dispatch_table"]},
        )
        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(admin_response.json()["cleanup"]["project_id"], self.project_id)


if __name__ == "__main__":
    unittest.main()
