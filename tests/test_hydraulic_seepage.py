"""Optional physical reach laws through the diagram's HTTP interface."""
import copy
import unittest

from tests import test_hydraulic_diagram as hydraulic_fixture


def seepage(points=None):
    return {"kind": "seepage", "level_timing": "start", "curve": {"points": points or [
        {"x_value": 700, "y_value": 0},
        {"x_value": 720, "y_value": 2},
        {"x_value": 760, "y_value": 10},
    ]}}


class HydraulicSeepageApiTests(unittest.TestCase):
    setUp = hydraulic_fixture.HydraulicDiagramApiTests.setUp
    _create_diagram = hydraulic_fixture.HydraulicDiagramApiTests._create_diagram
    _save_complete_v3_diagram = hydraulic_fixture.HydraulicDiagramApiTests._save_complete_v3_diagram

    def tearDown(self):
        self.client.close()

    @property
    def root(self):
        return f"/api/scenarios/{self.scenario['id']}/hydraulic-diagram"

    def test_filtration_can_be_saved_reloaded_and_removed_from_a_reach(self):
        self._save_complete_v3_diagram(reach_overrides={"flow_behavior": seepage()})
        diagram = self.client.get(self.root).json()["diagram"]
        behavior = diagram["reaches"][0]["flow_behavior"]
        self.assertIsNotNone(behavior)
        self.assertEqual(behavior["curve"]["points"], seepage()["curve"]["points"])
        self.assertEqual(behavior["level_timing"], "start")
        diagram["reaches"][0]["flow_behavior"] = None
        response = self.client.put(self.root, json=diagram)
        self.assertEqual(response.status_code, 200, response.text)
        reloaded = self.client.get(self.root).json()["diagram"]
        self.assertIsNone(reloaded["reaches"][0]["flow_behavior"])

    def test_preview_contains_the_filtration_law_and_its_curve_in_the_case(self):
        self._save_complete_v3_diagram(reach_overrides={"flow_behavior": seepage()})
        response = self.client.post(self.root + "/v3-preview")
        self.assertEqual(response.status_code, 200, response.text)
        network = response.json()["validation"]["system_case"]["hydraulic_network"]
        law = network["reaches"][0]["flow_behavior"]
        self.assertEqual(law, {"kind": "seepage", "level_timing": "start", "curve": [
            {"elevation_masl": 700, "flow_m3s": 0},
            {"elevation_masl": 720, "flow_m3s": 2},
            {"elevation_masl": 760, "flow_m3s": 10},
        ]})
        curve = next((c for c in network["curves"] if c["curve_role"] == "elevation_flow"), None)
        self.assertIsNotNone(curve)
        self.assertEqual(curve["entity_id"], "reach_reservoir_intake")
        self.assertEqual(curve["points"], law["curve"])

    def test_invalid_filtration_is_reported_on_the_reach_before_optimization(self):
        diagram = self._save_complete_v3_diagram(reach_overrides={"flow_behavior": seepage()})
        cases = [
            ({"flow_behavior": seepage([{"x_value": 710, "y_value": 0}, {"x_value": 760, "y_value": 2}])}, "elevation_flow_domain"),
            ({"flow_behavior": seepage([{"x_value": 700, "y_value": 0}, {"x_value": 700, "y_value": 2}])}, "invalid_elevation_flow_curve"),
            ({"flow_behavior": seepage([{"x_value": 700, "y_value": -1}, {"x_value": 760, "y_value": 2}])}, "invalid_elevation_flow_curve"),
            ({"flow_behavior": {"kind": "seepage", "curve": {"points": []}}}, "invalid_elevation_flow_curve"),
            ({"from_node_key": "junction_out"}, "seepage_requires_reservoir"),
        ]
        original = copy.deepcopy(diagram["reaches"][0])
        for patch, code in cases:
            with self.subTest(code=code, patch=patch):
                diagram["reaches"][0] = {**copy.deepcopy(original), **patch}
                saved = self.client.put(self.root, json=diagram)
                self.assertEqual(saved.status_code, 200, saved.text)
                diagram = saved.json()["diagram"]
                response = self.client.post(self.root + "/validate")
                self.assertEqual(response.status_code, 200, response.text)
                issues = response.json()["validation"]["errors"]
                self.assertTrue(any(e["code"] == code and e["technical_key"] == "reach_reservoir_intake" for e in issues), issues)


if __name__ == "__main__":
    unittest.main()
