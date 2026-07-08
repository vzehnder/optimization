import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore, derive_case_hierarchy_provenance
from app.result_indexing import (
    index_run_asset_dispatch_results,
    index_run_dispatch_results,
    index_run_results,
    index_run_summary_results,
    rebuild_all_run_results,
    rebuild_run_results,
)
from app.results import read_run_results
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    CatalogValueEdit,
    prepare_time_series_catalog_import,
)
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

    def test_indexes_summary_json_into_bbdd_linked_to_run_and_indexed_result_surfaces(self):
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
                index_run_asset_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )

                indexed = index_run_summary_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )

                self.assertIsNotNone(indexed)
                self.assertEqual(indexed["run_id"], run["id"])
                self.assertEqual(indexed["scenario_version_id"], run["scenario_version_id"])
                self.assertEqual(indexed["summary"]["solver_status"], "OPTIMAL")
                self.assertEqual(indexed["summary"]["termination_status"], "OPTIMAL")
                self.assertEqual(indexed["summary"]["objective_value_usd"], 1250.5)
                self.assertEqual(
                    indexed["linked_result_surfaces"],
                    ["dispatch_table", "asset_dispatch_table"],
                )
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

    def test_read_run_results_prefers_indexed_summary_over_json_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])
                index_run_summary_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )

                summary_path = artifact_root / "runs" / "1" / "outputs" / "summary.json"
                summary_path.unlink()

                results = read_run_results(run, artifacts, artifact_root, store=store)

                self.assertEqual(results["summary"]["case_name"], "hybrid_system")
                self.assertEqual(results["summary"]["termination_status"], "OPTIMAL")
                self.assertEqual(results["summary"]["objective_value_usd"], 1250.5)
            finally:
                store.close()

    def test_results_api_prefers_indexed_summary_over_json_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])
                index_run_summary_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )
                summary_path = artifact_root / "runs" / "1" / "outputs" / "summary.json"
                summary_path.unlink()
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
                    response.json()["results"]["summary"]["termination_status"],
                    "OPTIMAL",
                )
                self.assertEqual(
                    response.json()["results"]["summary"]["objective_value_usd"],
                    1250.5,
                )
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


class ResultIndexingIdempotencyTests(unittest.TestCase):
    def test_reindexing_an_already_indexed_run_converges_without_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])

                index_run_dispatch_results(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)
                index_run_dispatch_results(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)
                index_run_asset_dispatch_results(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)
                index_run_asset_dispatch_results(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)
                index_run_summary_results(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)
                index_run_summary_results(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)

                dispatch_row_count = store.connection.execute(
                    "SELECT COUNT(*) AS c FROM run_dispatch_result_rows WHERE run_id = ?", (run["id"],)
                ).fetchone()["c"]
                asset_row_count = store.connection.execute(
                    "SELECT COUNT(*) AS c FROM run_asset_dispatch_result_rows WHERE run_id = ?", (run["id"],)
                ).fetchone()["c"]
                summary_index_count = store.connection.execute(
                    "SELECT COUNT(*) AS c FROM run_summary_result_indexes WHERE run_id = ?", (run["id"],)
                ).fetchone()["c"]

                self.assertEqual(dispatch_row_count, 1)
                self.assertEqual(asset_row_count, 1)
                self.assertEqual(summary_index_count, 1)
            finally:
                store.close()

    def test_reindexing_after_artifact_content_change_drops_stale_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])
                index_run_dispatch_results(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)

                dispatch_path = artifact_root / "runs" / "1" / "outputs" / "dispatch.csv"
                dispatch_path.write_text(
                    "timestamp,duration_hours,price_usd_per_mwh,grid_import_mw,grid_export_mw,market_value_usd,"
                    "battery_charge_mw,battery_discharge_mw,battery_energy_mwh,period_profit_usd\n"
                    "2026-01-01T00:00:00,1.0,45.0,2.5,0.0,-112.5,0.0,0.0,20.0,-112.5\n"
                    "2026-01-01T01:00:00,1.0,46.0,3.0,0.0,-138.0,0.0,0.0,25.0,-138.0\n",
                    encoding="utf-8",
                )

                reindexed = index_run_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )

                self.assertEqual(len(reindexed["rows"]), 2)
                row_count = store.connection.execute(
                    "SELECT COUNT(*) AS c FROM run_dispatch_result_rows WHERE run_id = ?", (run["id"],)
                ).fetchone()["c"]
                self.assertEqual(row_count, 2)
            finally:
                store.close()


class ResultIndexingFailureSafetyTests(unittest.TestCase):
    def test_partial_row_failure_leaves_no_dispatch_index_and_is_safe_to_retry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                dispatch_path = artifact_root / "runs" / "1" / "outputs" / "dispatch.csv"
                dispatch_path.write_text(
                    "timestamp,duration_hours,price_usd_per_mwh,grid_import_mw,grid_export_mw,market_value_usd,"
                    "battery_charge_mw,battery_discharge_mw,battery_energy_mwh,period_profit_usd\n"
                    "2026-01-01T00:00:00,1.0,45.0,2.5,0.0,-112.5,0.0,0.0,20.0,-112.5\n"
                    "2026-01-01T00:00:00,1.0,46.0,3.0,0.0,-138.0,0.0,0.0,25.0,-138.0\n",
                    encoding="utf-8",
                )

                with self.assertLogs("app.result_indexing", level="ERROR") as logs:
                    outcome = index_run_results(store=store, run=run, artifact_root=artifact_root)

                self.assertIn("dispatch_table", outcome["failed"])
                self.assertEqual(set(outcome["indexed"]), {"asset_dispatch_table", "summary"})
                self.assertTrue(any(str(run["id"]) in message for message in logs.output))

                self.assertIsNone(store.get_run_dispatch_result_index(run["id"]))
                self.assertEqual(store.get_run(run["id"])["status"], "succeeded")
                self.assertEqual(len(store.list_run_artifacts(run["id"])), 3)

                results = read_run_results(run, store.list_run_artifacts(run["id"]), artifact_root, store=store)
                self.assertEqual(len(results["dispatch_table"]["rows"]), 2)

                dispatch_path.write_text(
                    "timestamp,duration_hours,price_usd_per_mwh,grid_import_mw,grid_export_mw,market_value_usd,"
                    "battery_charge_mw,battery_discharge_mw,battery_energy_mwh,period_profit_usd\n"
                    "2026-01-01T00:00:00,1.0,45.0,2.5,0.0,-112.5,0.0,0.0,20.0,-112.5\n",
                    encoding="utf-8",
                )

                retried = index_run_results(store=store, run=run, artifact_root=artifact_root)

                self.assertEqual(retried["failed"], {})
                self.assertIn("dispatch_table", retried["indexed"])
                indexed = store.get_run_dispatch_result_index(run["id"])
                self.assertIsNotNone(indexed)
                self.assertEqual(len(indexed["rows"]), 1)
            finally:
                store.close()

    def test_malformed_summary_does_not_block_dispatch_or_asset_dispatch_indexing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                summary_path = artifact_root / "runs" / "1" / "outputs" / "summary.json"
                summary_path.write_text("not json", encoding="utf-8")

                outcome = index_run_results(store=store, run=run, artifact_root=artifact_root)

                self.assertIn("summary", outcome["failed"])
                self.assertEqual(set(outcome["indexed"]), {"dispatch_table", "asset_dispatch_table"})
                self.assertIsNotNone(store.get_run_dispatch_result_index(run["id"]))
                self.assertIsNotNone(store.get_run_asset_dispatch_result_index(run["id"]))
                self.assertIsNone(store.get_run_summary_result_index(run["id"]))
                self.assertEqual(store.get_run(run["id"])["status"], "succeeded")
            finally:
                store.close()


class ResultLineageIndexingTests(unittest.TestCase):
    def test_indexed_result_surfaces_store_full_frozen_run_lineage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                generation_metadata = {
                    "kind": "case_input_variant",
                    "topology": {"content_hash": "sha256:topology-v1"},
                    "parameters": {"content_hash": "sha256:parameters-v1"},
                    "input_variant": {"id": 7, "display_name": "Dry year"},
                    "date_range": {
                        "start": "2026-01-01T00:00:00",
                        "end": "2026-01-01T01:00:00",
                    },
                    "series_bindings": [
                        {
                            "signal_key": "import_price_usd_per_mwh",
                            "entity_type": None,
                            "entity_id": None,
                            "time_series_set_id": 11,
                            "version_number": 2,
                            "version_label": "dry_year_v2",
                            "revision_number": 3,
                            "content_hash": "sha256:series-price-v3",
                            "validated_range": {
                                "start": "2026-01-01T00:00:00",
                                "end": "2026-01-01T01:00:00",
                            },
                        }
                    ],
                }
                run = create_completed_run_with_core_dispatch_artifacts(
                    store, artifact_root, generation_metadata=generation_metadata
                )
                scenario_version = store.get_scenario_version(
                    int(run["scenario_version_id"]), include_document=False
                )
                scenario_metadata = scenario_version["generation_metadata"]
                artifacts = store.list_run_artifacts(run["id"])

                dispatch_index = index_run_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )
                asset_dispatch_index = index_run_asset_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )
                summary_index = index_run_summary_results(
                    store=store,
                    run=run,
                    artifacts=artifacts,
                    artifact_root=artifact_root,
                )

                expected_lineage = {
                    "run_id": run["id"],
                    "scenario_version_id": run["scenario_version_id"],
                    "case": {
                        "scenario_id": scenario_version["scenario_id"],
                        "case_name": scenario_version["case_name"],
                    },
                    "topology_hash": scenario_metadata["topology"]["content_hash"],
                    "parameters_hash": scenario_metadata["parameters"]["content_hash"],
                    "input_variant": {"id": 7, "display_name": "Dry year"},
                    "date_range": {
                        "start": "2026-01-01T00:00:00",
                        "end": "2026-01-01T01:00:00",
                    },
                    "input_series": [
                        {
                            "signal_key": "import_price_usd_per_mwh",
                            "entity_type": None,
                            "entity_id": None,
                            "time_series_set_id": 11,
                            "version_number": 2,
                            "version_label": "dry_year_v2",
                            "revision_number": 3,
                            "content_hash": "sha256:series-price-v3",
                        }
                    ],
                }
                self.assertEqual(dispatch_index["lineage"], expected_lineage)
                self.assertEqual(asset_dispatch_index["lineage"], expected_lineage)
                self.assertEqual(summary_index["lineage"], expected_lineage)
            finally:
                store.close()

    def test_legacy_run_indexes_absent_variant_lineage_fields_without_fabrication(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(
                    store,
                    artifact_root,
                    generation_metadata={"topology": {"content_hash": "sha256:legacy-topology"}},
                )
                scenario_version = store.get_scenario_version(
                    int(run["scenario_version_id"]), include_document=False
                )

                indexed = index_run_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=store.list_run_artifacts(run["id"]),
                    artifact_root=artifact_root,
                )

                self.assertEqual(
                    indexed["lineage"]["topology_hash"],
                    scenario_version["generation_metadata"]["topology"]["content_hash"],
                )
                self.assertEqual(
                    indexed["lineage"]["parameters_hash"],
                    scenario_version["generation_metadata"]["parameters"]["content_hash"],
                )
                self.assertIsNone(indexed["lineage"]["input_variant"])
                self.assertIsNone(indexed["lineage"]["date_range"])
                self.assertEqual(indexed["lineage"]["input_series"], [])
            finally:
                store.close()

    def test_indexed_lineage_stays_frozen_after_live_series_topology_and_parameter_edits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                prepared = prepare_time_series_catalog_import(
                    rows=price_rows(datetime(2026, 1, 1), 3),
                    request=price_import_request(),
                )
                project = store.create_project(name="TS4 lineage project")
                scenario = store.create_scenario(project_id=project["id"], name="TS4 lineage scenario")
                store.create_or_replace_scenario_draft(
                    scenario_id=scenario["id"], document=grid_battery_draft_document()
                )
                optimization_case = store.get_or_create_case_for_scenario(scenario["id"])
                variant = store.get_or_create_default_input_variant(optimization_case["id"])
                price_set = store.import_time_series_catalog_set(
                    scenario_id=scenario["id"],
                    source={
                        "id": "csv_source_1",
                        "original_filename": "price.csv",
                        "media_type": "text/csv",
                        "checksum": "sha256:price-v1",
                    },
                    prepared_import=prepared,
                )
                store.upsert_case_time_series_binding(
                    case_input_variant_id=variant["id"],
                    signal_key="import_price_usd_per_mwh",
                    time_series_set_id=price_set["id"],
                )
                materialized = store.materialize_system_case_for_variant(
                    scenario_id=scenario["id"],
                    case_input_variant_id=variant["id"],
                    range_start=price_set["horizon"]["start"],
                    range_end=price_set["horizon"]["end"],
                )
                scenario_version = store.create_scenario_version(
                    scenario_id=scenario["id"],
                    system_case_json=materialized["system_case"],
                    validation_payload={"status": "ok"},
                    generation_metadata={
                        "kind": "case_input_variant",
                        "input_variant": {"id": variant["id"], "display_name": variant["display_name"]},
                        "date_range": {
                            "start": price_set["horizon"]["start"],
                            "end": price_set["horizon"]["end"],
                        },
                        "series_bindings": materialized["series_bindings"],
                    },
                )
                run = create_completed_run_with_core_dispatch_artifacts(
                    store,
                    artifact_root,
                    scenario_version=scenario_version,
                )

                indexed = index_run_dispatch_results(
                    store=store,
                    run=run,
                    artifacts=store.list_run_artifacts(run["id"]),
                    artifact_root=artifact_root,
                )
                frozen_lineage = indexed["lineage"]

                store.edit_time_series_set_values(
                    project_id=project["id"],
                    time_series_set_id=price_set["id"],
                    edits=[
                        CatalogValueEdit(
                            period_index=0,
                            signal_key="import_price_usd_per_mwh",
                            value_text="99.0",
                        )
                    ],
                    created_by="lineage-test@example.local",
                )
                mutated_draft = grid_battery_draft_document()
                mutated_draft["assets"][0]["charge_power_max_mw"] = 9.0
                mutated_draft["assets"].append(
                    {
                        "id": "battery_2",
                        "type": "battery",
                        "charge_power_max_mw": 2.0,
                        "discharge_power_max_mw": 2.0,
                        "energy_min_mwh": 0.0,
                        "energy_max_mwh": 4.0,
                        "initial_energy_mwh": 2.0,
                        "charge_efficiency": 0.95,
                        "discharge_efficiency": 0.95,
                        "degradation_cost_per_mwh_delta_soc": 0.0,
                        "terminal_condition": "none",
                        "prevent_simultaneous_charge_discharge": True,
                        "degradation_linear_delta_soc": True,
                    }
                )
                store.update_scenario_draft(
                    scenario_id=scenario["id"],
                    document=mutated_draft,
                )

                live_materialized = store.validate_case_input_variant(
                    scenario_id=scenario["id"],
                    case_input_variant_id=variant["id"],
                    range_start=price_set["horizon"]["start"],
                    range_end=price_set["horizon"]["end"],
                )
                live_price_set = store.get_time_series_set(project["id"], price_set["id"])
                live_provenance = derive_case_hierarchy_provenance(live_materialized["system_case"])
                reloaded = store.get_run_dispatch_result_index(run["id"])

                self.assertEqual(reloaded["lineage"], frozen_lineage)
                self.assertNotEqual(
                    live_price_set["content_hash"],
                    frozen_lineage["input_series"][0]["content_hash"],
                )
                self.assertNotEqual(
                    live_provenance["topology"]["content_hash"],
                    frozen_lineage["topology_hash"],
                )
                self.assertNotEqual(
                    live_provenance["parameters"]["content_hash"],
                    frozen_lineage["parameters_hash"],
                )
            finally:
                store.close()


def create_completed_run_with_core_dispatch_artifacts(
    store: AnalystStore,
    artifact_root: Path,
    *,
    generation_metadata: dict | None = None,
    scenario_version: dict | None = None,
) -> dict:
    output_dir = artifact_root / "runs" / "1" / "outputs"
    output_dir.mkdir(parents=True)
    summary_path = output_dir / "summary.json"
    dispatch_path = output_dir / "dispatch.csv"
    asset_dispatch_path = output_dir / "asset_dispatch.csv"
    case_name = str((scenario_version or {}).get("case_name") or "hybrid_system")
    summary_path.write_text(
        json.dumps(
            {
                "case_name": case_name,
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

    if scenario_version is None:
        project = store.create_project(name="TS4 Project")
        scenario = store.create_scenario(project_id=project["id"], name="Base case")
        scenario_version = store.create_scenario_version(
            scenario_id=scenario["id"],
            system_case_json={
                "schema_version": "bess_system_dispatch.v1",
                "case_name": case_name,
                "nodes": [],
                "time_series": [],
            },
            validation_payload={"status": "ok"},
            generation_metadata=generation_metadata,
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


def price_import_request(*, signal_key="import_price_usd_per_mwh", version_label="v1"):
    return CatalogImportRequest(
        set_name="Spot price",
        version_label=version_label,
        data_kind="real",
        timezone="America/Santiago",
        timestamp_column="period_start",
        duration_hours_column="hours",
        signal_mappings=[
            CatalogSignalMappingRequest(source_column="spot_price", signal_key=signal_key),
        ],
    )


def price_rows(start: datetime, count: int, *, value: float = 50.0):
    rows = []
    for hour in range(count):
        instant = start + timedelta(hours=hour)
        rows.append(
            {
                "period_start": instant.isoformat(),
                "hours": "1.0",
                "spot_price": str(value + hour),
            }
        )
    return rows


def grid_battery_draft_document():
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": "grid_battery_case", "description": ""},
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
        ],
        "time_series": {"sources": []},
        "solver": {"name": "HiGHS", "options": {}},
    }


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


class MixedSurfaceReadPathTests(unittest.TestCase):
    def test_read_run_results_degrades_gracefully_per_surface_for_a_partially_indexed_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])
                index_run_dispatch_results(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)
                index_run_summary_results(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)

                dispatch_path = artifact_root / "runs" / "1" / "outputs" / "dispatch.csv"
                summary_path = artifact_root / "runs" / "1" / "outputs" / "summary.json"
                dispatch_path.unlink()
                summary_path.unlink()

                results = read_run_results(run, artifacts, artifact_root, store=store)

                self.assertEqual(results["dispatch_table"]["rows"][0]["grid_import_mw"], "2.5")
                self.assertEqual(results["summary"]["objective_value_usd"], 1250.5)
                self.assertEqual(results["asset_dispatch_table"]["rows"][0]["asset_id"], "grid_1")
            finally:
                store.close()

    def test_results_api_serves_partially_indexed_run_without_failing_whole_view(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                artifacts = store.list_run_artifacts(run["id"])
                index_run_dispatch_results(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)
                index_run_summary_results(store=store, run=run, artifacts=artifacts, artifact_root=artifact_root)

                dispatch_path = artifact_root / "runs" / "1" / "outputs" / "dispatch.csv"
                summary_path = artifact_root / "runs" / "1" / "outputs" / "summary.json"
                dispatch_path.unlink()
                summary_path.unlink()

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
                results = response.json()["results"]
                self.assertEqual(results["dispatch_table"]["rows"][0]["grid_import_mw"], "2.5")
                self.assertEqual(results["summary"]["objective_value_usd"], 1250.5)
                self.assertEqual(results["asset_dispatch_table"]["rows"][0]["asset_id"], "grid_1")
                self.assertTrue(results["charts"]["grid_import_export"]["available"])
            finally:
                store.close()


class RebuildRunResultsTests(unittest.TestCase):
    def test_rebuild_indexes_a_never_indexed_historical_run_from_its_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                self.assertIsNone(store.get_run_dispatch_result_index(run["id"]))

                outcome = rebuild_run_results(store=store, run=run, artifact_root=artifact_root)

                self.assertEqual(outcome["run_id"], run["id"])
                self.assertEqual(outcome["status"], "indexed")
                self.assertEqual(
                    set(outcome["indexed"]), {"dispatch_table", "asset_dispatch_table", "summary"}
                )
                self.assertEqual(outcome["failed"], {})
                self.assertIsNotNone(store.get_run_dispatch_result_index(run["id"]))
                self.assertIsNotNone(store.get_run_asset_dispatch_result_index(run["id"]))
                self.assertIsNotNone(store.get_run_summary_result_index(run["id"]))
            finally:
                store.close()

    def test_rebuild_skips_an_already_fully_indexed_run_unless_forced(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                rebuild_run_results(store=store, run=run, artifact_root=artifact_root)
                first_index = store.get_run_dispatch_result_index(run["id"])

                skipped = rebuild_run_results(store=store, run=run, artifact_root=artifact_root)

                self.assertEqual(skipped, {"run_id": run["id"], "status": "skipped", "indexed": [], "failed": {}})
                self.assertEqual(store.get_run_dispatch_result_index(run["id"]), first_index)

                forced = rebuild_run_results(store=store, run=run, artifact_root=artifact_root, force=True)

                self.assertEqual(forced["status"], "indexed")
                self.assertEqual(set(forced["indexed"]), {"dispatch_table", "asset_dispatch_table", "summary"})
            finally:
                store.close()

    def test_rebuild_of_legacy_run_without_ts3_lineage_indexes_absent_lineage_and_serves_from_bbdd(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)

                outcome = rebuild_run_results(store=store, run=run, artifact_root=artifact_root)

                self.assertEqual(outcome["status"], "indexed")
                dispatch_index = store.get_run_dispatch_result_index(run["id"])
                self.assertIsNone(dispatch_index["lineage"]["input_variant"])
                self.assertIsNone(dispatch_index["lineage"]["date_range"])
                self.assertEqual(dispatch_index["lineage"]["input_series"], [])

                dispatch_path = artifact_root / "runs" / "1" / "outputs" / "dispatch.csv"
                dispatch_path.unlink()
                results = read_run_results(
                    run, store.list_run_artifacts(run["id"]), artifact_root, store=store
                )
                self.assertEqual(results["dispatch_table"]["rows"][0]["grid_import_mw"], "2.5")
            finally:
                store.close()

    def test_rebuild_reports_failed_status_with_surviving_indexed_surfaces_on_a_broken_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                summary_path = artifact_root / "runs" / "1" / "outputs" / "summary.json"
                summary_path.write_text("not json", encoding="utf-8")

                outcome = rebuild_run_results(store=store, run=run, artifact_root=artifact_root)

                self.assertEqual(outcome["status"], "failed")
                self.assertEqual(set(outcome["indexed"]), {"dispatch_table", "asset_dispatch_table"})
                self.assertIn("summary", outcome["failed"])
            finally:
                store.close()


class RebuildResultsApiTests(unittest.TestCase):
    def test_admin_rebuild_run_endpoint_indexes_a_historical_run_and_reports_the_outcome(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                client = TestClient(
                    create_app(
                        validation_service=StubValidationService(),
                        store=store,
                        run_queue=RecordingRunQueue(),
                        artifact_root=artifact_root,
                    )
                )

                response = client.post(f"/api/admin/runs/{run['id']}/rebuild-results")

                self.assertEqual(response.status_code, 200)
                rebuild = response.json()["rebuild"]
                self.assertEqual(rebuild["run_id"], run["id"])
                self.assertEqual(rebuild["status"], "indexed")
                self.assertIsNotNone(store.get_run_dispatch_result_index(run["id"]))
            finally:
                store.close()

    def test_admin_rebuild_all_endpoint_reports_indexed_and_skipped_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                never_indexed_run = create_completed_run_with_core_dispatch_artifacts(
                    store, artifact_root / "never-indexed"
                )
                already_indexed_run = create_completed_run_with_core_dispatch_artifacts(
                    store, artifact_root / "already-indexed"
                )
                rebuild_run_results(
                    store=store, run=already_indexed_run, artifact_root=artifact_root / "already-indexed"
                )
                client = TestClient(
                    create_app(
                        validation_service=StubValidationService(),
                        store=store,
                        run_queue=RecordingRunQueue(),
                        artifact_root=artifact_root,
                    )
                )

                response = client.post("/api/admin/runs/rebuild-results")

                self.assertEqual(response.status_code, 200)
                report = response.json()["rebuild"]
                self.assertEqual(report["indexed"], [never_indexed_run["id"]])
                self.assertEqual(report["skipped"], [already_indexed_run["id"]])
                self.assertEqual(report["failed"], {})
            finally:
                store.close()


class RebuildAllRunResultsTests(unittest.TestCase):
    def test_rebuild_all_reports_indexed_skipped_and_failed_runs_separately(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                never_indexed_run = create_completed_run_with_core_dispatch_artifacts(
                    store, artifact_root / "never-indexed"
                )
                already_indexed_run = create_completed_run_with_core_dispatch_artifacts(
                    store, artifact_root / "already-indexed"
                )
                rebuild_run_results(
                    store=store, run=already_indexed_run, artifact_root=artifact_root / "already-indexed"
                )
                broken_run = create_completed_run_with_core_dispatch_artifacts(
                    store, artifact_root / "broken"
                )
                (artifact_root / "broken" / "runs" / "1" / "outputs" / "summary.json").write_text(
                    "not json", encoding="utf-8"
                )

                report = rebuild_all_run_results(store=store, artifact_root=artifact_root)

                self.assertEqual(report["indexed"], [never_indexed_run["id"]])
                self.assertEqual(report["skipped"], [already_indexed_run["id"]])
                self.assertEqual(list(report["failed"].keys()), [broken_run["id"]])
                self.assertIn("summary", report["failed"][broken_run["id"]])
            finally:
                store.close()

    def test_rebuild_all_is_idempotent_and_converges_to_all_skipped_on_second_pass(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            store = AnalystStore("sqlite:///:memory:")
            try:
                run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root / "run")

                first_pass = rebuild_all_run_results(store=store, artifact_root=artifact_root)
                second_pass = rebuild_all_run_results(store=store, artifact_root=artifact_root)

                self.assertEqual(first_pass["indexed"], [run["id"]])
                self.assertEqual(second_pass["indexed"], [])
                self.assertEqual(second_pass["skipped"], [run["id"]])
            finally:
                store.close()


class ListSucceededRunsTests(unittest.TestCase):
    def test_list_succeeded_runs_returns_only_succeeded_runs_across_all_scenarios(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "artifacts"
            store = AnalystStore("sqlite:///:memory:")
            try:
                succeeded_run = create_completed_run_with_core_dispatch_artifacts(store, artifact_root)
                other_project = store.create_project(name="Other project")
                other_scenario = store.create_scenario(project_id=other_project["id"], name="Other scenario")
                other_version = store.create_scenario_version(
                    scenario_id=other_scenario["id"],
                    system_case_json={
                        "schema_version": "bess_system_dispatch.v1",
                        "case_name": "other",
                        "nodes": [],
                        "time_series": [],
                    },
                    validation_payload={"status": "ok"},
                )
                running_run = store.create_run(scenario_version_id=other_version["id"])
                store.mark_run_running(
                    running_run["id"],
                    workspace_path=str(artifact_root / "runs" / str(running_run["id"])),
                    input_snapshot_path=str(artifact_root / "runs" / str(running_run["id"]) / "input" / "system_case.json"),
                )
                failed_run = store.create_run(scenario_version_id=other_version["id"])
                store.mark_run_failed(
                    failed_run["id"],
                    exit_code=1,
                    stdout="",
                    stderr="boom",
                    error_payload={"status": "error", "message": "boom"},
                )

                succeeded_run_ids = [run["id"] for run in store.list_succeeded_runs()]

                self.assertEqual(succeeded_run_ids, [succeeded_run["id"]])
            finally:
                store.close()


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
