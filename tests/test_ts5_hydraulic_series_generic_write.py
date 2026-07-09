import unittest

from fastapi.testclient import TestClient

from app.main import create_app


class StubValidationService:
    def validate_text(self, candidate_text):
        raise AssertionError("validation not expected in these tests")

    def validate_file(self, candidate_path):
        raise AssertionError("validation not expected in these tests")


class HydraulicSeriesGenericWriteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
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

    def _save_reservoir_with_inflow(self, revision, series):
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
            "natural_inflow_series": series,
        }
        return self.client.put(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram",
            json={"revision": revision, "nodes": [node]},
        )

    def test_new_natural_inflow_series_is_stored_in_generic_catalog_not_legacy_table(self):
        created = self._create_diagram()
        save_response = self._save_reservoir_with_inflow(
            created["revision"], self._inflow_series(5.0, 6.0)
        )
        self.assertEqual(save_response.status_code, 200)
        series = save_response.json()["diagram"]["nodes"][0]["natural_inflow_series"]
        self.assertEqual(series["origin"], {"kind": "generic"})

        legacy = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic"
        ).json()["hydraulic_time_series_sets"]
        self.assertEqual(legacy, [])

        generic = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        ).json()["time_series_sets"]
        self.assertEqual(len(generic), 1)
        self.assertEqual(generic[0]["period_count"], 2)

    def test_new_minimum_flow_series_on_reach_is_stored_in_generic_catalog(self):
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
                        "minimum_flow_series": self._inflow_series(2.0, 4.0),
                    }
                ],
            },
        )
        self.assertEqual(save_response.status_code, 200)
        reach = save_response.json()["diagram"]["reaches"][0]
        self.assertEqual(reach["minimum_flow_series"]["origin"], {"kind": "generic"})

        legacy = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic"
        ).json()["hydraulic_time_series_sets"]
        self.assertEqual(legacy, [])

        generic = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        ).json()["time_series_sets"]
        minimum_flow_set = next(
            item for item in generic if item["name"].endswith("minimum_flow_m3s")
        )
        self.assertEqual(minimum_flow_set["period_count"], 2)

    def test_resaving_identical_new_points_reuses_generic_set_without_new_version(self):
        created = self._create_diagram()
        first = self._save_reservoir_with_inflow(
            created["revision"], self._inflow_series(5.0, 6.0)
        )
        first_series = first.json()["diagram"]["nodes"][0]["natural_inflow_series"]
        self.assertEqual(first_series["version_number"], 1)

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        second = self._save_reservoir_with_inflow(
            reloaded["revision"], self._inflow_series(5.0, 6.0)
        )
        second_series = second.json()["diagram"]["nodes"][0]["natural_inflow_series"]
        self.assertEqual(
            second_series["time_series_set_id"], first_series["time_series_set_id"]
        )
        self.assertEqual(second_series["version_number"], 1)

        generic = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        ).json()["time_series_sets"]
        self.assertEqual(len(generic), 1)

    def test_selecting_existing_generic_version_by_id_reuses_it_without_new_version(self):
        created = self._create_diagram()
        first = self._save_reservoir_with_inflow(
            created["revision"], self._inflow_series(5.0, 6.0)
        )
        first_series = first.json()["diagram"]["nodes"][0]["natural_inflow_series"]

        edited = self._save_reservoir_with_inflow(
            first.json()["diagram"]["revision"],
            self._inflow_series(9.0, 9.0, version_label="v2"),
        )
        edited_series = edited.json()["diagram"]["nodes"][0]["natural_inflow_series"]
        self.assertEqual(edited_series["version_number"], 2)
        self.assertNotEqual(
            edited_series["time_series_set_id"], first_series["time_series_set_id"]
        )

        reverted = self._save_reservoir_with_inflow(
            edited.json()["diagram"]["revision"],
            {
                "time_series_set_id": first_series["time_series_set_id"],
                "origin": {"kind": "generic"},
            },
        )
        reverted_series = reverted.json()["diagram"]["nodes"][0]["natural_inflow_series"]
        self.assertEqual(
            reverted_series["time_series_set_id"], first_series["time_series_set_id"]
        )
        self.assertEqual(reverted_series["version_number"], 1)

        generic = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        ).json()["time_series_sets"]
        self.assertEqual(len(generic), 2)


if __name__ == "__main__":
    unittest.main()
