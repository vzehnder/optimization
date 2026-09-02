"""TS7-012 direct bindings, structural read separation and archival."""

import os
import unittest
import uuid

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.time_series_canonical import CanonicalRevisionError, canonical_space_table_name
from tests.auth_test_helpers import csrf_headers, login_json_with_csrf, post_json_with_csrf
from tests.test_ts7_010_object_specific_series import DEFINITION, POINTS_INGESTION


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class ObjectSpecificBindingAndArchiveApiTests(unittest.TestCase):
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
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )

    def tearDown(self):
        self.store.close()

    @property
    def object_root(self):
        return (
            f"/api/projects/{self.project['id']}/linkable-objects/"
            f"{self.object['id']}/time-series"
        )

    @property
    def variant_root(self):
        return (
            f"/api/scenarios/{self.scenario['id']}/case-variants/"
            f"{self.variant['id']}"
        )

    def create_and_publish_local_series(self):
        created = self.client.post(
            f"{self.object_root}/object-series",
            json=DEFINITION,
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": f"define-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        signal_id = created.json()["object_series"]["signal_id"]
        prepared = post_json_with_csrf(
            self.client,
            f"{self.object_root}/object-series/{signal_id}"
            "/revision-ingestions/points",
            POINTS_INGESTION,
        )
        self.assertEqual(prepared.status_code, 201, prepared.text)
        ingestion = prepared.json()["ingestion"]
        published = self.client.post(
            f"{self.object_root}/object-series/{signal_id}/revision-ingestions/"
            f"{ingestion['ingestion_id']}/publications",
            json={
                "validation_token": ingestion["validation_token"],
                "confirm": False,
                "reason_code": "forecast_refresh",
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": created.headers["etag"],
                "Idempotency-Key": f"publish-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(published.status_code, 201, published.text)
        return signal_id, published.json()["publication"]

    def binding_request(self, signal_id, publication):
        return {
            "expected_bindings_revision": 0,
            "operations": [
                {
                    "client_operation_id": "bind-local-price",
                    "action": "create",
                    "linkable_object_id": self.object["id"],
                    "binding_role_key": "grid_import_price",
                    "signal_id": signal_id,
                    "revision": {
                        "mode": "current",
                        "revision_id": publication["revision_id"],
                        "content_hash": publication["content_hash"],
                    },
                    "catalog_association_id": None,
                    "reason_code": "variant_input_selected",
                }
            ],
        }

    def test_a_sealed_local_series_binds_directly_to_its_owner(self):
        signal_id, publication = self.create_and_publish_local_series()
        request = self.binding_request(signal_id, publication)

        prevalidated = post_json_with_csrf(
            self.client,
            f"{self.variant_root}/time-series-binding-prevalidations",
            request,
        )
        self.assertEqual(prevalidated.status_code, 200, prevalidated.text)
        self.assertTrue(prevalidated.json()["can_commit"], prevalidated.text)
        committed = self.client.post(
            f"{self.variant_root}/time-series-binding-batches",
            json={
                **request,
                "prevalidation_token": prevalidated.json()["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidated.json()["commit_etag"],
                "Idempotency-Key": "bind-local-price-01",
            },
        )
        self.assertEqual(committed.status_code, 201, committed.text)
        binding_id = committed.json()["operations"][0]["binding_id"]

        detail = self.client.get(
            f"{self.variant_root}/time-series-bindings/{binding_id}"
        )

        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["state"], "valid_current")
        self.assertEqual(
            detail.json()["bound_content_hash"], publication["content_hash"]
        )
        self.assertEqual(detail.json()["source_kind"], "object_specific")
        self.assertEqual(
            detail.json()["source_owner_linkable_object_id"], self.object["id"]
        )
        self.assertIsNone(detail.json()["catalog_association_id"])
        context = self.client.get(self.object_root)
        self.assertEqual(context.status_code, 200, context.text)
        local = next(
            item
            for item in context.json()["items"]
            if item["signal_id"] == signal_id
        )
        self.assertEqual(local["binding_state"], "bound")

    def test_the_canonical_query_layer_separates_catalog_and_local_signals(self):
        local_signal_id, _ = self.create_and_publish_local_series()
        generic = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Precios compartidos",
            data_class_key="forecast",
            timezone="UTC",
            signals=[
                {
                    "series_key": "shared_price_forecast",
                    "display_name": "Precio compartido",
                    "semantic_type_key": "energy_price",
                    "unit_key": "usd_per_mwh",
                    "signal_role": "input",
                    "aggregation": "mean",
                }
            ],
            periods=[
                {
                    "timestamp_start": "2026-08-31T04:00:00",
                    "timestamp_end": "2026-08-31T05:00:00",
                    "duration_hours": 1.0,
                }
            ],
            values={"shared_price_forecast": [21.0]},
            actor="analyst@example.local",
        )
        generic_signal_id = generic["signal_ids"]["shared_price_forecast"]
        catalog_view = canonical_space_table_name(
            "catalog_time_series_signals", self.store.database_backend
        )
        local_view = canonical_space_table_name(
            "object_specific_time_series_signals", self.store.database_backend
        )

        catalog_ids = {
            int(row["id"])
            for row in self.store.connection.execute(
                f"SELECT id FROM {catalog_view}"
            ).fetchall()
        }
        local_rows = self.store.connection.execute(
            f"SELECT id, owner_linkable_object_id FROM {local_view}"
        ).fetchall()

        self.assertEqual(catalog_ids, {generic_signal_id})
        self.assertEqual(
            [
                (int(row["id"]), int(row["owner_linkable_object_id"]))
                for row in local_rows
            ],
            [(local_signal_id, self.object["id"])],
        )

    def test_archiving_preserves_the_revision_preview_and_past_binding(self):
        signal_id, publication = self.create_and_publish_local_series()
        request = self.binding_request(signal_id, publication)
        prevalidated = post_json_with_csrf(
            self.client,
            f"{self.variant_root}/time-series-binding-prevalidations",
            request,
        ).json()
        committed = self.client.post(
            f"{self.variant_root}/time-series-binding-batches",
            json={
                **request,
                "prevalidation_token": prevalidated["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidated["commit_etag"],
                "Idempotency-Key": "bind-before-archive-01",
            },
        )
        self.assertEqual(committed.status_code, 201, committed.text)
        binding_id = committed.json()["operations"][0]["binding_id"]
        before_archive = self.client.get(
            f"{self.object_root}/object-series/{signal_id}"
        )

        archived = self.client.post(
            f"{self.object_root}/object-series/{signal_id}/archive",
            json={
                "reason_code": "source_retired",
                "reason_text": "The local forecast is no longer maintained.",
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": before_archive.headers["etag"],
            },
        )

        self.assertEqual(archived.status_code, 200, archived.text)
        series = archived.json()["object_series"]
        self.assertEqual(series["availability"], "archived")
        self.assertFalse(series["binding_ready"])
        self.assertEqual(
            series["current_revision"]["revision_id"], publication["revision_id"]
        )
        history = self.client.get(
            f"{self.object_root}/object-series/{signal_id}/revisions"
        )
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()["summary"], {"total_count": 1})
        preview = self.client.get(
            f"{self.object_root}/object-series/{signal_id}/preview"
            f"?revision_id={publication['revision_id']}"
            "&from=2026-08-31T00:00:00Z&to=2026-08-31T23:00:00Z"
            "&max_points=500"
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(
            [point["value"] for point in preview.json()["points"]], [18.4, 19.1]
        )
        binding = self.client.get(
            f"{self.variant_root}/time-series-bindings/{binding_id}"
        )
        self.assertEqual(binding.status_code, 200, binding.text)
        self.assertEqual(binding.json()["status"], "active")
        self.assertEqual(binding.json()["state"], "invalid")
        self.assertEqual(binding.json()["set_revision_id"], publication["revision_id"])
        context = self.client.get(self.object_root)
        local = next(
            item
            for item in context.json()["items"]
            if item["signal_id"] == signal_id
        )
        self.assertEqual(
            local["capabilities"],
            {
                "edit_definition": False,
                "ingest_points": False,
                "preview": True,
                "bind": False,
                "archive": False,
            },
        )
        patch = self.client.patch(
            f"{self.object_root}/object-series/{signal_id}",
            json={"display_name": "A name that must not be written"},
            headers={
                **csrf_headers(self.client),
                "If-Match": archived.headers["etag"],
            },
        )
        ingestion = post_json_with_csrf(
            self.client,
            f"{self.object_root}/object-series/{signal_id}"
            "/revision-ingestions/points",
            {
                **POINTS_INGESTION,
                "expected_base": {
                    "revision_id": publication["revision_id"],
                    "content_hash": publication["content_hash"],
                },
            },
        )
        self.assertEqual((patch.status_code, ingestion.status_code), (404, 404))
        self.assertEqual(patch.json()["code"], "TS_OBJECT_SERIES_NOT_FOUND")
        self.assertEqual(ingestion.json()["code"], "TS_OBJECT_SERIES_NOT_FOUND")

    def test_no_catalog_filter_or_candidate_route_can_surface_a_local_series(self):
        signal_id, _ = self.create_and_publish_local_series()
        catalog_queries = [
            {},
            {"q": "local price forecast"},
            {"semantic_type_key": "energy_price"},
            {"data_class_key": "forecast", "unit_key": "usd_per_mwh"},
            {"owner_project_id": self.project["id"], "visibility_scope": "project"},
            {"set_status": "validated", "signal_status": "active"},
            {
                "covers_from": "2026-08-31T04:00:00Z",
                "covers_to": "2026-08-31T06:00:00Z",
                "resolution_seconds_min": 3600,
                "resolution_seconds_max": 3600,
            },
            {
                "context_linkable_object_id": self.object["id"],
                "context_binding_role_key": "grid_import_price",
                "context_usage": "association",
                "compatibility": "allowed",
            },
        ]

        for query in catalog_queries:
            with self.subTest(query=query):
                response = self.client.get(
                    "/api/time-series/catalog/inputs", params=query
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertNotIn(
                    signal_id,
                    [item["signal_id"] for item in response.json()["items"]],
                )

        detail = self.client.get(f"/api/time-series/catalog/inputs/{signal_id}")
        candidates = self.client.get(
            f"/api/time-series/catalog/inputs/{signal_id}/object-candidates",
            params={
                "target_project_id": self.project["id"],
                "binding_role_key": "grid_import_price",
                "usage": "association",
                "include_denied": "true",
            },
        )
        self.assertEqual(detail.status_code, 404, detail.text)
        self.assertEqual(candidates.status_code, 404, candidates.text)

    def test_a_definition_without_a_sealed_revision_is_not_selectable(self):
        created = self.client.post(
            f"{self.object_root}/object-series",
            json=DEFINITION,
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": "define-awaiting-data-01",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        series = created.json()["object_series"]
        request = self.binding_request(
            series["signal_id"],
            {
                "revision_id": series["building_revision"]["revision_id"],
                "content_hash": "sha256:" + "0" * 64,
            },
        )

        prevalidated = post_json_with_csrf(
            self.client,
            f"{self.variant_root}/time-series-binding-prevalidations",
            request,
        )

        self.assertEqual(prevalidated.status_code, 200, prevalidated.text)
        self.assertFalse(prevalidated.json()["can_commit"])
        self.assertEqual(
            prevalidated.json()["operations"][0]["errors"][0]["code"],
            "TS_COMPAT_SIGNAL_UNAVAILABLE",
        )

    def test_a_local_series_refuses_a_binding_to_any_object_but_its_owner(self):
        signal_id, publication = self.create_and_publish_local_series()
        another_object = self.store.ensure_project_component(
            project_id=self.project["id"],
            component_key="load_a",
            component_type="load",
            display_name="Carga A",
        )
        request = self.binding_request(signal_id, publication)
        request["operations"][0]["linkable_object_id"] = another_object["id"]

        prevalidated = post_json_with_csrf(
            self.client,
            f"{self.variant_root}/time-series-binding-prevalidations",
            request,
        )

        self.assertEqual(prevalidated.status_code, 200, prevalidated.text)
        self.assertFalse(prevalidated.json()["can_commit"])
        self.assertIn(
            "TS_COMPAT_OBJECT_OWNER_MISMATCH",
            {
                error["code"]
                for error in prevalidated.json()["operations"][0]["errors"]
            },
        )

    def test_the_catalog_writer_cannot_reuse_a_local_identity(self):
        signal_id, publication = self.create_and_publish_local_series()
        local = self.client.get(
            f"{self.object_root}/object-series/{signal_id}"
        ).json()["object_series"]

        with self.assertRaises(CanonicalRevisionError) as raised:
            self.store.publish_canonical_set_revision(
                project_id=self.project["id"],
                set_id=local["set_id"],
                name=local["object_series_key"],
                data_class_key="forecast",
                timezone="America/Santiago",
                signals=[
                    {
                        "series_key": local["object_series_key"],
                        "display_name": local["display_name"],
                        "semantic_type_key": "energy_price",
                        "unit_key": "usd_per_mwh",
                        "signal_role": "input",
                        "aggregation": "mean",
                    }
                ],
                periods=[
                    {
                        "timestamp_start": "2026-08-31T04:00:00",
                        "timestamp_end": "2026-08-31T05:00:00",
                        "duration_hours": 1.0,
                    }
                ],
                values={local["object_series_key"]: [33.0]},
                actor="analyst@example.local",
            )

        self.assertEqual(raised.exception.code, "TS_SET_KIND_MISMATCH")
        unchanged = self.client.get(
            f"{self.object_root}/object-series/{signal_id}"
        ).json()["object_series"]
        self.assertEqual(unchanged["source_kind"], "object_specific")
        self.assertEqual(
            unchanged["current_revision"]["revision_id"],
            publication["revision_id"],
        )

    def test_a_catalog_copy_has_a_new_identity_and_keeps_the_local_source(self):
        local_signal_id, publication = self.create_and_publish_local_series()
        local = self.client.get(
            f"{self.object_root}/object-series/{local_signal_id}"
        ).json()["object_series"]

        copied = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Copia catalogada del precio local",
            data_class_key="forecast",
            timezone="UTC",
            signals=[
                {
                    "series_key": "catalog_price_copy",
                    "display_name": "Copia catalogada",
                    "semantic_type_key": "energy_price",
                    "unit_key": "usd_per_mwh",
                    "signal_role": "input",
                    "aggregation": "mean",
                }
            ],
            periods=[
                {
                    "timestamp_start": "2026-08-31T04:00:00",
                    "timestamp_end": "2026-08-31T05:00:00",
                    "duration_hours": 1.0,
                },
                {
                    "timestamp_start": "2026-08-31T05:00:00",
                    "timestamp_end": "2026-08-31T06:00:00",
                    "duration_hours": 1.0,
                },
            ],
            values={"catalog_price_copy": [18.4, 19.1]},
            lineage=[
                {
                    "series_key": "catalog_price_copy",
                    "source_set_revision_id": publication["revision_id"],
                    "source_signal_id": local_signal_id,
                    "lineage_kind": "object_specific_catalog_copy",
                    "source_content_hash": publication["content_hash"].removeprefix(
                        "sha256:"
                    ),
                    "source_owner_linkable_object_id": self.object["id"],
                    "target_owner_linkable_object_id": None,
                    "reason_code": "catalog_copy_requested",
                }
            ],
            actor="analyst@example.local",
        )
        copied_signal_id = copied["signal_ids"]["catalog_price_copy"]

        self.assertNotEqual(copied["set_id"], local["set_id"])
        self.assertNotEqual(copied_signal_id, local_signal_id)
        catalog_detail = self.client.get(
            f"/api/time-series/catalog/inputs/{copied_signal_id}"
        )
        self.assertEqual(catalog_detail.status_code, 200, catalog_detail.text)
        self.assertEqual(
            catalog_detail.json()["lineage_summary"],
            [{"kind": "object_specific_catalog_copy", "occurrence_count": 1}],
        )
        unchanged = self.client.get(
            f"{self.object_root}/object-series/{local_signal_id}"
        ).json()["object_series"]
        self.assertEqual(unchanged["source_kind"], "object_specific")
        self.assertEqual(unchanged["owner"]["linkable_object_id"], self.object["id"])


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL contract tests",
)
class PostgresObjectSpecificBindingAndArchiveApiTests(
    ObjectSpecificBindingAndArchiveApiTests
):
    """Mirror the complete HTTP/query contract on the reference engine."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        suffix = uuid.uuid4().hex[:10]
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.user = self.store.create_user(
            email=f"ts7-012-{suffix}@example.local",
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
