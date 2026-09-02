"""TS7-010 object-specific series created and ingested from their object."""

import os
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import (
    csrf_headers,
    delete_with_csrf,
    login_json_with_csrf,
    post_json_with_csrf,
    put_json_with_csrf,
)


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")

DEFINITION = {
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
    "metadata": {
        "tags": ["operacion", "diario"],
        "external_reference": "forecast:nodo-7",
    },
}

POINTS_INGESTION = {
    "mode": "replace_full",
    "expected_base": None,
    "revision_contract": {
        "data_class_key": "forecast",
        "timezone": "America/Santiago",
        "regularity": "regular",
        "nominal_resolution_seconds": 3600,
    },
    "source": {
        "kind": "api",
        "display_name": "Pronostico interno",
        "external_reference": "issue:2026-08-31T12:00Z",
    },
    "points": [
        {
            "timestamp_start": "2026-08-31T00:00:00-04:00",
            "duration_seconds": 3600,
            "values": {"local_price_forecast": {"value": 18.4, "quality_flag": "forecast"}},
        },
        {
            "timestamp_start": "2026-08-31T01:00:00-04:00",
            "duration_seconds": 3600,
            "values": {"local_price_forecast": {"value": 19.1}},
        },
    ],
}


class ObjectSpecificSeriesApiTests(unittest.TestCase):
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
        self.other_project = self.store.create_project(name="Cuenca Sur")
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        self.other_object = self.store.ensure_global_signal_slot(
            project_id=self.other_project["id"], display_name="Sistema sur"
        )

    def tearDown(self):
        self.store.close()

    @property
    def root(self):
        return (
            f"/api/projects/{self.project['id']}/linkable-objects/"
            f"{self.object['id']}/time-series"
        )

    def create_definition(self, *, payload=None, root=None, idempotency_key=None):
        return self.client.post(
            f"{root or self.root}/object-series",
            json=DEFINITION if payload is None else payload,
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": idempotency_key or f"define-{uuid.uuid4().hex}",
            },
        )

    def test_the_definition_is_born_from_an_existing_object_and_awaits_data(self):
        created = self.create_definition()

        self.assertEqual(created.status_code, 201, created.text)
        series = created.json()["object_series"]
        self.assertEqual(series["source_kind"], "object_specific")
        self.assertEqual(series["set_status"], "draft")
        self.assertEqual(series["availability"], "awaiting_data")
        self.assertIsNone(series["current_revision"])
        self.assertEqual(series["building_revision"]["revision_number"], 1)
        self.assertFalse(series["binding_ready"])
        # The declared intention is audit, not the only role: the executable
        # compatibility keeps coming from the positive matrix (chapter 7.5).
        self.assertEqual(
            series["compatible_role_keys"],
            ["grid_export_price", "grid_import_price"],
        )
        self.assertEqual(
            series["classification"]["intended_binding_role_key"],
            "grid_import_price",
        )
        self.assertEqual(series["object_series_key"], "local_price_forecast")
        self.assertEqual(
            series["owner"],
            {
                "project_id": self.project["id"],
                "linkable_object_id": self.object["id"],
                "object_kind": "global_signal_slot",
                "object_type_key": "global:system",
            },
        )
        self.assertEqual(series["resource_version"], 1)
        self.assertEqual(
            created.headers["etag"],
            f'"ts-object-series-{series["signal_id"]}-v1"',
        )

    def test_no_route_creates_the_object_and_the_definition_at_once(self):
        unknown_object = self.create_definition(
            root=(
                f"/api/projects/{self.project['id']}/linkable-objects/"
                f"{self.object['id'] + 4096}/time-series"
            )
        )

        self.assertEqual(unknown_object.status_code, 404, unknown_object.text)
        self.assertEqual(
            unknown_object.json()["code"], "TS_OBJECT_SERIES_NOT_FOUND"
        )

    def test_the_route_project_must_own_the_object_before_a_series_resolves(self):
        mismatched = self.create_definition(
            root=(
                f"/api/projects/{self.project['id']}/linkable-objects/"
                f"{self.other_object['id']}/time-series"
            )
        )

        self.assertEqual(mismatched.status_code, 404, mismatched.text)
        self.assertEqual(
            mismatched.json()["code"], "TS_COMPAT_PROJECT_CONTEXT_MISMATCH"
        )

    def test_the_detail_answers_only_under_the_root_that_owns_the_series(self):
        signal_id = self.create_definition().json()["object_series"]["signal_id"]

        detail = self.client.get(f"{self.root}/object-series/{signal_id}")
        from_another_object = self.client.get(
            f"/api/projects/{self.other_project['id']}/linkable-objects/"
            f"{self.other_object['id']}/time-series/object-series/{signal_id}"
        )
        from_the_global_catalog = self.client.get(
            f"/api/time-series/catalog/inputs/{signal_id}"
        )
        global_list = self.client.get("/api/time-series/catalog/inputs")

        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["object_series"]["signal_id"], signal_id)
        self.assertEqual(
            detail.json()["object_series"]["metadata"],
            {"tags": ["operacion", "diario"], "external_reference": "forecast:nodo-7"},
        )
        self.assertEqual(from_another_object.status_code, 404, from_another_object.text)
        self.assertEqual(
            from_another_object.json()["code"], "TS_OBJECT_SERIES_NOT_FOUND"
        )
        self.assertEqual(from_the_global_catalog.status_code, 404)
        self.assertEqual(global_list.json()["items"], [])

    def patch(self, signal_id, payload, *, if_match=None):
        headers = dict(csrf_headers(self.client))
        if if_match is not None:
            headers["If-Match"] = if_match
        return self.client.patch(
            f"{self.root}/object-series/{signal_id}", json=payload, headers=headers
        )

    def test_the_patch_touches_only_the_editable_face_under_if_match(self):
        created = self.create_definition()
        signal_id = created.json()["object_series"]["signal_id"]

        renamed = self.patch(
            signal_id,
            {
                "display_name": "Precio local revisado",
                "description": "Pronostico revisado",
                "metadata": {"tags": ["operacion"]},
            },
            if_match=created.headers["etag"],
        )

        self.assertEqual(renamed.status_code, 200, renamed.text)
        series = renamed.json()["object_series"]
        self.assertEqual(series["display_name"], "Precio local revisado")
        self.assertEqual(series["metadata"], {"tags": ["operacion"]})
        self.assertEqual(series["resource_version"], 2)
        self.assertEqual(
            renamed.headers["etag"], f'"ts-object-series-{signal_id}-v2"'
        )
        # Editing the visible face never creates another revision (chapter 7.5).
        self.assertIsNone(series["current_revision"])
        self.assertEqual(series["building_revision"]["revision_number"], 1)
        self.assertEqual(series["object_series_key"], "local_price_forecast")

    def test_the_patch_needs_a_precondition_and_refuses_a_stale_one(self):
        created = self.create_definition()
        signal_id = created.json()["object_series"]["signal_id"]

        unconditional = self.patch(signal_id, {"display_name": "Sin precondicion"})
        stale = self.patch(
            signal_id,
            {"display_name": "Precondicion vieja"},
            if_match='"ts-object-series-1-v99"',
        )

        self.assertEqual(unconditional.status_code, 428, unconditional.text)
        self.assertEqual(
            unconditional.json()["code"], "TS_INGEST_PRECONDITION_REQUIRED"
        )
        self.assertEqual(stale.status_code, 412, stale.text)
        self.assertEqual(stale.json()["code"], "TS_INGEST_PRECONDITION_CHANGED")
        self.assertEqual(
            self.client.get(f"{self.root}/object-series/{signal_id}")
            .json()["object_series"]["display_name"],
            "Precio local previsto",
        )

    def test_no_patch_reassigns_the_owner_or_the_immutable_identity(self):
        created = self.create_definition()
        signal_id = created.json()["object_series"]["signal_id"]
        etag = created.headers["etag"]

        refusals = {
            field: self.patch(signal_id, {field: value}, if_match=etag).status_code
            for field, value in (
                ("owner_linkable_object_id", self.other_object["id"]),
                ("object_series_key", "otra_clave"),
                ("semantic_type_key", "natural_inflow"),
                ("unit_key", "m3_per_s"),
                ("series_kind", "catalog"),
            )
        }
        after = self.client.get(f"{self.root}/object-series/{signal_id}").json()

        self.assertEqual(
            refusals,
            {
                "owner_linkable_object_id": 422,
                "object_series_key": 422,
                "semantic_type_key": 422,
                "unit_key": 422,
                "series_kind": 422,
            },
        )
        self.assertEqual(
            after["object_series"]["owner"]["linkable_object_id"], self.object["id"]
        )
        self.assertEqual(after["object_series"]["resource_version"], 1)

    def define(self):
        created = self.create_definition()
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()["object_series"]["signal_id"], created.headers["etag"]

    def target(self, signal_id):
        return f"{self.root}/object-series/{signal_id}"

    def prepare_points(self, signal_id, payload=None):
        return post_json_with_csrf(
            self.client,
            f"{self.target(signal_id)}/revision-ingestions/points",
            POINTS_INGESTION if payload is None else payload,
        )

    def publish(
        self,
        signal_id,
        ingestion,
        *,
        etag,
        idempotency_key="publish-local-price-01",
        body=None,
    ):
        return self.client.post(
            f"{self.target(signal_id)}/revision-ingestions/"
            f"{ingestion['ingestion_id']}/publications",
            json=body
            if body is not None
            else {
                "validation_token": ingestion["validation_token"],
                "confirm": False,
                "reason_code": "forecast_refresh",
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": etag,
                "Idempotency-Key": idempotency_key,
            },
        )

    def test_a_validated_batch_does_not_publish_until_it_is_confirmed(self):
        signal_id, etag = self.define()

        prepared = self.prepare_points(signal_id)

        self.assertEqual(prepared.status_code, 201, prepared.text)
        ingestion = prepared.json()["ingestion"]
        self.assertEqual(ingestion["state"], "ready_to_publish")
        self.assertEqual(ingestion["channel"], "api_points")
        self.assertEqual(ingestion["mode"], "replace_full")
        self.assertEqual(
            ingestion["target"],
            {
                "source_kind": "object_specific",
                "signal_id": signal_id,
                "set_id": prepared.json()["ingestion"]["target"]["set_id"],
            },
        )
        self.assertIsNone(ingestion["base"])
        self.assertEqual(
            ingestion["normalized"]["period_count"], len(POINTS_INGESTION["points"])
        )
        self.assertEqual(ingestion["normalized"]["value_count"], 2)
        self.assertEqual(
            ingestion["normalized"]["coverage_start"], "2026-08-31T04:00:00Z"
        )
        self.assertEqual(
            ingestion["normalized"]["coverage_end"], "2026-08-31T06:00:00Z"
        )
        self.assertTrue(ingestion["normalized"]["content_hash"].startswith("sha256:"))
        self.assertEqual(ingestion["validation"]["error_count"], 0)
        self.assertFalse(ingestion["requires_confirmation"])
        self.assertEqual(
            ingestion["impact"],
            {"bindings_current": 0, "bindings_pinned": 0, "will_become_stale": 0},
        )

        still_unpublished = self.client.get(self.target(signal_id)).json()
        self.assertEqual(
            still_unpublished["object_series"]["availability"], "awaiting_data"
        )
        self.assertIsNone(still_unpublished["object_series"]["current_revision"])

    def test_publishing_seals_the_building_revision_and_opens_binding(self):
        signal_id, etag = self.define()
        ingestion = self.prepare_points(signal_id).json()["ingestion"]

        published = self.publish(signal_id, ingestion, etag=etag)

        self.assertEqual(published.status_code, 201, published.text)
        publication = published.json()["publication"]
        self.assertEqual(publication["outcome"], "new_revision")
        self.assertEqual(publication["revision_number"], 1)
        self.assertEqual(publication["state"], "sealed")
        self.assertEqual(publication["signal_ids"], [signal_id])
        self.assertEqual(publication["availability"], "ready")
        self.assertTrue(publication["binding_ready"])
        self.assertEqual(
            publication["content_hash"], ingestion["normalized"]["content_hash"]
        )
        self.assertEqual(publication["resource_version"], 2)

        detail = self.client.get(self.target(signal_id)).json()["object_series"]
        self.assertEqual(detail["availability"], "ready")
        self.assertEqual(detail["set_status"], "validated")
        self.assertTrue(detail["binding_ready"])
        self.assertEqual(
            detail["current_revision"]["revision_id"], publication["revision_id"]
        )
        self.assertEqual(detail["current_revision"]["period_count"], 2)
        self.assertIsNone(detail["building_revision"])
        # A local series never becomes a global catalog row (chapter 7.3).
        self.assertEqual(
            self.client.get("/api/time-series/catalog/inputs").json()["items"], []
        )

    def test_the_same_ingestion_key_never_creates_a_second_revision(self):
        signal_id, etag = self.define()
        ingestion = self.prepare_points(signal_id).json()["ingestion"]

        first = self.publish(signal_id, ingestion, etag=etag)
        replay = self.publish(signal_id, ingestion, etag=etag)

        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json()["publication"], first.json()["publication"])
        revisions = self.client.get(f"{self.target(signal_id)}/revisions").json()
        self.assertEqual(revisions["summary"], {"total_count": 1})

    def test_the_same_key_with_another_payload_is_an_idempotency_conflict(self):
        signal_id, etag = self.define()
        first_batch = self.prepare_points(signal_id).json()["ingestion"]
        published = self.publish(
            signal_id, first_batch, etag=etag, idempotency_key="publish-local-price-01"
        )
        self.assertEqual(published.status_code, 201, published.text)
        after = self.client.get(self.target(signal_id))
        second_batch = self.prepare_points(
            signal_id,
            {
                **POINTS_INGESTION,
                "expected_base": {
                    "revision_id": published.json()["publication"]["revision_id"],
                    "content_hash": published.json()["publication"]["content_hash"],
                },
                "points": [
                    {
                        "timestamp_start": "2026-08-31T00:00:00-04:00",
                        "duration_seconds": 3600,
                        "values": {"local_price_forecast": {"value": 25.5}},
                    }
                ],
            },
        ).json()["ingestion"]

        conflict = self.publish(
            signal_id,
            second_batch,
            etag=after.headers["etag"],
            idempotency_key="publish-local-price-01",
        )

        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assertEqual(
            conflict.json()["code"], "TS_INGEST_IDEMPOTENCY_CONFLICT"
        )
        self.assertEqual(
            self.client.get(f"{self.target(signal_id)}/revisions").json()["summary"],
            {"total_count": 1},
        )

    def test_knowing_an_ingestion_id_does_not_reach_across_objects(self):
        signal_id, _ = self.define()
        ingestion = self.prepare_points(signal_id).json()["ingestion"]
        other_signal_id = self.create_definition(
            root=(
                f"/api/projects/{self.other_project['id']}/linkable-objects/"
                f"{self.other_object['id']}/time-series"
            )
        ).json()["object_series"]["signal_id"]

        borrowed = self.client.get(
            f"/api/projects/{self.other_project['id']}/linkable-objects/"
            f"{self.other_object['id']}/time-series/object-series/{other_signal_id}"
            f"/revision-ingestions/{ingestion['ingestion_id']}"
        )

        self.assertEqual(borrowed.status_code, 404, borrowed.text)
        self.assertEqual(borrowed.json()["code"], "TS_OBJECT_SERIES_NOT_FOUND")

    def test_a_cancelled_job_previews_no_more_and_never_publishes(self):
        signal_id, etag = self.define()
        ingestion = self.prepare_points(signal_id).json()["ingestion"]

        preview = self.client.get(
            f"{self.target(signal_id)}/revision-ingestions/"
            f"{ingestion['ingestion_id']}/preview?max_rows=1"
        )
        cancelled = delete_with_csrf(
            self.client,
            f"{self.target(signal_id)}/revision-ingestions/"
            f"{ingestion['ingestion_id']}",
        )
        after_cancel = self.publish(signal_id, ingestion, etag=etag)

        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["returned_row_count"], 1)
        self.assertEqual(preview.json()["source_row_count"], 2)
        self.assertEqual(
            preview.json()["rows"][0]["timestamp_start"], "2026-08-31T04:00:00Z"
        )
        self.assertEqual(preview.json()["rows"][0]["value"], 18.4)
        self.assertEqual(cancelled.status_code, 204, cancelled.text)
        self.assertEqual(after_cancel.status_code, 410, after_cancel.text)
        self.assertEqual(
            after_cancel.json()["code"], "TS_INGEST_SESSION_UNAVAILABLE"
        )
        self.assertEqual(
            self.client.get(self.target(signal_id)).json()["object_series"][
                "availability"
            ],
            "awaiting_data",
        )

    def test_a_broken_batch_refuses_with_the_common_problem_document(self):
        signal_id, _ = self.define()

        refused = self.prepare_points(
            signal_id,
            {
                **POINTS_INGESTION,
                "points": [
                    {
                        "timestamp_start": "2026-08-31T00:00:00-04:00",
                        "duration_seconds": 3600,
                        "values": {"local_price_forecast": {"value": "not a number"}},
                    },
                    {
                        "timestamp_start": "2026-08-31T00:30:00-04:00",
                        "duration_seconds": 3600,
                        "values": {"local_price_forecast": {"value": 12.0}},
                    },
                ],
            },
        )

        self.assertEqual(refused.status_code, 422, refused.text)
        self.assertEqual(
            refused.headers["content-type"].split(";")[0], "application/problem+json"
        )
        problem = refused.json()
        self.assertEqual(problem["code"], "TS_INGEST_VALIDATION_FAILED")
        self.assertEqual(problem["status"], 422)
        self.assertEqual(
            problem["error_counts"],
            {"TS_INGEST_VALUE_INVALID": 1, "TS_INGEST_PERIOD_CONFLICT": 1},
        )
        self.assertFalse(problem["errors_truncated"])
        self.assertEqual(
            problem["errors"][0]["location"],
            {
                "record_index": 0,
                "json_pointer": "/points/0/values/local_price_forecast/value",
            },
        )
        self.assertEqual(
            self.client.get(self.target(signal_id)).json()["object_series"][
                "availability"
            ],
            "awaiting_data",
        )

    def test_a_mapping_can_be_corrected_and_the_batch_revalidated(self):
        signal_id, etag = self.define()
        mismapped = {
            **POINTS_INGESTION,
            "points": [
                {
                    "timestamp_start": "2026-08-31T00:00:00-04:00",
                    "duration_seconds": 3600,
                    "values": {"precio_local": {"value": 18.4}},
                },
                {
                    "timestamp_start": "2026-08-31T01:00:00-04:00",
                    "duration_seconds": 3600,
                    "values": {"precio_local": {"value": 19.1}},
                },
            ],
        }

        refused = self.prepare_points(signal_id, mismapped)

        self.assertEqual(refused.status_code, 422, refused.text)
        self.assertEqual(refused.json()["code"], "TS_INGEST_MAPPING_INVALID")
        staged = refused.json()["context"]["ingestion"]
        self.assertEqual(staged["state"], "awaiting_mapping")
        self.assertTrue(staged["capabilities"]["remap"])
        self.assertFalse(staged["capabilities"]["publish"])

        status = self.client.get(
            f"{self.target(signal_id)}/revision-ingestions/{staged['ingestion_id']}"
        )
        self.assertEqual(status.status_code, 200, status.text)
        self.assertEqual(status.json()["ingestion"]["state"], "awaiting_mapping")
        self.assertEqual(status.json()["ingestion"]["validation"]["error_count"], 2)

        remapped = put_json_with_csrf(
            self.client,
            f"{self.target(signal_id)}/revision-ingestions/"
            f"{staged['ingestion_id']}/mapping",
            {"value_keys": {"precio_local": "local_price_forecast"}},
        )

        self.assertEqual(remapped.status_code, 200, remapped.text)
        fixed = remapped.json()["ingestion"]
        self.assertEqual(fixed["state"], "ready_to_publish")
        self.assertEqual(fixed["normalized"]["period_count"], 2)
        self.assertTrue(fixed["capabilities"]["publish"])

        published = self.publish(signal_id, fixed, etag=etag)
        self.assertEqual(published.status_code, 201, published.text)
        self.assertEqual(
            published.json()["publication"]["content_hash"],
            fixed["normalized"]["content_hash"],
        )

    def test_a_second_load_revises_the_same_identity_and_previews_it(self):
        signal_id, etag = self.define()
        first = self.publish(
            signal_id, self.prepare_points(signal_id).json()["ingestion"], etag=etag
        ).json()["publication"]
        after_first = self.client.get(self.target(signal_id))

        second_batch = self.prepare_points(
            signal_id,
            {
                **POINTS_INGESTION,
                "expected_base": {
                    "revision_id": first["revision_id"],
                    "content_hash": first["content_hash"],
                },
                "points": [
                    {
                        "timestamp_start": "2026-08-31T00:00:00-04:00",
                        "duration_seconds": 3600,
                        "values": {"local_price_forecast": {"value": 21.0}},
                    },
                    {
                        "timestamp_start": "2026-08-31T01:00:00-04:00",
                        "duration_seconds": 3600,
                        "values": {"local_price_forecast": {"value": 22.0}},
                    },
                ],
            },
        ).json()["ingestion"]
        second = self.publish(
            signal_id,
            second_batch,
            etag=after_first.headers["etag"],
            idempotency_key="publish-local-price-02",
        )

        self.assertEqual(second.status_code, 201, second.text)
        publication = second.json()["publication"]
        self.assertEqual(publication["revision_number"], 2)
        self.assertNotEqual(publication["revision_id"], first["revision_id"])
        self.assertEqual(publication["signal_ids"], [signal_id])

        history = self.client.get(f"{self.target(signal_id)}/revisions").json()
        self.assertEqual(history["summary"], {"total_count": 2})
        self.assertEqual([item["number"] for item in history["items"]], [2, 1])
        self.assertEqual([item["state"] for item in history["items"]], ["sealed"] * 2)

        preview = self.client.get(
            f"{self.target(signal_id)}/preview"
            f"?revision_id={publication['revision_id']}"
            "&from=2026-08-31T00:00:00Z&to=2026-08-31T23:00:00Z&max_points=500"
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["source_point_count"], 2)
        self.assertEqual(
            [point["value"] for point in preview.json()["points"]], [21.0, 22.0]
        )
        self.assertEqual(preview.json()["unit"]["key"], "usd_per_mwh")

        # A superseded revision stays readable at its exact id (chapter 2.3).
        older = self.client.get(
            f"{self.target(signal_id)}/preview"
            f"?revision_id={first['revision_id']}"
            "&from=2026-08-31T00:00:00Z&to=2026-08-31T23:00:00Z&max_points=500"
        )
        self.assertEqual(
            [point["value"] for point in older.json()["points"]], [18.4, 19.1]
        )

    def test_republishing_the_same_content_changes_nothing(self):
        signal_id, etag = self.define()
        first = self.publish(
            signal_id, self.prepare_points(signal_id).json()["ingestion"], etag=etag
        ).json()["publication"]
        after_first = self.client.get(self.target(signal_id))

        identical = self.prepare_points(
            signal_id,
            {
                **POINTS_INGESTION,
                "expected_base": {
                    "revision_id": first["revision_id"],
                    "content_hash": first["content_hash"],
                },
            },
        ).json()["ingestion"]
        republished = self.publish(
            signal_id,
            identical,
            etag=after_first.headers["etag"],
            idempotency_key="publish-local-price-identical",
        )

        self.assertEqual(republished.status_code, 200, republished.text)
        self.assertEqual(republished.json()["publication"]["outcome"], "unchanged")
        self.assertEqual(
            republished.json()["publication"]["revision_id"], first["revision_id"]
        )
        self.assertEqual(
            self.client.get(f"{self.target(signal_id)}/revisions").json()["summary"],
            {"total_count": 1},
        )

    def associate_a_generic_signal(self):
        """Give the object one catalog association, through its own API."""

        receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Inputs 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[
                {
                    "series_key": "energy_price",
                    "display_name": "Precio de energia",
                    "semantic_type_key": "energy_price",
                    "unit_key": "usd_per_mwh",
                    "signal_role": "input",
                    "aggregation": "mean",
                }
            ],
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
        request = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "op-add-price",
                    "action": "add",
                    "signal_id": receipt["signal_ids"]["energy_price"],
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
        committed = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **request,
                "prevalidation_token": prevalidation["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidation["commit_etag"],
                "Idempotency-Key": "associate-price-01",
            },
        )
        self.assertEqual(committed.status_code, 201, committed.text)
        return receipt["signal_ids"]["energy_price"]

    def test_the_contextual_list_unions_both_kinds_under_one_discriminator(self):
        generic_signal_id = self.associate_a_generic_signal()
        local_signal_id, etag = self.define()
        self.publish(
            local_signal_id,
            self.prepare_points(local_signal_id).json()["ingestion"],
            etag=etag,
        )

        listed = self.client.get(self.root)

        self.assertEqual(listed.status_code, 200, listed.text)
        page = listed.json()
        rows = {item["source_kind"]: item for item in page["items"]}
        self.assertEqual(sorted(rows), ["catalog", "object_specific"])
        self.assertEqual(rows["catalog"]["signal_id"], generic_signal_id)
        self.assertEqual(rows["object_specific"]["signal_id"], local_signal_id)
        self.assertEqual(page["summary"], {"total_count": 2})
        self.assertEqual(page["page"]["limit"], 50)
        for item in page["items"]:
            self.assertNotIn("points", item)
            self.assertNotIn("values", item)
            self.assertNotIn("consumers", item)
            self.assertIn("semantic_type_key", item)
            self.assertIn("current_revision", item)
            self.assertIn("binding_state", item)
            self.assertIn("capabilities", item)
            self.assertIn("links", item)
        self.assertEqual(
            rows["object_specific"]["current_revision"]["period_count"], 2
        )
        self.assertEqual(rows["object_specific"]["availability"], "ready")
        self.assertEqual(rows["catalog"]["availability"], "ready")

    def test_the_contextual_list_filters_by_kind_type_and_text(self):
        self.associate_a_generic_signal()
        local_signal_id, _ = self.define()

        only_local = self.client.get(f"{self.root}?kind=object_specific")
        only_catalog = self.client.get(f"{self.root}?kind=catalog")
        by_role = self.client.get(f"{self.root}?compatible_role_key=grid_import_price")
        by_missing_role = self.client.get(f"{self.root}?compatible_role_key=load_demand")
        by_text = self.client.get(f"{self.root}?q=previsto")
        awaiting = self.client.get(f"{self.root}?availability=awaiting_data")

        self.assertEqual(
            [item["signal_id"] for item in only_local.json()["items"]],
            [local_signal_id],
        )
        self.assertEqual(
            [item["source_kind"] for item in only_catalog.json()["items"]],
            ["catalog"],
        )
        self.assertEqual(len(by_role.json()["items"]), 2)
        self.assertEqual(by_missing_role.json()["items"], [])
        self.assertEqual(
            [item["signal_id"] for item in by_text.json()["items"]], [local_signal_id]
        )
        self.assertEqual(
            [item["signal_id"] for item in awaiting.json()["items"]], [local_signal_id]
        )

    def test_the_contextual_list_pages_with_the_shared_cursor(self):
        self.associate_a_generic_signal()
        self.define()

        first = self.client.get(f"{self.root}?limit=1")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertTrue(first.json()["page"]["has_more"])
        second = self.client.get(
            f"{self.root}?limit=1&cursor={first.json()['page']['next_cursor']}"
        )
        whole = self.client.get(self.root)

        self.assertEqual(second.status_code, 200, second.text)
        self.assertFalse(second.json()["page"]["has_more"])
        self.assertEqual(
            [
                item["signal_id"]
                for item in first.json()["items"] + second.json()["items"]
            ],
            [item["signal_id"] for item in whole.json()["items"]],
        )
        self.assertEqual(
            self.client.get(f"{self.root}?limit=1&cursor=not-a-cursor").status_code,
            400,
        )

    def test_an_interrupted_publication_leaves_no_partial_revision(self):
        signal_id, etag = self.define()
        ingestion = self.prepare_points(signal_id).json()["ingestion"]

        with patch.object(
            AnalystStore,
            "_stream_canonical_content_hash",
            side_effect=RuntimeError("the writer died mid publication"),
        ):
            with self.assertRaises(RuntimeError):
                self.publish(signal_id, ingestion, etag=etag)

        detail = self.client.get(self.target(signal_id)).json()["object_series"]
        self.assertEqual(detail["availability"], "awaiting_data")
        self.assertIsNone(detail["current_revision"])
        self.assertEqual(detail["building_revision"]["revision_number"], 1)
        history = self.client.get(f"{self.target(signal_id)}/revisions").json()
        self.assertEqual(history["summary"], {"total_count": 1})
        self.assertEqual(history["items"][0]["state"], "building")
        self.assertEqual(
            self.store.connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM {self.store.canonical_table_names()['time_series_periods']}
                """
            ).fetchone()["total"],
            0,
        )

        # The job survived the interruption and still publishes cleanly.
        recovered = self.publish(
            signal_id,
            ingestion,
            etag=etag,
            idempotency_key="publish-after-interruption",
        )
        self.assertEqual(recovered.status_code, 201, recovered.text)
        self.assertEqual(
            self.client.get(self.target(signal_id)).json()["object_series"][
                "availability"
            ],
            "ready",
        )

    def test_a_useless_type_role_and_object_combination_is_refused_up_front(self):
        refused = self.create_definition(
            payload={
                **DEFINITION,
                "object_series_key": "caudal_local",
                "semantic_type_key": "natural_inflow",
                "unit_key": "m3_per_s",
                "intended_binding_role_key": "natural_inflow",
            }
        )

        self.assertEqual(refused.status_code, 422, refused.text)
        self.assertEqual(refused.json()["code"], "TS_COMPAT_ROLE_NOT_ALLOWED")
        self.assertEqual(self.client.get(self.root).json()["items"], [])

    def test_the_payload_is_never_a_source_of_authority(self):
        refusals = {
            field: self.create_definition(
                payload={**DEFINITION, field: value}
            ).status_code
            for field, value in (
                ("project_id", self.other_project["id"]),
                ("owner_linkable_object_id", self.other_object["id"]),
                ("entity_type", "global_signal_slot"),
                ("entity_id", self.other_object["id"]),
                ("series_kind", "catalog"),
            )
        }

        self.assertEqual(
            refusals,
            {
                "project_id": 422,
                "owner_linkable_object_id": 422,
                "entity_type": 422,
                "entity_id": 422,
                "series_kind": 422,
            },
        )
        self.assertEqual(self.client.get(self.root).json()["items"], [])

    def test_an_external_identity_never_reaches_the_object_root(self):
        self.store.create_user(
            email="client@example.local",
            display_name="Client",
            role="external",
            password_hash=hash_password("client pass"),
        )
        signal_id, _ = self.define()
        self.assertEqual(
            login_json_with_csrf(
                self.client, "client@example.local", "client pass"
            ).status_code,
            200,
        )

        listed = self.client.get(self.root)
        detail = self.client.get(self.target(signal_id))
        created = self.create_definition(
            payload={**DEFINITION, "object_series_key": "otra_serie"}
        )

        self.assertEqual(listed.status_code, 404, listed.text)
        self.assertEqual(detail.status_code, 404, detail.text)
        self.assertEqual(created.status_code, 404, created.text)

    def test_a_local_key_is_refused_once_it_is_used_by_the_object(self):
        first = self.create_definition()
        self.assertEqual(first.status_code, 201, first.text)

        again = self.create_definition()

        self.assertEqual(again.status_code, 409, again.text)
        self.assertEqual(again.json()["code"], "TS_OBJECT_SERIES_KEY_CONFLICT")


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL contract tests",
)
class PostgresObjectSpecificSeriesApiTests(ObjectSpecificSeriesApiTests):
    """Run the same object-scoped contract on the production-reference engine."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        suffix = uuid.uuid4().hex[:10]
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.user = self.store.create_user(
            email=f"ts7-010-{suffix}@example.local",
            display_name="PostgreSQL Analyst",
            role="analyst",
            password_hash=hash_password("postgres analyst pass"),
        )
        login = login_json_with_csrf(
            self.client, self.user["email"], "postgres analyst pass"
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.project = self.store.create_project(name=f"Cuenca Norte {suffix}")
        self.other_project = self.store.create_project(name=f"Cuenca Sur {suffix}")
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        self.other_object = self.store.ensure_global_signal_slot(
            project_id=self.other_project["id"], display_name="Sistema sur"
        )

    def tearDown(self):
        try:
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()

    def test_an_interrupted_publication_leaves_no_partial_revision(self):
        # The interruption is proven on SQLite; on PostgreSQL the enclosing
        # rollback transaction of this fixture cannot survive the failure it
        # would have to provoke.
        self.skipTest("covered by the SQLite contract")


if __name__ == "__main__":
    unittest.main()
