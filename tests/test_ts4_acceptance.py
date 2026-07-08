import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.result_indexing import index_run_results
from tests.test_ts4_result_indexing import (
    RecordingRunQueue,
    StubValidationService,
    create_completed_run_with_core_dispatch_artifacts,
    create_completed_run_with_full_hybrid_dispatch_artifacts,
    create_completed_run_with_hydro_only_dispatch_artifacts,
    create_completed_run_with_multi_asset_dispatch_artifacts,
)
from tests.test_ts4_run_comparison import create_indexed_run


REPO_ROOT = Path(__file__).resolve().parents[1]


class TS4AcceptanceTests(unittest.TestCase):
    """BESS-TS4-010: closing proof for indexed run results and comparison.

    Exercises one continuous TS-4 story: a successful run indexes hybrid
    dispatch, asset rows and summary KPIs with frozen lineage; re-indexing is
    idempotent; an old non-indexed run still serves from artifacts; a rebuild
    makes that historical run BBDD-backed; hydro-only signals index too; and
    two indexed runs of the same case compare through KPI and period-level
    diffs with variant/range context.
    """

    def test_ts4_result_indexing_story_end_to_end(self):
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            artifact_root = temp_root / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            client = TestClient(
                create_app(
                    validation_service=StubValidationService(),
                    store=store,
                    run_queue=RecordingRunQueue(),
                    artifact_root=artifact_root,
                )
            )
            try:
                hybrid_run = create_completed_run_with_full_hybrid_dispatch_artifacts(
                    store, artifact_root / "hybrid"
                )
                hybrid_index = index_run_results(
                    store=store,
                    run=hybrid_run,
                    artifact_root=artifact_root / "hybrid",
                )
                self.assertEqual(
                    hybrid_index,
                    {
                        "run_id": hybrid_run["id"],
                        "indexed": ["dispatch_table", "asset_dispatch_table", "summary"],
                        "failed": {},
                    },
                )
                hybrid_dispatch_index = store.get_run_dispatch_result_index(hybrid_run["id"])
                self.assertEqual(
                    hybrid_dispatch_index["signal_keys"],
                    {
                        "import_price_usd_per_mwh": "grid_import_price_usd_per_mwh",
                        "export_price_usd_per_mwh": "grid_export_price_usd_per_mwh",
                        "grid_import_mw": "grid_import_power_mw",
                        "grid_export_mw": "grid_export_power_mw",
                        "renewable_used_mw": "renewable_used_power_mw",
                        "renewable_curtailed_mw": "renewable_curtailed_power_mw",
                        "load_demand_mw": "load_demand_power_mw",
                        "battery_charge_mw": "bess_charge_power_mw",
                        "battery_discharge_mw": "bess_discharge_power_mw",
                        "battery_energy_mwh": "bess_stored_energy_mwh",
                        "import_cost_usd": "grid_import_cost_usd",
                        "export_revenue_usd": "grid_export_revenue_usd",
                        "net_market_value_usd": "net_market_value_usd",
                        "market_value_usd": "market_value_usd",
                        "battery_degradation_cost_usd": "bess_degradation_cost_usd",
                        "curtailment_penalty_usd": "renewable_curtailment_cost_usd",
                        "period_profit_usd": "period_profit_usd",
                    },
                )
                self.assertEqual(
                    store.get_run_summary_result_index(hybrid_run["id"])["summary"]["objective_value_usd"],
                    500.0,
                )

                multi_asset_run = create_completed_run_with_multi_asset_dispatch_artifacts(
                    store, artifact_root / "multi-asset"
                )
                multi_asset_index = index_run_results(
                    store=store,
                    run=multi_asset_run,
                    artifact_root=artifact_root / "multi-asset",
                )
                self.assertEqual(multi_asset_index["failed"], {})
                self.assertEqual(
                    [
                        row["asset_id"]
                        for row in store.get_run_asset_dispatch_result_index(multi_asset_run["id"])["rows"]
                    ],
                    ["grid_1", "battery_1", "solar_1"],
                )

                baseline_run = create_indexed_run(
                    store,
                    artifact_root / "comparison",
                    input_variant={"id": 11, "display_name": "Base"},
                    date_range={"start": "2026-01-01T00:00:00", "end": "2026-01-01T02:00:00"},
                    dispatch_rows=[
                        {
                            "timestamp": "2026-01-01T00:00:00",
                            "duration_hours": "1.0",
                            "price_usd_per_mwh": "45.0",
                            "grid_import_mw": "2.0",
                            "grid_export_mw": "0.0",
                            "market_value_usd": "-90.0",
                            "battery_charge_mw": "0.0",
                            "battery_discharge_mw": "0.0",
                            "battery_energy_mwh": "20.0",
                            "period_profit_usd": "-90.0",
                        },
                        {
                            "timestamp": "2026-01-01T01:00:00",
                            "duration_hours": "1.0",
                            "price_usd_per_mwh": "46.0",
                            "grid_import_mw": "3.0",
                            "grid_export_mw": "0.0",
                            "market_value_usd": "-138.0",
                            "battery_charge_mw": "0.0",
                            "battery_discharge_mw": "0.0",
                            "battery_energy_mwh": "20.0",
                            "period_profit_usd": "-138.0",
                        },
                    ],
                )
                candidate_run = create_indexed_run(
                    store,
                    artifact_root / "comparison",
                    scenario_id=store.get_run_lineage(baseline_run["id"])["scenario_id"],
                    objective_value_usd=1400.0,
                    input_variant={"id": 12, "display_name": "Stress"},
                    date_range={"start": "2026-01-01T01:00:00", "end": "2026-01-01T03:00:00"},
                    dispatch_rows=[
                        {
                            "timestamp": "2026-01-01T01:00:00",
                            "duration_hours": "1.0",
                            "price_usd_per_mwh": "50.0",
                            "grid_import_mw": "5.0",
                            "grid_export_mw": "0.0",
                            "market_value_usd": "-250.0",
                            "battery_charge_mw": "0.0",
                            "battery_discharge_mw": "0.0",
                            "battery_energy_mwh": "20.0",
                            "period_profit_usd": "-250.0",
                        },
                        {
                            "timestamp": "2026-01-01T02:00:00",
                            "duration_hours": "1.0",
                            "price_usd_per_mwh": "52.0",
                            "grid_import_mw": "6.0",
                            "grid_export_mw": "0.0",
                            "market_value_usd": "-312.0",
                            "battery_charge_mw": "0.0",
                            "battery_discharge_mw": "0.0",
                            "battery_energy_mwh": "20.0",
                            "period_profit_usd": "-312.0",
                        },
                    ],
                )
                reindexed_baseline = index_run_results(
                    store=store,
                    run=store.get_run(baseline_run["id"]),
                    artifact_root=artifact_root / "comparison",
                )
                self.assertEqual(reindexed_baseline["failed"], {})
                self.assertEqual(
                    store.connection.execute(
                        "SELECT COUNT(*) AS c FROM run_dispatch_result_rows WHERE run_id = ?",
                        (baseline_run["id"],),
                    ).fetchone()["c"],
                    2,
                )
                baseline_lineage = store.get_run_dispatch_result_index(baseline_run["id"])["lineage"]
                self.assertEqual(
                    baseline_lineage["input_variant"], {"id": 11, "display_name": "Base"}
                )
                self.assertEqual(
                    baseline_lineage["date_range"],
                    {"start": "2026-01-01T00:00:00", "end": "2026-01-01T02:00:00"},
                )

                legacy_run = create_completed_run_with_core_dispatch_artifacts(
                    store, artifact_root / "legacy"
                )
                legacy_results = client.get(f"/api/runs/{legacy_run['id']}/results")
                self.assertEqual(legacy_results.status_code, 200)
                self.assertEqual(
                    legacy_results.json()["results"]["dispatch_table"]["rows"][0]["grid_import_mw"],
                    "2.5",
                )

                rebuild_response = client.post(f"/api/admin/runs/{legacy_run['id']}/rebuild-results")
                self.assertEqual(rebuild_response.status_code, 200)
                self.assertEqual(rebuild_response.json()["rebuild"]["status"], "indexed")
                for filename in ["dispatch.csv", "asset_dispatch.csv", "summary.json"]:
                    (artifact_root / "legacy" / "runs" / "1" / "outputs" / filename).unlink()
                rebuilt_results = client.get(f"/api/runs/{legacy_run['id']}/results")
                self.assertEqual(rebuilt_results.status_code, 200)
                self.assertEqual(
                    rebuilt_results.json()["results"]["summary"]["objective_value_usd"],
                    1250.5,
                )

                hydro_run = create_completed_run_with_hydro_only_dispatch_artifacts(
                    store, artifact_root / "hydro"
                )
                hydro_rebuild = client.post(f"/api/admin/runs/{hydro_run['id']}/rebuild-results")
                self.assertEqual(hydro_rebuild.status_code, 200)
                hydro_dispatch_index = store.get_run_dispatch_result_index(hydro_run["id"])
                self.assertEqual(
                    hydro_dispatch_index["signal_keys"],
                    {
                        "total_hydro_power_mw": "hydro_generation_power_mw",
                        "total_hydro_inflow_m3s": "hydro_inflow_flow_m3s",
                        "total_hydro_turbine_flow_m3s": "hydro_turbine_flow_m3s",
                        "total_hydro_spill_flow_m3s": "hydro_spill_flow_m3s",
                        "total_hydro_storage_hm3": "hydro_storage_volume_hm3",
                        "total_hydro_reservoir_elevation_masl": "hydro_reservoir_elevation_masl",
                        "total_hydro_terminal_water_value_usd": "hydro_terminal_water_value_usd",
                    },
                )

                comparison_response = client.get(
                    "/api/run-comparisons",
                    params={
                        "baseline_run_id": baseline_run["id"],
                        "candidate_run_id": candidate_run["id"],
                        "series": "grid_import_power_mw",
                    },
                )
                self.assertEqual(comparison_response.status_code, 200)
                comparison = comparison_response.json()["comparison"]
                objective_kpi = next(kpi for kpi in comparison["kpis"] if kpi["key"] == "objective_value_usd")
                self.assertEqual(objective_kpi["baseline"], 1000.0)
                self.assertEqual(objective_kpi["candidate"], 1400.0)
                self.assertEqual(objective_kpi["delta"], 400.0)
                self.assertEqual(
                    comparison["baseline"]["input_variant"], {"id": 11, "display_name": "Base"}
                )
                self.assertEqual(
                    comparison["candidate"]["input_variant"], {"id": 12, "display_name": "Stress"}
                )
                self.assertEqual(
                    comparison["series_periods"],
                    [
                        {
                            "timestamp": "2026-01-01T00:00:00",
                            "baseline": 2.0,
                            "candidate": None,
                            "delta": None,
                        },
                        {
                            "timestamp": "2026-01-01T01:00:00",
                            "baseline": 3.0,
                            "candidate": 5.0,
                            "delta": 2.0,
                        },
                        {
                            "timestamp": "2026-01-01T02:00:00",
                            "baseline": None,
                            "candidate": 6.0,
                            "delta": None,
                        },
                    ],
                )
            finally:
                store.close()

    def test_ts4_documentation_tracker_and_issue_are_done(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        issue = (
            REPO_ROOT
            / "docs"
            / "series_tiempo"
            / "iter4"
            / "issues"
            / "BESS-TS4-010-finalize-ts4-acceptance-suite-and-docs.md"
        ).read_text(encoding="utf-8")
        tracker = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter4" / "issues" / "tracker_ts4.md"
        ).read_text(encoding="utf-8")
        manual = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter4" / "pruebas_manuales_ts4.md"
        ).read_text(encoding="utf-8")

        self.assertIn("TS-4: Result Series, Rebuild, And Run Comparison", readme)
        self.assertIn("tests.test_ts4_acceptance", readme)

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_ts4_acceptance", issue)

        self.assertIn(
            "| BESS-TS4-010 | Finalize TS-4 Acceptance Suite And Docs | AFK | ready-for-agent | Done |",
            tracker,
        )
        self.assertIn("BESS-TS4-010 | Todo -> Done", tracker)
        self.assertIn("Final TS-4 Verification", tracker)
        self.assertIn("tests.test_ts4_acceptance", tracker)

        self.assertIn("Cierre TS-4", manual)
        self.assertIn("tests.test_ts4_acceptance", manual)


if __name__ == "__main__":
    unittest.main()
