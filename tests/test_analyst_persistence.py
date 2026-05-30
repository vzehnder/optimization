import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.validation import ValidationResult


REPO_ROOT = Path(__file__).resolve().parents[1]


class StubValidationService:
    def __init__(self, result=None):
        self.result = result or ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok", "case_name": "stub_case", "schema_version": "bess_system_dispatch.v1"},
        )
        self.candidates = []

    def validate_text(self, candidate_text):
        self.candidates.append(candidate_text)
        return self.result


class AnalystPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.validation_service = StubValidationService()
        self.client = TestClient(
            create_app(
                validation_service=self.validation_service,
                database_url="sqlite:///:memory:",
            )
        )

    def test_project_can_be_created_listed_and_opened_through_api(self):
        create_response = self.client.post(
            "/api/projects",
            json={"name": "Hybrid PMGD", "description": "Analyst workspace"},
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["name"], "Hybrid PMGD")
        self.assertEqual(created["description"], "Analyst workspace")
        self.assertIn("created_at", created)

        list_response = self.client.get("/api/projects")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([project["id"] for project in list_response.json()["projects"]], [created["id"]])

        detail_response = self.client.get(f"/api/projects/{created['id']}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["project"]["name"], "Hybrid PMGD")

    def test_scenario_can_be_created_listed_and_opened_under_project(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()

        create_response = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case", "description": "Initial modeling branch"},
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["project_id"], project["id"])
        self.assertEqual(created["name"], "Base case")
        self.assertIn("created_at", created)

        list_response = self.client.get(f"/api/projects/{project['id']}/scenarios")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([scenario["id"] for scenario in list_response.json()["scenarios"]], [created["id"]])

        detail_response = self.client.get(f"/api/scenarios/{created['id']}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["scenario"]["description"], "Initial modeling branch")

    def test_valid_system_case_is_saved_as_scenario_version_with_metadata(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()
        sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()

        create_response = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": sample_text},
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["scenario_id"], scenario["id"])
        self.assertEqual(created["version_number"], 1)
        self.assertEqual(created["case_name"], "hybrid_system")
        self.assertEqual(created["schema_version"], "bess_system_dispatch.v1")
        self.assertEqual(created["period_count"], 4)
        self.assertEqual(created["asset_counts"], {"battery": 1, "grid": 1, "load": 1, "renewable": 1})
        self.assertEqual(self.validation_service.candidates, [sample_text])

        list_response = self.client.get(f"/api/scenarios/{scenario['id']}/versions")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([version["id"] for version in list_response.json()["versions"]], [created["id"]])

        detail_response = self.client.get(f"/api/scenario-versions/{created['id']}")
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()["scenario_version"]
        self.assertEqual(detail["system_case_json"], json.loads(sample_text))

    def test_project_and_scenario_pages_render_persisted_workflow(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()
        sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()
        self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": sample_text},
        )

        projects_page = self.client.get("/projects")
        self.assertEqual(projects_page.status_code, 200)
        self.assertIn("Hybrid PMGD", projects_page.text)
        self.assertIn('action="/projects"', projects_page.text)

        project_page = self.client.get(f"/projects/{project['id']}")
        self.assertEqual(project_page.status_code, 200)
        self.assertIn("Base case", project_page.text)
        self.assertIn(f'action="/projects/{project["id"]}/scenarios"', project_page.text)

        scenario_page = self.client.get(f"/scenarios/{scenario['id']}")
        self.assertEqual(scenario_page.status_code, 200)
        self.assertIn("Version 1", scenario_page.text)
        self.assertIn("hybrid_system", scenario_page.text)
        self.assertIn('name="system_case_json"', scenario_page.text)

    def test_invalid_system_case_is_not_saved_as_version(self):
        self.validation_service.result = ValidationResult(
            ok=False,
            phase="julia",
            message="schema_version is required",
            payload={"status": "error", "message": "schema_version is required"},
        )
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()

        create_response = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": "{}"},
        )

        self.assertEqual(create_response.status_code, 400)
        self.assertIn("schema_version is required", create_response.json()["message"])

        list_response = self.client.get(f"/api/scenarios/{scenario['id']}/versions")
        self.assertEqual(list_response.json()["versions"], [])

    def test_uploaded_json_uses_same_validation_and_persistence_path_as_paste(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()
        sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()

        create_response = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions/upload",
            files={"system_case_file": ("system_case.json", sample_text, "application/json")},
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["version_number"], 1)
        self.assertEqual(created["case_name"], "hybrid_system")
        self.assertEqual(self.validation_service.candidates, [sample_text])

        detail = self.client.get(f"/api/scenario-versions/{created['id']}").json()["scenario_version"]
        self.assertEqual(detail["system_case_json"], json.loads(sample_text))

    def test_new_version_from_existing_json_preserves_previous_version(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()
        sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()
        first = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": sample_text},
        ).json()
        original_document = self.client.get(f"/api/scenario-versions/{first['id']}").json()["scenario_version"][
            "system_case_json"
        ]
        variant_document = dict(original_document)
        variant_document["case_name"] = "hybrid_variant"

        second_response = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": json.dumps(variant_document)},
        )

        self.assertEqual(second_response.status_code, 201)
        second = second_response.json()
        self.assertEqual(second["version_number"], 2)
        self.assertEqual(second["case_name"], "hybrid_variant")

        first_after = self.client.get(f"/api/scenario-versions/{first['id']}").json()["scenario_version"]
        self.assertEqual(first_after["system_case_json"], original_document)

        versions = self.client.get(f"/api/scenarios/{scenario['id']}/versions").json()["versions"]
        self.assertEqual([(version["version_number"], version["case_name"]) for version in versions], [
            (1, "hybrid_system"),
            (2, "hybrid_variant"),
        ])

        overwrite_response = self.client.put(
            f"/api/scenario-versions/{first['id']}",
            json={"system_case_json": json.dumps(variant_document)},
        )
        self.assertEqual(overwrite_response.status_code, 405)

    def test_scenario_page_supports_upload_and_new_version_from_existing_json(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()
        sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()
        version = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": sample_text},
        ).json()

        scenario_page = self.client.get(f"/scenarios/{scenario['id']}")
        self.assertEqual(scenario_page.status_code, 200)
        self.assertIn('enctype="multipart/form-data"', scenario_page.text)
        self.assertIn('type="file"', scenario_page.text)
        self.assertIn('name="system_case_file"', scenario_page.text)

        from_existing_page = self.client.get(f"/scenarios/{scenario['id']}?from_version_id={version['id']}")
        self.assertEqual(from_existing_page.status_code, 200)
        self.assertIn("&quot;case_name&quot;: &quot;hybrid_system&quot;", from_existing_page.text)

    def test_scenario_page_upload_form_creates_version(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()
        sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()

        response = self.client.post(
            f"/scenarios/{scenario['id']}/versions",
            files={"system_case_file": ("system_case.json", sample_text, "application/json")},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        versions = self.client.get(f"/api/scenarios/{scenario['id']}/versions").json()["versions"]
        self.assertEqual([(version["version_number"], version["case_name"]) for version in versions], [
            (1, "hybrid_system"),
        ])

    def test_scenario_page_shows_validation_error_without_saving_version(self):
        self.validation_service.result = ValidationResult(
            ok=False,
            phase="julia",
            message="schema_version is required",
            payload={"status": "error", "message": "schema_version is required"},
        )
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()

        response = self.client.post(
            f"/scenarios/{scenario['id']}/versions",
            data={"system_case_json": "{}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Validation Error", response.text)
        self.assertIn("schema_version is required", response.text)
        self.assertEqual(self.client.get(f"/api/scenarios/{scenario['id']}/versions").json()["versions"], [])


if __name__ == "__main__":
    unittest.main()
