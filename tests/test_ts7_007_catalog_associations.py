"""TS7-007 atomic, audited catalog-association HTTP contract."""

import os
import time
import unittest
import uuid
from unittest.mock import patch

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

POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class CatalogAssociationApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.user = self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        login = login_json_with_csrf(
            self.client, "analyst@example.local", "analyst pass"
        )
        self.assertEqual(login.status_code, 200)
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
        self.signal_id = self.client.get(
            "/api/time-series/catalog/inputs"
        ).json()["items"][0]["signal_id"]
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )

    def tearDown(self):
        self.store.close()

    def add_request(self, *, client_operation_id: str = "op-add-price") -> dict:
        return {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": client_operation_id,
                    "action": "add",
                    "signal_id": self.signal_id,
                    "linkable_object_id": self.object["id"],
                    "binding_role_key": "grid_import_price",
                    "expected_absent": True,
                    "reason_code": "catalog_association_requested",
                }
            ],
        }

    def prevalidate(self, request: dict) -> dict:
        response = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            request,
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def commit(
        self,
        request: dict,
        prevalidation: dict,
        *,
        idempotency_key: str,
        confirmed: bool = True,
        request_id: str = "req-association-batch",
    ):
        return self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **request,
                "prevalidation_token": prevalidation["prevalidation_token"],
                "confirmed": confirmed,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidation["commit_etag"],
                "Idempotency-Key": idempotency_key,
                "X-Request-Id": request_id,
            },
        )

    def test_prevalidation_is_repeatable_and_leaves_the_public_history_empty(self):
        request = self.add_request()

        with patch("app.time_series_associations.time.time", return_value=1_000_000):
            first = post_json_with_csrf(
                self.client,
                "/api/time-series/catalog/association-prevalidations",
                request,
            )
            second = post_json_with_csrf(
                self.client,
                "/api/time-series/catalog/association-prevalidations",
                request,
            )

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        payload = first.json()
        repeated_payload = second.json()
        payload.pop("request_id")
        repeated_payload.pop("request_id")
        self.assertEqual(payload, repeated_payload)
        self.assertEqual(payload["normalized_request"], request)
        self.assertTrue(payload["can_commit"])
        self.assertFalse(payload["requires_confirmation"])
        self.assertEqual(payload["operations"][0]["verdict"], "accepted")
        self.assertTrue(payload["operations"][0]["compatibility_decision"]["allowed"])
        self.assertTrue(payload["prevalidation_token"])
        self.assertTrue(payload["commit_etag"].startswith('"'))

        associations = self.client.get("/api/time-series/catalog/associations")
        self.assertEqual(associations.status_code, 200, associations.text)
        self.assertEqual(associations.json()["items"], [])

    def test_confirmed_add_is_atomic_readable_and_audited(self):
        request = self.add_request()
        prevalidation = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            request,
        )
        self.assertEqual(prevalidation.status_code, 200, prevalidation.text)
        observed = prevalidation.json()
        headers = {
            **csrf_headers(self.client),
            "If-Match": observed["commit_etag"],
            "Idempotency-Key": "assoc-add-price-1",
            "X-Request-Id": "req-assoc-add-price",
        }

        committed = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **request,
                "prevalidation_token": observed["prevalidation_token"],
                "confirmed": True,
            },
            headers=headers,
        )

        self.assertEqual(committed.status_code, 201, committed.text)
        result = committed.json()
        self.assertEqual(result["outcome"], "created")
        self.assertEqual(result["request_id"], "req-assoc-add-price")
        self.assertTrue(result["batch_id"])
        association_id = result["operations"][0]["association_id"]

        collection = self.client.get(
            "/api/time-series/catalog/associations"
        ).json()
        self.assertEqual(collection["summary"], {"total_count": 1})
        self.assertEqual(collection["items"][0]["association_id"], association_id)
        self.assertEqual(collection["items"][0]["signal_id"], self.signal_id)
        self.assertEqual(collection["items"][0]["object"]["id"], self.object["id"])
        self.assertEqual(
            collection["items"][0]["binding_role"]["key"],
            "grid_import_price",
        )
        self.assertEqual(collection["items"][0]["state"], "active_valid")

        detail = self.client.get(
            f"/api/time-series/catalog/associations/{association_id}"
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertTrue(detail.headers["etag"].startswith('"'))
        self.assertEqual(detail.json()["lifecycle_revision"], 1)

        events = self.client.get(
            f"/api/time-series/catalog/associations/{association_id}/events"
        )
        self.assertEqual(events.status_code, 200, events.text)
        self.assertEqual(events.json()["page"]["has_more"], False)
        event = events.json()["items"][0]
        self.assertEqual(event["event_type"], "created")
        self.assertEqual(event["batch_id"], result["batch_id"])
        self.assertEqual(event["actor"]["user_id"], self.user["id"])
        self.assertEqual(event["actor"]["identity"], "analyst@example.local")
        self.assertEqual(event["actor"]["role"], "analyst")
        self.assertEqual(event["reason"]["code"], "catalog_association_requested")
        self.assertEqual(event["request_id"], "req-assoc-add-price")
        self.assertTrue(event["occurred_at"])

        catalog_item = self.client.get(
            "/api/time-series/catalog/inputs"
        ).json()["items"][0]
        self.assertEqual(catalog_item["link_summary"]["association_count"], 1)

    def test_one_incompatible_row_rejects_the_whole_batch_without_partial_success(self):
        incompatible_object = self.store.ensure_project_component(
            project_id=self.project["id"],
            component_key="load_a",
            component_type="load",
            display_name="Load A",
        )
        request = self.add_request()
        request["operations"].append(
            {
                "client_operation_id": "op-incompatible-load",
                "action": "add",
                "signal_id": self.signal_id,
                "linkable_object_id": incompatible_object["id"],
                "binding_role_key": "grid_import_price",
                "expected_absent": True,
                "reason_code": "catalog_association_requested",
            }
        )
        prevalidation = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            request,
        )

        self.assertEqual(prevalidation.status_code, 200, prevalidation.text)
        observed = prevalidation.json()
        self.assertFalse(observed["can_commit"])
        self.assertEqual(
            [row["verdict"] for row in observed["operations"]],
            ["accepted", "rejected"],
        )
        self.assertEqual(
            observed["operations"][1]["errors"][0]["code"],
            "TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED",
        )

        committed = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **request,
                "prevalidation_token": observed["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": observed["commit_etag"],
                "Idempotency-Key": "assoc-mixed-1",
            },
        )

        self.assertEqual(committed.status_code, 422, committed.text)
        self.assertEqual(committed.json()["error"]["code"], "TS_LINK_BATCH_REJECTED")
        self.assertEqual(
            committed.json()["error"]["context"]["normalized_request"], request
        )
        self.assertEqual(
            [row["client_operation_id"] for row in committed.json()["error"]["details"]],
            ["op-add-price", "op-incompatible-load"],
        )
        self.assertEqual(
            self.client.get("/api/time-series/catalog/associations").json()["items"],
            [],
        )
        catalog_item = self.client.get(
            "/api/time-series/catalog/inputs"
        ).json()["items"][0]
        self.assertEqual(catalog_item["link_summary"]["association_count"], 0)

    def test_replace_archives_the_observed_row_and_inserts_a_superseding_identity(self):
        created = self.commit(
            self.add_request(),
            self.prevalidate(self.add_request()),
            idempotency_key="assoc-create-before-replace",
        )
        self.assertEqual(created.status_code, 201, created.text)
        previous_id = created.json()["operations"][0]["association_id"]

        alternative_signal = {
            **PRICE_SIGNAL,
            "series_key": "energy_price_alternative",
            "display_name": "Precio de energia alternativo",
        }
        self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Alternative inputs",
            data_class_key="real",
            timezone="UTC",
            signals=[alternative_signal],
            periods=[
                {
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                }
            ],
            values={"energy_price_alternative": [75.0]},
            actor="analyst@example.local",
        )
        alternative_id = next(
            item["signal_id"]
            for item in self.client.get(
                "/api/time-series/catalog/inputs"
            ).json()["items"]
            if item["identity"]["series_key"] == "energy_price_alternative"
        )
        request = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "op-replace-price",
                    "action": "replace",
                    "association_id": previous_id,
                    "expected_lifecycle_revision": 1,
                    "signal_id": alternative_id,
                    "linkable_object_id": self.object["id"],
                    "binding_role_key": "grid_import_price",
                    "reason_code": "better_source",
                    "reason_text": "Use the curated alternative.",
                }
            ],
        }

        prevalidation = self.prevalidate(request)

        self.assertTrue(prevalidation["can_commit"])
        self.assertTrue(prevalidation["requires_confirmation"])
        self.assertEqual(
            prevalidation["operations"][0]["verdict"], "confirmation_required"
        )
        refused = self.commit(
            request,
            prevalidation,
            idempotency_key="assoc-replace-unconfirmed",
            confirmed=False,
        )
        self.assertEqual(refused.status_code, 409, refused.text)
        self.assertEqual(
            refused.json()["error"]["code"], "TS_LINK_CONFIRMATION_REQUIRED"
        )

        replaced = self.commit(
            request,
            prevalidation,
            idempotency_key="assoc-replace-confirmed",
            request_id="req-assoc-replace",
        )

        self.assertEqual(replaced.status_code, 201, replaced.text)
        new_id = replaced.json()["operations"][0]["association_id"]
        previous = self.client.get(
            f"/api/time-series/catalog/associations/{previous_id}"
        ).json()
        current = self.client.get(
            f"/api/time-series/catalog/associations/{new_id}"
        ).json()
        self.assertEqual(previous["state"], "archived")
        self.assertEqual(previous["lifecycle_revision"], 2)
        self.assertEqual(current["state"], "active_valid")
        self.assertEqual(current["supersedes_association_id"], previous_id)
        self.assertEqual(current["signal_id"], alternative_id)
        previous_event = self.client.get(
            f"/api/time-series/catalog/associations/{previous_id}/events"
        ).json()["items"][-1]
        current_event = self.client.get(
            f"/api/time-series/catalog/associations/{new_id}/events"
        ).json()["items"][-1]
        self.assertEqual(previous_event["event_type"], "superseded")
        self.assertEqual(current_event["event_type"], "replaced")
        self.assertEqual(previous_event["batch_id"], current_event["batch_id"])
        self.assertEqual(current_event["reason"]["code"], "better_source")

    def test_revalidate_appends_evidence_and_archive_is_confirmed_and_terminal(self):
        created = self.commit(
            self.add_request(),
            self.prevalidate(self.add_request()),
            idempotency_key="assoc-create-before-lifecycle",
        )
        self.assertEqual(created.status_code, 201, created.text)
        association_id = created.json()["operations"][0]["association_id"]
        revalidate_request = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "op-revalidate-price",
                    "action": "revalidate",
                    "association_id": association_id,
                    "expected_lifecycle_revision": 1,
                    "reason_code": "contract_rechecked",
                }
            ],
        }
        revalidation = self.prevalidate(revalidate_request)
        self.assertEqual(revalidation["operations"][0]["verdict"], "accepted")
        revalidated = self.commit(
            revalidate_request,
            revalidation,
            idempotency_key="assoc-revalidate-1",
        )

        self.assertEqual(revalidated.status_code, 201, revalidated.text)
        detail_after_revalidation = self.client.get(
            f"/api/time-series/catalog/associations/{association_id}"
        ).json()
        self.assertEqual(detail_after_revalidation["lifecycle_revision"], 1)
        event_types = [
            item["event_type"]
            for item in self.client.get(
                f"/api/time-series/catalog/associations/{association_id}/events"
            ).json()["items"]
        ]
        self.assertEqual(event_types, ["created", "revalidated_current"])

        archive_request = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "op-archive-price",
                    "action": "archive",
                    "association_id": association_id,
                    "expected_lifecycle_revision": 1,
                    "reason_code": "source_retired",
                    "reason_text": "The source is no longer offered.",
                }
            ],
        }
        archival = self.prevalidate(archive_request)
        self.assertTrue(archival["requires_confirmation"])
        self.assertEqual(
            archival["operations"][0]["verdict"], "confirmation_required"
        )
        archived = self.commit(
            archive_request,
            archival,
            idempotency_key="assoc-archive-1",
        )

        self.assertEqual(archived.status_code, 201, archived.text)
        archived_detail = self.client.get(
            f"/api/time-series/catalog/associations/{association_id}"
        ).json()
        self.assertEqual(archived_detail["state"], "archived")
        self.assertEqual(archived_detail["lifecycle_revision"], 2)
        self.assertEqual(
            archived_detail["archive_reason"],
            {"code": "source_retired", "text": "The source is no longer offered."},
        )
        event_types = [
            item["event_type"]
            for item in self.client.get(
                f"/api/time-series/catalog/associations/{association_id}/events"
            ).json()["items"]
        ]
        self.assertEqual(
            event_types, ["created", "revalidated_current", "archived"]
        )
        catalog_item = self.client.get(
            "/api/time-series/catalog/inputs"
        ).json()["items"][0]
        self.assertEqual(catalog_item["link_summary"]["association_count"], 0)
        self.assertEqual(
            self.client.delete(
                f"/api/time-series/catalog/associations/{association_id}",
                headers=csrf_headers(self.client),
            ).status_code,
            405,
        )

    def test_scope_is_reauthorized_at_commit_after_a_passing_prevalidation(self):
        other_project = self.store.create_project(name="Cuenca Sur")
        other_object = self.store.ensure_global_signal_slot(
            project_id=other_project["id"], display_name="Sistema Sur"
        )
        canonical_sets = self.store.canonical_table_names()["time_series_sets"]
        entries = self.store.catalog_projection_table_names()[
            "time_series_catalog_entries"
        ]
        with self.store.connection:
            self.store.connection.execute(
                f"""
                UPDATE {canonical_sets}
                SET visibility_scope = 'global', scope_revision = scope_revision + 1
                WHERE id = ?
                """,
                (self.receipt["set_id"],),
            )
            self.store.connection.execute(
                f"""
                UPDATE {entries}
                SET visibility_scope = 'global', projection_revision = projection_revision + 1
                WHERE signal_id = ?
                """,
                (self.signal_id,),
            )
        request = {
            "target_project_id": other_project["id"],
            "operations": [
                {
                    "client_operation_id": "op-cross-project-global",
                    "action": "add",
                    "signal_id": self.signal_id,
                    "linkable_object_id": other_object["id"],
                    "binding_role_key": "grid_import_price",
                    "expected_absent": True,
                    "reason_code": "global_source_selected",
                }
            ],
        }
        prevalidation = self.prevalidate(request)
        self.assertTrue(prevalidation["can_commit"])

        with self.store.connection:
            self.store.connection.execute(
                f"""
                UPDATE {canonical_sets}
                SET visibility_scope = 'project', scope_revision = scope_revision + 1
                WHERE id = ?
                """,
                (self.receipt["set_id"],),
            )
            self.store.connection.execute(
                f"""
                UPDATE {entries}
                SET visibility_scope = 'project', projection_revision = projection_revision + 1
                WHERE signal_id = ?
                """,
                (self.signal_id,),
            )

        committed = self.commit(
            request,
            prevalidation,
            idempotency_key="assoc-cross-project-after-demotion",
        )

        self.assertEqual(committed.status_code, 412, committed.text)
        self.assertEqual(
            committed.json()["error"]["code"], "TS_COMPAT_SCOPE_NOT_ACCESSIBLE"
        )
        self.assertEqual(
            self.client.get("/api/time-series/catalog/associations").json()["items"],
            [],
        )

    def test_idempotent_replay_outlives_the_token_but_a_new_commit_does_not(self):
        request = self.add_request()
        with patch("app.time_series_associations.time.time", return_value=1_000_000):
            prevalidation = self.prevalidate(request)
            first = self.commit(
                request,
                prevalidation,
                idempotency_key="assoc-durable-replay",
                request_id="req-original-association",
            )
        self.assertEqual(first.status_code, 201, first.text)

        with patch("app.time_series_associations.time.time", return_value=1_001_000):
            replay = self.commit(
                request,
                prevalidation,
                idempotency_key="assoc-durable-replay",
                request_id="req-retried-association",
            )
            expired_new_attempt = self.commit(
                request,
                prevalidation,
                idempotency_key="assoc-expired-new-attempt",
            )

        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(expired_new_attempt.status_code, 410, expired_new_attempt.text)
        self.assertEqual(
            expired_new_attempt.json()["error"]["code"],
            "TS_LINK_PREVALIDATION_EXPIRED",
        )
        association_id = first.json()["operations"][0]["association_id"]
        events = self.client.get(
            f"/api/time-series/catalog/associations/{association_id}/events"
        ).json()["items"]
        self.assertEqual([event["event_type"] for event in events], ["created"])

    def test_associations_and_events_page_with_independent_signed_cursors(self):
        request = self.add_request()
        request["operations"].append(
            {
                **request["operations"][0],
                "client_operation_id": "op-add-export-price",
                "binding_role_key": "grid_export_price",
            }
        )
        created = self.commit(
            request,
            self.prevalidate(request),
            idempotency_key="assoc-two-roles",
        )
        self.assertEqual(created.status_code, 201, created.text)
        association_ids = [
            operation["association_id"] for operation in created.json()["operations"]
        ]
        first_page = self.client.get(
            "/api/time-series/catalog/associations", params={"limit": 1}
        )
        self.assertEqual(first_page.status_code, 200, first_page.text)
        self.assertTrue(first_page.json()["page"]["has_more"])
        association_cursor = first_page.json()["page"]["next_cursor"]
        second_page = self.client.get(
            "/api/time-series/catalog/associations",
            params={"limit": 1, "cursor": association_cursor},
        )
        self.assertEqual(second_page.status_code, 200, second_page.text)
        self.assertEqual(
            [
                first_page.json()["items"][0]["association_id"],
                second_page.json()["items"][0]["association_id"],
            ],
            association_ids,
        )

        association_id = association_ids[0]
        revalidate_request = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "op-page-revalidation",
                    "action": "revalidate",
                    "association_id": association_id,
                    "expected_lifecycle_revision": 1,
                    "reason_code": "contract_rechecked",
                }
            ],
        }
        revalidated = self.commit(
            revalidate_request,
            self.prevalidate(revalidate_request),
            idempotency_key="assoc-page-revalidation",
        )
        self.assertEqual(revalidated.status_code, 201, revalidated.text)
        event_path = (
            f"/api/time-series/catalog/associations/{association_id}/events"
        )
        first_events = self.client.get(event_path, params={"limit": 1})
        self.assertEqual(first_events.status_code, 200, first_events.text)
        self.assertTrue(first_events.json()["page"]["has_more"])
        second_events = self.client.get(
            event_path,
            params={
                "limit": 1,
                "cursor": first_events.json()["page"]["next_cursor"],
            },
        )
        self.assertEqual(second_events.status_code, 200, second_events.text)
        self.assertEqual(
            [
                first_events.json()["items"][0]["event_type"],
                second_events.json()["items"][0]["event_type"],
            ],
            ["created", "revalidated_current"],
        )
        mismatched = self.client.get(
            event_path, params={"limit": 1, "cursor": association_cursor}
        )
        self.assertEqual(mismatched.status_code, 400, mismatched.text)
        self.assertEqual(
            mismatched.json()["error"]["code"], "TS_QUERY_CURSOR_MISMATCH"
        )

    def test_a_full_200_operation_batch_commits_all_rows_together(self):
        signals = [
            {
                **PRICE_SIGNAL,
                "series_key": f"bulk_price_{index:03d}",
                "display_name": f"Bulk price {index:03d}",
            }
            for index in range(200)
        ]
        self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Bulk inputs",
            data_class_key="real",
            timezone="UTC",
            signals=signals,
            periods=[
                {
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                }
            ],
            values={signal["series_key"]: [70.0] for signal in signals},
            actor="analyst@example.local",
        )
        first_page = self.client.get(
            "/api/time-series/catalog/inputs", params={"limit": 200}
        ).json()
        catalog_items = list(first_page["items"])
        if first_page["page"]["has_more"]:
            catalog_items.extend(
                self.client.get(
                    "/api/time-series/catalog/inputs",
                    params={
                        "limit": 200,
                        "cursor": first_page["page"]["next_cursor"],
                    },
                ).json()["items"]
            )
        signal_ids = {
            item["identity"]["series_key"]: item["signal_id"]
            for item in catalog_items
        }
        request = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": f"op-bulk-{index:03d}",
                    "action": "add",
                    "signal_id": signal_ids[f"bulk_price_{index:03d}"],
                    "linkable_object_id": self.object["id"],
                    "binding_role_key": "grid_import_price",
                    "expected_absent": True,
                    "reason_code": "bulk_catalog_selection",
                }
                for index in range(200)
            ],
        }

        prevalidation = self.prevalidate(request)
        self.assertTrue(prevalidation["can_commit"])
        self.assertEqual(len(prevalidation["operations"]), 200)
        committed = self.commit(
            request,
            prevalidation,
            idempotency_key="assoc-full-200",
            request_id="req-assoc-full-200",
        )

        self.assertEqual(committed.status_code, 201, committed.text)
        self.assertEqual(len(committed.json()["operations"]), 200)
        self.assertTrue(
            all(
                operation["outcome"] == "created"
                for operation in committed.json()["operations"]
            )
        )
        associations = self.client.get(
            "/api/time-series/catalog/associations", params={"limit": 200}
        ).json()
        self.assertEqual(associations["summary"], {"total_count": 200})
        self.assertEqual(len(associations["items"]), 200)

    def test_duplicate_active_identity_inside_one_batch_is_a_prevalidated_conflict(self):
        request = self.add_request()
        request["operations"].append(
            {
                **request["operations"][0],
                "client_operation_id": "op-duplicate-price",
            }
        )

        prevalidation = self.prevalidate(request)

        self.assertFalse(prevalidation["can_commit"])
        self.assertEqual(
            [operation["verdict"] for operation in prevalidation["operations"]],
            ["accepted", "rejected"],
        )
        self.assertEqual(
            prevalidation["operations"][1]["errors"][0]["code"],
            "TS_LINK_CONFLICT",
        )
        committed = self.commit(
            request,
            prevalidation,
            idempotency_key="assoc-duplicate-triple",
        )
        self.assertEqual(committed.status_code, 422, committed.text)
        self.assertEqual(
            self.client.get("/api/time-series/catalog/associations").json()["items"],
            [],
        )

    def test_audit_reason_is_explicit_and_archive_requires_explanatory_text(self):
        missing_reason = self.add_request()
        missing_reason["operations"][0].pop("reason_code")

        refused = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            missing_reason,
        )

        self.assertEqual(refused.status_code, 400, refused.text)
        self.assertEqual(refused.json()["error"]["code"], "TS_LINK_PAYLOAD_INVALID")
        self.assertEqual(
            refused.json()["error"]["field"], "operations[0].reason_code"
        )

        created = self.commit(
            self.add_request(),
            self.prevalidate(self.add_request()),
            idempotency_key="assoc-before-invalid-archive",
        )
        association_id = created.json()["operations"][0]["association_id"]
        archive_without_text = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "op-archive-without-text",
                    "action": "archive",
                    "association_id": association_id,
                    "expected_lifecycle_revision": 1,
                    "reason_code": "source_retired",
                }
            ],
        }
        refused_archive = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            archive_without_text,
        )
        self.assertEqual(refused_archive.status_code, 400, refused_archive.text)
        self.assertEqual(
            refused_archive.json()["error"]["field"],
            "operations[0].reason_text",
        )

    def test_a_changed_revision_between_phases_refuses_the_stale_world_view(self):
        request = self.add_request()
        prevalidation = self.prevalidate(request)
        self.store.publish_canonical_set_revision(
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
                }
            ],
            values={"energy_price": [71.0]},
            actor="analyst@example.local",
        )

        committed = self.commit(
            request,
            prevalidation,
            idempotency_key="assoc-after-new-revision",
        )

        self.assertEqual(committed.status_code, 412, committed.text)
        self.assertEqual(
            committed.json()["error"]["code"], "TS_LINK_PRECONDITION_CHANGED"
        )
        self.assertEqual(
            committed.json()["error"]["context"]["normalized_request"], request
        )
        self.assertEqual(
            self.client.get("/api/time-series/catalog/associations").json()["items"],
            [],
        )

    def test_commit_requires_all_guards_and_the_token_is_bound_to_the_actor(self):
        request = self.add_request()
        prevalidation = self.prevalidate(request)
        body = {
            **request,
            "prevalidation_token": prevalidation["prevalidation_token"],
            "confirmed": True,
        }
        guard_sets = [
            {**csrf_headers(self.client)},
            {
                **csrf_headers(self.client),
                "If-Match": prevalidation["commit_etag"],
            },
            {
                **csrf_headers(self.client),
                "Idempotency-Key": "assoc-missing-etag",
            },
        ]
        for headers in guard_sets:
            response = self.client.post(
                "/api/time-series/catalog/association-batches",
                json=body,
                headers=headers,
            )
            self.assertEqual(response.status_code, 428, response.text)
            self.assertEqual(
                response.json()["error"]["code"], "TS_PRECONDITION_REQUIRED"
            )
        missing_token = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={**request, "confirmed": True},
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidation["commit_etag"],
                "Idempotency-Key": "assoc-missing-token",
            },
        )
        self.assertEqual(missing_token.status_code, 428, missing_token.text)
        self.assertEqual(
            missing_token.json()["error"]["code"], "TS_PRECONDITION_REQUIRED"
        )

        self.store.create_user(
            email="other@example.local",
            display_name="Other Analyst",
            role="analyst",
            password_hash=hash_password("other pass"),
        )
        login_json_with_csrf(self.client, "other@example.local", "other pass")
        wrong_actor = self.commit(
            request,
            prevalidation,
            idempotency_key="assoc-wrong-actor",
        )
        self.assertEqual(wrong_actor.status_code, 412, wrong_actor.text)
        self.assertEqual(
            wrong_actor.json()["error"]["code"], "TS_LINK_PRECONDITION_CHANGED"
        )
        self.assertEqual(
            self.client.get("/api/time-series/catalog/associations").json()["items"],
            [],
        )

    def test_idempotency_key_with_a_different_request_is_a_conflict(self):
        request = self.add_request()
        prevalidation = self.prevalidate(request)
        first = self.commit(
            request,
            prevalidation,
            idempotency_key="assoc-key-conflict",
        )
        self.assertEqual(first.status_code, 201, first.text)
        changed_request = self.add_request()
        changed_request["operations"][0]["reason_code"] = "different_reason"
        changed_prevalidation = self.prevalidate(changed_request)

        conflict = self.commit(
            changed_request,
            changed_prevalidation,
            idempotency_key="assoc-key-conflict",
        )

        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assertEqual(
            conflict.json()["error"]["code"], "TS_IDEMPOTENCY_CONFLICT"
        )
        association_id = first.json()["operations"][0]["association_id"]
        events = self.client.get(
            f"/api/time-series/catalog/associations/{association_id}/events"
        ).json()["items"]
        self.assertEqual([event["event_type"] for event in events], ["created"])

    def test_external_is_refused_before_ids_or_payloads_are_resolved(self):
        self.store.create_user(
            email="external@example.local",
            display_name="External",
            role="external",
            password_hash=hash_password("external pass"),
        )
        login = login_json_with_csrf(
            self.client, "external@example.local", "external pass"
        )
        self.assertEqual(login.status_code, 200, login.text)

        guessed_detail = self.client.get(
            "/api/time-series/catalog/associations/999999"
        )
        malformed_mutation = self.client.post(
            "/api/time-series/catalog/association-prevalidations",
            json={"target_project_id": "not-an-id", "operations": []},
        )

        self.assertEqual(guessed_detail.status_code, 403)
        self.assertEqual(malformed_mutation.status_code, 403)
        self.assertEqual(guessed_detail.json(), {"detail": "forbidden"})
        self.assertEqual(malformed_mutation.json(), {"detail": "forbidden"})

    def test_effective_state_ignores_value_only_revisions_but_detects_unavailability(self):
        created = self.commit(
            self.add_request(),
            self.prevalidate(self.add_request()),
            idempotency_key="assoc-state-machine",
        )
        association_id = created.json()["operations"][0]["association_id"]
        self.store.publish_canonical_set_revision(
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
                }
            ],
            values={"energy_price": [99.0]},
            actor="analyst@example.local",
        )

        after_values = self.client.get(
            f"/api/time-series/catalog/associations/{association_id}"
        )
        self.assertEqual(after_values.status_code, 200, after_values.text)
        self.assertEqual(after_values.json()["state"], "active_valid")

        self.store.archive_canonical_signal_identity(
            set_id=self.receipt["set_id"],
            series_key="energy_price",
            actor="analyst@example.local",
            reason_text="Retired source",
        )
        unavailable = self.client.get(
            f"/api/time-series/catalog/associations/{association_id}"
        )
        self.assertEqual(unavailable.status_code, 200, unavailable.text)
        self.assertEqual(unavailable.json()["state"], "active_incompatible")

    def test_repeating_an_active_triple_with_a_new_key_is_an_unchanged_no_op(self):
        request = self.add_request()
        first = self.commit(
            request,
            self.prevalidate(request),
            idempotency_key="assoc-first-active-triple",
        )
        self.assertEqual(first.status_code, 201, first.text)
        repeated_prevalidation = self.prevalidate(request)

        repeated = self.commit(
            request,
            repeated_prevalidation,
            idempotency_key="assoc-second-active-triple",
        )

        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(repeated.json()["outcome"], "unchanged")
        self.assertEqual(
            repeated.json()["operations"][0]["association_id"],
            first.json()["operations"][0]["association_id"],
        )
        events = self.client.get(
            f"/api/time-series/catalog/associations/"
            f"{first.json()['operations'][0]['association_id']}/events"
        ).json()["items"]
        self.assertEqual([event["event_type"] for event in events], ["created"])


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL contract tests",
)
class PostgresCatalogAssociationApiTests(unittest.TestCase):
    """Repeat the atomic HTTP contract on the production-reference engine."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        suffix = uuid.uuid4().hex[:10]
        self.email = f"ts7-007-{suffix}@example.local"
        self.store.create_user(
            email=self.email,
            display_name="TS7 PostgreSQL Analyst",
            role="analyst",
            password_hash=hash_password("postgres analyst pass"),
        )
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        login = login_json_with_csrf(
            self.client, self.email, "postgres analyst pass"
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.project = self.store.create_project(name=f"TS7-007 {suffix}")
        receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name=f"Inputs {suffix}",
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
            actor=self.email,
        )
        self.signal_id = int(
            self.store.connection.execute(
                f"SELECT id FROM {self.store.canonical_table_names()['time_series_signals']} "
                "WHERE time_series_set_id = ?",
                (receipt["set_id"],),
            ).fetchone()["id"]
        )
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )

    def tearDown(self):
        try:
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()

    def request(self, *, role="grid_import_price", object_id=None, operation_id="op-1"):
        return {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": operation_id,
                    "action": "add",
                    "signal_id": self.signal_id,
                    "linkable_object_id": object_id or self.object["id"],
                    "binding_role_key": role,
                    "expected_absent": True,
                    "reason_code": "postgres_contract",
                }
            ],
        }

    def prevalidate(self, request):
        response = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            request,
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def commit(self, request, prevalidation, idempotency_key):
        return self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **request,
                "prevalidation_token": prevalidation["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidation["commit_etag"],
                "Idempotency-Key": idempotency_key,
            },
        )

    def test_postgresql_commits_replays_and_rolls_back_the_same_http_contract(self):
        request = self.request()
        prevalidation = self.prevalidate(request)
        created = self.commit(request, prevalidation, "postgres-association")
        replayed = self.commit(request, prevalidation, "postgres-association")

        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(replayed.status_code, 200, replayed.text)
        self.assertEqual(replayed.json(), created.json())
        incompatible = self.store.ensure_project_component(
            project_id=self.project["id"],
            component_key="load_a",
            component_type="load",
            display_name="Load A",
        )
        mixed = self.request(
            role="grid_export_price", operation_id="op-valid-export"
        )
        mixed["operations"].extend(
            self.request(
                object_id=incompatible["id"], operation_id="op-invalid-load"
            )["operations"]
        )
        mixed_prevalidation = self.prevalidate(mixed)
        refused = self.commit(mixed, mixed_prevalidation, "postgres-mixed")

        self.assertEqual(refused.status_code, 422, refused.text)
        collection = self.client.get(
            "/api/time-series/catalog/associations"
        ).json()
        self.assertEqual(collection["summary"], {"total_count": 1})

    def test_postgresql_full_200_row_batches_stay_inside_the_operation_budget(self):
        signals = [
            {
                **PRICE_SIGNAL,
                "series_key": f"postgres_bulk_price_{index:04d}",
                "display_name": f"PostgreSQL bulk price {index:04d}",
            }
            for index in range(1_000)
        ]
        receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="PostgreSQL bulk inputs",
            data_class_key="real",
            timezone="UTC",
            signals=signals,
            periods=[
                {
                    "timestamp_start": "2026-01-01T00:00:00",
                    "timestamp_end": "2026-01-01T01:00:00",
                    "duration_hours": 1.0,
                }
            ],
            values={signal["series_key"]: [70.0] for signal in signals},
            actor=self.email,
        )
        signal_rows = self.store.connection.execute(
            f"""
            SELECT id, series_key
            FROM {self.store.canonical_table_names()['time_series_signals']}
            WHERE time_series_set_id = ?
            ORDER BY series_key
            """,
            (receipt["set_id"],),
        ).fetchall()
        prevalidation_samples = []
        commit_samples = []
        for batch_index in range(5):
            batch_rows = signal_rows[batch_index * 200 : (batch_index + 1) * 200]
            request = {
                "target_project_id": self.project["id"],
                "operations": [
                    {
                        "client_operation_id": (
                            f"op-postgres-bulk-{batch_index}-{row_index:03d}"
                        ),
                        "action": "add",
                        "signal_id": int(row["id"]),
                        "linkable_object_id": self.object["id"],
                        "binding_role_key": "grid_import_price",
                        "expected_absent": True,
                        "reason_code": "postgres_bulk_contract",
                    }
                    for row_index, row in enumerate(batch_rows)
                ],
            }

            started = time.perf_counter()
            prevalidation = self.prevalidate(request)
            prevalidation_samples.append(time.perf_counter() - started)
            started = time.perf_counter()
            committed = self.commit(
                request, prevalidation, f"postgres-bulk-200-{batch_index}"
            )
            commit_samples.append(time.perf_counter() - started)

            self.assertEqual(committed.status_code, 201, committed.text)
            self.assertEqual(len(committed.json()["operations"]), 200)

        self.assertLess(max(prevalidation_samples), 2.0, prevalidation_samples)
        self.assertLess(max(commit_samples), 2.0, commit_samples)


if __name__ == "__main__":
    unittest.main()
