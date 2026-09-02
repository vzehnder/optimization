"""TS7-009 canonical binding materialization into immutable run snapshots."""

import json
import os
import sqlite3
import unittest
import uuid

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.validation import ValidationResult
from tests.auth_test_helpers import csrf_headers, login_json_with_csrf
from tests.test_ts3_case_variant_api import grid_battery_draft_document


PRICE_SIGNAL = {
    "series_key": "energy_price",
    "display_name": "Precio de energia",
    "semantic_type_key": "energy_price",
    "unit_key": "usd_per_mwh",
    "signal_role": "input",
    "aggregation": "mean",
}

POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class AcceptingValidationService:
    def validate_text(self, candidate_text):
        json.loads(candidate_text)
        return ValidationResult(
            ok=True,
            phase="julia",
            message="Validation succeeded",
            payload={
                "status": "ok",
                "case_name": "grid_battery_case",
                "schema_version": "bess_system_dispatch.v1",
            },
        )


class RecordingRunQueue:
    def __init__(self):
        self.enqueued_run_ids = []

    def enqueue(self, run_id):
        self.enqueued_run_ids.append(run_id)

    def stop(self):
        pass


class CanonicalRunMaterializationApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self._set_up_fixture()

    def _set_up_fixture(self, suffix=""):
        self.queue = RecordingRunQueue()
        self.client = TestClient(
            create_app(
                store=self.store,
                auth_enabled=True,
                validation_service=AcceptingValidationService(),
                run_queue=self.queue,
            )
        )
        self.user = self.store.create_user(
            email=f"analyst{suffix}@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        login = login_json_with_csrf(
            self.client, self.user["email"], "analyst pass"
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.project = self.store.create_project(name=f"Cuenca Norte {suffix}".strip())
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Plan base"
        )
        self.store.create_or_replace_scenario_draft(
            scenario_id=self.scenario["id"], document=grid_battery_draft_document()
        )
        self.variant = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]
        self.receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Inputs 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[PRICE_SIGNAL],
            periods=[
                {
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                },
                {
                    "timestamp_start": "2026-01-01T01:00:00",
                    "timestamp_end": "2026-01-01T02:00:00",
                    "duration_hours": 1.0,
                },
            ],
            values={"energy_price": [70.0, 72.0]},
            actor=self.user["email"],
        )
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        self.binding_ids = self._bind_prices()

    def tearDown(self):
        self.store.close()

    @property
    def canonical_root(self):
        return (
            f"/api/scenarios/{self.scenario['id']}/case-variants/"
            f"{self.variant['id']}"
        )

    @property
    def run_path(self):
        return (
            f"/api/scenarios/{self.scenario['id']}/case/variants/"
            f"{self.variant['id']}/run"
        )

    def _bind_prices(self):
        operations = []
        for role in ("grid_import_price", "grid_export_price"):
            operations.append(
                {
                    "client_operation_id": f"bind-{role}",
                    "action": "create",
                    "linkable_object_id": self.object["id"],
                    "binding_role_key": role,
                    "signal_id": self.receipt["signal_ids"]["energy_price"],
                    "revision": {
                        "mode": "current",
                        "revision_id": self.receipt["revision_id"],
                        "content_hash": self.receipt["content_hash"],
                    },
                    "catalog_association_id": None,
                    "reason_code": "variant_input_selected",
                }
            )
        request = {"expected_bindings_revision": 0, "operations": operations}
        prevalidated = self.client.post(
            f"{self.canonical_root}/time-series-binding-prevalidations",
            json=request,
            headers=csrf_headers(self.client),
        )
        self.assertEqual(prevalidated.status_code, 200, prevalidated.text)
        committed = self.client.post(
            f"{self.canonical_root}/time-series-binding-batches",
            json={
                **request,
                "prevalidation_token": prevalidated.json()["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidated.json()["commit_etag"],
                "Idempotency-Key": "bind-both-prices",
                "X-Request-Id": "req-bind-both-prices",
            },
        )
        self.assertEqual(committed.status_code, 201, committed.text)
        return [item["binding_id"] for item in committed.json()["operations"]]

    def _run(self, *, request_id="req-materialize-prices"):
        return self.client.post(
            self.run_path,
            json={
                "range_start": "2026-01-01T00:00:00",
                "range_end": "2026-01-01T02:00:00",
            },
            headers={
                **csrf_headers(self.client),
                "X-Request-Id": request_id,
            },
        )

    def test_run_uses_exact_bound_revision_and_reuses_identical_snapshot(self):
        first_response = self._run()

        self.assertEqual(first_response.status_code, 201, first_response.text)
        first_run = first_response.json()
        self.assertIsNone(
            self.store.get_run_dispatch_result_index(first_run["id"]),
            "input materialization must not create or merge a TS-4 result index",
        )
        version = self.store.get_scenario_version(
            first_run["scenario_version_id"], include_document=True
        )
        self.assertEqual(
            version["system_case_json"]["time_series"],
            [
                {
                    "timestamp": "2026-01-01T00:00:00",
                    "duration_hours": 1.0,
                    "import_price_usd_per_mwh": 70.0,
                    "export_price_usd_per_mwh": 70.0,
                },
                {
                    "timestamp": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                    "import_price_usd_per_mwh": 72.0,
                    "export_price_usd_per_mwh": 72.0,
                },
            ],
        )
        metadata = version["generation_metadata"]
        self.assertEqual(metadata["kind"], "case_input_variant")
        self.assertEqual(metadata["bindings_revision"], 1)
        self.assertEqual(metadata["request_id"], "req-materialize-prices")
        self.assertEqual(metadata["actor"]["email"], self.user["email"])
        self.assertTrue(metadata["topology"]["content_hash"])
        self.assertTrue(metadata["parameters"]["content_hash"])
        self.assertEqual(
            {item["binding_id"] for item in metadata["series_bindings"]},
            set(self.binding_ids),
        )
        for item in metadata["series_bindings"]:
            self.assertEqual(item["set_revision_id"], self.receipt["revision_id"])
            self.assertEqual(item["content_hash"], self.receipt["content_hash"])
            self.assertEqual(item["source_kind"], "catalog")
            self.assertEqual(item["owner_project_id"], self.project["id"])
            self.assertEqual(item["revision_mode"], "current")
            self.assertEqual(item["state"], "valid_current")
            self.assertTrue(item["compatibility_fingerprint"])
            self.assertTrue(item["validation_fingerprint"])

        replay_response = self._run(request_id="req-materialize-prices-retry")

        self.assertEqual(replay_response.status_code, 201, replay_response.text)
        replay_run = replay_response.json()
        self.assertNotEqual(replay_run["id"], first_run["id"])
        self.assertEqual(
            replay_run["scenario_version_id"], first_run["scenario_version_id"]
        )
        self.assertEqual(
            self.queue.enqueued_run_ids, [first_run["id"], replay_run["id"]]
        )

    def test_materialization_recomputes_the_pinned_hash_and_refuses_corrupt_values(self):
        # Simulate storage corruption below the normal sealed-revision guard.
        # The run path must hash what it actually reads, not trust the pointer.
        self.store.connection.execute("DROP TRIGGER ts_next_values_sealed_update")
        self.store.connection.execute(
            """
            UPDATE time_series_values_next
            SET value_numeric = 999.0
            WHERE set_revision_id = ?
            """,
            (self.receipt["revision_id"],),
        )
        self.store.connection.commit()

        response = self._run()

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(
            response.json()["error"]["code"], "TS_BINDING_EXECUTION_BLOCKED"
        )
        [detail] = response.json()["error"]["details"]
        self.assertEqual(detail["state"], "invalid")
        self.assertEqual(detail["reason"], "content_hash_mismatch")
        self.assertEqual(
            self.client.get(
                f"/api/scenarios/{self.scenario['id']}/versions"
            ).json()["versions"],
            [],
        )
        self.assertEqual(
            self.client.get(
                f"/api/scenarios/{self.scenario['id']}/runs"
            ).json()["runs"],
            [],
        )
        self.assertEqual(self.queue.enqueued_run_ids, [])

    def test_failed_run_insert_rolls_back_the_new_scenario_version(self):
        self.store.connection.execute(
            """
            CREATE TRIGGER reject_ts7_run_insert
            BEFORE INSERT ON runs
            BEGIN
                SELECT RAISE(ABORT, 'simulated interrupted materialization');
            END
            """
        )
        self.store.connection.commit()

        with self.assertRaisesRegex(
            sqlite3.IntegrityError, "simulated interrupted materialization"
        ):
            self.store.materialize_run_from_canonical_bindings(
                scenario_id=self.scenario["id"],
                variant_id=self.variant["id"],
                range_start="2026-01-01T00:00:00",
                range_end="2026-01-01T02:00:00",
                validate_text=AcceptingValidationService().validate_text,
                actor_user=self.user,
                request_id="req-interrupted-materialization",
            )

        self.assertEqual(self.store.list_scenario_versions(self.scenario["id"]), [])
        self.assertEqual(self.store.list_scenario_runs(self.scenario["id"]), [])

    def test_an_explicitly_revalidated_pin_executes_the_old_revision(self):
        current = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            set_id=self.receipt["set_id"],
            name="Inputs 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[PRICE_SIGNAL],
            periods=[
                {
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                },
                {
                    "timestamp_start": "2026-01-01T01:00:00",
                    "timestamp_end": "2026-01-01T02:00:00",
                    "duration_hours": 1.0,
                },
            ],
            values={"energy_price": [90.0, 91.0]},
            actor=self.user["email"],
        )
        request = {
            "expected_bindings_revision": 1,
            "operations": [
                {
                    "client_operation_id": f"pin-{binding_id}",
                    "action": "revalidate_pinned",
                    "binding_id": binding_id,
                    "expected_lifecycle_revision": 1,
                    "reason_code": "historical_revision_accepted",
                    "reason_text": "Approved the prior revision for this run.",
                }
                for binding_id in self.binding_ids
            ],
        }
        prevalidated = self.client.post(
            f"{self.canonical_root}/time-series-binding-prevalidations",
            json=request,
            headers=csrf_headers(self.client),
        )
        self.assertEqual(prevalidated.status_code, 200, prevalidated.text)
        self.assertTrue(prevalidated.json()["can_commit"])
        committed = self.client.post(
            f"{self.canonical_root}/time-series-binding-batches",
            json={
                **request,
                "prevalidation_token": prevalidated.json()["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidated.json()["commit_etag"],
                "Idempotency-Key": "keep-old-price-revision",
                "X-Request-Id": "req-keep-old-price-revision",
            },
        )
        self.assertEqual(committed.status_code, 201, committed.text)

        response = self._run()

        self.assertEqual(response.status_code, 201, response.text)
        version = self.store.get_scenario_version(
            response.json()["scenario_version_id"], include_document=True
        )
        self.assertEqual(
            [row["import_price_usd_per_mwh"] for row in version["system_case_json"]["time_series"]],
            [70.0, 72.0],
        )
        self.assertNotEqual(self.receipt["revision_id"], current["revision_id"])
        for item in version["generation_metadata"]["series_bindings"]:
            self.assertEqual(item["set_revision_id"], self.receipt["revision_id"])
            self.assertEqual(item["revision_mode"], "pinned")
            self.assertEqual(item["state"], "valid_pinned")
            self.assertEqual(
                item["observed_current_revision_id"], current["revision_id"]
            )
            self.assertEqual(
                item["pin_reason"], "Approved the prior revision for this run."
            )


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL contract tests",
)
class PostgresCanonicalRunMaterializationApiTests(
    CanonicalRunMaterializationApiTests
):
    """Run the public materialization contract on the production-reference DB."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        suffix = f"-{uuid.uuid4().hex[:10]}"
        self._set_up_fixture(suffix)

    def tearDown(self):
        try:
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()

    @unittest.skip("SQLite-only storage corruption fixture")
    def test_materialization_recomputes_the_pinned_hash_and_refuses_corrupt_values(self):
        pass

    @unittest.skip("SQLite-only interrupted insert fixture")
    def test_failed_run_insert_rolls_back_the_new_scenario_version(self):
        pass


if __name__ == "__main__":
    unittest.main()
