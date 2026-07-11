import unittest
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.schedules import (
    due_fixed_range_schedules,
    execute_fixed_range_schedule,
    next_fixed_range_fire_time,
    resolve_schedule_range,
)
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)
from app.validation import ValidationResult
from tests.auth_test_helpers import login_json_with_csrf, post_json_with_csrf
from tests.test_ts3_case_variant_api import grid_battery_draft_document
from tests.test_ts3_input_variants import price_rows


class AcceptingValidationService:
    def validate_text(self, _candidate_text):
        return ValidationResult(
            ok=True,
            phase="julia",
            message="ok",
            payload={"status": "ok"},
        )


class CapturingRunQueue:
    def __init__(self):
        self.enqueued_run_ids = []

    def enqueue(self, run_id):
        self.enqueued_run_ids.append(run_id)


def price_import_request():
    return CatalogImportRequest(
        set_name="Schedule price",
        version_label="v1",
        data_kind="real",
        timezone="America/Santiago",
        timestamp_column="period_start",
        duration_hours_column="hours",
        signal_mappings=[
            CatalogSignalMappingRequest(
                source_column="spot_price", signal_key="import_price_usd_per_mwh"
            ),
        ],
    )


class SchedulePlanningTests(unittest.TestCase):
    def test_daily_schedule_due_at_or_before_now_with_fixed_range(self):
        schedules = [
            {
                "id": 1,
                "is_active": True,
                "next_run_at": "2026-08-06T09:00:00+00:00",
                "range_start": "2026-08-01T00:00:00-04:00",
                "range_end": "2026-08-02T00:00:00-04:00",
                "cadence": "daily",
            },
            {
                "id": 2,
                "is_active": True,
                "next_run_at": "2026-08-06T11:00:00+00:00",
                "range_start": "2026-08-01T00:00:00-04:00",
                "range_end": "2026-08-02T00:00:00-04:00",
                "cadence": "daily",
            },
            {
                "id": 3,
                "is_active": False,
                "next_run_at": "2026-08-06T08:00:00+00:00",
                "range_start": "2026-08-01T00:00:00-04:00",
                "range_end": "2026-08-02T00:00:00-04:00",
                "cadence": "daily",
            },
        ]

        due = due_fixed_range_schedules(
            schedules, now="2026-08-06T10:00:00+00:00"
        )

        self.assertEqual([schedule["id"] for schedule in due], [1])

    def test_next_fire_time_advances_from_due_time_not_wall_clock(self):
        self.assertEqual(
            next_fixed_range_fire_time(
                cadence="daily",
                due_at="2026-08-06T09:00:00+00:00",
                now="2026-08-08T10:00:00+00:00",
            ),
            "2026-08-09T09:00:00+00:00",
        )

    def test_rolling_schedule_range_resolves_from_due_time(self):
        schedule = {
            "id": 4,
            "range_mode": "rolling",
            "rolling_start_offset_hours": 0.0,
            "rolling_duration_hours": 168.0,
            "range_start": "2026-08-01T00:00:00-04:00",
            "range_end": "2026-08-08T00:00:00-04:00",
        }

        resolved = resolve_schedule_range(
            schedule=schedule, due_at="2026-08-11T09:00:00+00:00"
        )

        self.assertEqual(
            resolved,
            {
                "start": "2026-08-11T09:00:00+00:00",
                "end": "2026-08-18T09:00:00+00:00",
            },
        )


class RunSchedulePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS6-008")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Scheduled scenario"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"],
            document=grid_battery_draft_document(),
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])

    def test_create_fixed_range_schedule_records_case_variant_parameter_hash_and_cadence(self):
        schedule = self.store.create_run_schedule(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            display_name="Daily default rerun",
            range_start="2026-08-01T00:00:00-04:00",
            range_end="2026-08-02T00:00:00-04:00",
            cadence="daily",
            next_run_at="2026-08-06T09:00:00+00:00",
            created_by="scheduler-admin@example.com",
        )

        self.assertEqual(schedule["scenario_id"], self.scenario["id"])
        self.assertEqual(schedule["case_id"], self.case["id"])
        self.assertEqual(schedule["case_input_variant_id"], self.variant["id"])
        self.assertEqual(schedule["cadence"], "daily")
        self.assertEqual(schedule["range_start"], "2026-08-01T00:00:00-04:00")
        self.assertEqual(schedule["range_end"], "2026-08-02T00:00:00-04:00")
        self.assertTrue(schedule["parameter_hash"].startswith("sha256:"))
        self.assertTrue(schedule["topology_hash"].startswith("sha256:"))
        self.assertEqual(schedule["created_by"], "scheduler-admin@example.com")
        self.assertNotIn("system_case_json", schedule)

        [listed] = self.store.list_run_schedules()
        self.assertEqual(listed["id"], schedule["id"])

    def test_create_rolling_schedule_records_range_rule(self):
        schedule = self.store.create_run_schedule(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            display_name="Seven day rolling rerun",
            range_start="2026-08-01T00:00:00-04:00",
            range_end="2026-08-08T00:00:00-04:00",
            cadence="daily",
            next_run_at="2026-08-11T09:00:00+00:00",
            range_mode="rolling",
            rolling_start_offset_hours=0,
            rolling_duration_hours=168,
            created_by="scheduler-admin@example.com",
        )

        self.assertEqual(schedule["range_mode"], "rolling")
        self.assertEqual(schedule["rolling_start_offset_hours"], 0.0)
        self.assertEqual(schedule["rolling_duration_hours"], 168.0)
        self.assertNotIn("system_case_json", schedule)

        [listed] = self.store.list_run_schedules()
        self.assertEqual(listed["range_mode"], "rolling")
        self.assertEqual(listed["rolling_duration_hours"], 168.0)


class FixedRangeScheduleExecutionTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.project = self.store.create_project(name="TS6-008")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Scheduled scenario"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"],
            document=grid_battery_draft_document(),
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        prepared = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 8, 1), 24),
            request=price_import_request(),
        )
        self.price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "schedule-price-source",
                "original_filename": "prices.csv",
                "media_type": "text/csv",
                "checksum": "sha256:schedule-price",
            },
            prepared_import=prepared,
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.price_set["id"],
        )
        self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            range_start=self.price_set["horizon"]["start"],
            range_end=self.price_set["horizon"]["end"],
        )

    def test_execute_schedule_creates_snapshot_run_tick_and_advances_next_fire_time(self):
        schedule = self.store.create_run_schedule(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            display_name="Daily default rerun",
            range_start=self.price_set["horizon"]["start"],
            range_end=self.price_set["horizon"]["end"],
            cadence="daily",
            next_run_at="2026-08-06T09:00:00+00:00",
            created_by="scheduler-admin@example.com",
        )
        queue = CapturingRunQueue()

        tick = execute_fixed_range_schedule(
            store=self.store,
            validation_service=AcceptingValidationService(),
            run_queue=queue,
            schedule=schedule,
            now="2026-08-06T10:00:00+00:00",
            triggered_by="scheduler-admin@example.com",
        )

        self.assertEqual(tick["status"], "queued")
        self.assertEqual(tick["schedule_id"], schedule["id"])
        self.assertEqual(tick["range_start"], self.price_set["horizon"]["start"])
        self.assertEqual(tick["range_end"], self.price_set["horizon"]["end"])
        self.assertEqual(queue.enqueued_run_ids, [tick["run_id"]])

        run = self.store.get_run(tick["run_id"])
        self.assertEqual(run["trigger_type"], "scheduled")
        self.assertEqual(run["triggered_by"], "scheduler-admin@example.com")
        listed_runs = self.store.list_scenario_runs(self.scenario["id"])
        self.assertEqual([listed["id"] for listed in listed_runs], [run["id"]])
        self.assertEqual(listed_runs[0]["trigger_type"], "scheduled")
        version = self.store.get_scenario_version(run["scenario_version_id"])
        metadata = version["generation_metadata"]
        self.assertEqual(metadata["kind"], "case_input_variant")
        self.assertEqual(
            metadata["automation"],
            {
                "schedule_id": schedule["id"],
                "schedule_tick_id": tick["id"],
                "schedule_name": "Daily default rerun",
                "due_at": "2026-08-06T09:00:00+00:00",
                "fired_at": "2026-08-06T10:00:00+00:00",
            },
        )
        self.assertEqual(metadata["date_range"]["start"], self.price_set["horizon"]["start"])
        self.assertEqual(metadata["input_variant"]["display_name"], "Default")

        advanced = self.store.get_run_schedule(schedule["id"])
        self.assertEqual(advanced["next_run_at"], "2026-08-07T09:00:00+00:00")
        self.assertEqual(advanced["last_fired_at"], "2026-08-06T10:00:00+00:00")

    def test_execute_schedule_records_gate_failure_without_creating_run(self):
        schedule = self.store.create_run_schedule(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            display_name="Out of range rerun",
            range_start="2026-09-01T00:00:00-04:00",
            range_end="2026-09-02T00:00:00-04:00",
            cadence="daily",
            next_run_at="2026-08-06T09:00:00+00:00",
            created_by="scheduler-admin@example.com",
        )
        queue = CapturingRunQueue()

        tick = execute_fixed_range_schedule(
            store=self.store,
            validation_service=AcceptingValidationService(),
            run_queue=queue,
            schedule=schedule,
            now="2026-08-06T10:00:00+00:00",
            triggered_by="scheduler-admin@example.com",
        )

        self.assertEqual(tick["status"], "failed")
        self.assertIsNone(tick["run_id"])
        self.assertIn("missing coverage", tick["error_message"])
        self.assertEqual(queue.enqueued_run_ids, [])
        advanced = self.store.get_run_schedule(schedule["id"])
        self.assertTrue(advanced["is_active"])
        self.assertEqual(advanced["next_run_at"], "2026-08-07T09:00:00+00:00")

    def test_rolling_schedule_recomputes_range_for_each_tick(self):
        schedule = self.store.create_run_schedule(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            display_name="Rolling daily rerun",
            range_start="2020-01-01T00:00:00+00:00",
            range_end="2020-01-02T00:00:00+00:00",
            cadence="daily",
            next_run_at=self.price_set["horizon"]["start"],
            range_mode="rolling",
            rolling_start_offset_hours=0,
            rolling_duration_hours=24,
            created_by="scheduler-admin@example.com",
        )
        queue = CapturingRunQueue()

        first_tick = execute_fixed_range_schedule(
            store=self.store,
            validation_service=AcceptingValidationService(),
            run_queue=queue,
            schedule=schedule,
            now="2026-08-01T01:00:00-04:00",
            triggered_by="scheduler-admin@example.com",
        )
        second_schedule = self.store.get_run_schedule(schedule["id"])
        second_tick = execute_fixed_range_schedule(
            store=self.store,
            validation_service=AcceptingValidationService(),
            run_queue=queue,
            schedule=second_schedule,
            now="2026-08-02T01:00:00-04:00",
            triggered_by="scheduler-admin@example.com",
        )

        self.assertEqual(first_tick["status"], "queued")
        self.assertEqual(second_tick["status"], "failed")
        self.assertIsNone(second_tick["run_id"])
        self.assertEqual(second_tick["range_start"], "2026-08-02T00:00:00-04:00")
        self.assertEqual(second_tick["range_end"], "2026-08-03T00:00:00-04:00")
        self.assertIn("missing coverage", second_tick["error_message"])
        self.assertEqual(queue.enqueued_run_ids, [first_tick["run_id"]])
        advanced = self.store.get_run_schedule(schedule["id"])
        self.assertTrue(advanced["is_active"])
        self.assertEqual(advanced["next_run_at"], "2026-08-03T00:00:00-04:00")


class ScheduleApiTests(unittest.TestCase):
    def setUp(self):
        self.run_queue = CapturingRunQueue()
        self.client = TestClient(
            create_app(
                validation_service=AcceptingValidationService(),
                database_url="sqlite:///:memory:",
                run_queue=self.run_queue,
            )
        )
        self.store = self.client.app.state.analyst_store
        self.project = self.store.create_project(name="TS6-008 API")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Scheduled API scenario"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=grid_battery_draft_document()
        )
        self.case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(self.case["id"])
        prepared = prepare_time_series_catalog_import(
            rows=price_rows(datetime(2026, 8, 1), 24),
            request=price_import_request(),
        )
        self.price_set = self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "api-schedule-price-source",
                "original_filename": "prices.csv",
                "media_type": "text/csv",
                "checksum": "sha256:api-schedule-price",
            },
            prepared_import=prepared,
        )
        self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.price_set["id"],
        )
        self.store.validate_case_input_variant(
            scenario_id=self.scenario["id"],
            case_input_variant_id=self.variant["id"],
            range_start=self.price_set["horizon"]["start"],
            range_end=self.price_set["horizon"]["end"],
        )

    def test_admin_api_creates_lists_and_runs_due_schedules(self):
        create_response = self.client.post(
            "/api/admin/schedules",
            json={
                "scenario_id": self.scenario["id"],
                "case_input_variant_id": self.variant["id"],
                "display_name": "Daily API schedule",
                "range_start": self.price_set["horizon"]["start"],
                "range_end": self.price_set["horizon"]["end"],
                "cadence": "daily",
                "next_run_at": "2026-08-06T09:00:00+00:00",
            },
        )

        self.assertEqual(create_response.status_code, 201, create_response.text)
        schedule = create_response.json()["schedule"]
        self.assertEqual(schedule["display_name"], "Daily API schedule")

        list_response = self.client.get("/api/admin/schedules")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            [listed["id"] for listed in list_response.json()["schedules"]],
            [schedule["id"]],
        )

        run_due_response = self.client.post(
            "/api/admin/schedules/run-due",
            json={"now": "2026-08-06T10:00:00+00:00"},
        )

        self.assertEqual(run_due_response.status_code, 200, run_due_response.text)
        [tick] = run_due_response.json()["ticks"]
        self.assertEqual(tick["schedule_id"], schedule["id"])
        self.assertEqual(tick["status"], "queued")
        self.assertEqual(self.run_queue.enqueued_run_ids, [tick["run_id"]])

    def test_admin_api_creates_rolling_schedule(self):
        create_response = self.client.post(
            "/api/admin/schedules",
            json={
                "scenario_id": self.scenario["id"],
                "case_input_variant_id": self.variant["id"],
                "display_name": "Rolling API schedule",
                "range_start": "2020-01-01T00:00:00+00:00",
                "range_end": "2020-01-02T00:00:00+00:00",
                "cadence": "daily",
                "next_run_at": self.price_set["horizon"]["start"],
                "range_mode": "rolling",
                "rolling_start_offset_hours": 0,
                "rolling_duration_hours": 24,
            },
        )

        self.assertEqual(create_response.status_code, 201, create_response.text)
        schedule = create_response.json()["schedule"]
        self.assertEqual(schedule["range_mode"], "rolling")
        self.assertEqual(schedule["range_start"], self.price_set["horizon"]["start"])
        self.assertEqual(schedule["range_end"], self.price_set["horizon"]["end"])
        self.assertEqual(schedule["rolling_duration_hours"], 24.0)


class SchedulePermissionApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
            created_by="test",
        )
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        login = login_json_with_csrf(
            self.client, "analyst@example.local", "analyst pass"
        )
        self.assertEqual(login.status_code, 200)

    def test_schedule_management_is_admin_only(self):
        response = post_json_with_csrf(
            self.client,
            "/api/admin/schedules",
            {
                "scenario_id": 1,
                "case_input_variant_id": 1,
                "display_name": "Forbidden",
                "range_start": "2026-08-01T00:00:00-04:00",
                "range_end": "2026-08-02T00:00:00-04:00",
                "cadence": "daily",
                "next_run_at": "2026-08-06T09:00:00+00:00",
            },
        )

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
