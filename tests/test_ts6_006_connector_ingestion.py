import unittest

import httpx

from app.forecast_connector import (
    ForecastConnectorError,
    HttpJsonForecastConnector,
    HttpJsonForecastConnectorConfig,
    payload_rows_checksum,
)
from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)


def forecast_records():
    return [
        {
            "period_start": "2026-08-01T00:00:00",
            "hours": "1.0",
            "demand": "120.0",
            "price": "61.5",
        },
        {
            "period_start": "2026-08-01T01:00:00",
            "hours": "1.0",
            "demand": "121.0",
            "price": "62.5",
        },
        {
            "period_start": "2026-08-01T02:00:00",
            "hours": "1.0",
            "demand": "122.0",
            "price": "63.5",
        },
    ]


def json_transport(payload, *, status_code=200, capture=None):
    def handler(request):
        if capture is not None:
            capture.append(request)
        return httpx.Response(status_code, json=payload)

    return httpx.MockTransport(handler)


class HttpJsonForecastConnectorTests(unittest.TestCase):
    def test_fetch_parses_a_json_list_payload_into_rows(self):
        connector = HttpJsonForecastConnector(
            HttpJsonForecastConnectorConfig(
                connector_id="test_forecast_api",
                base_url="https://forecasts.example.com/v1/load",
            ),
            transport=json_transport(forecast_records()),
        )

        payload = connector.fetch()

        self.assertEqual(payload.rows, forecast_records())
        self.assertEqual(payload.connector_id, "test_forecast_api")
        self.assertEqual(payload.target, "https://forecasts.example.com/v1/load")
        self.assertTrue(payload.fetched_at)
        self.assertTrue(payload.payload_checksum.startswith("sha256:"))

    def test_fetch_extracts_records_from_a_nested_path_and_sends_the_auth_token(self):
        requests = []
        connector = HttpJsonForecastConnector(
            HttpJsonForecastConnectorConfig(
                connector_id="test_forecast_api",
                base_url="https://forecasts.example.com/v1/load",
                records_path="data.records",
                auth_token="secret-token",
            ),
            transport=json_transport(
                {"data": {"records": forecast_records()}}, capture=requests
            ),
        )

        payload = connector.fetch()

        self.assertEqual(payload.rows, forecast_records())
        self.assertEqual(len(requests), 1)
        self.assertEqual(
            requests[0].headers.get("authorization"), "Bearer secret-token"
        )

    def test_fetch_rejects_a_non_200_response(self):
        connector = HttpJsonForecastConnector(
            HttpJsonForecastConnectorConfig(
                connector_id="test_forecast_api",
                base_url="https://forecasts.example.com/v1/load",
            ),
            transport=json_transport({"error": "nope"}, status_code=503),
        )

        with self.assertRaisesRegex(ForecastConnectorError, "HTTP 503"):
            connector.fetch()

    def test_fetch_rejects_a_missing_records_path(self):
        connector = HttpJsonForecastConnector(
            HttpJsonForecastConnectorConfig(
                connector_id="test_forecast_api",
                base_url="https://forecasts.example.com/v1/load",
                records_path="data.records",
            ),
            transport=json_transport({"data": {"other": []}}),
        )

        with self.assertRaisesRegex(ForecastConnectorError, "records_path"):
            connector.fetch()

    def test_fetch_rejects_a_payload_that_is_not_a_list_of_records(self):
        connector = HttpJsonForecastConnector(
            HttpJsonForecastConnectorConfig(
                connector_id="test_forecast_api",
                base_url="https://forecasts.example.com/v1/load",
            ),
            transport=json_transport({"not": "a list"}),
        )

        with self.assertRaisesRegex(ForecastConnectorError, "list of"):
            connector.fetch()

    def test_identical_rows_produce_the_same_checksum_and_changed_rows_do_not(self):
        transport_a = json_transport(forecast_records())
        changed = forecast_records()
        changed[0]["demand"] = "999.0"
        config = HttpJsonForecastConnectorConfig(
            connector_id="test_forecast_api",
            base_url="https://forecasts.example.com/v1/load",
        )

        first = HttpJsonForecastConnector(config, transport=transport_a).fetch()
        second = HttpJsonForecastConnector(config, transport=transport_a).fetch()
        third = HttpJsonForecastConnector(
            config, transport=json_transport(changed)
        ).fetch()

        self.assertEqual(first.payload_checksum, second.payload_checksum)
        self.assertNotEqual(first.payload_checksum, third.payload_checksum)


def forecast_import_request(*, set_name="External load forecast", version_label="v1"):
    return CatalogImportRequest(
        set_name=set_name,
        version_label=version_label,
        data_kind="forecast",
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


def connector_source(rows, *, connector_id="test_forecast_api", fetched_at="2026-08-01T12:00:00+00:00"):
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
            "target": "https://forecasts.example.com/v1/load",
            "fetched_at": fetched_at,
            "record_count": len(rows),
        },
    }


class ConnectorIngestionStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS6-006 project")

    def ingest(self, rows, **kwargs):
        prepared = prepare_time_series_catalog_import(
            rows=rows,
            request=forecast_import_request(),
        )
        return self.store.ingest_connector_time_series_set(
            project_id=self.project["id"],
            source=connector_source(rows, **kwargs),
            prepared_import=prepared,
            created_by="analyst@example.com",
        )

    def test_first_ingestion_creates_a_validated_forecast_set_with_connector_source(self):
        result = self.ingest(forecast_records())

        self.assertEqual(result["outcome"], "created")
        ingested = result["time_series_set"]
        self.assertEqual(ingested["data_kind"], "forecast")
        self.assertEqual(ingested["status"], "validated")
        self.assertEqual(ingested["revision_number"], 1)

        detail = self.store.get_time_series_set(self.project["id"], ingested["id"])
        self.assertEqual(detail["source"]["kind"], "connector")
        self.assertEqual(
            detail["source"]["metadata"]["connector_id"], "test_forecast_api"
        )
        self.assertEqual(
            detail["source"]["metadata"]["target"],
            "https://forecasts.example.com/v1/load",
        )
        self.assertEqual(
            detail["source"]["metadata"]["fetched_at"], "2026-08-01T12:00:00+00:00"
        )
        listed = self.store.list_time_series_sets(self.project["id"])
        self.assertIn(ingested["id"], [item["id"] for item in listed])

    def test_reingesting_unchanged_data_converges_without_a_new_revision(self):
        first = self.ingest(forecast_records())

        second = self.ingest(
            forecast_records(), fetched_at="2026-08-02T12:00:00+00:00"
        )

        self.assertEqual(second["outcome"], "converged")
        self.assertEqual(
            second["time_series_set"]["id"], first["time_series_set"]["id"]
        )
        self.assertEqual(second["time_series_set"]["revision_number"], 1)
        self.assertEqual(
            second["time_series_set"]["content_hash"],
            first["time_series_set"]["content_hash"],
        )
        revisions = self.store.list_time_series_set_revisions(
            self.project["id"], first["time_series_set"]["id"]
        )
        self.assertEqual(len(revisions), 1)

    def test_reingesting_changed_data_creates_a_new_revision_with_fetch_metadata(self):
        first = self.ingest(forecast_records())
        changed = forecast_records()
        changed[0]["demand"] = "150.0"

        second = self.ingest(changed, fetched_at="2026-08-02T12:00:00+00:00")

        self.assertEqual(second["outcome"], "new_revision")
        self.assertEqual(
            second["time_series_set"]["id"], first["time_series_set"]["id"]
        )
        self.assertEqual(second["time_series_set"]["revision_number"], 2)
        self.assertNotEqual(
            second["time_series_set"]["content_hash"],
            first["time_series_set"]["content_hash"],
        )

        detail = self.store.get_time_series_set(
            self.project["id"], second["time_series_set"]["id"]
        )
        self.assertEqual(
            detail["source"]["metadata"]["fetched_at"], "2026-08-02T12:00:00+00:00"
        )
        self.assertEqual(
            [value["value_numeric"] for value in detail["values"]][:2],
            [61.5, 150.0],
        )

        revisions = self.store.list_time_series_set_revisions(
            self.project["id"], first["time_series_set"]["id"]
        )
        self.assertEqual(len(revisions), 2)
        by_revision = {item["revision_number"]: item for item in revisions}
        self.assertEqual(
            by_revision[1]["content_hash"], first["time_series_set"]["content_hash"]
        )
        self.assertIn("Re-ingested from connector", by_revision[2]["change_summary"])

    def test_ingestion_refuses_to_take_over_a_set_created_from_a_file(self):
        rows = forecast_records()
        prepared = prepare_time_series_catalog_import(
            rows=rows, request=forecast_import_request()
        )
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS6-006 scenario"
        )
        self.store.import_time_series_catalog_set(
            scenario_id=scenario["id"],
            source={
                "id": "csv_source_1",
                "original_filename": "forecast.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test",
            },
            prepared_import=prepared,
        )

        changed = forecast_records()
        changed[0]["demand"] = "150.0"
        with self.assertRaisesRegex(ValueError, "non-connector source"):
            self.ingest(changed)

    def test_ingested_forecast_set_is_bindable_in_a_case_input_variant(self):
        ingested = self.ingest(forecast_records())["time_series_set"]
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="TS6-006 binding scenario"
        )
        case = self.store.get_or_create_case_for_scenario(scenario["id"])
        variant = self.store.get_or_create_default_input_variant(case["id"])

        binding = self.store.upsert_case_time_series_binding(
            case_input_variant_id=variant["id"],
            signal_key="load_demand_mw",
            time_series_set_id=ingested["id"],
        )

        self.assertEqual(binding["time_series_set_id"], ingested["id"])
        bindings = self.store.list_case_time_series_bindings(variant["id"])
        self.assertEqual(len(bindings), 1)

    def test_ingestion_rejects_a_source_that_is_not_a_connector(self):
        prepared = prepare_time_series_catalog_import(
            rows=forecast_records(), request=forecast_import_request()
        )
        source = connector_source(forecast_records())
        source["kind"] = "csv"

        with self.assertRaisesRegex(ValueError, "kind 'connector'"):
            self.store.ingest_connector_time_series_set(
                project_id=self.project["id"],
                source=source,
                prepared_import=prepared,
                created_by="analyst@example.com",
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
        connector_id="test_forecast_api",
        target="https://forecasts.example.com/v1/load",
        fetched_at=fetched_at,
        payload_checksum=payload_rows_checksum(rows),
        rows=rows,
    )


class ConnectorIngestionApiTests(unittest.TestCase):
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

        self.connector_configs = []
        self.next_connector = StubForecastConnector(stub_payload(forecast_records()))

        def connector_factory(config):
            self.connector_configs.append(config)
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
        self.project = self.store.create_project(name="TS6-006 API project")

    def ingest_payload(self, **overrides):
        payload = {
            "connector": {
                "connector_id": "test_forecast_api",
                "base_url": "https://forecasts.example.com/v1/load",
            },
            "set_name": "External load forecast",
            "version_label": "v1",
            "timezone": "America/Santiago",
            "timestamp_column": "period_start",
            "duration_hours_column": "hours",
            "signal_mappings": [
                {"source_column": "demand", "signal_key": "load_demand_mw"},
                {"source_column": "price", "signal_key": "import_price_usd_per_mwh"},
            ],
        }
        payload.update(overrides)
        return payload

    def test_connector_ingestion_endpoint_creates_a_forecast_set(self):
        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/connector-ingest",
            json=self.ingest_payload(),
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["ingestion"]["outcome"], "created")
        self.assertEqual(body["ingestion"]["connector_id"], "test_forecast_api")
        ingested = body["time_series_set"]
        self.assertEqual(ingested["data_kind"], "forecast")
        self.assertEqual(ingested["status"], "validated")
        self.assertEqual(ingested["source"]["kind"], "connector")

        listing = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        )
        self.assertIn(
            ingested["id"],
            [item["id"] for item in listing.json()["time_series_sets"]],
        )

    def test_reingesting_through_the_endpoint_converges(self):
        first = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/connector-ingest",
            json=self.ingest_payload(),
        )

        second = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/connector-ingest",
            json=self.ingest_payload(),
        )

        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json()["ingestion"]["outcome"], "converged")
        self.assertEqual(
            second.json()["time_series_set"]["id"],
            first.json()["time_series_set"]["id"],
        )

    def test_connector_fetch_failure_returns_a_400_without_writing(self):
        self.next_connector = StubForecastConnector(
            error=ForecastConnectorError("connector 'test_forecast_api' received HTTP 503")
        )

        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/connector-ingest",
            json=self.ingest_payload(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("HTTP 503", response.text)
        listing = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        )
        self.assertEqual(listing.json()["time_series_sets"], [])

    def test_invalid_rows_fail_ts2_validation_and_write_nothing(self):
        bad_rows = forecast_records()
        bad_rows[1]["demand"] = "-5.0"
        self.next_connector = StubForecastConnector(stub_payload(bad_rows))

        response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/connector-ingest",
            json=self.ingest_payload(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("nonnegative", response.text)
        listing = self.client.get(
            f"/api/projects/{self.project['id']}/time-series-sets"
        )
        self.assertEqual(listing.json()["time_series_sets"], [])

    def test_unknown_project_returns_404(self):
        response = self.client.post(
            "/api/projects/999999/time-series-sets/connector-ingest",
            json=self.ingest_payload(),
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
