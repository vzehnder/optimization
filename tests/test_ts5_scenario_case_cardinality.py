import sqlite3
import unittest

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore


class StubValidationService:
    def validate_text(self, candidate_text):
        raise AssertionError("validation not expected in these tests")

    def validate_file(self, candidate_path):
        raise AssertionError("validation not expected in these tests")


class ScenarioCaseCardinalityStoreTests(unittest.TestCase):
    """BESS-TS5-006: Scenario -> OptimizationCase stays one-to-one, confirmed
    (not migrated) per docs/series_tiempo/iter5/decision_record_ts5_migration_semantics.md
    decision 4. These tests lock the store-level and schema-level guarantees
    behind that decision.
    """

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.project = self.store.create_project(name="TS-5 cardinality project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS-5 cardinality scenario"
        )

    def test_get_or_create_case_for_scenario_is_idempotent_and_returns_same_case(self):
        first = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        second = self.store.get_or_create_case_for_scenario(self.scenario["id"])

        self.assertEqual(first["id"], second["id"])
        row_count = self.store.connection.execute(
            "SELECT COUNT(*) AS count FROM optimization_cases WHERE scenario_id = ?",
            (self.scenario["id"],),
        ).fetchone()["count"]
        self.assertEqual(row_count, 1)

    def test_second_case_row_for_same_scenario_is_rejected_by_the_schema(self):
        self.store.get_or_create_case_for_scenario(self.scenario["id"])

        with self.assertRaises(sqlite3.IntegrityError):
            self.store.connection.execute(
                """
                INSERT INTO optimization_cases (
                    scenario_id, case_key, display_name, validation_payload_json,
                    created_at, updated_at, created_by, updated_by
                )
                VALUES (?, 'second_case', 'Second case', '{}', '2026-07-09T00:00:00Z',
                        '2026-07-09T00:00:00Z', 'internal_analyst', 'internal_analyst')
                """,
                (self.scenario["id"],),
            )


class ScenarioCaseCardinalityApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                store=self.store,
            )
        )
        self.project = self.client.post(
            "/api/projects", json={"name": "TS-5 cardinality project"}
        ).json()
        self.scenario = self.client.post(
            f"/api/projects/{self.project['id']}/scenarios",
            json={"name": "TS-5 cardinality scenario"},
        ).json()

    def test_default_variant_and_variants_endpoints_agree_on_the_same_case(self):
        default_response = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        )
        variants_response = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/variants"
        )

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(variants_response.status_code, 200)
        default_case = default_response.json()["case"]
        variants_case = variants_response.json()["case"]
        self.assertEqual(default_case["scenario_id"], self.scenario["id"])
        self.assertEqual(default_case["id"], variants_case["id"])


if __name__ == "__main__":
    unittest.main()
