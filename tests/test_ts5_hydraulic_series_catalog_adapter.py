import unittest

from fastapi.testclient import TestClient

from app.main import create_app


class StubValidationService:
    def validate_text(self, candidate_text):
        raise AssertionError("validation not expected in these tests")

    def validate_file(self, candidate_path):
        raise AssertionError("validation not expected in these tests")


class HydraulicTimeSeriesCatalogAdapterTests(unittest.TestCase):
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

    def test_legacy_hydraulic_set_listed_in_project_catalog_with_origin_label(self):
        created = self._create_diagram()
        self._save_reservoir_with_inflow(
            created["revision"], self._inflow_series(5.0, 6.0)
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
        save_response = self._save_reservoir_with_inflow(
            created["revision"], self._inflow_series(5.0, 6.0)
        )
        node = save_response.json()["diagram"]["nodes"][0]
        legacy_series = node["natural_inflow_series"]
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
        self._save_reservoir_with_inflow(
            created["revision"], self._inflow_series(5.0, 6.0)
        )

        reloaded = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        node = reloaded["nodes"][0]
        self.assertEqual(
            [point["value_m3s"] for point in node["natural_inflow_series"]["points"]],
            [5.0, 6.0],
        )
        self.assertEqual(len(node["available_inflow_series"]), 1)

    def test_hydraulic_set_from_other_project_is_not_exposed(self):
        created = self._create_diagram()
        save_response = self._save_reservoir_with_inflow(
            created["revision"], self._inflow_series(5.0, 6.0)
        )
        hydraulic_set_id = save_response.json()["diagram"]["nodes"][0][
            "natural_inflow_series"
        ]["time_series_set_id"]

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


    def _min_flow_series(self, *values, version_label="v1"):
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

    def _save_reach_with_min_flow_series(self, series):
        created = self._create_diagram()
        return self.client.put(
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
                        "minimum_flow_series": series,
                    }
                ],
            },
        )

    def test_reach_minimum_flow_series_listed_and_browsable_via_adapter(self):
        save_response = self._save_reach_with_min_flow_series(
            self._min_flow_series(2.0, 4.0)
        )
        reach = save_response.json()["diagram"]["reaches"][0]
        legacy_series = reach["minimum_flow_series"]

        list_response = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic"
        )
        entries = list_response.json()["hydraulic_time_series_sets"]
        entry = next(item for item in entries if item["entity_type"] == "hydraulic_reach")
        self.assertEqual(entry["signal_key"], "minimum_flow_m3s")
        self.assertEqual(entry["entity_display_name"], "Alpha to Junction")

        detail_response = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/hydraulic/"
            f"{legacy_series['time_series_set_id']}"
        )
        detail = detail_response.json()["hydraulic_time_series_set"]
        self.assertEqual(
            [value["value_numeric"] for value in detail["values"]], [2.0, 4.0]
        )


if __name__ == "__main__":
    unittest.main()
