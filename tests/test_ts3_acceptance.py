import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    CatalogValueEdit,
    prepare_time_series_catalog_import,
)
from app.validation import ValidationResult


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CASE_PATH = REPO_ROOT / "data" / "cases" / "hybrid_system" / "system_case.json"


class StubValidationService:
    def validate_text(self, candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={
                "status": "ok",
                "case_name": "ts3_acceptance_case",
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
        "case": {"name": "ts3_acceptance_case", "description": ""},
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


class TS3AcceptanceTests(unittest.TestCase):
    """BESS-TS3-009: closing proof for case input variants and run lineage.

    Exercises one continuous TS-3 story: a hybrid case lazily gets a default
    variant; missing required bindings are named clearly; range coverage and
    cross-signal horizon mismatches fail before a run is created; series-edit
    staleness blocks runs until explicit revalidation; cloning a variant keeps
    bindings independent; and two runs from one case preserve distinct variant,
    range and series-hash lineage while the legacy scenario-version path stays
    intact.
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
            "/api/projects", json={"name": "TS-3 Acceptance"}
        ).json()
        self.scenario = self.client.post(
            f"/api/projects/{self.project['id']}/scenarios",
            json={"name": "Variant workflow"},
        ).json()
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=hybrid_draft_document()
        )
        self._source_counter = 0
        start = datetime(2026, 1, 1)
        self.price_set = self._import_signal_set(
            set_name="Spot A",
            signal_key="price_usd_per_mwh",
            rows=timed_rows(start, [1.0, 1.0, 1.0, 1.0], value=50.0),
        )
        self.load_set = self._import_signal_set(
            set_name="Load base",
            signal_key="load_demand_mw",
            rows=timed_rows(start, [1.0, 1.0, 1.0, 1.0], value=12.0),
        )
        self.renewable_set = self._import_signal_set(
            set_name="Solar hourly",
            signal_key="renewable_available_power_mw",
            rows=timed_rows(start, [1.0, 1.0, 1.0, 1.0], value=3.0),
        )
        self.renewable_mismatch_set = self._import_signal_set(
            set_name="Solar 2h",
            signal_key="renewable_available_power_mw",
            rows=timed_rows(start, [2.0, 2.0], value=3.0),
        )
        self.stress_price_set = self._import_signal_set(
            set_name="Spot B",
            signal_key="price_usd_per_mwh",
            rows=timed_rows(start, [1.0, 1.0, 1.0, 1.0], value=500.0),
        )
        self.range_start = self.price_set["horizon"]["start"]
        self.range_end = self.price_set["horizon"]["end"]

    def _import_signal_set(self, *, set_name, signal_key, rows):
        self._source_counter += 1
        source_suffix = self._source_counter
        return self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": f"csv_source_{source_suffix}",
                "original_filename": f"{set_name.lower().replace(' ', '_')}.csv",
                "media_type": "text/csv",
                "checksum": f"sha256:test-{source_suffix}",
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

    def _variant_run(self, variant_id, *, range_start=None, range_end=None):
        return self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/run",
            json={
                "range_start": range_start or self.range_start,
                "range_end": range_end or self.range_end,
            },
        )

    def _variant_validate(self, variant_id):
        return self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/validate",
            json={"range_start": self.range_start, "range_end": self.range_end},
        )

    def test_case_variant_story_end_to_end(self):
        variant_body = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()
        variant_id = variant_body["variant"]["id"]
        self.assertTrue(variant_body["variant"]["is_default"])
        self.assertEqual(
            {(item["entity_type"], item["entity_id"], item["signal_key"]) for item in variant_body["required_signals"]},
            {
                ("grid", "grid_1", "price_usd_per_mwh"),
                ("component:load", "load_1", "load_demand_mw"),
                ("component:renewable", "solar_1", "renewable_available_power_mw"),
            },
        )

        # Missing bindings surface every required family clearly.
        self._bind(
            variant_id,
            signal_key="price_usd_per_mwh",
            time_series_set_id=self.price_set["id"],
        )
        missing_binding_response = self._variant_run(variant_id)
        self.assertEqual(missing_binding_response.status_code, 400)
        self.assertIn("load_demand_mw", missing_binding_response.text)
        self.assertIn("renewable_available_power_mw", missing_binding_response.text)

        # Mixed horizons fail before any run is created.
        self._bind(
            variant_id,
            signal_key="load_demand_mw",
            entity_type="component:load",
            entity_id="load_1",
            time_series_set_id=self.load_set["id"],
        )
        self._bind(
            variant_id,
            signal_key="renewable_available_power_mw",
            entity_type="component:renewable",
            entity_id="solar_1",
            time_series_set_id=self.renewable_mismatch_set["id"],
        )
        horizon_response = self._variant_run(variant_id)
        self.assertEqual(horizon_response.status_code, 400)
        self.assertIn("horizon incompatible", horizon_response.text)
        self.assertIn("renewable_available_power_mw", horizon_response.text)
        self.assertIn("no implicit resampling", horizon_response.text)

        # Exact-range coverage is enforced too.
        self._bind(
            variant_id,
            signal_key="renewable_available_power_mw",
            entity_type="component:renewable",
            entity_id="solar_1",
            time_series_set_id=self.renewable_set["id"],
        )
        coverage_end = (
            datetime.fromisoformat(self.range_end) + timedelta(hours=1)
        ).isoformat()
        coverage_response = self._variant_run(
            variant_id, range_start=self.range_start, range_end=coverage_end
        )
        self.assertEqual(coverage_response.status_code, 400)
        self.assertIn("missing coverage", coverage_response.text)
        self.assertIn("time-series set", coverage_response.text)

        # A clean validation stamps dependencies and keeps the variant runnable.
        validate_response = self._variant_validate(variant_id)
        self.assertEqual(validate_response.status_code, 200, validate_response.text)
        self.assertEqual(validate_response.json()["status"], "valid")
        fresh_variant = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()
        self.assertTrue(fresh_variant["staleness"]["validated"])
        self.assertFalse(fresh_variant["staleness"]["stale"])

        # Editing a bound set makes the variant stale until revalidated.
        self.store.edit_time_series_set_values(
            project_id=self.project["id"],
            time_series_set_id=self.price_set["id"],
            edits=[
                CatalogValueEdit(
                    period_index=0,
                    signal_key="price_usd_per_mwh",
                    value_text="999.0",
                )
            ],
        )
        stale_variant = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()
        self.assertTrue(stale_variant["staleness"]["stale"])
        self.assertEqual(
            [reason["dependency_type"] for reason in stale_variant["staleness"]["reasons"]],
            ["time_series_set"],
        )
        stale_run_response = self._variant_run(variant_id)
        self.assertEqual(stale_run_response.status_code, 400)
        self.assertIn("stale", stale_run_response.text.lower())

        revalidate_response = self._variant_validate(variant_id)
        self.assertEqual(revalidate_response.status_code, 200, revalidate_response.text)
        self.assertFalse(
            self.client.get(f"/api/scenarios/{self.scenario['id']}/case/default-variant").json()[
                "staleness"
            ]["stale"]
        )

        default_run_response = self._variant_run(variant_id)
        self.assertEqual(default_run_response.status_code, 201, default_run_response.text)
        default_run = default_run_response.json()
        default_version = self.client.get(
            f"/api/scenario-versions/{default_run['scenario_version_id']}"
        ).json()["scenario_version"]
        default_metadata = default_version["generation_metadata"]
        self.assertEqual(default_metadata["kind"], "case_input_variant")
        self.assertEqual(
            default_metadata["input_variant"],
            {"id": variant_id, "display_name": "Default"},
        )
        self.assertEqual(
            default_metadata["date_range"],
            {"start": self.range_start, "end": self.range_end},
        )
        default_series_by_key = {
            binding["signal_key"]: binding for binding in default_metadata["series_bindings"]
        }
        self.assertEqual(
            set(default_series_by_key),
            {"price_usd_per_mwh", "load_demand_mw", "renewable_available_power_mw"},
        )

        # Cloning preserves bindings by reference, then the clone can diverge.
        clone_response = self.client.post(
            f"/api/scenarios/{self.scenario['id']}/case/variants/{variant_id}/clone",
            json={"display_name": "Stress prices"},
        )
        self.assertEqual(clone_response.status_code, 201, clone_response.text)
        clone = clone_response.json()
        variant_list = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/variants"
        ).json()
        self.assertEqual(variant_list["default_variant_id"], variant_id)
        self.assertEqual(
            [entry["variant"]["display_name"] for entry in variant_list["variants"]],
            ["Default", "Stress prices"],
        )
        self.assertEqual(
            {
                binding["signal_key"]: binding["time_series_set_id"]
                for binding in variant_list["variants"][1]["bindings"]
            },
            {
                "price_usd_per_mwh": self.price_set["id"],
                "load_demand_mw": self.load_set["id"],
                "renewable_available_power_mw": self.renewable_set["id"],
            },
        )

        self._bind(
            clone["id"],
            signal_key="price_usd_per_mwh",
            time_series_set_id=self.stress_price_set["id"],
        )
        stress_run_response = self._variant_run(clone["id"])
        self.assertEqual(stress_run_response.status_code, 201, stress_run_response.text)
        stress_run = stress_run_response.json()
        stress_version = self.client.get(
            f"/api/scenario-versions/{stress_run['scenario_version_id']}"
        ).json()["scenario_version"]
        stress_metadata = stress_version["generation_metadata"]
        self.assertEqual(
            stress_metadata["input_variant"],
            {"id": clone["id"], "display_name": "Stress prices"},
        )
        self.assertEqual(
            stress_metadata["date_range"],
            {"start": self.range_start, "end": self.range_end},
        )

        stress_series_by_key = {
            binding["signal_key"]: binding for binding in stress_metadata["series_bindings"]
        }
        self.assertNotEqual(default_run["scenario_version_id"], stress_run["scenario_version_id"])
        self.assertNotEqual(default_version["system_case_json"], stress_version["system_case_json"])
        self.assertNotEqual(
            default_series_by_key["price_usd_per_mwh"]["content_hash"],
            stress_series_by_key["price_usd_per_mwh"]["content_hash"],
        )
        self.assertEqual(
            default_series_by_key["load_demand_mw"]["content_hash"],
            stress_series_by_key["load_demand_mw"]["content_hash"],
        )
        self.assertEqual(
            default_series_by_key["renewable_available_power_mw"]["content_hash"],
            stress_series_by_key["renewable_available_power_mw"]["content_hash"],
        )

        run_list = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/runs"
        ).json()["runs"]
        self.assertEqual(
            {run["id"] for run in run_list},
            {default_run["id"], stress_run["id"]},
        )
        self.assertEqual(
            self.run_queue.enqueued_run_ids,
            [default_run["id"], stress_run["id"]],
        )

        # Legacy scenario-version creation and manual runs remain available.
        legacy_project = self.client.post(
            "/api/projects", json={"name": "TS-3 Legacy Boundary"}
        ).json()
        legacy_scenario = self.client.post(
            f"/api/projects/{legacy_project['id']}/scenarios",
            json={"name": "Legacy scenario"},
        ).json()
        legacy_version = self.client.post(
            f"/api/scenarios/{legacy_scenario['id']}/versions",
            json={"system_case_json": SAMPLE_CASE_PATH.read_text(encoding="utf-8")},
        ).json()
        legacy_run_response = self.client.post(
            f"/api/scenario-versions/{legacy_version['id']}/runs"
        )
        self.assertEqual(legacy_run_response.status_code, 201, legacy_run_response.text)
        legacy_version_detail = self.client.get(
            f"/api/scenario-versions/{legacy_version['id']}"
        ).json()["scenario_version"]
        self.assertNotIn("input_variant", legacy_version_detail["generation_metadata"])

    def test_ts3_documentation_tracker_and_issue_are_done(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        issue = (
            REPO_ROOT
            / "docs"
            / "series_tiempo"
            / "iter3"
            / "issues"
            / "BESS-TS3-009-finalize-ts3-acceptance-suite-and-docs.md"
        ).read_text(encoding="utf-8")
        tracker = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter3" / "issues" / "tracker_ts3.md"
        ).read_text(encoding="utf-8")
        manual = (
            REPO_ROOT / "docs" / "series_tiempo" / "iter3" / "pruebas_manuales_ts3.md"
        ).read_text(encoding="utf-8")

        self.assertIn("TS-3: Input Variants, Date Range And Run Lineage", readme)
        self.assertIn("tests.test_ts3_acceptance", readme)

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_ts3_acceptance", issue)

        self.assertIn(
            "| BESS-TS3-009 | Finalize TS-3 Acceptance Suite And Docs | AFK | ready-for-agent | Done |",
            tracker,
        )
        self.assertIn("BESS-TS3-009 | Todo -> Done", tracker)
        self.assertIn("Final TS-3 Verification", tracker)
        self.assertIn("tests.test_ts3_acceptance", tracker)

        self.assertIn("Cierre TS-3", manual)
        self.assertIn("tests.test_ts3_acceptance", manual)


if __name__ == "__main__":
    unittest.main()
