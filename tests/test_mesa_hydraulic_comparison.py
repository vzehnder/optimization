"""MESA-010: frozen hydraulic comparison through authenticated HTTP (S2)."""

import tempfile
import unittest
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf, put_json_with_csrf, post_json_with_csrf
from tests.mesa_hydraulic_fixture import seed_hydraulic_mesa, seed_hydraulic_mesa_run
from tests.test_ts3_case_variant_api import RecordingRunQueue, StubValidationService


class MesaHydraulicComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.store.create_user(email="mesa@example.local", display_name="Analista", role="analyst",
                               password_hash=hash_password("mesa test pass"))
        self.fixture = seed_hydraulic_mesa(self.store)
        self.client = TestClient(create_app(store=self.store, auth_enabled=True, artifact_root=self.temp.name,
            run_queue=RecordingRunQueue(), validation_service=StubValidationService()))
        self.addCleanup(self.client.close)
        login_json_with_csrf(self.client, "mesa@example.local", "mesa test pass")
        self.path = f"/api/scenarios/{self.fixture['scenario']['id']}/mesa"
        self.params = {"case_id": self.fixture["case"]["id"], "variant_id": self.fixture["variant"]["id"]}

    def comparison(self, run, **params):
        response = self.client.get(self.path + "/comparison", params={**self.params, "run_id": run["id"], **params})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_same_named_volume_and_flow_keep_entity_units_and_have_no_invented_reference(self):
        diagram = self.fixture["diagram"]
        diagram["nodes"][0]["display_name"] = "Agua"
        diagram["reaches"][0]["display_name"] = "Agua"
        self.store.save_hydraulic_diagram(scenario_id=self.fixture["scenario"]["id"], revision=diagram["revision"],
            nodes=diagram["nodes"], reaches=diagram["reaches"])
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        series = self.comparison(run)["series"]
        volume = next(s for s in series if s["entity_id"] == "reservoir" and s["signal_key"] == "hydro_storage_volume_hm3")
        flow = next(s for s in series if s["entity_id"] == "reach" and s["signal_key"] == "hydraulic_flow_m3s")
        self.assertEqual((volume["entity_type"], volume["unit"]), ("hydraulic_node", "hm3"))
        self.assertEqual((flow["entity_type"], flow["unit"]), ("hydraulic_reach", "m3/s"))
        self.assertEqual([p["value"] for p in volume["after"]["points"]], [9.8, 9.6])
        self.assertEqual([p["value"] for p in flow["after"]["points"]], [16, 24])
        for item in (volume, flow):
            self.assertEqual(item["after"]["run_id"], run["id"])
            self.assertEqual(item["status"], "no_reference")
            self.assertIsNone(item["before"])
            self.assertIsNone(item["delta"])

    def test_external_inflow_is_the_unchanged_executed_input(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        series = self.comparison(run)["series"]
        inflow = next((s for s in series if s["entity_id"] == "reservoir" and s["signal_key"] == "natural_inflow_m3s"), None)
        self.assertIsNotNone(inflow, "La comparación debe incluir el aporte ejecutado")
        self.assertEqual(inflow["status"], "unchanged_input")
        self.assertEqual([p["value"] for p in inflow["before"]["points"]], [2, 4])
        self.assertEqual(inflow["after"], inflow["before"])
        self.assertEqual([p["value"] for p in inflow["delta"]], [0, 0])
        self.assertEqual(inflow["after"]["source"], "executed_snapshot")
        self.assertFalse(inflow["after"]["editable"])

    def test_homonymous_plants_aggregate_only_their_executed_units(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        series = self.comparison(run)["series"]
        plants = {s["entity_id"]: s for s in series if s["entity_type"] == "hydraulic_plant" and s["unit"] == "MW"}
        self.assertEqual(set(plants), {"plant_1", "plant_2"})
        self.assertEqual([p["value"] for p in plants["plant_1"]["after"]["points"]], [3, 6])
        self.assertEqual([p["value"] for p in plants["plant_2"]["after"]["points"]], [9, 12])
        flow = next(s for s in series if s["entity_id"] == "plant_1" and s["unit"] == "m3/s")
        self.assertEqual([p["value"] for p in flow["after"]["points"]], [4, 8])

    def test_explicit_reference_compares_same_entity_signal_and_unit_with_csv_fallback(self):
        reference = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name, volume=(10, 9), indexed=False)
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        body = self.comparison(run, reference_run_id=reference["id"])
        self.assertIsNotNone(body["reference_run"])
        self.assertEqual(body["reference_run"]["id"], reference["id"])
        self.assertEqual([r["id"] for r in body["references"]], [reference["id"]])
        volume = next(s for s in body["series"] if s["signal_key"] == "hydro_storage_volume_hm3")
        self.assertEqual(volume["status"], "comparable")
        self.assertEqual([p["value"] for p in volume["before"]["points"]], [10, 9])
        self.assertAlmostEqual(volume["delta"][0]["value"], -0.2)
        self.assertAlmostEqual(volume["delta"][1]["value"], 0.6)
        self.assertEqual(volume["before"]["run_id"], reference["id"])
        self.assertEqual(volume["after"]["run_id"], run["id"])

    def test_changed_network_connections_or_unit_membership_prevent_delta(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        for change in ("connection", "membership", "identity", "routing"):
            with self.subTest(change=change):
                document = self.client.get(f"/api/scenario-versions/{run['scenario_version_id']}").json()["scenario_version"]["system_case_json"]
                network = document["hydraulic_network"]
                if change == "connection":
                    network["reaches"][0]["to_node"] = "outlet"
                elif change == "membership":
                    network["units"][0]["plant_id"] = "plant_2"
                elif change == "identity":
                    network["nodes"][1]["id"] = "new_intake"
                else:
                    network["reaches"][0]["routing_method"] = "fixed_delay"
                    network["reaches"][0]["travel_time_hours"] = 1
                reference = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name, document=document)
                output = next(s for s in self.comparison(run, reference_run_id=reference["id"])["series"]
                              if s["signal_key"] == "hydro_storage_volume_hm3")
                self.assertEqual(output["status"], "incompatible")
                self.assertIn("topología", output["message"])
                self.assertIsNone(output["delta"])

    def test_incompatible_intervals_or_missing_timezone_never_subtract_by_position(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        for change in ("shorter", "shifted", "duration", "naive"):
            with self.subTest(change=change):
                document = self.client.get(f"/api/scenario-versions/{run['scenario_version_id']}").json()["scenario_version"]["system_case_json"]
                if change == "shorter":
                    document["time_series"] = document["time_series"][:1]
                elif change == "shifted":
                    for p in document["time_series"]:
                        p["timestamp"] = p["timestamp"].replace("2026-10-20", "2026-10-21")
                elif change == "duration":
                    document["time_series"] = document["time_series"][:1]
                    document["time_series"][0]["duration_hours"] = 2
                else:
                    for p in document["time_series"]:
                        p["timestamp"] = p["timestamp"].replace("+00:00", "")
                reference = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name, document=document)
                output = next(s for s in self.comparison(run, reference_run_id=reference["id"])["series"]
                              if s["signal_key"] == "hydro_storage_volume_hm3")
                self.assertEqual(output["status"], "incompatible")
                self.assertIsNone(output["delta"])
                self.assertIn("zona horaria" if change == "naive" else "intervalos", output["message"])

    def test_historical_names_scalar_parameters_and_samples_survive_current_case_edits(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        path = f"/api/scenarios/{self.fixture['scenario']['id']}/hydraulic-diagram"
        diagram = self.client.get(path).json()["diagram"]
        reservoir = next(n for n in diagram["nodes"] if n["technical_key"] == "reservoir")
        reservoir["display_name"] = "Nombre nuevo"
        reservoir["reservoir"]["initial_storage_hm3"] = 15
        reservoir["natural_inflow_series"]["points"][0]["value_m3s"] = 99
        response = put_json_with_csrf(self.client, path, {k: diagram[k] for k in ("revision", "nodes", "reaches")})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(next(n for n in self.client.get(path).json()["diagram"]["nodes"] if n["technical_key"] == "reservoir")["display_name"], "Nombre nuevo")
        body = self.comparison(run)
        self.assertIn("components", body)
        frozen = next(c for c in body["components"] if c["entity_id"] == "reservoir")
        self.assertEqual(frozen["name"], "Embalse Alto")
        initial = next(p for p in frozen["parameters"] if p["key"] == "initial_storage_hm3")
        self.assertEqual(initial["value"], 10)
        self.assertEqual(initial["source"], "executed_snapshot")
        self.assertEqual(initial["scenario_version_id"], run["scenario_version_id"])
        self.assertNotIn("initial_storage_hm3", [s["signal_key"] for s in body["series"]])
        inflow = next(s for s in body["series"] if s["signal_key"] == "natural_inflow_m3s")
        self.assertEqual([p["value"] for p in inflow["before"]["points"]], [2, 4])
        self.assertEqual(self.comparison(run), body)

    def test_minimum_flow_is_a_frozen_input_separate_from_calculated_reach_flow(self):
        document = self.store.generate_hydraulic_v3_preview(self.fixture["scenario"]["id"])
        for i, p in enumerate(document["time_series"]):
            p["minimum_flow_m3s"] = {"reach": [1, 2][i]}
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name, document=document)
        series = self.comparison(run)["series"]
        minimum = next((s for s in series if s["signal_key"] == "minimum_flow_m3s"), None)
        self.assertIsNotNone(minimum)
        self.assertEqual([p["value"] for p in minimum["before"]["points"]], [1, 2])
        self.assertEqual([p["value"] for p in minimum["delta"]], [0, 0])
        flow = next(s for s in series if s["signal_key"] == "hydraulic_flow_m3s")
        self.assertEqual([p["value"] for p in flow["after"]["points"]], [16, 24])

    def test_simple_v2_hydro_uses_its_own_frozen_inflow_and_outputs(self):
        from tests.mesa_fixture import seed_mesa_case
        fixture = seed_mesa_case(self.store)
        document = json.loads((Path(__file__).parents[1] / "data/cases/linear_hydro_system/system_case.json").read_text())
        version = self.store.create_scenario_version(scenario_id=fixture["scenario"]["id"], system_case_json=document,
            validation_payload={"status": "ok"}, generation_metadata={"input_variant": {"id": fixture["variant"]["id"]}})
        run = self.store.create_run(scenario_version_id=version["id"])
        self.store.mark_run_running(run["id"], workspace_path=self.temp.name, input_snapshot_path=str(Path(self.temp.name) / "input.json"))
        self.store.mark_run_succeeded(run["id"], exit_code=0, stdout="", stderr="", success_payload={}, output_dir=self.temp.name, summary_path=str(Path(self.temp.name) / "summary.json"))
        self.store.replace_run_asset_dispatch_result_index(run_id=run["id"], scenario_version_id=version["id"],
            columns=["timestamp", "duration_hours", "asset_id", "asset_type", "hydro_power_mw"],
            rows=[{"timestamp": f"2026-01-01T0{i}:00:00", "duration_hours": 1, "asset_id": "hydro_1", "asset_type": "hydro", "hydro_power_mw": v} for i, v in enumerate([0.5, 1])])
        response = self.client.get(f"/api/scenarios/{fixture['scenario']['id']}/mesa/comparison", params={
            "case_id": fixture["case"]["id"], "variant_id": fixture["variant"]["id"], "run_id": run["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        series = response.json()["series"]
        power = next((s for s in series if s["signal_key"] == "hydro_generation_power_mw"), None)
        self.assertIsNotNone(power)
        self.assertEqual((power["entity_id"], power["entity_type"], power["unit"]), ("hydro_1", "component:hydro", "MW"))
        self.assertEqual([p["value"] for p in power["after"]["points"]], [0.5, 1])
        self.assertIsNone(power["before"])
        inflow = next(s for s in series if s["signal_key"] == "hydro_inflow_m3s")
        self.assertEqual(inflow["unit"], "m3/s")
        self.assertEqual(inflow["before"], inflow["after"])

    def test_volume_in_another_unit_or_missing_result_is_unavailable_without_conversion(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name, storage_column="hydro_storage_m3", volume=(9800000, 9600000))
        volume = next(s for s in self.comparison(run)["series"] if s["signal_key"] == "hydro_storage_volume_hm3")
        self.assertEqual(volume["status"], "unavailable")
        self.assertEqual(volume["after"]["points"], [])
        self.assertIsNone(volume["delta"])
        compatible_run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        volume = next(s for s in self.comparison(compatible_run, reference_run_id=run["id"])["series"] if s["signal_key"] == "hydro_storage_volume_hm3")
        self.assertEqual(volume["status"], "unavailable")
        self.assertEqual(volume["before"]["points"], [])
        self.assertIsNone(volume["delta"])

    def test_real_network_compares_two_economic_runs_by_plant_and_reservoir(self):
        from tests.mesa_hydraulic_execution_fixture import seed_executable_hydraulic_mesa
        fixture = seed_executable_hydraulic_mesa(self.store)
        path = f"/api/scenarios/{fixture['scenario']['id']}/mesa"
        with TestClient(create_app(store=self.store, auth_enabled=True, artifact_root=self.temp.name)) as client:
            login_json_with_csrf(client, "mesa@example.local", "mesa test pass")
            runs = []
            for water in (50000, 1):
                payload = {"case_id": fixture["case"]["id"], "source_scenario_version_id": fixture["version"]["id"],
                    "range_start": "2026-10-20T00:00:00+00:00", "range_end": "2026-10-20T02:00:00+00:00",
                    "resolution_hours": 2, "objective": "market_value", "price_time_series_set_id": fixture["prices"]["id"],
                    "terminal_water_values_usd_per_hm3": {"reservoir": water}, "mip_rel_gap": 0.01}
                preview = post_json_with_csrf(client, path + "/hydraulic-execution/preview", payload)
                self.assertEqual(preview.status_code, 200, preview.text)
                launched = post_json_with_csrf(client, path + "/hydraulic-execution/runs", {**payload,
                    "expected_preparation_hash": preview.json()["preparation_hash"], "idempotency_key": f"real-compare-{water}"})
                self.assertEqual(launched.status_code, 201, launched.text)
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    run = client.get(path + "/hydraulic-execution", params={"case_id": fixture["case"]["id"]}).json()["run"]
                    if run["status"] in ("succeeded", "failed"):
                        break
                    time.sleep(0.1)
                self.assertEqual(run["status"], "succeeded", run)
                runs.append(run)
            response = client.get(path + "/comparison", params={"case_id": fixture["case"]["id"],
                "variant_id": fixture["variant"]["id"], "run_id": runs[1]["id"], "reference_run_id": runs[0]["id"]})
            self.assertEqual(response.status_code, 200, response.text)
            series = response.json()["series"]
            power = next(s for s in series if s["entity_id"] == "plant_1" and s["signal_key"] == "hydro_generation_power_mw")
            volume = next(s for s in series if s["signal_key"] == "hydro_storage_volume_hm3")
            inflow = next(s for s in series if s["signal_key"] == "natural_inflow_m3s")
            self.assertEqual(power["status"], "comparable")
            self.assertAlmostEqual(power["before"]["points"][0]["value"], 0)
            self.assertAlmostEqual(power["after"]["points"][0]["value"], 30)
            self.assertAlmostEqual(power["delta"][0]["value"], 30)
            self.assertAlmostEqual(volume["before"]["points"][0]["value"], 10.0216)
            self.assertAlmostEqual(volume["after"]["points"][0]["value"], 9.7336)
            self.assertAlmostEqual(volume["delta"][0]["value"], -0.288)
            self.assertEqual([p["value"] for p in inflow["before"]["points"]], [3])
            self.assertEqual([p["value"] for p in inflow["delta"]], [0])
            self.assertEqual(client.get(path + "/comparison", params={"case_id": fixture["case"]["id"],
                "variant_id": fixture["variant"]["id"], "run_id": runs[1]["id"], "reference_run_id": runs[0]["id"]}).json(), response.json())

    def test_hydraulic_comparison_keeps_case_variant_run_and_auth_boundaries(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        other = seed_hydraulic_mesa(self.store, name="Otro")
        other_run = seed_hydraulic_mesa_run(self.store, other, self.temp.name)
        pending = self.store.create_run(scenario_version_id=run["scenario_version_id"])
        for changes in ({"case_id": other["case"]["id"]}, {"variant_id": other["variant"]["id"]},
                        {"run_id": other_run["id"]}, {"reference_run_id": other_run["id"]},
                        {"run_id": pending["id"]}, {"reference_run_id": pending["id"]}, {"reference_run_id": run["id"]}):
            with self.subTest(changes=changes):
                response = self.client.get(self.path + "/comparison", params={**self.params, "run_id": run["id"], **changes})
                self.assertEqual(response.status_code, 404, response.text)
        self.store.create_user(email="external@example.local", display_name="Externo", role="external", password_hash=hash_password("external pass"))
        with TestClient(self.client.app) as external:
            params = {**self.params, "run_id": run["id"]}
            self.assertEqual(external.get(self.path + "/comparison", params=params).status_code, 401)
            login_json_with_csrf(external, "external@example.local", "external pass")
            self.assertEqual(external.get(self.path + "/comparison", params=params).status_code, 404)

    def test_range_uses_exact_instants_and_rejects_partial_intervals(self):
        reference = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name, volume=(10, 9))
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        body = self.comparison(run, reference_run_id=reference["id"], range_start="2026-10-19T22:00:00-03:00", range_end="2026-10-19T23:00:00-03:00")
        volume = next(s for s in body["series"] if s["signal_key"] == "hydro_storage_volume_hm3")
        self.assertEqual([p["value"] for p in volume["before"]["points"]], [9])
        self.assertEqual([p["value"] for p in volume["after"]["points"]], [9.6])
        self.assertAlmostEqual(volume["delta"][0]["value"], 0.6)
        partial = self.comparison(run, reference_run_id=reference["id"], range_start="2026-10-20T00:30:00+00:00", range_end="2026-10-20T02:00:00+00:00")
        self.assertTrue(all(s["delta"] is None for s in partial["series"]))
        self.assertTrue(all(s["after"]["points"] == [] for s in partial["series"]))
if __name__ == "__main__":
    unittest.main()
