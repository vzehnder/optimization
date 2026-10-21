"""MESA-005 behaviors observed only through authenticated HTTP."""

import tempfile
import unittest
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.time_series_catalog import CatalogImportRequest, CatalogSignalMappingRequest, prepare_time_series_catalog_import
from tests.auth_test_helpers import login_json_with_csrf
from tests.mesa_hydraulic_fixture import seed_hydraulic_mesa, seed_hydraulic_mesa_run, bind_hydraulic_mesa_inflow
from tests.mesa_fixture import seed_mesa_case


class HydraulicMesaApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.store.create_user(email="mesa@example.local", display_name="Analista", role="analyst", password_hash=hash_password("mesa test pass"))
        self.fixture = seed_hydraulic_mesa(self.store)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.artifact_root = Path(directory.name)
        self.client = TestClient(create_app(store=self.store, auth_enabled=True, artifact_root=self.artifact_root))
        self.addCleanup(self.client.close)
        response = login_json_with_csrf(self.client, "mesa@example.local", "mesa test pass")
        self.assertEqual(response.status_code, 200, response.text)

    @property
    def path(self):
        return f"/api/scenarios/{self.fixture['scenario']['id']}/mesa"

    @property
    def params(self):
        return {"case_id": self.fixture["case"]["id"], "variant_id": self.fixture["variant"]["id"]}

    def read(self, **params):
        response = self.client.get(self.path, params={**self.params, **params})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_equal_plant_names_keep_case_base_and_unit_identities_after_reload(self):
        for _ in range(2):
            body = self.read()
            plants = [c for c in body["components"] if c["entity_type"] == "hydraulic_plant"]
            self.assertEqual([p["entity_id"] for p in plants], ["plant_1", "plant_2"])
            self.assertEqual([p["name"] for p in plants], ["Central Norte", "Central Norte"])
            self.assertEqual(len({p["linkable_object_id"] for p in plants}), 2)
            self.assertEqual(len({p["base_entity_id"] for p in plants}), 2)
            self.assertEqual([p["case_entity_id"] for p in plants], [
                n["entity_id"] for n in self.fixture["diagram"]["nodes"] if n["component_type"] == "plant"])
            units = [c for c in body["components"] if c["entity_type"] == "hydraulic_unit"]
            self.assertEqual([(u["entity_id"], u["parent_entity_id"]) for u in units], [("unit_1", "plant_1"), ("unit_2", "plant_2")])
            self.assertTrue(all(u["case_entity_id"] and u["base_entity_id"] for u in units))
            self.assertIn("reach", [c["entity_id"] for c in body["components"]])

    def test_reservoir_inflow_has_source_periods_and_initial_volume_is_only_a_parameter(self):
        components = {c["entity_id"]: c for c in self.read()["components"]}
        reservoir = components["reservoir"]
        series = reservoir["series"]
        self.assertEqual(series["signal_key"], "natural_inflow_m3s")
        self.assertEqual(series["role"], "input")
        self.assertEqual(series["unit"], "m3/s")
        self.assertEqual(series["points"], [
            {"start": "2026-10-20T00:00:00+00:00", "end": "2026-10-20T01:00:00+00:00", "value": 2},
            {"start": "2026-10-20T01:00:00+00:00", "end": "2026-10-20T02:00:00+00:00", "value": 4}])
        self.assertIsNotNone(series["time_series_set_id"])
        self.assertIn(series["source"], ("hydraulic_legacy", "generic"))
        initial = next(p for p in reservoir["parameters"] if p["key"] == "initial_storage_hm3")
        self.assertEqual((initial["value"], initial["unit"]), (10, "hm3"))
        self.assertNotIn("points", initial)
        self.assertEqual({s["signal_key"] for s in reservoir["additional_series"]},
                         {"hydro_storage_volume_hm3", "hydro_reservoir_elevation_masl", "hydro_spill_flow_m3s"})
        for output in reservoir["additional_series"]:
            self.assertEqual(output["status"], "unavailable")
            self.assertEqual(output["points"], [])
        self.assertNotIn("natural_inflow_m3s", [components["plant_1"]["series"]["signal_key"],
            *[s["signal_key"] for s in components["plant_1"]["additional_series"]]])

    def test_existing_run_keeps_plant_unit_reservoir_and_reach_results_separate(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.artifact_root)
        body = self.read(run_id=run["id"])
        components = {c["entity_id"]: c for c in body["components"]}
        self.assertEqual(body["selected_run"]["model_contract"], "bess_system_dispatch.v3")
        for key, signal_key, values in (
            ("plant_1", "hydro_generation_power_mw", [3, 6]),
            ("plant_2", "hydro_generation_power_mw", [9, 12]),
            ("unit_1", "hydro_turbine_flow_m3s", [4, 8]),
            ("reservoir", "hydro_storage_volume_hm3", [9.8, 9.6]),
            ("reservoir", "hydro_reservoir_elevation_masl", [709.8, 709.6]),
            ("reach", "hydraulic_flow_m3s", [16, 24]),
        ):
            with self.subTest(component=key, signal=signal_key):
                c = components[key]
                series = next(s for s in [c["series"], *c["additional_series"]] if s["signal_key"] == signal_key)
                self.assertEqual([p["value"] for p in series["points"]], values)
                self.assertEqual((series["run_id"], series["scenario_version_id"]), (run["id"], run["scenario_version_id"]))
                self.assertEqual(series["points"][0]["start"], "2026-10-20T00:00:00+00:00")
                self.assertFalse(series["editable"])

    def test_inactive_unit_remains_identifiable_without_exposing_historical_samples(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.artifact_root)
        diagram = self.fixture["diagram"]
        next(n for n in diagram["nodes"] if n["technical_key"] == "plant_1")["units"][0]["is_active"] = False
        self.store.save_hydraulic_diagram(scenario_id=self.fixture["scenario"]["id"], revision=diagram["revision"],
            nodes=diagram["nodes"], reaches=diagram["reaches"])
        body = self.read(run_id=run["id"])
        unit = next(c for c in body["components"] if c["entity_id"] == "unit_1")
        self.assertEqual(unit["series"]["points"], [])
        self.assertIn("inactivo", unit["series"]["message"])
        self.assertFalse(unit["is_active"])
        self.assertEqual(unit["parent_entity_id"], "plant_1")

    def test_selected_variant_uses_its_canonical_inflow_revision_instead_of_diagram_values(self):
        variant = self.store.create_case_input_variant(case_id=self.fixture["case"]["id"], display_name="Aporte alternativo")
        receipt = bind_hydraulic_mesa_inflow(self.store, self.fixture, variant)
        reservoir = next(c for c in self.read(variant_id=variant["id"])["components"] if c["entity_id"] == "reservoir")
        self.assertEqual([p["value"] for p in reservoir["series"]["points"]], [7, 9])
        self.assertEqual(reservoir["series"]["revision_id"], receipt["revision_id"])
        self.assertEqual(reservoir["series"]["source"], "canonical_binding")
        default = next(c for c in self.read()["components"] if c["entity_id"] == "reservoir")
        self.assertEqual([p["value"] for p in default["series"]["points"]], [2, 4])

    def test_unprepared_variant_does_not_silently_inherit_the_diagram_inflow(self):
        variant = self.store.create_case_input_variant(case_id=self.fixture["case"]["id"], display_name="Sin preparar")
        reservoir = next(c for c in self.read(variant_id=variant["id"])["components"] if c["entity_id"] == "reservoir")
        self.assertEqual(reservoir["series"]["status"], "unbound")
        self.assertEqual(reservoir["series"]["points"], [])
        self.assertIn("sin preparar", reservoir["series"]["message"])

    def test_simple_v2_hydro_keeps_its_scalar_storage_and_own_result_identity(self):
        self.fixture = seed_mesa_case(self.store)
        draft = self.store.get_scenario_draft(self.fixture["scenario"]["id"])["document"]
        example = json.loads((Path(__file__).parents[1] / "data/cases/linear_hydro_system/system_case.json").read_text())
        hydro = next(n for n in example["nodes"] if n["type"] == "hydro")
        draft["assets"].append(hydro)
        self.store.create_or_replace_scenario_draft(scenario_id=self.fixture["scenario"]["id"], document=draft)
        self.store.materialize_project_linkable_objects(project_id=self.fixture["project"]["id"])
        body = self.read()
        component = next((c for c in body["components"] if c["entity_id"] == "hydro_1"), None)
        self.assertIsNotNone(component)
        self.assertEqual(component["entity_type"], "component:hydro")
        self.assertEqual(component["series"]["signal_key"], "hydro_inflow_m3s")
        self.assertEqual(next(p for p in component["parameters"] if p["key"] == "initial_storage_hm3")["value"], 2.5)
        version = self.store.create_scenario_version(scenario_id=self.fixture["scenario"]["id"], system_case_json=example,
            validation_payload={"status": "ok"}, generation_metadata={"input_variant": {"id": self.fixture["variant"]["id"]}})
        run = self.store.create_run(scenario_version_id=version["id"])
        self.store.mark_run_running(run["id"], workspace_path=str(self.artifact_root), input_snapshot_path=str(self.artifact_root / "input.json"))
        self.store.mark_run_succeeded(run["id"], exit_code=0, stdout="", stderr="", success_payload={}, output_dir=str(self.artifact_root), summary_path=str(self.artifact_root / "summary.json"))
        self.store.replace_run_asset_dispatch_result_index(run_id=run["id"], scenario_version_id=version["id"],
            columns=["timestamp", "duration_hours", "asset_id", "asset_type", "hydro_power_mw"],
            rows=[{"timestamp": f"2026-01-01T0{i}:00:00", "duration_hours": 1, "asset_id": "hydro_1", "asset_type": "hydro", "hydro_power_mw": value} for i, value in enumerate([0.5, 1])])
        component = next(c for c in self.read(run_id=run["id"])["components"] if c["entity_id"] == "hydro_1")
        power = next(s for s in component["additional_series"] if s["signal_key"] == "hydro_generation_power_mw")
        self.assertEqual([p["value"] for p in power["points"]], [0.5, 1])

    def test_non_modeled_plant_does_not_present_a_historical_run_as_currently_compatible(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.artifact_root)
        diagram = self.fixture["diagram"]
        next(n for n in diagram["nodes"] if n["technical_key"] == "plant_1")["plant"]["non_modeled"] = True
        self.store.save_hydraulic_diagram(scenario_id=self.fixture["scenario"]["id"], revision=diagram["revision"],
            nodes=diagram["nodes"], reaches=diagram["reaches"])
        plant = next(c for c in self.read(run_id=run["id"])["components"] if c["entity_id"] == "plant_1")
        self.assertEqual(plant["series"]["points"], [])
        self.assertIn("no modelada", plant["series"]["message"])

    def test_canonical_reach_minimum_flow_is_visible_without_a_legacy_diagram_binding(self):
        receipt = bind_hydraulic_mesa_inflow(self.store, self.fixture, self.fixture["variant"], reach=True)
        reach = next(c for c in self.read()["components"] if c["entity_id"] == "reach")
        self.assertEqual(reach["series"]["signal_key"], "minimum_flow_m3s")
        self.assertEqual([p["value"] for p in reach["series"]["points"]], [7, 9])
        self.assertEqual(reach["series"]["revision_id"], receipt["revision_id"])

    def test_legacy_hydraulic_variant_reads_its_bound_catalog_source(self):
        variant = self.store.create_case_input_variant(case_id=self.fixture["case"]["id"], display_name="Aporte anterior")
        prepared = prepare_time_series_catalog_import(rows=[
            {"timestamp": f"2026-10-20T0{i}:00:00+00:00", "hours": "1", "flow": value} for i, value in enumerate(["11", "13"])],
            request=CatalogImportRequest(set_name="Aporte anterior", version_label="v1", data_kind="real", timezone="UTC",
                timestamp_column="timestamp", duration_hours_column="hours", signal_mappings=[CatalogSignalMappingRequest(source_column="flow", signal_key="natural_inflow_m3s")]))
        source = self.store.import_time_series_catalog_set(scenario_id=self.fixture["scenario"]["id"],
            source={"id": "legacy-flow", "original_filename": "flow.csv", "media_type": "text/csv", "checksum": "fixture"}, prepared_import=prepared)
        self.store.upsert_case_time_series_binding(case_input_variant_id=variant["id"], signal_key="natural_inflow_m3s",
            entity_type="hydraulic_node", entity_id="reservoir", time_series_set_id=source["id"])
        reservoir = next(c for c in self.read(variant_id=variant["id"])["components"] if c["entity_id"] == "reservoir")
        self.assertEqual([p["value"] for p in reservoir["series"]["points"]], [11, 13])
        self.assertEqual(reservoir["series"]["time_series_set_id"], source["id"])

    def test_hydraulic_results_use_artifact_fallback_and_reject_incomplete_columns(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.artifact_root)
        self.store.delete_run_asset_dispatch_result_index(run["id"])
        plant = next(c for c in self.read(run_id=run["id"])["components"] if c["entity_id"] == "plant_1")
        self.assertEqual([p["value"] for p in plant["series"]["points"]], [3, 6])
        self.store.replace_run_asset_dispatch_result_index(run_id=run["id"], scenario_version_id=run["scenario_version_id"],
            columns=["timestamp", "asset_id", "asset_type", "hydro_power_mw"],
            rows=[{"timestamp": "2026-10-20T00:00:00", "asset_id": "unit_1", "asset_type": "hydraulic_unit", "hydro_power_mw": ""}])
        plant = next(c for c in self.read(run_id=run["id"])["components"] if c["entity_id"] == "plant_1")
        self.assertEqual(plant["series"]["points"], [])
        self.assertIn("compatible", plant["series"]["message"])

    def test_changed_unit_connection_rejects_that_plant_but_preserves_other_results(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.artifact_root)
        diagram = self.fixture["diagram"]
        plant = next(n for n in diagram["nodes"] if n["technical_key"] == "plant_1")
        plant["units"][0]["intake_node_key"] = "reservoir"
        self.store.save_hydraulic_diagram(scenario_id=self.fixture["scenario"]["id"], revision=diagram["revision"], nodes=diagram["nodes"], reaches=diagram["reaches"])
        components = {c["entity_id"]: c for c in self.read(run_id=run["id"])["components"]}
        self.assertEqual(components["plant_1"]["series"]["points"], [])
        self.assertIn("compatible", components["plant_1"]["series"]["message"])
        self.assertEqual([p["value"] for p in components["plant_2"]["series"]["points"]], [9, 12])

    def test_missing_source_and_partial_periods_never_get_zero_filled(self):
        body = self.read(range_start="2026-10-20T00:00:00+00:00", range_end="2026-10-20T03:00:00+00:00")
        reservoir = next(c for c in body["components"] if c["entity_id"] == "reservoir")
        self.assertEqual(reservoir["series"]["status"], "no_coverage")
        self.assertEqual(reservoir["series"]["points"], [])
        diagram = self.fixture["diagram"]
        next(n for n in diagram["nodes"] if n["technical_key"] == "reservoir")["natural_inflow_series"] = None
        self.store.save_hydraulic_diagram(scenario_id=self.fixture["scenario"]["id"], revision=diagram["revision"], nodes=diagram["nodes"], reaches=diagram["reaches"])
        reservoir = next(c for c in self.read()["components"] if c["entity_id"] == "reservoir")
        self.assertEqual(reservoir["series"]["status"], "unbound")
        self.assertEqual(reservoir["series"]["points"], [])

    def test_hydraulic_case_run_and_variant_cannot_cross_authorized_context(self):
        other = seed_hydraulic_mesa(self.store, name="Otra red")
        other_run = seed_hydraulic_mesa_run(self.store, other, self.artifact_root)
        own_run = seed_hydraulic_mesa_run(self.store, self.fixture, self.artifact_root)
        pending = self.store.create_run(scenario_version_id=own_run["scenario_version_id"])
        for params in ({"case_id": other["case"]["id"]}, {"variant_id": other["variant"]["id"]},
                       {"run_id": other_run["id"]}, {"run_id": pending["id"]}):
            response = self.client.get(self.path, params={**self.params, **params})
            self.assertEqual(response.status_code, 404, response.text)
            self.assertNotIn("points", response.text)
        self.store.create_user(email="operator@example.local", display_name="Operador", role="external", password_hash=hash_password("operator pass"))
        external = TestClient(self.client.app)
        self.addCleanup(external.close)
        self.assertEqual(external.get(self.path, params=self.params).status_code, 401)
        self.assertEqual(login_json_with_csrf(external, "operator@example.local", "operator pass").status_code, 200)
        self.assertEqual(external.get(self.path, params=self.params).status_code, 404)

    def test_archived_unit_cannot_contribute_to_the_plant_result(self):
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.artifact_root)
        unit = next(c for c in self.read()["components"] if c["entity_id"] == "unit_1")
        self.store.archive_linkable_object(linkable_object_id=unit["linkable_object_id"])
        components = {c["entity_id"]: c for c in self.read(run_id=run["id"])["components"]}
        self.assertEqual(components["plant_1"]["series"]["points"], [])
        self.assertEqual(components["unit_1"]["series"]["points"], [])
        self.assertEqual([p["value"] for p in components["plant_2"]["series"]["points"]], [9, 12])

    def test_plant_power_sums_only_its_complete_frozen_unit_membership(self):
        diagram = self.fixture["diagram"]
        plant = next(n for n in diagram["nodes"] if n["technical_key"] == "plant_1")
        plant["units"].append({**plant["units"][0], "technical_key": "unit_3",
            "flow_power_curve": {"version_label": "v1", "points": [{"x_value": 0, "y_value": 0}, {"x_value": 40, "y_value": 30}]}})
        self.store.save_hydraulic_diagram(scenario_id=self.fixture["scenario"]["id"], revision=diagram["revision"], nodes=diagram["nodes"], reaches=diagram["reaches"])
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.artifact_root)
        incomplete = next(c for c in self.read(run_id=run["id"])["components"] if c["entity_id"] == "plant_1")
        self.assertEqual(incomplete["series"]["points"], [])
        index = self.store.get_run_asset_dispatch_result_index(run["id"])
        index["rows"].extend([{**row, "asset_id": "unit_3", "hydro_power_mw": value}
                              for row, value in zip([r for r in index["rows"] if r["asset_id"] == "unit_1"], [1, 2])])
        self.store.replace_run_asset_dispatch_result_index(run_id=run["id"], scenario_version_id=run["scenario_version_id"], columns=index["columns"], rows=index["rows"])
        plant = next(c for c in self.read(run_id=run["id"])["components"] if c["entity_id"] == "plant_1")
        self.assertEqual([p["value"] for p in plant["series"]["points"]], [4, 8])
        self.assertEqual(plant["series"]["source"], "asset_dispatch:plant_units")

    def test_compiled_plant_transit_keeps_results_attached_to_the_original_plant(self):
        diagram = self.fixture["diagram"]
        plant = next(n for n in diagram["nodes"] if n["technical_key"] == "plant_1")
        plant["link_transit"] = {"in:intake": {"travel_time_hours": 1, "travel_time_unit": "hours"}}
        self.store.save_hydraulic_diagram(scenario_id=self.fixture["scenario"]["id"], revision=diagram["revision"], nodes=diagram["nodes"], reaches=diagram["reaches"])
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.artifact_root)
        components = {c["entity_id"]: c for c in self.read(run_id=run["id"])["components"]}
        self.assertEqual([p["value"] for p in components["plant_1"]["series"]["points"]], [3, 6])
        self.assertEqual(components["unit_1"]["from_entity_id"], "intake")
