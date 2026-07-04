import copy
import tempfile
import unittest
from pathlib import Path

from tests.test_draft_generated_system_case import (
    RecordingValidationService,
    make_client_and_scenario as make_draft_client_and_scenario,
    upload_mapped_csv,
)
from tests.test_hydraulic_diagram_hierarchy_provenance import (
    make_client_and_scenario,
    promote_hydraulic_diagram,
    save_diagram,
)


class HydraulicStaleValidationTests(unittest.TestCase):
    def test_v3_preview_validation_snapshot_records_topology_and_parameters_hash(self):
        client, scenario = make_client_and_scenario()
        created = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        save_diagram(client, scenario["id"], created["revision"])

        client.post(f"/api/scenarios/{scenario['id']}/hydraulic-diagram/validate")
        preview = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram/v3-preview"
        ).json()["validation"]

        self.assertTrue(preview["topology"]["content_hash"].startswith("sha256:"))
        self.assertTrue(preview["parameters"]["content_hash"].startswith("sha256:"))
        self.assertNotEqual(preview["topology"]["content_hash"], preview["parameters"]["content_hash"])

    def test_topology_only_edit_marks_validation_stale_with_topology_flag(self):
        client, scenario = make_client_and_scenario()
        created = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        save_diagram(client, scenario["id"], created["revision"])
        promote_hydraulic_diagram(client, scenario["id"])

        reloaded = client.get(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        self.assertTrue(reloaded["validation"]["ok"])
        self.assertFalse(reloaded["validation"]["stale"])

        edited_nodes = copy.deepcopy(reloaded["nodes"])
        for node in edited_nodes:
            if node["technical_key"] == "plant_laja":
                node["units"][0]["intake_node_key"] = "reservoir_alpha"

        stale_save = client.put(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram",
            json={
                "revision": reloaded["revision"],
                "nodes": edited_nodes,
                "reaches": reloaded["reaches"],
                "viewport": reloaded["layout"]["viewport"],
            },
        )
        self.assertEqual(stale_save.status_code, 200)
        validation = stale_save.json()["diagram"]["validation"]
        self.assertTrue(validation["stale"])
        self.assertTrue(validation["topology_stale"])
        self.assertFalse(validation["parameters_stale"])

        promote = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram/promote"
        )
        self.assertEqual(promote.status_code, 400)
        self.assertIn("topology", promote.json()["detail"])

    def test_parameter_only_edit_marks_validation_stale_with_parameters_flag(self):
        client, scenario = make_client_and_scenario()
        created = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        save_diagram(client, scenario["id"], created["revision"])
        promote_hydraulic_diagram(client, scenario["id"])

        reloaded = client.get(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        edited_nodes = copy.deepcopy(reloaded["nodes"])
        for node in edited_nodes:
            if node["technical_key"] == "reservoir_alpha":
                node["reservoir"]["storage_max_hm3"] = 42.0

        stale_save = client.put(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram",
            json={
                "revision": reloaded["revision"],
                "nodes": edited_nodes,
                "reaches": reloaded["reaches"],
                "viewport": reloaded["layout"]["viewport"],
            },
        )
        self.assertEqual(stale_save.status_code, 200)
        validation = stale_save.json()["diagram"]["validation"]
        self.assertTrue(validation["stale"])
        self.assertFalse(validation["topology_stale"])
        self.assertTrue(validation["parameters_stale"])

        promote = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram/promote"
        )
        self.assertEqual(promote.status_code, 400)
        self.assertIn("parameters", promote.json()["detail"])
        self.assertNotIn("topology", promote.json()["detail"])

    def test_layout_only_edit_keeps_validation_non_stale_and_promotable(self):
        client, scenario = make_client_and_scenario()
        created = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        save_diagram(client, scenario["id"], created["revision"])
        promote_hydraulic_diagram(client, scenario["id"])

        reloaded = client.get(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram"
        ).json()["diagram"]
        moved_nodes = copy.deepcopy(reloaded["nodes"])
        for node in moved_nodes:
            if node["technical_key"] == "reservoir_alpha":
                node["x"], node["y"] = 321.0, 654.0

        layout_save = client.put(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram",
            json={
                "revision": reloaded["revision"],
                "nodes": moved_nodes,
                "reaches": reloaded["reaches"],
                "viewport": reloaded["layout"]["viewport"],
            },
        )
        self.assertEqual(layout_save.status_code, 200)
        validation = layout_save.json()["diagram"]["validation"]
        self.assertTrue(validation["ok"])
        self.assertFalse(validation["stale"])

        promote = client.post(
            f"/api/scenarios/{scenario['id']}/hydraulic-diagram/promote"
        )
        self.assertEqual(promote.status_code, 201)


class StructuredDraftStaleValidationTests(unittest.TestCase):
    def test_generated_system_case_validation_snapshot_records_topology_and_parameters_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_draft_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_csv(client, scenario["id"])

            client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")
            stored_generated = client.get(
                f"/api/scenarios/{scenario['id']}/draft"
            ).json()["draft"]["document"]["generated_system_case"]

            self.assertTrue(stored_generated["topology"]["content_hash"].startswith("sha256:"))
            self.assertTrue(stored_generated["parameters"]["content_hash"].startswith("sha256:"))
            self.assertNotEqual(
                stored_generated["topology"]["content_hash"], stored_generated["parameters"]["content_hash"]
            )

    def test_parameter_only_draft_edit_blocks_promotion_with_parameters_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_draft_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_csv(client, scenario["id"])

            client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")

            document = client.get(f"/api/scenarios/{scenario['id']}/draft").json()["draft"]["document"]
            for asset in document["assets"]:
                if asset["id"] == "battery_1":
                    asset["charge_power_max_mw"] = 999.0
            client.put(f"/api/scenarios/{scenario['id']}/draft", json={"document": document})

            promote = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote"
            )
            self.assertEqual(promote.status_code, 400)
            self.assertIn("parameters", promote.json()["detail"])
            self.assertNotIn("topology", promote.json()["detail"])

    def test_structural_draft_edit_blocks_promotion_with_topology_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_draft_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_csv(client, scenario["id"])

            client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")

            document = client.get(f"/api/scenarios/{scenario['id']}/draft").json()["draft"]["document"]
            document["assets"] = [asset for asset in document["assets"] if asset["id"] != "solar_1"]
            client.put(f"/api/scenarios/{scenario['id']}/draft", json={"document": document})

            promote = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote"
            )
            self.assertEqual(promote.status_code, 400)
            self.assertIn("topology", promote.json()["detail"])


if __name__ == "__main__":
    unittest.main()
