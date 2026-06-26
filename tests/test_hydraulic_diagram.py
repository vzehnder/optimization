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


if __name__ == "__main__":
    unittest.main()
