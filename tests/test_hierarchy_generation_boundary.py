import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import derive_case_hierarchy_views, generate_system_case_from_hierarchy
from tests.test_draft_generated_system_case import (
    RecordingValidationService,
    make_client_and_scenario,
    upload_mapped_csv,
)
from tests.test_hydraulic_diagram_hierarchy_provenance import base_reach, save_diagram
from tests.test_hydro_diagram_acceptance import HydroAcceptanceValidationService, complete_v3_nodes


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CASE_PATH = REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json"


class StructuredCaseGenerationBoundaryTests(unittest.TestCase):
    def test_structured_case_regenerates_with_matching_hierarchy_views(self):
        original = json.loads(SAMPLE_CASE_PATH.read_text())
        views = derive_case_hierarchy_views(original)

        regenerated = generate_system_case_from_hierarchy(views["topology"], views["parameters"])

        self.assertEqual(derive_case_hierarchy_views(regenerated), views)


class HydraulicCaseGenerationBoundaryTests(unittest.TestCase):
    def test_hydraulic_v3_case_regenerates_with_matching_hierarchy_views(self):
        validation_service = HydroAcceptanceValidationService()
        client = TestClient(
            create_app(validation_service=validation_service, database_url="sqlite:///:memory:")
        )
        project = client.post("/api/projects", json={"name": "Hierarchy boundary"}).json()
        scenario = client.post(
            f"/api/projects/{project['id']}/scenarios", json={"name": "Hydro case"}
        ).json()
        created = client.post(f"/api/scenarios/{scenario['id']}/hydraulic-diagram").json()["diagram"]
        save_diagram(client, scenario["id"], created["revision"])

        analyst_store = client.app.state.analyst_store
        original = analyst_store.generate_hydraulic_v3_preview(scenario["id"])
        views = derive_case_hierarchy_views(original)

        regenerated = generate_system_case_from_hierarchy(views["topology"], views["parameters"])

        self.assertEqual(derive_case_hierarchy_views(regenerated), views)
        result = validation_service.validate_text(json.dumps(regenerated, sort_keys=True))
        self.assertTrue(result.ok)


class ManualRunFromGeneratedScenarioVersionTests(unittest.TestCase):
    def test_manual_run_can_still_be_created_from_a_structured_draft_generated_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_csv(client, scenario["id"])

            client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")
            scenario_version = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote",
            ).json()

            run_response = client.post(f"/api/scenario-versions/{scenario_version['id']}/runs")

            self.assertEqual(run_response.status_code, 201)
            self.assertEqual(run_response.json()["status"], "queued")


if __name__ == "__main__":
    unittest.main()
