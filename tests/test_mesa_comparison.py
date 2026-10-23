"""MESA-009: historical comparison observed through authenticated HTTP (S2)."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf
from tests.mesa_execution_fixture import seed_executable_mesa
from tests.mesa_comparison_fixture import complete_comparison_run
from tests.test_ts3_case_variant_api import RecordingRunQueue, StubValidationService


class MesaComparisonApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.store.create_user(email="mesa@example.local", display_name="Analista", role="analyst",
                               password_hash=hash_password("mesa test pass"))
        self.fixture = seed_executable_mesa(self.store)
        self.client = TestClient(create_app(store=self.store, auth_enabled=True,
            run_queue=RecordingRunQueue(), validation_service=StubValidationService(), artifact_root=self.temp.name))
        self.addCleanup(self.client.close)
        login_json_with_csrf(self.client, "mesa@example.local", "mesa test pass")
        self.path = f"/api/scenarios/{self.fixture['scenario']['id']}/mesa"
        self.params = {"case_id": self.fixture["case"]["id"], "variant_id": self.fixture["variant"]["id"]}

    def launch(self, key="comparison-1", **changes):
        payload = {**self.params, "range_start": "2026-10-20T00:00:00", "range_end": "2026-10-20T02:00:00",
                   "timezone": "America/Santiago", "resolution_hours": 1, **changes}
        preview = post_json_with_csrf(self.client, self.path + "/execution/preview", payload)
        self.assertEqual(preview.status_code, 200, preview.text)
        result = post_json_with_csrf(self.client, self.path + "/execution/runs", {
            **payload, "expected_preparation_hash": preview.json()["preparation_hash"], "idempotency_key": key})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def succeed(self, run, **options):
        return complete_comparison_run(self.store, run, self.temp.name, **options)

    def edit_demand(self):
        path = f"{self.path}/inputs/{self.fixture['object']['id']}/load_demand_mw"
        edit = self.client.get(path, params=self.params).json()
        points = [dict(p) for p in edit["series"]["points"]]
        points[0]["value"] = 12
        response = post_json_with_csrf(self.client, path + "/revisions", {
            **self.params, "expected": edit["expected"], "unit": "MW", "points": points,
            "confirm": True, "reason": "Fuente editada después de ejecutar"})
        self.assertEqual(response.status_code, 201, response.text)

    def comparison(self, run, **params):
        response = self.client.get(self.path + "/comparison", params={**self.params, "run_id": run["id"], **params})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_executed_demand_stays_ten_after_current_source_is_edited_to_twelve(self):
        run = self.launch()
        self.succeed(run)
        self.edit_demand()
        current = self.client.get(self.path, params=self.params).json()
        demand = next(c for c in current["components"] if c["entity_id"] == "load_north")
        self.assertEqual(demand["series"]["points"][0]["value"], 12)
        for _ in range(2):
            body = self.comparison(run)
            demand = next(c for c in body["series"] if c["signal_key"] == "load_demand_mw")
            self.assertEqual([p["value"] for p in demand["before"]["points"]], [10, 12])
            self.assertEqual([p["value"] for p in demand["after"]["points"]], [10, 12])
            self.assertEqual([p["value"] for p in demand["delta"]], [0, 0])
            self.assertEqual(demand["status"], "unchanged_input")
            self.assertEqual(demand["before"]["run_id"], run["id"])
            self.assertEqual(demand["before"]["revision_id"], self.fixture["receipt"]["revision_id"])
            self.assertFalse(demand["before"]["editable"])

    def test_output_without_explicit_reference_has_no_before_or_delta(self):
        run = self.launch()
        self.succeed(run)
        body = self.comparison(run)
        outputs = [s for s in body["series"] if s["role"] == "output"]
        self.assertEqual(len(outputs), 5)
        discharge = next(s for s in outputs if s["signal_key"] == "bess_discharge_power_mw")
        self.assertEqual([p["value"] for p in discharge["after"]["points"]], [2, 0])
        self.assertEqual(discharge["after"]["run_id"], run["id"])
        for output in outputs:
            self.assertEqual(output["status"], "no_reference")
            self.assertEqual(output["message"], "Sin referencia previa")
            self.assertIsNone(output["before"])
            self.assertIsNone(output["delta"])
            self.assertFalse(output["after"]["editable"])

    def test_selected_bess_reference_exposes_both_runs_and_after_minus_before(self):
        reference = self.launch("reference")
        self.succeed(reference, discharge=(1, 3), energy=(4, 1), indexed=False)
        run = self.launch("candidate")
        self.succeed(run)
        body = self.comparison(run, reference_run_id=reference["id"])
        self.assertEqual(body["reference_run"]["id"], reference["id"])
        self.assertEqual([r["id"] for r in body["references"]], [reference["id"]])
        discharge = next(s for s in body["series"] if s["signal_key"] == "bess_discharge_power_mw")
        self.assertEqual(discharge["status"], "comparable")
        self.assertEqual([p["value"] for p in discharge["before"]["points"]], [1, 3])
        self.assertEqual([p["value"] for p in discharge["after"]["points"]], [2, 0])
        self.assertEqual([p["value"] for p in discharge["delta"]], [1, -3])
        self.assertEqual(discharge["before"]["run_id"], reference["id"])
        self.assertEqual(discharge["after"]["run_id"], run["id"])
        energy = next(s for s in body["series"] if s["signal_key"] == "bess_stored_energy_mwh")
        self.assertEqual(energy["unit"], "MWh")
        self.assertAlmostEqual(energy["delta"][1]["value"], 1.95)

    def test_different_intervals_are_explained_without_positional_subtraction(self):
        reference = self.launch("short-reference", range_end="2026-10-20T01:00:00")
        self.succeed(reference)
        run = self.launch()
        self.succeed(run)
        body = self.comparison(run, reference_run_id=reference["id"])
        output = next(s for s in body["series"] if s["signal_key"] == "bess_discharge_power_mw")
        self.assertEqual(output["status"], "incompatible")
        self.assertIn("intervalos", output["message"])
        self.assertIsNone(output["delta"])
        self.assertEqual(len(output["before"]["points"]), 1)
        self.assertEqual(len(output["after"]["points"]), 2)

    def test_local_hours_without_frozen_timezone_are_not_assumed_to_be_aligned(self):
        from tests.mesa_fixture import seed_mesa_run
        reference = seed_mesa_run(self.store, self.fixture, self.temp.name, naive=True, frozen_zone=False)
        run = seed_mesa_run(self.store, self.fixture, self.temp.name, naive=True, frozen_zone=False)
        output = next(s for s in self.comparison(run, reference_run_id=reference["id"])["series"]
                      if s["signal_key"] == "bess_discharge_power_mw")
        self.assertEqual(output["status"], "incompatible")
        self.assertIn("zona horaria", output["message"])
        self.assertIsNone(output["delta"])

    def test_same_component_key_with_changed_topology_does_not_produce_delta(self):
        run = self.launch()
        self.succeed(run)
        version = self.client.get(f"/api/scenario-versions/{run['scenario_version_id']}").json()["scenario_version"]
        document = version["system_case_json"]
        battery = next(n for n in document["nodes"] if n["id"] == "battery_1")
        document["nodes"].append({**battery, "id": "battery_2"})
        document["edges"].append({"from": "battery_2", "to": "bus_1"})
        old = self.store.create_scenario_version(scenario_id=self.fixture["scenario"]["id"], system_case_json=document,
            generation_metadata=version["generation_metadata"], validation_payload={"status": "ok"})
        reference = self.store.create_run(scenario_version_id=old["id"])
        self.succeed(reference)
        output = next(s for s in self.comparison(run, reference_run_id=reference["id"])["series"]
                      if s["signal_key"] == "bess_discharge_power_mw")
        self.assertEqual(output["status"], "incompatible")
        self.assertIn("topología", output["message"])
        self.assertIsNone(output["delta"])

    def test_comparison_is_scoped_to_successful_runs_case_variant_and_internal_session(self):
        run = self.launch()
        self.succeed(run)
        pending = self.launch("pending")
        other = seed_executable_mesa(self.store, name="Otro caso")
        from tests.mesa_comparison_fixture import seed_comparison_runs
        seed_comparison_runs(self.store, other, self.temp.name)
        for changes in ({"case_id": other["case"]["id"]}, {"variant_id": other["variant"]["id"]},
                        {"run_id": other["run"]["id"]}, {"run_id": pending["id"]},
                        {"reference_run_id": other["reference"]["id"]}, {"reference_run_id": pending["id"]},
                        {"reference_run_id": run["id"]}):
            with self.subTest(changes=changes):
                response = self.client.get(self.path + "/comparison", params={**self.params, "run_id": run["id"], **changes})
                self.assertEqual(response.status_code, 404, response.text)
                self.assertNotIn("series", response.json())
        self.store.create_user(email="external@example.local", display_name="Externo", role="external",
                               password_hash=hash_password("external pass"))
        with TestClient(self.client.app) as external:
            params = {**self.params, "run_id": run["id"]}
            self.assertEqual(external.get(self.path + "/comparison", params=params).status_code, 401)
            login_json_with_csrf(external, "external@example.local", "external pass")
            self.assertEqual(external.get(self.path + "/comparison", params=params).status_code, 404)

    def test_range_is_applied_to_both_sides_by_instant_without_resampling(self):
        reference = self.launch("reference")
        self.succeed(reference, discharge=(1, 3))
        run = self.launch()
        self.succeed(run)
        body = self.comparison(run, reference_run_id=reference["id"],
            range_start="2026-10-20T04:00:00+00:00", range_end="2026-10-20T05:00:00+00:00")
        output = next(s for s in body["series"] if s["signal_key"] == "bess_discharge_power_mw")
        self.assertEqual([p["value"] for p in output["before"]["points"]], [3])
        self.assertEqual([p["value"] for p in output["after"]["points"]], [0])
        self.assertEqual([p["value"] for p in output["delta"]], [-3])
        body = self.comparison(run, reference_run_id=reference["id"],
            range_start="2026-10-20T03:30:00+00:00", range_end="2026-10-20T05:00:00+00:00")
        self.assertTrue(all(s["delta"] is None for s in body["series"]))
        for changes in ({"range_start": "invalid", "range_end": "invalid"}, {"range_start": "2026-10-20T00:00:00"},
                        {"range_start": "2026-10-20T00:00:00", "range_end": "2026-10-20T01:00:00"}):
            response = self.client.get(self.path + "/comparison", params={**self.params, "run_id": run["id"], **changes})
            self.assertEqual(response.status_code, 400, response.text)

    def test_reference_from_another_variant_of_the_same_case_keeps_its_own_provenance(self):
        run = self.launch()
        self.succeed(run)
        version = self.client.get(f"/api/scenario-versions/{run['scenario_version_id']}").json()["scenario_version"]
        variant = self.store.create_case_input_variant(case_id=self.params["case_id"], display_name="Referencia histórica")
        metadata = {**version["generation_metadata"], "input_variant": {"id": variant["id"]}}
        reference_version = self.store.create_scenario_version(scenario_id=self.fixture["scenario"]["id"],
            system_case_json=version["system_case_json"], generation_metadata=metadata, validation_payload={"status": "ok"})
        reference = self.store.create_run(scenario_version_id=reference_version["id"])
        self.succeed(reference, discharge=(1, 3))
        body = self.comparison(run, reference_run_id=reference["id"])
        discharge = next(s for s in body["series"] if s["signal_key"] == "bess_discharge_power_mw")
        self.assertEqual(discharge["before"]["scenario_version_id"], reference_version["id"])
        self.assertEqual([p["value"] for p in discharge["delta"]], [1, -3])

    def test_comparison_preferences_and_execution_polling_can_be_read_concurrently(self):
        run = self.launch()
        self.succeed(run)
        paths = [self.path, self.path + "/comparison", self.path + "/preferences", self.path + "/execution"]
        def read(path):
            response = self.client.get(path, params={**self.params, "run_id": run["id"]})
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()
        with ThreadPoolExecutor(max_workers=8) as workers:
            bodies = list(workers.map(read, paths * 10))
        self.assertEqual(len(bodies), 40)
        self.assertEqual(bodies[1]["series"][0]["before"]["points"][0]["value"], 10)


if __name__ == "__main__":
    unittest.main()
