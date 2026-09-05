"""TS7-021 preconditions the protected journey must be able to observe.

The journey never guesses a precondition it has to send. Chapter 6.8 makes
`expected_bindings_revision` mandatory on every binding batch, so the read that
opens the journey has to hand that number back before the first prevalidation.
"""

import unittest
import uuid

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import (
    csrf_headers,
    login_json_with_csrf,
    post_json_with_csrf,
)


PRICE_SIGNAL = {
    "series_key": "energy_price",
    "display_name": "Precio de energia",
    "semantic_type_key": "energy_price",
    "unit_key": "usd_per_mwh",
    "signal_role": "input",
    "aggregation": "mean",
}


class BindingRevisionObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        login = login_json_with_csrf(
            self.client, "analyst@example.local", "analyst pass"
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.project = self.store.create_project(name="Cuenca Norte")
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
                }
            ],
            values={"energy_price": [70.0]},
            actor="analyst@example.local",
        )
        self.signal_id = self.client.get("/api/time-series/catalog/inputs").json()[
            "items"
        ][0]["signal_id"]
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Plan base"
        )
        self.variant = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]
        self.root = (
            f"/api/scenarios/{self.scenario['id']}/case-variants/"
            f"{self.variant['id']}"
        )

    def tearDown(self):
        self.store.close()

    def create_request(self, expected_bindings_revision=0):
        return {
            "expected_bindings_revision": expected_bindings_revision,
            "operations": [
                {
                    "client_operation_id": "bind-grid-price",
                    "action": "create",
                    "linkable_object_id": self.object["id"],
                    "binding_role_key": "grid_import_price",
                    "signal_id": self.signal_id,
                    "revision": {
                        "mode": "current",
                        "revision_id": self.receipt["revision_id"],
                        "content_hash": self.receipt["content_hash"],
                    },
                    "catalog_association_id": None,
                    "reason_code": "variant_input_selected",
                }
            ],
        }

    def commit(self, request):
        prevalidated = post_json_with_csrf(
            self.client, f"{self.root}/time-series-binding-prevalidations", request
        )
        self.assertEqual(prevalidated.status_code, 200, prevalidated.text)
        prevalidation = prevalidated.json()
        return self.client.post(
            f"{self.root}/time-series-binding-batches",
            json={
                **request,
                "prevalidation_token": prevalidation["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidation["commit_etag"],
                "Idempotency-Key": f"bind-{uuid.uuid4().hex}",
            },
        )

    def test_the_binding_collection_states_the_revision_a_batch_must_expect(self):
        empty = self.client.get(f"{self.root}/time-series-bindings")

        self.assertEqual(empty.status_code, 200, empty.text)
        self.assertEqual(empty.json()["meta"]["bindings_revision"], 0)

        committed = self.commit(self.create_request())
        self.assertEqual(committed.status_code, 201, committed.text)

        after = self.client.get(f"{self.root}/time-series-bindings")
        self.assertEqual(after.status_code, 200, after.text)
        # The number the surface reads back is exactly the one the next batch
        # has to send, so the journey never has to guess it.
        self.assertEqual(
            after.json()["meta"]["bindings_revision"],
            committed.json()["bindings_revision"],
        )
        self.assertEqual(after.json()["items"][0]["lifecycle_revision"], 1)


if __name__ == "__main__":
    unittest.main()
