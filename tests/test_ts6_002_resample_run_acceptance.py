import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)
from app.validation import ValidationResult


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={
                "status": "ok",
                "case_name": "ts6_002_resample_case",
                "schema_version": "bess_system_dispatch.v2",
            },
        )


class RecordingRunQueue:
    def __init__(self):
        self.enqueued_run_ids = []

    def enqueue(self, run_id):
        self.enqueued_run_ids.append(run_id)

    def stop(self):
        pass


def hybrid_draft_document():
    return {
        "schema_version": "bess_editor_draft.v1",
        "case": {"name": "ts6_002_resample_case", "description": ""},
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
            {"id": "load_1", "type": "load"},
            {"id": "solar_1", "type": "renewable", "resource_type": "solar"},
        ],
        "time_series": {"sources": []},
        "solver": {"name": "HiGHS", "options": {}},
    }


def timed_rows(start, durations, *, value=50.0, value_column="value"):
    rows = []
    cursor = start
    for index, duration in enumerate(durations):
        rows.append(
            {
                "period_start": cursor.isoformat(),
                "hours": str(duration),
                value_column: str(value + index),
            }
        )
        cursor += timedelta(hours=duration)
    return rows


class ResampleRunAcceptanceTests(unittest.TestCase):
    """BESS-TS6-002: resample, bind, run closes the loop end-to-end.

    A load series is imported hourly (mismatched against the 2-hour model
    resolution used by the other two bound signals), resampled to 2 hours via
    the allowlisted `resample` transformation, then bound in the case's
    default variant alongside natively 2-hour price/renewable series. The run
    pipeline never resamples implicitly - only the explicit derived set makes
    the horizons compatible - and the run completes end-to-end.
    """

    def setUp(self):
        self.run_queue = RecordingRunQueue()
        self.client = TestClient(
            create_app(
                validation_service=StubValidationService(),
                database_url="sqlite:///:memory:",
                run_queue=self.run_queue,
            )
        )
        self.store = self.client.app.state.analyst_store
        self.project = self.client.post(
            "/api/projects", json={"name": "TS-6-002 Resample Acceptance"}
        ).json()
        self.scenario = self.client.post(
            f"/api/projects/{self.project['id']}/scenarios",
            json={"name": "Resample workflow"},
        ).json()
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=hybrid_draft_document()
        )
        start = datetime(2026, 2, 1)

        self.price_set = self._import_signal_set(
            set_name="Spot 2h",
            signal_key="price_usd_per_mwh",
            rows=timed_rows(start, [2.0, 2.0], value=50.0),
        )
        self.renewable_set = self._import_signal_set(
            set_name="Solar 2h",
            signal_key="renewable_available_power_mw",
            rows=timed_rows(start, [2.0, 2.0], value=3.0),
        )
        self.load_hourly_set = self._import_signal_set(
            set_name="Load hourly",
            signal_key="load_demand_mw",
            rows=timed_rows(start, [1.0, 1.0, 1.0, 1.0], value=10.0),
        )
        self.range_start = self.price_set["horizon"]["start"]
        self.range_end = self.price_set["horizon"]["end"]

    def _import_signal_set(self, *, set_name, signal_key, rows):
        return self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": f"csv_source_{set_name.lower().replace(' ', '_')}",
                "original_filename": f"{set_name.lower().replace(' ', '_')}.csv",
                "media_type": "text/csv",
                "checksum": f"sha256:test-{set_name}",
            },
            prepared_import=prepare_time_series_catalog_import(
                rows=rows,
                request=CatalogImportRequest(
                    set_name=set_name,
                    version_label="v1",
                    data_kind="real",
                    timezone="America/Santiago",
                    timestamp_column="period_start",
                    duration_hours_column="hours",
                    signal_mappings=[
                        CatalogSignalMappingRequest(
                            source_column="value", signal_key=signal_key
                        )
                    ],
                ),
            ),
        )

    def _bind(self, variant_id, *, signal_key, time_series_set_id, entity_type=None, entity_id=None):
        response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/bindings",
            json={
                "signal_key": signal_key,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "time_series_set_id": time_series_set_id,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _variant_run(self, variant_id):
        return self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/run",
            json={"range_start": self.range_start, "range_end": self.range_end},
        )

    def test_run_fails_on_mismatched_resolution_then_succeeds_after_resampling(self):
        variant_body = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()
        variant_id = variant_body["variant"]["id"]

        self._bind(
            variant_id,
            signal_key="price_usd_per_mwh",
            time_series_set_id=self.price_set["id"],
        )
        self._bind(
            variant_id,
            signal_key="renewable_available_power_mw",
            entity_type="component:renewable",
            entity_id="solar_1",
            time_series_set_id=self.renewable_set["id"],
        )
        self._bind(
            variant_id,
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_1",
            time_series_set_id=self.load_hourly_set["id"],
        )

        # The run pipeline never resamples implicitly: binding the raw hourly
        # load series against a 2-hour model horizon fails clearly.
        mismatched_response = self._variant_run(variant_id)
        self.assertEqual(mismatched_response.status_code, 400)
        self.assertIn("horizon incompatible", mismatched_response.text)
        self.assertIn("no implicit resampling", mismatched_response.text)

        # The analyst resolves this by resampling explicitly first.
        resample_response = self.client.post(
            f"/api/projects/{self.project['id']}/time-series-sets/"
            f"{self.load_hourly_set['id']}/transformations",
            json={
                "transformation_type": "resample",
                "parameters": {
                    "target_resolution_hours": 2.0,
                    "signal_methods": {"load_demand_mw": "mean"},
                },
            },
        )
        self.assertEqual(resample_response.status_code, 201, resample_response.text)
        resampled_set = resample_response.json()["time_series_set"]
        self.assertEqual(resampled_set["data_kind"], "derived")
        self.assertEqual(len(resampled_set["periods"]), 2)

        # Bind the resampled derived set in the same slot and run again.
        self._bind(
            variant_id,
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_1",
            time_series_set_id=resampled_set["id"],
        )

        success_response = self._variant_run(variant_id)
        self.assertEqual(success_response.status_code, 201, success_response.text)
        run = success_response.json()
        scenario_version = self.client.get(
            f"/api/scenario-versions/{run['scenario_version_id']}"
        ).json()["scenario_version"]
        series_bindings = {
            binding["signal_key"]: binding
            for binding in scenario_version["generation_metadata"]["series_bindings"]
        }
        self.assertEqual(
            series_bindings["load_demand_mw"]["time_series_set_id"],
            resampled_set["id"],
        )


if __name__ == "__main__":
    unittest.main()
