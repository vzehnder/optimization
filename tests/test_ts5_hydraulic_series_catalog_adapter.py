import unittest

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore


class StubValidationService:
    def validate_text(self, candidate_text):
        raise AssertionError("validation not expected in these tests")

    def validate_file(self, candidate_path):
        raise AssertionError("validation not expected in these tests")


class HydraulicTimeSeriesCatalogAdapterTests(unittest.TestCase):
    """Coexistence tests for the TS5-002 legacy read adapter.

    Since TS5-003, the hydro diagram flow no longer writes new
    ``hydraulic_time_series_sets`` rows -- new series land in the generic
    catalog instead (see ``tests/test_ts5_hydraulic_series_generic_write.py``).
    A genuinely legacy-backed set can therefore only exist as pre-existing
    data (from before that migration, or from a bulk/manual repair), so these
    tests seed one directly at the storage layer and prove the adapter still
    reads it correctly side by side with a newly, generically written series.
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

    def _inflow_series(self, *values, version_label="v1"):
        return {
            "version_label": version_label,
            "points": [
                {
                    "timestamp": f"2026-01-01T{index:02d}:00:00",
                    "duration_hours": 1.0,
                    "value_m3s": float(value),
                }
                for index, value in enumerate(values)
            ],
        }

    def _create_diagram(self):
        return self.client.post(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]

    def _save_reservoir(self, revision, *, inflow=None):
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
        if inflow is not None:
            node["natural_inflow_series"] = inflow
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
        create_binding=True,
    ):
        """Insert a legacy hydraulic_time_series_sets row directly.

        Simulates data written before TS5-003, which the public API can no
        longer produce -- new writes always go to the generic catalog now.
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
            ) VALUES (?, ?, ?, ?, 1, ?, 'legacy-seed-hash', 'draft', ?, ?, 'seed', 'seed')
            """,
            (
                self.project["id"],
                entity_type,
                base_entity_id,
                signal_key,
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

    def test_legacy_hydraulic_set_listed_in_project_catalog_with_origin_label(self):
        created = self._create_diagram()
        save_response = self._save_reservoir(created["revision"])
        node = save_response.json()["diagram"]["nodes"][0]
        self._seed_legacy_inflow_set(
            case_id=save_response.json()["diagram"]["optimization_case"]["id"],
            case_node_id=node["entity_id"],
            values=[5.0, 6.0],
        )

        response = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic"
        )
        self.assertEqual(response.status_code, 200)
        sets = response.json()["hydraulic_time_series_sets"]
        self.assertEqual(len(sets), 1)
        entry = sets[0]
        self.assertEqual(entry["signal_key"], "natural_inflow_m3s")
        self.assertEqual(entry["entity_type"], "hydraulic_node")
        self.assertEqual(entry["origin"]["kind"], "hydraulic_legacy")
        self.assertEqual(entry["period_count"], 2)

    def test_detail_endpoint_matches_legacy_hydro_diagram_read_path(self):
        created = self._create_diagram()
        save_response = self._save_reservoir(created["revision"])
        node = save_response.json()["diagram"]["nodes"][0]
        self._seed_legacy_inflow_set(
            case_id=save_response.json()["diagram"]["optimization_case"]["id"],
            case_node_id=node["entity_id"],
            values=[5.0, 6.0],
        )
        reloaded_node = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]["nodes"][0]
        legacy_series = reloaded_node["natural_inflow_series"]
        self.assertEqual(legacy_series["origin"], {"kind": "hydraulic_legacy"})
        hydraulic_set_id = legacy_series["time_series_set_id"]

        response = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/{hydraulic_set_id}"
        )
        self.assertEqual(response.status_code, 200)
        detail = response.json()["hydraulic_time_series_set"]

        self.assertEqual(detail["version_number"], legacy_series["version_number"])
        self.assertEqual(detail["version_label"], legacy_series["version_label"])
        adapter_values = [
            {
                "timestamp": period["timestamp_start"],
                "duration_hours": period["duration_hours"],
                "value_m3s": value["value_numeric"],
            }
            for period, value in zip(detail["periods"], detail["values"])
        ]
        self.assertEqual(adapter_values, legacy_series["points"])

    def test_hydro_diagram_editor_read_path_keeps_working_unchanged(self):
        created = self._create_diagram()
        save_response = self._save_reservoir(created["revision"])
        node = save_response.json()["diagram"]["nodes"][0]
        self._seed_legacy_inflow_set(
            case_id=save_response.json()["diagram"]["optimization_case"]["id"],
            case_node_id=node["entity_id"],
            values=[5.0, 6.0],
        )

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        reloaded_node = reloaded["nodes"][0]
        self.assertEqual(
            [point["value_m3s"] for point in reloaded_node["natural_inflow_series"]["points"]],
            [5.0, 6.0],
        )
        self.assertEqual(len(reloaded_node["available_inflow_series"]), 1)

    def test_hydraulic_set_from_other_project_is_not_exposed(self):
        created = self._create_diagram()
        save_response = self._save_reservoir(created["revision"])
        node = save_response.json()["diagram"]["nodes"][0]
        hydraulic_set_id = self._seed_legacy_inflow_set(
            case_id=save_response.json()["diagram"]["optimization_case"]["id"],
            case_node_id=node["entity_id"],
            values=[5.0, 6.0],
        )

        other_project = self.client.post(
            "/api/projects", json={"name": "Other Project"}
        ).json()

        list_response = self.client.get(
            f"/api/projects/{other_project['id']}/time-series-sets/hydraulic"
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["hydraulic_time_series_sets"], [])

        detail_response = self.client.get(
            f"/api/projects/{other_project['id']}/time-series-sets/hydraulic/{hydraulic_set_id}"
        )
        self.assertEqual(detail_response.status_code, 404)

    def test_reach_minimum_flow_series_listed_and_browsable_via_adapter(self):
        created = self._create_diagram()
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
        reach = save_response.json()["diagram"]["reaches"][0]
        self._seed_legacy_inflow_set(
            case_id=save_response.json()["diagram"]["optimization_case"]["id"],
            case_node_id=reach["entity_id"],
            values=[2.0, 4.0],
            signal_key="minimum_flow_m3s",
            entity_type="hydraulic_reach",
            binding_entity_type="case_hydraulic_reach",
        )

        list_response = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic"
        )
        entries = list_response.json()["hydraulic_time_series_sets"]
        entry = next(item for item in entries if item["entity_type"] == "hydraulic_reach")
        self.assertEqual(entry["signal_key"], "minimum_flow_m3s")
        self.assertEqual(entry["entity_display_name"], "Alpha to Junction")

        detail_response = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/{entry['id']}"
        )
        detail = detail_response.json()["hydraulic_time_series_set"]
        self.assertEqual(
            [value["value_numeric"] for value in detail["values"]], [2.0, 4.0]
        )

    def test_legacy_and_generic_series_coexist_side_by_side_in_same_diagram(self):
        created = self._create_diagram()
        save_response = self._save_reservoir(
            created["revision"], inflow=self._inflow_series(5.0, 6.0)
        )
        self.assertEqual(save_response.status_code, 200)
        node = save_response.json()["diagram"]["nodes"][0]
        generic_series = node["natural_inflow_series"]
        self.assertEqual(generic_series["origin"], {"kind": "generic"})

        self._seed_legacy_inflow_set(
            case_id=save_response.json()["diagram"]["optimization_case"]["id"],
            case_node_id=node["entity_id"],
            values=[1.0, 2.0],
            version_label="legacy-v1",
            create_binding=False,
        )

        reloaded_node = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]["nodes"][0]
        # The case is still bound to the generic set that was actually saved;
        # the seeded legacy set is merely available side by side.
        self.assertEqual(
            reloaded_node["natural_inflow_series"]["origin"], {"kind": "generic"}
        )
        origins = {item["origin"]["kind"] for item in reloaded_node["available_inflow_series"]}
        self.assertEqual(origins, {"generic", "hydraulic_legacy"})

        legacy_list = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic"
        ).json()["hydraulic_time_series_sets"]
        self.assertEqual(len(legacy_list), 1)

        generic_list = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        ).json()["time_series_sets"]
        self.assertEqual(len(generic_list), 1)


if __name__ == "__main__":
    unittest.main()
