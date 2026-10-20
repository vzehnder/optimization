import copy
import json
import unittest
import tempfile
import io
import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import create_app
from app.runner import JuliaRunExecutor
from app.time_series_catalog import CatalogImportRequest, CatalogSignalMappingRequest, CatalogValueEdit, prepare_time_series_catalog_import
from tests.test_ts3_case_variant_api import RecordingRunQueue, StubValidationService, grid_battery_draft_document


class HydraulicSimulationApiTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.artifact_root = Path(directory.name) / "artifacts"
        self.queue = RecordingRunQueue()
        self.client = TestClient(create_app(database_url="sqlite:///:memory:",
                                           validation_service=StubValidationService(), run_queue=self.queue,
                                           input_source_root=directory.name, artifact_root=self.artifact_root))
        self.store = self.client.app.state.analyst_store
        project = self.store.create_project(name="Hydraulic economics")
        self.scenario = self.store.create_scenario(project_id=project["id"], name="Cascade")
        self.store.create_or_replace_scenario_draft(scenario_id=self.scenario["id"], document=grid_battery_draft_document())
        self.document = json.loads((Path(__file__).parent / "fixtures/reg002_hydraulic.json").read_text())
        for period, inflow in zip(self.document["time_series"], [2, 4, 6, 8]):
            period["timestamp"] += "+00:00"
            period["natural_inflow_m3s"]["reservoir"] = inflow
        self.version = self.store.create_scenario_version(scenario_id=self.scenario["id"],
            system_case_json=self.document, validation_payload={"status": "ok"})
        self.prices = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={"id": "cmg", "original_filename": "cmg.csv", "media_type": "text/csv", "checksum": "cmg-v1"},
            prepared_import=prepare_time_series_catalog_import(
                rows=[{"timestamp": f"2026-01-01T0{i}:00:00+00:00", "duration_hours": "1", "price": str(price)}
                      for i, price in enumerate([10, 20, 80, 100])],
                request=CatalogImportRequest(set_name="CMg", version_label="v1", data_kind="synthetic", timezone="UTC",
                    timestamp_column="timestamp", duration_hours_column="duration_hours",
                    signal_mappings=[CatalogSignalMappingRequest(source_column="price", signal_key="price_usd_per_mwh")]),
            ),
        )
        self.url = f"/api/scenario-versions/{self.version['id']}/hydraulic-simulation"
        self.request = {"range_start": "2026-01-01T00:00:00+00:00", "range_end": "2026-01-01T04:00:00+00:00",
                        "resolution_hours": 2, "objective": "market_value", "price_time_series_set_id": self.prices["id"],
                        "price_signal_key": "price_usd_per_mwh"}

    def test_prepare_and_run_uses_promoted_network_with_prices_and_selected_resolution(self):
        original = copy.deepcopy(self.document)
        preview = self.client.post(self.url + "/preview", json=self.request)
        self.assertEqual(preview.status_code, 200, preview.text)
        prepared = preview.json()
        self.assertEqual(prepared["period_count"], 2)
        self.assertEqual([row["natural_inflow_m3s"] for row in prepared["preview_periods"]],
                         [{"reservoir": 3.0}, {"reservoir": 7.0}])
        self.assertEqual([row["price_usd_per_mwh"] for row in prepared["preview_periods"]], [15.0, 90.0])
        response = self.client.post(self.url + "/run", json={**self.request, "expected_preparation_hash": prepared["preparation_hash"]})
        self.assertEqual(response.status_code, 201, response.text)
        run = response.json()
        frozen = self.client.get(f"/api/scenario-versions/{run['scenario_version_id']}").json()["scenario_version"]
        self.assertEqual(frozen["system_case_json"]["hydraulic_network"], original["hydraulic_network"])
        self.assertEqual(frozen["system_case_json"]["hydraulic_objective"], "market_value")
        self.assertEqual(frozen["system_case_json"]["time_series"], prepared["preview_periods"])
        self.assertEqual(frozen["generation_metadata"]["source_scenario_version_id"], self.version["id"])
        self.assertEqual(frozen["generation_metadata"]["series_bindings"][0]["content_hash"], self.prices["content_hash"])
        source = self.client.get(f"/api/scenario-versions/{self.version['id']}").json()["scenario_version"]
        self.assertEqual(source["system_case_json"], original)
        self.assertEqual(run["status"], "queued")

    def test_import_cmg_file_into_catalog_without_changing_the_draft(self):
        url = f"/api/scenarios/{self.scenario['id']}/hydraulic-simulation/prices"
        response = self.client.post(url, data={"set_name": "CMg October", "timezone_name": "UTC", "data_kind": "synthetic"},
            files={"source_file": ("cmg.csv", b"timestamp,duration_hours,price_usd_per_mwh\n2026-01-01T00:00:00+00:00,4,-20\n", "text/csv")})
        self.assertEqual(response.status_code, 201, response.text)
        imported = response.json()["time_series_set"]
        preview = self.client.post(self.url + "/preview", json={**self.request, "price_time_series_set_id": imported["id"]})
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual([row["price_usd_per_mwh"] for row in preview.json()["preview_periods"]], [-20, -20])
        draft = self.client.get(f"/api/scenarios/{self.scenario['id']}/draft").json()["draft"]
        self.assertEqual(draft["document"]["time_series"], {"sources": []})

    def test_water_values_and_gap_are_frozen_with_the_run_and_require_review(self):
        source = copy.deepcopy(self.document)
        source["solver"]["options"] = {"time_limit": 120, "mip_rel_gap": 0.02}
        source["hydraulic_network"]["nodes"][0]["reservoir"].update(
            terminal_condition="min_terminal", terminal_storage_min_hm3=1, terminal_water_value_usd_per_hm3=1000)
        version = self.store.create_scenario_version(scenario_id=self.scenario["id"], system_case_json=source, validation_payload={"status": "ok"})
        url = f"/api/scenario-versions/{version['id']}/hydraulic-simulation"
        inherited = self.client.post(url + "/preview", json=self.request).json()["generation_metadata"]["hydraulic_simulation"]
        self.assertEqual(inherited["mip_rel_gap"], 0.02)
        self.assertEqual(inherited["terminal_water_values_usd_per_hm3"], {"reservoir": 1000})
        payload = {**self.request, "terminal_water_values_usd_per_hm3": {"reservoir": 50000}, "mip_rel_gap": 0.01}
        preview = self.client.post(url + "/preview", json=payload)
        self.assertEqual(preview.status_code, 200, preview.text)
        prepared = preview.json()
        settings = prepared["generation_metadata"]["hydraulic_simulation"]
        self.assertEqual(settings["terminal_water_values_usd_per_hm3"], {"reservoir": 50000})
        self.assertEqual(settings["mip_rel_gap"], 0.01)
        for change in ({"mip_rel_gap": 0.005}, {"terminal_water_values_usd_per_hm3": {"reservoir": 0}}):
            response = self.client.post(url + "/run", json={**payload, **change, "expected_preparation_hash": prepared["preparation_hash"]})
            self.assertEqual(response.status_code, 409, response.text)
        response = self.client.post(url + "/run", json={**payload, "expected_preparation_hash": prepared["preparation_hash"]})
        self.assertEqual(response.status_code, 201, response.text)
        frozen = self.store.get_scenario_version(response.json()["scenario_version_id"])
        expected = copy.deepcopy(source)
        expected["solver"]["options"]["mip_rel_gap"] = 0.01
        expected["hydraulic_network"]["nodes"][0]["reservoir"]["terminal_water_value_usd_per_hm3"] = 50000
        expected["hydraulic_objective"] = "market_value"
        expected["time_series"] = prepared["preview_periods"]
        self.assertEqual(frozen["system_case_json"], expected)
        self.assertEqual(self.store.get_scenario_version(version["id"])["system_case_json"], source)

    def test_invalid_water_values_and_gap_do_not_create_executions(self):
        for change, status in (
            ({"mip_rel_gap": -0.01}, 422),
            ({"mip_rel_gap": "NaN"}, 422),
            ({"mip_rel_gap": "Infinity"}, 422),
            ({"terminal_water_values_usd_per_hm3": {"reservoir": -1}}, 422),
            ({"terminal_water_values_usd_per_hm3": {"reservoir": "NaN"}}, 422),
            ({"terminal_water_values_usd_per_hm3": {"reservoir": "Infinity"}}, 422),
            ({"terminal_water_values_usd_per_hm3": {"intake": 100}}, 400),
            ({"terminal_water_values_usd_per_hm3": {"missing": 100}}, 400),
            ({"objective": "energy", "terminal_water_values_usd_per_hm3": {"reservoir": 100}}, 400),
        ):
            with self.subTest(change=change):
                response = self.client.post(self.url + "/run", json={**self.request, **change})
                self.assertEqual(response.status_code, status, response.text)
        versions = self.client.get(f"/api/scenarios/{self.scenario['id']}/versions").json()["versions"]
        self.assertEqual(len(versions), 1)
        self.assertEqual(self.queue.enqueued_run_ids, [])

    def test_zero_water_value_and_zero_gap_are_valid_for_energy(self):
        response = self.client.post(self.url + "/preview", json={**self.request, "objective": "energy",
            "terminal_water_values_usd_per_hm3": {"reservoir": 0}, "mip_rel_gap": 0})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["generation_metadata"]["hydraulic_simulation"]["mip_rel_gap"], 0)

    @unittest.skipUnless(shutil.which("julia"), "Julia is required for the solver integration")
    def test_water_value_reaches_the_solver_and_preserves_water(self):
        payload = {**self.request, "terminal_water_values_usd_per_hm3": {"reservoir": 50000}, "mip_rel_gap": 0.01}
        preview = self.client.post(self.url + "/preview", json=payload).json()
        response = self.client.post(self.url + "/run", json={**payload, "expected_preparation_hash": preview["preparation_hash"]})
        self.assertEqual(response.status_code, 201, response.text)
        run = response.json()
        JuliaRunExecutor(store=self.store, artifact_root=self.artifact_root).execute(run["id"])
        completed = self.client.get(f"/api/runs/{run['id']}").json()["run"]
        self.assertEqual(completed["status"], "succeeded", completed.get("error_message"))
        summary = self.client.get(f"/api/runs/{run['id']}/results").json()["results"]["summary"]
        totals = summary["hydraulic_v3_totals"]
        self.assertAlmostEqual(totals["total_generation_mwh"], 0)
        self.assertAlmostEqual(totals["final_storage_hm3"], 10.072)
        self.assertAlmostEqual(totals["terminal_water_value_usd"], 503600)
        self.assertAlmostEqual(summary["objective_value_usd"], 503600)

    def test_run_keeps_the_promoted_diagram_available_with_its_results(self):
        layout = {"schema_version": "hydraulic_diagram_layout.v1", "nodes": [{"technical_key": "reservoir", "x": 80, "y": 120}], "reaches": []}
        self.store.persist_scenario_version_hydraulic_diagram_snapshot(scenario_version_id=self.version["id"], layout_snapshot=layout)
        preview = self.client.post(self.url + "/preview", json=self.request).json()
        run = self.client.post(self.url + "/run", json={**self.request, "expected_preparation_hash": preview["preparation_hash"]}).json()
        snapshot = self.client.get(f"/api/scenario-versions/{run['scenario_version_id']}/hydraulic-diagram-snapshot")
        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        self.assertEqual(snapshot.json()["snapshot"]["layout_snapshot"], layout)

    def test_price_picker_lists_signal_and_coverage_without_all_series_values(self):
        response = self.client.get(f"/api/scenarios/{self.scenario['id']}/hydraulic-simulation/prices")
        self.assertEqual(response.status_code, 200, response.text)
        options = response.json()["time_series_sets"]
        self.assertEqual([item["id"] for item in options], [self.prices["id"]])
        self.assertEqual(options[0]["signals"][0]["signal_key"], "price_usd_per_mwh")
        self.assertEqual(options[0]["horizon"]["period_count"], 4)
        self.assertNotIn("values", options[0])

    def test_excel_cmg_with_offset_is_aligned_to_a_finer_utc_horizon(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["timestamp", "duration_hours", "price_usd_per_mwh"])
        sheet.append(["2025-12-31T21:00:00-03:00", 2, 10])
        sheet.append(["2025-12-31T23:00:00-03:00", 2, 50])
        stream = io.BytesIO()
        workbook.save(stream)
        uploaded = self.client.post(f"/api/scenarios/{self.scenario['id']}/hydraulic-simulation/prices",
            data={"set_name": "CMg Excel", "timezone_name": "America/Santiago"},
            files={"source_file": ("cmg.xlsx", stream.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        response = self.client.post(self.url + "/preview", json={**self.request,
            "range_start": "2026-01-01T01:00:00Z", "range_end": "2026-01-01T03:00:00Z", "resolution_hours": 0.5,
            "price_time_series_set_id": uploaded.json()["time_series_set"]["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        rows = response.json()["preview_periods"]
        self.assertEqual([row["price_usd_per_mwh"] for row in rows], [10, 10, 50, 50])
        self.assertEqual([row["natural_inflow_m3s"] for row in rows], [{"reservoir": 4}, {"reservoir": 4}, {"reservoir": 6}, {"reservoir": 6}])
        self.assertEqual([row["duration_hours"] for row in rows], [0.5] * 4)

    def test_reimported_cmg_creates_a_version_and_preserves_the_previous_values(self):
        url = f"/api/scenarios/{self.scenario['id']}/hydraulic-simulation/prices"
        imported = []
        for price in (30, 90, 90):
            response = self.client.post(url, data={"set_name": "Repeated CMg"}, files={"source_file":
                ("cmg.csv", f"timestamp,duration_hours,price_usd_per_mwh\n2026-01-01T00:00:00Z,4,{price}\n".encode(), "text/csv")})
            self.assertEqual(response.status_code, 201, response.text)
            imported.append(response.json()["time_series_set"])
        self.assertEqual([item["version_number"] for item in imported], [1, 2, 2])
        self.assertEqual(imported[1]["id"], imported[2]["id"])
        original = self.client.post(self.url + "/preview", json={**self.request, "price_time_series_set_id": imported[0]["id"]})
        self.assertEqual([row["price_usd_per_mwh"] for row in original.json()["preview_periods"]], [30, 30])

    def test_price_edit_requires_a_new_review_and_does_not_change_an_existing_run(self):
        preview = self.client.post(self.url + "/preview", json=self.request).json()
        payload = {**self.request, "expected_preparation_hash": preview["preparation_hash"]}
        response = self.client.post(self.url + "/run", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        run = response.json()
        self.store.edit_time_series_set_values(project_id=self.scenario["project_id"], time_series_set_id=self.prices["id"],
            edits=[CatalogValueEdit(period_index=0, signal_key="price_usd_per_mwh", value_text="1000")])
        blocked = self.client.post(self.url + "/run", json=payload)
        self.assertEqual(blocked.status_code, 409, blocked.text)
        version = self.client.get(f"/api/scenario-versions/{run['scenario_version_id']}").json()["scenario_version"]
        self.assertEqual([row["price_usd_per_mwh"] for row in version["system_case_json"]["time_series"]], [15, 90])
        versions = self.client.get(f"/api/scenarios/{self.scenario['id']}/versions").json()["versions"]
        self.assertEqual(len(versions), 2)

    def test_derived_cmg_must_be_regenerated_when_its_source_changes(self):
        derived = self.store.apply_time_series_transformation(project_id=self.scenario["project_id"],
            time_series_set_id=self.prices["id"], transformation_type="scale_signal",
            raw_parameters={"signal_key": "price_usd_per_mwh", "scale_factor": 2})
        self.store.edit_time_series_set_values(project_id=self.scenario["project_id"], time_series_set_id=self.prices["id"],
            edits=[CatalogValueEdit(period_index=0, signal_key="price_usd_per_mwh", value_text="1000")])
        response = self.client.post(self.url + "/preview", json={**self.request, "price_time_series_set_id": derived["id"]})
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("desactualizada", response.json()["detail"])

    def test_incomplete_inputs_do_not_create_a_run_or_a_version(self):
        for change in (
            {"price_time_series_set_id": None},
            {"range_end": "2026-01-02T00:00:00Z"},
            {"range_end": self.request["range_start"]},
            {"resolution_hours": 3},
        ):
            with self.subTest(change=change):
                response = self.client.post(self.url + "/run", json={**self.request, **change})
                self.assertEqual(response.status_code, 400, response.text)
        versions = self.client.get(f"/api/scenarios/{self.scenario['id']}/versions").json()["versions"]
        runs = self.client.get(f"/api/scenarios/{self.scenario['id']}/runs").json()["runs"]
        self.assertEqual(len(versions), 1)
        self.assertEqual(runs, [])

    @unittest.skipUnless(shutil.which("julia"), "Julia is required for the solver integration")
    def test_economic_run_reaches_results_with_the_real_julia_executor(self):
        preview = self.client.post(self.url + "/preview", json=self.request).json()
        response = self.client.post(self.url + "/run", json={**self.request, "expected_preparation_hash": preview["preparation_hash"]})
        self.assertEqual(response.status_code, 201, response.text)
        run = response.json()
        JuliaRunExecutor(store=self.store, artifact_root=self.artifact_root).execute(run["id"])
        completed = self.client.get(f"/api/runs/{run['id']}").json()["run"]
        self.assertEqual(completed["status"], "succeeded", completed.get("error_message"))
        results = self.client.get(f"/api/runs/{run['id']}/results")
        self.assertEqual(results.status_code, 200, results.text)
        totals = results.json()["results"]["summary"]["hydraulic_v3_totals"]
        self.assertAlmostEqual(totals["total_generation_mwh"], 120)
        self.assertAlmostEqual(totals["total_revenue_usd"], 6300)
