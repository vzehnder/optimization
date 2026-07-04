import copy
import unittest

from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_hydro_diagram_acceptance import (
    HydroAcceptanceValidationService,
    complete_v3_nodes,
)


def make_client_and_scenario():
    validation_service = HydroAcceptanceValidationService()
    client = TestClient(
        create_app(validation_service=validation_service, database_url="sqlite:///:memory:")
    )
    project = client.post("/api/projects", json={"name": "Hydro Provenance"}).json()
    scenario = client.post(
        f"/api/projects/{project['id']}/scenarios", json={"name": "Hydraulic case"}
    ).json()
    return client, scenario


def base_reach():
    return {
        "technical_key": "reach_reservoir_intake",
        "display_name": "Reservoir to intake",
        "from_node_key": "reservoir_alpha",
        "to_node_key": "junction_in",
        "reach_type": "river",
    }


def save_diagram(client, scenario_id, revision, *, nodes=None, reaches=None):
    response = client.put(
        f"/api/scenarios/{scenario_id}/hydraulic-diagram",
        json={
            "revision": revision,
            "nodes": nodes if nodes is not None else complete_v3_nodes(),
            "reaches": reaches if reaches is not None else [base_reach()],
        },
    )
    if response.status_code != 200:
        raise AssertionError(response.text)
    return response.json()["diagram"]


def promote_hydraulic_diagram(client, scenario_id):
    validate = client.post(f"/api/scenarios/{scenario_id}/hydraulic-diagram/validate")
    if not validate.json()["validation"]["ok"]:
        raise AssertionError(validate.text)
    preview = client.post(f"/api/scenarios/{scenario_id}/hydraulic-diagram/v3-preview")
    if preview.status_code != 200 or not preview.json()["validation"]["ok"]:
        raise AssertionError(preview.text)
    promote = client.post(f"/api/scenarios/{scenario_id}/hydraulic-diagram/promote")
    if promote.status_code != 201:
        raise AssertionError(promote.text)
    return promote.json()


class HydraulicDiagramHierarchyProvenanceTests(unittest.TestCase):
    def test_promoted_hydraulic_diagram_version_records_topology_and_parameter_provenance(self):
        client, scenario = make_client_and_scenario()
        created = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        save_diagram(client, scenario["id"], created["revision"])

        version = promote_hydraulic_diagram(client, scenario["id"])

        generation_metadata = version["generation_metadata"]
        self.assertEqual(generation_metadata["kind"], "hydraulic_diagram_v3")
        topology_hash = generation_metadata["topology"]["content_hash"]
        parameters_hash = generation_metadata["parameters"]["content_hash"]
        self.assertTrue(topology_hash.startswith("sha256:"))
        self.assertTrue(parameters_hash.startswith("sha256:"))
        self.assertNotEqual(topology_hash, parameters_hash)

    def test_layout_only_move_keeps_topology_and_parameters_hash_stable(self):
        client, scenario = make_client_and_scenario()
        created = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        save_diagram(client, scenario["id"], created["revision"])
        baseline = promote_hydraulic_diagram(client, scenario["id"])["generation_metadata"]

        reloaded = client.get(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        moved_nodes = copy.deepcopy(reloaded["nodes"])
        for node in moved_nodes:
            if node["technical_key"] == "reservoir_alpha":
                node["x"], node["y"] = 999.0, 999.0

        save_diagram(
            client,
            scenario["id"],
            reloaded["revision"],
            nodes=moved_nodes,
            reaches=reloaded["reaches"],
        )
        edited = promote_hydraulic_diagram(client, scenario["id"])["generation_metadata"]

        self.assertEqual(
            edited["topology"]["content_hash"], baseline["topology"]["content_hash"]
        )
        self.assertEqual(
            edited["parameters"]["content_hash"], baseline["parameters"]["content_hash"]
        )

    def test_reservoir_curve_unit_and_reach_control_edits_change_parameters_but_not_topology(self):
        client, scenario = make_client_and_scenario()
        created = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        save_diagram(client, scenario["id"], created["revision"])
        baseline = promote_hydraulic_diagram(client, scenario["id"])["generation_metadata"]

        reloaded = client.get(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        edited_nodes = copy.deepcopy(reloaded["nodes"])
        for node in edited_nodes:
            if node["technical_key"] == "reservoir_alpha":
                node["reservoir"]["storage_max_hm3"] = 40.0
                node["storage_elevation_curve"]["points"][-1]["y_value"] = 770.0
            if node["technical_key"] == "plant_laja":
                node["units"][0]["max_power_mw"] = 45.0
        edited_reaches = copy.deepcopy(reloaded["reaches"])
        edited_reaches[0]["flow_min_m3s"] = 1.5

        save_diagram(
            client,
            scenario["id"],
            reloaded["revision"],
            nodes=edited_nodes,
            reaches=edited_reaches,
        )
        edited = promote_hydraulic_diagram(client, scenario["id"])["generation_metadata"]

        self.assertEqual(
            edited["topology"]["content_hash"], baseline["topology"]["content_hash"]
        )
        self.assertNotEqual(
            edited["parameters"]["content_hash"], baseline["parameters"]["content_hash"]
        )

    def test_structural_edit_adding_node_and_reach_changes_topology_hash(self):
        client, scenario = make_client_and_scenario()
        created = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        save_diagram(client, scenario["id"], created["revision"])
        baseline = promote_hydraulic_diagram(client, scenario["id"])["generation_metadata"]

        reloaded = client.get(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        extra_node = {
            "component_type": "junction",
            "technical_key": "junction_extra",
            "display_name": "Extra junction",
            "x": 600.0,
            "y": 200.0,
        }
        extra_reach = {
            "technical_key": "reach_out_extra",
            "display_name": "Tailrace to extra",
            "from_node_key": "junction_out",
            "to_node_key": "junction_extra",
            "reach_type": "river",
        }
        nodes = copy.deepcopy(reloaded["nodes"]) + [extra_node]
        reaches = copy.deepcopy(reloaded["reaches"]) + [extra_reach]

        save_diagram(
            client, scenario["id"], reloaded["revision"], nodes=nodes, reaches=reaches
        )
        edited = promote_hydraulic_diagram(client, scenario["id"])["generation_metadata"]

        self.assertNotEqual(
            edited["topology"]["content_hash"], baseline["topology"]["content_hash"]
        )


    def test_unit_connectivity_edit_changes_topology_hash_without_adding_components(self):
        client, scenario = make_client_and_scenario()
        created = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        save_diagram(client, scenario["id"], created["revision"])
        baseline = promote_hydraulic_diagram(client, scenario["id"])["generation_metadata"]

        reloaded = client.get(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        edited_nodes = copy.deepcopy(reloaded["nodes"])
        for node in edited_nodes:
            if node["technical_key"] == "plant_laja":
                node["units"][0]["intake_node_key"] = "reservoir_alpha"

        save_diagram(
            client,
            scenario["id"],
            reloaded["revision"],
            nodes=edited_nodes,
            reaches=reloaded["reaches"],
        )
        edited = promote_hydraulic_diagram(client, scenario["id"])["generation_metadata"]

        self.assertNotEqual(
            edited["topology"]["content_hash"], baseline["topology"]["content_hash"]
        )
        self.assertEqual(
            edited["parameters"]["content_hash"], baseline["parameters"]["content_hash"]
        )


if __name__ == "__main__":
    unittest.main()
