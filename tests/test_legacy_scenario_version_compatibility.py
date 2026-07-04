import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.validation import ValidationResult


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CASE_PATH = REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json"


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok", "case_name": "stub_case", "schema_version": "bess_system_dispatch.v1"},
        )


class RecordingRunQueue:
    def __init__(self):
        self.enqueued_run_ids = []

    def enqueue(self, run_id):
        self.enqueued_run_ids.append(run_id)

    def stop(self):
        pass


class LegacyScenarioVersionCompatibilityTests(unittest.TestCase):
    """BESS-TS1-007: hierarchy provenance must not break scenario versions
    created before TS1-001, which have no generation_metadata_json content."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.artifact_root = Path(self.temp_dir.name) / "artifacts"
        self.artifact_root.mkdir()
        self.run_queue = RecordingRunQueue()
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                run_queue=self.run_queue,
                artifact_root=self.artifact_root,
            )
        )
        self.store = self.client.app.state.analyst_store

    def test_legacy_scenario_version_is_deletable_when_unreferenced(self):
        legacy_version = self._create_legacy_scenario_version()

        response = self.client.delete(f"/api/scenario-versions/{legacy_version['id']}")

        self.assertEqual(response.status_code, 200)
        body = response.json()["deleted_version"]
        self.assertEqual(body["deleted_run_count"], 0)
        self.assertEqual(body["deleted_publication_count"], 0)
        self.assertEqual(
            self.client.get(f"/api/scenario-versions/{legacy_version['id']}").status_code,
            404,
        )

    def test_legacy_scenario_version_supports_run_and_publication_pipeline_and_then_blocks_deletion(self):
        legacy_version = self._create_legacy_scenario_version()

        run_response = self.client.post(f"/api/scenario-versions/{legacy_version['id']}/runs")
        self.assertEqual(run_response.status_code, 201)
        run = run_response.json()
        self.assertEqual(run["scenario_version_id"], legacy_version["id"])
        self.assertEqual(self.run_queue.enqueued_run_ids, [run["id"]])

        run_workspace = self.artifact_root / "runs" / str(run["id"])
        self.store.mark_run_running(
            run["id"],
            workspace_path=str(run_workspace),
            input_snapshot_path=str(run_workspace / "input" / "system_case.json"),
        )
        output_dir = run_workspace / "outputs"
        output_dir.mkdir(parents=True)
        self.store.mark_run_succeeded(
            run["id"],
            exit_code=0,
            stdout=json.dumps({"status": "ok"}),
            stderr="",
            success_payload={"termination_status": "OPTIMAL"},
            output_dir=str(output_dir),
            summary_path=str(output_dir / "summary.json"),
        )
        for artifact_type in ["summary_json", "dispatch_csv"]:
            artifact_path = output_dir / artifact_type
            artifact_path.write_text("artifact contents", encoding="utf-8")
            self.store.register_run_artifact(
                run_id=run["id"],
                artifact_type=artifact_type,
                path=str(artifact_path),
                display_name=f"{artifact_type}.txt",
                media_type="text/plain",
                byte_size=artifact_path.stat().st_size,
            )

        artifacts_response = self.client.get(f"/api/runs/{run['id']}/artifacts")
        self.assertEqual(artifacts_response.status_code, 200)
        self.assertEqual(
            {artifact["artifact_type"] for artifact in artifacts_response.json()["artifacts"]},
            {"summary_json", "dispatch_csv"},
        )

        template = self.store.create_dashboard_template(
            project_id=legacy_version["project_id"],
            name="Client Summary",
        )
        publication_response = self.client.post(
            f"/api/runs/{run['id']}/publications",
            json={
                "dashboard_template_id": template["id"],
                "public_title": "Legacy Run Review",
            },
        )
        self.assertEqual(publication_response.status_code, 201)
        publication = publication_response.json()["publication"]
        self.assertEqual(publication["scenario_version_id"], legacy_version["id"])
        self.assertEqual(publication["run_id"], run["id"])

        delete_response = self.client.delete(f"/api/scenario-versions/{legacy_version['id']}")
        self.assertEqual(delete_response.status_code, 409)
        self.assertIn("runs", delete_response.json()["detail"])
        self.assertEqual(
            self.client.get(f"/api/scenario-versions/{legacy_version['id']}").status_code,
            200,
        )

    def _create_legacy_scenario_version(self):
        project = self.client.post("/api/projects", json={"name": "Legacy PMGD"}).json()
        scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Legacy case"},
        ).json()
        sample_text = SAMPLE_CASE_PATH.read_text()
        self.store.connection.execute(
            """
            INSERT INTO scenario_versions (
                scenario_id, version_number, system_case_json, case_name,
                schema_version, period_count, asset_counts_json,
                validation_payload_json, generation_metadata_json,
                created_at, created_by
            )
            VALUES (?, 1, ?, 'legacy_case', 'bess_system_dispatch.v1', 4, '{}', '{"status":"ok"}', '{}', ?, 'legacy_seed')
            """,
            (scenario["id"], sample_text, "2026-01-01T00:00:00+00:00"),
        )
        self.store.connection.commit()
        [legacy_summary] = self.client.get(f"/api/scenarios/{scenario['id']}/versions").json()["versions"]
        self.assertEqual(legacy_summary["generation_metadata"], {})
        legacy_summary["scenario_id"] = scenario["id"]
        legacy_summary["project_id"] = project["id"]
        return legacy_summary


if __name__ == "__main__":
    unittest.main()
