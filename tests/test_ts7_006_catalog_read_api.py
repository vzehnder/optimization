"""TS7-006 HTTP read surface for the signal-first global catalog."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from tests.auth_test_helpers import login_json_with_csrf


SIGNALS = [
    {
        "series_key": "energy_price",
        "display_name": "Precio de energia",
        "semantic_type_key": "energy_price",
        "unit_key": "usd_per_mwh",
        "signal_role": "input",
        "aggregation": "mean",
    },
    {
        "series_key": "inflow_node_a",
        "display_name": "Caudal afluente Nodo A",
        "semantic_type_key": "hydro_inflow",
        "unit_key": "m3_per_s",
        "signal_role": "input",
        "aggregation": "mean",
    },
]


def hourly_periods(count: int) -> list[dict]:
    return [
        {
            "timestamp_start": f"2026-01-01T{index:02d}:00:00",
            "timestamp_end": f"2026-01-01T{index + 1:02d}:00:00",
            "duration_hours": 1.0,
        }
        for index in range(count)
    ]


class CatalogInputsApiTests(unittest.TestCase):
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
        self.assertEqual(login.status_code, 200)
        self.project = self.store.create_project(name="Cuenca Norte")
        self.receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name="Inputs 2026",
            version_label="v1",
            description="Senales operativas",
            data_class_key="real",
            timezone="UTC",
            signals=SIGNALS,
            periods=hourly_periods(3),
            values={
                "energy_price": [70.0, 71.0, 72.0],
                "inflow_node_a": [10.0, 11.0, 12.0],
            },
            actor="analyst@example.local",
        )

    def tearDown(self):
        self.store.close()

    def test_internal_list_is_signal_first_and_exposes_the_required_summary(self):
        response = self.client.get("/api/time-series/catalog/inputs")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["page"], {
            "limit": 50,
            "has_more": False,
            "next_cursor": None,
        })
        self.assertEqual(payload["meta"]["section"], "inputs")
        self.assertEqual(len(payload["items"]), 2)
        by_key = {item["identity"]["series_key"]: item for item in payload["items"]}
        price = by_key["energy_price"]
        self.assertEqual(price["entry_kind"], "input")
        self.assertEqual(price["owner"], {
            "project_id": self.project["id"],
            "project_name": "Cuenca Norte",
        })
        self.assertEqual(price["set"]["visibility_scope"], "project")
        self.assertEqual(price["classification"], {
            "semantic_type_key": "energy_price",
            "data_class_key": "real",
            "unit_key": "usd_per_mwh",
        })
        self.assertEqual(price["coverage_summary"], {
            "start": "2026-01-01T00:00:00",
            "end": "2026-01-01T03:00:00",
            "period_count": 3,
            "nominal_resolution_seconds": 3600.0,
            "minimum_resolution_seconds": 3600.0,
            "maximum_resolution_seconds": 3600.0,
            "regularity": "regular",
            "source_timezone": "UTC",
        })

    def test_list_row_carries_set_identity_revision_date_and_source_timezone(self):
        item = next(
            item
            for item in self.client.get("/api/time-series/catalog/inputs").json()["items"]
            if item["identity"]["series_key"] == "energy_price"
        )

        self.assertEqual(item["identity"]["description"], "")
        self.assertEqual(
            item["set"],
            {
                "id": self.receipt["set_id"],
                "name": "Inputs 2026",
                "version_number": 1,
                "version_label": "v1",
                "description": "Senales operativas",
                "status": "validated",
                "visibility_scope": "project",
            },
        )
        self.assertTrue(item["current_revision"]["created_at"])
        self.assertEqual(item["coverage_summary"]["source_timezone"], "UTC")

    def test_combinable_filters_match_the_canonical_signal_set(self):
        other_project = self.store.create_project(name="Cuenca Sur")
        self.store.publish_canonical_set_revision(
            project_id=other_project["id"],
            name="Other inputs",
            data_class_key="real",
            signals=[SIGNALS[1]],
            periods=hourly_periods(3),
            values={"inflow_node_a": [20.0, 21.0, 22.0]},
            actor="analyst@example.local",
        )

        response = self.client.get(
            "/api/time-series/catalog/inputs",
            params={
                "q": "Nodo A",
                "semantic_type_key": "hydro_inflow",
                "data_class_key": "real",
                "unit_key": "m3_per_s",
                "owner_project_id": self.project["id"],
                "visibility_scope": "project",
                "set_status": "validated",
                "signal_status": "active",
                "source_kind": "api",
                "covers_from": "2026-01-01T00:30:00+00:00",
                "covers_to": "2026-01-01T02:30:00+00:00",
                "resolution_seconds_min": 3600,
                "resolution_seconds_max": 3600,
                "regularity": "regular",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["identity"]["series_key"] for item in response.json()["items"]],
            ["inflow_node_a"],
        )
        self.assertEqual(response.json()["summary"], {"total_count": 1})

    def test_cursor_is_signed_expiring_and_bound_to_query_and_actor(self):
        with patch("app.time_series_catalog_projection.time.time", return_value=1_000_000):
            first = self.client.get(
                "/api/time-series/catalog/inputs",
                params={"limit": 1, "q": "a"},
                headers={"X-Request-Id": "req-catalog-page"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers["cache-control"], "private, must-revalidate")
        self.assertEqual(first.json()["meta"]["request_id"], "req-catalog-page")
        cursor = first.json()["page"]["next_cursor"]
        tampered = cursor[:-4] + ("aaaa" if cursor[-4:] != "aaaa" else "bbbb")

        with patch("app.time_series_catalog_projection.time.time", return_value=1_000_001):
            tampered_response = self.client.get(
                "/api/time-series/catalog/inputs",
                params={"limit": 1, "q": "a", "cursor": tampered},
            )
        with patch("app.time_series_catalog_projection.time.time", return_value=1_000_001):
            changed_query = self.client.get(
                "/api/time-series/catalog/inputs",
                params={"limit": 1, "q": "precio", "cursor": cursor},
            )
        with patch("app.time_series_catalog_projection.time.time", return_value=1_001_000):
            expired = self.client.get(
                "/api/time-series/catalog/inputs",
                params={"limit": 1, "q": "a", "cursor": cursor},
            )

        self.store.create_user(
            email="other@example.local",
            display_name="Other Analyst",
            role="analyst",
            password_hash=hash_password("other pass"),
        )
        login_json_with_csrf(self.client, "other@example.local", "other pass")
        with patch("app.time_series_catalog_projection.time.time", return_value=1_000_001):
            other_actor = self.client.get(
                "/api/time-series/catalog/inputs",
                params={"limit": 1, "q": "a", "cursor": cursor},
            )

        self.assertEqual(
            {
                "tampered": (tampered_response.status_code, tampered_response.json()["error"]["code"]),
                "changed_query": (changed_query.status_code, changed_query.json()["error"]["code"]),
                "expired": (expired.status_code, expired.json()["error"]["code"]),
                "other_actor": (other_actor.status_code, other_actor.json()["error"]["code"]),
            },
            {
                "tampered": (400, "TS_QUERY_CURSOR_MISMATCH"),
                "changed_query": (400, "TS_QUERY_CURSOR_MISMATCH"),
                "expired": (410, "TS_QUERY_CURSOR_EXPIRED"),
                "other_actor": (400, "TS_QUERY_CURSOR_MISMATCH"),
            },
        )

    def test_detail_exposes_contract_provenance_current_hash_and_strong_etag(self):
        listed = self.client.get("/api/time-series/catalog/inputs").json()["items"]
        signal_id = next(
            item["signal_id"]
            for item in listed
            if item["identity"]["series_key"] == "energy_price"
        )

        response = self.client.get(
            f"/api/time-series/catalog/inputs/{signal_id}",
            headers={"X-Request-Id": "req-catalog-detail"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["etag"].startswith('"'))
        self.assertEqual(response.headers["cache-control"], "private, must-revalidate")
        detail = response.json()
        self.assertEqual(detail["signal_id"], signal_id)
        self.assertEqual(
            {
                "semantic_key": detail["contract"]["semantic_type"]["key"],
                "semantic_name": detail["contract"]["semantic_type"]["display_name"],
                "semantic_status": detail["contract"]["semantic_type"]["status"],
                "dimension": detail["contract"]["semantic_type"]["dimension_key"],
                "value_kind": detail["contract"]["semantic_type"]["value_kind"],
                "aggregation_default": detail["contract"]["semantic_type"]["default_aggregation"],
                "validation_rules": detail["contract"]["semantic_type"]["validation_rules"],
                "data_class": detail["contract"]["data_class"],
                "unit": detail["contract"]["unit"],
                "signal_role": detail["contract"]["signal_role"],
                "aggregation": detail["contract"]["aggregation"],
            },
            {
                "semantic_key": "energy_price",
                "semantic_name": "Energy price",
                "semantic_status": "active",
                "dimension": "currency_per_energy",
                "value_kind": "numeric",
                "aggregation_default": "mean",
                "validation_rules": {},
                "data_class": {"key": "real", "display_name": "Real", "status": "active"},
                "unit": {
                    "key": "usd_per_mwh",
                    "symbol": "USD/MWh",
                    "dimension_key": "currency_per_energy",
                    "status": "active",
                },
                "signal_role": "input",
                "aggregation": "mean",
            },
        )
        self.assertEqual(
            {
                key: detail["current_revision"][key]
                for key in ("id", "number", "state", "content_hash", "timezone")
            },
            {
                "id": self.receipt["revision_id"],
                "number": 1,
                "state": "sealed",
                "content_hash": self.receipt["content_hash"],
                "timezone": "UTC",
            },
        )
        self.assertTrue(detail["current_revision"]["created_at"])
        self.assertEqual(detail["provenance"]["kind"], "api")
        self.assertNotIn("stored_path", detail["provenance"])
        self.assertNotIn("values", detail)
        self.assertNotIn("points", detail)
        self.assertTrue(detail["capabilities"]["preview"])
        self.assertTrue(detail["links"]["revisions"].endswith("/revisions"))
        self.assertEqual(detail["request_id"], "req-catalog-detail")

        unchanged = self.client.get(
            f"/api/time-series/catalog/inputs/{signal_id}",
            headers={"If-None-Match": response.headers["etag"]},
        )
        self.assertEqual(unchanged.status_code, 304)

    def test_revision_history_pages_immutable_metadata_without_moving_current(self):
        second = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            set_id=self.receipt["set_id"],
            name="Inputs 2026",
            version_label="v1",
            data_class_key="real",
            timezone="UTC",
            signals=SIGNALS,
            periods=hourly_periods(3),
            values={
                "energy_price": [80.0, 81.0, 82.0],
                "inflow_node_a": [13.0, 14.0, 15.0],
            },
            change_summary="Updated forecast",
            actor="analyst@example.local",
        )
        signal_id = next(
            item["signal_id"]
            for item in self.client.get("/api/time-series/catalog/inputs").json()["items"]
            if item["identity"]["series_key"] == "energy_price"
        )
        detail_path = f"/api/time-series/catalog/inputs/{signal_id}"
        current_before = self.client.get(detail_path).json()["current_revision"]["id"]

        first_page = self.client.get(f"{detail_path}/revisions", params={"limit": 1})
        self.assertEqual(first_page.status_code, 200)
        cursor = first_page.json()["page"]["next_cursor"]
        second_page = self.client.get(
            f"{detail_path}/revisions", params={"limit": 1, "cursor": cursor}
        )

        revisions = first_page.json()["items"] + second_page.json()["items"]
        self.assertEqual(
            [(item["number"], item["content_hash"]) for item in revisions],
            [(2, second["content_hash"]), (1, self.receipt["content_hash"])],
        )
        self.assertEqual(
            set(revisions[0]),
            {
                "id",
                "number",
                "state",
                "content_hash",
                "created_at",
                "created_by",
                "change_summary",
                "source_kind",
                "validation_summary",
            },
        )
        self.assertEqual(first_page.json()["summary"], {"total_count": 2})
        self.assertEqual(
            self.client.get(detail_path).json()["current_revision"]["id"],
            current_before,
        )

    def test_preview_cites_the_exact_revision_and_never_silently_truncates(self):
        second = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            set_id=self.receipt["set_id"],
            name="Inputs 2026",
            version_label="v1",
            data_class_key="real",
            timezone="UTC",
            signals=SIGNALS,
            periods=hourly_periods(3),
            values={
                "energy_price": [90.0, 91.0, 92.0],
                "inflow_node_a": [30.0, 31.0, 32.0],
            },
            actor="analyst@example.local",
        )
        signal_id = next(
            item["signal_id"]
            for item in self.client.get("/api/time-series/catalog/inputs").json()["items"]
            if item["identity"]["series_key"] == "energy_price"
        )
        path = f"/api/time-series/catalog/inputs/{signal_id}/preview"
        query = {
            "revision_id": self.receipt["revision_id"],
            "from": "2026-01-01T00:00:00+00:00",
            "to": "2026-01-01T03:00:00+00:00",
            "sampling": "none",
            "max_points": 3,
        }

        response = self.client.get(path, params=query)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        preview = response.json()
        self.assertEqual(preview["revision"], {
            "id": self.receipt["revision_id"],
            "content_hash": self.receipt["content_hash"],
        })
        self.assertNotEqual(preview["revision"]["id"], second["revision_id"])
        self.assertEqual(preview["source_point_count"], 3)
        self.assertEqual(preview["returned_point_count"], 3)
        self.assertEqual(
            [point["value"] for point in preview["points"]],
            [70.0, 71.0, 72.0],
        )

        too_many_source_points = self.client.get(
            path, params={**query, "max_points": 2}
        )
        sampled = self.client.get(
            path, params={**query, "sampling": "minmax", "max_points": 2}
        )
        excessive_limit = self.client.get(
            path, params={**query, "sampling": "uniform", "max_points": 2001}
        )
        self.assertEqual(
            (
                too_many_source_points.status_code,
                too_many_source_points.json()["error"]["code"],
                excessive_limit.status_code,
                excessive_limit.json()["error"]["code"],
            ),
            (422, "TS_PREVIEW_TOO_LARGE", 422, "TS_PREVIEW_TOO_LARGE"),
        )
        self.assertEqual(sampled.status_code, 200)
        self.assertEqual(sampled.json()["source_point_count"], 3)
        self.assertEqual(sampled.json()["returned_point_count"], 2)
        self.assertEqual(
            [point["value"] for point in sampled.json()["points"]], [70.0, 72.0]
        )

    def test_external_is_refused_identically_before_any_catalog_id_is_resolved(self):
        self.store.create_user(
            email="external@example.local",
            display_name="External",
            role="external",
            password_hash=hash_password("external pass"),
        )
        login = login_json_with_csrf(
            self.client,
            "external@example.local",
            "external pass",
            next_path="/react/client",
        )
        self.assertEqual(login.status_code, 200)

        paths = [
            "/api/time-series/catalog/inputs",
            "/api/time-series/catalog/inputs/999999",
            "/api/time-series/catalog/inputs/999999/revisions",
            (
                "/api/time-series/catalog/inputs/999999/preview"
                "?revision_id=888888&from=2026-01-01T00%3A00%3A00%2B00%3A00"
                "&to=2026-01-01T01%3A00%3A00%2B00%3A00"
            ),
            "/api/time-series/catalog/inputs/999999/object-candidates",
            "/api/time-series/catalog/descriptors?kind=semantic_type",
            "/api/time-series/catalog/results",
            "/api/time-series/catalog/legacy",
        ]
        responses = [self.client.get(path) for path in paths]

        self.assertEqual(
            [(response.status_code, response.json()) for response in responses],
            [(403, {"detail": "forbidden"})] * len(paths),
        )

    def test_descriptors_page_persistent_catalogs_without_the_compatibility_matrix(self):
        custom = self.store.create_custom_time_series_semantic_type(
            semantic_key="spot_price_custom",
            display_name="Spot price custom",
            description="A governed custom spot price.",
            dimension_key="currency_per_energy",
            canonical_unit_key="usd_per_mwh",
            value_kind="numeric",
            default_aggregation="mean",
            validation_rules={"minimum": 0},
            created_by="admin@example.local",
        )

        semantic = self.client.get(
            "/api/time-series/catalog/descriptors",
            params={"kind": "semantic_type", "q": "spot custom"},
        )

        self.assertEqual(semantic.status_code, 200)
        self.assertEqual(len(semantic.json()["items"]), 1)
        item = semantic.json()["items"][0]
        self.assertEqual(
            {
                "id": item["id"],
                "key": item["key"],
                "display_name": item["display_name"],
                "status": item["status"],
                "dimension_key": item["dimension_key"],
                "canonical_unit_key": item["canonical_unit_key"],
            },
            {
                "id": custom["id"],
                "key": "spot_price_custom",
                "display_name": "Spot price custom",
                "status": "active",
                "dimension_key": "currency_per_energy",
                "canonical_unit_key": "usd_per_mwh",
            },
        )
        self.assertNotIn("compatibilities", item)
        self.assertNotIn("time_series_role_compatibilities", semantic.text)

        first_roles = self.client.get(
            "/api/time-series/catalog/descriptors",
            params={"kind": "binding_role", "limit": 1},
        ).json()
        second_roles = self.client.get(
            "/api/time-series/catalog/descriptors",
            params={
                "kind": "binding_role",
                "limit": 1,
                "cursor": first_roles["page"]["next_cursor"],
            },
        ).json()
        self.assertNotEqual(first_roles["items"][0]["id"], second_roles["items"][0]["id"])
        self.assertEqual(first_roles["meta"]["kind"], "binding_role")

    def test_object_candidates_use_the_single_evaluator_and_denied_are_not_selectable(self):
        system = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        load = self.store.ensure_project_component(
            project_id=self.project["id"],
            component_key="load_a",
            component_type="load",
            display_name="Load A",
        )
        signal_id = next(
            item["signal_id"]
            for item in self.client.get("/api/time-series/catalog/inputs").json()["items"]
            if item["identity"]["series_key"] == "energy_price"
        )
        path = f"/api/time-series/catalog/inputs/{signal_id}/object-candidates"
        query = {
            "target_project_id": self.project["id"],
            "binding_role_key": "grid_import_price",
            "usage": "association",
            "include_denied": "true",
        }

        response = self.client.get(path, params=query)

        self.assertEqual(response.status_code, 200)
        by_id = {item["object"]["id"]: item for item in response.json()["items"]}
        self.assertEqual(by_id[system["id"]]["compatibility_decision"]["allowed"], True)
        self.assertEqual(by_id[system["id"]]["selectable"], True)
        self.assertEqual(by_id[load["id"]]["compatibility_decision"]["allowed"], False)
        self.assertEqual(by_id[load["id"]]["selectable"], False)
        self.assertEqual(
            by_id[load["id"]]["compatibility_decision"]["primary_error"]["code"],
            "TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED",
        )

        allowed_only = self.client.get(
            path, params={key: value for key, value in query.items() if key != "include_denied"}
        )
        self.assertEqual(
            [item["object"]["id"] for item in allowed_only.json()["items"]],
            [system["id"]],
        )

    def test_archived_signal_keeps_reads_and_history_but_no_mutation_capabilities(self):
        archived = self.store.archive_canonical_signal_identity(
            set_id=self.receipt["set_id"],
            series_key="energy_price",
            actor="analyst@example.local",
            reason_text="Retired input",
        )

        default_keys = [
            item["identity"]["series_key"]
            for item in self.client.get("/api/time-series/catalog/inputs").json()["items"]
        ]
        archived_page = self.client.get(
            "/api/time-series/catalog/inputs",
            params={"signal_status": "archived"},
        )

        self.assertNotIn("energy_price", default_keys)
        self.assertEqual(archived_page.status_code, 200)
        self.assertEqual(len(archived_page.json()["items"]), 1)
        item = archived_page.json()["items"][0]
        self.assertEqual(item["signal_id"], archived["signal_id"])
        self.assertEqual(item["identity"]["status"], "archived")
        self.assertEqual(
            {
                name: item["capabilities"][name]
                for name in ("associate", "bind", "edit_set", "publish_revision")
            },
            {
                "associate": False,
                "bind": False,
                "edit_set": False,
                "publish_revision": False,
            },
        )
        base = f"/api/time-series/catalog/inputs/{archived['signal_id']}"
        self.assertEqual(self.client.get(base).status_code, 200)
        self.assertEqual(self.client.get(f"{base}/revisions").status_code, 200)
        preview = self.client.get(
            f"{base}/preview",
            params={
                "revision_id": self.receipt["revision_id"],
                "from": "2026-01-01T00:00:00+00:00",
                "to": "2026-01-01T03:00:00+00:00",
                "sampling": "none",
                "max_points": 3,
            },
        )
        self.assertEqual(preview.status_code, 200)

    def test_association_filters_and_inverse_object_context_share_compatibility(self):
        system = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        listed = self.client.get("/api/time-series/catalog/inputs").json()["items"]
        price = next(
            item for item in listed if item["identity"]["series_key"] == "energy_price"
        )
        associations = self.store.link_layer_table_names()[
            "time_series_catalog_associations"
        ]
        self.store.connection.execute(
            f"""
            INSERT INTO {associations} (
                signal_id, time_series_set_id, linkable_object_id,
                binding_role_id, compatibility_rule_id, lifecycle_revision,
                status, created_at, created_by
            ) VALUES (?, ?, ?, 1, 1, 1, 'active', ?, ?)
            """,
            (
                price["signal_id"],
                price["set"]["id"],
                system["id"],
                "2026-01-01T00:00:00+00:00",
                "analyst@example.local",
            ),
        )

        associated = self.client.get(
            "/api/time-series/catalog/inputs",
            params={
                "association_object_id": system["id"],
                "association_role_key": "grid_import_price",
                "association_state": "active",
            },
        )

        self.assertEqual(associated.status_code, 200)
        self.assertEqual(
            [item["identity"]["series_key"] for item in associated.json()["items"]],
            ["energy_price"],
        )

        context = {
            "context_linkable_object_id": system["id"],
            "context_binding_role_key": "grid_import_price",
            "context_usage": "association",
            "compatibility": "all",
        }
        contextual = self.client.get(
            "/api/time-series/catalog/inputs", params=context
        )
        self.assertEqual(contextual.status_code, 200)
        decisions = {
            item["identity"]["series_key"]: item["compatibility_decision"]
            for item in contextual.json()["items"]
        }
        self.assertTrue(decisions["energy_price"]["allowed"])
        self.assertFalse(decisions["inflow_node_a"]["allowed"])

        allowed = self.client.get(
            "/api/time-series/catalog/inputs",
            params={**context, "compatibility": "allowed"},
        )
        self.assertEqual(
            [item["identity"]["series_key"] for item in allowed.json()["items"]],
            ["energy_price"],
        )

    def test_variant_and_binding_state_filters_select_the_canonical_signal(self):
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Binding context"
        )
        now = "2026-01-01T00:00:00+00:00"
        case_id = int(
            self.store.connection.execute(
                """
                INSERT INTO optimization_cases (
                    scenario_id, case_key, display_name, created_at, updated_at,
                    created_by, updated_by
                ) VALUES (?, 'dispatch', 'Dispatch', ?, ?, 'seed', 'seed')
                """,
                (scenario["id"], now, now),
            ).lastrowid
        )
        variant_id = int(
            self.store.connection.execute(
                """
                INSERT INTO case_input_variants (
                    case_id, variant_key, display_name, is_default, created_at,
                    updated_at, created_by, updated_by
                ) VALUES (?, 'base', 'Base', 1, ?, ?, 'seed', 'seed')
                """,
                (case_id, now, now),
            ).lastrowid
        )
        object_row = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        inputs = self.client.get("/api/time-series/catalog/inputs").json()["items"]
        price = next(
            item for item in inputs if item["identity"]["series_key"] == "energy_price"
        )
        role = self.store.connection.execute(
            "SELECT id FROM time_series_binding_roles WHERE role_key = 'grid_import_price'"
        ).fetchone()
        rule = self.store.connection.execute(
            """
            SELECT compatibility.id
            FROM time_series_role_compatibilities AS compatibility
            JOIN time_series_semantic_types AS semantic
              ON semantic.id = compatibility.semantic_type_id
            JOIN linkable_object_types AS object_type
              ON object_type.id = compatibility.object_type_id
            WHERE semantic.semantic_key = 'energy_price'
              AND object_type.object_type_key = 'global:system'
              AND compatibility.binding_role_id = ?
            """,
            (role["id"],),
        ).fetchone()
        bindings = self.store.link_layer_table_names()["case_time_series_bindings"]
        self.store.connection.execute(
            f"""
            INSERT INTO {bindings} (
                case_input_variant_id, linkable_object_id, binding_role_id,
                signal_id, time_series_set_id, set_revision_id,
                bound_content_hash, source_kind, compatibility_rule_id,
                required, status, lifecycle_revision, change_reason_code,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'catalog', ?, 1, 'active', 1,
                      'TS_BINDING_CREATED', ?, ?, 'seed', 'seed')
            """,
            (
                variant_id,
                object_row["id"],
                role["id"],
                price["signal_id"],
                price["set"]["id"],
                self.receipt["revision_id"],
                self.receipt["content_hash"],
                rule["id"],
                now,
                now,
            ),
        )

        response = self.client.get(
            "/api/time-series/catalog/inputs",
            params={
                "scenario_id": scenario["id"],
                "variant_id": variant_id,
                "binding_state": "active",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["identity"]["series_key"] for item in response.json()["items"]],
            ["energy_price"],
        )

    def test_execution_context_rejects_a_variant_from_another_project(self):
        object_row = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        other_project = self.store.create_project(name="Contexto ajeno")
        scenario = self.store.create_scenario(
            project_id=other_project["id"], name="Other dispatch"
        )
        now = "2026-01-01T00:00:00+00:00"
        case_id = int(
            self.store.connection.execute(
                """
                INSERT INTO optimization_cases (
                    scenario_id, case_key, display_name, created_at, updated_at,
                    created_by, updated_by
                ) VALUES (?, 'other', 'Other', ?, ?, 'seed', 'seed')
                """,
                (scenario["id"], now, now),
            ).lastrowid
        )
        variant_id = int(
            self.store.connection.execute(
                """
                INSERT INTO case_input_variants (
                    case_id, variant_key, display_name, created_at, updated_at,
                    created_by, updated_by
                ) VALUES (?, 'base', 'Base', ?, ?, 'seed', 'seed')
                """,
                (case_id, now, now),
            ).lastrowid
        )

        response = self.client.get(
            "/api/time-series/catalog/inputs",
            params={
                "context_linkable_object_id": object_row["id"],
                "context_binding_role_key": "grid_import_price",
                "context_usage": "execution",
                "context_scenario_id": scenario["id"],
                "context_variant_id": variant_id,
                "compatibility": "all",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"],
            "TS_COMPAT_PROJECT_CONTEXT_MISMATCH",
        )

    def test_inputs_results_and_legacy_are_structurally_separate_resources(self):
        now = "2026-01-01T00:00:00+00:00"
        legacy_cursor = self.store.connection.execute(
            """
            INSERT INTO hydraulic_time_series_sets (
                project_id, entity_type, entity_id, signal_key,
                version_number, version_label, content_hash, status,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, 'hydraulic_node', 999, 'natural_inflow_m3s',
                      1, 'v1', 'legacy-hash', 'validated', ?, ?, 'seed', 'seed')
            """,
            (self.project["id"], now, now),
        )
        legacy_id = int(legacy_cursor.lastrowid)
        self.store.connection.executemany(
            """
            INSERT INTO hydraulic_time_series_points (
                hydraulic_time_series_set_id, point_index, timestamp,
                duration_hours, value
            ) VALUES (?, ?, ?, 1.0, ?)
            """,
            [
                (legacy_id, index, f"2026-01-01T0{index}:00:00", 5.0 + index)
                for index in range(2)
            ],
        )

        inputs = self.client.get("/api/time-series/catalog/inputs")
        results = self.client.get("/api/time-series/catalog/results")
        legacy = self.client.get("/api/time-series/catalog/legacy")

        self.assertEqual((inputs.status_code, results.status_code, legacy.status_code), (200, 200, 200))
        self.assertTrue(all(item["entry_kind"] == "input" for item in inputs.json()["items"]))
        self.assertEqual(results.json()["meta"]["section"], "results")
        self.assertEqual(results.json()["items"], [])
        self.assertEqual(legacy.json()["meta"]["section"], "legacy")
        self.assertEqual(len(legacy.json()["items"]), 1)
        legacy_item = legacy.json()["items"][0]
        self.assertEqual(legacy_item["entry_kind"], "legacy")
        self.assertNotEqual(legacy_item["legacy_entry_ref"], str(legacy_id))
        self.assertEqual(legacy_item["migration_state"], "unmigrated")
        self.assertNotIn("associate", legacy_item["capabilities"])
        self.assertNotIn("bind", legacy_item["capabilities"])
        legacy_ref = legacy_item["legacy_entry_ref"]
        detail = self.client.get(f"/api/time-series/catalog/legacy/{legacy_ref}")
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn("points", detail.json())
        self.assertNotIn("values", detail.json())
        preview = self.client.get(
            f"/api/time-series/catalog/legacy/{legacy_ref}/preview",
            params={
                "from": "2026-01-01T00:00:00+00:00",
                "to": "2026-01-01T02:00:00+00:00",
                "sampling": "none",
                "max_points": 2,
            },
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(
            [point["value"] for point in preview.json()["points"]], [5.0, 6.0]
        )
        self.assertEqual(self.client.get("/api/time-series/catalog").status_code, 404)

    def test_result_series_are_read_only_and_preview_the_result_index(self):
        scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Dispatch"
        )
        now = "2026-01-01T00:00:00+00:00"
        version = self.store.connection.execute(
            """
            INSERT INTO scenario_versions (
                scenario_id, version_number, system_case_json, case_name,
                schema_version, period_count, asset_counts_json,
                validation_payload_json, generation_metadata_json,
                created_at, created_by
            ) VALUES (?, 1, '{}', 'dispatch', 'v1', 2, '{}', '{}', '{}', ?, 'seed')
            """,
            (scenario["id"], now),
        )
        run = self.store.create_run(scenario_version_id=int(version.lastrowid))
        self.store.connection.execute(
            "UPDATE runs SET status = 'succeeded', finished_at = ? WHERE id = ?",
            ("2026-01-01T02:00:00+00:00", run["id"]),
        )
        self.store.connection.execute(
            """
            INSERT INTO run_dispatch_result_indexes (
                run_id, scenario_version_id, dispatch_columns_json,
                signal_keys_json, lineage_json, created_at
            ) VALUES (?, ?, ?, ?, '{}', ?)
            """,
            (
                run["id"],
                int(version.lastrowid),
                '["timestamp", "duration_hours", "grid_import_mw", "battery_energy_mwh"]',
                '{"grid_import_mw": "grid_import_power", "battery_energy_mwh": "stored_energy"}',
                now,
            ),
        )
        self.store.connection.executemany(
            """
            INSERT INTO run_dispatch_result_rows (
                run_id, period_index, row_json, timestamp, duration_hours,
                grid_import_mw, battery_energy_mwh, created_at
            ) VALUES (?, ?, ?, ?, '1.0', ?, ?, ?)
            """,
            [
                (
                    run["id"],
                    index,
                    f'{{"timestamp":"2026-01-01T0{index}:00:00","duration_hours":"1.0","grid_import_mw":"{value}","battery_energy_mwh":"{20.0 + index}"}}',
                    f"2026-01-01T0{index}:00:00",
                    str(value),
                    str(20.0 + index),
                    now,
                )
                for index, value in enumerate((2.5, 3.0))
            ],
        )

        listed = self.client.get("/api/time-series/catalog/results", params={"limit": 1})
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["items"]), 1)
        self.assertTrue(listed.json()["page"]["has_more"])
        self.assertIsNotNone(listed.json()["page"]["next_cursor"])
        next_page = self.client.get(
            "/api/time-series/catalog/results",
            params={"limit": 1, "cursor": listed.json()["page"]["next_cursor"]},
        )
        self.assertEqual(next_page.status_code, 200)
        self.assertNotEqual(
            listed.json()["items"][0]["result_series_id"],
            next_page.json()["items"][0]["result_series_id"],
        )
        filtered = self.client.get(
            "/api/time-series/catalog/results",
            params={
                "owner_project_id": self.project["id"],
                "scenario_id": scenario["id"],
                "run_id": run["id"],
                "run_status": "succeeded",
                "result_type": "grid_import_mw",
                "produced_from": "2025-12-31T23:00:00+00:00",
                "produced_to": "2026-01-01T01:00:00+00:00",
            },
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(
            [item["result_type"] for item in filtered.json()["items"]],
            ["grid_import_mw"],
        )
        result = listed.json()["items"][0]
        self.assertEqual(result["entry_kind"], "result")
        self.assertNotIn("signal_id", result)
        self.assertNotIn("associate", result["capabilities"])
        self.assertNotIn("bind", result["capabilities"])
        result_id = result["result_series_id"]

        detail = self.client.get(f"/api/time-series/catalog/results/{result_id}")
        preview = self.client.get(
            f"/api/time-series/catalog/results/{result_id}/preview",
            params={
                "from": "2026-01-01T00:00:00+00:00",
                "to": "2026-01-01T02:00:00+00:00",
                "sampling": "none",
                "max_points": 2,
            },
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["result_series_id"], result_id)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(
            [point["value"] for point in preview.json()["points"]], [2.5, 3.0]
        )

    def test_legacy_collection_uses_its_own_cursor(self):
        now = "2026-01-01T00:00:00+00:00"
        for entity_id in (901, 902):
            self.store.connection.execute(
                """
                INSERT INTO hydraulic_time_series_sets (
                    project_id, entity_type, entity_id, signal_key,
                    version_number, version_label, content_hash, status,
                    created_at, updated_at, created_by, updated_by
                ) VALUES (?, 'hydraulic_node', ?, 'natural_inflow_m3s',
                          1, 'v1', ?, 'validated', ?, ?, 'seed', 'seed')
                """,
                (self.project["id"], entity_id, f"legacy-{entity_id}", now, now),
            )

        first = self.client.get(
            "/api/time-series/catalog/legacy", params={"limit": 1}
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["page"]["has_more"])
        self.assertIsNotNone(first.json()["page"]["next_cursor"])
        second = self.client.get(
            "/api/time-series/catalog/legacy",
            params={"limit": 1, "cursor": first.json()["page"]["next_cursor"]},
        )
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(
            first.json()["items"][0]["legacy_entry_ref"],
            second.json()["items"][0]["legacy_entry_ref"],
        )
        self.assertEqual(second.json()["summary"], {"total_count": 2})


if __name__ == "__main__":
    unittest.main()
