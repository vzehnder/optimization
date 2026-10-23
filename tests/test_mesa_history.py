"""MESA-013 public HTTP history/export behavior (S2)."""

import csv
import io
import unittest

from tests.auth_test_helpers import post_json_with_csrf

from tests import test_mesa_comparison as comparison_tests


class MesaHistoryApiTests(unittest.TestCase):
    setUp = comparison_tests.MesaComparisonApiTests.setUp
    launch = comparison_tests.MesaComparisonApiTests.launch
    succeed = comparison_tests.MesaComparisonApiTests.succeed
    edit_demand = comparison_tests.MesaComparisonApiTests.edit_demand
    comparison = comparison_tests.MesaComparisonApiTests.comparison

    def export(self, run, **changes):
        return post_json_with_csrf(self.client, self.path + "/comparison/export", {
            **self.params, "run_id": run["id"], "panels": [{"title": "BESS Norte",
                "entity_id": "battery_1", "entity_type": "component:battery",
                "series_keys": ["bess_discharge_power_mw"]}], **changes})

    def rows(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.headers["content-type"].startswith("text/csv"))
        return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))

    def test_history_recovers_original_run_after_edit_without_replacing_preparation(self):
        run = self.launch()
        self.succeed(run)
        self.edit_demand()
        for _ in range(2):
            response = self.client.get(self.path + "/history", params=self.params)
            self.assertEqual(response.status_code, 200, response.text)
            item, = response.json()["runs"]
            self.assertEqual(item["id"], run["id"])
            self.assertEqual(item["status"], "succeeded")
            self.assertEqual(item["variant_id"], self.params["variant_id"])
            self.assertEqual(item["scenario_version_id"], run["scenario_version_id"])
            self.assertEqual(item["range_start"], "2026-10-20T00:00:00-03:00")
            self.assertEqual(item["range_end"], "2026-10-20T02:00:00-03:00")
            frozen = self.comparison(item)
            demand = next(s for s in frozen["series"] if s["signal_key"] == "load_demand_mw")
            self.assertEqual([p["value"] for p in demand["after"]["points"]], [10, 12])
            current = self.client.get(self.path, params=self.params).json()
            demand = next(c for c in current["components"] if c["entity_id"] == "load_north")
            self.assertEqual(demand["series"]["points"][0]["value"], 12)

    def test_export_recovers_selected_series_with_literal_values_and_provenance(self):
        reference = self.launch("reference")
        self.succeed(reference, discharge=(1, 3), indexed=False)
        run = self.launch()
        self.succeed(run)
        self.edit_demand()
        response = self.export(run, reference_run_id=reference["id"])
        self.assertIn("attachment", response.headers.get("content-disposition", ""))
        rows = self.rows(response)
        self.assertEqual(len(rows), 2)
        self.assertEqual([(r["before"], r["after"], r["delta"]) for r in rows], [("1.0", "2.0", "1.0"), ("3.0", "0.0", "-3.0")])
        self.assertEqual(rows[0]["entity_id"], "battery_1")
        self.assertEqual(rows[0]["unit"], "MW")
        self.assertEqual(rows[0]["start"], "2026-10-20T00:00:00-03:00")
        self.assertEqual(rows[1]["end"], "2026-10-20T02:00:00-03:00")
        self.assertEqual(rows[0]["before_run_id"], str(reference["id"]))
        self.assertEqual(rows[0]["after_snapshot_id"], str(run["scenario_version_id"]))
        self.assertEqual(rows[0]["after_source"], "asset_dispatch")

    def test_export_uses_selected_range_and_mode_without_silent_resampling(self):
        reference = self.launch("reference")
        self.succeed(reference, discharge=(1, 3))
        run = self.launch()
        self.succeed(run)
        rows = self.rows(self.export(run, reference_run_id=reference["id"], mode="after",
            range_start="2026-10-20T04:00:00+00:00", range_end="2026-10-20T05:00:00+00:00"))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["before"], rows[0]["after"], rows[0]["delta"]), ("", "0.0", ""))
        self.assertEqual(rows[0]["before_run_id"], "")
        rows = self.rows(self.export(run, range_start="2026-10-20T03:30:00+00:00", range_end="2026-10-20T05:00:00+00:00"))
        self.assertEqual(rows[0]["after"], "")
        self.assertEqual(rows[0]["after_status"], "no_coverage")
        self.assertIn("cobertura", rows[0]["after_message"])

    def test_csv_escapes_formula_text_delimiters_and_preserves_numeric_negative_delta(self):
        reference = self.launch("reference")
        self.succeed(reference, discharge=(1, 3))
        run = self.launch()
        self.succeed(run)
        for title in ('=HYPERLINK("https://example.invalid","x"),\nnota', ' \t+SUM(1,2)', '-1+2', '@SUM(1)', '\ttexto', '\rtexto'):
            with self.subTest(title=title):
                rows = self.rows(self.export(run, reference_run_id=reference["id"], panels=[{
                    "title": title, "entity_id": "battery_1", "entity_type": "component:battery",
                    "series_keys": ["bess_discharge_power_mw"]}]))
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["view"], "'" + title)
                self.assertEqual(rows[1]["delta"], "-3.0")

    def test_export_does_not_assume_a_timezone_for_a_legacy_reference(self):
        from tests.mesa_fixture import seed_mesa_run
        reference = seed_mesa_run(self.store, self.fixture, self.temp.name, naive=True, frozen_zone=False)
        run = self.launch()
        self.succeed(run)
        rows = self.rows(self.export(run, reference_run_id=reference["id"]))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["status"] == "incompatible" and row["delta"] == "" for row in rows))
        self.assertTrue(all(not (row["before"] and row["after"]) for row in rows))
        self.assertEqual(sorted(row["before"] for row in rows if row["before"]), ["0.0", "2.0"])

    def test_history_and_export_enforce_context_session_csrf_and_successful_outputs(self):
        from fastapi.testclient import TestClient
        from app.auth import hash_password
        from tests.auth_test_helpers import login_json_with_csrf
        from tests.mesa_execution_fixture import seed_executable_mesa
        from tests.mesa_comparison_fixture import seed_comparison_runs
        run = self.launch()
        self.succeed(run)
        pending = self.launch("pending")
        failed = self.launch("failed")
        self.store.mark_run_failed(failed["id"], exit_code=1, stdout="", stderr="", error_payload={"message": "Falló"})
        other = seed_executable_mesa(self.store, name="Otro caso")
        seed_comparison_runs(self.store, other, self.temp.name)
        variant = self.store.create_case_input_variant(case_id=self.params["case_id"], display_name="Otra variante")
        history = self.client.get(self.path + "/history", params=self.params)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual({r["id"]: r["status"] for r in history.json()["runs"]}, {
            run["id"]: "succeeded", pending["id"]: "queued", failed["id"]: "failed"})
        self.assertEqual(self.client.get(self.path + "/history", params={**self.params, "variant_id": variant["id"]}).json()["runs"], [])
        for changes in ({"case_id": other["case"]["id"]}, {"variant_id": other["variant"]["id"]}):
            self.assertEqual(self.client.get(self.path + "/history", params={**self.params, **changes}).status_code, 404)
            self.assertEqual(self.export(run, **changes).status_code, 404)
        for unavailable in (pending, failed, other["run"]):
            self.assertEqual(self.export(unavailable).status_code, 404)
        self.assertEqual(self.export(run, panels=[{"title": "Ajena", "entity_id": "foreign", "entity_type": "component:battery", "series_keys": ["bess_discharge_power_mw"]}]).status_code, 400)
        self.assertEqual(self.client.post(self.path + "/comparison/export", json={}).status_code, 403)
        self.store.create_user(email="external@example.local", display_name="Externo", role="external", password_hash=hash_password("external pass"))
        with TestClient(self.client.app) as external:
            self.assertEqual(external.get(self.path + "/history", params=self.params).status_code, 401)
            self.assertEqual(post_json_with_csrf(external, self.path + "/comparison/export", {}).status_code, 401)
            login_json_with_csrf(external, "external@example.local", "external pass")
            self.assertEqual(external.get(self.path + "/history", params=self.params).status_code, 404)
            self.assertEqual(post_json_with_csrf(external, self.path + "/comparison/export", {}).status_code, 404)

    def test_export_falls_back_after_retention_and_reports_absence_without_zero(self):
        from pathlib import Path
        from app.auth import hash_password
        from tests.auth_test_helpers import login_json_with_csrf
        run = self.launch()
        self.succeed(run)
        before = self.rows(self.export(run))
        self.store.create_user(email="admin@example.local", display_name="Admin", role="admin", password_hash=hash_password("admin pass"))
        login_json_with_csrf(self.client, "admin@example.local", "admin pass")
        cleanup = post_json_with_csrf(self.client, f"/api/admin/runs/{run['id']}/cleanup-results", {"targets": ["asset_dispatch_table"]})
        self.assertEqual(cleanup.status_code, 200, cleanup.text)
        self.assertEqual(cleanup.json()["cleanup"]["removed"], ["asset_dispatch_table"])
        self.assertEqual(self.rows(self.export(run)), before)
        # Simulate external artifact loss; observations still use HTTP only.
        (Path(self.temp.name) / f"comparison-{run['id']}" / "asset_dispatch.csv").unlink()
        rows = self.rows(self.export(run))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["before"], rows[0]["after"], rows[0]["delta"]), ("", "", ""))
        self.assertEqual(rows[0]["after_status"], "unavailable")
        self.assertIn("Sin resultado", rows[0]["after_message"])
        self.assertEqual(rows[0]["after_run_id"], str(run["id"]))
        history = self.client.get(self.path + "/history", params=self.params).json()["runs"]
        self.assertEqual([r["id"] for r in history], [run["id"]])

    def test_export_includes_all_256_intervals_and_frozen_input_revision(self):
        from datetime import datetime, timedelta
        run = self.launch()
        original = self.client.get(f"/api/scenario-versions/{run['scenario_version_id']}").json()["scenario_version"]
        document = original["system_case_json"]
        start = datetime.fromisoformat("2026-10-20T00:00:00-03:00")
        document["time_series"] = [{**document["time_series"][0],
            "timestamp": (start + timedelta(hours=i)).isoformat()} for i in range(256)]
        version = self.store.create_scenario_version(scenario_id=self.fixture["scenario"]["id"], system_case_json=document,
            generation_metadata=original["generation_metadata"], validation_payload={"status": "ok"})
        historical = self.store.create_run(scenario_version_id=version["id"])
        self.store.mark_run_succeeded(historical["id"], exit_code=0, stdout="", stderr="", success_payload={"termination_status": "OPTIMAL"}, output_dir=None, summary_path=None)
        rows = self.rows(self.export(historical, panels=[{"title": "Demanda", "entity_id": "load_north", "entity_type": "component:load", "series_keys": ["load_demand_mw"]}]))
        self.assertEqual(len(rows), 256)
        self.assertEqual(rows[-1]["end"], "2026-10-30T16:00:00-03:00")
        self.assertTrue(all((r["before"], r["after"], r["delta"]) == ("10.0", "10.0", "0") for r in rows))
        self.assertEqual(rows[0]["before_revision_id"], str(self.fixture["receipt"]["revision_id"]))

    def test_history_keeps_executed_electrical_components_after_current_object_is_archived(self):
        run = self.launch()
        self.succeed(run)
        self.store.archive_linkable_object(linkable_object_id=self.fixture["object"]["id"])
        current = self.client.get(self.path, params=self.params).json()
        self.assertNotIn("load_north", [c["entity_id"] for c in current["components"]])
        frozen = self.comparison(run)
        component = next((c for c in frozen["components"] if c["entity_id"] == "load_north"), None)
        self.assertIsNotNone(component, "El inventario histórico procede del snapshot, no del catálogo actual")
        self.assertEqual([p["value"] for p in component["series"]["points"]], [10, 12])
        self.assertEqual(component["series"]["scenario_version_id"], run["scenario_version_id"])


class MesaHydraulicHistoryApiTests(unittest.TestCase):
    from tests import test_mesa_hydraulic_comparison as hydraulic_tests
    setUp = hydraulic_tests.MesaHydraulicComparisonTests.setUp
    export = MesaHistoryApiTests.export
    rows = MesaHistoryApiTests.rows

    def test_hydraulic_history_exports_selected_entities_units_and_compatible_deltas(self):
        from tests.mesa_hydraulic_fixture import seed_hydraulic_mesa_run
        reference = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name, volume=(10, 9), indexed=False)
        run = seed_hydraulic_mesa_run(self.store, self.fixture, self.temp.name)
        history = self.client.get(self.path + "/history", params=self.params)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual([r["id"] for r in history.json()["runs"]], [run["id"], reference["id"]])
        rows = self.rows(self.export(run, reference_run_id=reference["id"], panels=[
            {"title": "Embalse", "entity_id": "reservoir", "entity_type": "hydraulic_node", "series_keys": ["hydro_storage_volume_hm3"]},
            {"title": "Central Norte", "entity_id": "plant_1", "entity_type": "hydraulic_plant", "series_keys": ["hydro_generation_power_mw"]}]))
        self.assertEqual(len(rows), 4)
        volume = [r for r in rows if r["entity_id"] == "reservoir"]
        self.assertEqual([r["unit"] for r in volume], ["hm3", "hm3"])
        self.assertEqual([float(r["after"]) for r in volume], [9.8, 9.6])
        self.assertAlmostEqual(float(volume[0]["delta"]), -0.2)
        self.assertAlmostEqual(float(volume[1]["delta"]), 0.6)
        self.assertEqual([float(r["after"]) for r in rows if r["unit"] == "MW"], [3, 6])
        self.assertEqual(rows[0]["before_run_id"], str(reference["id"]))


if __name__ == "__main__":
    unittest.main()
