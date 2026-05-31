import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.validation import ValidationResult


REPO_ROOT = Path(__file__).resolve().parents[1]


class StructuredDraftEditorTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
            )
        )
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        self.scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()

    def test_api_generates_one_bus_graph_from_structured_draft_assets(self):
        draft_document = {
            "schema_version": "bess_editor_draft.v1",
            "case": {"name": "structured_case", "description": "Form-authored one-bus case"},
            "pcc": {"id": "bus_main", "type": "bus", "name": "Main PCC"},
            "grid": {
                "id": "grid_import_export",
                "import_power_max_mw": 7.5,
                "export_power_max_mw": 6.0,
                "prevent_simultaneous_grid_import_export": False,
            },
            "assets": [
                {
                    "id": "battery_alpha",
                    "type": "battery",
                    "charge_power_max_mw": 2.0,
                    "discharge_power_max_mw": 3.0,
                    "energy_min_mwh": 0.5,
                    "energy_max_mwh": 8.0,
                    "initial_energy_mwh": 4.0,
                    "charge_efficiency": 0.96,
                    "discharge_efficiency": 0.94,
                    "degradation_cost_per_mwh_delta_soc": 1.25,
                    "terminal_condition": "min_terminal",
                    "terminal_energy_min_mwh": 2.0,
                    "prevent_simultaneous_charge_discharge": True,
                    "degradation_linear_delta_soc": True,
                },
                {
                    "id": "solar_north",
                    "type": "renewable",
                    "category": "solar",
                    "curtailment_penalty_usd_per_mwh": 0.75,
                },
                {"id": "site_load", "type": "load"},
            ],
            "solver": {"name": "HiGHS", "options": {"time_limit": 60}},
        }

        update_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/draft",
            json={"document": draft_document},
        )
        self.assertEqual(update_response.status_code, 201)

        preview_response = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/draft/generated-system-case",
        )

        self.assertEqual(preview_response.status_code, 200)
        system_case = preview_response.json()["system_case"]
        self.assertEqual(system_case["schema_version"], "bess_system_dispatch.v1")
        self.assertEqual(system_case["case_name"], "structured_case")
        self.assertEqual(
            {node["id"]: node["type"] for node in system_case["nodes"]},
            {
                "bus_main": "bus",
                "grid_import_export": "grid",
                "battery_alpha": "battery",
                "solar_north": "renewable",
                "site_load": "load",
            },
        )
        self.assertEqual(
            system_case["edges"],
            [
                {"from": "grid_import_export", "to": "bus_main"},
                {"from": "battery_alpha", "to": "bus_main"},
                {"from": "solar_north", "to": "bus_main"},
                {"from": "site_load", "to": "bus_main"},
            ],
        )
        battery = next(node for node in system_case["nodes"] if node["id"] == "battery_alpha")
        self.assertEqual(battery["terminal_condition"], "min_terminal")
        self.assertEqual(battery["terminal_energy_min_mwh"], 2.0)
        renewable = next(node for node in system_case["nodes"] if node["id"] == "solar_north")
        self.assertEqual(renewable["display_category"], "solar")
        self.assertEqual(system_case["solver"], {"name": "HiGHS", "options": {"time_limit": 60}})

    def test_generated_preview_rejects_duplicate_asset_ids_and_bad_solver_options(self):
        duplicate_document = {
            "schema_version": "bess_editor_draft.v1",
            "case": {"name": "bad_ids"},
            "pcc": {"id": "bus_1"},
            "grid": {"id": "grid_1"},
            "assets": [
                {"id": "asset_1", "type": "renewable"},
                {"id": "asset_1", "type": "load"},
            ],
            "solver": {"name": "HiGHS", "options": {}},
        }
        self.client.post(
            f"/api/scenarios/{self.scenario['id']}/draft",
            json={"document": duplicate_document},
        )

        duplicate_response = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/draft/generated-system-case",
        )

        self.assertEqual(duplicate_response.status_code, 400)
        self.assertIn("duplicate asset id: asset_1", duplicate_response.json()["detail"])

        bad_solver_document = dict(duplicate_document)
        bad_solver_document["assets"] = [{"id": "asset_1", "type": "load"}]
        bad_solver_document["solver"] = {"name": "HiGHS", "options": "time_limit=60"}
        self.client.post(
            f"/api/scenarios/{self.scenario['id']}/draft",
            json={"document": bad_solver_document},
        )

        solver_response = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/draft/generated-system-case",
        )

        self.assertEqual(solver_response.status_code, 400)
        self.assertIn("solver options must be a JSON object", solver_response.json()["detail"])

    def test_ssr_structured_form_edits_case_grid_assets_and_solver(self):
        draft_page = self.client.get(f"/scenarios/{self.scenario['id']}/draft")
        self.assertEqual(draft_page.status_code, 200)
        for expected in [
            'name="case_name"',
            'name="pcc_id"',
            'name="grid_import_power_max_mw"',
            'name="battery_id"',
            'name="renewable_id"',
            'name="load_id"',
            'name="solver_options_json"',
        ]:
            self.assertIn(expected, draft_page.text)

        form_response = self.client.post(
            f"/scenarios/{self.scenario['id']}/draft/structure",
            data={
                "case_name": "ui_structured_case",
                "case_description": "Saved through SSR form",
                "pcc_id": "pcc_1",
                "grid_id": "grid_1",
                "grid_import_power_max_mw": "10.0",
                "grid_export_power_max_mw": "9.0",
                "grid_prevent_simultaneous_grid_import_export": "on",
                "battery_id": "battery_1",
                "battery_charge_power_max_mw": "4.0",
                "battery_discharge_power_max_mw": "5.0",
                "battery_energy_min_mwh": "1.0",
                "battery_energy_max_mwh": "12.0",
                "battery_initial_energy_mwh": "6.0",
                "battery_charge_efficiency": "0.95",
                "battery_discharge_efficiency": "0.94",
                "battery_degradation_cost_per_mwh_delta_soc": "0.4",
                "battery_terminal_condition": "equal_initial",
                "battery_prevent_simultaneous_charge_discharge": "on",
                "battery_degradation_linear_delta_soc": "on",
                "renewable_id": "wind_1",
                "renewable_category": "wind",
                "renewable_curtailment_penalty_usd_per_mwh": "0.2",
                "load_id": "load_1",
                "solver_name": "HiGHS",
                "solver_options_json": '{"mip_rel_gap": 0.01}',
            },
            follow_redirects=False,
        )

        self.assertEqual(form_response.status_code, 303)
        self.assertEqual(form_response.headers["location"], f"/scenarios/{self.scenario['id']}/draft")

        draft = self.client.get(f"/api/scenarios/{self.scenario['id']}/draft").json()["draft"]["document"]
        self.assertEqual(draft["case"]["name"], "ui_structured_case")
        self.assertEqual(draft["grid"]["import_power_max_mw"], 10.0)
        self.assertEqual([asset["id"] for asset in draft["assets"]], ["battery_1", "wind_1", "load_1"])
        self.assertEqual(draft["solver"]["options"], {"mip_rel_gap": 0.01})

        preview = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/draft/generated-system-case",
        ).json()["system_case"]
        self.assertEqual(preview["case_name"], "ui_structured_case")
        self.assertEqual(preview["edges"][0], {"from": "grid_1", "to": "pcc_1"})

    def test_draft_initialized_from_version_prefills_structured_assets(self):
        sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()
        version = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/versions",
            json={"system_case_json": sample_text},
        ).json()

        draft_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/draft",
            json={"source_version_id": version["id"]},
        )

        self.assertEqual(draft_response.status_code, 201)
        document = draft_response.json()["document"]
        self.assertEqual(document["pcc"], {"id": "bus_1", "type": "bus"})
        self.assertEqual(document["grid"]["id"], "grid_1")
        self.assertEqual(
            [(asset["id"], asset["type"]) for asset in document["assets"]],
            [("solar_1", "renewable"), ("battery_1", "battery"), ("load_1", "load")],
        )

        preview_response = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/draft/generated-system-case",
        )
        self.assertEqual(preview_response.status_code, 200)
        preview = preview_response.json()["system_case"]
        self.assertEqual({edge["from"] for edge in preview["edges"]}, {"grid_1", "solar_1", "battery_1", "load_1"})


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
        )


if __name__ == "__main__":
    unittest.main()
