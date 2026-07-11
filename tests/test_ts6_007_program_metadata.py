import unittest

from app.forecast_connector import payload_rows_checksum
from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    TimeSeriesCatalogError,
    prepare_time_series_catalog_import,
    validate_program_metadata,
)


def program_metadata(**overrides):
    metadata = {
        "issuer": "Coordinador Electrico Nacional",
        "issued_at": "2026-08-01T10:00:00+00:00",
        "valid_from": "2026-08-02T00:00:00+00:00",
        "valid_until": "2026-08-03T00:00:00+00:00",
    }
    metadata.update(overrides)
    return metadata


class ValidateProgramMetadataTests(unittest.TestCase):
    def test_valid_metadata_is_normalized_and_returned(self):
        validated = validate_program_metadata(program_metadata(issuer="  CEN  "))

        self.assertEqual(
            validated,
            {
                "issuer": "CEN",
                "issued_at": "2026-08-01T10:00:00+00:00",
                "valid_from": "2026-08-02T00:00:00+00:00",
                "valid_until": "2026-08-03T00:00:00+00:00",
            },
        )

    def test_missing_issuer_is_rejected(self):
        with self.assertRaisesRegex(TimeSeriesCatalogError, "issuer is required"):
            validate_program_metadata(program_metadata(issuer="   "))

    def test_non_iso_issue_date_is_rejected(self):
        with self.assertRaisesRegex(TimeSeriesCatalogError, "must be ISO-8601"):
            validate_program_metadata(program_metadata(issued_at="not-a-date"))

    def test_naive_validity_timestamp_is_rejected(self):
        with self.assertRaisesRegex(TimeSeriesCatalogError, "timezone offset"):
            validate_program_metadata(
                program_metadata(valid_from="2026-08-02T00:00:00")
            )

    def test_empty_validity_window_is_rejected(self):
        with self.assertRaisesRegex(
            TimeSeriesCatalogError, "valid_from must be before valid_until"
        ):
            validate_program_metadata(
                program_metadata(
                    valid_from="2026-08-03T00:00:00+00:00",
                    valid_until="2026-08-03T00:00:00+00:00",
                )
            )

    def test_unknown_fields_are_rejected(self):
        with self.assertRaisesRegex(TimeSeriesCatalogError, "unknown field"):
            validate_program_metadata(program_metadata(extra="nope"))


def program_records():
    return [
        {
            "period_start": "2026-08-02T00:00:00",
            "hours": "1.0",
            "demand": "120.0",
            "price": "61.5",
        },
        {
            "period_start": "2026-08-02T01:00:00",
            "hours": "1.0",
            "demand": "121.0",
            "price": "62.5",
        },
    ]


def program_import_request(*, set_name="Programa oficial de despacho", version_label="v1"):
    return CatalogImportRequest(
        set_name=set_name,
        version_label=version_label,
        data_kind="programmed",
        timezone="America/Santiago",
        timestamp_column="period_start",
        duration_hours_column="hours",
        signal_mappings=[
            CatalogSignalMappingRequest(source_column="demand", signal_key="load_demand_mw"),
            CatalogSignalMappingRequest(
                source_column="price", signal_key="import_price_usd_per_mwh"
            ),
        ],
    )


def connector_source(rows, *, connector_id="official_program_api", fetched_at="2026-08-01T12:00:00+00:00"):
    checksum = payload_rows_checksum(rows)
    return {
        "id": f"connector:{connector_id}:{checksum}",
        "kind": "connector",
        "original_filename": f"{connector_id}.json",
        "media_type": "application/json",
        "checksum": checksum,
        "stored_path": "",
        "metadata": {
            "connector_id": connector_id,
            "target": "https://programs.example.com/v1/dispatch",
            "fetched_at": fetched_at,
            "record_count": len(rows),
        },
    }


class ProgrammedIngestionStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS6-007 project")

    def ingest(self, rows, *, program, **source_kwargs):
        prepared = prepare_time_series_catalog_import(
            rows=rows,
            request=program_import_request(),
        )
        return self.store.ingest_connector_time_series_set(
            project_id=self.project["id"],
            source=connector_source(rows, **source_kwargs),
            prepared_import=prepared,
            program=program,
            created_by="analyst@example.com",
        )

    def test_programmed_ingestion_records_issuer_and_validity_on_the_revision(self):
        result = self.ingest(program_records(), program=program_metadata())

        self.assertEqual(result["outcome"], "created")
        ingested = result["time_series_set"]
        self.assertEqual(ingested["data_kind"], "programmed")
        self.assertEqual(ingested["status"], "validated")

        detail = self.store.get_time_series_set(self.project["id"], ingested["id"])
        self.assertEqual(
            detail["revision_metadata"]["program"],
            {
                "issuer": "Coordinador Electrico Nacional",
                "issued_at": "2026-08-01T10:00:00+00:00",
                "valid_from": "2026-08-02T00:00:00+00:00",
                "valid_until": "2026-08-03T00:00:00+00:00",
            },
        )

    def test_programmed_ingestion_without_program_metadata_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "requires program metadata"):
            self.ingest(program_records(), program=None)

    def test_program_metadata_with_non_programmed_data_kind_is_rejected(self):
        prepared = prepare_time_series_catalog_import(
            rows=program_records(),
            request=CatalogImportRequest(
                set_name="Forecast set",
                version_label="v1",
                data_kind="forecast",
                timezone="America/Santiago",
                timestamp_column="period_start",
                duration_hours_column="hours",
                signal_mappings=[
                    CatalogSignalMappingRequest(
                        source_column="demand", signal_key="load_demand_mw"
                    ),
                    CatalogSignalMappingRequest(
                        source_column="price", signal_key="import_price_usd_per_mwh"
                    ),
                ],
            ),
        )

        with self.assertRaisesRegex(ValueError, "only allowed for data_kind 'programmed'"):
            self.store.ingest_connector_time_series_set(
                project_id=self.project["id"],
                source=connector_source(program_records()),
                prepared_import=prepared,
                program=program_metadata(),
                created_by="analyst@example.com",
            )

    def test_invalid_program_metadata_writes_nothing(self):
        with self.assertRaisesRegex(TimeSeriesCatalogError, "issuer is required"):
            self.ingest(program_records(), program=program_metadata(issuer=""))

        self.assertEqual(self.store.list_time_series_sets(self.project["id"]), [])

    def test_corrected_program_lands_as_a_new_revision_with_its_own_metadata(self):
        first = self.ingest(program_records(), program=program_metadata())
        corrected_rows = program_records()
        corrected_rows[0]["demand"] = "150.0"
        corrected_program = program_metadata(
            issued_at="2026-08-01T18:00:00+00:00",
        )

        second = self.ingest(
            corrected_rows,
            program=corrected_program,
            fetched_at="2026-08-01T19:00:00+00:00",
        )

        self.assertEqual(second["outcome"], "new_revision")
        self.assertEqual(
            second["time_series_set"]["id"], first["time_series_set"]["id"]
        )
        self.assertEqual(second["time_series_set"]["revision_number"], 2)

        revisions = self.store.list_time_series_set_revisions(
            self.project["id"], first["time_series_set"]["id"]
        )
        by_revision = {item["revision_number"]: item for item in revisions}
        self.assertEqual(
            by_revision[1]["program"]["issued_at"], "2026-08-01T10:00:00+00:00"
        )
        self.assertEqual(
            by_revision[2]["program"]["issued_at"], "2026-08-01T18:00:00+00:00"
        )
        self.assertEqual(
            by_revision[1]["content_hash"], first["time_series_set"]["content_hash"]
        )

    def test_unchanged_data_and_program_converge_without_a_new_revision(self):
        first = self.ingest(program_records(), program=program_metadata())

        second = self.ingest(
            program_records(),
            program=program_metadata(),
            fetched_at="2026-08-01T19:00:00+00:00",
        )

        self.assertEqual(second["outcome"], "converged")
        self.assertEqual(second["time_series_set"]["revision_number"], 1)
        revisions = self.store.list_time_series_set_revisions(
            self.project["id"], first["time_series_set"]["id"]
        )
        self.assertEqual(len(revisions), 1)

    def test_reissue_with_identical_values_still_creates_a_new_revision(self):
        first = self.ingest(program_records(), program=program_metadata())
        reissued_program = program_metadata(
            issued_at="2026-08-02T10:00:00+00:00",
            valid_until="2026-08-04T00:00:00+00:00",
        )

        second = self.ingest(
            program_records(),
            program=reissued_program,
            fetched_at="2026-08-02T11:00:00+00:00",
        )

        self.assertEqual(second["outcome"], "new_revision")
        self.assertEqual(second["time_series_set"]["revision_number"], 2)
        self.assertEqual(
            second["time_series_set"]["content_hash"],
            first["time_series_set"]["content_hash"],
        )

        revisions = self.store.list_time_series_set_revisions(
            self.project["id"], first["time_series_set"]["id"]
        )
        by_revision = {item["revision_number"]: item for item in revisions}
        self.assertIn("Program re-issued", by_revision[2]["change_summary"])
        self.assertEqual(
            by_revision[1]["program"]["valid_until"], "2026-08-03T00:00:00+00:00"
        )
        self.assertEqual(
            by_revision[2]["program"]["valid_until"], "2026-08-04T00:00:00+00:00"
        )

    def test_catalog_list_surfaces_issuer_and_validity_for_programmed_sets(self):
        ingested = self.ingest(program_records(), program=program_metadata())

        listed = self.store.list_time_series_sets(self.project["id"])

        by_id = {item["id"]: item for item in listed}
        entry = by_id[ingested["time_series_set"]["id"]]
        self.assertEqual(entry["data_kind"], "programmed")
        self.assertEqual(
            entry["program"],
            {
                "issuer": "Coordinador Electrico Nacional",
                "issued_at": "2026-08-01T10:00:00+00:00",
                "valid_from": "2026-08-02T00:00:00+00:00",
                "valid_until": "2026-08-03T00:00:00+00:00",
            },
        )

    def test_catalog_list_reports_no_program_for_non_programmed_sets(self):
        prepared = prepare_time_series_catalog_import(
            rows=program_records(),
            request=CatalogImportRequest(
                set_name="Forecast set",
                version_label="v1",
                data_kind="forecast",
                timezone="America/Santiago",
                timestamp_column="period_start",
                duration_hours_column="hours",
                signal_mappings=[
                    CatalogSignalMappingRequest(
                        source_column="demand", signal_key="load_demand_mw"
                    ),
                    CatalogSignalMappingRequest(
                        source_column="price", signal_key="import_price_usd_per_mwh"
                    ),
                ],
            ),
        )
        self.store.ingest_connector_time_series_set(
            project_id=self.project["id"],
            source=connector_source(program_records()),
            prepared_import=prepared,
            created_by="analyst@example.com",
        )

        listed = self.store.list_time_series_sets(self.project["id"])

        self.assertEqual(len(listed), 1)
        self.assertIsNone(listed[0]["program"])


def grid_battery_draft_document():
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": "grid_battery_case", "description": ""},
        "pcc": {"id": "bus_1", "type": "bus"},
        "grid": {
            "id": "grid_1",
            "import_power_max_mw": 10.0,
            "export_power_max_mw": 10.0,
            "prevent_simultaneous_grid_import_export": True,
        },
        "assets": [
            {
                "id": "battery_1",
                "type": "battery",
                "charge_power_max_mw": 4.0,
                "discharge_power_max_mw": 4.0,
                "energy_min_mwh": 0.0,
                "energy_max_mwh": 8.0,
                "initial_energy_mwh": 4.0,
                "charge_efficiency": 0.95,
                "discharge_efficiency": 0.95,
                "degradation_cost_per_mwh_delta_soc": 0.0,
                "terminal_condition": "none",
                "prevent_simultaneous_charge_discharge": True,
                "degradation_linear_delta_soc": True,
            },
        ],
        "time_series": {"sources": []},
        "solver": {"name": "HiGHS", "options": {}},
    }


def program_price_rows(*, value=50.0):
    return [
        {
            "period_start": f"2026-08-02T0{hour}:00:00",
            "hours": "1.0",
            "price": str(value + hour),
        }
        for hour in range(3)
    ]


def program_price_import_request():
    return CatalogImportRequest(
        set_name="Programa oficial de precios",
        version_label="v1",
        data_kind="programmed",
        timezone="America/Santiago",
        timestamp_column="period_start",
        duration_hours_column="hours",
        signal_mappings=[
            CatalogSignalMappingRequest(
                source_column="price", signal_key="import_price_usd_per_mwh"
            ),
        ],
    )


class ProgrammedSetRunTraceabilityTests(unittest.TestCase):
    """A run consuming a programmed set traces back to the exact program version.

    Runs record the content_hash of what they consumed (TS-3 lineage); the
    revision carrying that hash holds the issuer/validity metadata, so the
    mapping hash -> revision -> program answers "which official program did I
    use" even after reissues.
    """

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.project = self.store.create_project(name="TS6-007 variant project")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS6-007 variant scenario"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=grid_battery_draft_document()
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])

        self.first = self._ingest(program_price_rows(), program=program_metadata())
        self.programmed_set = self.first["time_series_set"]
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.programmed_set["id"],
        )

    def _ingest(self, rows, *, program, **source_kwargs):
        prepared = prepare_time_series_catalog_import(
            rows=rows, request=program_price_import_request()
        )
        return self.store.ingest_connector_time_series_set(
            project_id=self.project["id"],
            source=connector_source(rows, **source_kwargs),
            prepared_import=prepared,
            program=program,
            created_by="analyst@example.com",
        )

    def _validate(self):
        detail = self.store.get_time_series_set(
            self.project["id"], self.programmed_set["id"]
        )
        return self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            range_start=detail["horizon"]["start"],
            range_end=detail["horizon"]["end"],
        )

    def _staleness(self):
        return self.store.evaluate_case_input_variant_staleness(
            scenario_id=self.scenario["id"], case_input_variant_id=self.variant["id"]
        )

    def test_consumed_hash_maps_to_the_exact_program_version_after_a_reissue(self):
        self._validate()
        consumed_hash = self.programmed_set["content_hash"]

        corrected = self._ingest(
            program_price_rows(value=60.0),
            program=program_metadata(issued_at="2026-08-01T18:00:00+00:00"),
            fetched_at="2026-08-01T19:00:00+00:00",
        )
        self.assertEqual(corrected["outcome"], "new_revision")

        revisions = self.store.list_time_series_set_revisions(
            self.project["id"], self.programmed_set["id"]
        )
        consumed = [
            revision
            for revision in revisions
            if revision["content_hash"] == consumed_hash
        ]
        self.assertEqual(len(consumed), 1)
        self.assertEqual(
            consumed[0]["program"],
            {
                "issuer": "Coordinador Electrico Nacional",
                "issued_at": "2026-08-01T10:00:00+00:00",
                "valid_from": "2026-08-02T00:00:00+00:00",
                "valid_until": "2026-08-03T00:00:00+00:00",
            },
        )

    def test_variant_staleness_behaves_like_any_other_set_after_a_reissue(self):
        self._validate()
        self.assertFalse(self._staleness()["stale"])

        self._ingest(
            program_price_rows(value=60.0),
            program=program_metadata(issued_at="2026-08-01T18:00:00+00:00"),
            fetched_at="2026-08-01T19:00:00+00:00",
        )

        staleness = self._staleness()
        self.assertTrue(staleness["stale"])
        self.assertIn(
            "time_series_set",
            [reason["dependency_type"] for reason in staleness["reasons"]],
        )


class StubForecastConnector:
    def __init__(self, payload=None, error=None):
        self._payload = payload
        self._error = error

    def fetch(self):
        if self._error is not None:
            raise self._error
        return self._payload


def stub_payload(rows, *, fetched_at="2026-08-01T12:00:00+00:00"):
    from app.forecast_connector import ForecastPayload

    return ForecastPayload(
        connector_id="official_program_api",
        target="https://programs.example.com/v1/dispatch",
        fetched_at=fetched_at,
        payload_checksum=payload_rows_checksum(rows),
        rows=rows,
    )


class ProgrammedIngestionApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from app.main import create_app
        from app.validation import ValidationResult

        class StubValidationService:
            def validate_text(self, candidate_text):
                return ValidationResult(
                    ok=True, phase="julia", message="ok", payload={"status": "ok"}
                )

        class RecordingRunQueue:
            def enqueue(self, run_id):
                pass

            def stop(self):
                pass

        self.next_connector = StubForecastConnector(stub_payload(program_records()))

        def connector_factory(config):
            return self.next_connector

        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                run_queue=RecordingRunQueue(),
                forecast_connector_factory=connector_factory,
            )
        )
        self.store = self.client.app.state.analyst_store
        self.project = self.store.create_project(name="TS6-007 API project")

    def ingest_payload(self, **overrides):
        payload = {
            "connector": {
                "connector_id": "official_program_api",
                "base_url": "https://programs.example.com/v1/dispatch",
            },
            "set_name": "Programa oficial de despacho",
            "version_label": "v1",
            "timezone": "America/Santiago",
            "timestamp_column": "period_start",
            "duration_hours_column": "hours",
            "signal_mappings": [
                {"source_column": "demand", "signal_key": "load_demand_mw"},
                {"source_column": "price", "signal_key": "import_price_usd_per_mwh"},
            ],
            "program": program_metadata(),
        }
        payload.update(overrides)
        return payload

    def ingest(self, **overrides):
        return self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/connector-ingest",
            json=self.ingest_payload(**overrides),
        )

    def test_ingesting_with_program_metadata_creates_a_programmed_set(self):
        response = self.ingest()

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["ingestion"]["outcome"], "created")
        self.assertEqual(body["ingestion"]["program"], program_metadata())
        ingested = body["time_series_set"]
        self.assertEqual(ingested["data_kind"], "programmed")
        self.assertEqual(
            ingested["revision_metadata"]["program"], program_metadata()
        )

        listing = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        )
        entries = [
            item
            for item in listing.json()["time_series_sets"]
            if item["id"] == ingested["id"]
        ]
        self.assertEqual(entries[0]["program"], program_metadata())

    def test_ingesting_without_program_metadata_stays_a_forecast_set(self):
        response = self.ingest(program=None)

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["time_series_set"]["data_kind"], "forecast")
        self.assertNotIn("program", body["ingestion"])

    def test_invalid_program_metadata_returns_400_and_writes_nothing(self):
        response = self.ingest(program=program_metadata(issued_at="not-a-date"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("ISO-8601", response.text)
        listing = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        )
        self.assertEqual(listing.json()["time_series_sets"], [])

    def test_revision_history_endpoint_exposes_program_per_revision(self):
        self.ingest()
        corrected = program_records()
        corrected[0]["demand"] = "150.0"
        self.next_connector = StubForecastConnector(
            stub_payload(corrected, fetched_at="2026-08-01T19:00:00+00:00")
        )
        second = self.ingest(
            program=program_metadata(issued_at="2026-08-01T18:00:00+00:00")
        )
        self.assertEqual(second.json()["ingestion"]["outcome"], "new_revision")
        set_id = second.json()["time_series_set"]["id"]

        response = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets/{set_id}/revisions"
        )

        self.assertEqual(response.status_code, 200)
        revisions = response.json()["time_series_set_revisions"]
        by_revision = {item["revision_number"]: item for item in revisions}
        self.assertEqual(
            by_revision[1]["program"]["issued_at"], "2026-08-01T10:00:00+00:00"
        )
        self.assertEqual(
            by_revision[2]["program"]["issued_at"], "2026-08-01T18:00:00+00:00"
        )


if __name__ == "__main__":
    unittest.main()
