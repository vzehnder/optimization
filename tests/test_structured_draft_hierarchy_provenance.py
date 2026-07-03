import tempfile
import unittest
from pathlib import Path

from tests.test_draft_generated_system_case import (
    RecordingValidationService,
    make_client_and_scenario,
    make_hydro_client_and_scenario,
    upload_mapped_csv,
    upload_mapped_hydro_csv,
)


class StructuredDraftHierarchyProvenanceTests(unittest.TestCase):
    def test_promoted_structured_draft_version_records_topology_and_parameter_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_csv(client, scenario["id"])

            client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")
            promote_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote",
            )

            self.assertEqual(promote_response.status_code, 201)
            generation_metadata = promote_response.json()["generation_metadata"]
            self.assertEqual(generation_metadata["kind"], "structured_draft")
            topology_hash = generation_metadata["topology"]["content_hash"]
            parameters_hash = generation_metadata["parameters"]["content_hash"]
            self.assertTrue(topology_hash.startswith("sha256:"))
            self.assertTrue(parameters_hash.startswith("sha256:"))
            self.assertNotEqual(topology_hash, parameters_hash)

    def test_parameter_only_draft_edit_keeps_topology_hash_but_changes_parameters_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_csv(client, scenario["id"])

            client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")
            baseline = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote",
            ).json()["generation_metadata"]

            document = client.get(f"/api/scenarios/{scenario['id']}/draft").json()["draft"]["document"]
            for asset in document["assets"]:
                if asset["id"] == "battery_1":
                    asset["charge_power_max_mw"] = 999.0
            client.put(f"/api/scenarios/{scenario['id']}/draft", json={"document": document})

            client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")
            edited = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote",
            ).json()["generation_metadata"]

            self.assertEqual(edited["topology"]["content_hash"], baseline["topology"]["content_hash"])
            self.assertNotEqual(edited["parameters"]["content_hash"], baseline["parameters"]["content_hash"])

    def test_structural_draft_edit_changes_topology_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_csv(client, scenario["id"])

            client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")
            baseline = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote",
            ).json()["generation_metadata"]

            document = client.get(f"/api/scenarios/{scenario['id']}/draft").json()["draft"]["document"]
            document["assets"] = [asset for asset in document["assets"] if asset["id"] != "solar_1"]
            client.put(f"/api/scenarios/{scenario['id']}/draft", json={"document": document})

            client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")
            edited = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote",
            ).json()["generation_metadata"]

            self.assertNotEqual(edited["topology"]["content_hash"], baseline["topology"]["content_hash"])

    def test_hydro_mapping_metadata_and_hierarchy_provenance_coexist_after_promotion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validation_service = RecordingValidationService()
            client, scenario = make_hydro_client_and_scenario(Path(temp_dir), validation_service)
            upload_mapped_hydro_csv(client, scenario["id"])

            client.post(f"/api/scenarios/{scenario['id']}/draft/generated-system-case/validate")
            generation_metadata = client.post(
                f"/api/scenarios/{scenario['id']}/draft/generated-system-case/promote",
            ).json()["generation_metadata"]

            self.assertEqual(
                generation_metadata["mapping"]["hydro_inflow_m3s"],
                {"hydro_1": "hydro_inflow_m3s"},
            )
            self.assertTrue(generation_metadata["topology"]["content_hash"].startswith("sha256:"))
            self.assertTrue(generation_metadata["parameters"]["content_hash"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
