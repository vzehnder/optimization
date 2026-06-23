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

    def test_scenario_draft_can_be_created_read_and_updated_without_creating_version(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()
        draft_document = {
            "schema_version": "bess_editor_draft.v1",
            "case": {"name": "Working draft"},
            "assets": [],
        }

        create_response = self.client.post(
            f"/api/scenarios/{scenario['id']}/draft",
            json={"document": draft_document},
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["scenario_id"], scenario["id"])
        self.assertEqual(created["document"], draft_document)
        self.assertIsNone(created["source_version_id"])

        read_response = self.client.get(f"/api/scenarios/{scenario['id']}/draft")
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.json()["draft"]["id"], created["id"])

        updated_document = {
            "schema_version": "bess_editor_draft.v1",
            "case": {"name": "Edited draft"},
            "assets": [{"id": "battery_1", "type": "battery"}],
        }
        update_response = self.client.put(
            f"/api/scenarios/{scenario['id']}/draft",
            json={"document": updated_document},
        )

        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated["id"], created["id"])
        self.assertEqual(updated["document"], updated_document)

        recreate_response = self.client.post(
            f"/api/scenarios/{scenario['id']}/draft",
            json={"document": draft_document},
        )
        self.assertEqual(recreate_response.status_code, 201)
        self.assertEqual(recreate_response.json()["id"], created["id"])

        versions_response = self.client.get(f"/api/scenarios/{scenario['id']}/versions")
        self.assertEqual(versions_response.json()["versions"], [])

    def test_scenario_draft_can_start_from_version_without_mutating_source_version(self):
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
        original_version_document = self.client.get(
            f"/api/scenario-versions/{version['id']}"
        ).json()["scenario_version"]["system_case_json"]

        create_response = self.client.post(
            f"/api/scenarios/{scenario['id']}/draft",
            json={"source_version_id": version["id"]},
        )

        self.assertEqual(create_response.status_code, 201)
        draft = create_response.json()
        self.assertEqual(draft["source_version_id"], version["id"])
        self.assertEqual(draft["document"]["schema_version"], "bess_editor_draft.v1")
        self.assertEqual(draft["document"]["case"]["name"], "hybrid_system")
        self.assertEqual(draft["document"]["source"]["kind"], "scenario_version")
        self.assertEqual(draft["document"]["source"]["scenario_version_id"], version["id"])
        self.assertEqual(draft["document"]["system_case_seed"], original_version_document)

        edited_document = dict(draft["document"])
        edited_document["case"] = {"name": "Edited structured draft"}
        update_response = self.client.put(
            f"/api/scenarios/{scenario['id']}/draft",
            json={"document": edited_document},
        )
        self.assertEqual(update_response.status_code, 200)

        source_after_update = self.client.get(
            f"/api/scenario-versions/{version['id']}"
        ).json()["scenario_version"]["system_case_json"]
        self.assertEqual(source_after_update, original_version_document)

    def test_scenario_draft_page_exposes_basic_view_and_save_flow(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()

        scenario_page = self.client.get(f"/scenarios/{scenario['id']}")
        self.assertEqual(scenario_page.status_code, 200)
        self.assertIn(f'href="/scenarios/{scenario["id"]}/draft"', scenario_page.text)

        draft_page = self.client.get(f"/scenarios/{scenario['id']}/draft")
        self.assertEqual(draft_page.status_code, 200)
        self.assertIn("Structured Draft", draft_page.text)
        self.assertIn('name="structured_draft_json"', draft_page.text)
        self.assertIn(f'action="/scenarios/{scenario["id"]}/draft"', draft_page.text)

        saved_document = {
            "schema_version": "bess_editor_draft.v1",
            "case": {"name": "Saved draft"},
            "assets": [{"id": "battery_1", "type": "battery"}],
        }
        save_response = self.client.post(
            f"/scenarios/{scenario['id']}/draft",
            data={"structured_draft_json": json.dumps(saved_document)},
            follow_redirects=False,
        )

        self.assertEqual(save_response.status_code, 303)
        self.assertEqual(save_response.headers["location"], f"/scenarios/{scenario['id']}/draft")

        saved_page = self.client.get(f"/scenarios/{scenario['id']}/draft")
        self.assertEqual(saved_page.status_code, 200)
        self.assertIn("&quot;Saved draft&quot;", saved_page.text)
        self.assertEqual(self.client.get(f"/api/scenarios/{scenario['id']}/versions").json()["versions"], [])

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

    def test_scenario_versions_can_be_deleted_from_api_and_page(self):
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
        second = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": sample_text},
        ).json()

        page = self.client.get(f"/scenarios/{scenario['id']}")
        self.assertIn(f'action="/scenario-versions/{first["id"]}/delete"', page.text)
        self.assertIn("Delete Version", page.text)
        self.assertIn("Versions referenced by runs or publications are protected", page.text)

        delete_response = self.client.delete(f"/api/scenario-versions/{first['id']}")

        self.assertEqual(delete_response.status_code, 200)
        deleted = delete_response.json()["deleted_version"]
        self.assertEqual(deleted["id"], first["id"])
        self.assertEqual(deleted["deleted_run_count"], 0)
        self.assertEqual(self.client.get(f"/api/scenario-versions/{first['id']}").status_code, 404)
        remaining = self.client.get(f"/api/scenarios/{scenario['id']}/versions").json()["versions"]
        self.assertEqual([version["id"] for version in remaining], [second["id"]])

        page_delete_response = self.client.post(
            f"/scenario-versions/{second['id']}/delete",
            follow_redirects=False,
        )
        self.assertEqual(page_delete_response.status_code, 303)
        self.assertEqual(page_delete_response.headers["location"], f"/scenarios/{scenario['id']}")
        self.assertEqual(self.client.get(f"/api/scenarios/{scenario['id']}/versions").json()["versions"], [])

    def test_scenario_version_with_active_run_cannot_be_deleted(self):
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
        self.client.app.state.analyst_store.create_run(scenario_version_id=version["id"])

        delete_response = self.client.delete(f"/api/scenario-versions/{version['id']}")

        self.assertEqual(delete_response.status_code, 409)
        self.assertIn("referenced by runs", delete_response.json()["detail"])
        self.assertEqual(self.client.get(f"/api/scenario-versions/{version['id']}").status_code, 200)

    def test_scenario_version_with_completed_run_cannot_be_deleted(self):
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
        store = self.client.app.state.analyst_store
        run = store.create_run(scenario_version_id=version["id"])
        store.mark_run_running(
            run["id"],
            workspace_path="workspace/run-1",
            input_snapshot_path="workspace/run-1/input/system_case.json",
        )
        store.mark_run_succeeded(
            run["id"],
            exit_code=0,
            stdout="",
            stderr="",
            success_payload={"status": "ok"},
            output_dir="workspace/run-1/output",
            summary_path="workspace/run-1/output/summary.json",
        )

        delete_response = self.client.delete(f"/api/scenario-versions/{version['id']}")

        self.assertEqual(delete_response.status_code, 409)
        self.assertIn("referenced by runs", delete_response.json()["detail"])
        self.assertEqual(self.client.get(f"/api/scenario-versions/{version['id']}").status_code, 200)

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

    def test_scenario_page_lists_previous_version_runs_and_loads_succeeded_results(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()
        sample_text = (REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json").read_text()
        previous_version = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": sample_text},
        ).json()
        current_version = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": sample_text},
        ).json()
        store = self.client.app.state.analyst_store
        previous_run = store.create_run(scenario_version_id=previous_version["id"])
        store.mark_run_succeeded(
            previous_run["id"],
            exit_code=0,
            stdout="",
            stderr="",
            success_payload={"status": "ok"},
            output_dir=None,
            summary_path=None,
        )
        current_run = store.create_run(scenario_version_id=current_version["id"])

        api_response = self.client.get(f"/api/scenarios/{scenario['id']}/runs")
        page = self.client.get(f"/scenarios/{scenario['id']}")

        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(
            [run["id"] for run in api_response.json()["runs"]],
            [current_run["id"], previous_run["id"]],
        )
        self.assertIn("Previous Runs", page.text)
        self.assertIn(f'href="/runs/{previous_run["id"]}#results">Load Results</a>', page.text)
        self.assertIn(f'href="/runs/{current_run["id"]}">Open Run</a>', page.text)
        self.assertIn("Status: succeeded", page.text)
        self.assertIn("Status: queued", page.text)

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
