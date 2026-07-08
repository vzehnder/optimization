import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.result_indexing import index_run_results
from tests.test_ts4_result_indexing import RecordingRunQueue, StubValidationService

DISPATCH_COLUMNS = [
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
]

DEFAULT_DISPATCH_ROWS = [
    {
        "timestamp": "2026-01-01T00:00:00",
        "duration_hours": "1.0",
        "price_usd_per_mwh": "45.0",
        "grid_import_mw": "2.5",
        "grid_export_mw": "0.0",
        "market_value_usd": "-112.5",
        "battery_charge_mw": "0.0",
        "battery_discharge_mw": "0.0",
        "battery_energy_mwh": "20.0",
        "period_profit_usd": "-112.5",
    }
]


def create_indexed_run(
    store: AnalystStore,
    artifact_root: Path,
    *,
    scenario_id: int | None = None,
    objective_value_usd: float = 1000.0,
    input_variant: dict[str, Any] | None = None,
    date_range: dict[str, Any] | None = None,
    dispatch_rows: list[dict[str, Any]] | None = None,
    skip_indexing: bool = False,
) -> dict[str, Any]:
    if scenario_id is None:
        project = store.create_project(name="TS4 Comparison Project")
        scenario = store.create_scenario(project_id=project["id"], name="Comparison scenario")
        scenario_id = scenario["id"]

    generation_metadata = None
    if input_variant is not None or date_range is not None:
        generation_metadata = {
            "kind": "case_input_variant",
            "input_variant": input_variant,
            "date_range": date_range,
            "series_bindings": [],
        }
    scenario_version = store.create_scenario_version(
        scenario_id=scenario_id,
        system_case_json={
            "schema_version": "bess_system_dispatch.v1",
            "case_name": "hybrid_system",
            "nodes": [],
            "time_series": [],
        },
        validation_payload={"status": "ok"},
        generation_metadata=generation_metadata,
    )
    run = store.create_run(scenario_version_id=scenario_version["id"])

    output_dir = artifact_root / f"run-{run['id']}" / "outputs"
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
                "objective_value_usd": objective_value_usd,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    rows = dispatch_rows if dispatch_rows is not None else DEFAULT_DISPATCH_ROWS
    lines = [",".join(DISPATCH_COLUMNS)]
    for row in rows:
        lines.append(",".join(str(row[column]) for column in DISPATCH_COLUMNS))
    dispatch_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    asset_dispatch_path.write_text(
        "timestamp,asset_id,asset_type\n2026-01-01T00:00:00,grid_1,grid\n",
        encoding="utf-8",
    )

    store.mark_run_running(
        run["id"],
        workspace_path=str(artifact_root / f"run-{run['id']}"),
        input_snapshot_path=str(output_dir / "input" / "system_case.json"),
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

    if not skip_indexing:
        index_run_results(store=store, run=run, artifact_root=artifact_root)

    return run


class CompareRunsKpiAndContextTests(unittest.TestCase):
    def test_compares_kpis_and_shows_run_context_for_two_indexed_runs_of_the_same_case(self):
        from app.result_comparison import compare_runs

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                baseline_run = create_indexed_run(
                    store,
                    artifact_root,
                    objective_value_usd=1000.0,
                    input_variant={"id": 1, "display_name": "Default"},
                    date_range={"start": "2026-01-01T00:00:00", "end": "2026-01-02T00:00:00"},
                )
                candidate_run = create_indexed_run(
                    store,
                    artifact_root,
                    scenario_id=store.get_run_lineage(baseline_run["id"])["scenario_id"],
                    objective_value_usd=1200.0,
                    input_variant={"id": 2, "display_name": "Dry year"},
                    date_range={"start": "2026-01-01T00:00:00", "end": "2026-01-02T00:00:00"},
                )

                comparison = compare_runs(
                    store=store,
                    baseline_run_id=baseline_run["id"],
                    candidate_run_id=candidate_run["id"],
                )

                objective_kpi = next(k for k in comparison["kpis"] if k["key"] == "objective_value_usd")
                self.assertEqual(objective_kpi["baseline"], 1000.0)
                self.assertEqual(objective_kpi["candidate"], 1200.0)
                self.assertEqual(objective_kpi["delta"], 200.0)

                self.assertEqual(comparison["baseline"]["run_id"], baseline_run["id"])
                self.assertEqual(comparison["candidate"]["run_id"], candidate_run["id"])
                self.assertEqual(
                    comparison["baseline"]["input_variant"], {"id": 1, "display_name": "Default"}
                )
                self.assertEqual(
                    comparison["candidate"]["input_variant"], {"id": 2, "display_name": "Dry year"}
                )
            finally:
                store.close()


class ComparePeriodLevelSeriesDiffTests(unittest.TestCase):
    def test_diffs_a_selected_series_period_by_period_between_two_runs(self):
        from app.result_comparison import compare_runs

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                baseline_rows = [
                    {**DEFAULT_DISPATCH_ROWS[0], "timestamp": "2026-01-01T00:00:00", "grid_import_mw": "2.5"},
                    {**DEFAULT_DISPATCH_ROWS[0], "timestamp": "2026-01-01T01:00:00", "grid_import_mw": "3.0"},
                ]
                candidate_rows = [
                    {**DEFAULT_DISPATCH_ROWS[0], "timestamp": "2026-01-01T00:00:00", "grid_import_mw": "4.0"},
                    {**DEFAULT_DISPATCH_ROWS[0], "timestamp": "2026-01-01T01:00:00", "grid_import_mw": "1.0"},
                ]
                baseline_run = create_indexed_run(store, artifact_root, dispatch_rows=baseline_rows)
                candidate_run = create_indexed_run(
                    store,
                    artifact_root,
                    scenario_id=store.get_run_lineage(baseline_run["id"])["scenario_id"],
                    dispatch_rows=candidate_rows,
                )

                comparison = compare_runs(
                    store=store,
                    baseline_run_id=baseline_run["id"],
                    candidate_run_id=candidate_run["id"],
                    series="grid_import_power_mw",
                )

                self.assertEqual(comparison["selected_series"], "grid_import_power_mw")
                self.assertIn("grid_import_power_mw", comparison["available_signal_keys"])
                periods = comparison["series_periods"]
                self.assertEqual(
                    periods,
                    [
                        {
                            "timestamp": "2026-01-01T00:00:00",
                            "baseline": 2.5,
                            "candidate": 4.0,
                            "delta": 1.5,
                        },
                        {
                            "timestamp": "2026-01-01T01:00:00",
                            "baseline": 3.0,
                            "candidate": 1.0,
                            "delta": -2.0,
                        },
                    ],
                )
            finally:
                store.close()

    def test_defaults_to_a_common_series_when_none_is_selected(self):
        from app.result_comparison import compare_runs

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                baseline_run = create_indexed_run(store, artifact_root)
                candidate_run = create_indexed_run(
                    store,
                    artifact_root,
                    scenario_id=store.get_run_lineage(baseline_run["id"])["scenario_id"],
                )

                comparison = compare_runs(
                    store=store,
                    baseline_run_id=baseline_run["id"],
                    candidate_run_id=candidate_run["id"],
                )

                self.assertIsNotNone(comparison["selected_series"])
                self.assertIn(comparison["selected_series"], comparison["available_signal_keys"])
                self.assertIsNotNone(comparison["series_periods"])
            finally:
                store.close()


class CompareRunsGracefulFailureTests(unittest.TestCase):
    def test_fails_gracefully_pointing_at_the_rebuild_path_when_a_run_has_no_indexed_results(self):
        from app.result_comparison import ComparisonError, compare_runs

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                baseline_run = create_indexed_run(store, artifact_root)
                candidate_run = create_indexed_run(
                    store,
                    artifact_root,
                    scenario_id=store.get_run_lineage(baseline_run["id"])["scenario_id"],
                    skip_indexing=True,
                )

                with self.assertRaises(ComparisonError) as context:
                    compare_runs(
                        store=store,
                        baseline_run_id=baseline_run["id"],
                        candidate_run_id=candidate_run["id"],
                    )

                self.assertIn("rebuild-results", context.exception.message)
                self.assertIn(str(candidate_run["id"]), context.exception.message)
                self.assertEqual(context.exception.status_code, 409)
            finally:
                store.close()

    def test_fails_when_the_two_runs_belong_to_different_cases(self):
        from app.result_comparison import ComparisonError, compare_runs

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                baseline_run = create_indexed_run(store, artifact_root)
                candidate_run = create_indexed_run(store, artifact_root)

                with self.assertRaises(ComparisonError) as context:
                    compare_runs(
                        store=store,
                        baseline_run_id=baseline_run["id"],
                        candidate_run_id=candidate_run["id"],
                    )

                self.assertIn("same case", context.exception.message)
                self.assertEqual(context.exception.status_code, 422)
            finally:
                store.close()


class CompareRunsDifferentVariantsAndRangesTests(unittest.TestCase):
    def test_shows_differing_input_variants_for_both_runs(self):
        from app.result_comparison import compare_runs

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                baseline_run = create_indexed_run(
                    store,
                    artifact_root,
                    input_variant={"id": 1, "display_name": "Default"},
                    date_range={"start": "2026-01-01T00:00:00", "end": "2026-01-02T00:00:00"},
                )
                candidate_run = create_indexed_run(
                    store,
                    artifact_root,
                    scenario_id=store.get_run_lineage(baseline_run["id"])["scenario_id"],
                    input_variant={"id": 2, "display_name": "Hidrologia seca"},
                    date_range={"start": "2026-01-01T00:00:00", "end": "2026-01-02T00:00:00"},
                )

                comparison = compare_runs(
                    store=store,
                    baseline_run_id=baseline_run["id"],
                    candidate_run_id=candidate_run["id"],
                )

                self.assertEqual(
                    comparison["baseline"]["input_variant"], {"id": 1, "display_name": "Default"}
                )
                self.assertEqual(
                    comparison["candidate"]["input_variant"],
                    {"id": 2, "display_name": "Hidrologia seca"},
                )
                self.assertNotEqual(
                    comparison["baseline"]["input_variant"], comparison["candidate"]["input_variant"]
                )
            finally:
                store.close()

    def test_shows_differing_date_ranges_and_diffs_only_overlapping_periods(self):
        from app.result_comparison import compare_runs

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                baseline_rows = [
                    {**DEFAULT_DISPATCH_ROWS[0], "timestamp": "2026-01-01T00:00:00", "grid_import_mw": "1.0"},
                    {**DEFAULT_DISPATCH_ROWS[0], "timestamp": "2026-01-01T01:00:00", "grid_import_mw": "2.0"},
                ]
                candidate_rows = [
                    {**DEFAULT_DISPATCH_ROWS[0], "timestamp": "2026-01-01T01:00:00", "grid_import_mw": "5.0"},
                    {**DEFAULT_DISPATCH_ROWS[0], "timestamp": "2026-01-01T02:00:00", "grid_import_mw": "6.0"},
                ]
                baseline_run = create_indexed_run(
                    store,
                    artifact_root,
                    date_range={"start": "2026-01-01T00:00:00", "end": "2026-01-01T02:00:00"},
                    dispatch_rows=baseline_rows,
                )
                candidate_run = create_indexed_run(
                    store,
                    artifact_root,
                    scenario_id=store.get_run_lineage(baseline_run["id"])["scenario_id"],
                    date_range={"start": "2026-01-01T01:00:00", "end": "2026-01-01T03:00:00"},
                    dispatch_rows=candidate_rows,
                )

                comparison = compare_runs(
                    store=store,
                    baseline_run_id=baseline_run["id"],
                    candidate_run_id=candidate_run["id"],
                    series="grid_import_power_mw",
                )

                self.assertNotEqual(
                    comparison["baseline"]["date_range"], comparison["candidate"]["date_range"]
                )
                periods_by_timestamp = {p["timestamp"]: p for p in comparison["series_periods"]}
                self.assertEqual(
                    periods_by_timestamp["2026-01-01T00:00:00"],
                    {
                        "timestamp": "2026-01-01T00:00:00",
                        "baseline": 1.0,
                        "candidate": None,
                        "delta": None,
                    },
                )
                self.assertEqual(
                    periods_by_timestamp["2026-01-01T01:00:00"],
                    {
                        "timestamp": "2026-01-01T01:00:00",
                        "baseline": 2.0,
                        "candidate": 5.0,
                        "delta": 3.0,
                    },
                )
                self.assertEqual(
                    periods_by_timestamp["2026-01-01T02:00:00"],
                    {
                        "timestamp": "2026-01-01T02:00:00",
                        "baseline": None,
                        "candidate": 6.0,
                        "delta": None,
                    },
                )
            finally:
                store.close()


class CompareRunsApiTests(unittest.TestCase):
    def test_get_run_comparisons_returns_the_comparison_for_two_indexed_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                baseline_run = create_indexed_run(store, artifact_root, objective_value_usd=1000.0)
                candidate_run = create_indexed_run(
                    store,
                    artifact_root,
                    scenario_id=store.get_run_lineage(baseline_run["id"])["scenario_id"],
                    objective_value_usd=1500.0,
                )
                client = TestClient(
                    create_app(
                        validation_service=StubValidationService(),
                        store=store,
                        run_queue=RecordingRunQueue(),
                        artifact_root=artifact_root,
                    )
                )

                response = client.get(
                    "/api/run-comparisons",
                    params={
                        "baseline_run_id": baseline_run["id"],
                        "candidate_run_id": candidate_run["id"],
                    },
                )

                self.assertEqual(response.status_code, 200)
                comparison = response.json()["comparison"]
                self.assertEqual(comparison["baseline"]["run_id"], baseline_run["id"])
                self.assertEqual(comparison["candidate"]["run_id"], candidate_run["id"])
                objective_kpi = next(k for k in comparison["kpis"] if k["key"] == "objective_value_usd")
                self.assertEqual(objective_kpi["delta"], 500.0)
            finally:
                store.close()

    def test_get_run_comparisons_reports_a_non_indexed_run_gracefully(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                baseline_run = create_indexed_run(store, artifact_root)
                candidate_run = create_indexed_run(
                    store,
                    artifact_root,
                    scenario_id=store.get_run_lineage(baseline_run["id"])["scenario_id"],
                    skip_indexing=True,
                )
                client = TestClient(
                    create_app(
                        validation_service=StubValidationService(),
                        store=store,
                        run_queue=RecordingRunQueue(),
                        artifact_root=artifact_root,
                    )
                )

                response = client.get(
                    "/api/run-comparisons",
                    params={
                        "baseline_run_id": baseline_run["id"],
                        "candidate_run_id": candidate_run["id"],
                    },
                )

                self.assertEqual(response.status_code, 409)
                self.assertIn("rebuild-results", response.json()["message"])

            finally:
                store.close()

    def test_get_run_comparisons_returns_404_for_a_missing_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                baseline_run = create_indexed_run(store, artifact_root)
                client = TestClient(
                    create_app(
                        validation_service=StubValidationService(),
                        store=store,
                        run_queue=RecordingRunQueue(),
                        artifact_root=artifact_root,
                    )
                )

                response = client.get(
                    "/api/run-comparisons",
                    params={"baseline_run_id": baseline_run["id"], "candidate_run_id": 999},
                )

                self.assertEqual(response.status_code, 404)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
