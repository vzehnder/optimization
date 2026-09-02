"""TS7-008 exact, derived and audited case time-series bindings."""

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


class CaseTimeSeriesBindingApiTests(unittest.TestCase):
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
        self.assertEqual(login.status_code, 200, login.text)
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Plan base"
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
                }
            ],
            values={"energy_price": [70.0]},
            actor="analyst@example.local",
        )
        self.signal_id = self.receipt["signal_ids"]["energy_price"]
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )

    def tearDown(self):
        self.store.close()

    @property
    def root(self):
        return (
            f"/api/scenarios/{self.scenario['id']}/case-variants/"
            f"{self.variant['id']}"
        )

    def create_request(self):
        return {
            "expected_bindings_revision": 0,
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

    def prevalidate(self, request):
        response = post_json_with_csrf(
            self.client,
            f"{self.root}/time-series-binding-prevalidations",
            request,
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def commit(self, request, prevalidation, *, idempotency_key="bind-grid-price-1"):
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
                "Idempotency-Key": idempotency_key,
                "X-Request-Id": "req-bind-grid-price",
            },
        )

    def test_create_pins_the_exact_revision_and_reads_valid_current_with_an_etag(self):
        request = self.create_request()

        prevalidation = self.prevalidate(request)
        self.assertTrue(prevalidation["can_commit"])
        self.assertEqual(prevalidation["observed_bindings_revision"], 0)
        self.assertEqual(prevalidation["operations"][0]["verdict"], "accepted")
        self.assertEqual(
            prevalidation["operations"][0]["after"]["state"], "valid_current"
        )

        committed = self.commit(request, prevalidation)

        self.assertEqual(committed.status_code, 201, committed.text)
        result = committed.json()
        self.assertEqual(result["bindings_revision"], 1)
        binding_id = result["operations"][0]["binding_id"]

        collection = self.client.get(f"{self.root}/time-series-bindings")
        self.assertEqual(collection.status_code, 200, collection.text)
        self.assertEqual(collection.json()["summary"], {"total_count": 1})
        binding = collection.json()["items"][0]
        self.assertEqual(binding["binding_id"], binding_id)
        self.assertEqual(binding["state"], "valid_current")
        self.assertEqual(binding["set_revision_id"], self.receipt["revision_id"])
        self.assertEqual(binding["bound_content_hash"], self.receipt["content_hash"])

        detail = self.client.get(f"{self.root}/time-series-bindings/{binding_id}")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertTrue(detail.headers["etag"].startswith('"'))
        self.assertEqual(detail.json()["state"], "valid_current")
        self.assertEqual(detail.json()["revision"]["mode"], "current")
        self.assertEqual(detail.json()["lifecycle_revision"], 1)
        catalog_item = self.client.get(
            "/api/time-series/catalog/inputs"
        ).json()["items"][0]
        self.assertEqual(catalog_item["link_summary"]["binding_count"], 1)

    def test_a_new_publication_makes_the_binding_stale_without_moving_it_and_blocks_run(self):
        request = self.create_request()
        created = self.commit(request, self.prevalidate(request))
        self.assertEqual(created.status_code, 201, created.text)
        binding_id = created.json()["operations"][0]["binding_id"]
        original_revision_id = self.receipt["revision_id"]
        original_hash = self.receipt["content_hash"]

        published = self.store.publish_canonical_set_revision(
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
            values={"energy_price": [81.0]},
            actor="analyst@example.local",
        )
        self.assertNotEqual(published["revision_id"], original_revision_id)

        detail = self.client.get(f"{self.root}/time-series-bindings/{binding_id}")

        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["state"], "stale")
        self.assertEqual(detail.json()["set_revision_id"], original_revision_id)
        self.assertEqual(detail.json()["bound_content_hash"], original_hash)
        self.assertEqual(
            detail.json()["revision"]["current_revision_id"],
            published["revision_id"],
        )

        run = post_json_with_csrf(
            self.client,
            f"/api/scenarios/{self.scenario['id']}/case/variants/"
            f"{self.variant['id']}/run",
            {
                "range_start": "2026-01-01T00:00:00",
                "range_end": "2026-01-01T01:00:00",
            },
        )
        self.assertEqual(run.status_code, 409, run.text)
        self.assertEqual(run.json()["error"]["code"], "TS_BINDING_EXECUTION_BLOCKED")
        self.assertEqual(run.json()["error"]["details"][0]["binding_id"], binding_id)
        self.assertEqual(run.json()["error"]["details"][0]["state"], "stale")

    def test_replace_requires_comparison_and_reason_and_keeps_the_previous_binding(self):
        create_request = self.create_request()
        created = self.commit(create_request, self.prevalidate(create_request))
        old_binding_id = created.json()["operations"][0]["binding_id"]
        published = self.store.publish_canonical_set_revision(
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
            values={"energy_price": [82.0]},
            actor="analyst@example.local",
        )
        request = {
            "expected_bindings_revision": 1,
            "operations": [
                {
                    "client_operation_id": "replace-grid-price",
                    "action": "replace",
                    "binding_id": old_binding_id,
                    "expected_lifecycle_revision": 1,
                    "linkable_object_id": self.object["id"],
                    "binding_role_key": "grid_import_price",
                    "signal_id": self.signal_id,
                    "revision": {
                        "mode": "current",
                        "revision_id": published["revision_id"],
                        "content_hash": published["content_hash"],
                    },
                    "catalog_association_id": None,
                    "reason_code": "new_source_revision_accepted",
                    "reason_text": "Reviewed the changed value and accepted revision 2.",
                }
            ],
        }

        prevalidation = self.prevalidate(request)

        self.assertTrue(prevalidation["can_commit"])
        self.assertTrue(prevalidation["requires_confirmation"])
        operation = prevalidation["operations"][0]
        self.assertEqual(operation["verdict"], "confirmation_required")
        self.assertEqual(operation["comparison"]["before"]["binding_id"], old_binding_id)
        self.assertEqual(operation["comparison"]["before"]["state"], "stale")
        self.assertEqual(
            operation["comparison"]["after"]["set_revision_id"],
            published["revision_id"],
        )

        replaced = self.commit(
            request, prevalidation, idempotency_key="replace-grid-price-1"
        )

        self.assertEqual(replaced.status_code, 201, replaced.text)
        self.assertEqual(replaced.json()["bindings_revision"], 2)
        new_binding_id = replaced.json()["operations"][0]["binding_id"]
        old_detail = self.client.get(
            f"{self.root}/time-series-bindings/{old_binding_id}"
        ).json()
        new_detail = self.client.get(
            f"{self.root}/time-series-bindings/{new_binding_id}"
        ).json()
        self.assertEqual(old_detail["status"], "superseded")
        self.assertEqual(old_detail["state"], "inactive")
        self.assertEqual(old_detail["set_revision_id"], self.receipt["revision_id"])
        self.assertEqual(new_detail["state"], "valid_current")
        self.assertEqual(new_detail["supersedes_binding_id"], old_binding_id)
        collection = self.client.get(f"{self.root}/time-series-bindings").json()
        self.assertEqual(collection["summary"], {"total_count": 2})
        self.assertEqual(
            [item["binding_id"] for item in collection["items"]],
            [old_binding_id, new_binding_id],
        )

    def test_revalidate_pinned_keeps_the_exact_revision_and_goes_stale_again_later(self):
        create_request = self.create_request()
        created = self.commit(create_request, self.prevalidate(create_request))
        binding_id = created.json()["operations"][0]["binding_id"]

        revision_2 = self.store.publish_canonical_set_revision(
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
            values={"energy_price": [83.0]},
            actor="analyst@example.local",
        )
        request = {
            "expected_bindings_revision": 1,
            "operations": [
                {
                    "client_operation_id": "keep-pinned-grid-price",
                    "action": "revalidate_pinned",
                    "binding_id": binding_id,
                    "expected_lifecycle_revision": 1,
                    "reason_code": "historical_revision_accepted",
                    "reason_text": "The scenario must retain the approved baseline.",
                }
            ],
        }

        prevalidation = self.prevalidate(request)
        self.assertTrue(prevalidation["can_commit"])
        self.assertTrue(prevalidation["requires_confirmation"])
        self.assertEqual(
            prevalidation["operations"][0]["after"]["state"], "valid_pinned"
        )
        revalidated = self.commit(
            request, prevalidation, idempotency_key="keep-pinned-grid-price-1"
        )

        self.assertEqual(revalidated.status_code, 201, revalidated.text)
        self.assertEqual(revalidated.json()["bindings_revision"], 1)
        detail = self.client.get(
            f"{self.root}/time-series-bindings/{binding_id}"
        ).json()
        self.assertEqual(detail["state"], "valid_pinned")
        self.assertEqual(detail["revision"]["mode"], "pinned")
        self.assertEqual(detail["set_revision_id"], self.receipt["revision_id"])
        self.assertEqual(
            detail["revision"]["observed_current_revision_id"],
            revision_2["revision_id"],
        )
        events_path = f"{self.root}/time-series-bindings/{binding_id}/events"
        first_events = self.client.get(events_path, params={"limit": 1})
        self.assertEqual(first_events.status_code, 200, first_events.text)
        self.assertEqual(first_events.json()["items"][0]["event_type"], "created")
        self.assertTrue(first_events.json()["page"]["has_more"])
        second_events = self.client.get(
            events_path,
            params={
                "limit": 1,
                "cursor": first_events.json()["page"]["next_cursor"],
            },
        )
        self.assertEqual(second_events.status_code, 200, second_events.text)
        self.assertEqual(
            second_events.json()["items"][0]["event_type"],
            "revalidated_pinned",
        )
        self.assertEqual(
            second_events.json()["items"][0]["reason"],
            {
                "code": "historical_revision_accepted",
                "text": "The scenario must retain the approved baseline.",
            },
        )
        self.assertFalse(second_events.json()["page"]["has_more"])

        revision_3 = self.store.publish_canonical_set_revision(
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
            values={"energy_price": [84.0]},
            actor="analyst@example.local",
        )
        later = self.client.get(
            f"{self.root}/time-series-bindings/{binding_id}"
        ).json()
        self.assertEqual(later["state"], "stale")
        self.assertEqual(later["set_revision_id"], self.receipt["revision_id"])
        self.assertEqual(
            later["revision"]["current_revision_id"], revision_3["revision_id"]
        )

    def test_remove_and_restore_are_append_only_lifecycle_transitions(self):
        create_request = self.create_request()
        created = self.commit(create_request, self.prevalidate(create_request))
        binding_id = created.json()["operations"][0]["binding_id"]
        remove_request = {
            "expected_bindings_revision": 1,
            "operations": [
                {
                    "client_operation_id": "remove-grid-price",
                    "action": "remove",
                    "binding_id": binding_id,
                    "expected_lifecycle_revision": 1,
                    "reason_code": "input_not_needed",
                    "reason_text": "The variant no longer consumes this role.",
                }
            ],
        }
        removed_prevalidation = self.prevalidate(remove_request)
        self.assertTrue(removed_prevalidation["requires_confirmation"])

        removed = self.commit(
            remove_request,
            removed_prevalidation,
            idempotency_key="remove-grid-price-1",
        )

        self.assertEqual(removed.status_code, 201, removed.text)
        self.assertEqual(removed.json()["bindings_revision"], 2)
        removed_detail = self.client.get(
            f"{self.root}/time-series-bindings/{binding_id}"
        ).json()
        self.assertEqual(removed_detail["status"], "removed")
        self.assertEqual(removed_detail["state"], "inactive")
        self.assertEqual(removed_detail["lifecycle_revision"], 2)

        restore_request = {
            "expected_bindings_revision": 2,
            "operations": [
                {
                    "client_operation_id": "restore-grid-price",
                    "action": "restore",
                    "binding_id": binding_id,
                    "expected_lifecycle_revision": 2,
                    "reason_code": "input_needed_again",
                    "reason_text": "The role is required again after review.",
                }
            ],
        }
        restored_prevalidation = self.prevalidate(restore_request)
        self.assertTrue(restored_prevalidation["can_commit"])
        self.assertTrue(restored_prevalidation["requires_confirmation"])
        restored = self.commit(
            restore_request,
            restored_prevalidation,
            idempotency_key="restore-grid-price-1",
        )

        self.assertEqual(restored.status_code, 201, restored.text)
        self.assertEqual(restored.json()["bindings_revision"], 3)
        restored_id = restored.json()["operations"][0]["binding_id"]
        self.assertNotEqual(restored_id, binding_id)
        restored_detail = self.client.get(
            f"{self.root}/time-series-bindings/{restored_id}"
        ).json()
        self.assertEqual(restored_detail["state"], "valid_current")
        self.assertEqual(restored_detail["supersedes_binding_id"], binding_id)
        self.assertEqual(
            self.client.get(f"{self.root}/time-series-bindings").json()["summary"],
            {"total_count": 2},
        )

    def test_project_mismatch_rejects_the_whole_batch_and_client_state_is_forbidden(self):
        other_project = self.store.create_project(name="Cuenca Sur")
        foreign_object = self.store.ensure_global_signal_slot(
            project_id=other_project["id"], display_name="Sistema sur"
        )
        request = self.create_request()
        request["operations"].append(
            {
                **request["operations"][0],
                "client_operation_id": "bind-foreign-grid-price",
                "linkable_object_id": foreign_object["id"],
                "binding_role_key": "grid_export_price",
            }
        )

        prevalidation = self.prevalidate(request)

        self.assertFalse(prevalidation["can_commit"])
        self.assertEqual(
            prevalidation["operations"][1]["errors"][0]["code"],
            "TS_COMPAT_PROJECT_CONTEXT_MISMATCH",
        )
        refused = self.commit(
            request, prevalidation, idempotency_key="mixed-project-bindings"
        )
        self.assertEqual(refused.status_code, 422, refused.text)
        self.assertEqual(
            refused.json()["error"]["code"], "TS_LINK_BATCH_REJECTED"
        )
        self.assertEqual(
            self.client.get(f"{self.root}/time-series-bindings").json()["items"],
            [],
        )
        fresh = self.prevalidate(self.create_request())
        self.assertEqual(fresh["observed_bindings_revision"], 0)

        forged = self.create_request()
        forged["operations"][0]["state"] = "valid_current"
        forged_response = post_json_with_csrf(
            self.client,
            f"{self.root}/time-series-binding-prevalidations",
            forged,
        )
        self.assertEqual(forged_response.status_code, 400, forged_response.text)
        self.assertEqual(
            forged_response.json()["error"]["code"], "TS_LINK_PAYLOAD_INVALID"
        )
        self.assertEqual(
            forged_response.json()["error"]["field"], "operations[0].state"
        )

    def test_archiving_a_bound_signal_preserves_the_binding_and_derives_invalid(self):
        request = self.create_request()
        created = self.commit(request, self.prevalidate(request))
        binding_id = created.json()["operations"][0]["binding_id"]

        archived = self.store.archive_canonical_signal_identity(
            set_id=self.receipt["set_id"],
            series_key="energy_price",
            actor="analyst@example.local",
            reason_text="Retired source identity.",
        )

        self.assertEqual(archived["status"], "archived")
        detail = self.client.get(f"{self.root}/time-series-bindings/{binding_id}")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["state"], "invalid")
        self.assertEqual(detail.json()["set_revision_id"], self.receipt["revision_id"])
        self.assertEqual(detail.json()["bound_content_hash"], self.receipt["content_hash"])
        collection = self.client.get(f"{self.root}/time-series-bindings").json()
        self.assertEqual(collection["summary"], {"total_count": 1})
        self.assertEqual(collection["items"][0]["binding_id"], binding_id)
        events = self.client.get(
            f"{self.root}/time-series-bindings/{binding_id}/events"
        ).json()
        self.assertEqual(events["summary"], {"total_count": 1})
        self.assertEqual(events["items"][0]["event_type"], "created")

    def test_catalog_provenance_must_match_the_binding_signal_object_and_role(self):
        association_request = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "associate-export-price",
                    "action": "add",
                    "signal_id": self.signal_id,
                    "linkable_object_id": self.object["id"],
                    "binding_role_key": "grid_export_price",
                    "expected_absent": True,
                    "reason_code": "catalog_source_selected",
                }
            ],
        }
        association_prevalidation = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            association_request,
        ).json()
        association_commit = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **association_request,
                "prevalidation_token": association_prevalidation[
                    "prevalidation_token"
                ],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": association_prevalidation["commit_etag"],
                "Idempotency-Key": "associate-export-price-1",
            },
        )
        self.assertEqual(association_commit.status_code, 201, association_commit.text)
        association_id = association_commit.json()["operations"][0][
            "association_id"
        ]
        mismatched = self.create_request()
        mismatched["operations"][0]["catalog_association_id"] = association_id

        refused = self.prevalidate(mismatched)

        self.assertFalse(refused["can_commit"])
        self.assertEqual(
            refused["operations"][0]["errors"][0]["code"],
            "TS_COMPAT_ASSOCIATION_MISMATCH",
        )

        matching = self.create_request()
        matching["operations"][0]["binding_role_key"] = "grid_export_price"
        matching["operations"][0]["catalog_association_id"] = association_id
        accepted = self.prevalidate(matching)
        self.assertTrue(accepted["can_commit"])
        committed = self.commit(
            matching, accepted, idempotency_key="bind-associated-export-price"
        )
        self.assertEqual(committed.status_code, 201, committed.text)
        binding_id = committed.json()["operations"][0]["binding_id"]
        self.assertEqual(
            self.client.get(
                f"{self.root}/time-series-bindings/{binding_id}"
            ).json()["catalog_association_id"],
            association_id,
        )

        archive_request = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "archive-export-association",
                    "action": "archive",
                    "association_id": association_id,
                    "expected_lifecycle_revision": 1,
                    "reason_code": "catalog_association_retired",
                    "reason_text": "The catalog suggestion is no longer maintained.",
                }
            ],
        }
        archive_prevalidation = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            archive_request,
        ).json()
        archived = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **archive_request,
                "prevalidation_token": archive_prevalidation["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": archive_prevalidation["commit_etag"],
                "Idempotency-Key": "archive-export-association-1",
            },
        )
        self.assertEqual(archived.status_code, 201, archived.text)
        binding_after_archive = self.client.get(
            f"{self.root}/time-series-bindings/{binding_id}"
        ).json()
        self.assertEqual(binding_after_archive["state"], "stale")
        self.assertEqual(binding_after_archive["status"], "active")

    def test_commit_rechecks_the_observed_world_and_idempotent_replay_writes_once(self):
        request = self.create_request()
        stale_prevalidation = self.prevalidate(request)
        published = self.store.publish_canonical_set_revision(
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
            values={"energy_price": [85.0]},
            actor="analyst@example.local",
        )
        stale_commit = self.commit(
            request,
            stale_prevalidation,
            idempotency_key="binding-after-source-change",
        )
        self.assertEqual(stale_commit.status_code, 412, stale_commit.text)
        self.assertEqual(
            stale_commit.json()["error"]["code"],
            "TS_LINK_PRECONDITION_CHANGED",
        )
        self.assertEqual(
            self.client.get(f"{self.root}/time-series-bindings").json()["items"],
            [],
        )

        request["operations"][0]["revision"] = {
            "mode": "current",
            "revision_id": published["revision_id"],
            "content_hash": published["content_hash"],
        }
        prevalidation = self.prevalidate(request)
        first = self.commit(
            request, prevalidation, idempotency_key="idempotent-grid-binding"
        )
        replay = self.commit(
            request, prevalidation, idempotency_key="idempotent-grid-binding"
        )

        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json(), first.json())
        binding_id = first.json()["operations"][0]["binding_id"]
        events = self.client.get(
            f"{self.root}/time-series-bindings/{binding_id}/events"
        ).json()
        self.assertEqual(events["summary"], {"total_count": 1})
        self.assertEqual(
            self.prevalidate(
                {
                    **request,
                    "expected_bindings_revision": 1,
                    "operations": [
                        {
                            **request["operations"][0],
                            "client_operation_id": "duplicate-active-binding",
                        }
                    ],
                }
            )["observed_bindings_revision"],
            1,
        )


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL contract tests",
)
class PostgresCaseTimeSeriesBindingApiTests(CaseTimeSeriesBindingApiTests):
    """Run the same public binding contract on the production-reference engine."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        suffix = uuid.uuid4().hex[:10]
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.user = self.store.create_user(
            email=f"ts7-008-{suffix}@example.local",
            display_name="PostgreSQL Analyst",
            role="analyst",
            password_hash=hash_password("postgres analyst pass"),
        )
        login = login_json_with_csrf(
            self.client, self.user["email"], "postgres analyst pass"
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.project = self.store.create_project(name=f"Cuenca Norte {suffix}")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Plan base"
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
                }
            ],
            values={"energy_price": [70.0]},
            actor=self.user["email"],
        )
        self.signal_id = self.receipt["signal_ids"]["energy_price"]
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )

    def tearDown(self):
        try:
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()


if __name__ == "__main__":
    unittest.main()
