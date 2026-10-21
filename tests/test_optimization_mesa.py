"""MESA-002: observable read contracts, with authentication enabled."""

import unittest
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.time_series_catalog import CatalogImportRequest, CatalogSignalMappingRequest, prepare_time_series_catalog_import
from tests.auth_test_helpers import login_json_with_csrf
from tests.mesa_fixture import seed_mesa_case, seed_mesa_run


class OptimizationMesaApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.store.create_user(email="mesa@example.local", display_name="Analista", role="analyst", password_hash=hash_password("mesa test pass"))
        self.fixture = seed_mesa_case(self.store)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.artifact_root = Path(self.temp.name)
        self.client = TestClient(create_app(store=self.store, auth_enabled=True, artifact_root=self.artifact_root))
        response = login_json_with_csrf(self.client, "mesa@example.local", "mesa test pass")
        self.assertEqual(response.status_code, 200, response.text)

    def tearDown(self):
        self.client.close()
        self.store.close()

    @property
    def path(self):
        return f"/api/scenarios/{self.fixture['scenario']['id']}/mesa"

    @property
    def params(self):
        return {"case_id": self.fixture["case"]["id"], "variant_id": self.fixture["variant"]["id"]}

    def test_demand_is_read_from_the_selected_canonical_revision_after_reload(self):
        for _ in range(2):
            response = self.client.get(self.path, params=self.params)
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body["context"]["project_id"], self.fixture["project"]["id"])
            self.assertEqual(body["context"]["case_id"], self.fixture["case"]["id"])
            self.assertEqual(body["context"]["variant_id"], self.fixture["variant"]["id"])
            component, = [item for item in body["components"] if item["entity_type"] == "component:load"]
            self.assertEqual(component["linkable_object_id"], self.fixture["object"]["id"])
            self.assertEqual(component["entity_id"], "load_north")
            series = component["series"]
            self.assertEqual(series["role"], "input")
            self.assertEqual(series["unit"], "MW")
            self.assertTrue(series["editable"])
            self.assertEqual(series["revision_id"], self.fixture["receipt"]["revision_id"])
            self.assertEqual(series["timezone"], "America/Santiago")
            self.assertEqual(series["points"], [
                {"start": "2026-10-20T00:00:00-03:00", "end": "2026-10-20T01:00:00-03:00", "value": 10.0},
                {"start": "2026-10-20T01:00:00-03:00", "end": "2026-10-20T02:00:00-03:00", "value": 12.0},
            ])

    def test_uncovered_period_reports_no_coverage_without_inventing_zero(self):
        response = self.client.get(self.path, params={
            **self.params, "range_start": "2026-10-20T00:00:00-03:00", "range_end": "2026-10-20T03:00:00-03:00",
        })
        self.assertEqual(response.status_code, 200, response.text)
        series = response.json()["components"][0]["series"]
        self.assertEqual(series["status"], "no_coverage")
        self.assertIn("Sin cobertura", series["message"])
        self.assertEqual(series["points"], [])

    def test_electrical_case_exposes_renewable_input_but_no_invented_battery_results(self):
        self.fixture = seed_mesa_case(self.store, electrical=True)
        response = self.client.get(self.path, params=self.params)
        self.assertEqual(response.status_code, 200, response.text)
        components = {item["entity_id"]: item for item in response.json()["components"]}
        self.assertEqual(set(components), {"load_north", "battery_1", "solar_north"})
        solar = components["solar_north"]["series"]
        self.assertEqual(solar["signal_key"], "renewable_available_power_mw")
        self.assertEqual(solar["role"], "input")
        self.assertEqual(solar["unit"], "MW")
        self.assertEqual([point["value"] for point in solar["points"]], [3.0, 5.0])
        self.assertIsNotNone(solar["revision_id"])
        battery = components["battery_1"]
        outputs = [battery["series"], *battery["additional_series"], *components["solar_north"]["additional_series"]]
        self.assertEqual({item["signal_key"] for item in outputs}, {
            "bess_charge_power_mw", "bess_discharge_power_mw", "bess_stored_energy_mwh",
            "renewable_used_power_mw", "renewable_curtailed_power_mw",
        })
        for series in outputs:
            self.assertEqual(series["role"], "output")
            self.assertEqual(series["status"], "unavailable")
            self.assertEqual(series["points"], [])
            self.assertFalse(series["editable"])

    def test_existing_legacy_variant_reads_its_own_demand_source(self):
        variant = self.store.create_case_input_variant(case_id=self.fixture["case"]["id"], display_name="Demanda anterior")
        prepared = prepare_time_series_catalog_import(
            rows=[{"date": "2026-10-20T00:00:00-03:00", "hours": "1", "demand": "7"},
                  {"date": "2026-10-20T01:00:00-03:00", "hours": "1", "demand": "9"}],
            request=CatalogImportRequest(set_name="Demanda anterior", version_label="v1", data_kind="real",
                timezone="America/Santiago", timestamp_column="date", duration_hours_column="hours",
                signal_mappings=[CatalogSignalMappingRequest(source_column="demand", signal_key="load_demand_mw")]),
        )
        source = self.store.import_time_series_catalog_set(
            scenario_id=self.fixture["scenario"]["id"],
            source={"id": "mesa-legacy", "original_filename": "demand.csv", "media_type": "text/csv", "checksum": "mesa-fixture"},
            prepared_import=prepared,
        )
        self.store.upsert_case_time_series_binding(case_input_variant_id=variant["id"],
            signal_key="load_demand_mw", entity_type="component:load", entity_id="load_north", time_series_set_id=source["id"])
        response = self.client.get(self.path, params={**self.params, "variant_id": variant["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        series = response.json()["components"][0]["series"]
        self.assertEqual([point["value"] for point in series["points"]], [7.0, 9.0])
        self.assertEqual(series["time_series_set_id"], source["id"])
        self.assertIsNone(series["revision_id"])

    def test_case_and_variant_ids_cannot_cross_scenario_contexts_even_with_equal_names(self):
        other = seed_mesa_case(self.store, name="Otro caso", values=(90.0, 95.0))
        for params in (
            {**self.params, "case_id": other["case"]["id"]},
            {**self.params, "variant_id": other["variant"]["id"]},
            {"case_id": other["case"]["id"], "variant_id": other["variant"]["id"]},
        ):
            with self.subTest(params=params):
                response = self.client.get(self.path, params=params)
                self.assertEqual(response.status_code, 404, response.text)
                self.assertNotIn("points", response.json())
        response = self.client.get(f"/api/scenarios/{other['scenario']['id']}/mesa", params={
            "case_id": other["case"]["id"], "variant_id": other["variant"]["id"],
        })
        component = response.json()["components"][0]
        self.assertEqual(component["name"], "Demanda Norte")
        self.assertEqual(component["linkable_object_id"], other["object"]["id"])
        self.assertEqual([p["value"] for p in component["series"]["points"]], [90.0, 95.0])

    def test_battery_parameters_are_scalars_with_current_model_provenance(self):
        response = self.client.get(self.path, params=self.params)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["context"]["model_contract"], "bess_system_dispatch.v2")
        battery = next(c for c in body["components"] if c["entity_id"] == "battery_1")
        parameters = {p["key"]: p for p in battery["parameters"]}
        self.assertEqual(parameters["initial_energy_mwh"]["value"], 4.0)
        self.assertEqual(parameters["initial_energy_mwh"]["unit"], "MWh")
        self.assertEqual(parameters["initial_energy_mwh"]["source"], "current_preparation")
        self.assertEqual(parameters["charge_power_max_mw"]["value"], 4.0)
        self.assertEqual(parameters["charge_efficiency"]["value"], 0.95)
        self.assertNotIn("points", parameters["initial_energy_mwh"])
        self.assertIsNotNone(battery["linkable_object_id"])

    def test_selected_v1_and_v2_runs_expose_only_their_per_asset_results_with_lineage(self):
        self.fixture = seed_mesa_case(self.store, electrical=True)
        for contract in ("bess_system_dispatch.v1", "bess_system_dispatch.v2"):
            run = seed_mesa_run(self.store, self.fixture, self.artifact_root, contract=contract)
            response = self.client.get(self.path, params={**self.params, "run_id": run["id"]})
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            battery = next(c for c in body["components"] if c["entity_id"] == "battery_1")
            series = {s["signal_key"]: s for s in [battery["series"], *battery["additional_series"]]}
            discharge = series["bess_discharge_power_mw"]
            self.assertEqual([p["value"] for p in discharge["points"]], [2.0, 0.0])
            self.assertEqual(discharge["run_id"], run["id"])
            self.assertEqual(discharge["scenario_version_id"], run["scenario_version_id"])
            self.assertEqual(discharge["source"], "asset_dispatch")
            self.assertEqual(series["bess_stored_energy_mwh"]["unit"], "MWh")
            solar = next(c for c in body["components"] if c["entity_id"] == "solar_north")
            self.assertEqual([p["value"] for p in solar["additional_series"][0]["points"]], [2.0, 4.0])
            self.assertEqual(body["selected_run"]["model_contract"], contract)
            self.assertIn(run["id"], [r["id"] for r in body["runs"]])

    def test_result_query_falls_back_to_artifact_when_the_asset_index_is_absent(self):
        self.fixture = seed_mesa_case(self.store, electrical=True)
        run = seed_mesa_run(self.store, self.fixture, self.artifact_root)
        self.store.delete_run_asset_dispatch_result_index(run["id"])
        response = self.client.get(self.path, params={**self.params, "run_id": run["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        battery = next(c for c in response.json()["components"] if c["entity_id"] == "battery_1")
        self.assertEqual([p["value"] for p in battery["series"]["points"]], [0.0, 1.0])

    def test_inventory_keeps_equal_names_separate_and_excludes_archived_components(self):
        draft = self.store.get_scenario_draft(self.fixture["scenario"]["id"])["document"]
        second = {**draft["assets"][0], "id": "battery_2"}
        draft["assets"].append(second)
        self.store.create_or_replace_scenario_draft(scenario_id=self.fixture["scenario"]["id"], document=draft)
        first_obj = self.store.ensure_project_component(project_id=self.fixture["project"]["id"], component_key="battery_1", component_type="battery", display_name="BESS")
        second_obj = self.store.ensure_project_component(project_id=self.fixture["project"]["id"], component_key="battery_2", component_type="battery", display_name=first_obj["display_name"])
        body = self.client.get(self.path, params=self.params).json()
        batteries = [c for c in body["components"] if c["entity_type"] == "component:battery"]
        self.assertEqual({c["linkable_object_id"] for c in batteries}, {first_obj["id"], second_obj["id"]})
        self.assertEqual(len({c["name"] for c in batteries}), 1)
        self.store.archive_linkable_object(linkable_object_id=second_obj["id"])
        body = self.client.get(self.path, params=self.params).json()
        self.assertEqual([c["entity_id"] for c in body["components"] if c["entity_type"] == "component:battery"], ["battery_1"])

    def test_run_selection_is_scoped_to_case_variant_and_success(self):
        other = seed_mesa_case(self.store, electrical=True)
        other_run = seed_mesa_run(self.store, other, self.artifact_root)
        own_run = seed_mesa_run(self.store, self.fixture, self.artifact_root)
        variant = self.store.create_case_input_variant(case_id=self.fixture["case"]["id"], display_name="Otra variante")
        pending = self.store.create_run(scenario_version_id=own_run["scenario_version_id"])
        for extra in ({"run_id": other_run["id"]}, {"run_id": own_run["id"], "variant_id": variant["id"]}, {"run_id": pending["id"]}):
            response = self.client.get(self.path, params={**self.params, **extra})
            self.assertEqual(response.status_code, 404, response.text)
            self.assertNotIn("points", response.json())

    def test_missing_or_blank_output_column_is_unavailable_while_other_outputs_remain(self):
        run = seed_mesa_run(self.store, self.fixture, self.artifact_root)
        index = self.store.get_run_asset_dispatch_result_index(run["id"])
        columns = [c for c in index["columns"] if c != "battery_charge_mw"]
        rows = [{k: v for k, v in row.items() if k != "battery_charge_mw"} for row in index["rows"]]
        rows[0]["battery_energy_mwh"] = ""
        self.store.replace_run_asset_dispatch_result_index(run_id=run["id"], scenario_version_id=run["scenario_version_id"], columns=columns, rows=rows)
        response = self.client.get(self.path, params={**self.params, "run_id": run["id"]})
        battery = next(c for c in response.json()["components"] if c["entity_id"] == "battery_1")
        self.assertEqual(battery["series"]["status"], "unavailable")
        self.assertEqual(battery["series"]["points"], [])
        self.assertEqual(battery["additional_series"][1]["points"], [])
        self.assertEqual([p["value"] for p in battery["additional_series"][0]["points"]], [2.0, 0.0])

    def test_result_range_uses_the_frozen_timezone_for_naive_artifact_timestamps(self):
        run = seed_mesa_run(self.store, self.fixture, self.artifact_root, naive=True)
        response = self.client.get(self.path, params={**self.params, "run_id": run["id"],
            "range_start": "2026-10-20T00:00:00-03:00", "range_end": "2026-10-20T02:00:00-03:00"})
        self.assertEqual(response.status_code, 200, response.text)
        battery = next(c for c in response.json()["components"] if c["entity_id"] == "battery_1")
        self.assertEqual([p["value"] for p in battery["series"]["points"]], [0.0, 1.0])
        self.assertEqual(battery["series"]["timezone"], "America/Santiago")
        self.assertEqual(battery["series"]["points"][0]["start"], "2026-10-20T00:00:00-03:00")

    def test_result_with_a_different_interval_duration_is_not_presented_as_compatible(self):
        run = seed_mesa_run(self.store, self.fixture, self.artifact_root)
        index = self.store.get_run_asset_dispatch_result_index(run["id"])
        index["rows"][0]["duration_hours"] = 2
        self.store.replace_run_asset_dispatch_result_index(run_id=run["id"], scenario_version_id=run["scenario_version_id"], columns=index["columns"], rows=index["rows"])
        response = self.client.get(self.path, params={**self.params, "run_id": run["id"]})
        battery = next(c for c in response.json()["components"] if c["entity_id"] == "battery_1")
        self.assertEqual(battery["series"]["status"], "unavailable")
        self.assertEqual(battery["series"]["points"], [])

    def test_legacy_run_without_timezone_can_be_read_but_not_sliced_as_absolute_instants(self):
        run = seed_mesa_run(self.store, self.fixture, self.artifact_root, contract="bess_system_dispatch.v1", naive=True, frozen_zone=False)
        response = self.client.get(self.path, params={**self.params, "run_id": run["id"]})
        battery = next(c for c in response.json()["components"] if c["entity_id"] == "battery_1")
        self.assertEqual([p["value"] for p in battery["series"]["points"]], [0.0, 1.0])
        self.assertIsNone(battery["series"]["timezone"])
        self.assertEqual(battery["series"]["points"][0]["start"], "2026-10-20T00:00:00")
        response = self.client.get(self.path, params={**self.params, "run_id": run["id"],
            "range_start": "2026-10-20T00:00:00-03:00", "range_end": "2026-10-20T02:00:00-03:00"})
        battery = next(c for c in response.json()["components"] if c["entity_id"] == "battery_1")
        self.assertEqual(battery["series"]["points"], [])
        self.assertIn("zona horaria", battery["series"]["message"])

    def test_external_operator_and_anonymous_session_cannot_read_the_internal_mesa(self):
        self.store.create_user(email="operator@example.local", display_name="Operador", role="external", password_hash=hash_password("operator pass"))
        with TestClient(self.client.app) as external:
            self.assertEqual(external.get(self.path, params=self.params).status_code, 401)
            login = login_json_with_csrf(external, "operator@example.local", "operator pass")
            self.assertEqual(login.status_code, 200, login.text)
            for path in (self.path, "/api/scenarios/999999/mesa"):
                self.assertEqual(external.get(path, params=self.params).status_code, 404)

    def test_empty_case_and_unbound_variant_have_explicit_empty_states(self):
        variant = self.store.create_case_input_variant(case_id=self.fixture["case"]["id"], display_name="Sin fuente")
        response = self.client.get(self.path, params={**self.params, "variant_id": variant["id"]})
        series = response.json()["components"][0]["series"]
        self.assertEqual(series["status"], "unbound")
        self.assertEqual(series["points"], [])
        scenario = self.store.create_scenario(project_id=self.fixture["project"]["id"], name="Sin demanda")
        context = self.client.get(f"/api/scenarios/{scenario['id']}/case/default-variant").json()
        response = self.client.get(f"/api/scenarios/{scenario['id']}/mesa", params={"case_id": context["case"]["id"], "variant_id": context["variant"]["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["components"], [])

    def test_exact_period_slice_and_invalid_ranges_are_not_silently_resampled(self):
        response = self.client.get(self.path, params={**self.params,
            "range_start": "2026-10-20T01:00:00-03:00", "range_end": "2026-10-20T02:00:00-03:00"})
        self.assertEqual([p["value"] for p in response.json()["components"][0]["series"]["points"]], [12.0])
        for extra in ({"range_start": "invalid", "range_end": "invalid"},
                      {"range_start": "2026-10-20T00:00:00-03:00"},
                      {"range_start": "2026-10-20T00:00:00", "range_end": "2026-10-20T02:00:00"},
                      {"range_start": "2026-10-20T02:00:00-03:00", "range_end": "2026-10-20T00:00:00-03:00"}):
            with self.subTest(extra=extra):
                self.assertEqual(self.client.get(self.path, params={**self.params, **extra}).status_code, 400)
