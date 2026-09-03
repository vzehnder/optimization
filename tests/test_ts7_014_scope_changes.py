"""TS7-014 administrative scope promotion and demotion contract."""

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

LOCAL_DEFINITION = {
    "object_series_key": "local_price_forecast",
    "display_name": "Precio local previsto",
    "description": "Pronostico horario del nodo",
    "intended_binding_role_key": "grid_import_price",
    "semantic_type_key": "energy_price",
    "unit_key": "usd_per_mwh",
    "data_class_key": "forecast",
    "timezone": "America/Santiago",
    "temporal_contract": {
        "regularity": "regular",
        "nominal_resolution_seconds": 3600,
        "timestamp_convention": "period_start",
    },
    "source_expectation": {"kind": "api", "display_name": "Pronostico interno"},
}

POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class ScopeChangeApiTests(unittest.TestCase):
    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.admin = self.store.create_user(
            email="admin@example.local",
            display_name="Admin",
            role="admin",
            password_hash=hash_password("admin pass"),
        )
        self.analyst = self.store.create_user(
            email="analyst@example.local",
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
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
            actor="admin@example.local",
        )

    def tearDown(self):
        self.store.close()

    @property
    def root(self):
        return f"/api/time-series/catalog/sets/{self.receipt['set_id']}"

    def login(self, email="admin@example.local", password="admin pass"):
        response = login_json_with_csrf(self.client, email, password)
        self.assertEqual(response.status_code, 200, response.text)

    def associate_price(self, *, project=None, suffix="owner"):
        project = project or self.project
        signal_id = self.client.get("/api/time-series/catalog/inputs").json()["items"][0][
            "signal_id"
        ]
        linkable = self.store.ensure_global_signal_slot(
            project_id=project["id"], display_name="Sistema"
        )
        request = {
            "target_project_id": project["id"],
            "operations": [
                {
                    "client_operation_id": f"associate-price-{suffix}",
                    "action": "add",
                    "signal_id": signal_id,
                    "linkable_object_id": linkable["id"],
                    "binding_role_key": "grid_import_price",
                    "expected_absent": True,
                    "reason_code": "catalog_association_requested",
                }
            ],
        }
        preview = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            request,
        ).json()
        committed = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **request,
                "prevalidation_token": preview["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": preview["commit_etag"],
                "Idempotency-Key": f"associate-price-{suffix}-1",
            },
        )
        self.assertEqual(committed.status_code, 201, committed.text)
        return {
            "association_id": committed.json()["operations"][0]["association_id"],
            "linkable_object": linkable,
            "signal_id": signal_id,
        }

    def prevalidate_scope(self, target_scope):
        response = post_json_with_csrf(
            self.client,
            f"{self.root}/scope-prevalidations",
            {"target_scope": target_scope},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def commit_scope(
        self,
        preview,
        *,
        reason_text,
        idempotency_key,
        request_id,
        confirmed=True,
    ):
        revision = preview["impact"]["current_revision"]
        the_set = preview["impact"]["set"]
        return self.client.post(
            f"{self.root}/scope-changes",
            json={
                "target_scope": preview["normalized_request"]["target_scope"],
                "expected_scope_revision": the_set["scope_revision"],
                "observed_revision_id": revision["id"],
                "observed_content_hash": revision["content_hash"],
                "prevalidation_token": preview["prevalidation_token"],
                "confirmed": confirmed,
                "reason_code": "administrative_scope_change",
                "reason_text": reason_text,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": preview["commit_etag"],
                "Idempotency-Key": idempotency_key,
                "X-Request-Id": request_id,
            },
        )

    def test_analyst_cannot_prevalidate_or_commit_scope_changes(self):
        self.login("analyst@example.local", "analyst pass")
        for target_scope in ("global", "project"):
            prevalidation = post_json_with_csrf(
                self.client,
                f"{self.root}/scope-prevalidations",
                {"target_scope": target_scope},
            )
            change = post_json_with_csrf(
                self.client,
                f"{self.root}/scope-changes",
                {
                    "target_scope": target_scope,
                    "expected_scope_revision": 0,
                    "observed_revision_id": self.receipt["revision_id"],
                    "observed_content_hash": self.receipt["content_hash"],
                    "prevalidation_token": "not-a-real-token",
                    "confirmed": True,
                    "reason_code": "publish_shared_catalog",
                    "reason_text": "Approved for cross-project reuse.",
                },
            )

            self.assertEqual(prevalidation.status_code, 403, prevalidation.text)
            self.assertEqual(change.status_code, 403, change.text)
            self.assertEqual(
                prevalidation.json()["error"]["code"], "TS_SCOPE_ADMIN_REQUIRED"
            )
            self.assertEqual(
                change.json()["error"]["code"], "TS_SCOPE_ADMIN_REQUIRED"
            )

    def test_promotion_prevalidation_reports_impact_without_writing(self):
        self.login()
        sets = self.store.canonical_table_names()["time_series_sets"]
        events = self.store.link_layer_table_names()["time_series_scope_events"]
        before = dict(
            self.store.connection.execute(
                f"SELECT * FROM {sets} WHERE id = ?", (self.receipt["set_id"],)
            ).fetchone()
        )
        event_count_before = self.store.connection.execute(
            f"SELECT COUNT(*) AS total FROM {events}"
        ).fetchone()["total"]

        response = post_json_with_csrf(
            self.client,
            f"{self.root}/scope-prevalidations",
            {"target_scope": "global"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["can_commit"])
        self.assertTrue(payload["requires_confirmation"])
        self.assertEqual(payload["normalized_request"], {"target_scope": "global"})
        self.assertEqual(
            payload["impact"],
            {
                "set": {
                    "id": self.receipt["set_id"],
                    "series_kind": "catalog",
                    "status": "validated",
                    "owner_project_id": self.project["id"],
                    "visibility_scope": "project",
                    "scope_revision": 0,
                },
                "current_revision": {
                    "id": self.receipt["revision_id"],
                    "content_hash": self.receipt["content_hash"],
                },
                "target_scope": "global",
                "associations": {
                    "active_count": 0,
                    "owner_project_count": 0,
                    "other_project_count": 0,
                    "items": [],
                },
                "bindings": {
                    "active_count": 0,
                    "owner_project_count": 0,
                    "other_project_count": 0,
                    "items": [],
                },
            },
        )
        self.assertTrue(payload["prevalidation_token"])
        self.assertTrue(payload["commit_etag"].startswith('"'))
        after = dict(
            self.store.connection.execute(
                f"SELECT * FROM {sets} WHERE id = ?", (self.receipt["set_id"],)
            ).fetchone()
        )
        event_count_after = self.store.connection.execute(
            f"SELECT COUNT(*) AS total FROM {events}"
        ).fetchone()["total"]
        self.assertEqual(after, before)
        self.assertEqual(event_count_after, event_count_before)

    def test_promotion_preserves_identity_content_and_links_and_writes_audit_event(self):
        self.login()
        association_id = self.associate_price()["association_id"]
        sets = self.store.canonical_table_names()["time_series_sets"]
        revisions = self.store.canonical_table_names()["time_series_set_revisions"]
        events = self.store.link_layer_table_names()["time_series_scope_events"]
        revision_ids_before = [
            row["id"]
            for row in self.store.connection.execute(
                f"SELECT id FROM {revisions} WHERE time_series_set_id = ? ORDER BY id",
                (self.receipt["set_id"],),
            ).fetchall()
        ]
        preview = self.prevalidate_scope("global")

        changed = self.commit_scope(
            preview,
            reason_text="Approved for reuse by every internal project.",
            idempotency_key="promote-inputs-1",
            request_id="req-promote-inputs",
        )

        self.assertEqual(changed.status_code, 201, changed.text)
        self.assertEqual(changed.json()["outcome"], "promoted_global")
        row = dict(
            self.store.connection.execute(
                f"SELECT * FROM {sets} WHERE id = ?", (self.receipt["set_id"],)
            ).fetchone()
        )
        self.assertEqual(row["id"], self.receipt["set_id"])
        self.assertEqual(row["owner_project_id"], self.project["id"])
        self.assertEqual(row["current_revision_id"], self.receipt["revision_id"])
        self.assertEqual(row["visibility_scope"], "global")
        self.assertEqual(row["scope_revision"], 1)
        revision_ids_after = [
            revision["id"]
            for revision in self.store.connection.execute(
                f"SELECT id FROM {revisions} WHERE time_series_set_id = ? ORDER BY id",
                (self.receipt["set_id"],),
            ).fetchall()
        ]
        self.assertEqual(revision_ids_after, revision_ids_before)
        association = self.client.get(
            f"/api/time-series/catalog/associations/{association_id}"
        )
        self.assertEqual(association.status_code, 200, association.text)
        self.assertEqual(association.json()["association_id"], association_id)
        self.assertEqual(association.json()["state"], "active_stale")
        projected = self.client.get("/api/time-series/catalog/inputs").json()["items"][0]
        self.assertEqual(projected["set"]["visibility_scope"], "global")
        event = dict(
            self.store.connection.execute(
                f"SELECT * FROM {events} WHERE time_series_set_id = ?",
                (self.receipt["set_id"],),
            ).fetchone()
        )
        self.assertEqual(event["event_type"], "promoted_global")
        self.assertEqual(event["from_scope"], "project")
        self.assertEqual(event["to_scope"], "global")
        self.assertEqual(event["scope_revision"], 1)
        self.assertEqual(event["actor_user_id"], self.admin["id"])
        self.assertEqual(event["actor_identity_snapshot"], "admin@example.local")
        self.assertEqual(event["actor_role_snapshot"], "admin")
        self.assertEqual(event["reason_code"], "administrative_scope_change")
        self.assertEqual(
            event["reason_text"], "Approved for reuse by every internal project."
        )
        self.assertEqual(event["request_id"], "req-promote-inputs")

    def test_repeating_an_effective_scope_change_writes_nothing(self):
        self.login()
        preview = self.prevalidate_scope("global")
        first = self.commit_scope(
            preview,
            reason_text="Approved for shared reuse.",
            idempotency_key="promote-once",
            request_id="req-promote-once",
        )
        self.assertEqual(first.status_code, 201, first.text)
        events = self.store.link_layer_table_names()["time_series_scope_events"]

        repeated = self.commit_scope(
            preview,
            reason_text="Approved for shared reuse.",
            idempotency_key="promote-again",
            request_id="req-promote-again",
        )

        self.assertEqual(repeated.status_code, 409, repeated.text)
        self.assertEqual(
            repeated.json()["error"]["code"], "TS_SCOPE_ALREADY_EFFECTIVE"
        )
        current = self.prevalidate_scope("project")["impact"]["set"]
        self.assertEqual(current["visibility_scope"], "global")
        self.assertEqual(current["scope_revision"], 1)
        event_count = self.store.connection.execute(
            f"SELECT COUNT(*) AS total FROM {events} WHERE time_series_set_id = ?",
            (self.receipt["set_id"],),
        ).fetchone()["total"]
        self.assertEqual(event_count, 1)

    def test_demotion_with_other_project_consumers_is_enumerated_and_refused(self):
        self.login()
        promotion = self.prevalidate_scope("global")
        promoted = self.commit_scope(
            promotion,
            reason_text="Approved for shared reuse.",
            idempotency_key="promote-before-demotion",
            request_id="req-promote-before-demotion",
        )
        self.assertEqual(promoted.status_code, 201, promoted.text)
        other_project = self.store.create_project(name="Cuenca Sur")
        cross_project_association = self.associate_price(
            project=other_project, suffix="other"
        )
        cross_project_association_id = cross_project_association["association_id"]

        preview = self.prevalidate_scope("project")

        self.assertFalse(preview["can_commit"])
        self.assertTrue(preview["requires_confirmation"])
        self.assertEqual(preview["impact"]["associations"]["other_project_count"], 1)
        self.assertEqual(
            preview["impact"]["associations"]["items"],
            [
                {
                    "association_id": cross_project_association_id,
                    "signal_id": cross_project_association["signal_id"],
                    "linkable_object_id": cross_project_association["linkable_object"][
                        "id"
                    ],
                    "project_id": other_project["id"],
                }
            ],
        )
        refused = self.commit_scope(
            preview,
            reason_text="Return reuse to the owner project.",
            idempotency_key="demote-with-consumers",
            request_id="req-demote-with-consumers",
        )
        self.assertEqual(refused.status_code, 422, refused.text)
        self.assertEqual(refused.json()["error"]["code"], "TS_SCOPE_INVALID_STATE")
        self.assertEqual(
            refused.json()["error"]["context"]["impact"], preview["impact"]
        )
        current = self.prevalidate_scope("project")["impact"]["set"]
        self.assertEqual(current["visibility_scope"], "global")
        self.assertEqual(current["scope_revision"], 1)
        association = self.client.get(
            f"/api/time-series/catalog/associations/{cross_project_association_id}"
        ).json()
        self.assertEqual(association["state"], "active_valid")
        events = self.store.link_layer_table_names()["time_series_scope_events"]
        event_count = self.store.connection.execute(
            f"SELECT COUNT(*) AS total FROM {events} WHERE time_series_set_id = ?",
            (self.receipt["set_id"],),
        ).fetchone()["total"]
        self.assertEqual(event_count, 1)

    def test_object_specific_set_cannot_be_promoted(self):
        self.login()
        owner = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema local"
        )
        created = self.client.post(
            f"/api/projects/{self.project['id']}/linkable-objects/{owner['id']}"
            "/time-series/object-series",
            json=LOCAL_DEFINITION,
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": "define-local-for-scope",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        local_set_id = created.json()["object_series"]["set_id"]

        response = post_json_with_csrf(
            self.client,
            f"/api/time-series/catalog/sets/{local_set_id}/scope-prevalidations",
            {"target_scope": "global"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertFalse(payload["can_commit"])
        self.assertFalse(payload["requires_confirmation"])
        self.assertEqual(
            payload["errors"],
            [
                {
                    "code": "TS_SCOPE_INVALID_STATE",
                    "context": {
                        "reason": "object_specific",
                        "series_kind": "object_specific",
                    },
                }
            ],
        )
        self.assertEqual(payload["impact"]["set"]["visibility_scope"], "project")

    def test_scope_change_requires_token_etag_and_idempotency_key(self):
        self.login()
        preview = self.prevalidate_scope("global")
        revision = preview["impact"]["current_revision"]
        the_set = preview["impact"]["set"]
        body = {
            "target_scope": "global",
            "expected_scope_revision": the_set["scope_revision"],
            "observed_revision_id": revision["id"],
            "observed_content_hash": revision["content_hash"],
            "confirmed": True,
            "reason_code": "administrative_scope_change",
            "reason_text": "Approved for shared reuse.",
        }

        missing_token = self.client.post(
            f"{self.root}/scope-changes",
            json=body,
            headers={
                **csrf_headers(self.client),
                "If-Match": preview["commit_etag"],
                "Idempotency-Key": "scope-missing-token",
            },
        )
        missing_etag = self.client.post(
            f"{self.root}/scope-changes",
            json={**body, "prevalidation_token": preview["prevalidation_token"]},
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": "scope-missing-etag",
            },
        )
        missing_key = self.client.post(
            f"{self.root}/scope-changes",
            json={**body, "prevalidation_token": preview["prevalidation_token"]},
            headers={
                **csrf_headers(self.client),
                "If-Match": preview["commit_etag"],
            },
        )

        for response in (missing_token, missing_etag, missing_key):
            self.assertEqual(response.status_code, 428, response.text)
            self.assertEqual(
                response.json()["error"]["code"], "TS_PRECONDITION_REQUIRED"
            )

    def test_changed_impact_requires_a_fresh_prevalidation(self):
        self.login()
        preview = self.prevalidate_scope("global")
        association = self.associate_price(suffix="after-preview")

        changed = self.commit_scope(
            preview,
            reason_text="Approved before the impact changed.",
            idempotency_key="promotion-with-stale-impact",
            request_id="req-promotion-with-stale-impact",
        )

        self.assertEqual(changed.status_code, 412, changed.text)
        self.assertEqual(
            changed.json()["error"]["code"], "TS_SCOPE_PRECONDITION_CHANGED"
        )
        actual_impact = changed.json()["error"]["context"]["impact"]
        self.assertEqual(actual_impact["associations"]["active_count"], 1)
        self.assertEqual(
            actual_impact["associations"]["items"][0]["association_id"],
            association["association_id"],
        )
        current = self.prevalidate_scope("global")["impact"]["set"]
        self.assertEqual(current["visibility_scope"], "project")
        self.assertEqual(current["scope_revision"], 0)
        events = self.store.link_layer_table_names()["time_series_scope_events"]
        event_count = self.store.connection.execute(
            f"SELECT COUNT(*) AS total FROM {events} WHERE time_series_set_id = ?",
            (self.receipt["set_id"],),
        ).fetchone()["total"]
        self.assertEqual(event_count, 0)

    def test_set_can_return_to_project_scope_without_cross_project_consumers(self):
        self.login()
        promotion = self.prevalidate_scope("global")
        promoted = self.commit_scope(
            promotion,
            reason_text="Approved for shared reuse.",
            idempotency_key="promote-before-valid-demotion",
            request_id="req-promote-before-valid-demotion",
        )
        self.assertEqual(promoted.status_code, 201, promoted.text)
        demotion = self.prevalidate_scope("project")
        self.assertTrue(demotion["can_commit"])

        demoted = self.commit_scope(
            demotion,
            reason_text="Shared reuse is no longer required.",
            idempotency_key="valid-demotion",
            request_id="req-valid-demotion",
        )

        self.assertEqual(demoted.status_code, 201, demoted.text)
        self.assertEqual(demoted.json()["outcome"], "demoted_project")
        self.assertEqual(demoted.json()["impact"], demotion["impact"])
        current = self.prevalidate_scope("global")["impact"]["set"]
        self.assertEqual(current["visibility_scope"], "project")
        self.assertEqual(current["owner_project_id"], self.project["id"])
        self.assertEqual(current["scope_revision"], 2)
        events = self.store.link_layer_table_names()["time_series_scope_events"]
        ledger = self.store.connection.execute(
            f"""
            SELECT event_type, from_scope, to_scope, scope_revision
            FROM {events} WHERE time_series_set_id = ? ORDER BY scope_revision
            """,
            (self.receipt["set_id"],),
        ).fetchall()
        self.assertEqual(
            [dict(event) for event in ledger],
            [
                {
                    "event_type": "promoted_global",
                    "from_scope": "project",
                    "to_scope": "global",
                    "scope_revision": 1,
                },
                {
                    "event_type": "demoted_project",
                    "from_scope": "global",
                    "to_scope": "project",
                    "scope_revision": 2,
                },
            ],
        )

    def test_inactive_signal_blocks_promotion_before_confirmation(self):
        self.login()
        self.store.archive_canonical_signal_identity(
            set_id=self.receipt["set_id"],
            series_key="energy_price",
            actor="admin@example.local",
            reason_text="Retired source identity.",
        )

        preview = self.prevalidate_scope("global")

        self.assertFalse(preview["can_commit"])
        self.assertEqual(
            preview["errors"],
            [
                {
                    "code": "TS_SCOPE_INVALID_STATE",
                    "context": {
                        "reason": "inactive_signal",
                        "inactive_signal_count": 1,
                    },
                }
            ],
        )
        events = self.store.link_layer_table_names()["time_series_scope_events"]
        event_count = self.store.connection.execute(
            f"SELECT COUNT(*) AS total FROM {events} WHERE time_series_set_id = ?",
            (self.receipt["set_id"],),
        ).fetchone()["total"]
        self.assertEqual(event_count, 0)


    def test_failed_promotion_never_opens_project_source_to_another_project(self):
        self.login("analyst@example.local", "analyst pass")
        other_project = self.store.create_project(name="Cuenca Exterior")
        other_object = self.store.ensure_global_signal_slot(
            project_id=other_project["id"], display_name="Sistema exterior"
        )
        signal_id = self.receipt["signal_ids"]["energy_price"]
        request = {
            "target_project_id": other_project["id"],
            "operations": [
                {
                    "client_operation_id": "cross-project-price",
                    "action": "add",
                    "signal_id": signal_id,
                    "linkable_object_id": other_object["id"],
                    "binding_role_key": "grid_import_price",
                    "expected_absent": True,
                    "reason_code": "cross_project_attempt",
                }
            ],
        }

        before = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            request,
        )
        denied_promotion = post_json_with_csrf(
            self.client,
            f"{self.root}/scope-prevalidations",
            {"target_scope": "global"},
        )
        after = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            request,
        )

        self.assertEqual(before.status_code, 200, before.text)
        self.assertEqual(denied_promotion.status_code, 403, denied_promotion.text)
        self.assertEqual(after.status_code, 200, after.text)
        for response in (before, after):
            payload = response.json()
            self.assertFalse(payload["can_commit"])
            self.assertEqual(
                payload["operations"][0]["errors"][0]["code"],
                "TS_COMPAT_SCOPE_NOT_ACCESSIBLE",
            )
        sets = self.store.canonical_table_names()["time_series_sets"]
        current = self.store.connection.execute(
            f"SELECT visibility_scope, scope_revision FROM {sets} WHERE id = ?",
            (self.receipt["set_id"],),
        ).fetchone()
        self.assertEqual(dict(current), {"visibility_scope": "project", "scope_revision": 0})

    def test_confirmation_is_required_and_a_successful_change_replays_once(self):
        self.login()
        preview = self.prevalidate_scope("global")
        unconfirmed = self.commit_scope(
            preview,
            reason_text="Approved for shared reuse.",
            idempotency_key="confirmed-promotion",
            request_id="req-unconfirmed-promotion",
            confirmed=False,
        )
        self.assertEqual(unconfirmed.status_code, 409, unconfirmed.text)
        self.assertEqual(
            unconfirmed.json()["error"]["code"], "TS_SCOPE_CONFIRMATION_REQUIRED"
        )

        created = self.commit_scope(
            preview,
            reason_text="Approved for shared reuse.",
            idempotency_key="confirmed-promotion",
            request_id="req-confirmed-promotion",
        )
        replayed = self.commit_scope(
            preview,
            reason_text="Approved for shared reuse.",
            idempotency_key="confirmed-promotion",
            request_id="req-confirmed-promotion",
        )

        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(replayed.status_code, 200, replayed.text)
        self.assertEqual(replayed.json(), created.json())
        events = self.store.link_layer_table_names()["time_series_scope_events"]
        event_count = self.store.connection.execute(
            f"SELECT COUNT(*) AS total FROM {events} WHERE time_series_set_id = ?",
            (self.receipt["set_id"],),
        ).fetchone()["total"]
        self.assertEqual(event_count, 1)

    def test_signal_state_change_after_preview_is_a_changed_precondition(self):
        self.login()
        preview = self.prevalidate_scope("global")
        self.store.archive_canonical_signal_identity(
            set_id=self.receipt["set_id"],
            series_key="energy_price",
            actor="admin@example.local",
            reason_text="Retired after scope preview.",
        )

        changed = self.commit_scope(
            preview,
            reason_text="Approved before the source was retired.",
            idempotency_key="promotion-after-signal-retired",
            request_id="req-promotion-after-signal-retired",
        )

        self.assertEqual(changed.status_code, 412, changed.text)
        self.assertEqual(
            changed.json()["error"]["code"], "TS_SCOPE_PRECONDITION_CHANGED"
        )
        events = self.store.link_layer_table_names()["time_series_scope_events"]
        event_count = self.store.connection.execute(
            f"SELECT COUNT(*) AS total FROM {events} WHERE time_series_set_id = ?",
            (self.receipt["set_id"],),
        ).fetchone()["total"]
        self.assertEqual(event_count, 0)

    def test_scope_change_rejects_a_blank_reason_without_writing(self):
        self.login()
        preview = self.prevalidate_scope("global")
        revision = preview["impact"]["current_revision"]
        the_set = preview["impact"]["set"]

        response = self.client.post(
            f"{self.root}/scope-changes",
            json={
                "target_scope": "global",
                "expected_scope_revision": the_set["scope_revision"],
                "observed_revision_id": revision["id"],
                "observed_content_hash": revision["content_hash"],
                "prevalidation_token": preview["prevalidation_token"],
                "confirmed": True,
                "reason_code": "administrative_scope_change",
                "reason_text": "   ",
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": preview["commit_etag"],
                "Idempotency-Key": "blank-scope-reason",
            },
        )

        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["code"], "TS_SCOPE_INVALID_STATE")
        self.assertEqual(response.json()["error"]["field"], "reason_text")
        sets = self.store.canonical_table_names()["time_series_sets"]
        current = self.store.connection.execute(
            f"SELECT visibility_scope, scope_revision FROM {sets} WHERE id = ?",
            (self.receipt["set_id"],),
        ).fetchone()
        self.assertEqual(dict(current), {"visibility_scope": "project", "scope_revision": 0})


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL contract tests",
)
class PostgresScopeChangeApiTests(unittest.TestCase):
    """Run the scope transition and ledger contract on the reference engine."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        suffix = uuid.uuid4().hex[:10]
        self.email = f"ts7-014-{suffix}@example.local"
        self.store.create_user(
            email=self.email,
            display_name="TS7 PostgreSQL Admin",
            role="admin",
            password_hash=hash_password("postgres admin pass"),
        )
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        login = login_json_with_csrf(
            self.client, self.email, "postgres admin pass"
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.project = self.store.create_project(name=f"TS7-014 {suffix}")
        self.receipt = self.store.publish_canonical_set_revision(
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

    def tearDown(self):
        try:
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()

    @property
    def root(self):
        return f"/api/time-series/catalog/sets/{self.receipt['set_id']}"

    def change_scope(self, target_scope, *, key):
        preview_response = post_json_with_csrf(
            self.client,
            f"{self.root}/scope-prevalidations",
            {"target_scope": target_scope},
        )
        self.assertEqual(preview_response.status_code, 200, preview_response.text)
        preview = preview_response.json()
        return self.client.post(
            f"{self.root}/scope-changes",
            json={
                "target_scope": target_scope,
                "expected_scope_revision": preview["impact"]["set"][
                    "scope_revision"
                ],
                "observed_revision_id": preview["impact"]["current_revision"]["id"],
                "observed_content_hash": preview["impact"]["current_revision"][
                    "content_hash"
                ],
                "prevalidation_token": preview["prevalidation_token"],
                "confirmed": True,
                "reason_code": "postgres_scope_contract",
                "reason_text": "Exercise the PostgreSQL scope ledger.",
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": preview["commit_etag"],
                "Idempotency-Key": key,
            },
        )

    def test_postgresql_promotes_and_demotes_the_same_set_with_two_events(self):
        promoted = self.change_scope("global", key="postgres-promote")
        demoted = self.change_scope("project", key="postgres-demote")

        self.assertEqual(promoted.status_code, 201, promoted.text)
        self.assertEqual(demoted.status_code, 201, demoted.text)
        sets = self.store.canonical_table_names()["time_series_sets"]
        current = self.store.connection.execute(
            f"""
            SELECT owner_project_id, current_revision_id, visibility_scope,
                   scope_revision FROM {sets} WHERE id = ?
            """,
            (self.receipt["set_id"],),
        ).fetchone()
        self.assertEqual(
            dict(current),
            {
                "owner_project_id": self.project["id"],
                "current_revision_id": self.receipt["revision_id"],
                "visibility_scope": "project",
                "scope_revision": 2,
            },
        )
        events = self.store.link_layer_table_names()["time_series_scope_events"]
        event_types = self.store.connection.execute(
            f"""
            SELECT event_type FROM {events}
            WHERE time_series_set_id = ? ORDER BY scope_revision
            """,
            (self.receipt["set_id"],),
        ).fetchall()
        self.assertEqual(
            [event["event_type"] for event in event_types],
            ["promoted_global", "demoted_project"],
        )


if __name__ == "__main__":
    unittest.main()
