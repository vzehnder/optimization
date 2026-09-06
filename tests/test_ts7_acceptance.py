"""TS7-023: closing proof for the TS-7 global catalog and object-specific series.

One continuous narrative over the eighteen observable stories of chapter 11.4.
An analyst searches the signal-first catalog, opens a signal and previews an
exact revision without downloading it; associates a compatible object and is
blocked, with a stable code, on an incompatible one; pins a variant binding to
an exact revision and hash, watches a new publication turn it stale without
moving it, and replaces it with a reason that survives in history; creates a
series that belongs to one object, loads it by file and by API, binds it with
no catalog association in between and never sees it leak into the global
catalog; opens a shared generic source from the object, reads the whole impact
and takes both exits -- a local derivation with lineage, or the administrative
`Publicar para todos` that leaves consumers visibly stale; an admin promotes and
demotes a set without losing history; an external identity gets the same answer
everywhere as if nothing existed; and the migrator converges twice over an
unchanged source before the cutover closes every legacy write path in code and
in the database. Finally the ledger reconstructs actor and reason for every
mutation the narrative made.

The seams are the ones every TS7-0xx suite already uses: the HTTP contract of
the catalog, object, association, binding, scope and admin surfaces, and the
store's public migration operations. Nothing here reaches into internals.
"""

import json
import os
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.persistence import AnalystStore
from app.time_series_catalog import (
    CatalogImportRequest,
    CatalogSignalMappingRequest,
    prepare_time_series_catalog_import,
)
from app.time_series_links import LINK_LEDGER_IMMUTABLE
from app.time_series_migration import MigrationControlError
from tests.auth_test_helpers import (
    csrf_headers,
    login_json_with_csrf,
    post_json_with_csrf,
)


REPO_ROOT = Path(__file__).resolve().parents[1]

POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


PRICE_SIGNAL = {
    "series_key": "energy_price",
    "display_name": "Precio de energia",
    "semantic_type_key": "energy_price",
    "unit_key": "usd_per_mwh",
    "signal_role": "input",
    "aggregation": "mean",
}

INFLOW_SIGNAL = {
    "series_key": "inflow_node_a",
    "display_name": "Caudal afluente Nodo A",
    "semantic_type_key": "hydro_inflow",
    "unit_key": "m3_per_s",
    "signal_role": "input",
    "aggregation": "mean",
}


# The series that belongs to one object and must never leave it (chapter 7.5).
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
    "metadata": {"tags": ["operacion"], "external_reference": "forecast:nodo-7"},
}

LOCAL_CSV = (
    "timestamp,duration_hours,value_mwh,quality\n"
    "2026-08-31T00:00:00-04:00,1,18.4,forecast\n"
    "2026-08-31T01:00:00-04:00,1,19.1,measured\n"
)

LOCAL_CSV_MAPPING = {
    "mode": "replace_full",
    "expected_base": None,
    "revision_contract": {
        "data_class_key": "forecast",
        "timezone": "America/Santiago",
        "regularity": "regular",
        "nominal_resolution_seconds": 3600,
    },
    "columns": {
        "timestamp_start": "timestamp",
        "timestamp_end": None,
        "duration_hours": "duration_hours",
        "signals": [
            {
                "series_key": "local_price_forecast",
                "value": "value_mwh",
                "quality_flag": "quality",
            }
        ],
    },
    "source": {
        "kind": "csv",
        "display_name": "Pronostico del proveedor",
        "external_reference": "forecast-2026-08-30",
    },
}

LOCAL_POINTS = {
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
            "values": {"local_price_forecast": {"value": 20.5}},
        },
        {
            "timestamp_start": "2026-08-31T01:00:00-04:00",
            "duration_seconds": 3600,
            "values": {"local_price_forecast": {"value": 21.2}},
        },
    ],
}


def hourly_periods(count):
    return [
        {
            "timestamp_start": f"2026-01-01T{index:02d}:00:00",
            "timestamp_end": f"2026-01-01T{index + 1:02d}:00:00",
            "duration_hours": 1.0,
        }
        for index in range(count)
    ]


class TS7AcceptanceTests(unittest.TestCase):
    """The whole TS-7 story, told once, over the public surfaces."""

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.build_fixture()

    def build_fixture(self):
        suffix = uuid.uuid4().hex[:10]
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.analyst_email = f"ts7-analyst-{suffix}@example.local"
        self.admin_email = f"ts7-admin-{suffix}@example.local"
        self.store.create_user(
            email=self.analyst_email,
            display_name="Analyst",
            role="analyst",
            password_hash=hash_password("analyst pass"),
        )
        self.store.create_user(
            email=self.admin_email,
            display_name="Admin",
            role="admin",
            password_hash=hash_password("admin pass"),
        )
        self.login(self.analyst_email, "analyst pass")

        self.project = self.store.create_project(name=f"Cuenca Norte {suffix}")
        self.neighbour = self.store.create_project(name=f"Cuenca Sur {suffix}")
        self.receipt = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name=f"Inputs 2026 {suffix}",
            version_label="v1",
            description="Senales operativas",
            data_class_key="real",
            timezone="UTC",
            signals=[PRICE_SIGNAL, INFLOW_SIGNAL],
            periods=hourly_periods(3),
            values={
                "energy_price": [70.0, 71.0, 72.0],
                "inflow_node_a": [10.0, 11.0, 12.0],
            },
            actor=self.analyst_email,
        )
        self.system = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        self.load = self.store.ensure_project_component(
            project_id=self.project["id"],
            component_key="load_a",
            component_type="load",
            display_name="Load A",
        )
        self.neighbour_object = self.store.ensure_global_signal_slot(
            project_id=self.neighbour["id"], display_name="Sistema vecino"
        )
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Plan base"
        )
        self.variant = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]

    # -- narrative helpers -------------------------------------------------

    def login(self, email, password, next_path="/react/projects"):
        response = login_json_with_csrf(self.client, email, password, next_path)
        self.assertEqual(response.status_code, 200, response.text)

    def signal_id_of(self, series_key):
        # The catalog is global by design, so every read of it in this narrative
        # is scoped to the project under test.
        listing = self.client.get(
            "/api/time-series/catalog/inputs",
            params={"owner_project_id": self.project["id"]},
        )
        self.assertEqual(listing.status_code, 200, listing.text)
        return next(
            item["signal_id"]
            for item in listing.json()["items"]
            if item["identity"]["series_key"] == series_key
        )

    def my_association_ids(self):
        listing = self.client.get("/api/time-series/catalog/associations")
        self.assertEqual(listing.status_code, 200, listing.text)
        mine = {self.system["id"], self.load["id"], self.neighbour_object["id"]}
        return [
            row["association_id"]
            for row in listing.json()["items"]
            if row["object"]["id"] in mine
        ]

    @property
    def object_root(self):
        return (
            f"/api/projects/{self.project['id']}/linkable-objects/"
            f"{self.system['id']}/time-series"
        )

    @property
    def variant_root(self):
        return (
            f"/api/scenarios/{self.scenario['id']}/case-variants/"
            f"{self.variant['id']}"
        )

    def associate(self, *, signal_id, linkable_object_id, project_id=None):
        """H-04: prevalidate, then confirm exactly what was prevalidated."""

        request = {
            "target_project_id": project_id or self.project["id"],
            "operations": [
                {
                    "client_operation_id": f"add-{linkable_object_id}",
                    "action": "add",
                    "signal_id": signal_id,
                    "linkable_object_id": linkable_object_id,
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
        )
        self.assertEqual(prevalidation.status_code, 200, prevalidation.text)
        committed = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **request,
                "prevalidation_token": prevalidation.json()["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidation.json()["commit_etag"],
                "Idempotency-Key": f"associate-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(committed.status_code, 201, committed.text)
        return committed.json()["operations"][0]["association_id"]

    def prevalidate_scope(self, target_scope):
        response = post_json_with_csrf(
            self.client,
            f"/api/time-series/catalog/sets/{self.receipt['set_id']}"
            "/scope-prevalidations",
            {"target_scope": target_scope},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def commit_scope(self, preview, *, reason_text, request_id):
        revision = preview["impact"]["current_revision"]
        return self.client.post(
            f"/api/time-series/catalog/sets/{self.receipt['set_id']}/scope-changes",
            json={
                "target_scope": preview["normalized_request"]["target_scope"],
                "expected_scope_revision": preview["impact"]["set"]["scope_revision"],
                "observed_revision_id": revision["id"],
                "observed_content_hash": revision["content_hash"],
                "prevalidation_token": preview["prevalidation_token"],
                "confirmed": True,
                "reason_code": "administrative_scope_change",
                "reason_text": reason_text,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": preview["commit_etag"],
                "Idempotency-Key": f"scope-{uuid.uuid4().hex}",
                "X-Request-Id": request_id,
            },
        )

    def promote_the_shared_set(self):
        """H-15 as a fixture: the same administrative route, run for real."""

        self.login(self.admin_email, "admin pass")
        promoted = self.commit_scope(
            self.prevalidate_scope("global"),
            reason_text="Aprobado para reuso entre proyectos internos.",
            request_id="req-promote-inputs",
        )
        self.assertEqual(promoted.status_code, 201, promoted.text)
        self.login(self.analyst_email, "analyst pass")

    def assert_ledger_refuses(self, statement):
        """A refused write must not poison the rest of the narrative.

        PostgreSQL aborts the whole transaction on the failed statement, so the
        probe runs inside its own savepoint on both engines.
        """

        savepoint = f"ledger_{uuid.uuid4().hex[:8]}"
        self.store.connection.execute(f"SAVEPOINT {savepoint}")
        try:
            with self.assertRaisesRegex(Exception, LINK_LEDGER_IMMUTABLE):
                self.store.connection.execute(statement)
        finally:
            self.store.connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            self.store.connection.execute(f"RELEASE SAVEPOINT {savepoint}")

    def shared_points(self):
        return {
            "mode": "replace_full",
            "expected_base": {
                "revision_id": self.receipt["revision_id"],
                "content_hash": self.receipt["content_hash"],
            },
            "revision_contract": {
                "data_class_key": "real",
                "timezone": "UTC",
                "regularity": "regular",
                "nominal_resolution_seconds": 3600,
            },
            "source": {"kind": "api", "display_name": "Mesa de precios"},
            "points": [
                {
                    "timestamp_start": f"2026-01-01T{index:02d}:00:00+00:00",
                    "duration_seconds": 3600,
                    "values": {
                        "energy_price": {"value": 81.0 + index},
                        "inflow_node_a": {"value": 10.0 + index},
                    },
                }
                for index in range(3)
            ],
        }

    def publish_shared(self, association_root, ingestion, **overrides):
        body = {
            "validation_token": ingestion["validation_token"],
            "impact_fingerprint": ingestion["impact_fingerprint"],
            "confirm": True,
            "comprehension_acknowledged": True,
            "reason_code": "shared_price_update",
            "reason_text": "Mesa de precios de enero.",
        }
        body.update(overrides)
        return self.client.post(
            f"{association_root}/shared-series/revision-ingestions/"
            f"{ingestion['ingestion_id']}/publications",
            json=body,
            headers={
                **csrf_headers(self.client),
                "If-Match": ingestion["etag"],
                "Idempotency-Key": f"publish-{uuid.uuid4().hex}",
            },
        )

    def bind(self, operation, *, expected_bindings_revision):
        request = {
            "expected_bindings_revision": expected_bindings_revision,
            "operations": [operation],
        }
        prevalidated = post_json_with_csrf(
            self.client,
            f"{self.variant_root}/time-series-binding-prevalidations",
            request,
        )
        self.assertEqual(prevalidated.status_code, 200, prevalidated.text)
        prevalidation = prevalidated.json()
        return self.client.post(
            f"{self.variant_root}/time-series-binding-batches",
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

    # -- H-01, H-02, H-03 --------------------------------------------------

    def test_the_catalog_is_signal_first_searchable_and_previews_exact_revisions(self):
        listing = self.client.get(
            "/api/time-series/catalog/inputs",
            params={
                "owner_project_id": self.project["id"],
                "q": "precio",
                "semantic_type_key": "energy_price",
                "unit_key": "usd_per_mwh",
                "visibility_scope": "project",
                "lifecycle_state": "active",
                "limit": 50,
            },
        )

        self.assertEqual(listing.status_code, 200, listing.text)
        page = listing.json()
        self.assertEqual(len(page["items"]), 1)
        row = page["items"][0]
        # H-01: one row per signal, owner and scope visible without opening it.
        self.assertEqual(row["identity"]["series_key"], "energy_price")
        self.assertEqual(
            row["owner"],
            {
                "project_id": self.project["id"],
                "project_name": self.project["name"],
            },
        )
        self.assertEqual(row["set"]["visibility_scope"], "project")
        self.assertEqual(row["classification"]["unit_key"], "usd_per_mwh")
        self.assertEqual(row["coverage_summary"]["period_count"], 3)
        self.assertEqual(row["coverage_summary"]["nominal_resolution_seconds"], 3600.0)
        self.assertEqual(page["page"]["next_cursor"], None)

        signal_id = row["signal_id"]

        # H-02: the detail carries contract, provenance, current revision and
        # hash, and it never carries points.
        detail = self.client.get(f"/api/time-series/catalog/inputs/{signal_id}")
        self.assertEqual(detail.status_code, 200, detail.text)
        body = detail.json()
        self.assertEqual(
            body["current_revision"]["id"], self.receipt["revision_id"]
        )
        self.assertEqual(
            body["current_revision"]["content_hash"], self.receipt["content_hash"]
        )
        self.assertRegex(body["current_revision"]["content_hash"], r"^[0-9a-f]{64}$")
        self.assertNotIn("points", body)
        self.assertNotIn("values", body)

        # H-03: a bounded preview of an exact revision, never the whole series.
        preview = self.client.get(
            f"/api/time-series/catalog/inputs/{signal_id}/preview",
            params={
                "revision_id": self.receipt["revision_id"],
                "from": "2026-01-01T00:00:00+00:00",
                "to": "2026-01-01T03:00:00+00:00",
                "sampling": "none",
                "max_points": 3,
            },
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(
            preview.json()["revision"],
            {
                "id": self.receipt["revision_id"],
                "content_hash": self.receipt["content_hash"],
            },
        )
        self.assertEqual(
            [point["value"] for point in preview.json()["points"]],
            [70.0, 71.0, 72.0],
        )

        # AC-DET-03: over the limit it refuses instead of truncating quietly.
        too_large = self.client.get(
            f"/api/time-series/catalog/inputs/{signal_id}/preview",
            params={
                "revision_id": self.receipt["revision_id"],
                "from": "2026-01-01T00:00:00+00:00",
                "to": "2026-01-01T03:00:00+00:00",
                "sampling": "none",
                "max_points": 2,
            },
        )
        self.assertEqual(too_large.status_code, 422, too_large.text)
        self.assertEqual(
            too_large.json()["error"]["code"], "TS_PREVIEW_TOO_LARGE"
        )

    # -- H-04, H-05 --------------------------------------------------------

    def test_a_compatible_object_is_associated_and_an_incompatible_one_is_blocked(self):
        signal_id = self.signal_id_of("energy_price")

        # H-05 first: the candidate list explains and blocks before anything is
        # sent, and the block carries a stable code.
        candidates = self.client.get(
            f"/api/time-series/catalog/inputs/{signal_id}/object-candidates",
            params={
                "target_project_id": self.project["id"],
                "binding_role_key": "grid_import_price",
                "usage": "association",
                "include_denied": "true",
            },
        )
        self.assertEqual(candidates.status_code, 200, candidates.text)
        by_id = {item["object"]["id"]: item for item in candidates.json()["items"]}
        self.assertTrue(by_id[self.system["id"]]["selectable"])
        self.assertFalse(by_id[self.load["id"]]["selectable"])
        self.assertEqual(
            by_id[self.load["id"]]["compatibility_decision"]["primary_error"]["code"],
            "TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED",
        )

        # H-04: prevalidate, confirm, and the association is active and audited.
        association_id = self.associate(
            signal_id=signal_id, linkable_object_id=self.system["id"]
        )
        self.assertEqual(self.my_association_ids(), [association_id])
        listed = self.client.get(
            f"/api/time-series/catalog/associations/{association_id}"
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()["state"], "active_valid")

        events = self.client.get(
            f"/api/time-series/catalog/associations/{association_id}/events"
        )
        self.assertEqual(events.status_code, 200, events.text)
        created = events.json()["items"][0]
        self.assertEqual(created["event_type"], "created")
        self.assertEqual(created["actor"]["identity"], self.analyst_email)
        self.assertEqual(created["actor"]["role"], "analyst")
        self.assertEqual(created["reason"]["code"], "catalog_association_requested")

        # H-05: the API refuses the same incompatible row it explained, and a
        # batch carrying it commits nothing at all.
        request = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "op-add-inflow",
                    "action": "add",
                    "signal_id": self.signal_id_of("inflow_node_a"),
                    "linkable_object_id": self.system["id"],
                    "binding_role_key": "grid_import_price",
                    "expected_absent": True,
                    "reason_code": "catalog_association_requested",
                },
                {
                    "client_operation_id": "op-forced-load",
                    "action": "add",
                    "signal_id": signal_id,
                    "linkable_object_id": self.load["id"],
                    "binding_role_key": "grid_import_price",
                    "expected_absent": True,
                    "reason_code": "catalog_association_requested",
                },
            ],
        }
        prevalidation = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            request,
        )
        self.assertEqual(prevalidation.status_code, 200, prevalidation.text)
        self.assertFalse(prevalidation.json()["can_commit"])
        self.assertEqual(
            prevalidation.json()["operations"][1]["errors"][0]["code"],
            "TS_COMPAT_OBJECT_TYPE_NOT_ALLOWED",
        )

        forced = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **request,
                "prevalidation_token": prevalidation.json()["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidation.json()["commit_etag"],
                "Idempotency-Key": f"forced-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(forced.status_code, 422, forced.text)
        self.assertEqual(
            forced.json()["error"]["code"], "TS_LINK_BATCH_REJECTED"
        )
        # AC-ASO-02: no partial success -- the compatible row of the same batch
        # did not land either.
        self.assertEqual(self.my_association_ids(), [association_id])

    # -- H-06, H-07 --------------------------------------------------------

    def test_a_binding_pins_a_revision_goes_stale_and_is_replaced_with_a_reason(self):
        signal_id = self.signal_id_of("energy_price")
        association_id = self.associate(
            signal_id=signal_id, linkable_object_id=self.system["id"]
        )

        # H-06: the confirmation shows the revision, coverage and resolution the
        # variant is about to pin.
        created = self.bind(
            {
                "client_operation_id": "bind-grid-price",
                "action": "create",
                "linkable_object_id": self.system["id"],
                "binding_role_key": "grid_import_price",
                "signal_id": signal_id,
                "revision": {
                    "mode": "current",
                    "revision_id": self.receipt["revision_id"],
                    "content_hash": self.receipt["content_hash"],
                },
                "catalog_association_id": association_id,
                "reason_code": "variant_input_selected",
            },
            expected_bindings_revision=0,
        )
        self.assertEqual(created.status_code, 201, created.text)
        binding_id = created.json()["operations"][0]["binding_id"]
        pinned = self.client.get(
            f"{self.variant_root}/time-series-bindings/{binding_id}"
        ).json()
        self.assertEqual(pinned["state"], "valid_current")
        self.assertEqual(pinned["set_revision_id"], self.receipt["revision_id"])
        self.assertEqual(pinned["bound_content_hash"], self.receipt["content_hash"])

        # H-07: the source publishes again. The binding does not move.
        published = self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            set_id=self.receipt["set_id"],
            name="Inputs 2026",
            data_class_key="real",
            timezone="UTC",
            signals=[PRICE_SIGNAL, INFLOW_SIGNAL],
            periods=hourly_periods(3),
            values={
                "energy_price": [81.0, 82.0, 83.0],
                "inflow_node_a": [10.0, 11.0, 12.0],
            },
            actor=self.analyst_email,
        )
        stale = self.client.get(
            f"{self.variant_root}/time-series-bindings/{binding_id}"
        ).json()
        self.assertEqual(stale["state"], "stale")
        self.assertEqual(stale["set_revision_id"], self.receipt["revision_id"])
        self.assertEqual(stale["bound_content_hash"], self.receipt["content_hash"])
        self.assertEqual(
            stale["revision"]["current_revision_id"], published["revision_id"]
        )

        # H-07: and it blocks the run instead of quietly executing an old pin.
        blocked = post_json_with_csrf(
            self.client,
            f"/api/scenarios/{self.scenario['id']}/case/variants/"
            f"{self.variant['id']}/run",
            {
                "range_start": "2026-01-01T00:00:00",
                "range_end": "2026-01-01T03:00:00",
            },
        )
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertEqual(
            blocked.json()["error"]["code"], "TS_BINDING_EXECUTION_BLOCKED"
        )
        self.assertEqual(blocked.json()["error"]["details"][0]["state"], "stale")

        # H-07: replacing demands the comparison and a reason, and the previous
        # binding survives as history.
        replace_request = {
            "client_operation_id": "replace-grid-price",
            "action": "replace",
            "binding_id": binding_id,
            "expected_lifecycle_revision": 1,
            "linkable_object_id": self.system["id"],
            "binding_role_key": "grid_import_price",
            "signal_id": signal_id,
            "revision": {
                "mode": "current",
                "revision_id": published["revision_id"],
                "content_hash": published["content_hash"],
            },
            "catalog_association_id": association_id,
            "reason_code": "new_source_revision_accepted",
            "reason_text": "Revise el cambio de precio y acepto la revision 2.",
        }
        prevalidated = post_json_with_csrf(
            self.client,
            f"{self.variant_root}/time-series-binding-prevalidations",
            {"expected_bindings_revision": 1, "operations": [replace_request]},
        )
        self.assertEqual(prevalidated.status_code, 200, prevalidated.text)
        self.assertTrue(prevalidated.json()["requires_confirmation"])
        comparison = prevalidated.json()["operations"][0]["comparison"]
        self.assertEqual(comparison["before"]["state"], "stale")
        self.assertEqual(
            comparison["after"]["set_revision_id"], published["revision_id"]
        )

        replaced = self.bind(replace_request, expected_bindings_revision=1)
        self.assertEqual(replaced.status_code, 201, replaced.text)
        new_binding_id = replaced.json()["operations"][0]["binding_id"]
        superseded = self.client.get(
            f"{self.variant_root}/time-series-bindings/{binding_id}"
        ).json()
        current = self.client.get(
            f"{self.variant_root}/time-series-bindings/{new_binding_id}"
        ).json()
        self.assertEqual(superseded["status"], "superseded")
        self.assertEqual(superseded["set_revision_id"], self.receipt["revision_id"])
        self.assertEqual(current["state"], "valid_current")
        self.assertEqual(current["supersedes_binding_id"], binding_id)

    # -- H-08, H-09, H-10, H-11 -------------------------------------------

    def test_an_object_specific_series_lives_and_binds_inside_its_own_object(self):
        # H-08: the object exists first; the definition is born from it and
        # carries `Solo este objeto` through every step.
        created = self.client.post(
            f"{self.object_root}/object-series",
            json=LOCAL_DEFINITION,
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": f"define-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        series = created.json()["object_series"]
        signal_id = series["signal_id"]
        self.assertEqual(series["source_kind"], "object_specific")
        self.assertEqual(series["availability"], "awaiting_data")
        self.assertFalse(series["binding_ready"])
        self.assertEqual(
            series["owner"]["linkable_object_id"], self.system["id"]
        )
        target = f"{self.object_root}/object-series/{signal_id}"

        # H-08: the first revision arrives by file, validated in staging, and
        # publishes exactly what the preview showed.
        uploaded = self.client.post(
            f"{target}/revision-ingestions/files",
            files={"file": ("forecast.csv", LOCAL_CSV, "text/csv")},
            data={"mapping": json.dumps(LOCAL_CSV_MAPPING)},
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": f"upload-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(uploaded.status_code, 202, uploaded.text)
        ingestion = uploaded.json()["ingestion"]
        self.assertEqual(ingestion["state"], "ready_to_publish")
        preview = self.client.get(
            f"{target}/revision-ingestions/{ingestion['ingestion_id']}/preview"
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(
            [row["value"] for row in preview.json()["rows"]], [18.4, 19.1]
        )

        first = self.client.post(
            f"{target}/revision-ingestions/{ingestion['ingestion_id']}/publications",
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
        self.assertEqual(first.status_code, 201, first.text)
        first_publication = first.json()["publication"]
        self.assertEqual(
            first_publication["content_hash"],
            ingestion["normalized"]["content_hash"],
        )

        # H-09: the API update seals a second revision without reassigning the
        # identity.
        after_first = self.client.get(target)
        self.assertEqual(after_first.status_code, 200, after_first.text)
        prepared = post_json_with_csrf(
            self.client,
            f"{target}/revision-ingestions/points",
            {
                **LOCAL_POINTS,
                "expected_base": {
                    "revision_id": first_publication["revision_id"],
                    "content_hash": first_publication["content_hash"],
                },
            },
        )
        self.assertEqual(prepared.status_code, 201, prepared.text)
        points_ingestion = prepared.json()["ingestion"]
        second = self.client.post(
            f"{target}/revision-ingestions/"
            f"{points_ingestion['ingestion_id']}/publications",
            json={
                "validation_token": points_ingestion["validation_token"],
                "confirm": False,
                "reason_code": "forecast_refresh",
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": after_first.headers["etag"],
                "Idempotency-Key": f"publish-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(second.status_code, 201, second.text)
        second_publication = second.json()["publication"]
        self.assertNotEqual(
            second_publication["revision_id"], first_publication["revision_id"]
        )
        revisions = self.client.get(f"{target}/revisions")
        self.assertEqual(revisions.status_code, 200, revisions.text)
        self.assertEqual(len(revisions.json()["items"]), 2)
        self.assertEqual(
            self.client.get(target).json()["object_series"]["signal_id"], signal_id
        )

        # H-10: the binding is created with no catalog association in between.
        bound = self.bind(
            {
                "client_operation_id": "bind-local-price",
                "action": "create",
                "linkable_object_id": self.system["id"],
                "binding_role_key": "grid_import_price",
                "signal_id": signal_id,
                "revision": {
                    "mode": "current",
                    "revision_id": second_publication["revision_id"],
                    "content_hash": second_publication["content_hash"],
                },
                "catalog_association_id": None,
                "reason_code": "variant_input_selected",
            },
            expected_bindings_revision=0,
        )
        self.assertEqual(bound.status_code, 201, bound.text)
        binding = self.client.get(
            f"{self.variant_root}/time-series-bindings/"
            f"{bound.json()['operations'][0]['binding_id']}"
        ).json()
        self.assertEqual(binding["state"], "valid_current")
        self.assertEqual(binding["source_kind"], "object_specific")
        self.assertIsNone(binding["catalog_association_id"])
        self.assertEqual(self.my_association_ids(), [])

        # H-11: it never surfaces in the global catalog, under any filter, and
        # it is never a candidate for another object.
        owner = {"owner_project_id": self.project["id"]}
        for params in (
            owner,
            {**owner, "q": "local"},
            {**owner, "semantic_type_key": "energy_price"},
            {**owner, "unit_key": "usd_per_mwh"},
            {**owner, "visibility_scope": "project"},
            {**owner, "signal_status": "active"},
            {**owner, "data_class_key": "forecast"},
            {**owner, "source_kind": "api"},
        ):
            with self.subTest(filters=params):
                listing = self.client.get(
                    "/api/time-series/catalog/inputs", params=params
                )
                self.assertEqual(listing.status_code, 200, listing.text)
                self.assertNotIn(
                    signal_id,
                    [item["signal_id"] for item in listing.json()["items"]],
                )
        candidates = self.client.get(
            f"/api/time-series/catalog/inputs/{signal_id}/object-candidates",
            params={
                "target_project_id": self.project["id"],
                "binding_role_key": "grid_import_price",
                "usage": "association",
                "include_denied": "true",
            },
        )
        self.assertEqual(candidates.status_code, 404, candidates.text)

        # H-08 again, at the end: archiving keeps history, revisions and the
        # binding that already consumed it.
        before_archive = self.client.get(target)
        archived = self.client.post(
            f"{target}/archive",
            json={
                "reason_code": "source_retired",
                "reason_text": "El pronostico local ya no se mantiene.",
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": before_archive.headers["etag"],
            },
        )
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(
            archived.json()["object_series"]["availability"], "archived"
        )
        self.assertEqual(
            len(self.client.get(f"{target}/revisions").json()["items"]), 2
        )

    # -- H-12, H-13, H-14 --------------------------------------------------

    def test_loading_over_a_shared_source_shows_the_impact_and_has_two_exits(self):
        signal_id = self.signal_id_of("energy_price")
        # The source is shared first: an association created against a set that
        # is later promoted is stale by construction, and a stale association is
        # not a binding candidate.
        self.promote_the_shared_set()
        association_id = self.associate(
            signal_id=signal_id, linkable_object_id=self.system["id"]
        )
        self.associate(
            signal_id=signal_id,
            linkable_object_id=self.neighbour_object["id"],
            project_id=self.neighbour["id"],
        )
        bound = self.bind(
            {
                "client_operation_id": "bind-shared-price",
                "action": "create",
                "linkable_object_id": self.system["id"],
                "binding_role_key": "grid_import_price",
                "signal_id": signal_id,
                "revision": {
                    "mode": "current",
                    "revision_id": self.receipt["revision_id"],
                    "content_hash": self.receipt["content_hash"],
                },
                "catalog_association_id": association_id,
                "reason_code": "variant_input_selected",
            },
            expected_bindings_revision=0,
        )
        self.assertEqual(bound.status_code, 201, bound.text)
        binding_id = bound.json()["operations"][0]["binding_id"]

        association_root = (
            f"{self.object_root}/catalog-associations/{association_id}"
        )

        # H-12: before deciding anything, the object shows scope, owner, current
        # revision, associations, other objects and projects, and exactly which
        # bindings will go stale.
        view = self.client.get(f"{association_root}?intent=local")
        self.assertEqual(view.status_code, 200, view.text)
        impact = view.json()["impact"]
        self.assertEqual(impact["source"]["visibility_scope"], "global")
        self.assertEqual(impact["source"]["owner_project_id"], self.project["id"])
        self.assertEqual(
            impact["source"]["current_revision_id"], self.receipt["revision_id"]
        )
        self.assertEqual(impact["associations"], {"total": 2, "other_objects": 1})
        self.assertEqual(impact["bindings"]["total_active"], 1)
        self.assertEqual(impact["effect"]["bindings_will_become_stale"], 1)
        self.assertEqual(
            sorted(
                {
                    consumer["project_id"]
                    for consumer in impact["listed_consumers"]
                }
            ),
            sorted({self.project["id"], self.neighbour["id"]}),
        )
        self.assertEqual(
            [
                consumer["linkable_object_id"]
                for consumer in impact["listed_consumers"]
            ],
            [self.system["id"], self.neighbour_object["id"]],
        )
        self.assertFalse(impact["consumers_truncated"])
        # H-12: and the object is offered its local alternative first.
        self.assertEqual(
            [alternative["kind"] for alternative in view.json()["alternatives"]],
            ["derive_object_specific", "publish_shared"],
        )

        # AC-SHR-05: the analyst cannot publish over a global source at all.
        refused = post_json_with_csrf(
            self.client,
            f"{association_root}/shared-series/revision-ingestions/points",
            self.shared_points(),
        )
        self.assertEqual(refused.status_code, 403, refused.text)
        self.assertEqual(
            refused.json()["code"], "TS_SHARED_REVISION_ADMIN_REQUIRED"
        )

        # H-13, first exit: the local derivation. It carries lineage and moves
        # nothing that already exists.
        derivation = {
            "object_series_key": "local_price_copy",
            "display_name": "Precio local (copia)",
            "description": "Copia local del precio compartido",
            "reason_code": "local_copy_preferred",
            "reason_text": "El objeto necesita su propia curva.",
        }
        prevalidated = post_json_with_csrf(
            self.client,
            f"{association_root}/object-series-derivation-prevalidations",
            derivation,
        )
        self.assertEqual(prevalidated.status_code, 200, prevalidated.text)
        self.assertTrue(prevalidated.json()["can_commit"])
        self.assertEqual(
            prevalidated.json()["reassignments"],
            {"associations": 0, "bindings": 0},
        )
        derived = self.client.post(
            f"{association_root}/object-series-derivations",
            json={
                **derivation,
                "prevalidation_token": prevalidated.json()["prevalidation_token"],
                "confirmed": True,
                "source_revision": {
                    "revision_id": self.receipt["revision_id"],
                    "content_hash": self.receipt["content_hash"],
                },
            },
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": f"derive-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(derived.status_code, 201, derived.text)
        payload = derived.json()["derivation"]
        self.assertEqual(
            payload["lineage"]["kind"], "catalog_object_specific_copy"
        )
        self.assertEqual(
            payload["lineage"]["source_revision_id"], self.receipt["revision_id"]
        )
        self.assertEqual(
            payload["reassignments"], {"associations": 0, "bindings": 0}
        )
        # The shared source did not move, and neither did the binding.
        self.assertEqual(
            self.client.get(association_root).json()["impact"]["source"][
                "current_revision_id"
            ],
            self.receipt["revision_id"],
        )
        self.assertEqual(
            self.client.get(
                f"{self.variant_root}/time-series-bindings/{binding_id}"
            ).json()["state"],
            "valid_current",
        )

        # H-14, second exit: the admin publishes for everyone. Confirmation and
        # comprehension are mandatory, and the consumers are left visibly stale.
        self.login(self.admin_email, "admin pass")
        prepared = post_json_with_csrf(
            self.client,
            f"{association_root}/shared-series/revision-ingestions/points",
            self.shared_points(),
        )
        self.assertEqual(prepared.status_code, 201, prepared.text)
        ingestion = prepared.json()["ingestion"]
        self.assertEqual(ingestion["impact"]["bindings"]["total_active"], 1)
        self.assertEqual(
            ingestion["impact"]["effect"]["bindings_will_become_stale"], 1
        )

        unconfirmed = self.publish_shared(
            association_root, ingestion, confirm=False
        )
        self.assertEqual(unconfirmed.status_code, 409, unconfirmed.text)
        self.assertEqual(
            unconfirmed.json()["code"],
            "TS_SHARED_REVISION_CONFIRMATION_REQUIRED",
        )

        published = self.publish_shared(association_root, ingestion)
        self.assertEqual(published.status_code, 201, published.text)
        publication = published.json()["publication"]
        self.assertEqual(publication["outcome"], "published")
        self.assertNotEqual(
            publication["revision_id"], self.receipt["revision_id"]
        )
        # AC-SHR-08: stale, and not resolved by the same action.
        self.assertEqual(
            publication["staleness"],
            {
                "bindings_now_stale": 1,
                "bindings_still_stale": 1,
                "resolved_in_this_action": 0,
                "resolution_required": True,
            },
        )
        stale = self.client.get(
            f"{self.variant_root}/time-series-bindings/{binding_id}"
        ).json()
        self.assertEqual(stale["state"], "stale")
        self.assertEqual(stale["set_revision_id"], self.receipt["revision_id"])
        self.assertEqual(
            stale["revision"]["current_revision_id"], publication["revision_id"]
        )

    # -- H-15 --------------------------------------------------------------

    def test_an_admin_promotes_and_demotes_a_set_without_losing_history(self):
        signal_id = self.signal_id_of("energy_price")
        association_id = self.associate(
            signal_id=signal_id, linkable_object_id=self.system["id"]
        )

        # AC-SCO-02: the analyst never gets there.
        refused = post_json_with_csrf(
            self.client,
            f"/api/time-series/catalog/sets/{self.receipt['set_id']}"
            "/scope-prevalidations",
            {"target_scope": "global"},
        )
        self.assertEqual(refused.status_code, 403, refused.text)
        self.assertEqual(
            refused.json()["error"]["code"], "TS_SCOPE_ADMIN_REQUIRED"
        )

        self.login(self.admin_email, "admin pass")

        # H-15: the impact is visible before the change.
        preview = self.prevalidate_scope("global")
        self.assertTrue(preview["requires_confirmation"])
        self.assertEqual(preview["impact"]["set"]["visibility_scope"], "project")
        self.assertEqual(preview["impact"]["set"]["scope_revision"], 0)

        promoted = self.commit_scope(
            preview,
            reason_text="Aprobado para reuso entre proyectos internos.",
            request_id="req-promote-inputs",
        )
        self.assertEqual(promoted.status_code, 201, promoted.text)
        self.assertEqual(promoted.json()["outcome"], "promoted_global")

        # AC-SCO-01: same row, same owner, same revisions, same associations.
        after = self.prevalidate_scope("project")
        self.assertEqual(after["impact"]["set"]["visibility_scope"], "global")
        self.assertEqual(after["impact"]["set"]["scope_revision"], 1)
        self.assertEqual(
            after["impact"]["current_revision"]["id"], self.receipt["revision_id"]
        )
        self.assertEqual(
            self.client.get(
                f"/api/time-series/catalog/associations/{association_id}"
            ).status_code,
            200,
        )
        self.assertEqual(
            len(
                self.client.get(
                    f"/api/time-series/catalog/inputs/{signal_id}/revisions"
                ).json()["items"]
            ),
            1,
        )

        # AC-SCO-04: repeating an effective change writes nothing.
        repeated = self.commit_scope(
            self.prevalidate_scope("global"),
            reason_text="Ya estaba aprobado.",
            request_id="req-promote-again",
        )
        self.assertEqual(repeated.status_code, 409, repeated.text)
        self.assertEqual(
            repeated.json()["error"]["code"], "TS_SCOPE_ALREADY_EFFECTIVE"
        )

        # AC-SCO-03: with a consumer in another project, demotion fails closed
        # and enumerates who is in the way.
        cross_project = self.associate(
            signal_id=signal_id,
            linkable_object_id=self.neighbour_object["id"],
            project_id=self.neighbour["id"],
        )
        blocked = self.prevalidate_scope("project")
        self.assertFalse(blocked["can_commit"])
        self.assertEqual(
            blocked["impact"]["associations"]["other_project_count"], 1
        )
        self.assertEqual(
            [
                row["association_id"]
                for row in blocked["impact"]["associations"]["items"]
                if row["project_id"] == self.neighbour["id"]
            ],
            [cross_project],
        )
        refused_demotion = self.commit_scope(
            blocked,
            reason_text="Devolver el reuso al proyecto propietario.",
            request_id="req-demote-blocked",
        )
        self.assertEqual(refused_demotion.status_code, 422, refused_demotion.text)
        self.assertEqual(
            refused_demotion.json()["error"]["code"], "TS_SCOPE_INVALID_STATE"
        )
        self.assertEqual(
            self.prevalidate_scope("project")["impact"]["set"]["visibility_scope"],
            "global",
        )

        # H-15: once the cross-project consumer is gone, demotion succeeds and
        # the history is still there.
        retired = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            {
                "target_project_id": self.neighbour["id"],
                "operations": [
                    {
                        "client_operation_id": "retire-cross-project",
                        "action": "archive",
                        "association_id": cross_project,
                        "expected_lifecycle_revision": 1,
                        "reason_code": "source_retired",
                        "reason_text": "El objeto vecino deja de usar la fuente.",
                    }
                ],
            },
        )
        self.assertEqual(retired.status_code, 200, retired.text)
        removed = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                "target_project_id": self.neighbour["id"],
                "operations": [
                    {
                        "client_operation_id": "retire-cross-project",
                        "action": "archive",
                        "association_id": cross_project,
                        "expected_lifecycle_revision": 1,
                        "reason_code": "source_retired",
                        "reason_text": "El objeto vecino deja de usar la fuente.",
                    }
                ],
                "prevalidation_token": retired.json()["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": retired.json()["commit_etag"],
                "Idempotency-Key": f"retire-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(removed.status_code, 201, removed.text)

        demoted = self.commit_scope(
            self.prevalidate_scope("project"),
            reason_text="Devolver el reuso al proyecto propietario.",
            request_id="req-demote-inputs",
        )
        self.assertEqual(demoted.status_code, 201, demoted.text)
        self.assertEqual(demoted.json()["outcome"], "demoted_project")
        final = self.prevalidate_scope("global")["impact"]
        self.assertEqual(final["set"]["visibility_scope"], "project")
        self.assertEqual(final["set"]["scope_revision"], 2)
        self.assertEqual(
            final["current_revision"]["id"], self.receipt["revision_id"]
        )
        # The association of the owner project is untouched by both moves.
        self.assertEqual(
            self.client.get(
                f"/api/time-series/catalog/associations/{association_id}"
            ).status_code,
            200,
        )

    # -- H-16 --------------------------------------------------------------

    def test_an_external_identity_gets_the_same_answer_on_the_whole_surface(self):
        # Real rows exist first, so the refusal is proven against a catalog that
        # has something to reveal.
        signal_id = self.signal_id_of("energy_price")
        association_id = self.associate(
            signal_id=signal_id, linkable_object_id=self.system["id"]
        )
        bound = self.bind(
            {
                "client_operation_id": "bind-grid-price",
                "action": "create",
                "linkable_object_id": self.system["id"],
                "binding_role_key": "grid_import_price",
                "signal_id": signal_id,
                "revision": {
                    "mode": "current",
                    "revision_id": self.receipt["revision_id"],
                    "content_hash": self.receipt["content_hash"],
                },
                "catalog_association_id": association_id,
                "reason_code": "variant_input_selected",
            },
            expected_bindings_revision=0,
        )
        self.assertEqual(bound.status_code, 201, bound.text)
        binding_id = bound.json()["operations"][0]["binding_id"]

        self.store.create_user(
            email="ts7-external@example.local",
            display_name="External",
            role="external",
            password_hash=hash_password("external pass"),
        )
        self.login(
            "ts7-external@example.local", "external pass", next_path="/react/client"
        )

        # AC-SEG-01 to AC-SEG-04: knowing a real id changes nothing. The global
        # surface is refused before any id is resolved; the object-scoped and
        # variant-scoped surfaces answer as if nothing were there. In both
        # families a real id and an invented one are indistinguishable.
        catalog_surface = [
            "/api/time-series/catalog/inputs",
            f"/api/time-series/catalog/inputs/{signal_id}",
            "/api/time-series/catalog/inputs/999999",
            f"/api/time-series/catalog/inputs/{signal_id}/revisions",
            (
                f"/api/time-series/catalog/inputs/{signal_id}/preview"
                "?revision_id=1&from=2026-01-01T00%3A00%3A00%2B00%3A00"
                "&to=2026-01-01T01%3A00%3A00%2B00%3A00"
            ),
            f"/api/time-series/catalog/inputs/{signal_id}/object-candidates",
            "/api/time-series/catalog/descriptors?kind=semantic_type",
            "/api/time-series/catalog/associations",
            f"/api/time-series/catalog/associations/{association_id}",
            f"/api/time-series/catalog/associations/{association_id}/events",
            "/api/time-series/catalog/results",
            "/api/time-series/catalog/legacy",
        ]
        object_surface = [
            self.object_root,
            f"/api/projects/{self.project['id']}/linkable-objects/999999"
            "/time-series",
            f"{self.variant_root}/time-series-bindings",
            f"{self.variant_root}/time-series-bindings/{binding_id}",
            f"{self.variant_root}/time-series-bindings/999999",
        ]

        refusals = {}
        for family, paths, expected in (
            ("catalog", catalog_surface, (403, {"detail": "forbidden"})),
            ("object", object_surface, (404, {"detail": "not found"})),
        ):
            observed = [(path, self.client.get(path)) for path in paths]
            for path, response in observed:
                with self.subTest(path=path):
                    self.assertEqual(
                        (response.status_code, response.json()), expected, path
                    )
            # AC-SEG-02: one shape per family -- no counts, no identifiers,
            # nothing that betrays whether the row was there.
            refusals[family] = {
                json.dumps(response.json()) for _, response in observed
            }
            self.assertEqual(len(refusals[family]), 1)

        # The mutation surfaces are refused by the same gate as their reads.
        writes = [
            (
                403,
                post_json_with_csrf(
                    self.client,
                    "/api/time-series/catalog/association-prevalidations",
                    {"target_project_id": self.project["id"], "operations": []},
                ),
            ),
            (
                403,
                post_json_with_csrf(
                    self.client,
                    f"/api/time-series/catalog/sets/{self.receipt['set_id']}"
                    "/scope-prevalidations",
                    {"target_scope": "global"},
                ),
            ),
            (
                404,
                post_json_with_csrf(
                    self.client,
                    f"{self.variant_root}/time-series-binding-prevalidations",
                    {"expected_bindings_revision": 0, "operations": []},
                ),
            ),
            (
                404,
                self.client.post(
                    f"{self.object_root}/object-series",
                    json=LOCAL_DEFINITION,
                    headers={
                        **csrf_headers(self.client),
                        "Idempotency-Key": f"external-{uuid.uuid4().hex}",
                    },
                ),
            ),
        ]
        for expected_status, response in writes:
            with self.subTest(write=str(response.request.url)):
                self.assertEqual(response.status_code, expected_status, response.text)

        # Nothing the external identity touched wrote anything.
        self.login(self.analyst_email, "analyst pass")
        self.assertEqual(self.my_association_ids(), [association_id])
        self.assertEqual(
            [
                item["source_kind"]
                for item in self.client.get(self.object_root).json()["items"]
            ],
            ["catalog"],
        )

    # -- Definition of done, point 6 ---------------------------------------

    def test_the_ledger_reconstructs_who_made_every_mutation_and_why(self):
        signal_id = self.signal_id_of("energy_price")
        association_id = self.associate(
            signal_id=signal_id, linkable_object_id=self.system["id"]
        )
        bound = self.bind(
            {
                "client_operation_id": "bind-grid-price",
                "action": "create",
                "linkable_object_id": self.system["id"],
                "binding_role_key": "grid_import_price",
                "signal_id": signal_id,
                "revision": {
                    "mode": "current",
                    "revision_id": self.receipt["revision_id"],
                    "content_hash": self.receipt["content_hash"],
                },
                "catalog_association_id": association_id,
                "reason_code": "variant_input_selected",
            },
            expected_bindings_revision=0,
        )
        self.assertEqual(bound.status_code, 201, bound.text)
        binding_id = bound.json()["operations"][0]["binding_id"]

        # The admin makes the third mutation, so the ledger has to distinguish
        # two identities and two roles, not just record "somebody".
        self.login(self.admin_email, "admin pass")
        promoted = self.commit_scope(
            self.prevalidate_scope("global"),
            reason_text="Aprobado para reuso entre proyectos internos.",
            request_id="req-promote-inputs",
        )
        self.assertEqual(promoted.status_code, 201, promoted.text)
        self.login(self.analyst_email, "analyst pass")

        ledgers = {
            "association": self.client.get(
                f"/api/time-series/catalog/associations/{association_id}/events"
            ),
            "binding": self.client.get(
                f"{self.variant_root}/time-series-bindings/{binding_id}/events"
            ),
        }
        for name, response in ledgers.items():
            with self.subTest(ledger=name):
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json()["items"])
                for event in response.json()["items"]:
                    # Actor, role, reason, request and moment: every mutation
                    # is reconstructible from its own row.
                    self.assertEqual(event["actor"]["identity"], self.analyst_email)
                    self.assertEqual(event["actor"]["role"], "analyst")
                    self.assertTrue(event["actor"]["user_id"])
                    self.assertTrue(event["reason"]["code"])
                    self.assertTrue(event["request_id"])
                    self.assertTrue(event["occurred_at"])
                    self.assertTrue(event["event_type"])

        scope_events = self.store.link_layer_table_names()["time_series_scope_events"]
        recorded = [
            dict(row)
            for row in self.store.connection.execute(
                f"SELECT * FROM {scope_events} WHERE time_series_set_id = ?",
                (self.receipt["set_id"],),
            ).fetchall()
        ]
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["actor_identity_snapshot"], self.admin_email)
        self.assertEqual(recorded[0]["actor_role_snapshot"], "admin")
        self.assertEqual(recorded[0]["reason_code"], "administrative_scope_change")
        self.assertEqual(
            recorded[0]["reason_text"],
            "Aprobado para reuso entre proyectos internos.",
        )
        self.assertEqual(recorded[0]["request_id"], "req-promote-inputs")

        # AC-SEG-05: no public route erases what the ledger recorded, and the
        # ledger itself refuses the deletion even below the API.
        deletions = [
            self.client.delete(
                f"/api/time-series/catalog/associations/{association_id}/events",
                headers=csrf_headers(self.client),
            ),
            self.client.delete(
                f"{self.variant_root}/time-series-bindings/{binding_id}/events",
                headers=csrf_headers(self.client),
            ),
        ]
        for response in deletions:
            with self.subTest(deletion=str(response.request.url)):
                self.assertIn(response.status_code, (404, 405), response.text)

        events_table = self.store.link_layer_table_names()["time_series_link_events"]
        for statement in (
            f"DELETE FROM {events_table}",
            f"UPDATE {events_table} SET reason_code = 'rewritten'",
        ):
            with self.subTest(statement=statement):
                self.assert_ledger_refuses(statement)
        self.assertTrue(
            self.client.get(
                f"/api/time-series/catalog/associations/{association_id}/events"
            ).json()["items"]
        )


class TS7MigrationAcceptanceTests(unittest.TestCase):
    """H-17 and H-18: the operator's half of the story.

    The seam is the store's public migration surface, the same one the C0 to C6
    slices use. A legacy source is built with the legacy writer, migrated, and
    the cutover is proven to close every legacy write path.
    """

    def setUp(self):
        self.store = AnalystStore("sqlite:///:memory:")
        self.addCleanup(self.store.close)
        self.recovery = tempfile.TemporaryDirectory()
        self.addCleanup(self.recovery.cleanup)
        self.project = self.store.create_project(name="Cuenca Norte")
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Base"
        )
        case = self.store.get_or_create_case_for_scenario(self.scenario["id"])
        self.variant = self.store.get_or_create_default_input_variant(case["id"])
        self.legacy_set = self.import_legacy_price_set()
        self.legacy_binding = self.store.upsert_case_time_series_binding(
            case_input_variant_id=self.variant["id"],
            signal_key="import_price_usd_per_mwh",
            time_series_set_id=self.legacy_set["id"],
            created_by="legacy_analyst",
        )

    def import_legacy_price_set(self):
        start = datetime(2026, 1, 1)
        prepared = prepare_time_series_catalog_import(
            rows=[
                {
                    "period_start": (start + timedelta(hours=offset)).isoformat(),
                    "hours": "1.0",
                    "value": str(70.0 + offset),
                }
                for offset in range(3)
            ],
            request=CatalogImportRequest(
                set_name="Precio importacion",
                version_label="v1",
                data_kind="real",
                timezone="UTC",
                timestamp_column="period_start",
                duration_hours_column="hours",
                signal_mappings=[
                    CatalogSignalMappingRequest(
                        source_column="value",
                        signal_key="import_price_usd_per_mwh",
                    )
                ],
            ),
        )
        return self.store.import_time_series_catalog_set(
            scenario_id=self.scenario["id"],
            source={
                "id": "ts7-023-price",
                "original_filename": "price.csv",
                "media_type": "text/csv",
                "checksum": "sha256:ts7-023-price",
            },
            prepared_import=prepared,
            created_by="legacy_analyst",
        )

    # -- H-17 --------------------------------------------------------------

    def test_the_migrator_run_twice_on_an_unchanged_source_converges(self):
        recovery = self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name)
        )
        self.assertTrue(
            self.store.verify_c0_manifest(
                manifest=recovery["manifest"],
                manifest_signature=recovery["manifest_signature"],
            )
        )

        for phase, backfill in (
            ("C2", self.store.backfill_time_series_c2),
            ("C3", self.store.backfill_time_series_c3),
            ("C4", self.store.backfill_time_series_c4),
        ):
            with self.subTest(phase=phase):
                first = backfill(actor="internal_admin")
                second = backfill(actor="internal_admin")

                # H-17: the same manifest, zero new rows, zero altered mappings.
                self.assertEqual(first["manifest"], second["manifest"])
                self.assertEqual(second["created_rows"], 0)
                self.assertEqual(second["mapping_changes"], 0)
                self.assertEqual(
                    self.store.read_migration_anomalies(
                        int(second["migration_run_id"])
                    ),
                    [],
                )

        # AC-MIG-05: the shadow comparison finds no difference on any of the
        # six dimensions it is required to compare.
        shadow = self.store.verify_time_series_c5_shadow(actor="internal_admin")
        self.assertEqual(shadow["status"], "proven")
        self.assertEqual(shadow["manifest"]["differences"], [])
        self.assertEqual(
            shadow["manifest"]["shadow_read"]["dimensions"],
            ["semantics", "counts", "values", "hashes", "authorization", "lineage"],
        )
        self.assertEqual(shadow["manifest"]["settled_source"]["pending_dirty_roots"], 0)
        self.assertIsNone(self.store.read_legacy_mutation_pause())

    # -- H-18 --------------------------------------------------------------

    def test_after_the_cutover_no_write_reaches_the_legacy_tables(self):
        self.store.take_c0_recovery_point(
            actor="internal_admin", copy_directory=Path(self.recovery.name)
        )
        self.store.backfill_time_series_c2(actor="internal_admin")
        self.store.backfill_time_series_c3(actor="internal_admin")
        self.store.backfill_time_series_c4(actor="internal_admin")
        self.store.verify_time_series_c5_shadow(actor="internal_admin")

        receipt = self.store.cut_over_time_series_c6(actor="internal_admin")

        self.assertEqual(receipt["status"], "proven")
        state = self.store.read_time_series_c6_state()
        self.assertTrue(state["cutover_active"])
        self.assertTrue(state["ts_next_canonical_read"])
        self.assertTrue(state["ts_next_canonical_write"])

        # H-18, by code: the legacy writer refuses.
        with self.assertRaises(MigrationControlError) as by_code:
            self.import_legacy_price_set()
        self.assertEqual(by_code.exception.code, "TS_LEGACY_WRITE_FORBIDDEN")
        with self.assertRaises(MigrationControlError) as binding_refused:
            self.store.upsert_case_time_series_binding(
                case_input_variant_id=self.variant["id"],
                signal_key="import_price_usd_per_mwh",
                time_series_set_id=self.legacy_set["id"],
                created_by="legacy_analyst",
            )
        self.assertEqual(
            binding_refused.exception.code, "TS_LEGACY_WRITE_FORBIDDEN"
        )

        # H-18, by permissions: the database refuses the same three tables even
        # when the write bypasses the writer entirely.
        protection = self.store.read_legacy_write_protection()
        self.assertTrue(protection["code_guard_enabled"])
        self.assertTrue(protection["database_guard_enabled"])
        self.assertEqual(
            set(protection["required_tables"]),
            {
                "time_series_values",
                "time_series_signals",
                "case_time_series_bindings",
            },
        )
        for statement in (
            "UPDATE time_series_values SET value_numeric = 999",
            "UPDATE time_series_signals SET signal_key = 'tampered'",
            "UPDATE case_time_series_bindings SET signal_key = 'tampered'",
        ):
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(
                    Exception, "TS_LEGACY_WRITE_FORBIDDEN"
                ):
                    self.store.connection.execute(statement)

        # The legacy reads still answer, now served by the canonical model.
        legacy = self.store.get_time_series_set(
            self.project["id"], self.legacy_set["id"]
        )
        self.assertEqual(legacy["signal_count"], 1)

        # AC-MIG-02 again, after the cutover: the phase is idempotent.
        self.assertEqual(
            self.store.cut_over_time_series_c6(actor="internal_admin"), receipt
        )


class TS7DocumentationTests(unittest.TestCase):
    """Chapter 11.8 closes on a record, not only on a green run."""

    def test_the_acceptance_record_and_the_manual_narrative_exist(self):
        iteration = REPO_ROOT / "docs" / "series_tiempo" / "iter7"
        acceptance = (iteration / "acceptance_ts7.md").read_text(encoding="utf-8")
        manual = (iteration / "pruebas_manuales_ts7.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        # The record names every part of the definition of done.
        for heading in (
            "The Blocking Matrix On PostgreSQL",
            "Regression, TS-2 To TS-6",
            "Frontend Gates",
            "Performance (AC-PER-01 To AC-PER-07)",
            "Migrator Convergence And Shadow",
            "The Ledger",
            "Manual Chrome Verification",
            "Contract Changes",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, acceptance)

        # The seven performance budgets are recorded, not just the three that
        # TS7-005 measured.
        for identifier in (f"AC-PER-0{index}" for index in range(1, 8)):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, acceptance)

        # The manual narrative covers the three complete flows of point 5.
        for flow in (
            "Flujo 1: Vincular Una Fuente Generica",
            "Flujo 2: Crear Y Cargar Una Serie Especifica",
            "Flujo 3: Carga Compartida Desde El Objeto, Con Sus Dos Salidas",
        ):
            with self.subTest(flow=flow):
                self.assertIn(flow, manual)
        # The credentials are the real ones, and no test administrator is made.
        self.assertIn("MAIL_USUARIO_TEST", manual)
        self.assertIn("no se crean", manual)

        self.assertIn("TS-7: Global Catalog And Object-Specific Series", readme)
        self.assertIn("tests.test_ts7_acceptance", readme)

    def test_the_saved_performance_evidence_meets_every_budget(self):
        evidence = json.loads(
            (
                REPO_ROOT
                / "docs"
                / "series_tiempo"
                / "iter7"
                / "performance"
                / "ts7-023-postgresql-acceptance.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(evidence["engine"], "postgresql")
        budgets = evidence["budgets"]
        self.assertEqual(
            sorted(budgets), [f"AC-PER-0{index}" for index in range(1, 8)]
        )
        for identifier, measured in budgets.items():
            with self.subTest(identifier=identifier):
                self.assertIsNotNone(measured["p95_ms"], identifier)
                self.assertLessEqual(
                    measured["p95_ms"], measured["budget_ms"], identifier
                )

        # AC-CAT-04: no list or detail plan walks periods or values, and the
        # preview, which is allowed to read them, does it through the index.
        self.assertFalse(evidence["reads_periods_or_values"])
        self.assertFalse(evidence["preview_scans_values"])
        self.assertIn("revision_preview", evidence["reference_plans"])

    def test_the_issue_and_the_tracker_close_the_iteration(self):
        issues = REPO_ROOT / "docs" / "series_tiempo" / "iter7" / "issues"
        issue = (issues / "TS7-023-prove-ts7-end-to-end.md").read_text(
            encoding="utf-8"
        )
        tracker = (issues / "tracker_ts7_catalogo_global.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Status: Done", issue)
        self.assertNotIn("- [ ]", issue)
        self.assertIn("tests.test_ts7_acceptance", issue)

        self.assertIn(
            "| TS7-023 | Prove TS-7 End To End | AFK | ready-for-agent | Done |",
            tracker,
        )
        self.assertIn("TS7-023 | Todo -> Done", tracker)
        self.assertNotIn("| Todo |", tracker)


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL acceptance narrative",
)
class PostgresTS7AcceptanceTests(TS7AcceptanceTests):
    """Chapter 11.8, point 1: the same narrative on the development engine."""

    def setUp(self):
        self.store = AnalystStore(POSTGRES_TEST_DATABASE_URL)
        self.rollback = self.store.connection._connection.transaction(  # noqa: SLF001
            force_rollback=True
        )
        self.rollback.__enter__()
        self.build_fixture()

    def tearDown(self):
        try:
            self.rollback.__exit__(None, None, None)
        finally:
            self.store.close()


if __name__ == "__main__":
    unittest.main()
