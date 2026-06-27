import unittest

from fastapi.testclient import TestClient

from app.main import create_app
from app.validation import ValidationResult


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
        )


class HydraulicDiagramApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
            )
        )
        project = self.client.post("/api/projects", json={"name": "Hydro Project"}).json()
        self.scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Hydraulic base case"},
        ).json()

    def test_minimal_hydraulic_diagram_can_be_saved_reloaded_and_rejects_stale_revision(self):
        create_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()["diagram"]
        self.assertEqual(created["scenario_id"], self.scenario["id"])
        self.assertEqual(created["nodes"], [])
        self.assertEqual(created["layout"]["layout_key"], "default")
        first_revision = created["revision"]

        save_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": first_revision,
                "viewport": {"x": 10.0, "y": 20.0, "zoom": 0.85},
                "nodes": [
                    {
                        "component_type": "reservoir",
                        "technical_key": "reservoir_alpha",
                        "display_name": "Reservoir Alpha",
                        "x": 120.0,
                        "y": 80.0,
                    },
                    {
                        "component_type": "junction",
                        "technical_key": "junction_a",
                        "display_name": "Junction A",
                        "x": 300.0,
                        "y": 110.0,
                    },
                    {
                        "component_type": "plant",
                        "technical_key": "plant_laja",
                        "display_name": "Plant Laja",
                        "x": 480.0,
                        "y": 140.0,
                    },
                ],
            },
        )

        self.assertEqual(save_response.status_code, 200)
        saved = save_response.json()["diagram"]
        self.assertNotEqual(saved["revision"], first_revision)
        self.assertEqual(saved["layout"]["viewport"], {"x": 10.0, "y": 20.0, "zoom": 0.85})
        self.assertEqual(
            [(node["component_type"], node["technical_key"], node["display_name"]) for node in saved["nodes"]],
            [
                ("reservoir", "reservoir_alpha", "Reservoir Alpha"),
                ("junction", "junction_a", "Junction A"),
                ("plant", "plant_laja", "Plant Laja"),
            ],
        )

        reload_response = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        )
        self.assertEqual(reload_response.status_code, 200)
        reloaded = reload_response.json()["diagram"]
        self.assertEqual(reloaded["revision"], saved["revision"])
        self.assertEqual(reloaded["nodes"], saved["nodes"])

        stale_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={"revision": first_revision, "nodes": saved["nodes"]},
        )
        self.assertEqual(stale_response.status_code, 409)
        self.assertIn("stale hydraulic diagram revision", stale_response.json()["detail"])

    def test_directed_reaches_can_be_saved_reloaded_and_validated(self):
        created = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]

        save_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
                    {
                        "component_type": "junction",
                        "technical_key": "junction_up",
                        "display_name": "Junction Up",
                        "x": 120.0,
                        "y": 80.0,
                    },
                    {
                        "component_type": "junction",
                        "technical_key": "junction_a",
                        "display_name": "Junction A",
                        "x": 300.0,
                        "y": 110.0,
                    },
                ],
                "reaches": [
                    {
                        "technical_key": "reach_alpha_junction",
                        "display_name": "Alpha to Junction",
                        "from_node_key": "junction_up",
                        "to_node_key": "junction_a",
                        "reach_type": "river",
                    }
                ],
            },
        )

        self.assertEqual(save_response.status_code, 200)
        saved = save_response.json()["diagram"]
        self.assertEqual(
            [
                (
                    reach["technical_key"],
                    reach["from_node_key"],
                    reach["to_node_key"],
                    reach["reach_type"],
                    reach["entity_type"],
                )
                for reach in saved["reaches"]
            ],
            [
                (
                    "reach_alpha_junction",
                    "junction_up",
                    "junction_a",
                    "river",
                    "case_hydraulic_reach",
                )
            ],
        )

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        self.assertEqual(reloaded["reaches"], saved["reaches"])

        validation_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        )
        self.assertEqual(validation_response.status_code, 200)
        validation = validation_response.json()["validation"]
        self.assertTrue(validation["ok"])
        self.assertEqual(validation["errors"], [])

    def test_directed_reach_validation_identifies_missing_inactive_and_bad_type_errors(self):
        created = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]

        invalid_type_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
                    {
                        "component_type": "junction",
                        "technical_key": "junction_up",
                        "display_name": "Junction Up",
                        "x": 120.0,
                        "y": 80.0,
                    },
                    {
                        "component_type": "junction",
                        "technical_key": "junction_a",
                        "display_name": "Junction A",
                        "x": 300.0,
                        "y": 110.0,
                    },
                ],
                "reaches": [
                    {
                        "technical_key": "bad_reach",
                        "display_name": "Bad Reach",
                        "from_node_key": "junction_up",
                        "to_node_key": "junction_a",
                        "reach_type": "siphon",
                    }
                ],
            },
        )
        self.assertEqual(invalid_type_response.status_code, 400)
        self.assertIn("unsupported hydraulic reach type", invalid_type_response.json()["detail"])

        missing_endpoint_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
                    {
                        "component_type": "junction",
                        "technical_key": "junction_up",
                        "display_name": "Junction Up",
                        "x": 120.0,
                        "y": 80.0,
                    },
                    {
                        "component_type": "junction",
                        "technical_key": "junction_a",
                        "display_name": "Junction A",
                        "x": 300.0,
                        "y": 110.0,
                    },
                ],
                "reaches": [
                    {
                        "technical_key": "reach_missing",
                        "display_name": "Missing endpoint",
                        "from_node_key": "junction_up",
                        "to_node_key": "junction_missing",
                        "reach_type": "canal",
                    }
                ],
            },
        )
        self.assertEqual(missing_endpoint_response.status_code, 400)
        self.assertIn("hydraulic reach endpoint not found", missing_endpoint_response.json()["detail"])

        first_save_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": created["revision"],
                "nodes": [
                    {
                        "component_type": "junction",
                        "technical_key": "junction_up",
                        "display_name": "Junction Up",
                        "x": 120.0,
                        "y": 80.0,
                    },
                    {
                        "component_type": "junction",
                        "technical_key": "junction_a",
                        "display_name": "Junction A",
                        "x": 300.0,
                        "y": 110.0,
                    },
                ],
                "reaches": [
                    {
                        "technical_key": "reach_missing",
                        "display_name": "Missing endpoint",
                        "from_node_key": "junction_up",
                        "to_node_key": "junction_a",
                        "reach_type": "canal",
                    }
                ],
            },
        )
        self.assertEqual(first_save_response.status_code, 200)

        save_response = self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={
                "revision": first_save_response.json()["diagram"]["revision"],
                "nodes": [
                    {
                        "component_type": "junction",
                        "technical_key": "junction_up",
                        "display_name": "Junction Up",
                        "x": 120.0,
                        "y": 80.0,
                    }
                ],
                "reaches": [
                    {
                        "technical_key": "reach_missing",
                        "display_name": "Missing endpoint",
                        "from_node_key": "junction_up",
                        "to_node_key": "junction_a",
                        "reach_type": "canal",
                    }
                ],
            },
        )
        self.assertEqual(save_response.status_code, 200)

        validation_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        )
        self.assertEqual(validation_response.status_code, 200)
        validation = validation_response.json()["validation"]
        self.assertFalse(validation["ok"])
        self.assertEqual(validation["warnings"], [])
        self.assertEqual(
            [
                (
                    error["code"],
                    error["entity_type"],
                    error["entity_id"],
                    error["technical_key"],
                )
                for error in validation["errors"]
            ],
            [
                (
                    "inactive_or_missing_endpoint",
                    "case_hydraulic_reach",
                    save_response.json()["diagram"]["reaches"][0]["entity_id"],
                    "reach_missing",
                )
            ],
        )


    def _create_diagram(self):
        return self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]

    def _save(self, revision, *, reservoir=None, curve=None):
        node = {
            "component_type": "reservoir",
            "technical_key": "reservoir_alpha",
            "display_name": "Reservoir Alpha",
            "x": 120.0,
            "y": 80.0,
        }
        if reservoir is not None:
            node["reservoir"] = reservoir
        if curve is not None:
            node["storage_elevation_curve"] = curve
        return self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={"revision": revision, "nodes": [node]},
        )

    def _reservoir_node(self, diagram):
        return next(
            node for node in diagram["nodes"] if node["component_type"] == "reservoir"
        )

    def test_reservoir_parameters_and_storage_elevation_curve_persist_and_reload(self):
        created = self._create_diagram()
        reservoir = {
            "storage_min_hm3": 5.0,
            "storage_max_hm3": 50.0,
            "initial_storage_hm3": 20.0,
            "terminal_condition": "equal_initial",
            "terminal_water_value_usd_per_hm3": 12.5,
        }
        curve = {
            "version_label": "v1",
            "points": [
                {"x_value": 5.0, "y_value": 700.0},
                {"x_value": 50.0, "y_value": 760.0},
            ],
        }
        response = self._save(created["revision"], reservoir=reservoir, curve=curve)
        self.assertEqual(response.status_code, 200)
        node = self._reservoir_node(response.json()["diagram"])
        self.assertEqual(node["reservoir"]["storage_min_hm3"], 5.0)
        self.assertEqual(node["reservoir"]["storage_max_hm3"], 50.0)
        self.assertEqual(node["reservoir"]["initial_storage_hm3"], 20.0)
        self.assertEqual(node["reservoir"]["terminal_condition"], "equal_initial")
        self.assertIsNone(node["reservoir"]["terminal_storage_min_hm3"])
        self.assertEqual(node["reservoir"]["terminal_water_value_usd_per_hm3"], 12.5)
        self.assertEqual(node["storage_elevation_curve"]["version_number"], 1)
        self.assertEqual(node["storage_elevation_curve"]["version_label"], "v1")
        self.assertEqual(
            node["storage_elevation_curve"]["points"],
            [
                {"x_value": 5.0, "y_value": 700.0},
                {"x_value": 50.0, "y_value": 760.0},
            ],
        )
        self.assertEqual(len(node["available_curves"]), 1)
        first_curve_set_id = node["storage_elevation_curve"]["curve_set_id"]

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        self.assertEqual(self._reservoir_node(reloaded), node)

        # Editing points to a new shape creates a new version.
        edited_curve = {
            "version_label": "v2",
            "points": [
                {"x_value": 5.0, "y_value": 705.0},
                {"x_value": 50.0, "y_value": 765.0},
            ],
        }
        edited = self._save(
            reloaded["revision"], reservoir=reservoir, curve=edited_curve
        )
        edited_node = self._reservoir_node(edited.json()["diagram"])
        self.assertEqual(edited_node["storage_elevation_curve"]["version_number"], 2)
        self.assertNotEqual(
            edited_node["storage_elevation_curve"]["curve_set_id"], first_curve_set_id
        )
        self.assertEqual(len(edited_node["available_curves"]), 2)

        # Selecting an existing version by id reuses it without a new version.
        selected = self._save(
            edited.json()["diagram"]["revision"],
            reservoir=reservoir,
            curve={"curve_set_id": first_curve_set_id},
        )
        selected_node = self._reservoir_node(selected.json()["diagram"])
        self.assertEqual(
            selected_node["storage_elevation_curve"]["curve_set_id"], first_curve_set_id
        )
        self.assertEqual(selected_node["storage_elevation_curve"]["version_number"], 1)
        self.assertEqual(len(selected_node["available_curves"]), 2)

    def test_validation_requires_reservoir_parameters_and_curve(self):
        created = self._create_diagram()
        save_response = self._save(created["revision"])
        self.assertEqual(save_response.status_code, 200)

        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertFalse(validation["ok"])
        codes = {error["code"] for error in validation["errors"]}
        self.assertIn("missing_reservoir_parameters", codes)
        self.assertIn("missing_storage_elevation_curve", codes)
        for error in validation["errors"]:
            if error["code"] in {
                "missing_reservoir_parameters",
                "missing_storage_elevation_curve",
            }:
                self.assertEqual(error["entity_type"], "case_hydraulic_node")
                self.assertEqual(error["technical_key"], "reservoir_alpha")

    def test_validation_rejects_bad_curve_and_terminal_settings(self):
        created = self._create_diagram()
        bad_reservoir = {
            "storage_min_hm3": 1.0,
            "storage_max_hm3": 200.0,
            "initial_storage_hm3": 20.0,
            "terminal_condition": "min_terminal",
            "terminal_water_value_usd_per_hm3": 0.0,
        }
        bad_curve = {
            "version_label": "bad",
            "points": [
                {"x_value": 50.0, "y_value": 760.0},
                {"x_value": 5.0, "y_value": 700.0},
            ],
        }
        save_response = self._save(
            created["revision"], reservoir=bad_reservoir, curve=bad_curve
        )
        self.assertEqual(save_response.status_code, 200)

        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertFalse(validation["ok"])
        codes = {error["code"] for error in validation["errors"]}
        self.assertIn("non_increasing_storage_points", codes)
        self.assertIn("storage_bounds_outside_curve_domain", codes)
        self.assertIn("invalid_terminal_settings", codes)

    def test_validation_passes_for_complete_reservoir(self):
        created = self._create_diagram()
        reservoir = {
            "storage_min_hm3": 5.0,
            "storage_max_hm3": 50.0,
            "initial_storage_hm3": 20.0,
            "terminal_condition": "min_terminal",
            "terminal_storage_min_hm3": 10.0,
            "terminal_water_value_usd_per_hm3": 8.0,
        }
        curve = {
            "version_label": "v1",
            "points": [
                {"x_value": 5.0, "y_value": 700.0},
                {"x_value": 25.0, "y_value": 730.0},
                {"x_value": 50.0, "y_value": 760.0},
            ],
        }
        save_response = self._save(created["revision"], reservoir=reservoir, curve=curve)
        self.assertEqual(save_response.status_code, 200)

        validation = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram/validate"
        ).json()["validation"]
        self.assertTrue(validation["ok"])
        self.assertEqual(validation["errors"], [])


if __name__ == "__main__":
    unittest.main()
