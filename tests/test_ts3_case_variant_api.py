import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app
from app.time_series_catalog import CatalogImportRequest, CatalogSignalMappingRequest, prepare_time_series_catalog_import
from app.validation import ValidationResult


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


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={"status": "ok", "case_name": "grid_battery_case", "schema_version": "bess_system_dispatch.v1"},
        )


class RecordingRunQueue:
    def __init__(self):
        self.enqueued_run_ids = []

    def enqueue(self, run_id):
        self.enqueued_run_ids.append(run_id)

    def stop(self):
        pass


class CaseInputVariantApiTests(unittest.TestCase):
    def setUp(self):
        self.validation_service = StubValidationService()
        self.run_queue = RecordingRunQueue()
        self.client = TestClient(
            create_app(
                validation_service=self.validation_service,
                database_url="sqlite:///:memory:",
                run_queue=self.run_queue,
            )
        )
        self.store = self.client.app.state.analyst_store
        project = self.store.create_project(name="TS-3 project")
        self.scenario = self.store.create_scenario(project_id=project["id"], name="TS-3 scenario")
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=grid_battery_draft_document()
        )
        prepared = prepare_time_series_catalog_import(
            rows=self._price_rows(datetime(2026, 1, 1), 3),
            request=CatalogImportRequest(
                set_name="Spot price",
                version_label="v1",
                data_kind="real",
                timezone="America/Santiago",
                timestamp_column="period_start",
                duration_hours_column="hours",
                signal_mappings=[
                    CatalogSignalMappingRequest(source_column="spot_price", signal_key="import_price_usd_per_mwh"),
                ],
            ),
        )
        self.price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "csv_source_1",
                "original_filename": "price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:test",
            },
            prepared_import=prepared,
        )

    @staticmethod
    def _price_rows(start, count, *, value=50.0):
        rows = []
        for hour in range(count):
            instant = start + timedelta(hours=hour)
            rows.append(
                {
                    "period_start": instant.isoformat(),
                    "hours": "1.0",
                    "spot_price": str(value + hour),
                }
            )
        return rows

    def test_get_default_variant_creates_it_lazily(self):
        response = self.client.get(f"/api/scenarios/{self.scenario['id']}/case/default-variant")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["variant"]["is_default"])
        self.assertEqual(body["bindings"], [])

    def test_bind_price_signal_then_run_launches_a_run(self):
        variant_id = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]["id"]

        bind_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/bindings",
            json={"signal_key": "import_price_usd_per_mwh", "time_series_set_id": self.price_set["id"]},
        )
        self.assertEqual(bind_response.status_code, 201)

        run_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/run",
            json={
                "range_start": self.price_set["horizon"]["start"],
                "range_end": self.price_set["horizon"]["end"],
            },
        )

        self.assertEqual(run_response.status_code, 201)
        run = run_response.json()
        self.assertEqual(run["status"], "queued")
        self.assertEqual(self.run_queue.enqueued_run_ids, [run["id"]])

    def test_run_with_range_not_covered_returns_400(self):
        variant_id = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]["id"]
        self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/bindings",
            json={"signal_key": "import_price_usd_per_mwh", "time_series_set_id": self.price_set["id"]},
        )

        run_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/run",
            json={"range_start": self.price_set["horizon"]["start"], "range_end": "2026-01-02T00:00:00-03:00"},
        )

        self.assertEqual(run_response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
