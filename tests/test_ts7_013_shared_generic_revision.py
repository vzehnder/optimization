"""TS7-013 shared generic revision from the object, or a local derivation."""

import os
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

PERIODS = [
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
]

POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class SharedGenericRevisionApiTests(unittest.TestCase):
    database_url = "sqlite:///:memory:"

    def setUp(self):
        self.store = AnalystStore(self.database_url)
        self.build_fixture()

    def build_fixture(self):
        suffix = uuid.uuid4().hex[:10]
        self.client = TestClient(create_app(store=self.store, auth_enabled=True))
        self.analyst_email = f"ts7-013-analyst-{suffix}@example.local"
        self.admin_email = f"ts7-013-admin-{suffix}@example.local"
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
        self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name=f"Inputs 2026 {suffix}",
            data_class_key="real",
            timezone="UTC",
            signals=[PRICE_SIGNAL],
            periods=PERIODS,
            values={"energy_price": [70.0, 71.0]},
            actor=self.analyst_email,
        )
        self.signal_id = next(
            item["signal_id"]
            for item in self.client.get("/api/time-series/catalog/inputs").json()[
                "items"
            ]
            if item["identity"]["series_key"] == "energy_price"
        )
        self.object = self.store.ensure_global_signal_slot(
            project_id=self.project["id"], display_name="Sistema"
        )
        self.neighbour_object = self.store.ensure_global_signal_slot(
            project_id=self.neighbour["id"], display_name="Sistema vecino"
        )
        self.promote_set_to_global()
        self.association_id = self.associate(
            project_id=self.project["id"], linkable_object_id=self.object["id"]
        )
        self.neighbour_association_id = self.associate(
            project_id=self.neighbour["id"],
            linkable_object_id=self.neighbour_object["id"],
        )
        self.scenario = self.store.create_scenario(
            project_id=self.project["id"], name="Plan base"
        )
        self.variant = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case/default-variant"
        ).json()["variant"]

    def tearDown(self):
        self.store.close()

    # -- fixtures ---------------------------------------------------------

    def login(self, email, password):
        response = login_json_with_csrf(self.client, email, password)
        self.assertEqual(response.status_code, 200, response.text)

    def promote_set_to_global(self):
        """TS7-014 owns the administrative promotion; this fixture needs the
        resulting state, not the journey."""

        set_id = int(
            self.store.read_catalog_input_detail(self.signal_id)["set"]["id"]
        )
        with self.store._lock:
            with self.store._database_transaction():
                self.store.connection.execute(
                    f"UPDATE {self.store._canonical('time_series_sets')} "
                    "SET visibility_scope = 'global' WHERE id = ?",
                    (set_id,),
                )
                self.store._project_catalog_entries(
                    set_id=set_id, now="2026-01-02T00:00:00Z"
                )
                self.store._raise_catalog_generation(now="2026-01-02T00:00:00Z")
        self.set_id = set_id

    def associate(self, *, project_id, linkable_object_id):
        request = {
            "target_project_id": project_id,
            "operations": [
                {
                    "client_operation_id": f"add-{linkable_object_id}",
                    "action": "add",
                    "signal_id": self.signal_id,
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

    @property
    def object_root(self):
        return (
            f"/api/projects/{self.project['id']}/linkable-objects/"
            f"{self.object['id']}/time-series"
        )

    @property
    def association_root(self):
        return f"{self.object_root}/catalog-associations/{self.association_id}"

    def shared_points(self, *, first=81.0, second=82.0, series_key="energy_price"):
        return {
            "mode": "replace_full",
            "expected_base": {
                "revision_id": self.current_revision()["revision_id"],
                "content_hash": self.current_revision()["content_hash"],
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
                    "timestamp_start": "2026-01-01T00:00:00+00:00",
                    "duration_seconds": 3600,
                    "values": {series_key: {"value": first}},
                },
                {
                    "timestamp_start": "2026-01-01T01:00:00+00:00",
                    "duration_seconds": 3600,
                    "values": {series_key: {"value": second}},
                },
            ],
        }

    def bind_the_shared_source(self):
        """One active binding, so the impact has something real to stale."""

        revision = self.current_revision()
        request = {
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
                        "revision_id": revision["revision_id"],
                        "content_hash": revision["content_hash"],
                    },
                    "catalog_association_id": self.association_id,
                    "reason_code": "variant_input_selected",
                }
            ],
        }
        variant_root = (
            f"/api/scenarios/{self.scenario['id']}/case-variants/"
            f"{self.variant['id']}"
        )
        prevalidated = post_json_with_csrf(
            self.client,
            f"{variant_root}/time-series-binding-prevalidations",
            request,
        )
        self.assertEqual(prevalidated.status_code, 200, prevalidated.text)
        committed = self.client.post(
            f"{variant_root}/time-series-binding-batches",
            json={
                **request,
                "prevalidation_token": prevalidated.json()["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidated.json()["commit_etag"],
                "Idempotency-Key": f"bind-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(committed.status_code, 201, committed.text)
        return committed.json()["operations"][0]["binding_id"]

    def prepare_shared(self, **kwargs):
        prepared = post_json_with_csrf(
            self.client,
            f"{self.association_root}/shared-series/revision-ingestions/points",
            self.shared_points(**kwargs),
        )
        self.assertEqual(prepared.status_code, 201, prepared.text)
        return prepared.json()["ingestion"]

    def publish_shared(self, ingestion, **overrides):
        body = {
            "validation_token": ingestion["validation_token"],
            "impact_fingerprint": ingestion["impact_fingerprint"],
            "confirm": True,
            "comprehension_acknowledged": True,
            "reason_code": "shared_price_update",
            "reason_text": "Mesa de precios de enero",
        }
        body.update(overrides)
        return self.client.post(
            f"{self.association_root}/shared-series/revision-ingestions/"
            f"{ingestion['ingestion_id']}/publications",
            json=body,
            headers={
                **csrf_headers(self.client),
                "If-Match": ingestion["etag"],
                "Idempotency-Key": f"publish-{uuid.uuid4().hex}",
            },
        )

    def current_revision(self):
        view = self.client.get(self.association_root)
        self.assertEqual(view.status_code, 200, view.text)
        source = view.json()["impact"]["source"]
        return {
            "revision_id": source["current_revision_id"],
            "content_hash": source["current_content_hash"],
        }

    # -- AC-SHR-01, AC-SHR-02 ---------------------------------------------

    def test_the_association_view_shows_the_whole_impact_before_deciding(self):
        response = self.client.get(f"{self.association_root}?intent=local")

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        impact = payload["impact"]
        self.assertEqual(impact["source"]["set_id"], self.set_id)
        self.assertEqual(impact["source"]["visibility_scope"], "global")
        self.assertEqual(impact["source"]["owner_project_id"], self.project["id"])
        self.assertTrue(impact["source"]["current_revision_id"])
        self.assertTrue(
            impact["source"]["current_content_hash"].startswith("sha256:")
        )
        self.assertEqual(impact["associations"], {"total": 2, "other_objects": 1})
        self.assertEqual(impact["bindings"]["total_active"], 0)
        self.assertEqual(impact["effect"]["bindings_will_become_stale"], 0)
        self.assertEqual(
            [
                consumer["linkable_object_id"]
                for consumer in impact["listed_consumers"]
            ],
            [self.object["id"], self.neighbour_object["id"]],
        )
        self.assertEqual(
            sorted(
                {consumer["project_id"] for consumer in impact["listed_consumers"]}
            ),
            sorted([self.project["id"], self.neighbour["id"]]),
        )
        self.assertFalse(impact["consumers_truncated"])
        self.assertTrue(payload["requires_confirmation"])
        self.assertEqual(
            [alternative["kind"] for alternative in payload["alternatives"]],
            ["derive_object_specific", "publish_shared"],
        )

    # -- SHARED_TARGET is reachable only through a real association --------

    def test_a_fabricated_or_foreign_association_never_opens_shared_target(self):
        self.login(self.admin_email, "admin pass")

        fabricated = post_json_with_csrf(
            self.client,
            f"{self.object_root}/catalog-associations/987654"
            "/shared-series/revision-ingestions/points",
            self.shared_points(),
        )
        foreign = post_json_with_csrf(
            self.client,
            f"{self.object_root}/catalog-associations/"
            f"{self.neighbour_association_id}"
            "/shared-series/revision-ingestions/points",
            self.shared_points(),
        )

        for response in (fabricated, foreign):
            self.assertEqual(response.status_code, 404, response.text)
            self.assertEqual(
                response.headers["content-type"].split(";")[0],
                "application/problem+json",
            )
            self.assertEqual(
                response.json()["code"], "TS_OBJECT_SERIES_NOT_FOUND"
            )

    def test_a_shared_batch_answers_the_impact_and_always_needs_confirmation(self):
        self.login(self.admin_email, "admin pass")

        prepared = post_json_with_csrf(
            self.client,
            f"{self.association_root}/shared-series/revision-ingestions/points",
            self.shared_points(),
        )

        self.assertEqual(prepared.status_code, 201, prepared.text)
        ingestion = prepared.json()["ingestion"]
        self.assertEqual(ingestion["state"], "ready_to_publish")
        self.assertEqual(
            ingestion["target"],
            {
                "source_kind": "catalog",
                "signal_id": self.signal_id,
                "set_id": self.set_id,
                "association_id": self.association_id,
            },
        )
        self.assertTrue(ingestion["requires_confirmation"])
        self.assertTrue(ingestion["impact_fingerprint"].startswith("tsi_"))
        self.assertEqual(
            ingestion["impact"]["source"]["visibility_scope"], "global"
        )
        self.assertEqual(
            ingestion["impact"]["associations"], {"total": 2, "other_objects": 1}
        )
        self.assertTrue(ingestion["validation_token"])

    # -- AC-SHR-04, AC-SHR-05 ---------------------------------------------

    def test_an_analyst_may_not_publish_a_global_source(self):
        refused = post_json_with_csrf(
            self.client,
            f"{self.association_root}/shared-series/revision-ingestions/points",
            self.shared_points(),
        )

        self.assertEqual(refused.status_code, 403, refused.text)
        payload = refused.json()
        self.assertEqual(payload["code"], "TS_SHARED_REVISION_ADMIN_REQUIRED")
        self.assertEqual(payload["context"]["visibility_scope"], "global")
        self.assertEqual(payload["context"]["required_role"], "admin")

    def test_publishing_for_everyone_needs_an_explicit_confirmation(self):
        self.login(self.admin_email, "admin pass")
        ingestion = self.prepare_shared()

        unconfirmed = self.publish_shared(ingestion, confirm=False)
        unacknowledged = self.publish_shared(
            ingestion, comprehension_acknowledged=False
        )

        for response, missing in (
            (unconfirmed, "confirm"),
            (unacknowledged, "comprehension_acknowledged"),
        ):
            self.assertEqual(response.status_code, 409, response.text)
            payload = response.json()
            self.assertEqual(
                payload["code"], "TS_SHARED_REVISION_CONFIRMATION_REQUIRED"
            )
            self.assertEqual(payload["context"]["missing"], missing)
            self.assertIn("impact", payload["context"])

    # -- AC-SHR-08 ---------------------------------------------------------

    def test_publishing_for_everyone_leaves_the_stale_states_visible(self):
        binding_id = self.bind_the_shared_source()
        base = self.current_revision()
        self.login(self.admin_email, "admin pass")
        ingestion = self.prepare_shared()
        self.assertEqual(ingestion["impact"]["bindings"]["total_active"], 1)
        self.assertEqual(ingestion["impact"]["bindings"]["current"], 1)
        self.assertEqual(
            ingestion["impact"]["effect"]["bindings_will_become_stale"], 1
        )

        published = self.publish_shared(ingestion)

        self.assertEqual(published.status_code, 201, published.text)
        publication = published.json()["publication"]
        self.assertEqual(publication["outcome"], "published")
        self.assertNotEqual(publication["revision_id"], base["revision_id"])
        self.assertEqual(
            publication["staleness"],
            {
                "bindings_now_stale": 1,
                "bindings_still_stale": 1,
                "resolved_in_this_action": 0,
                "resolution_required": True,
            },
        )

        detail = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case-variants/"
            f"{self.variant['id']}/time-series-bindings/{binding_id}"
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["state"], "stale")
        self.assertEqual(detail.json()["set_revision_id"], base["revision_id"])
        self.assertEqual(
            detail.json()["revision"]["current_revision_id"],
            publication["revision_id"],
        )

    # -- AC-SHR-06 ---------------------------------------------------------

    def test_an_impact_that_moved_since_the_preview_blocks_the_confirmation(self):
        self.login(self.admin_email, "admin pass")
        ingestion = self.prepare_shared()
        self.assertEqual(ingestion["impact"]["bindings"]["total_active"], 0)

        self.bind_the_shared_source()
        blocked = self.publish_shared(ingestion)

        self.assertEqual(blocked.status_code, 412, blocked.text)
        payload = blocked.json()
        self.assertEqual(payload["code"], "TS_INGEST_PRECONDITION_CHANGED")
        self.assertTrue(payload["context"]["requires_new_confirmation"])
        self.assertEqual(payload["context"]["impact"]["bindings"]["total_active"], 1)
        self.assertNotEqual(
            payload["context"]["impact_fingerprint"],
            ingestion["impact_fingerprint"],
        )

        refreshed = self.client.get(
            f"{self.association_root}/shared-series/revision-ingestions/"
            f"{ingestion['ingestion_id']}"
        )
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        retried = self.publish_shared(refreshed.json()["ingestion"])
        self.assertEqual(retried.status_code, 201, retried.text)

    # -- AC-SHR-07 ---------------------------------------------------------

    def derivation_request(self, **overrides):
        body = {
            "object_series_key": "local_price_copy",
            "display_name": "Precio local (copia)",
            "description": "Copia local del precio compartido",
            "reason_code": "local_copy_preferred",
            "reason_text": "El objeto necesita su propia curva",
        }
        body.update(overrides)
        return body

    def test_deriving_a_local_copy_keeps_lineage_and_reassigns_nothing(self):
        binding_id = self.bind_the_shared_source()
        source = self.current_revision()

        prevalidated = post_json_with_csrf(
            self.client,
            f"{self.association_root}/object-series-derivation-prevalidations",
            self.derivation_request(),
        )
        self.assertEqual(prevalidated.status_code, 200, prevalidated.text)
        prevalidation = prevalidated.json()
        self.assertTrue(prevalidation["can_commit"])
        self.assertEqual(
            prevalidation["source"]["revision_id"], source["revision_id"]
        )
        self.assertEqual(
            prevalidation["source"]["content_hash"], source["content_hash"]
        )
        self.assertEqual(
            prevalidation["reassignments"], {"associations": 0, "bindings": 0}
        )
        self.assertEqual(prevalidation["proposed"]["period_count"], 2)

        derived = self.client.post(
            f"{self.association_root}/object-series-derivations",
            json={
                **self.derivation_request(),
                "prevalidation_token": prevalidation["prevalidation_token"],
                "confirmed": True,
                "source_revision": {
                    "revision_id": source["revision_id"],
                    "content_hash": source["content_hash"],
                },
            },
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": f"derive-{uuid.uuid4().hex}",
            },
        )

        self.assertEqual(derived.status_code, 201, derived.text)
        payload = derived.json()["derivation"]
        series = payload["object_series"]
        self.assertEqual(series["object_series_key"], "local_price_copy")
        self.assertEqual(series["availability"], "ready")
        self.assertTrue(series["binding_ready"])
        self.assertEqual(series["current_revision"]["period_count"], 2)
        self.assertEqual(payload["lineage"]["kind"], "catalog_object_specific_copy")
        self.assertEqual(
            payload["lineage"]["source_revision_id"], source["revision_id"]
        )
        self.assertEqual(payload["reassignments"], {"associations": 0, "bindings": 0})

        # The shared source is untouched: same pointer, same hash.
        self.assertEqual(self.current_revision(), source)

        # The association keeps its identity, and the binding keeps pointing at
        # the catalog signal it was created against.
        association = self.client.get(self.association_root).json()["association"]
        self.assertEqual(association["status"], "active")
        self.assertEqual(association["signal_id"], self.signal_id)
        binding = self.client.get(
            f"/api/scenarios/{self.scenario['id']}/case-variants/"
            f"{self.variant['id']}/time-series-bindings/{binding_id}"
        ).json()
        self.assertEqual(binding["signal_id"], self.signal_id)
        self.assertEqual(binding["state"], "valid_current")

    def test_the_derived_copy_records_its_lineage_in_the_canonical_tables(self):
        source = self.current_revision()
        derived = self.client.post(
            f"{self.association_root}/object-series-derivations",
            json={
                **self.derivation_request(),
                "confirmed": True,
                "source_revision": {
                    "revision_id": source["revision_id"],
                    "content_hash": source["content_hash"],
                },
            },
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": f"derive-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(derived.status_code, 201, derived.text)
        series = derived.json()["derivation"]["object_series"]

        lineage = self.store.connection.execute(
            f"SELECT * FROM {self.store._canonical('time_series_revision_lineage')} "
            "WHERE derived_signal_id = ?",
            (series["signal_id"],),
        ).fetchall()

        self.assertEqual(len(lineage), 1)
        row = dict(lineage[0])
        self.assertEqual(row["lineage_kind"], "catalog_object_specific_copy")
        self.assertEqual(row["source_signal_id"], self.signal_id)
        self.assertEqual(row["source_set_revision_id"], source["revision_id"])
        self.assertEqual(
            f"sha256:{row['source_content_hash']}", source["content_hash"]
        )
        self.assertEqual(
            row["target_owner_linkable_object_id"], self.object["id"]
        )

    def test_an_analyst_derives_from_a_source_they_may_not_publish(self):
        refused = post_json_with_csrf(
            self.client,
            f"{self.association_root}/shared-series/revision-ingestions/points",
            self.shared_points(),
        )
        self.assertEqual(refused.status_code, 403, refused.text)

        view = self.client.get(f"{self.association_root}?intent=local").json()
        self.assertTrue(view["derivation_required"])
        self.assertEqual(
            view["derivation_required_codes"],
            ["TS_SHARED_REVISION_ADMIN_REQUIRED"],
        )
        self.assertEqual(view["recommendation"], "derive_object_specific")
        self.assertEqual(
            [alternative["kind"] for alternative in view["alternatives"]],
            ["derive_object_specific", "publish_shared"],
        )
        self.assertFalse(view["alternatives"][1]["available"])
        self.assertEqual(
            view["alternatives"][1]["unavailable_code"],
            "TS_SHARED_REVISION_ADMIN_REQUIRED",
        )

        source = self.current_revision()
        derived = self.client.post(
            f"{self.association_root}/object-series-derivations",
            json={
                **self.derivation_request(),
                "confirmed": True,
                "source_revision": {
                    "revision_id": source["revision_id"],
                    "content_hash": source["content_hash"],
                },
            },
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": f"derive-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(derived.status_code, 201, derived.text)

    # -- The remaining guards of chapter 7.9 -------------------------------

    def test_an_unconfirmed_derivation_is_refused(self):
        source = self.current_revision()

        refused = self.client.post(
            f"{self.association_root}/object-series-derivations",
            json={
                **self.derivation_request(),
                "source_revision": {
                    "revision_id": source["revision_id"],
                    "content_hash": source["content_hash"],
                },
            },
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": f"derive-{uuid.uuid4().hex}",
            },
        )

        self.assertEqual(refused.status_code, 409, refused.text)
        self.assertEqual(
            refused.json()["code"], "TS_LINK_CONFIRMATION_REQUIRED"
        )

    def test_a_partial_payload_on_a_multi_signal_set_forces_the_derivation(self):
        pair_association_id = self.associate_multi_signal_set()
        self.login(self.admin_email, "admin pass")
        association_root = (
            f"{self.object_root}/catalog-associations/{pair_association_id}"
        )
        source = self.client.get(association_root).json()["impact"]["source"]

        partial = post_json_with_csrf(
            self.client,
            f"{association_root}/shared-series/revision-ingestions/points",
            {
                "mode": "replace_full",
                "expected_base": {
                    "revision_id": source["current_revision_id"],
                    "content_hash": source["current_content_hash"],
                },
                "source": {"kind": "api", "display_name": "Mesa de precios"},
                "points": [
                    {
                        "timestamp_start": "2026-01-01T00:00:00+00:00",
                        "duration_seconds": 3600,
                        "values": {"pair_price": {"value": 91.0}},
                    }
                ],
            },
        )

        self.assertEqual(partial.status_code, 422, partial.text)
        payload = partial.json()
        self.assertEqual(payload["code"], "TS_INGEST_VALIDATION_FAILED")
        self.assertIn(
            "TS_INGEST_SIGNAL_SET_INCOMPLETE", payload["error_counts"]
        )
        ingestion = payload["context"]["ingestion"]
        self.assertEqual(ingestion["state"], "invalid")
        self.assertTrue(ingestion["derivation_required"])
        self.assertEqual(
            ingestion["derivation_required_codes"],
            ["TS_INGEST_SIGNAL_SET_INCOMPLETE"],
        )
        self.assertEqual(
            ingestion["alternatives"][0]["kind"], "derive_object_specific"
        )

    def associate_multi_signal_set(self):
        self.store.publish_canonical_set_revision(
            project_id=self.project["id"],
            name=f"Inputs pareados {uuid.uuid4().hex[:10]}",
            data_class_key="real",
            timezone="UTC",
            signals=[
                {
                    "series_key": "pair_price",
                    "display_name": "Precio pareado",
                    "semantic_type_key": "energy_price",
                    "unit_key": "usd_per_mwh",
                    "signal_role": "input",
                    "aggregation": "mean",
                },
                {
                    "series_key": "pair_price_alt",
                    "display_name": "Precio pareado alterno",
                    "semantic_type_key": "energy_price",
                    "unit_key": "usd_per_mwh",
                    "signal_role": "input",
                    "aggregation": "mean",
                },
            ],
            periods=PERIODS[:1],
            values={"pair_price": [90.0], "pair_price_alt": [95.0]},
            actor=self.analyst_email,
        )
        signal_id = next(
            item["signal_id"]
            for item in self.client.get("/api/time-series/catalog/inputs").json()[
                "items"
            ]
            if item["identity"]["series_key"] == "pair_price"
        )
        previous_signal_id, self.signal_id = self.signal_id, signal_id
        try:
            return self.associate(
                project_id=self.project["id"],
                linkable_object_id=self.object["id"],
            )
        finally:
            self.signal_id = previous_signal_id

    def test_a_derivation_must_pin_the_source_revision_it_compared(self):
        unpinned = self.client.post(
            f"{self.association_root}/object-series-derivations",
            json={**self.derivation_request(), "confirmed": True},
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": f"derive-{uuid.uuid4().hex}",
            },
        )

        self.assertEqual(unpinned.status_code, 428, unpinned.text)
        payload = unpinned.json()
        self.assertEqual(payload["code"], "TS_INGEST_PRECONDITION_REQUIRED")
        self.assertEqual(payload["context"]["field"], "source_revision")

        source = self.current_revision()
        moved = self.client.post(
            f"{self.association_root}/object-series-derivations",
            json={
                **self.derivation_request(),
                "confirmed": True,
                "source_revision": {
                    "revision_id": source["revision_id"] + 1,
                    "content_hash": source["content_hash"],
                },
            },
            headers={
                **csrf_headers(self.client),
                "Idempotency-Key": f"derive-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(moved.status_code, 412, moved.text)
        self.assertEqual(
            moved.json()["code"], "TS_INGEST_PRECONDITION_CHANGED"
        )

    def test_a_batch_that_fails_for_another_reason_is_not_called_incomplete(self):
        self.login(self.admin_email, "admin pass")
        payload = self.shared_points()
        payload["points"][1]["timestamp_start"] = "not-a-timestamp"

        refused = post_json_with_csrf(
            self.client,
            f"{self.association_root}/shared-series/revision-ingestions/points",
            payload,
        )

        self.assertEqual(refused.status_code, 422, refused.text)
        body = refused.json()
        self.assertEqual(
            sorted(body["error_counts"]), ["TS_INGEST_TIMESTAMP_INVALID"]
        )
        ingestion = body["context"]["ingestion"]
        self.assertEqual(ingestion["state"], "invalid")
        self.assertFalse(ingestion["derivation_required"])
        self.assertEqual(ingestion["derivation_required_codes"], [])
        self.assertEqual(
            ingestion["alternatives"][0]["kind"], "publish_shared"
        )

    def test_an_archived_association_does_not_open_the_shared_flow(self):
        archive = {
            "target_project_id": self.project["id"],
            "operations": [
                {
                    "client_operation_id": "archive-price",
                    "action": "archive",
                    "association_id": self.association_id,
                    "expected_lifecycle_revision": 1,
                    "reason_code": "association_no_longer_needed",
                    "reason_text": "El objeto usara una copia local",
                }
            ],
        }
        prevalidation = post_json_with_csrf(
            self.client,
            "/api/time-series/catalog/association-prevalidations",
            archive,
        )
        self.assertEqual(prevalidation.status_code, 200, prevalidation.text)
        archived = self.client.post(
            "/api/time-series/catalog/association-batches",
            json={
                **archive,
                "prevalidation_token": prevalidation.json()["prevalidation_token"],
                "confirmed": True,
            },
            headers={
                **csrf_headers(self.client),
                "If-Match": prevalidation.json()["commit_etag"],
                "Idempotency-Key": f"archive-{uuid.uuid4().hex}",
            },
        )
        self.assertEqual(archived.status_code, 201, archived.text)
        self.login(self.admin_email, "admin pass")

        refused = post_json_with_csrf(
            self.client,
            f"{self.association_root}/shared-series/revision-ingestions/points",
            self.shared_points(),
        )

        self.assertEqual(refused.status_code, 404, refused.text)
        self.assertEqual(refused.json()["code"], "TS_OBJECT_SERIES_NOT_FOUND")
        # The contextual read still works, and it says both outcomes are closed.
        view = self.client.get(self.association_root)
        self.assertEqual(view.status_code, 200, view.text)
        self.assertEqual(view.json()["association"]["status"], "archived")
        self.assertFalse(view.json()["capabilities"]["publish_shared"])
        self.assertFalse(view.json()["capabilities"]["derive_object_specific"])


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "set POSTGRES_TEST_DATABASE_URL to run the PostgreSQL contract tests",
)
class PostgresSharedGenericRevisionApiTests(SharedGenericRevisionApiTests):
    """Mirror the complete HTTP contract on the reference engine."""

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
