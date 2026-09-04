"""TS7-020 contextual object summary contracts."""

import os
import unittest
import uuid

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import csrf_headers, login_json_with_csrf, post_json_with_csrf


PRICE_SIGNAL = {
    "series_key": "energy_price",
    "display_name": "Precio de energia",
    "semantic_type_key": "energy_price",
    "unit_key": "usd_per_mwh",
    "signal_role": "input",
    "aggregation": "mean",
}

POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class ContextualObjectSummaryApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.user = self.store.create_user(
            email="verifier@example.local",
            display_name="Verifier",
            role="analyst",
            password_hash=hash_password("verifier pass"),
        )
        login = login_json_with_csrf(
            self.client, "verifier@example.local", "verifier pass"
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Plan base"
        )
        self.variant = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        self.receipt = self._publish_price(value=70.0)
        self.association_id = self._associate_price()
        self.binding_id = self._bind_price()

    def tearDown(self):
        self.store.close()

    @property
    def object_root(self) -> str:
        return (
            f"/api/projects/{self.project['id']}/linkable-objects/"
            f"{self.object['id']}/time-series"
        )

    def _publish_price(self, *, value: float, set_id: int | None = None):
        return self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            set_id=set_id,
            name="Inputs 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[PRICE_SIGNAL],
            periods=[
                {
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                }
            ],
            values={"energy_price": [value]},
            actor=self.user["email"],
        )

    def _associate_price(self) -> int:
        request = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "associate-price",
                    "action": "add",
                    "signal_id": self.receipt["signal_ids"]["energy_price"],
                    "linkable_object_id": self.object["id"],
                    "binding_role_key": "grid_import_price",
                    "expected_absent": True,
                    "reason_code": "catalog_association_requested",
                }
            ],
        }
        prevalidation = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            request,
        ).json()
        response = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **request,
                "prevalidation_token": prevalidation["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidation["commit_etag"],
                "Idempotency-Key": "associate-price",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["operations"][0]["association_id"]

    def _bind_price(self) -> int:
        request = {
            "expected_bindings_revision": 0,
            "operations": [
                {
                    "client_operation_id": "use-price",
                    "action": "create",
                    "linkable_object_id": self.object["id"],
                    "binding_role_key": "grid_import_price",
                    "signal_id": self.receipt["signal_ids"]["energy_price"],
                    "revision": {
                        "mode": "current",
                        "revision_id": self.receipt["revision_id"],
                        "content_hash": self.receipt["content_hash"],
                    },
                    "catalog_association_id": self.association_id,
                    "reason_code": "variant_input_selected",
                }
            ],
        }
        root = (
            f"/api/scenarios/{self.scenario['id']}/case-variants/"
            f"{self.variant['id']}"
        )
        prevalidation = post_json_with_csrf(
            self.client,
            f"{root}/time-series-binding-prevalidations",
            request,
        ).json()
        response = self.client.post(
            f"{root}/time-series-binding-batches",
            json={
                **request,
                "prevalidation_token": prevalidation["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidation["commit_etag"],
                "Idempotency-Key": "use-price",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["operations"][0]["binding_id"]

    def test_summary_names_the_object_and_keeps_association_and_variant_usage_separate(self):
        response = self.client.get(self.object_root)

        self.assertEqual(response.status_code, 200, response.text)
        page = response.json()
        self.assertEqual(
            page["meta"]["object"],
            {
                "id": self.object["id"],
                "display_name": "Sistema",
                "object_kind": "global_signal_slot",
                "object_type_key": "global:system",
            },
        )
        row = page["items"][0]
        self.assertEqual(row["association"]["state"], "active_valid")
        self.assertEqual(
            row["binding_summary"],
            {
                "total_count": 1,
                "truncated": False,
                "items": [
                    {
                        "binding_id": self.binding_id,
                        "scenario_id": self.scenario["id"],
                        "scenario_name": "Plan base",
                        "variant_id": self.variant["id"],
                        "variant_name": "Default",
                        "binding_role_key": "grid_import_price",
                        "revision_id": self.receipt["revision_id"],
                        "revision_number": 1,
                        "content_hash": self.receipt["content_hash"],
                        "state": "valid_current",
                        "execution_blocked": False,
                    }
                ],
            },
        )

        self._publish_price(value=81.0, set_id=self.receipt["set_id"])
        stale_row = self.client.get(self.object_root).json()["items"][0]

        self.assertEqual(stale_row["association"]["state"], "active_valid")
        self.assertEqual(stale_row["binding_summary"]["items"][0]["state"], "stale")
        self.assertTrue(
            stale_row["binding_summary"]["items"][0]["execution_blocked"]
        )
        self.assertEqual(
            stale_row["binding_summary"]["items"][0]["revision_id"],
            self.receipt["revision_id"],
        )

    def test_each_kind_names_the_need_it_covers_without_fabricating_a_local_association(self):
        created = self.client.post(
            f"{self.object_root}/object-series",
            json={
                "object_series_key": "local_price_forecast",
                "display_name": "Precio local previsto",
                "intended_binding_role_key": "grid_export_price",
                "semantic_type_key": "energy_price",
                "unit_key": "usd_per_mwh",
                "data_class_key": "forecast",
                "timezone": "America/Santiago",
                "temporal_contract": {
                    "regularity": "regular",
                    "nominal_resolution_seconds": 3600,
                    "timestamp_convention": "period_start",
                },
                "source_expectation": {"kind": "api"},
                "metadata": {},
            },
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": "define-local-price",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)

        rows = {
            item["source_kind"]: item
            for item in self.client.get(self.object_root).json()["items"]
        }

        self.assertEqual(
            rows["catalog"]["need"],
            {
                "binding_role_key": "grid_import_price",
                "source": "catalog_association",
            },
        )
        self.assertEqual(
            rows["object_specific"]["need"],
            {
                "binding_role_key": "grid_export_price",
                "source": "object_specific_intention",
            },
        )
        self.assertIsNone(rows["object_specific"]["association"])
        self.assertEqual(
            rows["object_specific"]["binding_summary"],
            {"total_count": 0, "truncated": False, "items": []},
        )


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL contract tests",
)
class PostgresContextualObjectSummaryApiTests(ContextualObjectSummaryApiTests):
    """Run the same read contract on the production-reference engine."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        suffix = uuid.uuid4().hex[:10]
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.user = self.store.create_user(
            email=f"ts7-020-{suffix}@example.local",
            display_name="PostgreSQL Verifier",
            role="analyst",
            password_hash=hash_password("postgres verifier pass"),
        )
        login = login_json_with_csrf(
            self.client, self.user["email"], "postgres verifier pass"
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.project = self.store.create_project(name=f"Cuenca Norte {suffix}")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Plan base"
        )
        self.variant = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        self.receipt = self._publish_price(value=70.0)
        self.association_id = self._associate_price()
        self.binding_id = self._bind_price()

    def tearDown(self):
        try:
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()


if __name__ == "__main__":
    unittest.main()
