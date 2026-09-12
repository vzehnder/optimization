"""UX-005: authenticated public preparation, validation and run contracts (F3)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf
from tests.test_ts3_case_variant_api import grid_battery_draft_document
from tests.auth_test_helpers import post_json_with_csrf
from tests.auth_test_helpers import csrf_headers
from tests import test_ts7_009_run_materialization as canonical_fixtures
from tests.test_ts7_022_c6_cutover import import_legacy_price_set
from app.time_series_catalog import CatalogImportRequest, CatalogSignalMappingRequest, prepare_time_series_catalog_import


class VariantPreparationApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.client = TestClient(create_app(store=self.store, auth_enabled=True, validation_service=canonical_fixtures.AcceptingValidationService(), run_queue=canonical_fixtures.RecordingRunQueue()))
        self.store.create_user(email="ux005@example.local", display_name="Analista UX", role="analyst", password_hash=hash_password("test-only"))
        login_json_with_csrf(self.client, "ux005@example.local", "test-only")
        self.project = self.store.create_project(name="Preparación UX-005")
        self.scenario = self.store.create_scenario(project_id=self.project["id"], name="Dos horas")
        self.store.create_or_replace_scenario_draft(scenario_id=self.scenario["id"], document=grid_battery_draft_document())
        self.path = f"/api/scenarios/{self.scenario['id']}/case/variants"

    def test_c6_execution_keeps_the_reviewed_revision_and_rejects_a_changed_model_without_touching_history(self):
        variant_id = self.client.get(self.path).json()["variants"][0]["variant"]["id"]
        source = import_legacy_price_set(self.store, self.scenario["id"])
        bound = post_json_with_csrf(self.client, f"{self.path}/{variant_id}/bindings", {"signal_key": "import_price_usd_per_mwh", "time_series_set_id": source["id"]})
        self.assertEqual(bound.status_code, 201, bound.text)
        with tempfile.TemporaryDirectory() as recovery:
            self.store.take_c0_recovery_point(actor="internal_admin", copy_directory=Path(recovery))
            self.store.backfill_time_series_c2(actor="internal_admin")
            self.store.backfill_time_series_c3(actor="internal_admin")
            self.store.backfill_time_series_c4(actor="internal_admin")
            self.store.verify_time_series_c5_shadow(actor="internal_admin")
            self.store.cut_over_time_series_c6(actor="internal_admin")
        preparation = self.client.get(self.path).json()["variants"][0]["preparation"]
        self.assertEqual(preparation["binding_mode"], "protected")
        payload = {"range_start": "2026-01-01T00:00:00+00:00", "range_end": "2026-01-01T02:00:00+00:00", "expected_bindings_revision": preparation["bindings_revision"]}
        reviewed = post_json_with_csrf(self.client, f"{self.path}/{variant_id}/validate", payload)
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        accepted = post_json_with_csrf(self.client, f"{self.path}/{variant_id}/run", payload)
        self.assertEqual(accepted.status_code, 201, accepted.text)
        version_path = f"/api/scenario-versions/{accepted.json()['scenario_version_id']}"
        historical = self.client.get(version_path).json()
        metadata = historical["scenario_version"]["generation_metadata"]
        self.assertEqual(metadata["actor"]["email"], "ux005@example.local")
        self.assertEqual(metadata["date_range"], {"start": payload["range_start"], "end": payload["range_end"]})
        self.assertEqual(metadata["series_bindings"][0]["revision_number"], 1)
        document = grid_battery_draft_document()
        document["assets"][0]["energy_max_mwh"] = 12
        updated = self.client.put(f"/api/scenarios/{self.scenario['id']}/draft", json={"document": document}, headers=csrf_headers(self.client))
        self.assertEqual(updated.status_code, 200, updated.text)
        rejected = post_json_with_csrf(self.client, f"{self.path}/{variant_id}/run", payload)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        reviewed_again = post_json_with_csrf(self.client, f"{self.path}/{variant_id}/validate", payload)
        self.assertEqual(reviewed_again.status_code, 409, reviewed_again.text)
        self.assertEqual(len(self.client.get(f"/api/scenarios/{self.scenario['id']}/runs").json()["runs"]), 1)
        self.assertEqual(self.client.get(version_path).json(), historical)

    def test_available_coverage_is_only_offered_when_all_bound_periods_have_no_holes(self):
        variant_id = self.client.get(self.path).json()["variants"][0]["variant"]["id"]
        for hours, name, expected in [
            ([0, 1], "Completa", {"start": "2026-01-01T00:00:00-03:00", "end": "2026-01-01T02:00:00-03:00"}),
            ([0, 2], "Con hueco", None),
        ]:
            prepared = prepare_time_series_catalog_import(rows=[{"time": f"2026-01-01T{hour:02d}:00:00", "hours": "1", "price": "70"} for hour in hours], request=CatalogImportRequest(
                set_name=name, version_label="v1", data_kind="real", timezone="America/Santiago", timestamp_column="time", duration_hours_column="hours",
                signal_mappings=[CatalogSignalMappingRequest(source_column="price", signal_key="import_price_usd_per_mwh")],
            ))
            source = self.store.import_time_series_catalog_set(scenario_id=self.scenario["id"], source={"id": name, "original_filename": "price.csv", "media_type": "text/csv", "checksum": name}, prepared_import=prepared)
            bound = post_json_with_csrf(self.client, f"{self.path}/{variant_id}/bindings", {"signal_key": "import_price_usd_per_mwh", "time_series_set_id": source["id"]})
            self.assertEqual(bound.status_code, 201, bound.text)
            preparation = self.client.get(self.path).json()["variants"][0]["preparation"]
            self.assertEqual(preparation["available_coverage"], expected)

    def test_canonical_preparation_reviews_exact_sources_and_range_without_creating_a_version_or_run(self):
        fixture = canonical_fixtures.CanonicalRunMaterializationApiTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        root = f"/api/scenarios/{fixture.scenario['id']}"
        detail = fixture.client.get(f"{root}/case/variants").json()["variants"][0]
        preparation = detail["preparation"]
        self.assertEqual(preparation["binding_mode"], "protected")
        self.assertTrue(preparation["required_signals"][0]["bound"])
        self.assertEqual(preparation["required_signals"][0]["linkable_object_id"], fixture.object["id"])
        self.assertEqual(preparation["sources"][0]["revision_number"], 1)
        reviewed = post_json_with_csrf(fixture.client, f"{root}/case/variants/{fixture.variant['id']}/validate", {
            "range_start": "2026-01-01T00:00:00", "range_end": "2026-01-01T02:00:00",
            "expected_bindings_revision": preparation["bindings_revision"],
        })
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        self.assertEqual(reviewed.json()["status"], "valid")
        self.assertEqual(fixture.client.get(f"{root}/versions").json()["versions"], [])
        self.assertEqual(fixture.client.get(f"{root}/runs").json()["runs"], [])

    def test_binding_editor_capability_follows_c6_even_when_canonical_read_is_enabled_before_cutover(self):
        with patch.dict("os.environ", {"TS_NEXT_CANONICAL_READ_ACCOUNTS": "ux005@example.local"}):
            self.assertTrue(self.client.get("/api/auth/me").json()["ts_next_canonical_read"])
            response = self.client.get(self.path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["variants"][0]["preparation"]["binding_mode"], "legacy")
            with tempfile.TemporaryDirectory() as recovery:
                self.store.take_c0_recovery_point(actor="internal_admin", copy_directory=Path(recovery))
                self.store.backfill_time_series_c2(actor="internal_admin")
                self.store.backfill_time_series_c3(actor="internal_admin")
                self.store.backfill_time_series_c4(actor="internal_admin")
                self.store.verify_time_series_c5_shadow(actor="internal_admin")
                self.store.cut_over_time_series_c6(actor="internal_admin")
            response = self.client.get(self.path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["variants"][0]["preparation"]["binding_mode"], "protected")
