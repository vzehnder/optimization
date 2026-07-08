import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AnalystStore
from app.validation import ValidationResult


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok"},
        )


def draft_document_with_load_and_renewable() -> dict:
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": "legacy_case"},
        "pcc": {"id": "bus_1", "type": "bus"},
        "grid": {"id": "grid_1"},
        "assets": [
            {"id": "load_1", "type": "load"},
            {"id": "solar_1", "type": "renewable", "category": "solar"},
        ],
        "time_series": {"sources": []},
        "solver": {"name": "HiGHS", "options": {}},
    }


def csv_source_bytes() -> str:
    return (
        "period_start,hours,buy_price,sell_price,load_1_demand,solar_1_avail\n"
        "2026-01-01T00:00:00,1.0,55.0,45.0,10.0,0.0\n"
        "2026-01-01T01:00:00,1.0,60.0,48.0,12.0,5.0\n"
    )


class DraftSeriesExtractionTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS-5 extraction project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Legacy draft scenario"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"],
            document=draft_document_with_load_and_renewable(),
        )

    def upload_and_map_source(self):
        from app.time_series_ingestion import (
            apply_time_series_mapping,
            attach_time_series_source,
            ingest_csv_source,
        )
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            draft = self.store.get_scenario_draft(self.scenario["id"])
            source = ingest_csv_source(
                draft_document=draft["document"],
                original_filename="legacy_prices.csv",
                content_type="text/csv",
                content=csv_source_bytes().encode("utf-8"),
                input_source_root=input_source_root,
            )
            updated_document = attach_time_series_source(draft["document"], source)
            self.store.update_scenario_draft(
                scenario_id=self.scenario["id"], document=updated_document
            )
            mapping = {
                "timestamp": "period_start",
                "duration_hours": "hours",
                "import_price_usd_per_mwh": "buy_price",
                "export_price_usd_per_mwh": "sell_price",
                "load_demand_mw": {"load_1": "load_1_demand"},
                "renewable_available_power_mw": {"solar_1": "solar_1_avail"},
            }
            draft = self.store.get_scenario_draft(self.scenario["id"])
            mapped_document, mapped_source = apply_time_series_mapping(
                document=draft["document"],
                source_id=source["id"],
                mapping=mapping,
                input_source_root=input_source_root,
            )
            self.store.update_scenario_draft(
                scenario_id=self.scenario["id"], document=mapped_document
            )
            return mapped_source["id"]

    def test_extraction_creates_generic_catalog_set_from_validated_rows(self):
        source_id = self.upload_and_map_source()

        created_set = self.store.extract_draft_time_series_set(
            scenario_id=self.scenario["id"],
            source_id=source_id,
            set_name="Legacy case series",
            version_label="v1",
            data_kind="real",
            timezone_name="America/Santiago",
        )

        self.assertEqual(created_set["period_count"], 2)
        signal_keys = {signal["signal_key"] for signal in created_set["signals"]}
        self.assertEqual(
            signal_keys,
            {
                "import_price_usd_per_mwh",
                "export_price_usd_per_mwh",
                "load_demand_mw",
                "renewable_available_power_mw",
            },
        )
        load_signal = next(
            signal
            for signal in created_set["signals"]
            if signal["signal_key"] == "load_demand_mw"
        )
        self.assertEqual(load_signal["entity_key"], "load_1")

        listed = self.store.list_time_series_sets(self.project["id"])
        self.assertIn(created_set["id"], [item["id"] for item in listed])

        values_by_signal = {
            (value["period_index"], value["signal_key"])
            for value in created_set["values"]
        }
        self.assertIn((0, "load_demand_mw"), values_by_signal)
        first_load_value = next(
            value["value_numeric"]
            for value in created_set["values"]
            if value["period_index"] == 0 and value["signal_key"] == "load_demand_mw"
        )
        self.assertEqual(first_load_value, 10.0)

    def test_reextraction_is_idempotent_and_creates_no_duplicates(self):
        source_id = self.upload_and_map_source()
        kwargs = dict(
            scenario_id=self.scenario["id"],
            source_id=source_id,
            set_name="Legacy case series",
            version_label="v1",
            data_kind="real",
            timezone_name="America/Santiago",
        )

        first = self.store.extract_draft_time_series_set(**kwargs)
        second = self.store.extract_draft_time_series_set(**kwargs)

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["content_hash"], second["content_hash"])
        listed = self.store.list_time_series_sets(self.project["id"])
        self.assertEqual(len(listed), 1)
        revisions = self.store.list_time_series_set_revisions(self.project["id"], first["id"])
        self.assertEqual(len(revisions), 1)
        self.assertEqual(len(second["values"]), len(first["values"]))

    def test_extraction_records_origin_metadata(self):
        source_id = self.upload_and_map_source()

        created_set = self.store.extract_draft_time_series_set(
            scenario_id=self.scenario["id"],
            source_id=source_id,
            set_name="Legacy case series",
            version_label="v1",
            data_kind="real",
            timezone_name="America/Santiago",
            created_by="analyst@example.com",
        )

        origin = created_set["revision_metadata"]["origin"]
        self.assertEqual(origin["kind"], "legacy_draft_extraction")
        self.assertEqual(origin["scenario_id"], self.scenario["id"])
        self.assertEqual(origin["source_id"], source_id)
        self.assertEqual(origin["source_filename"], "legacy_prices.csv")
        self.assertEqual(origin["extracted_by"], "analyst@example.com")
        self.assertTrue(origin["source_checksum"])
        self.assertTrue(origin["extracted_at"])

    def test_extraction_leaves_draft_document_unchanged(self):
        source_id = self.upload_and_map_source()
        draft_before = self.store.get_scenario_draft(self.scenario["id"])

        self.store.extract_draft_time_series_set(
            scenario_id=self.scenario["id"],
            source_id=source_id,
            set_name="Legacy case series",
            version_label="v1",
            data_kind="real",
            timezone_name="America/Santiago",
        )

        draft_after = self.store.get_scenario_draft(self.scenario["id"])
        self.assertEqual(draft_before["document"], draft_after["document"])
        self.assertEqual(draft_before["updated_at"], draft_after["updated_at"])

    def test_extraction_is_bindable_to_a_case_input_variant(self):
        source_id = self.upload_and_map_source()
        created_set = self.store.extract_draft_time_series_set(
            scenario_id=self.scenario["id"],
            source_id=source_id,
            set_name="Legacy case series",
            version_label="v1",
            data_kind="real",
            timezone_name="America/Santiago",
        )
        case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        variant = self.store.get_or_create_default_input_variant(case["id"])

        binding = self.store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_1",
            time_series_set_id=created_set["id"],
        )

        self.assertEqual(binding["time_series_set_id"], created_set["id"])

    def test_extraction_without_validated_rows_raises_clear_error(self):
        from app.time_series_ingestion import attach_time_series_source, ingest_csv_source
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            draft = self.store.get_scenario_draft(self.scenario["id"])
            source = ingest_csv_source(
                draft_document=draft["document"],
                original_filename="unmapped.csv",
                content_type="text/csv",
                content=csv_source_bytes().encode("utf-8"),
                input_source_root=input_source_root,
            )
            updated_document = attach_time_series_source(draft["document"], source)
            self.store.update_scenario_draft(
                scenario_id=self.scenario["id"], document=updated_document
            )

            with self.assertRaisesRegex(ValueError, "has not passed mapping validation"):
                self.store.extract_draft_time_series_set(
                    scenario_id=self.scenario["id"],
                    source_id=source["id"],
                    set_name="Unmapped series",
                    version_label="v1",
                    data_kind="real",
                    timezone_name="UTC",
                )


class DraftSeriesExtractionEndpointTests(unittest.TestCase):
    def make_client_and_context(self, input_source_root: Path):
        client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                input_source_root=input_source_root,
            )
        )
        project = client.post("/api/projects", json={"name": "TS-5 extraction project"}).json()
        scenario = client.post(
            f"/api/projects/{project['id']}/scenarios",
            json={"name": "Legacy draft scenario"},
        ).json()
        client.post(
            f"/api/scenarios/{scenario['id']}/draft",
            json={"document": draft_document_with_load_and_renewable()},
        )
        return client, project, scenario

    def test_extract_endpoint_creates_catalog_set_listed_in_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, project, scenario = self.make_client_and_context(input_source_root)

            upload = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("legacy_prices.csv", csv_source_bytes(), "text/csv")},
            )
            source = upload.json()["source"]
            mapping_response = client.put(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{source['id']}/mapping",
                json={
                    "mapping": {
                        "timestamp": "period_start",
                        "duration_hours": "hours",
                        "import_price_usd_per_mwh": "buy_price",
                        "export_price_usd_per_mwh": "sell_price",
                        "load_demand_mw": {"load_1": "load_1_demand"},
                        "renewable_available_power_mw": {"solar_1": "solar_1_avail"},
                    }
                },
            )
            self.assertEqual(mapping_response.status_code, 200)

            extract_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{source['id']}/extract",
                json={
                    "set_name": "Legacy case series",
                    "version_label": "v1",
                    "data_kind": "real",
                    "timezone": "America/Santiago",
                },
            )

            self.assertEqual(extract_response.status_code, 201)
            created_set = extract_response.json()["time_series_set"]
            self.assertEqual(created_set["period_count"], 2)

            listing = client.get(f"/api/projects/{project['id']}/time-series-sets")
            self.assertEqual(listing.status_code, 200)
            self.assertIn(
                created_set["id"],
                [item["id"] for item in listing.json()["time_series_sets"]],
            )

    def test_extract_endpoint_rejects_source_without_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_source_root = Path(temp_dir) / "input-sources"
            client, _project, scenario = self.make_client_and_context(input_source_root)

            upload = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/upload",
                files={"source_file": ("legacy_prices.csv", csv_source_bytes(), "text/csv")},
            )
            source = upload.json()["source"]

            extract_response = client.post(
                f"/api/scenarios/{scenario['id']}/draft/time-series-sources/{source['id']}/extract",
                json={
                    "set_name": "Legacy case series",
                    "version_label": "v1",
                    "data_kind": "real",
                    "timezone": "America/Santiago",
                },
            )

            self.assertEqual(extract_response.status_code, 400)
            self.assertIn("has not passed mapping validation", extract_response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
