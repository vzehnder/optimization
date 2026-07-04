import copy
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_hydraulic_diagram_hierarchy_provenance import (
    promote_hydraulic_diagram,
    save_diagram,
)
from tests.test_hydro_diagram_acceptance import HydroAcceptanceValidationService


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CASE_PATH = REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json"


class RecordingRunQueue:
    def __init__(self):
        self.enqueued_run_ids = []

    def enqueue(self, run_id):
        self.enqueued_run_ids.append(run_id)

    def stop(self):
        pass


class TS1AcceptanceTests(unittest.TestCase):
    """BESS-TS1-008: closing proof for the TS-1 topology/parameter hierarchy.

    Exercises one continuous story: a hydraulic diagram promotion records
    distinct topology/parameter provenance, a topology-only edit and a
    parameter-only edit each independently stale and block promotion, revalidated
    promotions keep the untouched hash stable, and a version created before
    TS1-001 (no generation_metadata) still lists, loads and runs.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.artifact_root = Path(self.temp_dir.name) / "artifacts"
        self.artifact_root.mkdir()
        self.run_queue = RecordingRunQueue()
        self.client = TestClient(
            create_app(
                validation_service=HydroAcceptanceValidationService(),
                database_url="sqlite:///:memory:",
                run_queue=self.run_queue,
                artifact_root=self.artifact_root,
            )
        )
        self.store = self.client.app.state.analyst_store
        project = self.client.post("/api/projects", json={"name": "TS1 Acceptance"}).json()
        self.scenario = self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Hydraulic case"},
        ).json()

    def test_hierarchy_provenance_stale_validation_and_legacy_compatibility(self):
        scenario_id = self.scenario["id"]
        created = self.client.post(f"/api/scenarios/{scenario_id}/hydraulic-diagram").json()["diagram"]
        save_diagram(self.client, scenario_id, created["revision"])

        version_1 = promote_hydraulic_diagram(self.client, scenario_id)
        provenance_1 = version_1["generation_metadata"]
        self.assertEqual(provenance_1["kind"], "hydraulic_diagram_v3")
        topology_hash_1 = provenance_1["topology"]["content_hash"]
        parameters_hash_1 = provenance_1["parameters"]["content_hash"]
        self.assertTrue(topology_hash_1.startswith("sha256:"))
        self.assertTrue(parameters_hash_1.startswith("sha256:"))
        self.assertNotEqual(topology_hash_1, parameters_hash_1)

        run_id_1 = self._launch_run(version_1["id"])
        self._complete_run(run_id_1)
        self.assertEqual(self.client.get(f"/api/runs/{run_id_1}").json()["run"]["status"], "succeeded")

        # Topology-only edit: unit intake rewired, no add/remove.
        reloaded = self.client.get(f"/api/scenarios/{scenario_id}/hydraulic-diagram").json()["diagram"]
        topology_edited_nodes = copy.deepcopy(reloaded["nodes"])
        for node in topology_edited_nodes:
            if node["technical_key"] == "plant_laja":
                node["units"][0]["intake_node_key"] = "reservoir_alpha"
        topology_stale_diagram = save_diagram(
            self.client, scenario_id, reloaded["revision"],
            nodes=topology_edited_nodes, reaches=reloaded["reaches"],
        )
        validation = topology_stale_diagram["validation"]
        self.assertTrue(validation["stale"])
        self.assertTrue(validation["topology_stale"])
        self.assertFalse(validation["parameters_stale"])

        blocked = self.client.post(f"/api/scenarios/{scenario_id}/hydraulic-diagram/promote")
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("topology", blocked.json()["detail"])

        version_2 = promote_hydraulic_diagram(self.client, scenario_id)
        provenance_2 = version_2["generation_metadata"]
        topology_hash_2 = provenance_2["topology"]["content_hash"]
        self.assertNotEqual(topology_hash_2, topology_hash_1)
        self.assertEqual(provenance_2["parameters"]["content_hash"], parameters_hash_1)

        # Parameter-only edit: reservoir max storage changed.
        reloaded_2 = self.client.get(f"/api/scenarios/{scenario_id}/hydraulic-diagram").json()["diagram"]
        parameter_edited_nodes = copy.deepcopy(reloaded_2["nodes"])
        for node in parameter_edited_nodes:
            if node["technical_key"] == "reservoir_alpha":
                node["reservoir"]["storage_max_hm3"] = 42.0
        parameters_stale_diagram = save_diagram(
            self.client, scenario_id, reloaded_2["revision"],
            nodes=parameter_edited_nodes, reaches=reloaded_2["reaches"],
        )
        validation_2 = parameters_stale_diagram["validation"]
        self.assertTrue(validation_2["stale"])
        self.assertFalse(validation_2["topology_stale"])
        self.assertTrue(validation_2["parameters_stale"])

        blocked_2 = self.client.post(f"/api/scenarios/{scenario_id}/hydraulic-diagram/promote")
        self.assertEqual(blocked_2.status_code, 400)
        self.assertIn("parameters", blocked_2.json()["detail"])
        self.assertNotIn("topology", blocked_2.json()["detail"])

        version_3 = promote_hydraulic_diagram(self.client, scenario_id)
        provenance_3 = version_3["generation_metadata"]
        self.assertEqual(provenance_3["topology"]["content_hash"], topology_hash_2)
        self.assertNotEqual(provenance_3["parameters"]["content_hash"], parameters_hash_1)

        # A legacy version (pre-TS1-001, no generation_metadata) must still
        # list, load and run identically to hierarchy-generated versions.
        legacy_version_id = self._insert_legacy_scenario_version(scenario_id)
        versions = self.client.get(f"/api/scenarios/{scenario_id}/versions").json()["versions"]
        legacy_summary = next(v for v in versions if v["id"] == legacy_version_id)
        self.assertEqual(legacy_summary["generation_metadata"], {})

        detail = self.client.get(f"/api/scenario-versions/{legacy_version_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["scenario_version"]["generation_metadata"], {})

        legacy_run_id = self._launch_run(legacy_version_id)
        self._complete_run(legacy_run_id)
        self.assertEqual(self.client.get(f"/api/runs/{legacy_run_id}").json()["run"]["status"], "succeeded")

    def _launch_run(self, scenario_version_id):
        response = self.client.post(f"/api/scenario-versions/{scenario_version_id}/runs")
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def _complete_run(self, run_id):
        run_workspace = self.artifact_root / "runs" / str(run_id)
        self.store.mark_run_running(
            run_id,
            workspace_path=str(run_workspace),
            input_snapshot_path=str(run_workspace / "input" / "system_case.json"),
        )
        output_dir = run_workspace / "outputs"
        output_dir.mkdir(parents=True)
        self.store.mark_run_succeeded(
            run_id,
            exit_code=0,
            stdout=json.dumps({"status": "ok"}),
            stderr="",
            success_payload={"termination_status": "OPTIMAL"},
            output_dir=str(output_dir),
            summary_path=str(output_dir / "summary.json"),
        )

    def _insert_legacy_scenario_version(self, scenario_id):
        sample_text = SAMPLE_CASE_PATH.read_text(encoding="utf-8")
        self.store.connection.execute(
            """
            INSERT INTO scenario_versions (
                scenario_id, version_number, system_case_json, case_name,
                schema_version, period_count, asset_counts_json,
                validation_payload_json, generation_metadata_json,
                created_at, created_by
            )
            VALUES (?, 99, ?, 'legacy_case', 'bess_system_dispatch.v1', 4, '{}', '{"status":"ok"}', '{}', ?, 'legacy_seed')
            """,
            (scenario_id, sample_text, "2026-01-01T00:00:00+00:00"),
        )
        self.store.connection.commit()
        [legacy_summary] = [
            version
            for version in self.client.get(f"/api/scenarios/{scenario_id}/versions").json()["versions"]
            if version["version_number"] == 99
        ]
        return legacy_summary["id"]

    def test_ts1_documentation_tracker_and_issue_are_done(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        issue = (
            REPO_ROOT
            / "docs"
            / "series_tiempo"
            / "iter1"
            / "issues"
            / "BESS-TS1-008-finalize-ts1-acceptance-suite-and-docs.md"
        ).read_text(encoding="utf-8")
        tracker = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter1" / "issues" / "tracker_ts1.md"
        ).read_text(encoding="utf-8")
        manual = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter1" / "pruebas_manuales_ts1.md"
        ).read_text(encoding="utf-8")

        self.assertIn("TS-1: Topology And Parameter Hierarchy", readme)
        self.assertIn("tests.test_ts1_acceptance", readme)

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_ts1_acceptance", issue)

        self.assertIn(
            "| BESS-TS1-008 | Finalize TS-1 Acceptance Suite And Docs | AFK | ready-for-agent | Done |",
            tracker,
        )
        self.assertIn("BESS-TS1-008 | Todo -> Done", tracker)
        self.assertIn("Final TS-1 Verification", tracker)
        self.assertIn("tests.test_ts1_acceptance", tracker)

        self.assertIn("Cierre TS-1", manual)
        self.assertIn("tests.test_ts1_acceptance", manual)


if __name__ == "__main__":
    unittest.main()
