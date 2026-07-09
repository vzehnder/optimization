import unittest

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf


class StubValidationService:
    def validate_text(self, candidate_text):
        raise AssertionError("validation not expected in these tests")

    def validate_file(self, candidate_path):
        raise AssertionError("validation not expected in these tests")


class HydraulicTimeSeriesMigrationTests(unittest.TestCase):
    """BESS-TS5-004: on-demand migration of legacy hydraulic sets.

    Since TS5-003 the public API can no longer produce legacy
    ``hydraulic_time_series_sets`` rows, so these tests seed one directly at
    the storage layer (matching the TS5-002 adapter test convention) and
    migrate it through the new endpoint.
    """

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
            "/api/projects", json={"name": "Hydro Project"}
        ).json()
        self.scenario = self.client.post(
            f"/api/projects/{self.project['id']}/scenarios",
            json={"name": "Hydraulic base case"},
        ).json()

    def _create_diagram(self):
        return self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]

    def _save_reservoir(self, revision):
        node = {
            "component_type": "reservoir",
            "technical_key": "reservoir_alpha",
            "display_name": "Reservoir Alpha",
            "x": 120.0,
            "y": 80.0,
            "reservoir": {
                "storage_min_hm3": 5.0,
                "storage_max_hm3": 50.0,
                "initial_storage_hm3": 20.0,
                "terminal_condition": "none",
                "terminal_water_value_usd_per_hm3": 0.0,
            },
            "storage_elevation_curve": {
                "version_label": "v1",
                "points": [
                    {"x_value": 5.0, "y_value": 700.0},
                    {"x_value": 50.0, "y_value": 760.0},
                ],
            },
        }
        return self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={"revision": revision, "nodes": [node]},
        )

    def _seed_legacy_inflow_set(
        self,
        *,
        case_id,
        case_node_id,
        values,
        signal_key="natural_inflow_m3s",
        entity_type="hydraulic_node",
        binding_entity_type="case_hydraulic_node",
        version_label="v1",
        version_number=1,
        create_binding=True,
    ):
        """Insert a legacy hydraulic_time_series_sets row directly.

        Simulates data written before TS5-003, which the public API can no
        longer produce.
        """
        case_table, base_id_column = {
            "hydraulic_node": ("case_hydraulic_nodes", "hydraulic_node_id"),
            "hydraulic_reach": ("case_hydraulic_reaches", "hydraulic_reach_id"),
        }[entity_type]
        base_row = self.store.connection.execute(
            f"SELECT {base_id_column} FROM {case_table} WHERE id = ?",
            (case_node_id,),
        ).fetchone()
        base_entity_id = int(base_row[0])
        now = "2026-01-01T00:00:00+00:00"
        cursor = self.store.connection.execute(
            """
            INSERT INTO hydraulic_time_series_sets (
                project_id, entity_type, entity_id, signal_key, version_number,
                version_label, content_hash, status, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, 'legacy-seed-hash', 'draft', ?, ?, 'seed', 'seed')
            """,
            (
                self.project["id"],
                entity_type,
                base_entity_id,
                signal_key,
                version_number,
                version_label,
                now,
                now,
            ),
        )
        set_id = int(cursor.lastrowid)
        for index, value in enumerate(values):
            self.store.connection.execute(
                """
                INSERT INTO hydraulic_time_series_points (
                    hydraulic_time_series_set_id, point_index, timestamp,
                    duration_hours, value
                ) VALUES (?, ?, ?, 1.0, ?)
                """,
                (set_id, index, f"2026-01-01T{index:02d}:00:00", float(value)),
            )
        if create_binding:
            self.store.connection.execute(
                """
                INSERT INTO case_hydraulic_time_series_bindings (
                    case_id, entity_type, entity_id, signal_key,
                    hydraulic_time_series_set_id, time_series_set_id, required,
                    created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, ?, ?, ?, NULL, 1, ?, ?, 'seed', 'seed')
                """,
                (case_id, binding_entity_type, case_node_id, signal_key, set_id, now, now),
            )
        self.store.connection.commit()
        return set_id

    def test_migrate_single_legacy_set_creates_generic_set_with_origin_metadata(self):
        created = self._create_diagram()
        save_response = self._save_reservoir(created["revision"])
        node = save_response.json()["diagram"]["nodes"][0]
        legacy_id = self._seed_legacy_inflow_set(
            case_id=save_response.json()["diagram"]["optimization_case"]["id"],
            case_node_id=node["entity_id"],
            values=[5.0, 6.0],
        )

        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/{legacy_id}/migrate"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["already_migrated"])
        migrated_set = body["time_series_set"]
        self.assertEqual(migrated_set["period_count"], 2)

        origin = migrated_set["revision_metadata"]["origin"]
        self.assertEqual(origin["kind"], "hydraulic_legacy_migration")
        self.assertEqual(origin["hydraulic_time_series_set_id"], legacy_id)
        self.assertEqual(origin["signal_key"], "natural_inflow_m3s")

        generic_list = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        ).json()["time_series_sets"]
        self.assertEqual(len(generic_list), 1)

    def test_migration_leaves_bound_legacy_reads_untouched(self):
        created = self._create_diagram()
        save_response = self._save_reservoir(created["revision"])
        node = save_response.json()["diagram"]["nodes"][0]
        legacy_id = self._seed_legacy_inflow_set(
            case_id=save_response.json()["diagram"]["optimization_case"]["id"],
            case_node_id=node["entity_id"],
            values=[5.0, 6.0],
        )

        before_migration = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]["nodes"][0]["natural_inflow_series"]
        self.assertEqual(before_migration["origin"], {"kind": "hydraulic_legacy"})
        self.assertEqual(
            [point["value_m3s"] for point in before_migration["points"]], [5.0, 6.0]
        )

        self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/{legacy_id}/migrate"
        )

        # The legacy set itself, and the case binding pointing at it, are
        # untouched by migration: historical runs/scenario versions that
        # already resolved this legacy id keep reading the exact same data.
        after_migration = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]["nodes"][0]["natural_inflow_series"]
        self.assertEqual(after_migration["origin"], {"kind": "hydraulic_legacy"})
        self.assertEqual(after_migration["time_series_set_id"], legacy_id)
        self.assertEqual(
            [point["value_m3s"] for point in after_migration["points"]], [5.0, 6.0]
        )

        legacy_detail = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/{legacy_id}"
        )
        self.assertEqual(legacy_detail.status_code, 200)
        self.assertEqual(
            [value["value_numeric"] for value in legacy_detail.json()["hydraulic_time_series_set"]["values"]],
            [5.0, 6.0],
        )

    def test_re_migrating_same_legacy_set_is_idempotent_no_duplicate(self):
        created = self._create_diagram()
        save_response = self._save_reservoir(created["revision"])
        node = save_response.json()["diagram"]["nodes"][0]
        legacy_id = self._seed_legacy_inflow_set(
            case_id=save_response.json()["diagram"]["optimization_case"]["id"],
            case_node_id=node["entity_id"],
            values=[5.0, 6.0],
        )

        url = f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/{legacy_id}/migrate"
        first = self.client.post(url)
        second = self.client.post(url)

        self.assertFalse(first.json()["already_migrated"])
        self.assertTrue(second.json()["already_migrated"])
        self.assertEqual(
            first.json()["time_series_set"]["id"], second.json()["time_series_set"]["id"]
        )

        generic_list = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        ).json()["time_series_sets"]
        self.assertEqual(len(generic_list), 1)

    def test_bulk_sweep_migrates_all_legacy_sets_and_is_stable_on_repeat(self):
        created = self._create_diagram()
        save_response = self._save_reservoir(created["revision"])
        node = save_response.json()["diagram"]["nodes"][0]
        case_id = save_response.json()["diagram"]["optimization_case"]["id"]
        legacy_id_1 = self._seed_legacy_inflow_set(
            case_id=case_id, case_node_id=node["entity_id"], values=[5.0, 6.0]
        )
        legacy_id_2 = self._seed_legacy_inflow_set(
            case_id=case_id,
            case_node_id=node["entity_id"],
            values=[1.0, 2.0],
            version_label="v2",
            version_number=2,
            create_binding=False,
        )
        empty_legacy_id = self._seed_legacy_inflow_set(
            case_id=case_id,
            case_node_id=node["entity_id"],
            values=[],
            version_label="v3-empty",
            version_number=3,
            create_binding=False,
        )

        url = f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/migrate-all"
        first_report = self.client.post(url).json()
        self.assertEqual(sorted(first_report["migrated"]), sorted([legacy_id_1, legacy_id_2]))
        self.assertEqual(first_report["skipped"], [])
        self.assertEqual(len(first_report["failed"]), 1)
        self.assertEqual(first_report["failed"][0]["hydraulic_time_series_set_id"], empty_legacy_id)

        second_report = self.client.post(url).json()
        self.assertEqual(second_report["migrated"], [])
        self.assertEqual(sorted(second_report["skipped"]), sorted([legacy_id_1, legacy_id_2]))
        self.assertEqual(len(second_report["failed"]), 1)

        generic_list = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        ).json()["time_series_sets"]
        self.assertEqual(len(generic_list), 2)


class HydraulicTimeSeriesBulkMigrationAuthTests(unittest.TestCase):
    """BESS-TS5-004: bulk migration sweep is an admin-only action."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
            created_by="test",
        )
        self.store.create_user(
            email="admin@example.local",
            display_name="Admin",
            role="admin",
            password_hash=hash_password("admin pass"),
            created_by="test",
        )
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.login(self.client, "admin@example.local", "admin pass")
        self.project = post_json_with_csrf(
            self.client, "/api/projects", {"name": "Hydro Project"}
        ).json()

    def login(self, client, email, password):
        response = login_json_with_csrf(client, email, password)
        self.assertEqual(response.status_code, 200)

    def test_analyst_cannot_run_bulk_migration_sweep(self):
        analyst_client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.login(analyst_client, "analyst@example.local", "analyst pass")

        response = post_json_with_csrf(
            analyst_client,
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/migrate-all",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_run_bulk_migration_sweep(self):
        response = post_json_with_csrf(
            self.client,
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/migrate-all",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"migrated": [], "skipped": [], "failed": []})


if __name__ == "__main__":
    unittest.main()
