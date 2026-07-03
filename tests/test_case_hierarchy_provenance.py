import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.validation import ValidationResult


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CASE_PATH = REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json"


class StubValidationService:
    def __init__(self):
        self.candidates = []

    def validate_text(self, candidate_text):
        self.candidates.append(candidate_text)
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok", "case_name": "stub_case", "schema_version": "bess_system_dispatch.v1"},
        )


class CaseHierarchyProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.validation_service = StubValidationService()
        self.client = TestClient(
            create_app(
                validation_service=self.validation_service,
                database_url="sqlite:///:memory:",
            )
        )

    def create_scenario(self):
        project = self.client.post("/api/projects", json={"name": "Hybrid PMGD"}).json()
        return self.client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Base case"},
        ).json()

    def test_new_scenario_version_records_topology_and_parameter_provenance(self):
        scenario = self.create_scenario()
        sample_text = SAMPLE_CASE_PATH.read_text()

        created = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": sample_text},
        ).json()

        provenance = created["generation_metadata"]
        topology_hash = provenance["topology"]["content_hash"]
        parameters_hash = provenance["parameters"]["content_hash"]
        self.assertTrue(topology_hash.startswith("sha256:"))
        self.assertTrue(parameters_hash.startswith("sha256:"))
        self.assertNotEqual(topology_hash, parameters_hash)

        detail = self.client.get(f"/api/scenario-versions/{created['id']}").json()["scenario_version"]
        self.assertEqual(detail["generation_metadata"]["topology"]["content_hash"], topology_hash)
        self.assertEqual(detail["generation_metadata"]["parameters"]["content_hash"], parameters_hash)

    def test_topology_hash_ignores_parameter_edits_but_changes_on_structural_edits(self):
        scenario = self.create_scenario()
        base_case = json.loads(SAMPLE_CASE_PATH.read_text())

        baseline = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": json.dumps(base_case)},
        ).json()["generation_metadata"]

        parameter_edited_case = json.loads(json.dumps(base_case))
        for node in parameter_edited_case["nodes"]:
            if node["id"] == "battery_1":
                node["charge_power_max_mw"] = 999.0
        parameter_edited = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": json.dumps(parameter_edited_case)},
        ).json()["generation_metadata"]

        self.assertEqual(
            parameter_edited["topology"]["content_hash"], baseline["topology"]["content_hash"]
        )
        self.assertNotEqual(
            parameter_edited["parameters"]["content_hash"], baseline["parameters"]["content_hash"]
        )

        structurally_edited_case = json.loads(json.dumps(base_case))
        structurally_edited_case["nodes"].append({"id": "load_2", "type": "load"})
        structurally_edited_case["edges"].append({"from": "load_2", "to": "bus_1"})
        structurally_edited = self.client.post(
            f"/api/scenarios/{scenario['id']}/versions",
            json={"system_case_json": json.dumps(structurally_edited_case)},
        ).json()["generation_metadata"]

        self.assertNotEqual(
            structurally_edited["topology"]["content_hash"], baseline["topology"]["content_hash"]
        )

    def test_legacy_scenario_version_without_provenance_still_loads(self):
        scenario = self.create_scenario()
        sample_text = SAMPLE_CASE_PATH.read_text()
        store = self.client.app.state.analyst_store

        created_at = "2026-01-01T00:00:00+00:00"
        store.connection.execute(
            """
            INSERT INTO scenario_versions (
                scenario_id, version_number, system_case_json, case_name,
                schema_version, period_count, asset_counts_json,
                validation_payload_json, generation_metadata_json,
                created_at, created_by
            )
            VALUES (?, 1, ?, 'legacy_case', 'bess_system_dispatch.v1', 4, '{}', '{}', '{}', ?, 'legacy_seed')
            """,
            (scenario["id"], sample_text, created_at),
        )
        store.connection.commit()

        list_response = self.client.get(f"/api/scenarios/{scenario['id']}/versions")
        self.assertEqual(list_response.status_code, 200)
        [legacy_summary] = list_response.json()["versions"]
        self.assertEqual(legacy_summary["generation_metadata"], {})

        detail_response = self.client.get(f"/api/scenario-versions/{legacy_summary['id']}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["scenario_version"]["generation_metadata"], {})
